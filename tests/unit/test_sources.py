"""Official catalogue and document pages are read without inventing facts."""

import unittest
from pathlib import Path
from types import SimpleNamespace

from cvm_archive.sources import (
    CatalogCountError,
    CatalogLoopError,
    DocumentParseError,
    UnsupportedCategoryError,
    catalog_url,
    enumerate_catalog,
    parse_catalog,
    parse_document_page,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sources"
DOCUMENT_URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _StubClient:
    def __init__(self, pages: dict[str, bytes]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def fetchArtifact(self, url: str) -> SimpleNamespace:
        self.calls.append(url)
        return SimpleNamespace(bytes=self.pages[url])


class _RealCatalogClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.pages = {
            catalog_url("resolucoes", page): (FIXTURES / f"catalog-resolucoes-p{page}.html").read_bytes()
            for page in range(1, 6)
        }

    def fetchArtifact(self, url: str) -> SimpleNamespace:
        self.calls.append(url)
        return SimpleNamespace(bytes=self.pages[url])


class CatalogUrlTests(unittest.TestCase):
    def test_url_targets_official_resolution_search(self):
        self.assertEqual(
            catalog_url("resolucoes", 3),
            "https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true"
            "&contCategoriasCheck=1&vimDaCategoria=/legislacao/resolucoes/"
            "&itensPagina=50&searchPage=3",
        )

    def test_page_must_be_positive_integer(self):
        for value in (0, -1, True, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                catalog_url("resolucoes", value)  # type: ignore[arg-type]

    def test_other_category_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(UnsupportedCategoryError, "only resolucoes"):
            catalog_url("deliberacoes", 1)


class CatalogParsingTests(unittest.TestCase):
    def test_first_page_keeps_real_candidates_and_declared_total(self):
        entries, declared = parse_catalog(_read("catalog-resolucoes-p1.html"), DOCUMENT_URL, "resolucoes")
        self.assertEqual(declared, 249)
        self.assertEqual(len(entries), 50)
        first = entries[0]
        self.assertEqual(first.title, "Resolução CVM 249")
        self.assertEqual(first.number, "249")
        self.assertEqual(first.date, "2026-10-13")
        self.assertEqual(first.url, DOCUMENT_URL)
        self.assertEqual(first.category, "resolucoes")

    def test_entry_order_is_stable_between_reads(self):
        first, _ = parse_catalog(_read("catalog-resolucoes-p2.html"), DOCUMENT_URL, "resolucoes")
        second, _ = parse_catalog(_read("catalog-resolucoes-p2.html"), DOCUMENT_URL, "resolucoes")
        self.assertEqual([entry.url for entry in first], [entry.url for entry in second])

    def test_duplicate_absolute_and_relative_links_are_one_candidate(self):
        entries, declared = parse_catalog(_read("catalog-alias.html"), DOCUMENT_URL, "resolucoes")
        self.assertEqual(declared, 1)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].url, DOCUMENT_URL)

    def test_missing_counter_is_not_invented(self):
        entries, declared = parse_catalog(
            "<section class='listaResultados'><article><h3><a href='/x.html'>Resolução CVM 1</a></h3></article></section>",
            DOCUMENT_URL,
            "resolucoes",
        )
        self.assertIsNone(declared)
        self.assertEqual(len(entries), 1)


class CatalogEnumerationTests(unittest.TestCase):
    def test_all_five_pages_are_walked_to_the_real_total(self):
        client = _RealCatalogClient()
        entries = enumerate_catalog(client, "resolucoes")
        self.assertEqual(len(client.calls), 5)
        self.assertEqual(len(entries), 249)
        self.assertEqual(len({entry.url for entry in entries}), 249)
        self.assertEqual(entries[0].number, "249")
        self.assertEqual(entries[-1].number, "1")
        self.assertTrue(all(entry.number is not None for entry in entries))
        self.assertTrue(all(entry.date is not None for entry in entries))

    def test_alias_page_does_not_force_a_second_fetch(self):
        client = _StubClient({catalog_url("resolucoes", 1): (FIXTURES / "catalog-alias.html").read_bytes()})
        entries = enumerate_catalog(client, "resolucoes")
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(client.calls), 1)

    def test_declared_count_mismatch_fails(self):
        client = _StubClient(
            {
                catalog_url("resolucoes", 1): (FIXTURES / "catalog-count-mismatch-p1.html").read_bytes(),
                catalog_url("resolucoes", 2): (FIXTURES / "catalog-empty-p2.html").read_bytes(),
            }
        )
        with self.assertRaisesRegex(CatalogCountError, "declared 3"):
            enumerate_catalog(client, "resolucoes")
        self.assertEqual(len(client.calls), 2)

    def test_counter_change_between_pages_fails(self):
        client = _StubClient(
            {
                catalog_url("resolucoes", 1): (FIXTURES / "catalog-counter-divergence-p1.html").read_bytes(),
                catalog_url("resolucoes", 2): (FIXTURES / "catalog-counter-divergence-p2.html").read_bytes(),
            }
        )
        with self.assertRaisesRegex(CatalogCountError, "changed between pages"):
            enumerate_catalog(client, "resolucoes")

    def test_repeated_pagination_fails_instead_of_looping(self):
        client = _StubClient(
            {
                catalog_url("resolucoes", 1): (FIXTURES / "catalog-loop-p1.html").read_bytes(),
                catalog_url("resolucoes", 2): (FIXTURES / "catalog-loop-p2.html").read_bytes(),
            }
        )
        with self.assertRaisesRegex(CatalogLoopError, "repeated"):
            enumerate_catalog(client, "resolucoes")

    def test_unsupported_category_never_fetches(self):
        client = _StubClient({})
        with self.assertRaises(UnsupportedCategoryError):
            enumerate_catalog(client, "deliberacoes")
        self.assertEqual(client.calls, [])


