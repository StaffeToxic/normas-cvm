"""Polite sequential HTTP transport with robots.txt checks and audit logging."""

from __future__ import annotations

import json
import math
import posixpath
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import SplitResult, unquote, urljoin, urlsplit, urlunsplit

from cvm_archive.models import Artifact

__all__ = ["DEFAULT_USER_AGENT", "BlockedError", "FetchError", "PoliteClient"]

DEFAULT_USER_AGENT = (
    "NormasCVMResearch/0.5 (+https://github.com/StaffeToxic/normas-cvm; polite collection)"
)

_API_HOST = "dados.cvm.gov.br"
_BLOCKED_STATUSES = frozenset({401, 403, 429})
_MISSING_ROBOTS_STATUSES = frozenset({404, 410})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_FALLBACK_CONTENT_TYPE = "application/octet-stream"

_EXT_BY_MEDIA_TYPE = {
    "application/json": "json",
    "application/msword": "doc",
    "application/pdf": "pdf",
    "application/rss+xml": "xml",
    "application/xhtml+xml": "html",
    "text/html": "html",
    "text/plain": "txt",
    "text/xml": "xml",
}

_ROBOTS_UNSET = object()
_ROBOTS_ALLOW_ALL = object()


class FetchError(Exception):
    """HTTP or transport failure that carries its status and reason."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(f"HTTP {status}: {reason}" if status is not None else reason)
        self.reason = reason
        self.status = status


class BlockedError(FetchError):
    """Access denied; collection must stop instead of bypassing."""

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(reason, status=status)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


class _RobotsBlocked:
    def __init__(self, reason: str, status: int | None) -> None:
        self.reason = reason
        self.status = status


class _HostState:
    def __init__(self) -> None:
        self.last_sent: float | None = None
        self.requests = 0
        self.robots_checks = 0
        self.failures = 0


class _ResponseView:
    __slots__ = ("status", "reason", "headers", "url", "payload")

    def __init__(self, status, reason, headers, url, payload) -> None:
        self.status = status
        self.reason = reason
        self.headers = headers
        self.url = url
        self.payload = payload


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect())


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _url_parts(url: str) -> SplitResult:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials are not allowed in source URLs")
    _ = parsed.port
    return parsed


def _host_key(parsed: SplitResult) -> str:
    return (parsed.hostname or "").rstrip(".").lower()


def _origin(parsed: SplitResult) -> str:
    host = _host_key(parsed)
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    if port is not None and port != {"http": 80, "https": 443}[parsed.scheme]:
        host = f"{host}:{port}"
    return f"{parsed.scheme}://{host}"


def _policy_path(path: str) -> str:
    for _ in range(8):
        decoded = unquote(path, errors="strict")
        if decoded == path:
            return "/" + posixpath.normpath(decoded.replace("\\", "/")).lstrip("/")
        path = decoded
    raise BlockedError("ambiguous-path-encoding")


def _header(response: _ResponseView, name: str) -> str:
    headers = response.headers
    if headers is None:
        return ""
    value = headers.get(name)
    return value if isinstance(value, str) else ""


def _cache_extension(content_type: str) -> str:
    media = content_type.split(";", 1)[0].strip().lower()
    ext = _EXT_BY_MEDIA_TYPE.get(media)
    if ext is None:
        subtype = media.split("/")[-1] if "/" in media else ""
        ext = subtype if subtype.replace("-", "").isalnum() else "bin"
    return ext


def _robots_text(response: _ResponseView) -> str:
    payload = response.payload
    if isinstance(payload, str):
        return payload
    return bytes(payload).decode("utf-8", errors="replace")


def _response_view(response: object, url: str, payload: bytes) -> _ResponseView:
    getter = getattr(response, "geturl", None)
    effective = getter() if callable(getter) else None
    if not effective:
        effective = url
    status = getattr(response, "status", None)
    if status is None:
        status = getattr(response, "code", None) or 200
    reason = getattr(response, "reason", None) or ""
    return _ResponseView(status, reason, getattr(response, "headers", None), effective, payload)


def _error_view(error: urllib.error.HTTPError, url: str) -> _ResponseView:
    status = getattr(error, "code", None) or getattr(error, "status", None) or 500
    reason = getattr(error, "reason", None) or ""
    try:
        payload = error.read() or b""
    except (AttributeError, OSError):
        payload = b""
    finally:
        error.close()
    effective = getattr(error, "url", None) or url
    return _ResponseView(status, reason, getattr(error, "headers", None), effective, payload)


class PoliteClient:
    """Sequential fetcher: one request at a time, spaced per host, robots first."""

    MAX_HOPS = 10

    def __init__(
        self,
        *,
        min_interval: float = 5.0,
        user_agent: str | None = None,
        cache_dir: str | Path | None = None,
        log_path: str | Path | None = None,
        timeout: float | None = 30.0,
        opener=None,
        clock=None,
        monotonic=None,
        sleep=None,
    ) -> None:
        if (
            not isinstance(min_interval, (int, float))
            or not math.isfinite(min_interval)
            or min_interval < 5.0
        ):
            raise ValueError("min_interval must be at least 5 seconds")
        self.min_interval = float(min_interval)
        self.user_agent = user_agent if user_agent is not None else DEFAULT_USER_AGENT
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must identify the collector")
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.log_path = Path(log_path) if log_path is not None else None
        self.timeout = timeout
        self._opener = opener if opener is not None else _default_opener()
        self._clock = clock if clock is not None else _default_clock
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._sleep = sleep if sleep is not None else time.sleep
        self._states: dict[str, _HostState] = {}
        self._robots: dict[str, object] = {}
        self._lock = threading.Lock()
        self.events: list[dict[str, object]] = []

    def fetch(self, url: str) -> Artifact:
        with self._lock:
            return self._fetch(url)

    def _fetch(self, url: str) -> Artifact:
        parsed = _url_parts(url)
        current = url
        hops: list[dict[str, object]] = []
        while True:
            self._assert_api_allowed(current)
            state = self._ensure_robots(parsed)
            self._check_robots(current, state)
            response = self._send("content", current)
            if response.status in _REDIRECT_STATUSES:
                target = self._redirect_target(current, response)
                self._record(
                    {
                        "event": "redirect",
                        "url": current,
                        "to": target,
                        "status": response.status,
                    }
                )
                hops.append({"url": current, "status": response.status})
                if len(hops) >= self.MAX_HOPS:
                    state.failures += 1
                    self._record({"event": "fail", "url": target, "reason": "too-many-redirects"})
                    raise FetchError("too-many-redirects")
                try:
                    parsed = _url_parts(target)
                except ValueError as error:
                    state.failures += 1
                    self._record({"event": "fail", "url": target, "reason": "invalid-redirect-target"})
                    raise FetchError("invalid-redirect-target") from error
                current = target
                continue
            if response.status in _BLOCKED_STATUSES:
                state.failures += 1
                self._record({"event": "fail", "url": current, "status": response.status})
                raise BlockedError(response.reason or "blocked", status=response.status)
            if response.status >= 500:
                state.failures += 1
                self._record({"event": "fail", "url": current, "status": response.status})
                raise FetchError(response.reason or "server-error", status=response.status)
            if not 200 <= response.status < 300:
                state.failures += 1
                self._record({"event": "fail", "url": current, "status": response.status})
                raise FetchError(response.reason or "http-error", status=response.status)
            fetched_at = self._clock().isoformat()
            content_type = _header(response, "Content-Type").strip() or _FALLBACK_CONTENT_TYPE
            artifact = Artifact.from_bytes(
                current, response.payload, content_type, fetched_at
            )
            self._write_cache(artifact)
            self._record(
                {
                    "event": "fetched",
                    "url": current,
                    "status": response.status,
                    "sha256": artifact.sha256,
                    "hops": hops,
                }
            )
            return artifact

    @property
    def stats(self) -> dict[str, dict[str, int]]:
        return {
            netloc: {
                "requests": state.requests,
                "robots_checks": state.robots_checks,
                "failures": state.failures,
            }
            for netloc, state in self._states.items()
        }

    def _send(self, kind: str, url: str) -> _ResponseView:
        self._assert_api_allowed(url)
        netloc = _host_key(_url_parts(url))
        state = self._host(netloc)
        if kind == "robots":
            state.robots_checks += 1
        state.requests += 1
        self._throttle(netloc)
        self._record({"event": "request", "kind": kind, "url": url})
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        state.last_sent = self._monotonic()
        try:
            raw = self._opener.open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            return _error_view(error, url)
        except OSError as error:
            detail = getattr(error, "reason", error)
            state.failures += 1
            self._record({"event": "transport-failure", "kind": kind, "url": url, "reason": str(detail)})
            raise FetchError("transport-error") from error
        try:
            payload = raw.read()
            return _response_view(raw, url, payload)
        except OSError as error:
            state.failures += 1
            self._record({"event": "transfer-failure", "kind": kind, "url": url, "reason": str(error)})
            raise FetchError("transfer-error") from error
        finally:
            close = getattr(raw, "close", None)
            if callable(close):
                close()

    def _throttle(self, netloc: str) -> None:
        state = self._host(netloc)
        if state.last_sent is None:
            return
        elapsed = self._monotonic() - state.last_sent
        wait = self.min_interval - elapsed
        if wait > 0:
            self._record({"event": "wait", "host": netloc, "seconds": round(wait, 3)})
            self._sleep(wait)

    def _ensure_robots(self, parsed: SplitResult) -> _HostState:
        state = self._host(_host_key(parsed))
        origin = _origin(parsed)
        policy = self._robots.get(origin, _ROBOTS_UNSET)
        if policy is _ROBOTS_ALLOW_ALL:
            return state
        if isinstance(policy, _RobotsBlocked):
            raise BlockedError(policy.reason, status=policy.status)
        if policy is not _ROBOTS_UNSET:
            return state
        robots_url = origin + "/robots.txt"
        for _ in range(self.MAX_HOPS):
            response = self._send("robots", robots_url)
            if response.status in _REDIRECT_STATUSES:
                location = _header(response, "Location").strip()
                if not location:
                    state.failures += 1
                    self._record({"event": "robots-error", "url": robots_url, "status": response.status})
                    self._robots[origin] = _RobotsBlocked("robots-fetch-error", response.status)
                    raise BlockedError("robots-fetch-error", status=response.status)
                candidate = urljoin(robots_url, location)
                self._assert_api_allowed(candidate)
                try:
                    target_parts = _url_parts(candidate)
                except ValueError as error:
                    state.failures += 1
                    self._record({"event": "robots-error", "url": candidate, "reason": "invalid-robots-location"})
                    self._robots[origin] = _RobotsBlocked("invalid-robots-location", None)
                    raise FetchError("invalid-robots-location") from error
                # A redirected robots resource bootstraps the INITIAL origin's
                # policy (RFC 9309, 2.3.1.2). Limit this exception to robots.txt;
                # content redirects still require the destination's own policy.
                if (
                    _origin(target_parts) != origin
                    and not _policy_path(target_parts.path).endswith("/robots.txt")
                ):
                    state.failures += 1
                    self._robots[origin] = _RobotsBlocked("cross-origin-robots-redirect", None)
                    self._record({"event": "robots-error", "url": candidate,
                                  "reason": "cross-origin-robots-redirect"})
                    raise BlockedError("cross-origin-robots-redirect")
                self._record({"event": "redirect", "url": robots_url, "to": candidate, "status": response.status})
                robots_url = candidate
                continue
            if response.status in _BLOCKED_STATUSES:
                state.failures += 1
                self._record({"event": "robots-blocked", "url": robots_url, "status": response.status})
                self._robots[origin] = _RobotsBlocked("robots-fetch-blocked", response.status)
                raise BlockedError("robots-fetch-blocked", status=response.status)
            if response.status >= 500:
                state.failures += 1
                self._record({"event": "robots-error", "url": robots_url, "status": response.status})
                self._robots[origin] = _RobotsBlocked("robots-fetch-error", response.status)
                raise BlockedError("robots-fetch-error", status=response.status)
            if response.status in _MISSING_ROBOTS_STATUSES:
                self._record(
                    {
                        "event": "robots-missing",
                        "url": robots_url,
                        "status": response.status,
                        "allow_all": True,
                    }
                )
                self._robots[origin] = _ROBOTS_ALLOW_ALL
                return state
            if not 200 <= response.status < 300:
                state.failures += 1
                self._record({"event": "robots-error", "url": robots_url, "status": response.status})
                self._robots[origin] = _RobotsBlocked("robots-fetch-error", response.status)
                raise BlockedError("robots-fetch-error", status=response.status)
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(_robots_text(response).splitlines())
            self._robots[origin] = parser
            self._record({"event": "robots-checked", "url": robots_url,
                          "origin": origin, "status": response.status})
            return state
        state.failures += 1
        self._robots[origin] = _RobotsBlocked("too-many-redirects", None)
        raise FetchError("too-many-redirects")

    def _check_robots(self, url: str, state: _HostState) -> None:
        parsed = _url_parts(url)
        policy = self._robots[_origin(parsed)]
        if policy is _ROBOTS_ALLOW_ALL:
            return
        parser = policy
        if not isinstance(parser, urllib.robotparser.RobotFileParser):
            raise RuntimeError("robots.txt state invariant was broken")
        policy_url = urlunsplit(parsed._replace(path=_policy_path(parsed.path or "/")))
        if not parser.can_fetch(self.user_agent, policy_url):
            state.failures += 1
            self._record({"event": "robots-blocked", "url": url, "reason": "disallowed-path"})
            raise BlockedError("disallowed-by-robots", status=None)

    def _assert_api_allowed(self, url: str) -> None:
        parsed = _url_parts(url)
        host = _host_key(parsed)
        path = _policy_path(parsed.path or "/").lower()
        if host == _API_HOST and (path == "/api" or path.startswith("/api/")):
            state = self._host(host)
            state.failures += 1
            self._record({"event": "api-refused", "url": url})
            raise BlockedError("api-forbidden", status=None)

    def _redirect_target(self, current: str, response: _ResponseView) -> str:
        location = _header(response, "Location").strip()
        if not location:
            raise FetchError("redirect-without-location", status=response.status)
        return urljoin(current, location)

    def _write_cache(self, artifact: Artifact) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = artifact.sha256
        ext = _cache_extension(artifact.content_type)
        (self.cache_dir / f"{key}.{ext}").write_bytes(artifact.bytes)
        meta = {
            "url": artifact.url,
            "sha256": artifact.sha256,
            "content_type": artifact.content_type,
            "fetched_at": artifact.fetched_at,
        }
        (self.cache_dir / f"{key}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )

    def _record(self, record: dict[str, object]) -> None:
        entry = {"ts": self._clock().isoformat(), "monotonic": self._monotonic(), **record}
        self.events.append(entry)
        if self.log_path is not None:
            parent = self.log_path.parent
            if str(parent):
                parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    def _host(self, netloc: str) -> _HostState:
        return self._states.setdefault(netloc, _HostState())
