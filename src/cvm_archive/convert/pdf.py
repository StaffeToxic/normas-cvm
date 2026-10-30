"""Conversion of official textual PDF documents into publication candidates.

The converter extracts textual layout using Poppler (``pdftotext -layout``),
cleans repeating headers and footers across page zones, resolves hyphenated
line breaks without breaking URLs, codes or lexical prefixes, bolds legal
device markers (``Art.``, ``§``, ``Parágrafo único``), and formats structural
headings into Markdown.

Fidelity rules (Constitution Principle II):
- Scanned PDFs or pages lacking an extractable text layer are marked as
  pending (``ocr-pendente``) for OCR processing.
- Tables whose complex multi-column grid cannot be reproduced faithfully are
  marked as pending (``tabela-nao-reproduzida``) instead of flattening text.
- If Poppler cannot be located, the document remains pending
  (``pdf-conversor-pendente``).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from cvm_archive.models import Conversion
from cvm_archive.normalize.text import (
    clean_page_zones,
    collapse_whitespace,
    format_pdf_blocks,
    reconstruct_pdf_paragraphs,
)

__all__ = ["convert_pdf", "extract_pdf_pages", "extract_pdf_pages_raw", "find_pdftotext"]

_KNOWN_POPPLER_PATHS: tuple[Path, ...] = (
    Path(r"C:\Users\User\Documents\normas-cvm\.scratch\benchmark\tools\poppler\poppler-26.09.0\Library\bin\pdftotext.exe"),
    Path.home() / ".local" / "bin" / ("pdftotext.exe" if os.name == "nt" else "pdftotext"),
)


def find_pdftotext() -> str | None:
    """Locate the pdftotext executable from PATH, environment or local tools."""
    found = shutil.which("pdftotext")
    if found:
        return found
    env_path = os.environ.get("POPPLER_PATH")
    if env_path:
        exe = Path(env_path) / ("pdftotext.exe" if os.name == "nt" else "pdftotext")
        if exe.is_file():
            return str(exe)
    for candidate in _KNOWN_POPPLER_PATHS:
        if candidate.is_file():
            return str(candidate)
    return None


def extract_pdf_pages(data: bytes, *, poppler_bin: str | None = None) -> list[str]:
    """Extract page layout text from raw PDF bytes using pdftotext -layout."""
    raw_pages = extract_pdf_pages_raw(data, poppler_bin=poppler_bin)
    return [page for page in raw_pages if page.strip()]


def extract_pdf_pages_raw(data: bytes, *, poppler_bin: str | None = None) -> list[str]:
    """Extract all pages including empty ones to preserve 1-based page indexing."""
    exe = poppler_bin or find_pdftotext()
    if not exe:
        raise FileNotFoundError("pdftotext executable not found")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temporary:
        temporary.write(data)
        temporary_path = temporary.name

    try:
        result = subprocess.run(
            [exe, "-layout", "-enc", "UTF-8", temporary_path, "-"],
            capture_output=True,
            check=True,
            timeout=120,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        pages = text.split("\x0c")
        if pages and not pages[-1].strip():
            pages.pop()
        return pages
    finally:
        try:
            os.remove(temporary_path)
        except OSError:
            pass


def _has_complex_table(pages: list[str]) -> bool:
    """Detect whether any page holds an unparseable complex tabular matrix."""
    for page in pages:
        lines = [ln.strip() for ln in page.split("\n") if ln.strip()]
        table_lines = 0
        for line in lines:
            if "|" in line or "+-" in line or "+=" in line:
                table_lines += 1
            elif (
                len(re.findall(r"\s{3,}", line)) >= 2
                and not line.startswith("Rua")
                and not line.startswith("SCN")
                and not line.startswith("COMISSÃO")
            ):
                table_lines += 1
        if table_lines >= 4:
            return True
    return False


def convert_pdf(
    pdf_bytes: bytes,
    source_url: str,
    *,
    poppler_bin: str | None = None,
    allow_ocr: bool = False,
    tesseract_bin: str | None = None,
    pdftoppm_bin: str | None = None,
) -> Conversion:
    """Convert official textual PDF bytes into a Markdown conversion candidate."""
    if allow_ocr:
        from cvm_archive.convert.ocr import convert_pdf_ocr

        return convert_pdf_ocr(
            pdf_bytes,
            source_url,
            tesseract_bin=tesseract_bin,
            poppler_bin=poppler_bin,
            pdftoppm_bin=pdftoppm_bin,
        )

    if not pdf_bytes or not pdf_bytes.strip():
        return Conversion(source_text="", markdown="", pending_reason="arquivo-vazio")

    exe = poppler_bin or find_pdftotext()
    if not exe:
        return Conversion(
            source_text="",
            markdown="",
            pending_reason="pdf-conversor-pendente",
        )

    try:
        pages = extract_pdf_pages(pdf_bytes, poppler_bin=exe)
    except (subprocess.SubprocessError, OSError) as exc:
        return Conversion(
            source_text="",
            markdown="",
            warnings=(f"poppler-exec-error: {exc}",),
            pending_reason="pdf-conversor-falha",
        )

    total_chars = sum(len(collapse_whitespace(p)) for p in pages)
    if not pages or total_chars < 50:
        return Conversion(
            source_text="",
            markdown="",
            pending_reason="ocr-pendente",
        )

    raw_text = "\n\n".join(collapse_whitespace(p) for p in pages)

    if _has_complex_table(pages):
        return Conversion(
            source_text=raw_text,
            markdown="",
            pending_reason="tabela-nao-reproduzida",
        )

    cleaned_pages = clean_page_zones(pages)
    paragraphs = reconstruct_pdf_paragraphs(cleaned_pages)
    if not paragraphs:
        return Conversion(
            source_text=raw_text,
            markdown="",
            pending_reason="ocr-pendente",
        )

    markdown = format_pdf_blocks(paragraphs)
    source_text = "\n\n".join(paragraphs)

    return Conversion(
        source_text=source_text,
        markdown=markdown,
        warnings=(),
        pending_reason=None,
    )
