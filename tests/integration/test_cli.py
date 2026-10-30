"""Exercise the full MVP command boundary, including failure preservation."""

import io
import hashlib
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cvm_archive.cli import main, verify_tree
from cvm_archive.fetch.client import BlockedError, FetchError
from cvm_archive.models import Artifact, CatalogEntry
from cvm_archive.sources.catalog import catalog_url


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PAGE = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
HTML = "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm"
STAMP = "2026-10-29T12:00:00Z"


class Client:
    def __init__(self, replies=None):
        self.replies = replies or {}
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        reply = self.replies[url]
        if isinstance(reply, Exception):
            raise reply
        return Artifact.from_bytes(url, reply, "text/html", STAMP)

    @property
    def stats(self):
        return {"conteudo.cvm.gov.br": {"requests": len(self.calls), "failures": 0}}


def real_client():
    replies = {catalog_url("resolucoes", page): (FIXTURES / "sources" / f"catalog-resolucoes-p{page}.html").read_bytes() for page in range(1, 6)}
    replies[PAGE] = (FIXTURES / "sources/document-resol249.html").read_bytes()
    replies[HTML] = (FIXTURES / "html/resol249.htm").read_bytes()
    return Client(replies)


def command(args, client=None, day=29):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(args, client=client, now=lambda: datetime(2026, 10, day, 12, tzinfo=timezone.utc))
    output = json.loads(stdout.getvalue().splitlines()[-1]) if stdout.getvalue().strip() else None
    return code, output, stderr.getvalue()


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def synthetic(root, count=1, pdf=False, consolidated=False):
    entries, replies = [], {}
    for number in range(1, count + 1):
        page = f"https://conteudo.cvm.gov.br/legislacao/resolucoes/resol{number:03d}.html"
        html = f"https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/resol{number:03d}.htm"
        entries.append(CatalogEntry(page, f"Resolução CVM {number}", "resolucoes", str(number), "2026-10-13"))
        links = f'<a href="{html[:-4]}.pdf">[PDF]</a>' if pdf else f'<a href="{html}">[HTML]</a>'
        if consolidated:
            links += f'<a href="{html[:-4]}consolid.pdf">Texto consolidado</a>'
        replies[page] = (f'<article class="contentTextoGeral"><h2>Resolução CVM {number}</h2><section class="contentArticle">'
                         f'<p>Tue Oct 13 18:00:00 BRT 2026</p><p>Regra de teste.</p><p>{links}</p></section></article>').encode()
        replies[html] = (f'<html><body><div><p>RESOLUÇÃO CVM Nº {number}, DE 13 DE OUTUBRO DE 2026</p>'
                         f'<p>Art. 1º Regra {number}.</p></div></body></html>').encode()
    catalog = {"schema_versao": "1.0", "gerado_em": STAMP, "metodo": "enumeracao", "contador_divulgado": count,
               "total": count, "registros": [asdict(entry) for entry in entries]}
    (root / "catalogo").mkdir(parents=True)
    (root / "catalogo/resolucoes.json").write_text(json.dumps(catalog), encoding="utf-8")
    return Client(replies), entries


