"""Compare ordered legal text and independently inspect source HTML structure."""

from __future__ import annotations

import re
import unicodedata
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, urljoin


_BLOCKS = {"p", "div", "section", "article", "li", "ul", "ol", "br", "hr", "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6"}
_IGNORED = {"head", "script", "style", "nav", "noscript", "template"}
_VOID = {"meta", "link", "img", "input", "br", "hr", "col", "wbr", "source", "area", "embed", "param", "track", "base"}
_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^\s)]+)\)")
_DEVICES = re.compile(r"(?mi)^\s*(Art\.\s*\d+[º°.]?|§\s*\d+[º°.]?|Par[áa]grafo\s+[úu]nico[.:]?|[IVXLCDM]+\s*[–—-]|[a-z]\)|ANEXO\s+\S+)(?=\s|$)")


def _tokens(text: str) -> tuple[str, ...]:
    # Punctuation, case, accents, decimals and signs remain significant.
    return tuple(re.findall(r"\w+|[^\w\s]", unicodedata.normalize("NFC", text)))


class _Reader(HTMLParser):
    """Read all body text, never reuse the converter's body selector."""

    def __init__(self, *, collapse_data=False):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []
        self.tables = []
        self.rows = None
        self.row = None
        self.cell_count = 0
        self.strike_depth = 0
        self.strike_parts = []
        self.strikes = []
        self.links = []
        self.active_link = None
        self.errors = []
        self.collapse_data = collapse_data

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        ignored = bool(self.stack and self.stack[-1][1]) or tag in _IGNORED
        strike = tag in {"del", "s", "strike"} or bool(re.search(r"text-decoration(?:-line)?\s*:[^;]*line-through", attrs.get("style", ""), re.I))
        if tag not in _VOID:
            self.stack.append((tag, ignored, strike))
        if ignored:
            return
        if tag == "img" and not re.match(r"(?:logotipo|logo|bras[aã]o)\b", attrs.get("alt", "").strip(), re.I):
            self.errors.append("unverified-image")
        if tag in {"svg", "canvas", "object", "iframe", "embed"}:
            self.errors.append("unverified-embedded-content")
        if strike:
            self.strike_depth += 1
        if tag in _BLOCKS:
            self.parts.append("\n")
        if tag == "table":
            if self.rows is not None:
                self.errors.append("nested-table")
            self.rows = []
        elif tag == "tr":
            self.row = []
            self.cell_count = 0
        elif tag in {"td", "th"}:
            if self.row is None:
                self.errors.append("cell-outside-row")
            else:
                try:
                    spans = (int(attrs.get("colspan", "1")), int(attrs.get("rowspan", "1")))
                    if min(spans) < 1:
                        raise ValueError
                    self.row.append((tag, *spans))
                except ValueError:
                    self.errors.append("invalid-table-span")
                if self.cell_count:
                    self.parts.append(" | ")
                self.cell_count += 1
        elif tag == "a" and attrs.get("href"):
            self.active_link = (attrs["href"], [])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        # Void elements can appear with explicit closing tags in office HTML.
        if tag in _VOID:
            return
        pos = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if pos is None:
            return
        closed = self.stack[pos:]
        del self.stack[pos:]
        if closed[0][1]:
            return
        for _, ignored, strike in reversed(closed):
            if strike and not ignored:
                self.strike_depth -= 1
                if not self.strike_depth:
                    self.strikes.append("".join(self.strike_parts))
                    self.strike_parts = []
        if tag in _BLOCKS:
            self.parts.append("\n")
        if tag == "tr" and self.rows is not None:
            self.rows.append(tuple(self.row or ()))
            self.row = None
        elif tag == "table" and self.rows is not None:
            self.tables.append(tuple(self.rows))
            self.rows = None
        elif tag == "a" and self.active_link is not None:
            href, parts = self.active_link
            if "".join(parts).strip():
                self.links.append((href, "".join(parts)))
            self.active_link = None

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        if self.collapse_data:
            data = re.sub(r"\s+", " ", data)
        self.parts.append(data)
        if self.strike_depth:
            self.strike_parts.append(data)
        if self.active_link is not None:
            self.active_link[1].append(data)

    @property
    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


def _read_html(text: str, *, collapse_data=False) -> _Reader:
    reader = _Reader(collapse_data=collapse_data)
    reader.feed(text)
    reader.close()
    return reader


def _source_reader(source_html: str) -> _Reader:
    body = re.search(r"<body\b[^>]*>(.*?)</body\s*>", source_html, re.I | re.S)
    return _read_html(body[1] if body else source_html, collapse_data=True)


def read_html_text(source_html: str) -> str:
    """Inspect the complete source without selecting or converting its body."""
    return _source_reader(source_html).text


