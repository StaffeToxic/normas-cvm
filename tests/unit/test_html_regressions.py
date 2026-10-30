"""Reproduce independently observed losses before publication is allowed."""

from html.parser import HTMLParser
import unittest

from cvm_archive.convert.html import convert_html
from cvm_archive.normalize.text import heading_level

URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/999/resol999.htm"
OPEN = "<html><body><div><p>RESOLUÇÃO CVM Nº 999, DE 2026</p><p>Art. 1º Regra.</p>"
CLOSE = "</div></body></html>"


class Plain(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


class PreservationRegressions(unittest.TestCase):
    def test_sibling_annex_is_not_silently_left_out(self):
        html = OPEN + "</div><section><h2>ANEXO A</h2><p>Texto obrigatório.</p></section></body></html>"
        result = convert_html(html, URL)
        self.assertIsNotNone(result.pending_reason)
        self.assertEqual(result.markdown, "")

    def test_unknown_image_is_not_assumed_decorative(self):
        for alt in ["", ' alt="Fórmula"']:
            with self.subTest(alt=alt):
                result = convert_html(OPEN + '<img src="formula.png"' + alt + '>' + CLOSE, URL)
                self.assertIsNotNone(result.pending_reason)
                self.assertEqual(result.markdown, "")

    def test_unsafe_links_cannot_be_published(self):
        for href in ["javascript:alert(1)", "data:text/html,x", "file:///tmp/item"]:
            with self.subTest(href=href):
                result = convert_html(OPEN + f'<p><a href="{href}">Referência</a></p>' + CLOSE, URL)
                self.assertIsNotNone(result.pending_reason)
                self.assertEqual(result.markdown, "")

    def test_literal_angle_brackets_in_html_cells_remain_visible(self):
        result = convert_html(OPEN + '<table><tr><td>&lt;limite&gt; &amp; R$</td><td></td></tr></table>' + CLOSE, URL)
        self.assertIsNone(result.pending_reason)
        plain = Plain()
        plain.feed(result.markdown)
        self.assertIn("<limite> & R$", "".join(plain.parts))
        self.assertIn("&lt;limite&gt;", result.markdown)

    def test_markdown_cells_keep_strike_and_links(self):
        html = '<table><tr><th>Item</th><th>Valor</th></tr><tr><td><del>Revogado</del></td><td><a href="#nota">1</a></td></tr></table>'
        result = convert_html(OPEN + html + CLOSE, URL)
        self.assertIsNone(result.pending_reason)
        self.assertIn("~~Revogado~~", result.markdown)
        self.assertIn(f"[1]({URL}#nota)", result.markdown)

    def test_overlapping_spans_are_pending(self):
        html = '<table><tr><td rowspan="2">A</td><td>B</td><td rowspan="2">C</td></tr><tr><td colspan="2">D</td></tr></table>'
        result = convert_html(OPEN + html + CLOSE, URL)
        self.assertIsNotNone(result.pending_reason)
        self.assertEqual(result.markdown, "")

    def test_cell_paragraph_boundaries_are_preserved(self):
        result = convert_html(OPEN + '<table><tr><td><p>Primeira.</p><p>Segunda.</p></td></tr></table>' + CLOSE, URL)
        self.assertIsNone(result.pending_reason)
        self.assertIn("Primeira. Segunda.", result.source_text)
        self.assertIn("Primeira.<br>Segunda.", result.markdown)

    def test_unknown_table_content_is_pending(self):
        html = '<table><tr><td>A</td></tr><div><p>Nota normativa obrigatória.</p></div></table>'
        result = convert_html(OPEN + html + CLOSE, URL)
        self.assertIsNotNone(result.pending_reason)
        self.assertEqual(result.markdown, "")

    def test_unknown_table_wrapper_cannot_hide_an_image(self):
        html = '<table><tr><td>A</td></tr><div><img src="formula.png"></div></table>'
        result = convert_html(OPEN + html + CLOSE, URL)
        self.assertIsNotNone(result.pending_reason)

    def test_inline_css_strike_is_preserved(self):
        result = convert_html(OPEN + '<p><span style="text-decoration: line-through">Revogado</span></p>' + CLOSE, URL)
        self.assertIn("~~Revogado~~", result.markdown)

    def test_link_parentheses_cannot_break_markdown_destination(self):
        result = convert_html(OPEN + '<p><a href="https://a.test/item(x)">Texto</a></p>' + CLOSE, URL)
        self.assertIn("[Texto](https://a.test/item%28x%29)", result.markdown)

    def test_header_spelling_is_preserved_without_assuming_accents(self):
        self.assertEqual(heading_level("CAPITULO I"), 3)
        self.assertEqual(heading_level("SECAO I"), 4)
        result = convert_html(OPEN + '<p>CAPITULO I</p>' + CLOSE, URL)
        self.assertIn("### CAPITULO I", result.markdown)

    def test_unresolved_css_strike_is_pending(self):
        html = OPEN.replace('<body>', '<head><style>.old {text-decoration:line-through}</style></head><body>')
        result = convert_html(html + '<p class="old">Revogado</p>' + CLOSE, URL)
        self.assertIsNotNone(result.pending_reason)
        self.assertEqual(result.markdown, "")

    def test_hidden_content_cannot_be_published_as_visible(self):
        result = convert_html(OPEN + '<p hidden>Texto de outra versão.</p>' + CLOSE, URL)
        self.assertIsNotNone(result.pending_reason)
        self.assertEqual(result.markdown, "")


if __name__ == "__main__":
    unittest.main()
