"""Polite transport tests with injected openers and clocks; no network access."""

import hashlib
import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cvm_archive.fetch.client import BlockedError, FetchError, PoliteClient

USER_AGENT = "FetchDriver/1.0 (+https://github.com/StaffeToxic/normas-cvm; unit-tests)"
T0 = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)

ROBOTS_RESTRICTED = "User-agent: *\nDisallow: /restrito/\n"


class FakeResponse:
    def __init__(self, url, status, headers, body, reason):
        self.status = status
        self.reason = reason
        self.headers = headers
        self.url = url
        self._body = body
        self.closed = False

    def geturl(self):
        return self.url

    def read(self):
        return self._body

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, routes):
        self.routes = dict(routes)
        self.requests = []
        self.responses = []

    def open(self, request, timeout=None):
        url = request.full_url
        self.requests.append({"url": url, "user_agent": request.headers["User-agent"]})
        route = self.routes.get(url)
        if isinstance(route, BaseException):
            raise route
        if route is None:
            raise ConnectionError(f"fake opener has no route for {url}")
        status, headers, body, reason = route
        response = FakeResponse(url, status, headers, body, reason)
        self.responses.append(response)
        return response

    def sent_urls(self):
        return [item["url"] for item in self.requests]


class FakeClock:
    def __init__(self):
        self.now = T0
        self.sleeps = []
        self.elapsed = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += timedelta(seconds=seconds)
        self.elapsed += seconds

    def monotonic(self):
        return self.elapsed


class FetchTestCase(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.scratch, ignore_errors=True)

    def client(self, routes, **options):
        clock = FakeClock()
        opener = FakeOpener(routes)
        passed = {"opener": opener, "clock": clock, "sleep": clock.sleep,
                  "monotonic": clock.monotonic}
        passed.update(options)
        client = PoliteClient(user_agent=USER_AGENT, **passed)
        return client, opener, clock


class ArtifactTests(FetchTestCase):
    def test_fetch_returns_artifact_with_exact_bytes(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, ROBOTS_RESTRICTED, "OK"),
                "https://a.test/doc": (200, {"Content-Type": "text/html; charset=utf-8"}, b"<h1>norma</h1>", "OK"),
            }
        )
        artifact = client.fetch("https://a.test/doc")
        self.assertEqual(artifact.url, "https://a.test/doc")
        self.assertEqual(artifact.bytes, b"<h1>norma</h1>")
        self.assertEqual(artifact.content_type, "text/html; charset=utf-8")
        self.assertEqual(artifact.sha256, hashlib.sha256(b"<h1>norma</h1>").hexdigest())
        self.assertEqual(artifact.fetched_at, (T0 + timedelta(seconds=5)).isoformat())
        self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt", "https://a.test/doc"])
        self.assertEqual(
            client.stats["a.test"],
            {"requests": 2, "robots_checks": 1, "failures": 0},
        )

    def test_default_user_agent_carries_repository_link(self):
        self.assertIn("https://github.com/StaffeToxic/normas-cvm", PoliteClient(user_agent=None).user_agent)

    def test_every_request_carries_the_user_agent(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (404, {}, "", "Not Found"),
                "https://a.test/doc": (200, {"Content-Type": "text/plain"}, b"doc", "OK"),
            }
        )
        client.fetch("https://a.test/doc")
        self.assertEqual(len(opener.requests), 2)
        for request in opener.requests:
            self.assertEqual(request["user_agent"], USER_AGENT)


class RobotsTests(FetchTestCase):
    def test_missing_robots_404_allows_the_page(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (404, {}, "", "Not Found"),
                "https://a.test/doc": (200, {"Content-Type": "text/plain"}, b"doc", "OK"),
            }
        )
        artifact = client.fetch("https://a.test/doc")
        self.assertEqual(artifact.bytes, b"doc")

    def test_missing_robots_410_allows_the_page(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (410, {}, "", "Gone"),
                "https://a.test/doc": (200, {"Content-Type": "text/plain"}, b"doc", "OK"),
            }
        )
        artifact = client.fetch("https://a.test/doc")
        self.assertEqual(artifact.bytes, b"doc")

    def test_robots_disallowed_path_is_never_requested(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, ROBOTS_RESTRICTED, "OK"),
                "https://a.test/doc": (200, {"Content-Type": "text/plain"}, b"doc", "OK"),
            }
        )
        with self.assertRaisesRegex(BlockedError, "robots"):
            client.fetch("https://a.test/restrito/doc")
        self.assertNotIn("https://a.test/restrito/doc", opener.sent_urls())
        self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt"])
        self.assertEqual(client.stats["a.test"]["failures"], 1)

    def test_api_path_is_refused_without_any_request(self):
        client, opener, _ = self.client({})
        with self.assertRaisesRegex(BlockedError, "api"):
            client.fetch("https://dados.cvm.gov.br/api/catalogo.json")
        self.assertEqual(opener.requests, [])
        self.assertEqual(client.stats["dados.cvm.gov.br"]["failures"], 1)

    def test_robots_server_500_stops_the_fetch(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (500, {}, "", "Internal Server Error"),
            }
        )
        with self.assertRaises(BlockedError) as caught:
            client.fetch("https://a.test/doc")
        self.assertEqual(caught.exception.status, 500)
        self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt"])
        self.assertEqual(client.stats["a.test"]["failures"], 1)


