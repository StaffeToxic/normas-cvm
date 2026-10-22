"""Immutable records shared by collection, conversion and publication."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date as calendar_date
from datetime import datetime, timezone
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class Artifact:
    """Exact downloaded bytes; the digest never describes transformed text."""

    url: str
    bytes: bytes
    content_type: str
    sha256: str
    fetched_at: str

    def __post_init__(self) -> None:
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Artifact URL must be an absolute HTTP(S) URL")
        if not isinstance(self.bytes, bytes):
            raise TypeError("Artifact payload must be immutable bytes")
        if hashlib.sha256(self.bytes).hexdigest() != self.sha256:
            raise ValueError("Artifact digest does not match its exact bytes")
        collected = datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
        if collected.utcoffset() != timezone.utc.utcoffset(collected):
            raise ValueError("Artifact collection time must include UTC timezone")

    @classmethod
    def from_bytes(
        cls, url: str, data: bytes, content_type: str, fetched_at: str | None = None
    ) -> Artifact:
        return cls(
            url=url,
            bytes=data,
            content_type=content_type,
            sha256=hashlib.sha256(data).hexdigest(),
            fetched_at=fetched_at or datetime.now(timezone.utc).isoformat(),
        )


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """An official listing entry whose legal metadata is not yet confirmed."""

    url: str
    title: str
    category: str
    number: str | None
    date: str | None

    def __post_init__(self) -> None:
        if self.date is not None:
            calendar_date.fromisoformat(self.date)


@dataclass(frozen=True, slots=True)
class Conversion:
    """Candidate output, never a publication approval by itself."""

    source_text: str
    markdown: str
    warnings: tuple[str, ...] = ()
    pending_reason: str | None = None
