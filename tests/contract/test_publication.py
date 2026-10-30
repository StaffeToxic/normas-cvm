"""Prove that corrupted candidates cannot pass the publication boundary."""

import copy
import hashlib
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cvm_archive.convert.html import convert_html
from cvm_archive.gates.fidelity import check_fidelity, check_html_structure
from cvm_archive.gates.metadata import validate_metadata
from cvm_archive.models import Artifact, CatalogEntry, Conversion
from cvm_archive.publish.coverage import build_coverage, coverage_files, pending_entry, validate_coverage
from cvm_archive.publish.markdown import PublicationError, document_path, parse_document, render_document
from cvm_archive.publish.transaction import promote


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
URL = "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm"
PAGE = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
STAMP = "2026-10-29T12:00:00Z"


def metadata(artifact):
    return {
        "schema_versao": "1.0", "id": "cvm-resolucao-249-2026", "classe": "norma",
        "tipo": "Resolução", "titulo": "Resolução CVM 249", "orgao": "Comissão de Valores Mobiliários",
        "unidade": None, "numero": "249", "data": "2026-10-13", "revogada": None,
        "revogada_por": [], "alterada_por": [], "versao_texto": "publicação original",
        "publicacao": "(Publicada no DOU de 14.10.2026)", "data_publicacao": "2026-10-14",
        "edicao": None, "ementa": None, "fonte": URL, "fonte_cvm": PAGE,
        "sha256_fonte": artifact.sha256, "formato_fonte": "html", "ocr": False,
        "baixado_em": STAMP[:10], "anexos": [
            {"rotulo": "ANEXO A", "url": artifact.url, "sha256": artifact.sha256, "formato": "html"}
        ],
    }


class FidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (FIXTURES / "resol249.htm").read_text(encoding="utf-8")
        cls.result = convert_html(cls.html, URL)

    def test_real_resolution_has_exact_ordered_text_and_devices(self):
        self.assertEqual(check_fidelity(self.result.source_text, self.result.markdown), ())
        self.assertEqual(check_html_structure(self.html, self.result.markdown, URL), ())

    def test_real_resolution_rejects_deletion(self):
        changed = self.result.markdown.replace("Fica instituído", "", 1)
        self.assertIn("token-sequence", check_fidelity(self.result.source_text, changed))

    def test_real_resolution_rejects_permutation(self):
        blocks = self.result.markdown.split("\n\n")
        blocks[0], blocks[1] = blocks[1], blocks[0]
        self.assertIn("token-sequence", check_fidelity(self.result.source_text, "\n\n".join(blocks)))

    def test_real_resolution_rejects_duplication(self):
        changed = self.result.markdown + "\n\nArt. 26. Esta Resolução entra em vigor."
        errors = check_fidelity(self.result.source_text, changed)
        self.assertIn("token-sequence", errors)
        self.assertIn("legal-devices", errors)

    def test_device_formatting_is_part_of_publication(self):
        changed = self.result.markdown.replace("**Art. 1º**", "Art. 1º", 1)
        self.assertIn("device-format", check_fidelity(self.result.source_text, changed))

    def test_real_unique_paragraph_colon_keeps_its_punctuation(self):
        self.assertIn("**Parágrafo único:** A gestora de rede", self.result.markdown)

    def test_independent_reader_does_not_ignore_unknown_image(self):
        html = '<p>Art. 1º Regra.</p><img src="formula.png">'
        self.assertIn("unverified-image", check_html_structure(html, "**Art. 1º** Regra.", URL))

    def test_independent_source_catches_truncated_reference(self):
        changed = self.result.markdown.split("## ANEXO A")[0].rstrip()
        # A compromised reference can agree with a compromised candidate.
        reference = self.result.source_text.split("ANEXO A\n\nMODELO")[0].rstrip()
        self.assertEqual(check_fidelity(reference, changed), ())
        self.assertIn("token-sequence", check_html_structure(self.html, changed, URL))

    def test_table_geometry_and_text_are_preserved(self):
        html = (FIXTURES / "estrutura-completa.html").read_text(encoding="utf-8")
        result = convert_html(html, URL)
        self.assertEqual(check_html_structure(html, result.markdown, URL), ())
        corrupted = result.markdown.replace('colspan="2"', 'colspan="1"', 1)
        self.assertIn("table-structure", check_html_structure(html, corrupted, URL))

    def test_plaintext_table_cannot_replace_a_table(self):
        self.assertIn("flattened-table", check_fidelity("A | B\n1 | 2", "A | B\n1 | 2"))

    def test_matching_invalid_geometry_is_still_rejected(self):
        table = '<table><tr><td rowspan="2">A</td><td>B</td><td rowspan="2">C</td></tr><tr><td colspan="2">D</td></tr></table>'
        self.assertIn("table-shape", check_html_structure(table, table, URL))

    def test_missing_heading_format_is_rejected(self):
        self.assertIn("heading-format", check_fidelity("ANEXO A", "ANEXO A"))

    def test_link_and_strike_loss_are_rejected(self):
        html = '<html><body><div><h1>RESOLUÇÃO CVM 1</h1><p>Art. 1º <del>Antigo</del> <a href="resol002.html">novo</a>.</p></div></body></html>'
        result = convert_html(html, URL)
        self.assertEqual(check_html_structure(html, result.markdown, URL), ())
        for before, after, error in (("~~Antigo~~", "Antigo", "strike-text"), ("resol002.html", "resol003.html", "legal-links")):
            with self.subTest(error=error):
                self.assertIn(error, check_html_structure(html, result.markdown.replace(before, after), URL))

    def test_decimal_sign_and_accent_changes_are_rejected(self):
        for changed in ("Art. 1º R$ 1,50", "Art. 1º R$ -1.50", "Art. 1º R$ 1.50 acoes"):
            with self.subTest(changed=changed):
                self.assertTrue(check_fidelity("Art. 1º R$ 1.50 ações", changed))


