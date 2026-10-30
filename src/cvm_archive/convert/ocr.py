"""OCR extraction for textless PDF pages using Tesseract (Decision D-10 / FR-006 / FR-012 / FR-014).

Fidelity rules:
- FR-006 / D-10: OCR is executed strictly and exclusively on pages that lack an
  extractable text layer. Textual pages (including sparse signature pages) must
  always preserve the original text layer extracted by Poppler.
- Blank pages (pure white canvas / no ink) are distinguished from raster/scanned
  pages and do not trigger OCR errors or noise.
- FR-012: Any document containing text derived from OCR must prepend a visible
  notice banner to the Markdown body.
- FR-014: Fidelity gates verify minimum recognizable character output and valid
  token sequence; incomplete or failing OCR marks the act as pending
  (``ocr-pendente``).
- Standard library only plus external CLI tools (Poppler and Tesseract).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from cvm_archive.convert.pdf import (
    _has_complex_table,
    extract_pdf_pages_raw,
    find_pdftotext,
)
from cvm_archive.models import Conversion
from cvm_archive.normalize.text import (
    clean_page_zones,
    collapse_whitespace,
    format_pdf_blocks,
    reconstruct_pdf_paragraphs,
)

__all__ = [
    "OCR_NOTICE_BANNER",
    "convert_pdf_ocr",
    "find_pdftoppm",
    "find_tesseract",
    "is_ppm_blank",
    "render_pdf_page_ppm",
    "run_tesseract",
]

OCR_NOTICE_BANNER: str = (
    "> **Aviso:** Texto obtido por reconhecimento óptico de caracteres (OCR) a partir do "
    "documento original digitalizado. Pode conter imperfeições de transcrição.\n\n"
)

_KNOWN_TESSERACT_PATHS: tuple[Path, ...] = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    Path.home() / ".local" / "bin" / ("tesseract.exe" if os.name == "nt" else "tesseract"),
)

_KNOWN_PDFTOPPM_PATHS: tuple[Path, ...] = (
    Path(
        r"C:\Users\User\Documents\normas-cvm\.scratch\benchmark\tools\poppler\poppler-26.09.0\Library\bin\pdftoppm.exe"
    ),
    Path.home() / ".local" / "bin" / ("pdftoppm.exe" if os.name == "nt" else "pdftoppm"),
)


def find_tesseract() -> str | None:
    """Locate the tesseract executable from PATH, environment or standard directories."""
    found = shutil.which("tesseract")
    if found:
        return found
    env_path = os.environ.get("TESSERACT_PATH") or os.environ.get("CVM_TESSERACT_BIN")
    if env_path:
        exe = Path(env_path)
        if exe.is_file():
            return str(exe)
        exe = Path(env_path) / ("tesseract.exe" if os.name == "nt" else "tesseract")
        if exe.is_file():
            return str(exe)
    for candidate in _KNOWN_TESSERACT_PATHS:
        if candidate.is_file():
            return str(candidate)
    return None


def find_pdftoppm() -> str | None:
    """Locate the pdftoppm executable from PATH, environment or beside pdftotext."""
    found = shutil.which("pdftoppm")
    if found:
        return found
    env_path = os.environ.get("POPPLER_PATH") or os.environ.get("CVM_PDFTOPPM_BIN")
    if env_path:
        exe = Path(env_path)
        if exe.is_file():
            return str(exe)
        exe = Path(env_path) / ("pdftoppm.exe" if os.name == "nt" else "pdftoppm")
        if exe.is_file():
            return str(exe)
    ptotext = find_pdftotext()
    if ptotext:
        ppm_candidate = Path(ptotext).parent / (
            "pdftoppm.exe" if os.name == "nt" else "pdftoppm"
        )
        if ppm_candidate.is_file():
            return str(ppm_candidate)
    for candidate in _KNOWN_PDFTOPPM_PATHS:
        if candidate.is_file():
            return str(candidate)
    return None


def is_ppm_blank(ppm_bytes: bytes, threshold: float = 0.998) -> bool:
    """Determine whether a binary PPM (P6) image is essentially a blank white canvas."""
    if not ppm_bytes.startswith(b"P6"):
        return False
    tokens: list[bytes] = []
    idx = 0
    length = len(ppm_bytes)
    while len(tokens) < 4 and idx < length:
        if ppm_bytes[idx : idx + 1] == b"#":
            idx = ppm_bytes.find(b"\n", idx) + 1
            continue
        if ppm_bytes[idx : idx + 1] in b" \t\r\n":
            idx += 1
            continue
        end = idx
        while end < length and ppm_bytes[end : end + 1] not in b" \t\r\n":
            end += 1
        tokens.append(ppm_bytes[idx:end])
        idx = end + 1

    if len(tokens) < 4:
        return False

    pixel_data = ppm_bytes[idx:]
    if not pixel_data:
        return True

    # Count non-white bytes (values below 240)
    non_white = sum(1 for b in pixel_data if b < 240)
    white_ratio = 1.0 - (non_white / len(pixel_data))
    return white_ratio >= threshold


def render_pdf_page_ppm(
    pdf_bytes: bytes,
    page_number: int,
    *,
    pdftoppm_bin: str | None = None,
) -> bytes:
    """Render a specific 1-indexed page of a PDF document to raw PPM bytes."""
    exe = pdftoppm_bin or find_pdftoppm()
    if not exe:
        raise FileNotFoundError("pdftoppm executable not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_file = os.path.join(tmpdir, "input.pdf")
        with open(pdf_file, "wb") as f:
            f.write(pdf_bytes)

        prefix = os.path.join(tmpdir, "page")
        cmd = [
            exe,
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-r",
            "150",
            pdf_file,
            prefix,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise subprocess.SubprocessError(
                f"pdftoppm failed with code {result.returncode}: {result.stderr.decode('utf-8', errors='replace')}"
            )

        rendered_files = [f for f in os.listdir(tmpdir) if f.startswith("page") and f.endswith(".ppm")]
        if not rendered_files:
            raise FileNotFoundError(f"pdftoppm produced no output for page {page_number}")

        page_ppm = os.path.join(tmpdir, sorted(rendered_files)[0])
        with open(page_ppm, "rb") as f:
            return f.read()


def run_tesseract(
    image_bytes: bytes,
    *,
    lang: str = "por",
    tesseract_bin: str | None = None,
) -> str:
    """Execute Tesseract OCR on image bytes and return extracted text."""
    exe = tesseract_bin or find_tesseract()
    if not exe:
        raise FileNotFoundError("tesseract executable not found")

    with tempfile.NamedTemporaryFile(suffix=".ppm", delete=False) as temporary:
        temporary.write(image_bytes)
        temporary_path = temporary.name

    try:
        cmd = [exe, temporary_path, "stdout", "-l", lang]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise subprocess.SubprocessError(f"tesseract failed with code {result.returncode}: {err}")
        return result.stdout.decode("utf-8", errors="replace")
    finally:
        try:
            os.remove(temporary_path)
        except OSError:
            pass


def convert_pdf_ocr(
    pdf_bytes: bytes,
    source_url: str,
    *,
    tesseract_bin: str | None = None,
    poppler_bin: str | None = None,
    pdftoppm_bin: str | None = None,
) -> Conversion:
    """Convert a PDF document, running OCR strictly and only on textless pages."""
    if not pdf_bytes or not pdf_bytes.strip():
        return Conversion(source_text="", markdown="", pending_reason="arquivo-vazio")

    ptotext_exe = poppler_bin or find_pdftotext()
    if not ptotext_exe:
        return Conversion(
            source_text="",
            markdown="",
            pending_reason="pdf-conversor-pendente",
        )

    try:
        raw_pages = extract_pdf_pages_raw(pdf_bytes, poppler_bin=ptotext_exe)
    except (subprocess.SubprocessError, OSError) as exc:
        return Conversion(
            source_text="",
            markdown="",
            warnings=(f"poppler-exec-error: {exc}",),
            pending_reason="pdf-conversor-falha",
        )

    if not raw_pages:
        return Conversion(
            source_text="",
            markdown="",
            pending_reason="ocr-pendente",
            warnings=("documento-sem-texto",),
        )

    collected_pages: list[str] = []
    ocr_applied = False
    ocr_warnings: list[str] = []

    ppm_exe = pdftoppm_bin or find_pdftoppm()
    tess_exe = tesseract_bin or find_tesseract()

    for page_idx, page_raw in enumerate(raw_pages, start=1):
        cleaned_text = page_raw.strip()
        # FR-006 / D-10: If the page already has an extractable text layer, keep it!
        # This includes sparse signature sheets (e.g. 50-200 chars).
        if cleaned_text:
            collected_pages.append(page_raw)
            continue

        # Page has no text layer: inspect visual rendering
        if not ppm_exe:
            return Conversion(
                source_text="",
                markdown="",
                pending_reason="ocr-pendente",
                warnings=("pdftoppm-indisponivel",),
            )

        try:
            ppm_data = render_pdf_page_ppm(pdf_bytes, page_idx, pdftoppm_bin=ppm_exe)
        except (subprocess.SubprocessError, OSError, FileNotFoundError) as exc:
            return Conversion(
                source_text="",
                markdown="",
                pending_reason="ocr-pendente",
                warnings=(f"renderizacao-falhou: {exc}",),
            )

        # Distinguish blank page (white canvas) from scanned/raster/vector drawings
        if is_ppm_blank(ppm_data):
            # Pure blank page: contributes no text and is not an error
            continue

        # Page is non-blank and lacks text: OCR is required!
        if not tess_exe:
            return Conversion(
                source_text="",
                markdown="",
                pending_reason="ocr-pendente",
                warnings=("ocr-tesseract-indisponivel",),
            )

        try:
            ocr_text = run_tesseract(ppm_data, lang="por", tesseract_bin=tess_exe)
        except (subprocess.SubprocessError, OSError) as exc:
            return Conversion(
                source_text="",
                markdown="",
                pending_reason="ocr-pendente",
                warnings=(f"ocr-exec-falhou: {exc}",),
            )

        # FR-014: Fidelity gate on OCR text output
        alphanumeric_count = len(re.findall(r"\w", ocr_text))
        if alphanumeric_count < 10:
            return Conversion(
                source_text="",
                markdown="",
                pending_reason="ocr-pendente",
                warnings=("ocr-reconhecimento-insuficiente",),
            )

        collected_pages.append(ocr_text)
        ocr_applied = True

    if not collected_pages:
        return Conversion(
            source_text="",
            markdown="",
            pending_reason="ocr-pendente",
            warnings=("documento-sem-texto",),
        )

    raw_text = "\n\n".join(collapse_whitespace(p) for p in collected_pages)

    if _has_complex_table(collected_pages):
        return Conversion(
            source_text=raw_text,
            markdown="",
            pending_reason="tabela-nao-reproduzida",
        )

    cleaned_pages = clean_page_zones(collected_pages)
    paragraphs = reconstruct_pdf_paragraphs(cleaned_pages)
    if not paragraphs:
        return Conversion(
            source_text=raw_text,
            markdown="",
            pending_reason="ocr-pendente",
        )

    markdown = format_pdf_blocks(paragraphs)

    # FR-012: Prepend mandatory notice if OCR was used
    if ocr_applied:
        markdown = OCR_NOTICE_BANNER + markdown
        ocr_warnings.append("ocr-utilizado")

    source_text = "\n\n".join(paragraphs)
    return Conversion(
        source_text=source_text,
        markdown=markdown,
        warnings=tuple(ocr_warnings),
        pending_reason=None,
    )