class DocumentRes249Tests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document_page(_read("document-resol249.html"), DOCUMENT_URL, "resolucoes")

    def test_identity_comes_from_the_epigraph(self):
        self.assertEqual(self.document["title"], "Resolução CVM 249")
        self.assertEqual(self.document["type"], "resolucao")
        self.assertEqual(self.document["number"], "249")
        self.assertEqual(self.document["date"], "2026-10-13")

    def test_revocation_is_unknown_without_explicit_evidence(self):
        self.assertIsNone(self.document["revoked"])
        self.assertIsNone(self.document["revocation_evidence"])
        self.assertEqual(self.document["relations"], {"altered_by": [], "revoked_by": []})

    def test_own_artifacts_are_classified_without_version_claims(self):
        artifacts = self.document["artifacts"]
        self.assertEqual([artifact["format"] for artifact in artifacts], ["html", "pdf", "docx"])
        self.assertTrue(all(artifact["version"] == "publicação original" for artifact in artifacts))
        self.assertTrue(all(artifact["url"].startswith("https://conteudo.cvm.gov.br/") for artifact in artifacts))
        self.assertEqual(artifacts[0]["label"], "[HTML]")
        self.assertTrue(artifacts[0]["url"].endswith("/resol249.htm"))

    def test_metadata_is_read_from_the_central_article(self):
        metadata = self.document["document_metadata"]
        self.assertTrue(metadata["ementa"].startswith("Institui, em caráter experimental"))
        self.assertNotIn("Você está aqui", metadata["ementa"])
        self.assertEqual(metadata["publication"], "(Publicada no DOU de 14.10.2026)")
        self.assertEqual(metadata["data_publication"], "2026-10-14")
        self.assertIsNone(metadata["edition"])


class DocumentRes175Tests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document_page(
            _read("document-resol175.html"),
            "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html",
            "resolucoes",
        )

    def test_consolidated_original_and_annexes_are_distinguished(self):
        artifacts = self.document["artifacts"]
        self.assertEqual(len(artifacts), 17)
        versions = {artifact["version"] for artifact in artifacts}
        self.assertEqual(versions, {"consolidada", "publicação original"})
        self.assertTrue(any(artifact["url"].endswith("resol175.pdf") for artifact in artifacts))
        self.assertTrue(any("Anexo01" in artifact["url"] for artifact in artifacts))
        self.assertTrue(all("resol175" in artifact["url"] for artifact in artifacts))

    def test_altering_norms_become_relations_not_artifacts(self):
        relations = self.document["relations"]
        self.assertEqual(len(relations["altered_by"]), 8)
        self.assertEqual(relations["revoked_by"], [])
        self.assertTrue(any(relation["title"] == "181/23" for relation in relations["altered_by"]))
        self.assertFalse(any("resol181" in artifact["url"] for artifact in self.document["artifacts"]))

    def test_ementa_does_not_imply_whole_act_revocation(self):
        self.assertIsNone(self.document["revoked"])
        self.assertIn("revoga as normas que especifica", self.document["document_metadata"]["ementa"])
        self.assertEqual(self.document["document_metadata"]["data_publication"], "2022-12-28")