def _valid_grid(rows) -> bool:
    occupied = set()
    for row_index, row in enumerate(rows):
        column = 0
        for _, width, height in row:
            if width > 1000 or height + row_index > len(rows):
                return False
            while (row_index, column) in occupied:
                column += 1
            for y in range(row_index, row_index + height):
                for x in range(column, column + width):
                    if (y, x) in occupied:
                        return False
                    occupied.add((y, x))
            column += width
    width = max((x + 1 for _, x in occupied), default=0)
    return bool(width) and all(sum(y == index for y, _ in occupied) == width for index in range(len(rows)))


def _markdown_parts(markdown: str):
    lines = markdown.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (i + 1 < len(lines) and line.startswith("|") and
                re.fullmatch(r"\s*\|(?:\s*:?-+:?\s*\|)+\s*", lines[i + 1])):
            output.append("<table>")
            header = True
            while i < len(lines) and lines[i].startswith("|"):
                row = lines[i]
                i += 1
                if re.fullmatch(r"\s*\|(?:\s*:?-+:?\s*\|)+\s*", row):
                    continue
                cells = re.split(r"(?<!\\)\|", row.strip()[1:-1])
                tag = "th" if header else "td"
                output.append("<tr>" + "".join(f"<{tag}>{cell.strip()}</{tag}>" for cell in cells) + "</tr>")
                header = False
            output.append("</table>")
            continue
        output.append(re.sub(r"^#{1,6}\s+", "", line))
        i += 1
    text = "\n".join(output)
    text = _LINK.sub(lambda m: f'<a href="{escape(m[2], quote=True)}">{m[1]}</a>', text)
    text = re.sub(r"~~([^\n]+?)~~", r"<del>\1</del>", text)
    for marker in (r"\*\*", r"\*", "_"):
        text = re.sub(marker + r"([^\n]+?)" + marker, r"\1", text)
    text = re.sub(r"\\([\\`*{}_\[\]()#+.!|>~-])", r"\1", text)
    reader = _read_html(text)
    return reader.text, reader.tables, reader.links, reader.strikes, reader.errors


def check_fidelity(source_text: str, markdown: str) -> tuple[str, ...]:
    """Require exact ordered text and device markers, not just equal word sets."""
    plain, tables, _, _, errors = _markdown_parts(markdown)
    failures = list(errors)
    if not source_text.strip() or not markdown.strip():
        failures.append("empty-content")
    if _tokens(source_text) != _tokens(plain):
        failures.append("token-sequence")
    source_devices = tuple(_tokens(m[0]) for m in _DEVICES.finditer(source_text))
    output_devices = tuple(_tokens(m[0]) for m in _DEVICES.finditer(plain))
    if source_devices != output_devices:
        failures.append("legal-devices")
    if " | " in source_text and not tables:
        failures.append("flattened-table")
    for line in markdown.splitlines():
        plain_start = re.match(r"(?:Art\.\s*\d|§|Par[áa]grafo\s+[úu]nico)", line.strip(), re.I)
        if plain_start:
            failures.append("device-format")
        heading = re.match(r"^(ANEXO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O)\s+\S+", line.lstrip("# "), re.I)
        if heading:
            kind = unicodedata.normalize("NFKD", heading[1]).encode("ascii", "ignore").decode().upper()
            level = {"ANEXO": 2, "TITULO": 2, "CAPITULO": 3, "SECAO": 4, "SUBSECAO": 5}[kind]
            if not line.startswith("#" * level + " "):
                failures.append("heading-format")
    return tuple(dict.fromkeys(failures))


def check_html_structure(source_html: str, markdown: str, source_url: str) -> tuple[str, ...]:
    """Check source independently, including cells, spans, links and strike text."""
    # A complete HTML artifact uses its body, excluding the title's duplicate text.
    reference = _source_reader(source_html)
    text, tables, links, strikes, errors = _markdown_parts(markdown)
    failures = list(reference.errors) + errors
    failures.extend(check_fidelity(reference.text, markdown))
    if reference.tables != tables:
        failures.append("table-structure")
    if any(not _valid_grid(table) for table in reference.tables + tables):
        failures.append("table-shape")
    def link_key(pair):
        href, label = pair
        url = quote(urljoin(source_url, href), safe="/:#?&=%,;+@~.!$*'[]")
        return url, _tokens(label)
    if tuple(map(link_key, reference.links)) != tuple(map(link_key, links)):
        failures.append("legal-links")
    if tuple(map(_tokens, reference.strikes)) != tuple(map(_tokens, strikes)):
        failures.append("strike-text")
    return tuple(dict.fromkeys(failures))
