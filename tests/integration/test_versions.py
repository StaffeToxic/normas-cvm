"""Version uncertainty belongs to the artifact, not to every version of an act."""

import json
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cvm_archive.sources.document import parse_document_page
from cvm_archive.gates.metadata import confirmed_id
from tests.integration.test_cli import Client, command, synthetic
from cvm_archive.cli import verify_tree
from cvm_archive.publish.coverage import coverage_files


URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol001.html"


def metadata_page(content):
    return ('<article class="contentTextoGeral"><h2>Resolução CVM 1</h2>'
            '<section class="contentArticle"><p>Tue Oct 13 18:00:00 BRT 2026</p>' + content + '</section></article>')


def alias_client(root, *, conflict=False):
    client, entries = synthetic(root)
    first = entries[0].url
    alias = first.replace("/resol001.html", "/alias/resol001.html")
    client.replies[alias] = client.replies[first]
    if conflict:
        client.replies[first] = client.replies[first].replace(b"</section>", '<p>NÃO REVOGADA.</p></section>'.encode())
        client.replies[alias] = client.replies[alias].replace(b"</section>", '<p>REVOGADA pela <a href="resol002.html">Resolução 2</a>.</p></section>'.encode())
    path = root / "catalogo/resolucoes.json"
    catalog = json.loads(path.read_bytes())
    catalog["registros"].append({**catalog["registros"][0], "url": alias})
    catalog["registros"].sort(key=lambda row: row["url"])
    catalog["total"] = catalog["contador_divulgado"] = 2
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return client, first, alias


