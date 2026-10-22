"""Structural conversion of the official HTML keeps the whole normative body.

The golden expectations come from the official Resolution 249 and were written
by hand from the document itself, not from the output of this converter.  The
counts reproduce the measurement made in the research stage (26 articles, 15
paragraphs and 99 items at the beginning of the line), so two extractors that
were truncated in the same way cannot satisfy the test.
"""

import hashlib
import json
import pathlib
import re
import unittest

from cvm_archive.convert.html import convert_html
from cvm_archive.normalize.text import (
    BlockKind,
    classify_block,
    heading_level,
    join_hyphenated_lines,
    normalize_paragraph,
)

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures" / "html"
RESOLUTION_249_URL = (
    "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm"
)
RESOLUTION_249_PAGE_URL = (
    "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
)
ITEM_MARKER = re.compile(r"(?m)^(?:X{0,3}(?:IX|IV|V?I{0,3}))\s*[–-]\s")


def read_fixture(name: str) -> str:
    """Read a fixture as text, without touching its line endings."""

    return (FIXTURES / name).read_bytes().decode("utf-8")


class ManifestTests(unittest.TestCase):
    """The fixtures carry their own provenance and no local path."""

    def setUp(self):
        self.raw = (FIXTURES / "manifest.json").read_text(encoding="utf-8")
        self.manifest = json.loads(self.raw)
        self.entries = {
            entry["arquivo"]: entry for entry in self.manifest["fixtures"]
        }

    def test_every_fixture_is_listed_with_its_digest(self):
        present = {
            path.name for path in FIXTURES.glob("*") if path.name != "manifest.json"
        }
        self.assertEqual(set(self.entries), present)
        for name, entry in self.entries.items():
            digest = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
            self.assertEqual(digest, entry["sha256"], name)

    def test_official_fixtures_keep_their_provenance(self):
        for name in ("resol249.htm", "pagina-cvm-resol249.html"):
            entry = self.entries[name]
            self.assertEqual(entry["origem"], "cvm-oficial")
            self.assertTrue(entry["url"].startswith("https://conteudo.cvm.gov.br/"))
            self.assertEqual(len(entry["sha256_origem"]), 64)

    def test_manifest_registers_no_local_path(self):
        for marker in ("C:\\", "C:/", "file://", ".scratch", "Documents", "Users"):
            self.assertNotIn(marker, self.raw)


class Resolution249GoldenTests(unittest.TestCase):
    """The golden test compares against the real text of the Resolution 249."""

    @classmethod
    def setUpClass(cls):
        cls.conversion = convert_html(read_fixture("resol249.htm"), RESOLUTION_249_URL)

    def test_conversion_is_publishable(self):
        self.assertIsNone(self.conversion.pending_reason)
        self.assertTrue(self.conversion.markdown)

    def test_reference_keeps_the_real_excerpt(self):
        source = self.conversion.source_text
        self.assertTrue(
            source.startswith("RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026")
        )
        self.assertIn(
            "Institui, em caráter experimental, o Programa Piloto DLT CVM destinado "
            "à realização de testes no mercado de valores mobiliários",
            source,
        )
        self.assertIn(
            "Art. 1º Fica instituído o Programa Piloto DLT CVM, programa de testes "
            "destinado à realização de operações experimentais",
            source,
        )

    def test_reference_reaches_the_end_of_the_act_and_of_the_annex(self):
        source = self.conversion.source_text
        self.assertIn(
            "Art. 26. Esta Resolução entra em vigor na data de sua publicação.",
            source,
        )
        self.assertIn("ANEXO A", source)
        self.assertIn("MODELO DE TERMO DE ADESÃO AO PROGRAMA PILOTO DLT CVM", source)
        self.assertTrue(source.rstrip().endswith("[Representantes legais do Participante]"))

    def test_device_counts_match_the_research_measurement(self):
        markdown = self.conversion.markdown
        self.assertEqual(len(re.findall(r"(?m)^\*\*Art\. ", markdown)), 26)
        self.assertEqual(len(re.findall(r"(?m)^\*\*§ ", markdown)), 15)
        self.assertEqual(len(ITEM_MARKER.findall(markdown)), 99)
        self.assertEqual(len(re.findall(r"(?m)^## ANEXO", markdown)), 1)

    def test_markdown_marks_devices_and_headings(self):
        markdown = self.conversion.markdown
        self.assertIn("**Art. 1º** Fica instituído", markdown)
        self.assertIn("**Art. 10.** Os participantes", markdown)
        self.assertIn("**§ 1º** As operações experimentais", markdown)
        self.assertIn("**Parágrafo único.** A observância dos princípios", markdown)
        self.assertIn(
            "### CAPÍTULO I – ÂMBITO, FINALIDADE E CARÁTER EXPERIMENTAL", markdown
        )
        self.assertIn("## ANEXO A", markdown)

    def test_inciso_keeps_its_own_paragraph(self):
        markdown = self.conversion.markdown
        self.assertIn("\n\nI – têm natureza experimental,", markdown)
        self.assertIn("\n\nV – não tornam irregulares outras iniciativas", markdown)

    def test_entities_and_lexical_hyphen_are_preserved(self):
        markdown = self.conversion.markdown
        self.assertIn('("Participante")', markdown)
        self.assertIn("off-chain", markdown)

    def test_numbered_item_of_the_annex_keeps_its_number(self):
        markdown = self.conversion.markdown
        self.assertIn("1\\. conhece e adere integralmente à Resolução CVM nº [•]", markdown)
        self.assertNotIn("\n1. conhece", markdown)

    def test_decorative_image_is_reported_instead_of_being_dropped_silently(self):
        warnings = " ".join(self.conversion.warnings)
        self.assertIn("imagem-decorativa-descartada", warnings)
        self.assertIn("Logotipo", warnings)