class RedirectTests(FetchTestCase):
    def test_redirect_chain_reaches_the_final_url(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, ROBOTS_RESTRICTED, "OK"),
                "https://a.test/moved": (301, {"Location": "https://a.test/doc"}, b"", "Moved Permanently"),
                "https://a.test/doc": (200, {"Content-Type": "text/html"}, b"<h1>norma</h1>", "OK"),
            }
        )
        artifact = client.fetch("https://a.test/moved")
        self.assertEqual(artifact.url, "https://a.test/doc")
        self.assertEqual(artifact.bytes, b"<h1>norma</h1>")
        fetched = [event for event in client.events if event["event"] == "fetched"]
        self.assertEqual(
            fetched[-1]["hops"], [{"url": "https://a.test/moved", "status": 301}]
        )

    def test_redirect_to_a_new_host_checks_robots_first(self):
        client, opener, clock = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                "https://a.test/doc": (302, {"Location": "https://b.test/doc"}, b"", "Found"),
                "https://b.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                "https://b.test/doc": (200, {"Content-Type": "text/plain"}, b"docs", "OK"),
            }
        )
        artifact = client.fetch("https://a.test/doc")
        self.assertEqual(opener.sent_urls(), [
            "https://a.test/robots.txt",
            "https://a.test/doc",
            "https://b.test/robots.txt",
            "https://b.test/doc",
        ])
        self.assertEqual(artifact.bytes, b"docs")
        self.assertGreaterEqual(sum(clock.sleeps), 5)

    def test_redirect_to_robots_disallowed_path_blocks_before_request(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, ROBOTS_RESTRICTED, "OK"),
                "https://a.test/doc": (302, {"Location": "/restrito/doc"}, b"", "Found"),
            }
        )
        with self.assertRaises(BlockedError) as caught:
            client.fetch("https://a.test/doc")
        self.assertEqual(caught.exception.reason, "disallowed-by-robots")
        self.assertNotIn("https://a.test/restrito/doc", opener.sent_urls())

    def test_redirect_into_the_api_path_blocks_before_request(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                "https://a.test/doc": (
                    302,
                    {"Location": "https://dados.cvm.gov.br/api/feed.xml"},
                    b"",
                    "Found",
                ),
            }
        )
        with self.assertRaises(BlockedError):
            client.fetch("https://a.test/doc")
        self.assertNotIn("https://dados.cvm.gov.br/api/feed.xml", opener.sent_urls())


class BlockAndErrorTests(FetchTestCase):
    def test_blocked_statuses_stop_collection_as_blocked_error(self):
        for status, phrase in ((401, "Unauthorized"), (403, "Forbidden"), (429, "Too Many Requests")):
            with self.subTest(status=status):
                client, opener, _ = self.client(
                    {
                        "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                        "https://a.test/doc": (status, {}, b"", phrase),
                    }
                )
                with self.assertRaises(BlockedError) as caught:
                    client.fetch("https://a.test/doc")
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.reason, phrase)
                self.assertEqual(client.stats["a.test"]["failures"], 1)

    def test_server_error_5xx_stops_without_retry_or_bypass(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                "https://a.test/doc": (503, {}, b"", "Service Unavailable"),
            }
        )
        with self.assertRaises(FetchError) as caught:
            client.fetch("https://a.test/doc")
        self.assertEqual(caught.exception.status, 503)
        self.assertNotIsInstance(caught.exception, BlockedError)
        self.assertEqual(
            opener.sent_urls(), ["https://a.test/robots.txt", "https://a.test/doc"]
        )
        self.assertEqual(client.stats["a.test"]["failures"], 1)

    def test_other_client_errors_carry_status(self):
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (404, {}, "", "Not Found"),
                "https://a.test/doc": (404, {}, b"", "Not Found"),
            }
        )
        with self.assertRaises(FetchError) as caught:
            client.fetch("https://a.test/doc")
        self.assertEqual(caught.exception.status, 404)