class VersionTests(unittest.TestCase):
    def test_real_version_fixtures_match_exact_provenance(self):
        root = Path(__file__).resolve().parents[1] / "fixtures/versions"
        manifest = json.loads((root / "manifest.json").read_bytes())
        self.assertEqual(len(manifest["fixtures"]), 6)
        self.assertEqual({item["file"] for item in manifest["fixtures"]}, {path.name for path in root.glob("*.html")})
        for item in manifest["fixtures"]:
            with self.subTest(file=item["file"]):
                raw = (root / item["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["fixture_sha256"])
                self.assertEqual(len(raw), item["bytes"])
                self.assertTrue(item["source_url"].startswith("https://conteudo.cvm.gov.br/legislacao/"))

    def test_real_opinions_and_deliberation_keep_their_official_identity(self):
        root = Path(__file__).resolve().parents[1] / "fixtures"
        for number, year in ((39, "2021"), (40, "2022")):
            with self.subTest(number=number):
                file = root / f"versions/pare{number:03d}.html"
                url = f"https://conteudo.cvm.gov.br/legislacao/pareceres-orientacao/pare{number:03d}.html"
                page = parse_document_page(file.read_text(encoding="utf-8"), url, "pareceres-orientacao")
                self.assertEqual(page["type"], "parecer-de-orientacao")
                self.assertEqual(confirmed_id("Parecer de Orientação", page["number"], page["date"]), f"cvm-parecer-de-orientacao-{number}-{year}")
                self.assertFalse(any(item["format"] == "html" for item in page["artifacts"]))
        page = parse_document_page((root / "sources/document-del870.html").read_text(encoding="utf-8"),
                                   "https://conteudo.cvm.gov.br/legislacao/deliberacoes/deli0900/deli870.html", "deliberacoes")
        self.assertEqual(confirmed_id("Deliberação", page["number"], page["date"]), "cvm-deliberacao-870-2021")

    def test_real_175_exposes_both_versions_and_external_annexes(self):
        root = Path(__file__).resolve().parents[1] / "fixtures/versions"
        page = parse_document_page((root / "resol175.html").read_text(encoding="utf-8"),
                                   "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html", "resolucoes")
        self.assertEqual({item["version"] for item in page["artifacts"]}, {"publicação original", "consolidada"})
        self.assertEqual(len(page["artifacts"]), 17)
        self.assertEqual(len(page["relations"]["altered_by"]), 8)
        self.assertTrue(any("_Anexo12" in item["url"] for item in page["artifacts"]))

    def test_real_59_100_110_are_not_certified_from_auxiliary_triage(self):
        root = Path(__file__).resolve().parents[1] / "fixtures/versions"
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            client, entries = synthetic(output, count=3)
            path = output / "catalogo/resolucoes.json"
            catalog = json.loads(path.read_bytes())
            rows = []
            for number in (59, 100, 110):
                url = f"https://conteudo.cvm.gov.br/legislacao/resolucoes/resol{number:03d}.html"
                client.replies[url] = (root / f"resol{number:03d}.html").read_bytes()
                rows.append({"url": url, "title": f"Resolução CVM {number}", "category": "resolucoes", "number": str(number), "date": None})
            catalog["registros"] = rows
            path.write_text(json.dumps(catalog), encoding="utf-8")
            code, result, error = command(["collect", "--category", "resolucoes", "--output", str(output)], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual((result["publicados"], result["pendentes"]), (0, 3))
            self.assertFalse(list(output.rglob("reguladores/**/*.md")))

    def test_two_confirmed_urls_have_one_identity_and_denominator(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, first, alias = alias_client(root)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["categorias"][0]["catalogo_total"], 1)
            self.assertEqual(len(report["documentos"]), 1)
            record = report["documentos"][0]
            self.assertEqual(set((record["fonte_cvm"], *record["urls_alternativas"])), {first, alias})
            self.assertEqual(output["publicados"], 1)
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            self.assertFalse(output["changed"])

    def test_counter_consistency_cannot_hide_a_removed_catalog_entry(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _, _ = alias_client(root)
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root), "--limit", "1"], client)[0], 0)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            report["documentos"] = [row for row in report["documentos"] if row["id"] is not None]
            report["categorias"][0]["catalogo_total"] -= 1
            report["categorias"][0]["pendentes"] -= 1
            for name, data in coverage_files(report).items():
                (root / name).write_bytes(data)
            self.assertIn("catalog entry absent from coverage and aliases", verify_tree(root)["violacoes"])

    def test_two_hashes_for_the_same_source_are_preserved_as_conflict(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ordinary, _, _ = alias_client(root)
            html = next(url for url in ordinary.replies if url.endswith(".htm"))
            first_hash = hashlib.sha256(ordinary.replies[html]).hexdigest()
            second_raw = ordinary.replies[html].replace(b"Regra 1.", b"Regra nova 1.")
            second_hash = hashlib.sha256(second_raw).hexdigest()
            class ChangingClient(Client):
                def fetch(self, url):
                    result = super().fetch(url)
                    if url == html:
                        self.replies[url] = second_raw
                    return result
            client = ChangingClient(ordinary.replies)
            code, _, error = command(["collect", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["estado"], "divergente")
            self.assertNotIn(html, report["documentos"][0]["sha256_fontes"])
            self.assertIn(first_hash, report["divergencias"][0]["descricao"])
            self.assertIn(second_hash, report["divergencias"][0]["descricao"])

    def test_unvisited_candidate_is_not_merged_by_its_number_and_date(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _, _ = alias_client(root)
            code, _, error = command(["collect", "--category", "resolucoes", "--output", str(root), "--limit", "1"], client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["categorias"][0]["catalogo_total"], 2)
            self.assertEqual(sum(row["id"] is None for row in report["documentos"]), 1)

    def test_contradictory_official_pages_preserve_both_evidences(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, first, alias = alias_client(root, conflict=True)
            code, output, error = command(["collect", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["estado"], "divergente")
            self.assertEqual(set(report["divergencias"][0]["evidencias"]), {first, alias})
            self.assertIn("NÃO REVOGADA", report["divergencias"][0]["descricao"])
            human = (root / "cobertura/COBERTURA.md").read_text(encoding="utf-8")
            self.assertIn("NÃO REVOGADA", human)
            self.assertIn(first, human)
            self.assertIn(alias, human)
            self.assertFalse(list((root / "reguladores").rglob("*.md")))

    def test_known_aliases_are_reconciled_together_with_limit_one(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, first, alias = alias_client(root, conflict=True)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, client)[0], 0)
            client.replies[alias] = client.replies[first]
            code, output, error = command([*args, "--limit", "1"], client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["estado"], "publicado")
            self.assertEqual(report["divergencias"], [])
    def test_original_and_consolidated_html_are_distinct_files_and_hashes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root, consolidated=True)
            original = next(url for url in client.replies if url.endswith(".htm"))
            consolidated = original[:-4] + "consolid.htm"
            client.replies[entries[0].url] = client.replies[entries[0].url].replace(b"consolid.pdf", b"consolid.htm")
            client.replies[consolidated] = client.replies[original].replace(b"Regra 1.", b"Regra consolidada 1.")
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            record = report["documentos"][0]
            self.assertEqual(len(record["arquivos"]), 2)
            self.assertNotEqual(record["sha256_fontes"][original], record["sha256_fontes"][consolidated])
            self.assertEqual(output["publicados"], 1)
            before_original = next(path for path in record["arquivos"] if ".consolidada." not in path)
            before = (root / before_original).read_bytes()
            client.replies[consolidated] = b"<html><body>Bad source</body></html>"
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            record = json.loads((root / "cobertura/cobertura.json").read_bytes())["documentos"][0]
            self.assertEqual(record["estado"], "pendente")
            self.assertEqual(record["arquivos"], [before_original])
            self.assertEqual((root / before_original).read_bytes(), before)

    def test_conflicting_status_is_persisted_and_resolution_removes_the_conflict(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root)
            page = client.replies[entries[0].url]
            client.replies[entries[0].url] = page.replace(b"CVM 1</h2>", b"CVM 1 (Revogada)</h2>").replace(b"</section>", '<p>NÃO REVOGADA.</p></section>'.encode())
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["estado"], "divergente")
            self.assertEqual(len(report["divergencias"]), 1)
            self.assertIn("NÃO REVOGADA", report["divergencias"][0]["descricao"])
            self.assertIn("Revogada", report["divergencias"][0]["descricao"])
            client.replies[entries[0].url] = page
            self.assertEqual(command(args, client)[0], 0)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["estado"], "publicado")
            self.assertEqual(report["divergencias"], [])

    def test_partial_revocation_is_not_total_revocation(self):
        page = metadata_page('<p>PARCIALMENTE REVOGADA pela <a href="resol002.html">Resolução 2</a>.</p>')
        parsed = parse_document_page(page, URL, "resolucoes")
        self.assertIsNone(parsed["revoked"])
        self.assertEqual(len(parsed["relations"]["revoked_by"]), 1)

    def test_negated_alteration_is_not_positive_relation(self):
        page = metadata_page('<p>NÃO ALTERADA pela <a href="resol002.html">Resolução 2</a>.</p>')
        parsed = parse_document_page(page, URL, "resolucoes")
        self.assertEqual(parsed["relations"]["altered_by"], [])

    def test_each_relation_uses_the_notice_before_its_anchor(self):
        page = metadata_page('<p>ALTERADA pela <a href="resol002.html">Resolução 2</a> e REVOGADA pela <a href="resol003.html">Resolução 3</a>.</p>')
        parsed = parse_document_page(page, URL, "resolucoes")
        self.assertEqual([row["title"] for row in parsed["relations"]["altered_by"]], ["Resolução 2"])
        self.assertEqual([row["title"] for row in parsed["relations"]["revoked_by"]], ["Resolução 3"])

    def test_site_filename_does_not_mean_consolidated(self):
        parsed = parse_document_page(metadata_page('<p><a href="resol001site.pdf">Resolução CVM 1</a></p>'), URL, "resolucoes")
        self.assertEqual(parsed["artifacts"][0]["version"], "publicação original")

    def test_republication_is_not_forced_into_a_public_version_enum(self):
        parsed = parse_document_page(metadata_page('<p><a href="resol001_repub.pdf">Republicado em parte</a></p>'), URL, "resolucoes")
        self.assertIsNone(parsed["artifacts"][0]["version"])
        self.assertEqual(parsed["artifacts"][0]["pending_reason"], "republicacao-parcial")

    def test_clean_copy_label_alone_does_not_prove_consolidation(self):
        parsed = parse_document_page(metadata_page('<p><a href="resol001semmarcas.pdf">Texto sem marcas</a></p>'), URL, "resolucoes")
        self.assertIsNone(parsed["artifacts"][0]["version"])

    def test_original_label_conflicting_with_consolidated_name_is_pending(self):
        parsed = parse_document_page(metadata_page('<p><a href="resol001consolid.pdf">Publicação original</a></p>'), URL, "resolucoes")
        self.assertIsNone(parsed["artifacts"][0]["version"])
        self.assertEqual(parsed["artifacts"][0]["pending_reason"], "versao-ambigua")

    def test_pending_republication_does_not_remove_approved_original(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root)
            original = client.replies[entries[0].url].decode()
            client.replies[entries[0].url] = original.replace('</section>', '<p><a href="resol001_repub.pdf">Republicado em parte</a></p></section>').encode()
            code, output, error = command(["collect", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            record = json.loads((root / "cobertura/cobertura.json").read_bytes())["documentos"][0]
            self.assertEqual(record["estado"], "pendente")
            self.assertEqual(len(record["arquivos"]), 1)
            self.assertIn("republicacao-parcial", record["motivo"])
            self.assertIn("resol001_repub.pdf", record["motivo"])


if __name__ == "__main__":
    unittest.main()
