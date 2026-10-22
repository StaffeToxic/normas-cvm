"""Structural conversion of official CVM HTML into a conversion candidate.

The converter reads the official HTML with the standard library parser only,
keeps the normative body of the act (the epigraph together with the articles)
and returns a :class:`~cvm_archive.models.Conversion` holding the plain
reference text, the Markdown body, the warnings and an explicit pending reason.

A pending conversion never produces Markdown.  An ambiguous body, an image
that carries textual content and a table whose grid cannot be reproduced are
reported as pending instead of being published with a silent loss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

from cvm_archive.models import Conversion
from cvm_archive.normalize.text import (
    BlockKind,
    classify_block,
    collapse_whitespace,
    device_marker,
    escape_leading_list_marker,
    heading_level,
    normalize_heading,
)

__all__ = ["convert_html"]

VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

INLINE_TAGS = frozenset(
    {
        "a",
        "abbr",
        "b",
        "bdi",
        "bdo",
        "cite",
        "code",
        "del",
        "dfn",
        "em",
        "font",
        "i",
        "ins",
        "kbd",
        "mark",
        "q",
        "s",
        "samp",
        "small",
        "span",
        "strike",
        "strong",
        "sub",
        "sup",
        "time",
        "tt",
        "u",
        "var",
    }
)

SKIP_TAGS = frozenset(
    {
        "base",
        "head",
        "link",
        "meta",
        "noscript",
        "script",
        "source",
        "style",
        "template",
        "title",
        "track",
    }
)

#: Skipped elements that carry content and therefore have to be reported.
REPORTED_SKIP_TAGS = frozenset({"nav", "noscript", "script", "style", "template"})

NAV_ROLES = frozenset(
    {"banner", "contentinfo", "menu", "menubar", "navigation", "search", "toolbar"}
)

UNSUPPORTED_TAGS = frozenset({"applet", "embed", "iframe", "object"})

BOLD_TAGS = frozenset({"b", "strong"})
ITALIC_TAGS = frozenset({"cite", "em", "i", "var"})
STRIKE_TAGS = frozenset({"del", "s", "strike"})

_EPIGRAPH_RE = re.compile(
    r"^(RESOLUÇÃO|INSTRUÇÃO|DELIBERAÇÃO|PARECER(?:\s+DE\s+ORIENTAÇÃO)?|"
    r"DECISÃO(?:\s+CONJUNTA)?|PORTARIA|OFÍCIO(?:\s+CIRCULAR)?|"
    r"NOTA(?:\s+EXPLICATIVA)?|EMENDA|CONVÊNIO|CONSÓRCIO)\b"
    r".*?\b(?:n[º°o]\s*)?\d+",
    re.IGNORECASE,
)
_ARTICLE_START_RE = re.compile(r"^Art\.?\s*\d")
_ANNEX_START_RE = re.compile(r"^ANEXO\s+(?P<label>[IVXLCDM]+|[A-Z]|\d+)\b")
_IMAGE_TEXTUAL_RE = re.compile(r"^(Art\.?|§|ANEXO\b|RESOLUÇÃO|INSTRUÇÃO|DELIBERAÇÃO)")
_IMAGE_TEXTUAL_WORDS = 8


@dataclass
class _Node:
    """Minimal structural node built from the official HTML."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: "_Node | None" = None


@dataclass
class _Run:
    """A styled fragment of text."""

    text: str
    bold: bool = False
    italic: bool = False
    strike: bool = False
    href: str | None = None


@dataclass
class _Cell:
    """One table cell with its original spans."""

    text: str
    runs: list[_Run]
    colspan: int
    rowspan: int
    header: bool


@dataclass
class _Table:
    """A table whose grid was validated before it was rendered."""

    rows: list[list[_Cell]]
    has_header: bool


@dataclass
class _TextBlock:
    """A paragraph or heading of the normative body."""

    kind: BlockKind
    plain: str
    markdown: str


@dataclass
class _TableBlock:
    """A table of the normative body."""

    table: _Table


