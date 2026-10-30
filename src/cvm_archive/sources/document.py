"""Official CVM document pages: epigraph, metadata, artifacts and relations."""

from __future__ import annotations

import html as html_module
import re
import unicodedata
from datetime import date as calendar_date
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit, urlunsplit

from .catalog import UnsupportedCategoryError, _require_category

VERSION_ORIGINAL = "publicação original"
VERSION_CONSOLIDATED = "consolidada"

_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
_SKIP_TEXT_TAGS = frozenset({"script", "style"})
_BLOCK_TAGS = frozenset(
    {"p", "div", "li", "ul", "ol", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_JAVA_DATE_RE = re.compile(
    r"\b(?:mon|tue|wed|thu|fri|sat|sun)\s+([a-z]{3})\s+(\d{1,2})\s+"
    r"\d{2}:\d{2}:\d{2}\s+\S+\s+(\d{4})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_PUBLICATION_RE = re.compile(r"^\(?\s*(?:publicad|retificad|republicad)", re.IGNORECASE)
_RELATION_STOP_RE = re.compile(
    r"\b(?:alterad[oa]s?|revogad[oa]s?\s+(?:pela|pelo|por)|audiencias\s+publicas)\b",
    re.IGNORECASE,
)
_EPIGRAPH_TYPES = (
    ("parecer-de-orientacao", r"parecer\s+de\s+orientacao"),
    ("decisao-conjunta", r"decisao\s+conjunta"),
    ("oficio-circular", r"oficio\s+circular"),
    ("nota-explicativa", r"nota\s+explicativa"),
    ("resolucao", r"resolucao"),
    ("instrucao", r"instrucao"),
    ("deliberacao", r"deliberacao"),
    ("portaria", r"portaria"),
)
_TYPE_NUMBER_RE = re.compile(r"(?:cvm\s+)?(?:n[.º°o]*\s*)?(\d+)", re.IGNORECASE)
_STATUS_SUFFIX_RE = re.compile(r"\s*\((?:revogad[ao]|em\s+vigor)\)\s*$", re.IGNORECASE)
_SUPPORTED_FORMATS = {
    ".htm": "html",
    ".html": "html",
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".rtf": "doc",
    ".xlsx": "xlsx",
}


class DocumentParseError(ValueError):
    """The official document page does not expose a trustworthy central act."""


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: dict[str, str], parent: _Node | None = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node | str] = []
        self.parent = parent

    def classes(self) -> list[str]:
        return self.attrs.get("class", "").split()


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document", {})
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), {key.lower(): value or "" for key, value in attrs}, self.current)
        self.current.children.append(node)
        if tag.lower() not in _VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(tag.lower(), {key.lower(): value or "" for key, value in attrs}, self.current)
        self.current.children.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        node: _Node | None = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data: str) -> None:
        self.current.children.append(data)