class IntervalTests(FetchTestCase):
    def test_requests_on_a_host_wait_at_least_min_interval(self):
        client, opener, clock = self.client(
            {
                "https://a.test/robots.txt": (200, {"Content-Type": "text/plain"}, "User-agent: *\n", "OK"),
                "https://a.test/doc-1": (200, {"Content-Type": "text/plain"}, b"one", "OK"),
                "https://a.test/doc-2": (200, {"Content-Type": "text/plain"}, b"two", "OK"),
                "https://b.test/robots.txt": (404, {}, "", "Not Found"),
                "https://b.test/doc": (200, {"Content-Type": "text/plain"}, b"three", "OK"),
            }
        )
        client.fetch("https://a.test/doc-1")
        client.fetch("https://a.test/doc-2")
        client.fetch("https://b.test/doc")
        self.assertEqual(clock.sleeps, [5.0, 5.0, 5.0])
        self.assertEqual(clock.now, T0 + timedelta(seconds=15))

    def test_min_interval_below_five_seconds_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "min_interval"):
            PoliteClient(min_interval=4.99, opener=FakeOpener({}))
        with self.assertRaisesRegex(ValueError, "min_interval"):
            PoliteClient(min_interval=0, opener=FakeOpener({}))
        client = PoliteClient(min_interval=5, opener=FakeOpener({}))
        self.assertEqual(client.min_interval, 5.0)


class PolicyRegressionTests(FetchTestCase):
    def test_encoded_api_paths_are_refused_before_any_request(self):
        paths = ["/%61pi/items", "/%2561pi/items", "/ignored/../api/items",
                 "/ignored/%2e%2e/%61pi/items", "//api/items", "/API/items",
                 "/ignored%5c..%5capi/items"]
        for path in paths:
            with self.subTest(path=path):
                client, opener, _ = self.client({})
                with self.assertRaises(BlockedError):
                    client.fetch("https://dados.cvm.gov.br" + path)
                self.assertEqual(opener.sent_urls(), [])

    def test_robots_redirect_cannot_access_the_api(self):
        for target in ["https://dados.cvm.gov.br/api/policy",
                       "https://dados.cvm.gov.br/%61pi/policy"]:
            with self.subTest(target=target):
                client, opener, _ = self.client({
                    "https://a.test/robots.txt": (302, {"Location": target}, b"", "Found"),
                })
                with self.assertRaises(BlockedError):
                    client.fetch("https://a.test/doc")
                self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt"])

    def test_cross_origin_robots_redirect_fails_closed(self):
        client, opener, _ = self.client({
            "https://a.test/robots.txt":
                (302, {"Location": "https://b.test/private/policy.txt"}, b"", "Found"),
        })
        with self.assertRaisesRegex(BlockedError, "cross-origin"):
            client.fetch("https://a.test/doc")
        self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt"])

    def test_encoded_and_dot_segment_paths_respect_robots(self):
        for path in ["/%2572estrito/doc", "/other/../restrito/doc"]:
            with self.subTest(path=path):
                client, opener, _ = self.client({
                    "https://a.test/robots.txt": (200, {}, ROBOTS_RESTRICTED, "OK"),
                })
                with self.assertRaises(BlockedError):
                    client.fetch("https://a.test" + path)
                self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt"])

    def test_non_finite_intervals_are_rejected(self):
        for value in [float("nan"), float("inf"), float("-inf")]:
            with self.subTest(interval=value), self.assertRaises(ValueError):
                PoliteClient(min_interval=value)

    def test_wall_clock_jumps_do_not_shorten_the_interval(self):
        client, _, clock = self.client({
            "https://a.test/robots.txt": (404, {}, b"", "Not Found"),
            "https://a.test/first": (200, {}, b"first", "OK"),
            "https://a.test/second": (200, {}, b"second", "OK"),
            "https://a.test/third": (200, {}, b"third", "OK"),
        })
        client.fetch("https://a.test/first")
        clock.now += timedelta(days=2)
        client.fetch("https://a.test/second")
        clock.now -= timedelta(days=4)
        client.fetch("https://a.test/third")
        requests = [e for e in client.events if e["event"] == "request"]
        self.assertEqual([e["monotonic"] for e in requests], [0, 5, 10, 15])
        self.assertEqual(clock.sleeps, [5, 5, 5])

    def test_origins_share_host_budget_but_not_robots(self):
        client, opener, clock = self.client({
            "https://a.test/robots.txt": (404, {}, b"", "Not Found"),
            "https://a.test.:443/first": (200, {}, b"first", "OK"),
            "http://a.test/robots.txt": (200, {}, "User-agent: *\nDisallow: /second\n", "OK"),
        })
        client.fetch("https://a.test.:443/first")
        with self.assertRaises(BlockedError):
            client.fetch("http://a.test/second")
        self.assertEqual(clock.sleeps, [5, 5])
        self.assertEqual(len(client.stats), 1)
        self.assertEqual(opener.sent_urls(), ["https://a.test/robots.txt",
                         "https://a.test.:443/first", "http://a.test/robots.txt"])

    def test_success_responses_are_closed(self):
        client, opener, _ = self.client({
            "https://a.test/robots.txt": (200, {}, b"User-agent: *\n", "OK"),
            "https://a.test/doc": (200, {}, b"doc", "OK"),
        })
        client.fetch("https://a.test/doc")
        self.assertEqual(len(opener.responses), 2)
        self.assertTrue(all(response.closed for response in opener.responses))

    def test_http_error_streams_are_closed(self):
        payload = io.BytesIO(b"not found")
        error = urllib.error.HTTPError("https://a.test/robots.txt", 404, "Not Found", {}, payload)
        client, _, _ = self.client({
            "https://a.test/robots.txt": error,
            "https://a.test/doc": (200, {}, b"doc", "OK"),
        })
        client.fetch("https://a.test/doc")
        self.assertTrue(payload.closed)

    def test_credentials_and_blank_identity_are_rejected(self):
        client, opener, _ = self.client({})
        with self.assertRaises(ValueError):
            client.fetch("https://user:secret@a.test/doc")
        self.assertEqual(opener.sent_urls(), [])
        with self.assertRaises(ValueError):
            PoliteClient(user_agent=" ")


