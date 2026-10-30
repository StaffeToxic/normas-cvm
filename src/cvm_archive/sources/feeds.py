"""Official RSS is a discovery signal, never an authority for legal metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from cvm_archive.gates.metadata import valid_url
from cvm_archive.models import CatalogEntry


FEED_URLS = (
    "https://conteudo.cvm.gov.br/feed/legislacao.xml",
    "https://conteudo.cvm.gov.br/feed/audiencias.xml",
)


class FeedError(ValueError):
    """The response is not a readable official RSS snapshot."""


@dataclass(frozen=True, slots=True)
class FeedItem:
    url: str
    title: str
    pub_date: str | None
    published_at: str | None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(data: bytes) -> list[FeedItem]:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise FeedError("RSS declarations with entities are not supported")
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise FeedError("invalid RSS XML") from exc
    channels = [child for child in root if _local(child.tag) == "channel"]
    if _local(root.tag) != "rss" or len(channels) != 1:
        raise FeedError("expected one RSS channel")
    items, seen = [], set()
    for node in channels[0]:
        if _local(node.tag) != "item":
            continue
        fields = {_local(child.tag): child.text or "" for child in node}
        link, title = fields.get("link", "").strip(), " ".join(fields.get("title", "").split())
        if not valid_url(link) or not title:
            raise FeedError("RSS item is missing a title or absolute HTTP(S) link")
        if link in seen:
            continue
        seen.add(link)
        raw_date = fields.get("pubDate", "").strip() or None
        published = None
        if raw_date:
            try:
                value = parsedate_to_datetime(raw_date)
                if value.tzinfo is not None:
                    published = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OverflowError):
                pass
        items.append(FeedItem(link, title, raw_date, published))
    return items


def match_catalog(items: list[FeedItem], entries: list[CatalogEntry]) -> list[str]:
    """Prioritize an enumerated URL; do not fetch or certify a legacy RSS redirect."""
    by_path = {}
    for entry in entries:
        by_path.setdefault(urlsplit(entry.url).path, []).append(entry.url)
    matched = []
    for item in items:
        parsed = urlsplit(item.url)
        if parsed.hostname not in {"www.cvm.gov.br", "conteudo.cvm.gov.br", "cvm.gov.br"}:
            continue
        for url in by_path.get(parsed.path, []):
            if url not in matched:
                matched.append(url)
    return matched


def incremental_urls(entries: list[CatalogEntry], *, known_urls: set[str], signal_urls: list[str], first_page_urls: list[str], today: date, batch_size: int = 50) -> list[str]:
    ordered = sorted(entry.url for entry in entries)
    count = max(1, (len(ordered) + batch_size - 1) // batch_size)
    week = (today.toordinal() - 1) // 7
    start = (week % count) * batch_size
    priorities = [url for url in ordered if url not in known_urls] + signal_urls + first_page_urls + ordered[start:start + batch_size]
    valid = set(ordered)
    result = []
    for url in priorities:
        if url in valid and url not in result:
            result.append(url)
    return result
