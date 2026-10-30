"""Incremental collection uses a complete catalog and preserves prior bytes on error."""

import hashlib
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from cvm_archive.models import CatalogEntry
from cvm_archive.sources.catalog import catalog_url
from cvm_archive.sources.feeds import FEED_URLS, FeedError, FeedItem, incremental_urls, match_catalog, parse_feed
from cvm_archive.fetch.client import BlockedError
from tests.integration.test_cli import command, snapshot, synthetic


def rss(urls=()):
    return ('<rss><channel>' + ''.join(f'<item><title>Signal</title><link>{url}</link><pubDate>Tue, 27 Oct 2026 16:31:17 -0300</pubDate><description>Not a normative body</description></item>' for url in urls) + '</channel></rss>').encode()


def search(entries):
    return (f'<section class="listaResultados">{len(entries)} resultados encontrados' + ''.join(
        f'<article><h3><a href="{entry["url"]}">{entry["title"]}</a></h3><b>Data:</b> 13/10/2026</article>' for entry in entries
    ) + '</section>').encode()


def setup(root, count=1):
    client, entries = synthetic(root, count=count)
    catalog = json.loads((root / "catalogo/resolucoes.json").read_bytes())
    client.replies[catalog_url("resolucoes", 1)] = search(catalog["registros"])
    for feed in FEED_URLS:
        client.replies[feed] = rss()
    return client, entries