class NavigationPageTests(unittest.TestCase):
    """The official page of the act is not published as a normative body."""

    def setUp(self):
        self.conversion = convert_html(
            read_fixture("pagina-cvm-resol249.html"), RESOLUTION_249_PAGE_URL
        )

    def test_navigation_page_stays_pending(self):
        self.assertIsNotNone(self.conversion.pending_reason)
        self.assertEqual(self.conversion.markdown, "")

    def test_navigation_is_removed_and_reported(self):
        warnings = " ".join(self.conversion.warnings)
        self.assertIn("nav", warnings)
        self.assertIn("script", warnings)


class StructuralFixtureTests(unittest.TestCase):
    """Tables, links, emphasis and struck text survive the conversion."""

    def setUp(self):
        self.conversion = convert_html(
            read_fixture("estrutura-completa.html"),
            "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/999/resol999.htm",
        )

    def test_table_with_merges_keeps_the_grid(self):
        markdown = self.conversion.markdown
        self.assertIn("<table>", markdown)
        self.assertIn('<td colspan="2">celula mesclada em duas colunas</td>', markdown)
        self.assertIn('<td rowspan="2">celula mesclada em duas linhas</td>', markdown)
        self.assertIn("<td></td>", markdown)
        self.assertIn("</table>", markdown)

    def test_table_is_not_flattened_in_running_text(self):
        source = self.conversion.source_text
        self.assertIn("linha 1 coluna 1 | celula mesclada em duas colunas", source)
        self.assertIn("celula mesclada em duas linhas |  | valor da coluna 3", source)

    def test_simple_table_is_published_as_a_markdown_table(self):
        markdown = self.conversion.markdown
        self.assertIn("| Item | Valor |", markdown)
        self.assertIn("| primeiro | 1 |", markdown)

    def test_legal_link_is_preserved(self):
        self.assertIn(
            "[ANEXO A](https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/999"
            "/anexos/termo.html)",
            self.conversion.markdown,
        )

    def test_emphasis_and_strike_are_preserved(self):
        markdown = self.conversion.markdown
        self.assertIn("**negrito**", markdown)
        self.assertIn("*italico*", markdown)
        self.assertIn("~~trecho tachado~~", markdown)

    def test_inciso_and_alinea_keep_their_own_paragraph(self):
        markdown = self.conversion.markdown
        self.assertIn("\n\nI – o primeiro inciso,", markdown)
        self.assertIn("\n\na) a alinea do inciso,", markdown)


class UnsupportedStructureTests(unittest.TestCase):
    """Structure that cannot be reproduced becomes an explicit pending item."""

    def test_table_with_a_divergent_grid_is_pending(self):
        conversion = convert_html(
            read_fixture("estrutura-tabela-inconsistente.html"),
            "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/998/resol998.htm",
        )
        self.assertIsNotNone(conversion.pending_reason)
        self.assertTrue(
            conversion.pending_reason.startswith("tabela-estrutura-inconsistente")
        )
        self.assertEqual(conversion.markdown, "")

    def test_image_with_textual_content_is_pending(self):
        conversion = convert_html(
            read_fixture("estrutura-imagem-texto.html"),
            "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/997/resol997.htm",
        )
        self.assertIsNotNone(conversion.pending_reason)
        self.assertTrue(
            conversion.pending_reason.startswith("imagem-com-conteudo-textual")
        )
        self.assertEqual(conversion.markdown, "")


