"""Conditional auxiliary table extraction from official Word DOCX packages.

Decision D-8 / FR-011 / C9:
- The official DOCX, when linked on the act page and edition-compatible, serves
  as a preferred auxiliary source for table geometry.
- Parsed using standard library only (zipfile and xml.etree.ElementTree).
- Handles horizontal merges (w:gridSpan -> colspan) and vertical merges
  (w:vMerge -> rowspan).
- Preserves empty cells and table matrix fidelity.
- Renders simple tables as Markdown, and complex tables with spans or multiline
  content as HTML tables.
- Fidelity gates:
  - Sabotaged or inconsistent grids fail (tabela-estrutura-inconsistente).
  - Duplicate paragraphs in a single cell (the Resolução 175 LIG case) are
    detected and marked as pending (tabela-discrepancia-edicao), preventing
    silent omission.
  - Corrupt or invalid archives are marked as pending (arquivo-corrompido).
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from html import escape

from cvm_archive.models import Conversion
from cvm_archive.normalize.text import collapse_whitespace

__all__ = [
    "WordCell",
    "WordTable",
    "convert_word_tables",
    "extract_docx_tables",
]

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"


@dataclass(slots=True)
class WordCell:
    """A cell within a Word table."""

    text: str
    colspan: int = 1
    rowspan: int = 1
    header: bool = False
    paragraphs: list[str] = field(default_factory=list)
    _start_col: int = 0


@dataclass(slots=True)
class WordTable:
    """A table extracted from a Word document whose grid was validated."""

    rows: list[list[WordCell]]
    has_header: bool = False

    def render_markdown(self) -> str:
        """Render as a Markdown table if simple, or HTML table if complex."""
        if self._is_simple():
            return self._render_markdown_table()
        return self._render_html_table()

    def _is_simple(self) -> bool:
        """Tell whether the table has a simple rectangular structure without spans."""
        if not self.rows:
            return False
        # Must have header in first row and no header in following rows
        if not all(cell.header for cell in self.rows[0]):
            return False
        if any(cell.header for row in self.rows[1:] for cell in row):
            return False
        # No spans, non-empty header text, single-line text
        for row in self.rows:
            for cell in row:
                if cell.colspan > 1 or cell.rowspan > 1:
                    return False
                if "\n" in cell.text:
                    return False
        return True

    def _render_markdown_table(self) -> str:
        """Render a simple table in standard Markdown format."""
        lines: list[str] = []
        for index, row in enumerate(self.rows):
            cells = [cell.text.replace("|", "\\|") for cell in row]
            lines.append("| " + " | ".join(cells) + " |")
            if index == 0:
                lines.append("| " + " | ".join("---" for _ in row) + " |")
        return "\n".join(lines)

    def _render_html_table(self) -> str:
        """Render a table with spans or multiline content as an HTML table."""
        lines: list[str] = ["<table>"]
        for row in self.rows:
            cells: list[str] = []
            for cell in row:
                tag = "th" if cell.header else "td"
                attributes = ""
                if cell.colspan > 1:
                    attributes += f' colspan="{cell.colspan}"'
                if cell.rowspan > 1:
                    attributes += f' rowspan="{cell.rowspan}"'
                escaped = escape(cell.text).replace("\n", "<br>")
                cells.append(f"<{tag}{attributes}>{escaped}</{tag}>")
            lines.append("<tr>" + "".join(cells) + "</tr>")
        lines.append("</table>")
        return "\n".join(lines)


def _grid_is_consistent(rows: list[list[WordCell]]) -> bool:
    """Validate that every position of the matrix is accounted for without overlap."""
    if not rows:
        return False
    occupied: set[tuple[int, int]] = set()
    for index, row in enumerate(rows):
        column = 0
        for cell in row:
            while (index, column) in occupied:
                column += 1
            if index + cell.rowspan > len(rows):
                return False
            for line in range(cell.rowspan):
                for offset in range(cell.colspan):
                    position = (index + line, column + offset)
                    if position in occupied:
                        return False
                    occupied.add(position)
            column += cell.colspan

    widths = {
        max((column for row, column in occupied if row == index), default=-1) + 1
        for index in range(len(rows))
    }
    return len(widths) == 1 and all(
        len([column for row, column in occupied if row == index]) == next(iter(widths))
        for index in range(len(rows))
    )


def _parse_table(tbl: ET.Element) -> tuple[WordTable | None, str | None]:
    """Parse a single <w:tbl> element into a WordTable."""
    rows: list[list[WordCell]] = []
    active_anchors: dict[int, WordCell] = {}
    has_header = False

    for tr in tbl.findall(f"{W}tr"):
        tr_pr = tr.find(f"{W}trPr")
        is_header_row = (
            tr_pr is not None and tr_pr.find(f"{W}tblHeader") is not None
        )
        if is_header_row:
            has_header = True

        row_cells: list[WordCell] = []
        col_idx = 0

        for tc in tr.findall(f"{W}tc"):
            tc_pr = tc.find(f"{W}tcPr")
            colspan = 1
            vmerge_val = None
            has_vmerge = False

            if tc_pr is not None:
                grid_span = tc_pr.find(f"{W}gridSpan")
                if grid_span is not None:
                    val = grid_span.attrib.get(f"{W}val", "1").strip()
                    if not val.isdigit() or int(val) < 1:
                        return None, "tabela-estrutura-inconsistente: gridSpan invalido"
                    colspan = int(val)

                v_merge = tc_pr.find(f"{W}vMerge")
                if v_merge is not None:
                    has_vmerge = True
                    vmerge_val = v_merge.attrib.get(f"{W}val", "continue").strip()

            paragraphs: list[str] = []
            for p in tc.findall(f"{W}p"):
                texts = [t.text for t in p.iter(f"{W}t") if t.text]
                p_text = collapse_whitespace("".join(texts))
                if p_text:
                    paragraphs.append(p_text)

            # Check D-8 duplicate identical paragraphs in cell (e.g. Resolução 175 LIG case)
            if len(paragraphs) >= 2:
                for i in range(len(paragraphs) - 1):
                    if paragraphs[i] == paragraphs[i + 1]:
                        return (
                            None,
                            "tabela-discrepancia-edicao: paragrafos duplicados na celula",
                        )

            cell_text = "\n".join(paragraphs)

            if has_vmerge:
                if vmerge_val == "restart":
                    cell = WordCell(
                        text=cell_text,
                        colspan=colspan,
                        rowspan=1,
                        header=is_header_row,
                        paragraphs=paragraphs,
                        _start_col=col_idx,
                    )
                    for c in range(col_idx, col_idx + colspan):
                        active_anchors[c] = cell
                    row_cells.append(cell)
                elif vmerge_val == "continue":
                    anchor = active_anchors.get(col_idx)
                    if anchor is None:
                        return (
                            None,
                            "tabela-estrutura-inconsistente: vMerge continue sem restart",
                        )
                    if anchor.colspan != colspan:
                        return (
                            None,
                            "tabela-estrutura-inconsistente: vMerge com colspan divergente",
                        )
                    if col_idx == anchor._start_col:
                        anchor.rowspan += 1
                else:
                    return (
                        None,
                        f"tabela-estrutura-inconsistente: vMerge desconhecido {vmerge_val}",
                    )
            else:
                for c in range(col_idx, col_idx + colspan):
                    active_anchors.pop(c, None)
                cell = WordCell(
                    text=cell_text,
                    colspan=colspan,
                    rowspan=1,
                    header=is_header_row,
                    paragraphs=paragraphs,
                    _start_col=col_idx,
                )
                row_cells.append(cell)

            col_idx += colspan

        rows.append(row_cells)

    if not rows:
        return None, "tabela-vazia"

    if not _grid_is_consistent(rows):
        return None, "tabela-estrutura-inconsistente: grade assimetrica ou sobreposicao"

    return WordTable(rows=rows, has_header=has_header), None


def extract_docx_tables(
    docx_bytes: bytes,
) -> tuple[list[WordTable] | None, str | None]:
    """Extract and validate all tables from official DOCX bytes using standard library."""
    if not docx_bytes:
        return None, "arquivo-vazio"

    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            if "word/document.xml" not in archive.namelist():
                return None, "arquivo-corrompido: word/document.xml ausente"
            document_xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        return None, f"arquivo-corrompido: {exc}"

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        return None, f"arquivo-corrompido: {exc}"

    body = root.find(f"{W}body")
    if body is None:
        return [], None

    tables: list[WordTable] = []
    for tbl in body.findall(f"{W}tbl"):
        table, error = _parse_table(tbl)
        if error:
            return None, error
        if table:
            tables.append(table)

    return tables, None


def convert_word_tables(docx_bytes: bytes, source_url: str) -> Conversion:
    """Convert tables from an official DOCX into a candidate conversion."""
    tables, error = extract_docx_tables(docx_bytes)
    if error:
        return Conversion(source_text="", markdown="", pending_reason=error)

    if not tables:
        return Conversion(
            source_text="",
            markdown="",
            warnings=("nenhuma-tabela-encontrada",),
            pending_reason=None,
        )

    rendered_markdown: list[str] = []
    source_parts: list[str] = []

    for table in tables:
        rendered_markdown.append(table.render_markdown())
        for row in table.rows:
            source_parts.append(" | ".join(cell.text for cell in row))

    return Conversion(
        source_text="\n\n".join(source_parts),
        markdown="\n\n".join(rendered_markdown),
        warnings=(),
        pending_reason=None,
    )
