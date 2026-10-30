"""Integration tests for OCR of textless PDF pages (Decision D-10 / FR-006 / FR-012 / FR-014).

Verifies:
- Textless pages trigger OCR; textual pages (including sparse signature sheets)
  preserve the Poppler text layer without OCR.
- Distinguishes blank pages (white canvas) from scanned/raster/drawing pages.
- Mandatory visible notice prepended when OCR is utilized.
- Fidelity gates reject noise or insufficient recognition output.
- Manifest integrity validation for all OCR fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from cvm_archive.convert.ocr import (
    OCR_NOTICE_BANNER,
    convert_pdf_ocr,
    find_pdftoppm,
    find_tesseract,
    is_ppm_blank,
)
from cvm_archive.convert.pdf import convert_pdf

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "ocr"


def get_mock_tesseract_bin() -> str:
    """Get the appropriate mock tesseract runner for the current OS."""
    if os.name == "nt":
        return str(FIXTURES_DIR / "mock_tesseract.cmd")
    return str(FIXTURES_DIR / "mock_tesseract.sh")


class OcrIntegrationTests(unittest.TestCase):
    """Integration and fidelity tests for OCR processing."""

    def test_fixtures_manifest_digest(self) -> None:
        """Every PDF fixture in tests/fixtures/ocr must match its sha256 in manifest.json."""
        manifest_path = FIXTURES_DIR / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json missing in fixtures/ocr")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for filename, meta in manifest.items():
            fixture_path = FIXTURES_DIR / filename
            self.assertTrue(fixture_path.exists(), f"Fixture {filename} missing")
            content = fixture_path.read_bytes()
            self.assertEqual(len(content), meta["bytes"], f"Byte mismatch for {filename}")
            digest = hashlib.sha256(content).hexdigest()
            self.assertEqual(digest, meta["sha256"], f"Digest mismatch for {filename}")

    def test_empty_bytes_returns_arquivo_vazio(self) -> None:
        """Empty input bytes must immediately return arquivo-vazio."""
        conv = convert_pdf_ocr(b"", "https://example.com/doc.pdf")
        self.assertEqual(conv.pending_reason, "arquivo-vazio")

    def test_missing_poppler_returns_pdf_conversor_pendente(self) -> None:
        """If Poppler is unavailable, pending reason must indicate missing converter."""
        fixture = (FIXTURES_DIR / "scanned-act.pdf").read_bytes()
        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/doc.pdf",
            poppler_bin="caminho_inexistente_para_pdftotext",
        )
        self.assertIn("pdf-conversor", conv.pending_reason)

    def test_sparse_signature_page_keeps_text_layer_without_ocr(self) -> None:
        """A page with sparse text (signature sheet) must NOT run OCR and retains native text."""
        fixture = (FIXTURES_DIR / "folha-assinatura-esparsa.pdf").read_bytes()
        mock_bin = get_mock_tesseract_bin()

        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/portaria.pdf",
            tesseract_bin=mock_bin,
        )

        self.assertIsNone(conv.pending_reason)
        self.assertEqual(conv.warnings, ())
        self.assertNotIn("Aviso: Texto obtido por reconhecimento óptico", conv.markdown)
        self.assertIn("MARCELO BARBOSA", conv.markdown)
        self.assertIn("Presidente da CVM", conv.markdown)

    def test_blank_page_does_not_trigger_ocr_noise(self) -> None:
        """A pure white page must be detected as blank and not sent to OCR."""
        fixture = (FIXTURES_DIR / "pagina-branca.pdf").read_bytes()
        mock_bin = get_mock_tesseract_bin()

        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/blank.pdf",
            tesseract_bin=mock_bin,
        )

        self.assertEqual(conv.pending_reason, "ocr-pendente")
        self.assertIn("documento-sem-texto", conv.warnings)

    def test_scanned_act_runs_ocr_and_prepends_notice(self) -> None:
        """A scanned page without text layer runs OCR, prepends notice and formats markdown."""
        fixture = (FIXTURES_DIR / "scanned-act.pdf").read_bytes()
        mock_bin = get_mock_tesseract_bin()

        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/portaria109.pdf",
            tesseract_bin=mock_bin,
        )

        self.assertIsNone(conv.pending_reason)
        self.assertIn("ocr-utilizado", conv.warnings)
        self.assertTrue(conv.markdown.startswith(OCR_NOTICE_BANNER))
        self.assertIn("PORTARIA CVM", conv.markdown)
        self.assertIn("**Art. 1º**", conv.markdown)
        self.assertIn("**Art. 2º**", conv.markdown)

    def test_mixed_document_preserves_text_and_ocrs_raster(self) -> None:
        """Mixed documents keep native text for textual pages and OCR text for raster pages."""
        fixture = (FIXTURES_DIR / "misto-texto-e-scan.pdf").read_bytes()
        mock_bin = get_mock_tesseract_bin()

        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/misto.pdf",
            tesseract_bin=mock_bin,
        )

        self.assertIsNone(conv.pending_reason)
        self.assertIn("ocr-utilizado", conv.warnings)
        self.assertTrue(conv.markdown.startswith(OCR_NOTICE_BANNER))
        # Text from native layer on page 1
        self.assertIn("PORTARIA CVM N 109", conv.markdown)
        # Text from OCR on page 2
        self.assertIn("**Art. 2º**", conv.markdown)

    def test_fidelity_gate_insufficient_ocr_output_fails(self) -> None:
        """OCR output with fewer than 10 alphanumeric characters must fail fidelity gate."""
        fixture = (FIXTURES_DIR / "scanned-act.pdf").read_bytes()

        # Temporary script that returns minimal noise
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("print('..')\n")
            noise_script = f.name

        try:
            if os.name == "nt":
                cmd_path = noise_script + ".cmd"
                Path(cmd_path).write_text(f'@echo off\npy "{noise_script}"\n', encoding="utf-8")
                test_bin = cmd_path
            else:
                Path(noise_script).chmod(0o755)
                test_bin = noise_script

            conv = convert_pdf_ocr(
                fixture,
                "https://example.com/doc.pdf",
                tesseract_bin=test_bin,
            )

            self.assertEqual(conv.pending_reason, "ocr-pendente")
            self.assertIn("ocr-reconhecimento-insuficiente", conv.warnings)
        finally:
            for p in (noise_script, noise_script + ".cmd"):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def test_missing_tesseract_binary_marks_pending(self) -> None:
        """Missing tesseract executable on page requiring OCR results in ocr-pendente."""
        fixture = (FIXTURES_DIR / "scanned-act.pdf").read_bytes()
        conv = convert_pdf_ocr(
            fixture,
            "https://example.com/doc.pdf",
            tesseract_bin="caminho_inexistente_tesseract_fake",
        )
        self.assertEqual(conv.pending_reason, "ocr-pendente")

    def test_convert_pdf_with_allow_ocr_flag(self) -> None:
        """Calling convert_pdf with allow_ocr=True delegates to OCR processor."""
        fixture = (FIXTURES_DIR / "scanned-act.pdf").read_bytes()
        mock_bin = get_mock_tesseract_bin()

        conv = convert_pdf(
            fixture,
            "https://example.com/doc.pdf",
            allow_ocr=True,
            tesseract_bin=mock_bin,
        )
        self.assertIsNone(conv.pending_reason)
        self.assertIn("ocr-utilizado", conv.warnings)
        self.assertTrue(conv.markdown.startswith(OCR_NOTICE_BANNER))

    def test_is_ppm_blank_white_vs_black(self) -> None:
        """is_ppm_blank accurately distinguishes white canvas from inked pixels."""
        # Pure white 10x10 PPM
        white_ppm = b"P6\n10 10\n255\n" + (b"\xff\xff\xff" * 100)
        self.assertTrue(is_ppm_blank(white_ppm))

        # Inked 10x10 PPM
        ink_ppm = b"P6\n10 10\n255\n" + (b"\x00\x00\x00" * 50) + (b"\xff\xff\xff" * 50)
        self.assertFalse(is_ppm_blank(ink_ppm))

        # Invalid format
        self.assertFalse(is_ppm_blank(b"NOT_PPM"))


if __name__ == "__main__":
    unittest.main()
