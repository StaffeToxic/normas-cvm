"""Official CVM catalogue discovery for the MVP resolution family."""

from __future__ import annotations

import html as html_module
import re
from datetime import date as calendar_date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from cvm_archive.models import CatalogEntry

CATALOG_BASE = "https://conteudo.cvm.gov.br"
CATALOG_PATH = "/legislacao/index.html"
PAGE_SIZE = 50
SUPPORTED_CATEGORIES = frozenset({"resolucoes"})
MAX_PAGES = 1000

_ARTICLE_RE = re.compile(r"<article\b[^>]*>(.*?)</article>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(
    r"<h3\b[^>]*>\s*<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL
)
_HREF_RE = re.compile(r'''href\s*=\s*["']([^"']*)["']''', re.IGNORECASE)
_TITLE_ATTR_RE = re.compile(r'''title\s*=\s*["']([^"']*)["']''', re.IGNORECASE)
_DATE_RE = re.compile(
    r"<b>\s*Data:\s*</b>\s*(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE
)
_COUNT_RE = re.compile(r"(\d[\d.]*)\s+resultados\s+encontrados", re.IGNORECASE)
_SECTION_RE = re.compile(
    r'<section\b[^>]*class="[^"]*\blistaResultados\b[^"]*"[^>]*>(.*?)</section>',
    re.IGNORECASE | re.DOTALL,
)
_NUMBER_RE = re.compile(
    r"(?:resolu[cç][aã]o|instru[cç][aã]o|delibera[cç][aã]o|parecer(?:\s+de\s+orienta[cç][aã]o)?)"
    r"\s+(?:cvm\s+)?(?:n[.º°o]*\s*)?(\d+)",
    re.IGNORECASE,
)


class CatalogError(ValueError):
    """The official catalogue could not be read as an exhaustive inventory."""


class UnsupportedCategoryError(CatalogError):
    """The requested family is outside this ticket's MVP scope."""


class CatalogCountError(CatalogError):
    """The declared result counter disagrees with the enumerated entries."""


class CatalogLoopError(CatalogError):
    """Pagination repeated itself before the declared counter was reached."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _text(fragment: str) -> str:
    parser = _TextExtractor()
    parser.feed(fragment)
    parser.close()
    return " ".join("".join(parser.parts).split())


def _require_category(category: str) -> None:
    if category not in SUPPORTED_CATEGORIES:
        supported = ", ".join(sorted(SUPPORTED_CATEGORIES))
        raise UnsupportedCategoryError(
            f"unsupported catalogue category {category!r}; MVP supports only {supported}"
        )


def _canonical_url(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _parse_date(text: str | None) -> str | None:
    if not text:
        return None
    day, month, year = (int(part) for part in text.split("/"))
    try:
        return calendar_date(year, month, day).isoformat()
    except ValueError:
        return None


def catalog_url(category: str, page: int) -> str:
    """Return the official search URL for one catalogue page."""
    _require_category(category)
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise ValueError("catalogue page must be a positive integer")
    return (
        f"{CATALOG_BASE}{CATALOG_PATH}?buscado=true&contCategoriasCheck=1"
        f"&vimDaCategoria=/legislacao/{category}/&itensPagina={PAGE_SIZE}&searchPage={page}"
    )


def parse_catalog(html: str, base_url: str, category: str) -> tuple[list[CatalogEntry], int | None]:
    """Parse one official result page into candidate entries and its declared count."""
    _require_category(category)
    if not isinstance(html, str):
        raise TypeError("catalogue HTML must be text")

    match = _SECTION_RE.search(html)
    scope = match.group(1) if match else html
    counter_match = _COUNT_RE.search(scope)
    declared = (
        int(counter_match.group(1).replace(".", "")) if counter_match is not None else None
    )

    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    for article in _ARTICLE_RE.findall(scope):
        heading = _HEADING_RE.search(article)
        if heading is None:
            continue
        href_match = _HREF_RE.search(heading.group(1))
        if href_match is None:
            continue
        href = html_module.unescape(href_match.group(1)).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        title = _text(heading.group(2))
        if not title:
            title_match = _TITLE_ATTR_RE.search(heading.group(1))
            title = html_module.unescape(title_match.group(1)).strip() if title_match else ""
        if not title:
            continue
        url = urljoin(base_url, href)
        canonical = _canonical_url(url)
        if canonical in seen:
            continue
        seen.add(canonical)

        number_match = _NUMBER_RE.search(title)
        number = number_match.group(1).lstrip("0") or "0" if number_match else None
        date_match = _DATE_RE.search(article)
        entry_date = (
            _parse_date("/".join(date_match.groups())) if date_match is not None else None
        )
        entries.append(
            CatalogEntry(
                url=url,
                title=title,
                category=category,
                number=number,
                date=entry_date,
            )
        )

    return entries, declared


def _fetch_bytes(client: object, url: str) -> bytes:
    for name in ("fetch_artifact", "fetchArtifact", "fetch"):
        method = getattr(client, name, None)
        if callable(method):
            result = method(url)
            break
    else:
        raise TypeError("client must expose fetch_artifact, fetchArtifact or fetch")
    if isinstance(result, (bytes, bytearray)):
        return bytes(result)
    data = getattr(result, "bytes", None)
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    raise TypeError("client fetch result must expose immutable bytes")


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def enumerate_catalog(client: object, category: str) -> list[CatalogEntry]:
    """Fetch every result page and return stable, de-duplicated entries."""
    _require_category(category)
    entries: list[CatalogEntry] = []
    seen: set[str] = set()
    declared: int | None = None
    page = 1

    while page <= MAX_PAGES:
        url = catalog_url(category, page)
        data = _fetch_bytes(client, url)
        page_entries, page_counter = parse_catalog(_decode(data), url, category)

        if page_counter is None and declared is None:
            raise CatalogCountError("catalogue has no declared counter; completeness is unknown")

        if page_counter is not None:
            if declared is None:
                declared = page_counter
            elif page_counter != declared:
                raise CatalogCountError(
                    f"catalogue counter changed between pages: {declared} then {page_counter}"
                )

        new_entries = 0
        for entry in page_entries:
            canonical = _canonical_url(entry.url)
            if canonical in seen:
                continue
            seen.add(canonical)
            entries.append(entry)
            new_entries += 1

        if page_entries and new_entries == 0:
            raise CatalogLoopError(f"catalogue page {page} repeated only known entries")
        if not page_entries:
            break
        if declared is not None and len(entries) >= declared:
            break
        page += 1
    else:
        raise CatalogLoopError(f"catalogue did not finish within {MAX_PAGES} pages")

    if declared is not None and len(entries) != declared:
        raise CatalogCountError(
            f"catalogue declared {declared} results but enumeration found {len(entries)} unique entries"
        )
    return entries
