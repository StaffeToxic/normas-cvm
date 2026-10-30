"""Integration tests for Word DOCX table extraction (Decision D-8 / FR-011 / C9)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cvm_archive.convert.word import (
    WordCell,
    WordTable,
    convert_word_tables,
    extract_docx_tables,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "tables"


def test_tables_fixtures_manifest_digest() -> None:
    """Every fixture in tests/fixtures/tables must match its sha256 digest in manifest.json."""
    manifest_path = FIXTURES_DIR / "manifest.json"
    assert manifest_path.exists(), "manifest.json does not exist in fixtures/tables"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for filename, meta in manifest.items():
        fixture_path = FIXTURES_DIR / filename
        assert fixture_path.exists(), f"Fixture {filename} missing"
        data = fixture_path.read_bytes()
        assert len(data) == meta["bytes"], f"Byte size mismatch for {filename}"
        digest = hashlib.sha256(data).hexdigest()
        assert digest == meta["sha256"], f"Digest mismatch for {filename}"


def test_simple_table_converts_to_markdown() -> None:
    """A regular rectangular table with a header row must render as standard Markdown."""
    fixture = (FIXTURES_DIR / "tabela-simples.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is None
    assert "| Artigo | Descricao |" in conversion.markdown
    assert "| --- | --- |" in conversion.markdown
    assert "| Art. 1º | Regulamenta o mercado. |" in conversion.markdown
    assert "| Art. 2º | Revoga normas anteriores. |" in conversion.markdown


def test_gridspan_converts_to_html_table() -> None:
    """A table with w:gridSpan (colspan) must render as an HTML table preserving span."""
    fixture = (FIXTURES_DIR / "tabela-gridspan.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is None
    assert '<table>' in conversion.markdown
    assert '<th colspan="2">Parametro Global</th>' in conversion.markdown
    assert '<td>Acoes</td><td>100%</td>' in conversion.markdown


def test_vmerge_converts_to_html_table() -> None:
    """A table with w:vMerge (rowspan) must render as an HTML table preserving span."""
    fixture = (FIXTURES_DIR / "tabela-vmerge.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is None
    assert '<table>' in conversion.markdown
    assert '<td rowspan="2">Renda Fixa</td><td>CDB</td><td>10%</td>' in conversion.markdown
    assert '<td>LCI</td><td>20%</td>' in conversion.markdown


def test_empty_cells_preserved() -> None:
    """Empty cells in a table matrix must be preserved, not dropped."""
    fixture = (FIXTURES_DIR / "tabela-celulas-vazias.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is None
    assert "| Item | Obs |" in conversion.markdown
    assert "| 1 |  |" in conversion.markdown


def test_sabotage_duplicate_paragraphs_detects_175_lig_case() -> None:
    """Duplicate identical paragraphs inside a cell (Resolução 175 LIG case) mark pending."""
    fixture = (FIXTURES_DIR / "tabela-175-lig-sabotada.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is not None
    assert "tabela-discrepancia-edicao" in conversion.pending_reason
    assert conversion.markdown == ""


def test_sabotage_orphan_vmerge_fails_gracefully() -> None:
    """An orphan w:vMerge continue without restart must fail with tabela-estrutura-inconsistente."""
    fixture = (FIXTURES_DIR / "tabela-merge-sabotada.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is not None
    assert "tabela-estrutura-inconsistente" in conversion.pending_reason


def test_corrupt_docx_returns_arquivo_corrompido() -> None:
    """A non-zip or corrupt docx package must be flagged as arquivo-corrompido."""
    fixture = (FIXTURES_DIR / "tabela-corrompida.docx").read_bytes()
    conversion = convert_word_tables(fixture, "https://conteudo.cvm.gov.br/anexo.docx")

    assert conversion.pending_reason is not None
    assert "arquivo-corrompido" in conversion.pending_reason


def test_empty_bytes_and_no_tables() -> None:
    """Empty bytes return arquivo-vazio; document without tables returns warning."""
    # Empty bytes
    conv_empty = convert_word_tables(b"", "https://conteudo.cvm.gov.br/anexo.docx")
    assert conv_empty.pending_reason == "arquivo-vazio"

    # Minimal valid docx with no tables
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body><w:p><w:r><w:t>Apenas texto</w:t></w:r></w:p></w:body>'
            b'</w:document>'
        )
    conv_no_tbl = convert_word_tables(buf.getvalue(), "https://conteudo.cvm.gov.br/anexo.docx")
    assert conv_no_tbl.pending_reason is None
    assert "nenhuma-tabela-encontrada" in conv_no_tbl.warnings