class FeedTests(unittest.TestCase):
    def test_official_snapshot_hash_and_signals_are_verified_without_new_http(self):
        root = Path(__file__).resolve().parents[1] / "fixtures/feeds"
        metadata = json.loads((root / "manifest.json").read_bytes())
        raw = (root / metadata["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["fixture_sha256"])
        items = parse_feed(raw)
        self.assertEqual(len(items), 10)
        self.assertTrue(any("oc-smi-0426" in item.url for item in items))
        self.assertTrue(any("resol067" in item.url and "2026" in item.pub_date for item in items))

    def test_feed_date_does_not_become_an_act_date_or_body(self):
        item = parse_feed(rss(["http://www.cvm.gov.br/legislacao/resolucoes/resol001.html"]))[0]
        self.assertEqual(item.published_at, "2026-10-27T19:31:17Z")
        self.assertFalse(hasattr(item, "description"))

    def test_legacy_links_prioritize_real_catalog_urls_without_fetching_legacy(self):
        url = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol001.html"
        item = FeedItem(url.replace("https://conteudo", "http://www"), "Signal", None, None)
        entry = CatalogEntry(url, "Resolution", "resolucoes", "1", "2026-10-13")
        self.assertEqual(match_catalog([item], [entry]), [url])
        self.assertEqual(match_catalog([FeedItem("https://example.org/legislacao/resolucoes/resol001.html", "Fake", None, None)], [entry]), [])

    def test_invalid_xml_entities_and_non_http_links_are_rejected(self):
        for data in (b"<html>Maintenance</html>", b"<rss>", b'<!DOCTYPE rss [<!ENTITY x "x">]><rss><channel/></rss>', rss(["javascript:alert(1)"])):
            with self.subTest(data=data), self.assertRaises(FeedError):
                parse_feed(data)

    def test_unknown_timezone_is_not_invented(self):
        data = rss(["https://conteudo.cvm.gov.br/x"]).replace(b"-0300", b"UNKNOWN")
        self.assertIsNone(parse_feed(data)[0].published_at)

    def test_rotation_visits_all_batches_over_successive_weeks(self):
        entries = [CatalogEntry(f"https://conteudo.cvm.gov.br/legislacao/resolucoes/resol{n:03d}.html", "Candidate", "resolucoes", str(n), None) for n in range(1, 121)]
        known = {entry.url for entry in entries}
        visited = set()
        for offset in range(3):
            visited.update(incremental_urls(entries, known_urls=known, signal_urls=[], first_page_urls=[], today=date(2026, 10, 26) + timedelta(weeks=offset)))
        self.assertEqual(visited, known)


class IncrementalTests(unittest.TestCase):
    def args(self, root):
        return ["collect", "--category", "resolucoes", "--output", str(root), "--cache-dir", str(root / "cache")]

    def test_unchanged_incremental_keeps_all_public_bytes_and_dates(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = setup(root)
            self.assertEqual(command(self.args(root), client)[0], 0)
            before = {name: data for name, data in snapshot(root).items() if not name.startswith(("cache/", "logs/"))}
            code, result, error = command(self.args(root) + ["--incremental"], client, day=30)
            self.assertEqual((code, error), (0, ""))
            self.assertFalse(result["changed"])
            self.assertEqual(before, {name: data for name, data in snapshot(root).items() if not name.startswith(("cache/", "logs/"))})
            self.assertTrue(all(url in client.calls for url in FEED_URLS))

    def test_new_catalog_entry_is_collected_even_when_absent_from_rss(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = setup(root)
            self.assertEqual(command(self.args(root), client)[0], 0)
            other = root / "other"
            new_client, new_entries = synthetic(other, count=2)
            client.replies.update(new_client.replies)
            catalog = json.loads((other / "catalogo/resolucoes.json").read_bytes())
            client.replies[catalog_url("resolucoes", 1)] = search(catalog["registros"])
            code, result, error = command(self.args(root) + ["--incremental"], client)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(result["publicados"], 2)
            self.assertEqual(json.loads((root / "catalogo/resolucoes.json").read_bytes())["total"], 2)

    def test_catalog_removal_is_logged_without_erasing_existing_data(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = setup(root, count=2)
            self.assertEqual(command(self.args(root), client)[0], 0)
            before = {name: data for name, data in snapshot(root).items() if name.startswith(("catalogo/", "cobertura/", "reguladores/"))}
            catalog = json.loads((root / "catalogo/resolucoes.json").read_bytes())
            client.replies[catalog_url("resolucoes", 1)] = search(catalog["registros"][:1])
            self.assertEqual(command(self.args(root) + ["--incremental"], client)[0], 2)
            self.assertEqual(before, {name: data for name, data in snapshot(root).items() if name.startswith(("catalogo/", "cobertura/", "reguladores/"))})
            self.assertTrue(any("catalog-removal-needs-review" in path.read_text() for path in (root / "logs").glob("*.events.jsonl")))

    def test_consolidated_change_at_the_same_url_updates_only_that_version(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            client, entries = setup(root)
            original = next(url for url in client.replies if url.endswith(".htm"))
            consolidated = original[:-4] + "consolid.htm"
            client.replies[entries[0].url] = client.replies[entries[0].url].replace(b"</section>", f'<p><a href="{consolidated}">Texto consolidado [HTML]</a></p></section>'.encode())
            client.replies[consolidated] = client.replies[original].replace(b"Regra 1.", b"Regra consolidada 1.")
            self.assertEqual(command(self.args(root), client)[0], 0)
            report = json.loads((root / "cobertura/cobertura.json").read_bytes())
            record = report["documentos"][0]
            original_path = next(name for name in record["arquivos"] if ".consolidada." not in name)
            old_body = (root / original_path).read_bytes()
            old_hash = record["sha256_fontes"][consolidated]
            client.replies[consolidated] = client.replies[consolidated].replace(b"Regra consolidada", b"Regra revista")
            code, result, error = command(self.args(root) + ["--incremental"], client)
            self.assertEqual((code, error), (0, ""))
            self.assertTrue(result["changed"])
            record = json.loads((root / "cobertura/cobertura.json").read_bytes())["documentos"][0]
            self.assertNotEqual(record["sha256_fontes"][consolidated], old_hash)
            self.assertEqual((root / original_path).read_bytes(), old_body)

    def test_feed_block_or_soft_404_does_not_promote_a_partial_run(self):
        for reply, expected in ((BlockedError("denied", 429), 3), (b"<html>Unavailable</html>", 2)):
            with self.subTest(expected=expected), TemporaryDirectory() as temporary:
                root = Path(temporary)
                client, _ = setup(root)
                self.assertEqual(command(self.args(root), client)[0], 0)
                before = {name: data for name, data in snapshot(root).items() if name.startswith(("catalogo/", "cobertura/", "reguladores/"))}
                client.replies[FEED_URLS[1]] = reply
                self.assertEqual(command(self.args(root) + ["--incremental"], client)[0], expected)
                self.assertEqual(before, {name: data for name, data in snapshot(root).items() if name.startswith(("catalogo/", "cobertura/", "reguladores/"))})


if __name__ == "__main__":
    unittest.main()
