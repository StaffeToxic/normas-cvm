"""Integration tests for Word DOCX table extraction (Decision D-8 / FR-011 / C9)."""

from __future__ import annotations

import hashlib
import io
import json
import unittest
import zipfile
from pathlib import Path

from cvm_archive.convert.word import (
    WordCell,
    WordTable,
    convert_word_tables,
    extract_docx_tables,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "tables"


class WordTableTests(unittest.TestCase):
    """Fidelity and extraction tests for Word DOCX tables."""

    def test_tables_fixtures_manifest_digest(self) -> None:
        """Every fixture in tests/fixtures/tables must match its sha256 digest in manifest.json."""
        manifest_path = FIXTURES_DIR / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json does not exist in fixtures/tables")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        for filename, meta in manifest.items():
            fixture_path = FIXTURES_DIR / filename
            self.assertTrue(fixture_path.exists(), f"Fixture {filename} missing")
            data = fixture_path.read_bytes()
            self.assertEqual(len(data), meta["bytes"], f"Byte size mismatch for {filename}")
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(digest, meta["sha256"], f"Digest mismatch for {filename}")

    def test_simple_table_converts_to_markdown(self) -> None:
        """A regular rectangular table with a header row must render as standard Markdown."""
        fixture = (FIXTURES_DIR / "tabela-simples.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNone(conversion.pending_reason)
        self.assertIn("| Artigo | Descricao |", conversion.markdown)
        self.assertIn("| --- | --- |", conversion.markdown)
        self.assertIn("| Art. 1º | Regulamenta o mercado. |", conversion.markdown)
        self.assertIn("| Art. 2º | Revoga normas anteriores. |", conversion.markdown)

    def test_gridspan_converts_to_html_table(self) -> None:
        """A table with w:gridSpan (colspan) must render as an HTML table preserving span."""
        fixture = (FIXTURES_DIR / "tabela-gridspan.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNone(conversion.pending_reason)
        self.assertIn("<table>", conversion.markdown)
        self.assertIn('<th colspan="2">Parametro Global</th>', conversion.markdown)
        self.assertIn("<td>Acoes</td><td>100%</td>", conversion.markdown)

    def test_vmerge_converts_to_html_table(self) -> None:
        """A table with w:vMerge (rowspan) must render as an HTML table preserving span."""
        fixture = (FIXTURES_DIR / "tabela-vmerge.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNone(conversion.pending_reason)
        self.assertIn("<table>", conversion.markdown)
        self.assertIn('<td rowspan="2">Renda Fixa</td><td>CDB</td><td>10%</td>', conversion.markdown)
        self.assertIn("<td>LCI</td><td>20%</td>", conversion.markdown)

    def test_empty_cells_preserved(self) -> None:
        """Empty cells in a table matrix must be preserved, not dropped."""
        fixture = (FIXTURES_DIR / "tabela-celulas-vazias.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNone(conversion.pending_reason)
        self.assertIn("| Item | Obs |", conversion.markdown)
        self.assertIn("| 1 |  |", conversion.markdown)

    def test_sabotage_duplicate_paragraphs_detects_175_lig_case(self) -> None:
        """Duplicate identical paragraphs inside a cell (Resolução 175 LIG case) mark pending."""
        fixture = (FIXTURES_DIR / "tabela-175-lig-sabotada.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNotNone(conversion.pending_reason)
        self.assertIn("tabela-discrepancia-edicao", conversion.pending_reason)
        self.assertEqual(conversion.markdown, "")

    def test_sabotage_orphan_vmerge_fails_gracefully(self) -> None:
        """An orphan w:vMerge continue without restart must fail with tabela-estrutura-inconsistente."""
        fixture = (FIXTURES_DIR / "tabela-merge-sabotada.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNotNone(conversion.pending_reason)
        self.assertIn("tabela-estrutura-inconsistente", conversion.pending_reason)

    def test_corrupt_docx_returns_arquivo_corrompido(self) -> None:
        """A non-zip or corrupt docx package must be flagged as arquivo-corrompido."""
        fixture = (FIXTURES_DIR / "tabela-corrompida.docx").read_bytes()
        conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

        self.assertIsNotNone(conversion.pending_reason)
        self.assertIn("arquivo-corrompido", conversion.pending_reason)

    def test_empty_bytes_and_no_tables(self) -> None:
        """Empty bytes return arquivo-vazio; document without tables returns warning."""
        conv_empty = convert_word_tables(b"", "https://conteudo.cvm.gov.br/anexo.docx")
        self.assertEqual(conv_empty.pending_reason, "arquivo-vazio")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(
                "word/document.xml",
                b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                b'<w:body><w:p><w:r><w:t>Apenas texto</w:t></w:r></w:p></w:body>'
                b'</w:document>',
            )
        conv_no_tbl = convert_word_tables(buf.getvalue(), "https://conteudo.cvm.gov.br/anexo.docx")
        self.assertIsNone(conv_no_tbl.pending_reason)
        self.assertIn("nenhuma-tabela-encontrada", conv_no_tbl.warnings)


if __name__ == "__main__":
    unittest.main()
