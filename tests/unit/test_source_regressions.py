"""Independent failures must stop discovery or preserve official uncertainty."""

import unittest
import hashlib
from pathlib import Path

from cvm_archive.sources import CatalogCountError, DocumentParseError, enumerate_catalog, parse_document_page


URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol001.html"


def page(body, title="Resolução CVM 1"):
    return f'<article class="contentTextoGeral"><h2>{title}</h2><section class="contentArticle">{body}</section></article>'


class SourceRegressionTests(unittest.TestCase):
    def test_fixture_bytes_match_provenance_manifest(self):
        root = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
        rows = (root / "MANIFEST.md").read_text(encoding="utf-8").splitlines()
        checked = 0
        for row in rows:
            fields = [field.strip() for field in row.split("|")]
            if len(fields) < 8 or not fields[1].endswith(".html"):
                continue
            with self.subTest(fixture=fields[1]):
                data = (root / fields[1]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), fields[5].strip("`"))
                self.assertEqual(len(data), int(fields[6]))
                checked += 1
        self.assertEqual(checked, 17)

    def test_missing_counter_cannot_certify_empty_catalog(self):
        class Client:
            def fetch(self, url):
                return b"<html>Maintenance</html>"
        with self.assertRaises(CatalogCountError):
            enumerate_catalog(Client(), "resolucoes")

    def test_publication_date_is_not_act_date(self):
        result = parse_document_page(page("<p>(Publicada no DOU de 14.10.2026)</p>"), URL, "resolucoes")
        self.assertIsNone(result["date"])
        self.assertEqual(result["document_metadata"]["data_publication"], "2026-10-14")

    def test_revocation_of_another_act_is_not_status(self):
        result = parse_document_page(page('<p>A norma anterior não foi revogada.</p>'), URL, "resolucoes")
        self.assertIsNone(result["revoked"])

    def test_negated_revocation_is_not_revocation_relation(self):
        result = parse_document_page(page('<p>NÃO REVOGADA pela <a href="resol002.html">Resolução 2</a>.</p>'), URL, "resolucoes")
        self.assertIs(result["revoked"], False)
        self.assertEqual(result["relations"]["revoked_by"], [])

    def test_conflicting_explicit_status_is_not_silently_overwritten(self):
        with self.assertRaises(DocumentParseError):
            parse_document_page(page('<p>NÃO REVOGADA.</p>', "Resolução CVM 1 (Revogada)"), URL, "resolucoes")

    def test_epigraph_must_identify_the_current_act(self):
        with self.assertRaises(DocumentParseError):
            parse_document_page(page('', "Página alterada pela Resolução CVM 1"), URL, "resolucoes")

    def test_explicit_in_force_heading_is_false_not_unknown(self):
        result = parse_document_page(page('', "Resolução CVM 1 (Em vigor)"), URL, "resolucoes")
        self.assertIs(result["revoked"], False)
        self.assertEqual(result["revocation_evidence"], "Resolução CVM 1 (Em vigor)")


if __name__ == "__main__":
    unittest.main()
