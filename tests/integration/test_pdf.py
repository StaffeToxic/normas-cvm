"""Integration tests for textual PDF extraction and zone normalization (T010 / US3).

Verifies Poppler layout extraction, repeating header/footer stripping,
hyphenation resolution, URL preservation across line breaks, bolding of legal
devices (Art., §, Parágrafo único, items, subitems), structural headings,
detection of scanned PDFs (ocr-pendente) and complex tables (tabela-nao-reproduzida).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import unittest

from cvm_archive.convert.pdf import convert_pdf, extract_pdf_pages, find_pdftotext
from cvm_archive.normalize.text import (
    clean_page_zones,
    format_pdf_blocks,
    join_pdf_lines,
    reconstruct_pdf_paragraphs,
)

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "pdf"


def read_fixture_bytes(name: str) -> bytes:
    """Read a fixture as raw bytes."""
    return (FIXTURES / name).read_bytes()


class ManifestTests(unittest.TestCase):
    """The PDF fixtures carry their own provenance manifest and valid digests."""

    def setUp(self):
        self.raw = (FIXTURES / "manifest.json").read_text(encoding="utf-8")
        self.manifest = json.loads(self.raw)
        self.entries = {
            entry["arquivo"]: entry for entry in self.manifest["fixtures"]
        }

    def test_every_file_matches_its_manifest_digest(self):
        for name, entry in self.entries.items():
            content = read_fixture_bytes(name)
            self.assertEqual(
                hashlib.sha256(content).hexdigest(),
                entry["sha256"],
                f"digest mismatch for fixture {name}",
            )


class PopplerDiscoveryTests(unittest.TestCase):
    """The Poppler binary is discovered from PATH or environment."""

    def test_pdftotext_is_found(self):
        exe = find_pdftotext()
        self.assertIsNotNone(exe, "pdftotext must be discoverable in test environment")


class PageZoneNormalizationTests(unittest.TestCase):
    """Headers and footers are identified by frequency in top/bottom zones."""

    def test_strip_repeated_headers_and_page_numbers(self):
        page1 = (
            "COMISSÃO DE VALORES MOBILIÁRIOS\n"
            "Rua Sete de Setembro, 111\n"
            "www.cvm.gov.br\n"
            "PARECER DE ORIENTAÇÃO CVM Nº 40, DE 11 DE OUTUBRO DE 2022\n"
            "Corpo da página 1.\n"
            "1\n"
        )
        page2 = (
            "COMISSÃO DE VALORES MOBILIÁRIOS\n"
            "Rua Sete de Setembro, 111\n"
            "www.cvm.gov.br\n"
            "Corpo da página 2 com dispositivo Art. 1º.\n"
            "2\n"
        )
        cleaned = clean_page_zones([page1, page2])
        self.assertEqual(len(cleaned), 2)
        # Repeated institutional header is stripped from both pages
        self.assertNotIn("Rua Sete de Setembro", cleaned[0])
        self.assertNotIn("Rua Sete de Setembro", cleaned[1])
        # Epigraph of the act on page 1 is preserved
        self.assertIn("PARECER DE ORIENTAÇÃO CVM Nº 40", cleaned[0])
        # Body text is preserved
        self.assertIn("Corpo da página 1.", cleaned[0])
        self.assertIn("Corpo da página 2 com dispositivo Art. 1º.", cleaned[1])
        # Standalone page numbers in footer are stripped
        lines_p1 = [ln.strip() for ln in cleaned[0].split("\n") if ln.strip()]
        lines_p2 = [ln.strip() for ln in cleaned[1].split("\n") if ln.strip()]
        self.assertNotEqual(lines_p1[-1], "1")
        self.assertNotEqual(lines_p2[-1], "2")

    def test_single_page_removes_standalone_page_number_only(self):
        page = "RESOLUÇÃO CVM Nº 999\nArt. 1º Texto.\n1\n"
        cleaned = clean_page_zones([page])
        self.assertEqual(len(cleaned), 1)
        self.assertIn("RESOLUÇÃO CVM Nº 999", cleaned[0])
        self.assertIn("Art. 1º Texto.", cleaned[0])
        lines = [ln.strip() for ln in cleaned[0].split("\n") if ln.strip()]
        self.assertNotEqual(lines[-1], "1")


class HyphenationAndUrlTests(unittest.TestCase):
    """Line-break hyphens and split URLs are resolved correctly."""

    def test_soft_hyphen_is_joined(self):
        lines = ["Criptoativos são ativos com regu-", "lação específica."]
        joined = join_pdf_lines(lines)
        self.assertEqual(joined, "Criptoativos são ativos com regulação específica.")

    def test_lexical_hyphen_prefix_is_kept(self):
        lines = ["Aplicam-se as regras de sub-", "item e anti-", "fraude."]
        joined = join_pdf_lines(lines)
        self.assertEqual(joined, "Aplicam-se as regras de sub-item e anti-fraude.")

    def test_broken_url_across_lines_is_preserved_without_space(self):
        lines = [
            "disponível em https://www.oecd.org/daf/fin/financial-",
            "markets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf, último acesso",
        ]
        joined = join_pdf_lines(lines)
        expected_url = (
            "https://www.oecd.org/daf/fin/financial-markets/Why-Decentralised-"
            "Finance-DeFi-Matters-and-the-Policy-Implications.pdf"
        )
        self.assertIn(expected_url, joined)
        self.assertNotIn("financial- markets", joined)


class LegalBlockFormattingTests(unittest.TestCase):
    """Devices and headings are properly recognized and formatted."""

    def test_devices_and_headings_formatting(self):
        pages = [
            (
                "PARECER DE ORIENTAÇÃO CVM Nº 40, DE 11 DE OUTUBRO DE 2022\n\n"
                "1. Objeto deste Parecer de Orientação\n\n"
                "Art. 1º O Colegiado aprova as regras.\n\n"
                "I - primeiro inciso;\n\n"
                "§ 1º Primeiro parágrafo.\n\n"
                "Parágrafo único. Regra única.\n\n"
                "a) primeira alínea."
            )
        ]
        paras = reconstruct_pdf_paragraphs(pages)
        md = format_pdf_blocks(paras)
        self.assertIn("# PARECER DE ORIENTAÇÃO CVM Nº 40, DE 11 DE OUTUBRO DE 2022", md)
        self.assertIn("## 1. Objeto deste Parecer de Orientação", md)
        self.assertIn("**Art. 1º** O Colegiado aprova as regras.", md)
        self.assertIn("I - primeiro inciso;", md)
        self.assertIn("**§ 1º** Primeiro parágrafo.", md)
        self.assertIn("**Parágrafo único.** Regra única.", md)
        self.assertIn("a) primeira alínea.", md)


class PdfConversionIntegrationTests(unittest.TestCase):
    """Full conversion of sample PDF fixture."""

    def setUp(self):
        self.pdf_bytes = read_fixture_bytes("pare040-sample.pdf")

    def test_sample_parecer_conversion(self):
        conv = convert_pdf(self.pdf_bytes, "https://conteudo.cvm.gov.br/pare040.pdf")
        self.assertIsNone(conv.pending_reason)
        md = conv.markdown
        # Act title heading
        self.assertIn("# PARECER DE ORIENTAÇÃO CVM Nº 40, DE 11 DE OUTUBRO DE 2022", md)
        # Topics
        self.assertIn("## 1. Objeto deste Parecer de Orientação", md)
        self.assertIn("## 2. Mercado de Valores Mobiliários e Criptoativos", md)
        # Legal devices bolded
        self.assertIn("**Art. 1º**", md)
        self.assertIn("**§ 1º**", md)
        self.assertIn("**§ 2º**", md)
        self.assertIn("**Parágrafo único.**", md)
        self.assertIn("I - aos participantes do mercado;", md)
        self.assertIn("a) relativamente aos emissores registrados;", md)
        # Institutional header not repeated
        self.assertNotIn("Rua Sete de Setembro", md)
        # Footnotes preserved
        self.assertIn("1 Essa definição cumpre o fim de delinear o objeto", md)
        # Broken OECD URL joined cleanly
        self.assertIn(
            "https://www.oecd.org/daf/fin/financial-markets/Why-Decentralised-Finance-DeFi-Matters-and-the-Policy-Implications.pdf",
            md,
        )


class PdfPendingReasonTests(unittest.TestCase):
    """Fidelity gates: failure to extract or complex tables yield explicit pending states."""

    def test_empty_bytes_is_arquivo_vazio(self):
        conv = convert_pdf(b"", "https://example.com/vazio.pdf")
        self.assertEqual(conv.pending_reason, "arquivo-vazio")

    def test_scanned_pdf_triggers_ocr_pendente(self):
        empty_pdf = read_fixture_bytes("sem-texto.pdf")
        conv = convert_pdf(empty_pdf, "https://example.com/scanned.pdf")
        self.assertEqual(conv.pending_reason, "ocr-pendente")

    def test_complex_table_triggers_tabela_nao_reproduzida(self):
        table_pdf = read_fixture_bytes("tabela-complexa.pdf")
        conv = convert_pdf(table_pdf, "https://example.com/table.pdf")
        self.assertEqual(conv.pending_reason, "tabela-nao-reproduzida")

    def test_missing_poppler_binary_triggers_pending(self):
        conv = convert_pdf(
            read_fixture_bytes("pare040-sample.pdf"),
            "https://example.com/doc.pdf",
            poppler_bin="caminho_inexistente_para_pdftotext",
        )
        self.assertIn("pdf-conversor", conv.pending_reason)


if __name__ == "__main__":
    unittest.main()