def _collapse(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def _text(node: _Node, breaks: bool = False) -> str:
    parts: list[str] = []

    def walk(current: _Node | str) -> None:
        if isinstance(current, str):
            parts.append(current)
            return
        if current.tag in _SKIP_TEXT_TAGS:
            return
        if current.tag == "br":
            parts.append("\n" if breaks else " ")
            return
        if current.tag in _BLOCK_TAGS:
            parts.append(" ")
        for child in current.children:
            walk(child)
        if current.tag in _BLOCK_TAGS:
            parts.append(" ")

    walk(node)
    raw = "".join(parts).replace("\xa0", " ")
    if not breaks:
        return _collapse(raw)
    return "\n".join(line for line in (_collapse(part) for part in raw.split("\n")) if line)


def _find_all(node: _Node, tag: str, class_token: str | None = None) -> list[_Node]:
    found: list[_Node] = []
    for child in node.children:
        if not isinstance(child, _Node):
            continue
        if child.tag == tag and (class_token is None or class_token in child.classes()):
            found.append(child)
        found.extend(_find_all(child, tag, class_token))
    return found


def _find_first(node: _Node, tag: str, class_token: str | None = None) -> _Node | None:
    for child in node.children:
        if not isinstance(child, _Node):
            continue
        if child.tag == tag and (class_token is None or class_token in child.classes()):
            return child
        nested = _find_first(child, tag, class_token)
        if nested is not None:
            return nested
    return None


def _direct(node: _Node, tag: str) -> list[_Node]:
    return [child for child in node.children if isinstance(child, _Node) and child.tag == tag]


def _anchors(node: _Node) -> list[_Node]:
    return _find_all(node, "a")


def _href(node: _Node) -> str:
    return html_module.unescape(node.attrs.get("href", "")).strip()


def _anchor_label(node: _Node) -> str:
    label = _text(node)
    if label:
        return label
    parent = node.parent
    while parent is not None:
        if parent.tag in {"td", "tr"}:
            row = _text(parent)
            if row:
                return row
        parent = parent.parent
    label = html_module.unescape(node.attrs.get("title", "")).strip()
    if label and _normalize(label) != "download":
        return label
    return PurePosixPath(urlsplit(_href(node)).path).name


def _parse_date(value: str) -> str | None:
    match = _JAVA_DATE_RE.search(value)
    if match is not None:
        month = _MONTHS.get(match.group(1).lower())
        if month is not None:
            try:
                return calendar_date(int(match.group(3)), month, int(match.group(2))).isoformat()
            except ValueError:
                return None
    match = _ISO_DATE_RE.search(value)
    if match is not None:
        try:
            return calendar_date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return None
    match = _NUMERIC_DATE_RE.search(value)
    if match is not None:
        year = int(match.group(3))
        if year < 100:
            year += 2000 if year < 70 else 1900
        try:
            return calendar_date(year, int(match.group(2)), int(match.group(1))).isoformat()
        except ValueError:
            return None
    return None


def _epigraph(epigraph: str) -> tuple[str, str | None]:
    normalized = _collapse(_normalize(epigraph))
    for name, pattern in _EPIGRAPH_TYPES:
        match = re.match(pattern + r"\b", normalized)
        if match is None:
            continue
        remainder = normalized[match.end() :]
        number_match = _TYPE_NUMBER_RE.search(remainder)
        return name, number_match.group(1) if number_match is not None else None
    raise DocumentParseError(f"unrecognised document epigraph: {epigraph!r}")


def _publication_date(publication: str | None) -> str | None:
    if not publication:
        return None
    match = _NUMERIC_DATE_RE.search(publication)
    if match is None:
        return None
    year = int(match.group(3))
    if year < 100:
        year += 2000 if year < 70 else 1900
    try:
        return calendar_date(year, int(match.group(2)), int(match.group(1))).isoformat()
    except ValueError:
        return None


def _edition(publication: str | None) -> str | None:
    if not publication:
        return None
    match = re.search(r"edi[cç][aã]o\s*(?:n[.º°o]*\s*)?(\d+)", publication, re.IGNORECASE)
    return match.group(1) if match is not None else None


def _artifact_format(url: str) -> str | None:
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    return _SUPPORTED_FORMATS.get(suffix)


def _is_html_artifact(url: str, label: str) -> bool:
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    if suffix == ".htm":
        return True
    if suffix != ".html":
        return True
    normalized = _normalize(label)
    return "[html]" in normalized or "integral" in normalized or "consolid" in normalized


def _matches_own_number(url: str, number: str | None) -> bool:
    if number is None:
        return True
    stem = _normalize(PurePosixPath(urlsplit(url).path).stem)
    match = re.search(r"(?:resol|inst|deli|pare|oc)[-_]?0*(\d{1,4})", stem)
    if match is None:
        return True
    return match.group(1).lstrip("0") == number.lstrip("0")


def _inside_relation(anchor: _Node, content: _Node) -> bool:
    node = anchor.parent
    while node is not None and node is not content:
        if node.tag == "p":
            normalized = _collapse(_normalize(_text(node)))
            if _RELATION_STOP_RE.search(normalized):
                return True
        node = node.parent
    return False


def _artifact_version(url: str, label: str) -> str:
    haystack = _normalize(f"{url} {label}")
    if "consolid" in haystack or "sem marcas" in haystack:
        return VERSION_CONSOLIDATED
    return VERSION_ORIGINAL


def _parse_metadata(content: _Node, date_text: str | None) -> dict[str, str | None]:
    ementa_lines: list[str] = []
    publication_lines: list[str] = []
    stopped = False
    for paragraph in _direct(content, "p"):
        text = _text(paragraph, breaks=True)
        if not text:
            continue
        if any(re.fullmatch(r"\[(?:HTML|PDF|DOCX?)\]", _text(anchor), re.I) for anchor in _anchors(paragraph)):
            break
        if date_text is not None and _parse_date(text) == date_text:
            continue
        normalized = _collapse(_normalize(text))
        if _RELATION_STOP_RE.search(normalized):
            break
        for line in text.split("\n"):
            if _PUBLICATION_RE.match(line) or "no dou de" in _normalize(line):
                publication_lines.append(line)
            elif not publication_lines:
                ementa_lines.append(line)
            else:
                stopped = True
                break
        if stopped:
            break

    publication = "; ".join(publication_lines) if publication_lines else None
    return {
        "ementa": " ".join(ementa_lines) if ementa_lines else None,
        "publication": publication,
        "data_publication": _publication_date(publication),
        "edition": _edition(publication),
    }


def _parse_relations(content: _Node) -> tuple[list[dict[str, str]], list[dict[str, str]], str | None]:
    altered_by: list[dict[str, str]] = []
    revoked_by: list[dict[str, str]] = []
    revocation_evidence: str | None = None
    altered_seen: set[tuple[str, str]] = set()
    revoked_seen: set[tuple[str, str]] = set()

    for paragraph in _find_all(content, "p"):
        context = _text(paragraph)
        if not context:
            continue
        normalized = _collapse(_normalize(context))
        is_altered = re.search(r"\balterad[oa]s?\b", normalized) is not None
        is_revoked = re.match(r"revogad[oa]\s+(?:pela|pelo|por)\b", normalized) is not None
        if not is_altered and not is_revoked:
            continue
        for anchor in _anchors(paragraph):
            raw_href = _href(anchor)
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            url = urljoin(content.attrs.get("_base", ""), raw_href)
            title = _anchor_label(anchor)
            target = revoked_by if is_revoked else altered_by
            seen = revoked_seen if is_revoked else altered_seen
            key = (url, title)
            if key in seen:
                continue
            seen.add(key)
            target.append({"title": title, "url": url, "context": context})
        if is_revoked and revocation_evidence is None:
            revocation_evidence = context

    return altered_by, revoked_by, revocation_evidence


def parse_document_page(html: str, url: str, category: str) -> dict[str, object]:
    """Parse one official metadata page without approving any linked integral text."""
    _require_category(category)
    if not isinstance(html, str):
        raise TypeError("document HTML must be text")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("document URL must be an absolute HTTP(S) URL")

    parser = _TreeParser()
    parser.feed(html)
    parser.close()

    article = _find_first(parser.root, "article", "contentTextoGeral")
    if article is None:
        raise DocumentParseError("central document article was not found")
    heading = _find_first(article, "h2")
    if heading is None:
        raise DocumentParseError("document epigraph (h2) was not found")

    epigraph_text = _text(heading)
    doc_type, number = _epigraph(epigraph_text)
    title = _STATUS_SUFFIX_RE.sub("", epigraph_text).strip()
    content = _find_first(article, "section", "contentArticle") or article
    content.attrs["_base"] = url

    date_text: str | None = None
    revoked: bool | None = None
    revocation_evidence: str | None = None
    for paragraph in _direct(content, "p"):
        paragraph_text = _text(paragraph)
        if not paragraph_text:
            continue
        # A date embedded in an ementa or DOU notice is not the act's date.
        if not (_JAVA_DATE_RE.fullmatch(paragraph_text) or
                _NUMERIC_DATE_RE.fullmatch(paragraph_text) or
                _ISO_DATE_RE.fullmatch(paragraph_text)):
            continue
        candidate = _parse_date(paragraph_text)
        if candidate is not None:
            date_text = candidate
            break

    metadata = _parse_metadata(content, date_text)
    altered_by, revoked_by, explicit_evidence = _parse_relations(content)

    epigraph_status = bool(re.search(r"\((?:revogad[ao])\)", _normalize(epigraph_text)))
    if epigraph_status or explicit_evidence is not None or revoked_by:
        revoked = True
        revocation_evidence = explicit_evidence or epigraph_text

    negative_evidence = (
        epigraph_text if re.search(r"\(em\s+vigor\)", _normalize(epigraph_text)) else None
    )
    for paragraph in _find_all(content, "p"):
        normalized = _collapse(_normalize(_text(paragraph)))
        if re.match(r"nao\s+(?:foi\s+)?revogad[ao]\b", normalized):
            negative_evidence = _text(paragraph)
            break

    if negative_evidence is not None:
        if revoked is True:
            raise DocumentParseError("conflicting explicit revocation evidence on official page")
        revoked = False
        revocation_evidence = negative_evidence

    artifacts: list[dict[str, str]] = []
    artifact_seen: set[str] = set()
    for anchor in _anchors(content):
        raw_href = _href(anchor)
        if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(url, raw_href)
        parts = urlsplit(absolute)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            continue
        absolute = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        label = _anchor_label(anchor)
        artifact_format = _artifact_format(absolute)
        if artifact_format is None:
            continue
        if not _is_html_artifact(absolute, label):
            continue
        if _inside_relation(anchor, content):
            continue
        if not _matches_own_number(absolute, number):
            continue
        if absolute in artifact_seen:
            continue
        artifact_seen.add(absolute)
        artifacts.append(
            {
                "url": absolute,
                "format": artifact_format,
                "version": _artifact_version(absolute, label),
                "label": label,
            }
        )

    return {
        "title": title,
        "type": doc_type,
        "number": number,
        "date": date_text,
        "revoked": revoked,
        "revocation_evidence": revocation_evidence,
        "artifacts": artifacts,
        "relations": {"altered_by": altered_by, "revoked_by": revoked_by},
        "document_metadata": metadata,
    }