@dataclass
class _Context:
    """Warnings, pending reason and provenance of the running conversion."""

    source_url: str
    warnings: list[str] = field(default_factory=list)
    pending_reason: str | None = None
    removed_tags: set[str] = field(default_factory=set)
    empty_blocks: int = 0

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def pending(self, reason: str, detail: str = "") -> None:
        if self.pending_reason is not None:
            return
        self.pending_reason = f"{reason}: {detail}" if detail else reason


class _TreeBuilder(HTMLParser):
    """Build a tolerant tree from the official HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self._stack: list[_Node] = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        node = _Node(
            tag, {name: (value or "") for name, value in attrs}, parent=self._stack[-1]
        )
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs) -> None:
        node = _Node(
            tag, {name: (value or "") for name, value in attrs}, parent=self._stack[-1]
        )
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def convert_html(html: str, source_url: str) -> Conversion:
    """Convert the official HTML of an act into a conversion candidate.

    ``source_text`` is the plain reference of the selected normative body,
    written before any Markdown formatting, and keeps every legal text in the
    order of the source.  ``markdown`` is the formatted body; it is empty when
    the structure is ambiguous or unsupported, and ``pending_reason`` then
    states why the document cannot be published.
    """

    context = _Context(source_url=source_url)
    builder = _TreeBuilder()
    builder.feed(html)
    builder.close()
    _prune(builder.root, context)

    container, reason = _select_container(builder.root)
    blocks: list = []
    if container is not None:
        blocks = _collect_blocks(container, context)

    source_text = _source_text(blocks)
    warnings = tuple(_finish_warnings(context))
    if context.pending_reason is not None:
        return Conversion(source_text, "", warnings, context.pending_reason)
    if container is None:
        return Conversion(
            source_text, "", warnings, reason or "corpo-normativo-nao-encontrado"
        )
    return Conversion(source_text, _markdown(blocks), warnings, None)


def _finish_warnings(context: _Context) -> list[str]:
    """Return the warnings of the conversion, including the removal summary."""

    warnings = list(context.warnings)
    if context.removed_tags:
        warnings.append(
            "elementos-removidos: " + ", ".join(sorted(context.removed_tags))
        )
    if context.empty_blocks:
        warnings.append(f"paragrafos-vazios-descartados: {context.empty_blocks}")
    return warnings


def _prune(node: _Node, context: _Context) -> None:
    """Remove scripts, styles and navigation that carry no legal text."""

    kept: list = []
    for child in node.children:
        if isinstance(child, str):
            kept.append(child)
            continue
        if child.tag in SKIP_TAGS:
            if child.tag in REPORTED_SKIP_TAGS:
                context.removed_tags.add(child.tag)
            continue
        if child.tag == "nav" or child.attrs.get("role", "").lower() in NAV_ROLES:
            context.removed_tags.add(child.tag)
            continue
        _prune(child, context)
        kept.append(child)
    node.children = kept


def _select_container(root: _Node) -> tuple[_Node | None, str | None]:
    """Return the element holding the whole normative body of the act.

    The container must hold the epigraph and every article of the document.
    When no element qualifies, the reason explains what was missing instead of
    publishing a truncated body.
    """

    articles = _find_markers(root, _is_article_block)
    if not articles:
        return None, "corpo-normativo-nao-encontrado"
    epigraphs = _find_markers(root, _is_epigraph_block)
    if not epigraphs:
        return None, "epigrafe-nao-encontrada"

    candidates = [
        element
        for element in _iter_elements(root)
        if _holds_all(element, articles) and _holds_any(element, epigraphs)
    ]
    if not candidates:
        return None, "corpo-normativo-incompleto"
    deepest = max(_depth(element) for element in candidates)
    best = [element for element in candidates if _depth(element) == deepest]
    if len(best) > 1:
        return None, "selecao-ambigua-corpo-normativo"
    if len(_held_markers(best[0], epigraphs)) > 1:
        return None, "selecao-ambigua-corpo-normativo"
    return best[0], None


def _iter_elements(node: _Node):
    """Yield every element of the tree, depth first."""

    for child in node.children:
        if isinstance(child, str):
            continue
        yield child
        yield from _iter_elements(child)


def _depth(node: _Node) -> int:
    """Return how deep the node is in the tree."""

    depth = 0
    current = node.parent
    while current is not None:
        depth += 1
        current = current.parent
    return depth


def _holds_all(element: _Node, targets: list[_Node]) -> bool:
    """Tell whether the element holds every given node."""

    return all(_holds(element, target) for target in targets)


def _holds_any(element: _Node, targets: list[_Node]) -> bool:
    """Tell whether the element holds at least one of the given nodes."""

    return any(_holds(element, target) for target in targets)


def _held_markers(element: _Node, targets: list[_Node]) -> list[_Node]:
    """Return the given nodes the element holds."""

    return [target for target in targets if _holds(element, target)]


def _holds(element: _Node, target: _Node) -> bool:
    """Tell whether the target is a descendant of the element."""

    current = target.parent
    while current is not None:
        if current is element:
            return True
        current = current.parent
    return False


def _find_markers(root: _Node, predicate) -> list[_Node]:
    """Return the leaf blocks whose own text satisfies the predicate."""

    found = []
    for element in _iter_elements(root):
        if _has_block_children(element):
            continue
        if predicate(_own_text(element)):
            found.append(element)
    return found


def _is_article_block(text: str) -> bool:
    """Tell whether the text opens an article."""

    return bool(_ARTICLE_START_RE.match(text))


def _is_epigraph_block(text: str) -> bool:
    """Tell whether the text is the epigraph of an act."""

    return bool(_EPIGRAPH_RE.match(text))


def _collect_blocks(node: _Node, context: _Context) -> list:
    """Collect the blocks of the normative body, in the order of the source."""

    blocks: list = []
    _walk_blocks(node, blocks, context)
    return blocks


def _walk_blocks(node: _Node, blocks: list, context: _Context) -> None:
    """Walk a container and emit its paragraphs, headings and tables."""

    pending: list[_Run] = []
    container = _has_block_children(node)

    def flush() -> None:
        if pending:
            blocks.append(_text_block(pending, context))
            pending.clear()

    for child in node.children:
        if isinstance(child, str):
            if container and not child.strip():
                continue
            pending.extend(_text_runs(child))
            continue
        if child.tag == "img":
            flush()
            _handle_image(child, context)
            continue
        if not _is_block(child):
            pending.extend(_inline_runs(child, context))
            continue
        flush()
        if child.tag == "table":
            blocks.extend(_table_blocks(child, context))
            continue
        if child.tag in UNSUPPORTED_TAGS:
            context.pending("conteudo-embutido-nao-suportado", child.tag)
            continue
        _walk_blocks(child, blocks, context)
    flush()


def _text_block(runs: list[_Run], context: _Context) -> _TextBlock:
    """Build a text block from the runs of a paragraph."""

    plain = collapse_whitespace("".join(run.text for run in runs))
    if not plain:
        context.empty_blocks += 1
        return _TextBlock(BlockKind.PLAIN, "", "")
    kind = classify_block(plain)
    markdown = _render_runs(runs)
    marker = device_marker(plain)
    if marker and markdown.startswith(marker) and not markdown.startswith("**"):
        markdown = f"**{marker}**{markdown[len(marker):]}"
    markdown = escape_leading_list_marker(markdown)
    return _TextBlock(kind, plain, markdown)


def _inline_runs(
    node: _Node,
    context: _Context,
    bold: bool = False,
    italic: bool = False,
    strike: bool = False,
    href: str | None = None,
) -> list[_Run]:
    """Collect the styled runs of an inline subtree."""

    bold = bold or node.tag in BOLD_TAGS
    italic = italic or node.tag in ITALIC_TAGS
    strike = strike or node.tag in STRIKE_TAGS
    if node.tag == "a":
        target = node.attrs.get("href", "").strip()
        if target:
            href = urljoin(context.source_url, target)
    runs: list[_Run] = []
    for child in node.children:
        if isinstance(child, str):
            runs.extend(_text_runs(child, bold, italic, strike, href))
            continue
        if child.tag == "br":
            runs.append(_Run(" ", bold, italic, strike, href))
            continue
        if child.tag == "img":
            _handle_image(child, context)
            continue
        if child.tag in UNSUPPORTED_TAGS:
            context.pending("conteudo-embutido-nao-suportado", child.tag)
            continue
        runs.extend(_inline_runs(child, context, bold, italic, strike, href))
    return runs


def _text_runs(
    text: str,
    bold: bool = False,
    italic: bool = False,
    strike: bool = False,
    href: str | None = None,
) -> list[_Run]:
    """Turn a text node into a run with collapsed whitespace."""

    collapsed = re.sub(r"\s+", " ", text.replace("\u00a0", " "))
    if not collapsed:
        return []
    return [_Run(collapsed, bold, italic, strike, href)]


def _render_runs(runs: list[_Run]) -> str:
    """Render the styled runs as Markdown."""

    parts: list[str] = []
    for run in runs:
        text = run.text
        if not text:
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        core = text.strip()
        if not core:
            parts.append(text)
            continue
        if run.href:
            core = f"[{core}]({run.href})"
        if run.strike:
            core = f"~~{core}~~"
        if run.bold:
            core = f"**{core}**"
        if run.italic:
            core = f"*{core}*"
        parts.append(f"{lead}{core}{trail}")
    return collapse_whitespace("".join(parts))


def _handle_image(node: _Node, context: _Context) -> None:
    """Record an image, refusing to drop one that carries textual content."""

    label = collapse_whitespace(node.attrs.get("alt", "")) or collapse_whitespace(
        node.attrs.get("title", "")
    )
    if not label:
        context.warn("imagem-sem-texto-descartada")
        return
    if _IMAGE_TEXTUAL_RE.match(label) or len(label.split()) >= _IMAGE_TEXTUAL_WORDS:
        context.pending("imagem-com-conteudo-textual", label[:120])
        return
    context.warn(f"imagem-decorativa-descartada: {label}")


def _table_blocks(node: _Node, context: _Context) -> list:
    """Build the blocks of a table, refusing an unsupported grid."""

    rows: list[list[_Cell]] = []
    has_header = False
    caption: list = []
    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag == "tr":
            row = _parse_row(child, context)
            if row is None:
                return []
            if row:
                rows.append(row)
                has_header = has_header or all(cell.header for cell in row)
            continue
        if child.tag in ("thead", "tbody", "tfoot"):
            section, section_header = _parse_section(child, context)
            if section is None:
                return []
            rows.extend(section)
            has_header = has_header or section_header
            continue
        if child.tag == "caption":
            runs = _inline_runs(child, context)
            if runs:
                caption.append(_text_block(runs, context))
            continue
    if not rows:
        context.warn("tabela-sem-conteudo-descartada")
        return []
    if not _grid_is_consistent(rows):
        context.pending("tabela-estrutura-inconsistente", "grade divergente")
        return []
    return caption + [_TableBlock(_Table(rows, has_header))]


def _parse_section(node: _Node, context: _Context) -> tuple[list[list[_Cell]] | None, bool]:
    """Parse the rows of a table section."""

    rows: list[list[_Cell]] = []
    has_header = False
    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag != "tr":
            continue
        row = _parse_row(child, context)
        if row is None:
            return None, False
        if row:
            rows.append(row)
            has_header = has_header or all(cell.header for cell in row)
    return rows, has_header


def _parse_row(node: _Node, context: _Context) -> list[_Cell] | None:
    """Parse the cells of a table row."""

    cells: list[_Cell] = []
    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag not in ("td", "th"):
            continue
        if _contains_tag(child, "table"):
            context.pending("tabela-estrutura-nao-suportada", "tabela aninhada")
            return None
        runs = _inline_runs(child, context)
        text = collapse_whitespace("".join(run.text for run in runs))
        colspan = _span(child, "colspan")
        rowspan = _span(child, "rowspan")
        if colspan is None or rowspan is None:
            context.pending("tabela-estrutura-nao-suportada", "span invalido")
            return None
        cells.append(_Cell(text, runs, colspan, rowspan, child.tag == "th"))
    return cells


def _span(node: _Node, attribute: str) -> int | None:
    """Read a span attribute, refusing a value that is not a positive integer."""

    raw = node.attrs.get(attribute, "1").strip()
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if value >= 1 else None


def _contains_tag(node: _Node, tag: str) -> bool:
    """Tell whether the subtree holds an element with the given tag."""

    for child in node.children:
        if isinstance(child, str):
            continue
        if child.tag == tag or _contains_tag(child, tag):
            return True
    return False


def _grid_is_consistent(rows: list[list[_Cell]]) -> bool:
    """Validate the grid of the table, spans included."""

    occupied: set[tuple[int, int]] = set()
    for index, row in enumerate(rows):
        column = 0
        for cell in row:
            while (index, column) in occupied:
                column += 1
            for line in range(cell.rowspan):
                for offset in range(cell.colspan):
                    occupied.add((index + line, column + offset))
            if index + cell.rowspan > len(rows):
                return False
            column += cell.colspan
    widths = {
        max((column for row, column in occupied if row == index), default=-1) + 1
        for index in range(len(rows))
    }
    return len(widths) == 1


def _source_text(blocks: list) -> str:
    """Build the plain reference of the body, before any Markdown formatting."""

    parts: list[str] = []
    for block in blocks:
        if isinstance(block, _TextBlock):
            if block.plain:
                parts.append(block.plain)
            continue
        for row in block.table.rows:
            parts.append(" | ".join(cell.text for cell in row))
    return "\n\n".join(parts)


def _markdown(blocks: list) -> str:
    """Build the Markdown body of the act."""

    parts: list[str] = []
    for block in blocks:
        if isinstance(block, _TextBlock):
            if not block.plain:
                continue
            if block.kind in (BlockKind.HEADING, BlockKind.ANNEX):
                level = heading_level(block.plain) or 2
                parts.append(f"{'#' * level} {normalize_heading(block.plain)}")
                continue
            parts.append(block.markdown)
            continue
        parts.append(_render_table(block.table))
    return "\n\n".join(parts)


def _render_table(table: _Table) -> str:
    """Render a table as Markdown when the grid is simple, as HTML otherwise."""

    simple = table.has_header and not any(
        cell.colspan > 1 or cell.rowspan > 1 or not cell.text
        for row in table.rows
        for cell in row
    )
    if simple:
        return _render_markdown_table(table)
    return _render_html_table(table)


def _render_markdown_table(table: _Table) -> str:
    """Render a simple grid as a Markdown table."""

    lines: list[str] = []
    for index, row in enumerate(table.rows):
        cells = [cell.text.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def _render_html_table(table: _Table) -> str:
    """Render a table with spans or empty cells as an HTML table."""

    lines: list[str] = ["<table>"]
    for row in table.rows:
        cells: list[str] = []
        for cell in row:
            tag = "th" if cell.header else "td"
            attributes = ""
            if cell.colspan > 1:
                attributes += f' colspan="{cell.colspan}"'
            if cell.rowspan > 1:
                attributes += f' rowspan="{cell.rowspan}"'
            cells.append(f"<{tag}{attributes}>{_render_html_runs(cell.runs)}</{tag}>")
        lines.append("<tr>" + "".join(cells) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _render_html_runs(runs: list[_Run]) -> str:
    """Render the styled runs as inline HTML."""

    parts: list[str] = []
    for run in runs:
        text = run.text
        if not text:
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        core = text.strip()
        if not core:
            parts.append(text)
            continue
        if run.href:
            core = f'<a href="{run.href}">{core}</a>'
        if run.strike:
            core = f"<del>{core}</del>"
        if run.bold:
            core = f"<strong>{core}</strong>"
        if run.italic:
            core = f"<em>{core}</em>"
        parts.append(f"{lead}{core}{trail}")
    return collapse_whitespace("".join(parts))


def _is_block(node: _Node) -> bool:
    """Tell whether the element is a block level element."""

    return node.tag not in INLINE_TAGS and node.tag not in VOID_TAGS


def _has_block_children(node: _Node) -> bool:
    """Tell whether the element holds block level children."""

    return any(
        not isinstance(child, str) and _is_block(child) for child in node.children
    )


def _own_text(node: _Node) -> str:
    """Return the text the element owns, keeping the inline order."""

    parts: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif _is_block(child):
            parts.append(" " + _own_text(child) + " ")
        else:
            parts.append(_own_text(child))
    return collapse_whitespace("".join(parts))