class DocumentInst400Tests(unittest.TestCase):
    def setUp(self):
        self.document = parse_document_page(
            _read("document-inst400.html"),
            "https://conteudo.cvm.gov.br/legislacao/instrucoes/inst400.html",
            "resolucoes",
        )

    def test_revocation_has_explicit_official_evidence(self):
        self.assertTrue(self.document["revoked"])
        self.assertEqual(self.document["revocation_evidence"], "REVOGADA pela Resolução 160/22.")
        revoked_by = self.document["relations"]["revoked_by"]
        self.assertEqual(len(revoked_by), 1)
        self.assertEqual(revoked_by[0]["title"], "160/22")
        self.assertTrue(revoked_by[0]["url"].endswith("/resolucoes/resol160.html"))

    def test_only_this_acts_files_are_artifacts(self):
        artifacts = self.document["artifacts"]
        self.assertEqual(len(artifacts), 4)
        self.assertTrue(all("inst400" in artifact["url"] for artifact in artifacts))
        self.assertFalse(any("inst013" in artifact["url"] for artifact in artifacts))
        self.assertFalse(any("inst088" in artifact["url"] for artifact in artifacts))
        self.assertFalse(any("inst429" in artifact["url"] for artifact in artifacts))
        consolidated = [artifact for artifact in artifacts if artifact["version"] == "consolidada"]
        self.assertEqual(len(consolidated), 3)

    def test_altering_norms_are_relations(self):
        altered_by = self.document["relations"]["altered_by"]
        self.assertGreaterEqual(len(altered_by), 20)
        self.assertTrue(any(relation["url"].endswith("inst429.pdf") for relation in altered_by))

    def test_publication_and_ementa_stay_separate(self):
        metadata = self.document["document_metadata"]
        self.assertIn("Instrução 13/80", metadata["ementa"])
        self.assertNotIn("Publicada", metadata["ementa"])
        self.assertIn("09.01.04", metadata["publication"])
        self.assertEqual(metadata["data_publication"], "2004-01-09")


class DocumentClassificationTests(unittest.TestCase):
    def test_catalog_category_does_not_override_the_epigraph(self):
        document = parse_document_page(
            _read("document-del870.html"),
            "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0900/deli870.html",
            "resolucoes",
        )
        self.assertEqual(document["type"], "deliberacao")
        self.assertEqual(document["number"], "870")
        self.assertEqual(document["title"], "Deliberação CVM 870")
        self.assertIsNone(document["revoked"])
        self.assertEqual([artifact["format"] for artifact in document["artifacts"]], ["pdf", "doc"])
        self.assertEqual(document["document_metadata"]["data_publication"], "2021-02-03")

    def test_revoked_title_and_evidence_are_both_required_for_true(self):
        document = parse_document_page(
            _read("document-del841.html"),
            "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0800/deli841.html",
            "resolucoes",
        )
        self.assertTrue(document["revoked"])
        self.assertEqual(document["revocation_evidence"], "REVOGADA pela Resolução 69/22.")
        self.assertEqual(len(document["relations"]["revoked_by"]), 1)
        self.assertTrue(document["relations"]["revoked_by"][0]["url"].endswith("/resolucoes/resol069.html"))


class DocumentRejectionTests(unittest.TestCase):
    def test_page_without_central_article_is_rejected(self):
        with self.assertRaisesRegex(DocumentParseError, "central document article"):
            parse_document_page("<html><body><nav>Resolução CVM 249</nav></body></html>", DOCUMENT_URL, "resolucoes")

    def test_non_http_url_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_document_page(_read("document-resol249.html"), "resol249.html", "resolucoes")

    def test_unsupported_category_is_rejected(self):
        with self.assertRaises(UnsupportedCategoryError):
            parse_document_page(_read("document-resol249.html"), DOCUMENT_URL, "unknown")


if __name__ == "__main__":
    unittest.main()