class MetadataAndDocumentTests(unittest.TestCase):
    def setUp(self):
        self.raw = (FIXTURES / "resol249.htm").read_bytes()
        self.artifact = Artifact.from_bytes(URL, self.raw, "text/html", fetched_at=STAMP)
        self.metadata = metadata(self.artifact)
        self.html = self.raw.decode("utf-8")
        self.conversion = convert_html(self.html, URL)

    def render(self, **kwargs):
        return render_document(self.metadata, self.artifact, self.conversion, discovered_annex_urls=(self.artifact.url,), source_html=self.html, **kwargs)

    def test_real_document_round_trip_uses_exact_artifact_digest(self):
        self.assertEqual(validate_metadata(self.metadata, self.artifact), ())
        data = self.render()
        fields, body = parse_document(data)
        self.assertEqual(fields, self.metadata)
        self.assertEqual(body, self.conversion.markdown + "\n")
        self.assertEqual(fields["sha256_fonte"], hashlib.sha256(self.raw).hexdigest())
        self.assertNotIn(b"\r", data)
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(data, (FIXTURES.parent / "expected" / "resol249.md").read_bytes())

    def test_hash_of_markdown_cannot_masquerade_as_source_hash(self):
        self.metadata["sha256_fonte"] = hashlib.sha256(self.conversion.markdown.encode()).hexdigest()
        self.assertIn("artifact-hash", validate_metadata(self.metadata, self.artifact))
        with self.assertRaises(PublicationError):
            self.render()

    def test_incorrect_source_url_or_download_date_is_rejected(self):
        for key, value, error in (("fonte", PAGE, "artifact-url"), ("baixado_em", "2026-10-28", "artifact-date")):
            with self.subTest(key=key):
                fields = {**self.metadata, key: value}
                self.assertIn(error, validate_metadata(fields, self.artifact))

    def test_false_revocation_requires_explicit_evidence(self):
        self.metadata["revogada"] = False
        self.assertIn("revocation-evidence", validate_metadata(self.metadata, self.artifact))
        self.assertEqual(validate_metadata(self.metadata, self.artifact, revocation_evidence="NÃO REVOGADA."), ())

    def test_schema_fields_and_identity_are_checked(self):
        for field, value in (("schema_versao", "9.0"), ("id", "cvm-resolucao-1-2026"), ("data", "2026-02-30"), ("ocr", "false"), ("revogada", 0), ("anexos", None)):
            with self.subTest(field=field):
                self.assertTrue(validate_metadata({**self.metadata, field: value}, self.artifact))
        missing = dict(self.metadata)
        del missing["unidade"]
        self.assertTrue(validate_metadata(missing))
        self.assertTrue(validate_metadata({**self.metadata, "fontes": []}))

    def test_invalid_field_types_return_errors_without_crashing(self):
        for field in self.metadata:
            for value in ([], {}, 42):
                with self.subTest(field=field, value=value):
                    # Empty lists are valid for relation and attachment collections.
                    errors = validate_metadata({**self.metadata, field: value}, self.artifact)
                    if value != [] or field not in ("revogada_por", "alterada_por", "anexos"):
                        self.assertTrue(errors)

    def test_annex_absence_is_not_claimed_when_discovery_is_unknown(self):
        for expected in (None, (), ("https://conteudo.cvm.gov.br/anexo.pdf",)):
            with self.subTest(expected=expected), self.assertRaises(PublicationError):
                render_document(self.metadata, self.artifact, self.conversion, discovered_annex_urls=expected, source_html=self.html)

    def test_independent_source_is_derived_from_exact_artifact(self):
        data = render_document(self.metadata, self.artifact, self.conversion, discovered_annex_urls=(self.artifact.url,))
        self.assertEqual(data, self.render())
        with self.assertRaises(PublicationError):
            render_document(self.metadata, self.artifact, self.conversion, discovered_annex_urls=(), source_html="<p>truncated</p>")

    def test_artifact_identity_cannot_be_relabelled(self):
        self.metadata["numero"] = "250"
        self.metadata["id"] = "cvm-resolucao-250-2026"
        with self.assertRaisesRegex(PublicationError, "artifact-identity"):
            self.render()

    def test_artifact_date_cannot_be_relabelled(self):
        self.metadata["data"] = "2026-10-14"
        with self.assertRaisesRegex(PublicationError, "artifact-act-date"):
            self.render()

    def test_pending_conversion_cannot_publish(self):
        broken = Conversion(self.conversion.source_text, self.conversion.markdown, (), "revisao-manual")
        with self.assertRaises(PublicationError):
            render_document(self.metadata, self.artifact, broken, discovered_annex_urls=(), source_html=self.html)

    def test_paths_distinguish_versions_and_use_official_date_slug(self):
        self.assertEqual(document_path(self.metadata), "reguladores/cvm/resolucoes/2026/cvm-resolucao-249-2026.md")
        self.metadata["versao_texto"] = "consolidada"
        self.assertTrue(document_path(self.metadata).endswith(".consolidada.md"))
        self.metadata["titulo"] = "RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026"
        self.assertTrue(document_path(self.metadata).endswith("resolucao-cvm-n-249-de-13-de-outubro-de-2026.consolidada.md"))

    def test_malformed_or_duplicate_header_is_rejected(self):
        data = self.render()
        for broken in (b"\xef\xbb\xbf" + data, data.replace(b"\n", b"\r\n"), data.replace(b'schema_versao: "1.0"', b'schema_versao: "1.0"\nschema_versao: "1.0"'), b"---\ninvalid\n---\n# Title\n\nBody\n"):
            with self.subTest(prefix=broken[:12]), self.assertRaises(PublicationError):
                parse_document(broken)

    def test_embedded_annex_cannot_disappear_from_metadata(self):
        self.metadata["anexos"] = []
        with self.assertRaisesRegex(PublicationError, "embedded-annex"):
            render_document(self.metadata, self.artifact, self.conversion, discovered_annex_urls=())

    def test_embedded_annex_digest_must_match_exact_source(self):
        self.metadata["anexos"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(PublicationError, "annex-artifact"):
            self.render()


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.pending = pending_entry(CatalogEntry(PAGE, "Resolução CVM 249", "resolucoes", "249", "2026-10-13"))
        self.collection = {"modo": "completa", "requisicoes": 3, "falhas_http": 0}

    def report(self, records=None, **kwargs):
        records = [self.pending] if records is None else records
        return build_coverage(records, len(records), STAMP, self.collection, **kwargs)

    def test_candidate_remains_without_legal_identity_in_full_denominator(self):
        report = self.report()
        self.assertIsNone(report["documentos"][0]["id"])
        self.assertEqual(report["categorias"][0]["catalogo_total"], 1)
        self.assertEqual(report["categorias"][0]["pendentes"], 1)
        self.assertEqual(validate_coverage(report), ())

    def test_missing_or_duplicate_record_cannot_close_coverage(self):
        with self.assertRaises(PublicationError):
            build_coverage([self.pending], 2, STAMP, self.collection)
        with self.assertRaises(PublicationError):
            self.report([self.pending, self.pending])

    def test_original_approved_consolidated_pending_counts_once(self):
        record = {**self.pending, "id": "cvm-resolucao-249-2026", "motivo": "consolidada: tabela-nao-reproduzida", "verificado_em": STAMP[:10],
                  "arquivos": ["reguladores/cvm/resolucoes/2026/cvm-resolucao-249-2026.md"], "sha256_fontes": {URL: "a" * 64}}
        report = self.report([record])
        self.assertEqual(report["categorias"][0]["pendentes"], 1)
        self.assertEqual(report["categorias"][0]["publicados"], 0)
        self.assertEqual(report["documentos"][0]["arquivos"], record["arquivos"])

    def test_out_of_scope_is_counted_with_reason(self):
        record = {**self.pending, "estado": "fora-de-escopo", "motivo": "ato-administrativo-confirmado"}
        self.assertEqual(self.report([record])["categorias"][0]["fora_de_escopo"], 1)

    def test_unconfirmed_identity_cannot_have_published_files(self):
        report = self.report()
        report["documentos"][0]["arquivos"] = ["reguladores/cvm/resolucoes/2026/unconfirmed.md"]
        self.assertIn("unconfirmed-publication", validate_coverage(report))

    def test_pending_file_requires_missing_version_reason_and_safe_path(self):
        report = self.report()
        record = report["documentos"][0]
        record.update(id="cvm-resolucao-249-2026", arquivos=["reguladores/cvm/../../outside.md"])
        self.assertIn("record-path", validate_coverage(report))
        self.assertIn("missing-version-reason", validate_coverage(report))

    def test_counter_and_hash_corruption_are_rejected(self):
        report = self.report()
        report["categorias"][0]["pendentes"] = 0
        report["documentos"][0]["sha256_fontes"] = {URL: "not-a-hash"}
        self.assertIn("category-counts", validate_coverage(report))
        self.assertIn("record-hashes", validate_coverage(report))

    def test_only_run_dates_or_metrics_change_nothing_public(self):
        first = self.report()
        record = {**self.pending, "verificado_em": "2026-10-30"}
        second = build_coverage([record], 1, "2026-10-30T18:00:00Z", {**self.collection, "requisicoes": 11}, existing=first)
        self.assertEqual(coverage_files(first), coverage_files(second))
        self.assertEqual(second["coleta"]["requisicoes"], 3)

    def test_source_hash_change_is_a_real_metadata_change(self):
        first = self.report()
        record = {**self.pending, "sha256_fontes": {URL: "a" * 64}, "verificado_em": "2026-10-30"}
        second = build_coverage([record], 1, "2026-10-30T18:00:00Z", self.collection, existing=first)
        self.assertNotEqual(coverage_files(first), coverage_files(second))

    def test_reports_are_deterministic_and_machine_readable(self):
        files = coverage_files(self.report())
        self.assertEqual(json.loads(files["cobertura/cobertura.json"])["schema_versao"], "2.0")
        self.assertIn("não confirmado".encode(), files["cobertura/COBERTURA.md"])
        self.assertEqual(files, coverage_files(self.report()))


class TransactionTests(unittest.TestCase):
    def test_no_change_preserves_bytes_and_modification_time(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            updates = {"cobertura/cobertura.json": b"old\n"}
            self.assertTrue(promote(root, updates))
            path = root / "cobertura/cobertura.json"
            stamp = path.stat().st_mtime_ns
            self.assertFalse(promote(root, updates))
            self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_second_replace_failure_rolls_back_first_and_keeps_old_report(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = {"reguladores/cvm/resolucoes/2026/a.md": b"old\n", "cobertura/cobertura.json": b"old report\n"}
            promote(root, old)
            real_replace = os.replace
            calls = []
            def failing_replace(source, target):
                calls.append((source, target))
                if len(calls) == 2:
                    raise OSError("simulated disk failure")
                return real_replace(source, target)
            with patch("cvm_archive.publish.transaction.os.replace", side_effect=failing_replace), self.assertRaises(OSError):
                promote(root, {key: b"changed\n" for key in old})
            self.assertEqual({key: (root / key).read_bytes() for key in old}, old)
            self.assertFalse(list(root.glob(".cvm-transaction-*")))

    def test_delete_is_rolled_back_when_later_write_fails(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            name = "reguladores/cvm/resolucoes/2026/a.md"
            promote(root, {name: b"approved\n"})
            real_replace = os.replace
            def failing_replace(source, target):
                if str(source).endswith(".new"):
                    raise OSError("simulated disk failure")
                return real_replace(source, target)
            with patch("cvm_archive.publish.transaction.os.replace", side_effect=failing_replace), self.assertRaises(OSError):
                promote(root, {name: None, "cobertura/cobertura.json": b"new\n"})
            self.assertEqual((root / name).read_bytes(), b"approved\n")

    def test_path_traversal_and_uncontrolled_paths_are_rejected(self):
        with TemporaryDirectory() as temporary:
            for name in ("../outside", "/absolute", "README.md", "reguladores/../../outside", "cobertura/C:evil", "cobertura\\evil"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    promote(Path(temporary), {name: b"bad"})


if __name__ == "__main__":
    unittest.main()