class CliTests(unittest.TestCase):
    def test_catalog_enumerates_real_five_pages_without_resolving_integral_text(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = real_client()
            code, output, error = command(["catalog", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(output["total"], 249)
            self.assertEqual(client.calls, [catalog_url("resolucoes", page) for page in range(1, 6)])
            rows = json.loads((root / "catalogo/resolucoes.json").read_bytes())["registros"]
            self.assertNotIn("id", rows[0])
            self.assertEqual(len(rows), 249)
            self.assertFalse((root / "cobertura").exists())
            self.assertFalse((root / "reguladores").exists())

    def test_catalog_repeat_keeps_bytes_and_timestamp(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = ["catalog", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, real_client())[0], 0)
            before = snapshot(root)
            code, output, error = command(args, real_client(), day=30)
            self.assertEqual((code, error), (0, ""))
            self.assertFalse(output["changed"])
            self.assertEqual(snapshot(root), before)

    def test_document_auto_enumerates_and_retains_full_denominator(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = real_client()
            code, output, error = command(["collect", "--category", "resolucoes", "--output", str(root), "--document", PAGE, "--cache-dir", str(root / "cache")], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(output["publicados"], 1)
            self.assertEqual(output["pendentes"], 248)
            self.assertIs(output["changed"], True)
            self.assertEqual(len(client.calls), 7)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["categorias"][0]["catalogo_total"], 249)
            self.assertEqual(sum(row["id"] is None for row in report["documentos"]), 248)

    def test_repeated_document_does_not_convert_or_rewrite_unchanged_sources(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = ["collect", "--category", "resolucoes", "--output", str(root), "--document", PAGE, "--cache-dir", str(root / "cache")]
            self.assertEqual(command(args, real_client())[0], 0)
            before = snapshot(root)
            with patch("cvm_archive.cli.convert_html", side_effect=AssertionError("unchanged source was reconverted")):
                code, output, error = command(args, real_client(), day=30)
            self.assertEqual((code, error), (0, ""))
            self.assertFalse(output["changed"])
            self.assertEqual(output["processados"], 0)
            self.assertEqual(snapshot(root), before)

    def test_document_mode_uses_existing_complete_catalog(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root)
            code, _, error = command(["collect", "--category", "resolucoes", "--output", str(root), "--document", entries[0].url], client)
            self.assertEqual((code, error), (0, ""))
            self.assertNotIn(catalog_url("resolucoes", 1), client.calls)

    def test_cached_repeat_does_not_reconvert_during_preflight_verification(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            args = ["collect", "--category", "resolucoes", "--output", str(root), "--document", PAGE, "--cache-dir", str(cache)]
            client = real_client()
            self.assertEqual(command(args, client)[0], 0)
            cache.mkdir()
            for url in (PAGE, HTML):
                raw = client.replies[url]
                (cache / (hashlib.sha256(raw).hexdigest() + ".html")).write_bytes(raw)
            with patch("cvm_archive.cli.convert_html", side_effect=AssertionError("cached source reconverted")):
                self.assertEqual(command(args, real_client())[0], 0)

    def test_pdf_only_is_pending_and_stays_in_denominator(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root, pdf=True)
            code, output, error = command(["collect", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(output["pendentes"], 1)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["motivo"], "pdf-conversor-pendente")
            self.assertEqual(report["categorias"][0]["catalogo_total"], 1)
            self.assertFalse((root / "reguladores").exists())

    def test_stable_batches_do_not_partition_the_mutable_pending_set(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root, count=60)
            args = ["collect", "--category", "resolucoes", "--output", str(root), "--limit", "1"]
            for batch in (0, 1):
                code, output, error = command([*args, "--batch", str(batch)], client)
                self.assertEqual((code, error), (0, ""))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            published = {row["id"] for row in report["documentos"] if row["estado"] == "publicado"}
            self.assertEqual(published, {"cvm-resolucao-1-2026", "cvm-resolucao-51-2026"})
            self.assertEqual(report["categorias"][0]["catalogo_total"], 60)
            self.assertNotIn(entries[1].url, client.calls)

    def test_unchanged_pending_does_not_consume_the_next_limit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root, count=2, pdf=True)
            args = ["collect", "--category", "resolucoes", "--output", str(root), "--limit", "1"]
            self.assertEqual(command(args, client)[0], 0)
            self.assertEqual(command(args, client)[0], 0)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(sum(row["id"] is not None for row in report["documentos"]), 2)

    def test_original_survives_consolidated_pdf_pending(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root, consolidated=True)
            code, output, error = command(["collect", "--category", "resolucoes", "--output", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual((output["pendentes"], output["publicados"]), (1, 0))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            record = report["documentos"][0]
            self.assertEqual(len(record["arquivos"]), 1)
            self.assertIn("consolidada:", record["motivo"])
            self.assertEqual(verify_tree(root)["violacoes"], [])

    def test_changed_original_that_fails_conversion_leaves_no_current_publication(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, client)[0], 0)
            html = next(url for url in client.replies if url.endswith(".htm"))
            client.replies[html] = b"<html><body>Unavailable document</body></html>"
            code, output, error = command(args, client)
            self.assertEqual((code, error), (0, ""))
            self.assertIs(output["changed"], True)
            self.assertEqual(output["publicados"], 0)
            self.assertFalse(list((root / "reguladores").rglob("*.md")))
            self.assertEqual(verify_tree(root)["violacoes"], [])

    def test_metadata_page_byte_change_updates_index_without_rewriting_body(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, client)[0], 0)
            document = next((root / "reguladores").rglob("*.md"))
            before, timestamp = document.read_bytes(), document.stat().st_mtime_ns
            client.replies[entries[0].url] += b"<!-- source bytes changed -->"
            code, output, error = command(args, client, day=30)
            self.assertEqual((code, error), (0, ""))
            self.assertTrue(output["changed"])
            self.assertEqual((document.read_bytes(), document.stat().st_mtime_ns), (before, timestamp))
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            self.assertEqual(report["documentos"][0]["sha256_fontes"][entries[0].url], hashlib.sha256(client.replies[entries[0].url]).hexdigest())

    def test_semantically_unchanged_coverage_preserves_existing_json_bytes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, client)[0], 0)
            path = root / "cobertura/cobertura.json"
            path.write_bytes((json.dumps(json.loads(path.read_bytes()), ensure_ascii=False) + "\n").encode())
            before = snapshot(root)
            code, output, error = command(args, client, day=30)
            self.assertEqual((code, error), (0, ""))
            self.assertFalse(output["changed"])
            self.assertEqual(snapshot(root), before)

    def test_cache_corruption_is_not_reported_as_verified(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            client, _ = synthetic(root)
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root)], client)[0], 0)
            html = next(url for url in client.replies if url.endswith(".htm"))
            cache.mkdir()
            (cache / (hashlib.sha256(client.replies[html]).hexdigest() + ".html")).write_bytes(b"tampered")
            self.assertTrue(verify_tree(root, cache_dir=cache)["violacoes"])

    def test_external_catalog_url_is_rejected_before_any_request(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root)
            path = root / "catalogo/resolucoes.json"
            catalog = json.loads(path.read_bytes())
            catalog["registros"][0]["url"] = "https://dados.cvm.gov.br/api/forbidden"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root)], client)[0], 2)
            self.assertEqual(client.calls, [])

    def test_blocked_auto_enumeration_or_document_never_promotes_partial_data(self):
        for blocked_url in (catalog_url("resolucoes", 3), PAGE, HTML):
            with self.subTest(url=blocked_url), TemporaryDirectory() as temporary:
                root = Path(temporary) / "data"
                client = real_client()
                client.replies[blocked_url] = BlockedError("denied", 403)
                code, output, _ = command(["collect", "--category", "resolucoes", "--output", str(root), "--document", PAGE], client)
                self.assertEqual(code, 3)
                self.assertIsNone(output)
                self.assertFalse(root.exists())

    def test_failed_catalog_keeps_old_catalog_byte_for_byte(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = ["catalog", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command(args, real_client())[0], 0)
            before = snapshot(root)
            client = real_client()
            client.replies[catalog_url("resolucoes", 2)] = b'<section class="listaResultados">0 resultados encontrados</section>'
            self.assertEqual(command(args, client)[0], 2)
            self.assertEqual(snapshot(root), before)

    def test_error_after_a_candidate_keeps_all_previous_public_bytes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = synthetic(root, count=2)
            args = ["collect", "--category", "resolucoes", "--output", str(root)]
            self.assertEqual(command([*args, "--limit", "1"], client)[0], 0)
            before = snapshot(root)
            client.replies[entries[0].url] += b"<!-- changed -->"
            client.replies[entries[1].url] = FetchError("server error", 503)
            self.assertEqual(command(args, client)[0], 2)
            self.assertEqual(snapshot(root), before)

    def test_invalid_local_catalog_fails_before_fetching(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root)
            path = root / "catalogo/resolucoes.json"
            path.write_bytes(b"{broken")
            before = snapshot(root)
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root)], client)[0], 2)
            self.assertEqual(client.calls, [])
            self.assertEqual(snapshot(root), before)

    def test_verify_has_no_network_and_reports_missing_source_bytes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root)
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root)], client)[0], 0)
            client.calls.clear()
            before = snapshot(root)
            code, output, error = command(["verify", "--root", str(root)], client)
            self.assertEqual((code, error), (0, ""))
            self.assertTrue(output["UNVERIFIED"])
            self.assertEqual(client.calls, [])
            self.assertEqual(snapshot(root), before)

    def test_verify_rejects_orphan_and_wrong_front_matter_digest(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, _ = synthetic(root)
            self.assertEqual(command(["collect", "--category", "resolucoes", "--output", str(root)], client)[0], 0)
            original = next((root / "reguladores").rglob("*.md"))
            (original.parent / "orphan.md").write_bytes(original.read_bytes())
            self.assertEqual(command(["verify", "--root", str(root)])[0], 2)
            (original.parent / "orphan.md").unlink()
            source_hash = json.loads((root / "cobertura/cobertura.json").read_bytes())["documentos"][0]["sha256_fontes"][next(url for url in client.replies if url.endswith(".htm"))]
            original.write_bytes(original.read_bytes().replace(source_hash.encode(), b"0" * 64))
            self.assertEqual(command(["verify", "--root", str(root)])[0], 2)

    def test_bad_arguments_and_interval_fail_without_any_http(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client = Client()
            base = ["collect", "--category", "resolucoes", "--output", str(root)]
            for extra in (["--limit", "0"], ["--batch", "-1"], ["--min-interval", "4"], ["--min-interval", "nan"], ["--user-agent", "anonymous"]):
                with self.subTest(extra=extra):
                    self.assertEqual(command(base + extra, client)[0], 2)
            self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