class CacheAndAuditTests(FetchTestCase):
    def fetch_twice(self, cache_dir):
        payload = b"<h1>norma</h1>"
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (404, {}, "", "Not Found"),
                "https://a.test/doc": (200, {"Content-Type": "text/html"}, payload, "OK"),
            },
            cache_dir=cache_dir,
        )
        first = client.fetch("https://a.test/doc")
        second = client.fetch("https://a.test/doc")
        return first, second

    def test_cache_stores_exact_bytes_and_sha256(self):
        cache_dir = self.scratch / "cache"
        first, second = self.fetch_twice(cache_dir)
        self.assertEqual(first.sha256, second.sha256)
        bytes_path = cache_dir / f"{first.sha256}.html"
        meta_path = cache_dir / f"{first.sha256}.meta.json"
        self.assertTrue(bytes_path.is_file())
        self.assertEqual(bytes_path.read_bytes(), b"<h1>norma</h1>")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self.assertEqual(meta["url"], "https://a.test/doc")
        self.assertEqual(meta["sha256"], first.sha256)
        self.assertEqual(meta["content_type"], "text/html")
        self.assertEqual(meta["fetched_at"], second.fetched_at)

    def test_events_and_jsonl_log_record_the_capture(self):
        log_path = self.scratch / "logs" / "audit.jsonl"
        cache_dir = self.scratch / "cache"
        client, opener, _ = self.client(
            {
                "https://a.test/robots.txt": (404, {}, "", "Not Found"),
                "https://a.test/doc": (200, {"Content-Type": "text/html"}, b"doc", "OK"),
            },
            cache_dir=cache_dir,
            log_path=log_path,
        )
        client.fetch("https://a.test/doc")
        events = [event["event"] for event in client.events]
        self.assertIn("robots-missing", events)
        self.assertIn("fetched", events)
        self.assertTrue(log_path.is_file())
        lines = log_path.read_text(encoding="utf-8").splitlines()
        entries = [json.loads(line) for line in lines]
        recorded = [entry for entry in entries if entry["event"] == "request"]
        self.assertEqual(
            [entry["url"] for entry in recorded],
            ["https://a.test/robots.txt", "https://a.test/doc"],
        )


if __name__ == "__main__":
    unittest.main()
