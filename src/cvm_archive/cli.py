"""Resolution MVP: exhaustive catalog, bounded collection and offline verification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from cvm_archive.convert.html import convert_html
from cvm_archive.fetch.client import DEFAULT_USER_AGENT, BlockedError, FetchError, PoliteClient
from cvm_archive.gates.fidelity import check_html_structure, read_html_text
from cvm_archive.gates.metadata import TYPES, confirmed_id, valid_date, valid_url, validate_metadata
from cvm_archive.models import Artifact, CatalogEntry
from cvm_archive.publish.coverage import aggregate_aliases, build_coverage, coverage_files, pending_entry, validate_coverage
from cvm_archive.publish.markdown import PublicationError, check_embedded_annexes, check_identity, decode_html, decode_html_bytes, document_path, embedded_annexes, parse_document, render_document
from cvm_archive.publish.transaction import promote, safe_target
from cvm_archive.sources import DocumentConflictError, DocumentParseError, enumerate_catalog, parse_document_page


BATCH_SIZE = 50
CATALOG_PATH = "catalogo/resolucoes.json"
COVERAGE_PATH = "cobertura/cobertura.json"
RECORD_KEYS = {"url", "title", "category", "number", "date"}


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _read_json(data: bytes):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data.decode("utf-8"), object_pairs_hook=unique)


def _catalog_entries(catalog: dict) -> list[CatalogEntry]:
    keys = {"schema_versao", "gerado_em", "metodo", "contador_divulgado", "total", "registros"}
    if (not isinstance(catalog, dict) or set(catalog) != keys or catalog["schema_versao"] != "1.0" or
            catalog["metodo"] != "enumeracao" or not isinstance(catalog["registros"], list) or
            type(catalog["total"]) is not int or catalog["total"] != len(catalog["registros"])):
        raise ValueError("invalid exhaustive catalog")
    if catalog["contador_divulgado"] is not None and catalog["contador_divulgado"] != catalog["total"]:
        raise ValueError("catalog counter disagrees with enumeration")
    if catalog["contador_divulgado"] is not None and type(catalog["contador_divulgado"]) is not int:
        raise ValueError("catalog counter must be an integer")
    if not isinstance(catalog["gerado_em"], str) or not catalog["gerado_em"].endswith("Z"):
        raise ValueError("catalog timestamp must be UTC")
    datetime.fromisoformat(catalog["gerado_em"].replace("Z", "+00:00"))
    entries = []
    for row in catalog["registros"]:
        if (not isinstance(row, dict) or set(row) != RECORD_KEYS or row["category"] != "resolucoes" or
                not valid_url(row["url"]) or not isinstance(row["title"], str) or not row["title"].strip() or
                row["number"] is not None and not isinstance(row["number"], str) or
                row["date"] is not None and not valid_date(row["date"])):
            raise ValueError("invalid catalog candidate")
        if urlsplit(row["url"]).hostname != "conteudo.cvm.gov.br" or not urlsplit(row["url"]).path.startswith("/legislacao/"):
            raise ValueError("catalog candidate is outside the official MVP source")
        entries.append(CatalogEntry(**row))
    urls = [entry.url for entry in entries]
    if urls != sorted(set(urls)):
        raise ValueError("catalog is not sorted or has duplicate URLs")
    return entries


def _enumerated_catalog(client, stamp: str) -> dict:
    entries = sorted(enumerate_catalog(client, "resolucoes"), key=lambda entry: entry.url)
    catalog = {"schema_versao": "1.0", "gerado_em": stamp, "metodo": "enumeracao",
               "contador_divulgado": len(entries), "total": len(entries), "registros": [asdict(entry) for entry in entries]}
    _catalog_entries(catalog)
    return catalog


def _metrics(client) -> dict:
    stats = getattr(client, "stats", {})
    return {"requisicoes": sum(item["requests"] for item in stats.values()),
            "falhas_http": sum(item["failures"] for item in stats.values())}


def _cached_bytes(cache_dir: Path, digest: str) -> bytes | None:
    if not cache_dir.is_dir():
        return None
    found = None
    for path in sorted(cache_dir.glob(digest + ".*")):
        if path.name.endswith(".meta.json"):
            continue
        if path.is_symlink() or path.is_junction():
            raise ValueError("cache symlinks are not accepted")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("cached bytes disagree with their digest")
        found = raw
    return found


def verify_tree(root: Path, *, cache_dir: Path | None = None, updates: dict[str, bytes | None] | None = None) -> dict:
    """Inspect proposed or existing files without modifying them or using HTTP."""
    updates = updates or {}
    def read(name):
        if name in updates:
            if updates[name] is None:
                raise FileNotFoundError(name)
            return updates[name]
        return safe_target(root, name).read_bytes()
    errors, unverified = [], []
    try:
        report = _read_json(read(COVERAGE_PATH))
        errors.extend(validate_coverage(report))
        if errors:
            return {"violacoes": errors, "UNVERIFIED": unverified}
    except (OSError, ValueError, TypeError) as exc:
        return {"violacoes": [str(exc)], "UNVERIFIED": unverified}
    listed = set()
    expected_files = coverage_files(report)
    try:
        if read("cobertura/COBERTURA.md") != expected_files["cobertura/COBERTURA.md"]:
            errors.append("human coverage disagrees with machine coverage")
    except OSError as exc:
        errors.append(str(exc))
    for record in report["documentos"]:
        for name in record["arquivos"]:
            listed.add(name)
            try:
                fields, body = parse_document(read(name))
                errors.extend(f"{name}: {error}" for error in validate_metadata(fields, require_evidence=False))
                if fields["id"] != record["id"] or name != document_path(fields):
                    errors.append(f"{name}: coverage identity or document path mismatch")
                if fields["fonte_cvm"] not in (record["fonte_cvm"], *record["urls_alternativas"]):
                    errors.append(f"{name}: source page mismatch")
                if record["sha256_fontes"].get(fields["fonte"]) != fields["sha256_fonte"]:
                    errors.append(f"{name}: source digest missing from coverage index")
                for annex in fields["anexos"]:
                    if record["sha256_fontes"].get(annex["url"]) != annex["sha256"]:
                        errors.append(f"{name}: annex digest missing from coverage index")
                raw = _cached_bytes(cache_dir, fields["sha256_fonte"]) if cache_dir else None
                if raw is None:
                    unverified.append(f"source bytes: {fields['fonte']}")
                elif fields["formato_fonte"] == "html":
                    source = decode_html_bytes(raw)
                    errors.extend(f"{name}: {error}" for error in check_html_structure(source, body, fields["fonte"]))
                    errors.extend(f"{name}: {error}" for error in check_identity(read_html_text(source), fields))
                    errors.extend(f"{name}: {error}" for error in check_embedded_annexes(read_html_text(source), fields))
                if fields["revogada"] is not None:
                    unverified.append(f"current revocation evidence (offline): {record['fonte_cvm']}")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                errors.append(f"{name}: {exc}")
        if cache_dir:
            for url, digest in record["sha256_fontes"].items():
                try:
                    if _cached_bytes(cache_dir, digest) is None:
                        unverified.append(f"source bytes: {url}")
                except (OSError, ValueError) as exc:
                    errors.append(f"{url}: {exc}")
    actual = {path.relative_to(root).as_posix() for path in (root / "reguladores").rglob("*.md")}
    actual.update(name for name, data in updates.items() if name.startswith("reguladores/") and name.endswith(".md") and data is not None)
    actual.difference_update(name for name, data in updates.items() if data is None)
    if actual != listed:
        errors.append("published files outside coverage or missing files")
    try:
        catalog_path = safe_target(root, CATALOG_PATH)
        if CATALOG_PATH in updates or catalog_path.is_file():
            entries = _catalog_entries(_read_json(read(CATALOG_PATH)))
            for entry in entries:
                matches = [record for record in report["documentos"] if entry.url in (record["fonte_cvm"], *record["urls_alternativas"])]
                if not matches:
                    errors.append("catalog entry absent from coverage and aliases")
                elif len(matches) > 1 and all(record["id"] is not None for record in matches):
                    errors.append("catalog URL assigned to multiple confirmed identities")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"catalog coverage: {exc}")
    return {"categorias": report["categorias"], "violacoes": sorted(set(errors)), "UNVERIFIED": sorted(set(unverified))}


def _relation(row: dict) -> dict:
    return {"id": None, "titulo": row["title"], "url": row["url"], "contexto": row["context"]}


def _metadata(page: dict, artifact: Artifact, source_page: str, version: str) -> dict:
    kind = next((label for label, value in TYPES.items() if value[1] == page["type"]), None)
    if kind is None:
        raise ValueError("unconfirmed official type")
    details = page["document_metadata"]
    return {
        "schema_versao": "1.0", "id": confirmed_id(kind, page["number"], page["date"]),
        "classe": TYPES[kind][0], "tipo": kind, "titulo": page["title"],
        "orgao": "Comissão de Valores Mobiliários", "unidade": None,
        "numero": page["number"], "data": page["date"], "revogada": page["revoked"],
        "revogada_por": [_relation(row) for row in page["relations"]["revoked_by"]],
        "alterada_por": [_relation(row) for row in page["relations"]["altered_by"]],
        "versao_texto": version, "publicacao": details["publication"],
        "data_publicacao": details["data_publication"], "edicao": details["edition"],
        "ementa": details["ementa"], "fonte": artifact.url,
        "fonte_cvm": source_page if source_page != artifact.url else None,
        "sha256_fonte": artifact.sha256, "formato_fonte": "html", "ocr": False,
        "baixado_em": artifact.fetched_at[:10], "anexos": [],
    }


def _annex_candidate(artifact: dict) -> bool:
    return bool(re.search(r"(?:_anexo|_suplement|_partegeral)|^(?:Anexo|Suplementos|Parte Geral)\b",
                          artifact["url"] + "\n" + artifact["label"], re.I | re.M))


def _linked_annexes(html: str, base: str) -> list[str]:
    class Anchors(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.href, self.label, self.result = None, [], []
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.href, self.label = dict(attrs).get("href"), []
        def handle_data(self, data):
            if self.href:
                self.label.append(data)
        def handle_endtag(self, tag):
            if tag == "a" and self.href:
                target = urljoin(base, self.href)
                path = urlsplit(target).path
                if path != urlsplit(base).path and re.match(r"\s*(?:ANEXO|SUPLEMENTO|APÊNDICE)\b", "".join(self.label), re.I):
                    self.result.append(target)
                self.href = None
    parser = Anchors()
    parser.feed(html)
    parser.close()
    return parser.result


def _same_publication(old: bytes, new: bytes) -> bool:
    previous, previous_body = parse_document(old)
    current, current_body = parse_document(new)
    previous.pop("baixado_em")
    current.pop("baixado_em")
    return previous == current and previous_body == current_body


def _process(entry: CatalogEntry, client, stamp: str, fetched: dict[str, Artifact], root: Path, old: dict | None, *, findings: list[dict], views: dict[str, dict]) -> tuple[dict, dict[str, bytes]]:
    record = pending_entry(entry)
    record["verificado_em"] = stamp[:10]
    def fetch(url):
        if url not in fetched:
            fetched[url] = client.fetch(url)
        artifact = fetched[url]
        record["sha256_fontes"][artifact.url] = artifact.sha256
        return artifact
    try:
        page_artifact = fetch(entry.url)
    except FetchError as exc:
        if exc.status not in (404, 410):
            raise
        if old and old["id"] is not None:
            record = copy.deepcopy(old)
            record.update(estado="pendente", motivo="publicação original: pagina-indisponivel", verificado_em=stamp[:10])
        else:
            record.update(estado="indisponivel", motivo=f"http-{exc.status}")
        return record, {}
    if page_artifact.url != entry.url:
        record["urls_alternativas"] = [page_artifact.url]
    try:
        page = parse_document_page(decode_html(page_artifact), page_artifact.url, entry.category)
    except DocumentConflictError as exc:
        identity = exc.identity
        try:
            kind = next(label for label, value in TYPES.items() if value[1] == identity["type"])
            record["id"] = confirmed_id(kind, identity["number"], identity["date"])
        except (StopIteration, ValueError):
            pass
        record.update(estado="divergente", motivo="revogacao-conflitante")
        findings.append({"id": record["id"], "descricao": "Declarações oficiais incompatíveis na mesma página: " + " / ".join(exc.claims),
                         "evidencias": [exc.source_url]})
        return record, {}
    except DocumentParseError as exc:
        record["motivo"] = "revisao-manual: " + str(exc)
        return record, {}
    views[entry.url] = page
    try:
        kind = next(label for label, value in TYPES.items() if value[1] == page["type"])
        record["id"] = confirmed_id(kind, page["number"], page["date"])
    except (StopIteration, ValueError):
        record["motivo"] = "identidade-nao-confirmada"
        return record, {}
    if page["type"] != "resolucao":
        record["motivo"] = "familia-fora-do-mvp"
        return record, {}
    artifacts = page["artifacts"]
    if not artifacts:
        record["motivo"] = "integra-nao-encontrada"
        return record, {}
    uncertain = [item for item in artifacts if item["version"] is None]
    files = {}
    pending = [("artefato " + item["url"], item["pending_reason"]) for item in uncertain]
    versions = sorted({artifact["version"] for artifact in artifacts if artifact["version"] is not None})
    for version in versions:
        variants = [item for item in artifacts if item["version"] == version]
        if any(_annex_candidate(item) for item in variants):
            pending.append((version, "anexo-revisao-manual"))
            continue
        html_variants = [item for item in variants if item["format"] == "html"]
        if not html_variants:
            pending.append((version, "pdf-conversor-pendente" if any(item["format"] == "pdf" for item in variants) else "conversor-pendente"))
            continue
        if len(html_variants) != 1:
            pending.append((version, "integra-ambigua"))
            continue
        if urlsplit(html_variants[0]["url"]).hostname != "conteudo.cvm.gov.br":
            pending.append((version, "fonte-externa-revisao-manual"))
            continue
        try:
            artifact = fetch(html_variants[0]["url"])
        except FetchError as exc:
            if exc.status not in (404, 410):
                raise
            pending.append((version, f"integra-http-{exc.status}"))
            continue
        if urlsplit(artifact.url).hostname != "conteudo.cvm.gov.br":
            pending.append((version, "fonte-externa-revisao-manual"))
            continue
        source = decode_html(artifact)
        if _linked_annexes(source, artifact.url):
            pending.append((version, "anexo-revisao-manual"))
            continue
        conversion = convert_html(source, artifact.url)
        if conversion.pending_reason:
            pending.append((version, conversion.pending_reason))
            continue
        fields = _metadata(page, artifact, page_artifact.url, version)
        fields["anexos"] = embedded_annexes(read_html_text(source), artifact.url, artifact.sha256, "html")
        try:
            data = render_document(fields, artifact, conversion, discovered_annex_urls=tuple(annex["url"] for annex in fields["anexos"]),
                                   revocation_evidence=page["revocation_evidence"])
        except PublicationError as exc:
            pending.append((version, "portao-fidelidade: " + str(exc)))
            continue
        name = document_path(fields)
        previous = safe_target(root, name)
        if previous.is_file() and _same_publication(previous.read_bytes(), data):
            data = previous.read_bytes()
        files[name] = data
    record["arquivos"] = sorted(files)
    if pending:
        record["motivo"] = "; ".join(version + ": " + reason for version, reason in pending) if files or len(versions) > 1 or uncertain else pending[0][1]
    elif files:
        record.update(estado="publicado", motivo=None)
    return record, files


def _collect(args, client, stamp: str) -> dict:
    root = Path(args.output)
    catalog_path = safe_target(root, CATALOG_PATH)
    previous_catalog = _read_json(catalog_path.read_bytes()) if catalog_path.is_file() else None
    # Invalid existing state must fail before any source requests.
    entries = _catalog_entries(previous_catalog) if previous_catalog is not None else None
    coverage_path = safe_target(root, COVERAGE_PATH)
    previous = _read_json(coverage_path.read_bytes()) if coverage_path.is_file() else None
    if previous is not None:
        checked = verify_tree(root, cache_dir=Path(args.cache_dir))
        if checked["violacoes"]:
            raise PublicationError("; ".join(checked["violacoes"]))
    elif any((root / "reguladores").rglob("*.md")):
        raise PublicationError("published files exist without coverage")
    catalog = previous_catalog if previous_catalog is not None else _enumerated_catalog(client, stamp)
    entries = entries if entries is not None else _catalog_entries(catalog)
    old_records = {url: record for record in previous["documentos"] for url in (record["fonte_cvm"], *(record["urls_alternativas"] if record["id"] is not None else []))} if previous else {}
    catalog_urls = {entry.url for entry in entries}
    if previous and any(not catalog_urls.intersection((record["fonte_cvm"], *record["urls_alternativas"])) for record in previous["documentos"]):
        raise PublicationError("catalog removal or alias needs manual reconciliation; old coverage preserved")
    records = {entry.url: copy.deepcopy(old_records.get(entry.url, pending_entry(entry))) for entry in entries}
    if args.document:
        selected = [entry for entry in entries if entry.url == args.document]
        if len(selected) != 1:
            raise ValueError("document URL must exist in the complete local catalog")
    else:
        selected = entries[args.batch * BATCH_SIZE:(args.batch + 1) * BATCH_SIZE]
        if not selected and entries:
            raise ValueError("batch is outside the complete catalog")
    updates, processed = {}, 0
    prepared, views = {}, {}
    handled_urls, processed_keys = set(), set()
    findings = copy.deepcopy(previous["divergencias"]) if previous else []
    for entry in selected:
        if entry.url in handled_urls:
            continue
        if not args.document and args.limit is not None and processed >= args.limit:
            break
        old = old_records.get(entry.url)
        fetched = {}
        unchanged = bool(old and old["sha256_fontes"])
        if old:
            try:
                page = client.fetch(entry.url)
                fetched[entry.url] = fetched[page.url] = page
                if old["sha256_fontes"].get(page.url) != page.sha256:
                    unchanged = False
            except FetchError as exc:
                if exc.status not in (404, 410):
                    raise
                unchanged = False
            for url, digest in old["sha256_fontes"].items():
                try:
                    if url not in fetched:
                        fetched[url] = client.fetch(url)
                    if fetched[url].sha256 != digest or fetched[url].url != url:
                        unchanged = False
                except FetchError as exc:
                    if exc.status not in (404, 410):
                        raise
                    unchanged = False
        needs_reconciliation = old and (old["estado"] == "divergente" or str(old["motivo"]).startswith("reconciliacao-de-metadados"))
        if unchanged and not args.document and not needs_reconciliation:
            handled_urls.update(url for url, record in old_records.items() if record is old)
            continue
        # A normal unchanged published document is not reconverted, including document mode.
        if unchanged and old["estado"] == "publicado":
            handled_urls.update(url for url, record in old_records.items() if record is old)
            continue
        findings = [finding for finding in findings if entry.url not in finding["evidencias"]
                    and not (old and old["id"] is not None and finding["id"] == old["id"])]
        work = [entry]
        if old and old["id"] is not None:
            work.extend(candidate for candidate in entries if candidate.url != entry.url and
                        old_records.get(candidate.url, {}).get("id") == old["id"])
        for member in work:
            member_old = old_records.get(member.url)
            record, files = _process(member, client, stamp, fetched, root, member_old, findings=findings, views=views)
            if member_old and member_old["id"] is not None:
                if record["id"] is None:
                    record["id"] = member_old["id"]
                elif record["id"] != member_old["id"]:
                    raise PublicationError("official identity changed; manual reconciliation required")
                record["urls_alternativas"] = sorted(set((member.url, member_old["fonte_cvm"], *member_old["urls_alternativas"], *record["urls_alternativas"])) - {record["fonte_cvm"]})
            records[member.url] = record
            prepared[member.url] = files
            updates.update(files)
            for name in member_old["arquivos"] if member_old else ():
                if name not in record["arquivos"]:
                    updates[name] = None
            handled_urls.add(member.url)
            processed_keys.add(("id", record["id"]) if record["id"] else ("url", member.url))
        processed = len(processed_keys)
    grouped, alias_updates, alias_findings = aggregate_aliases(records, prepared, lambda name: safe_target(root, name).read_bytes(), views)
    updates.update(alias_updates)
    findings.extend(finding for finding in alias_findings if finding not in findings)
    report = build_coverage(grouped, len(grouped), stamp,
                            {"modo": "documento" if args.document else "completa", **_metrics(client)}, existing=previous,
                            divergences=sorted(findings, key=lambda item: (item["id"] or "", item["evidencias"], item["descricao"])))
    reports = coverage_files(report)
    if previous is not None and report == previous:
        reports = {name: safe_target(root, name).read_bytes() for name in reports}
    updates.update(reports)
    if previous_catalog is None:
        updates[CATALOG_PATH] = _json_bytes(catalog)
    checked = verify_tree(root, cache_dir=Path(args.cache_dir), updates=updates)
    if checked["violacoes"]:
        raise PublicationError("; ".join(checked["violacoes"]))
    before = {name: safe_target(root, name).read_bytes() if safe_target(root, name).is_file() else None for name in updates}
    promote(root, updates)
    changed = any(before[name] != value for name, value in updates.items() if name.startswith(("reguladores/", "cobertura/")))
    category = report["categorias"][0]
    return {"changed": changed, "publicados": category["publicados"], "pendentes": category["pendentes"],
            "indisponiveis": category["indisponiveis"], "processados": processed, **_metrics(client)}


def _nonnegative(value):
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _positive(value):
    parsed = _nonnegative(value)
    if not parsed:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main(argv=None, *, client=None, now=None) -> int:
    parser = argparse.ArgumentParser(description="Official CVM resolution archive collector")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("catalog", "collect"):
        command = commands.add_parser(name)
        command.add_argument("--category", choices=("resolucoes",), required=True)
        command.add_argument("--output", required=True)
        command.add_argument("--min-interval", type=float, default=5.0)
        command.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
        if name == "collect":
            command.add_argument("--cache-dir", default=".scratch/cache")
            command.add_argument("--document")
            command.add_argument("--batch", type=_nonnegative, default=0)
            command.add_argument("--limit", type=_positive)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", required=True)
    try:
        args = parser.parse_args(argv)
        if args.command == "verify":
            result = verify_tree(Path(args.root), cache_dir=Path(".scratch/cache"))
            print(json.dumps(result, ensure_ascii=False))
            return 2 if result["violacoes"] else 0
        if args.min_interval < 5 or not math.isfinite(args.min_interval):
            raise ValueError("minimum interval must be finite and at least five seconds")
        if "https://github.com/StaffeToxic/normas-cvm" not in args.user_agent:
            raise ValueError("User-Agent must identify this repository")
        clock = now or (lambda: datetime.now(timezone.utc))
        stamp = clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if client is None:
            cache = Path(getattr(args, "cache_dir", ".scratch/cache"))
            client = PoliteClient(min_interval=args.min_interval, user_agent=args.user_agent,
                                  cache_dir=cache, log_path=cache.parent / "logs" / (stamp.replace(":", "-") + ".jsonl"))
        if args.command == "catalog":
            catalog = _enumerated_catalog(client, stamp)
            target = safe_target(Path(args.output), CATALOG_PATH)
            encoded = _json_bytes(catalog)
            if target.is_file():
                old_bytes = target.read_bytes()
                old = _read_json(old_bytes)
                _catalog_entries(old)
                if {key: value for key, value in old.items() if key != "gerado_em"} == {key: value for key, value in catalog.items() if key != "gerado_em"}:
                    catalog = old
                    encoded = old_bytes
            changed = promote(Path(args.output), {CATALOG_PATH: encoded})
            print(json.dumps({"changed": changed, "total": catalog["total"], **_metrics(client)}))
        else:
            print(json.dumps(_collect(args, client, stamp), ensure_ascii=False))
        return 0
    except SystemExit as exc:
        return int(exc.code)
    except BlockedError as exc:
        print(f"blocked: {exc}", file=sys.stderr)
        return 3
    except (FetchError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
