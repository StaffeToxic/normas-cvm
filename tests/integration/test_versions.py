"""Version uncertainty belongs to the artifact, not to every version of an act."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cvm_archive.sources.document import parse_document_page
from tests.integration.test_cli import command, synthetic


URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol001.html"


def metadata_page(content):
    return ('<article class="contentTextoGeral"><h2>Resolução CVM 1</h2>'
            '<section class="contentArticle"><p>Tue Oct 13 18:00:00 BRT 2026</p>' + content + '</section></article>')


class VersionTests(unittest.TestCase):
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