class SelectionTests(unittest.TestCase):
    """The normative body is selected, and doubt is reported instead of cut."""

    URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/900/resol900.htm"

    def test_body_without_articles_is_pending(self):
        conversion = convert_html(
            "<html><body><p>RESOLUÇÃO CVM Nº 1, DE 2026</p></body></html>", self.URL
        )
        self.assertEqual(conversion.pending_reason, "corpo-normativo-nao-encontrado")
        self.assertEqual(conversion.markdown, "")

    def test_body_without_epigraph_is_pending(self):
        conversion = convert_html(
            "<html><body><p>Art. 1º Fica instituido o programa.</p></body></html>",
            self.URL,
        )
        self.assertEqual(conversion.pending_reason, "epigrafe-nao-encontrada")
        self.assertEqual(conversion.markdown, "")

    def test_two_acts_in_one_body_are_pending(self):
        html = (
            "<html><body><div><p>RESOLUÇÃO CVM Nº 1, DE 2026</p>"
            "<p>Art. 1º Primeiro.</p></div><div><p>RESOLUÇÃO CVM Nº 2, DE 2026</p>"
            "<p>Art. 2º Segundo.</p></div></body></html>"
        )
        conversion = convert_html(html, self.URL)
        self.assertEqual(
            conversion.pending_reason, "selecao-ambigua-corpo-normativo"
        )
        self.assertEqual(conversion.markdown, "")

    def test_articles_in_sibling_blocks_are_not_lost(self):
        html = (
            "<html><body><div><p>RESOLUÇÃO CVM Nº 1, DE 2026</p>"
            "<p>Art. 1º Primeiro.</p></div><div><p>Art. 2º Segundo.</p></div></body></html>"
        )
        conversion = convert_html(html, self.URL)
        self.assertIsNone(conversion.pending_reason)
        self.assertIn("Art. 1º Primeiro.", conversion.source_text)
        self.assertIn("Art. 2º Segundo.", conversion.source_text)

    def test_embedded_content_is_pending(self):
        html = (
            "<html><body><div><p>RESOLUÇÃO CVM Nº 1, DE 2026</p>"
            "<p>Art. 1º Primeiro.</p><iframe src='anexo.html'></iframe></div></body></html>"
        )
        conversion = convert_html(html, self.URL)
        self.assertTrue(
            conversion.pending_reason.startswith("conteudo-embutido-nao-suportado")
        )
        self.assertEqual(conversion.markdown, "")

    def test_nested_table_is_pending(self):
        html = (
            "<html><body><div><p>RESOLUÇÃO CVM Nº 1, DE 2026</p>"
            "<p>Art. 1º Primeiro.</p><table><tr><td><table><tr><td>x</td></tr>"
            "</table></td></tr></table></div></body></html>"
        )
        conversion = convert_html(html, self.URL)
        self.assertTrue(
            conversion.pending_reason.startswith("tabela-estrutura-nao-suportada")
        )
        self.assertEqual(conversion.markdown, "")


class NormalizerTests(unittest.TestCase):
    """The normalizer formats the legal text without rewriting it."""

    def test_device_markers_are_bolded(self):
        self.assertEqual(
            normalize_paragraph("Art. 1º Fica instituído"), "**Art. 1º** Fica instituído"
        )
        self.assertEqual(
            normalize_paragraph("Art. 10. Os participantes"),
            "**Art. 10.** Os participantes",
        )
        self.assertEqual(
            normalize_paragraph("§ 2º Compete ao Comitê"), "**§ 2º** Compete ao Comitê"
        )
        self.assertEqual(
            normalize_paragraph("Parágrafo único. A critério"),
            "**Parágrafo único.** A critério",
        )

    def test_heading_levels_follow_the_front_matter_contract(self):
        self.assertEqual(heading_level("TÍTULO I – DISPOSIÇÕES"), 2)
        self.assertEqual(heading_level("CAPÍTULO I – DISPOSIÇÕES"), 3)
        self.assertEqual(heading_level("SEÇÃO 1 – DISPOSIÇÕES"), 4)
        self.assertEqual(heading_level("SUBSEÇÃO I – DISPOSIÇÕES"), 5)
        self.assertEqual(heading_level("ANEXO A"), 2)
        self.assertIsNone(heading_level("Art. 1º Fica instituído"))

    def test_inciso_and_alinea_are_recognized(self):
        self.assertIs(classify_block("I – o primeiro inciso"), BlockKind.ITEM)
        self.assertIs(classify_block("a) a alínea"), BlockKind.SUBITEM)
        self.assertIs(classify_block("Art. 1º Fica instituído"), BlockKind.ARTICLE)
        self.assertIs(classify_block("Parágrafo único. A critério"), BlockKind.UNIQUE_PARAGRAPH)

    def test_numbered_item_keeps_its_number(self):
        self.assertEqual(normalize_paragraph("1. conhece e adere"), "1\\. conhece e adere")
        self.assertEqual(normalize_paragraph("Art. 1º Fica"), "**Art. 1º** Fica")

    def test_url_is_not_broken_by_the_hyphen_join(self):
        text = "https://conteudo.cvm.gov.br/legislacao/resoluc-\noes/resol249.htm"
        self.assertEqual(
            join_hyphenated_lines(text),
            "https://conteudo.cvm.gov.br/legislacao/resoluc-\noes/resol249.htm",
        )

    def test_lexical_hyphen_is_kept(self):
        self.assertEqual(
            join_hyphenated_lines("atividades off-\nchain"), "atividades off-\nchain"
        )

    def test_soft_hyphen_is_joined(self):
        self.assertEqual(join_hyphenated_lines("distri-\nbuida"), "distribuida")
        self.assertEqual(join_hyphenated_lines("Art. 12-\n3456"), "Art. 12-\n3456")


if __name__ == "__main__":
    unittest.main()
