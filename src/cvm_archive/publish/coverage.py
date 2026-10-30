"""Coverage 2.0 retains unconfirmed entries without inventing legal identities."""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from html import escape
from pathlib import PurePosixPath

from cvm_archive.gates.metadata import valid_date, valid_hash, valid_url
from cvm_archive.models import CatalogEntry
from .markdown import PublicationError, parse_document


STATES = {
    "publicado": "publicados", "pendente": "pendentes", "indisponivel": "indisponiveis",
    "divergente": "divergentes", "fora-de-escopo": "fora_de_escopo",
}
RECORD_FIELDS = {"id", "estado", "motivo", "arquivos", "fonte_cvm", "urls_alternativas", "sha256_fontes", "verificado_em"}


def record_key(record: dict) -> tuple:
    return record["id"] is None, record["id"] or "", record["fonte_cvm"]


def pending_entry(entry: CatalogEntry) -> dict:
    return {
        "id": None, "estado": "pendente", "motivo": "nao-processado", "arquivos": [],
        "fonte_cvm": entry.url, "urls_alternativas": [], "sha256_fontes": {}, "verificado_em": None,
    }


def aggregate_aliases(records: dict[str, dict], prepared: dict[str, dict[str, bytes]], read_file, views: dict[str, dict]) -> tuple[list[dict], dict[str, bytes | None], list[dict]]:
    """Merge only identities already confirmed from official pages, never candidates."""
    groups = {}
    for url, record in records.items():
        key = ("id", record["id"]) if record["id"] is not None else ("url", url)
        groups.setdefault(key, []).append((url, record))
    merged, updates, findings = [], {}, []
    for group in groups.values():
        if len(group) == 1:
            merged.append(copy.deepcopy(group[0][1]))
            continue
        group.sort(key=lambda item: (item[1]["fonte_cvm"], item[0]))
        row = copy.deepcopy(group[0][1])
        pages = sorted({url for _, record in group for url in (record["fonte_cvm"], *record["urls_alternativas"])})
        row["urls_alternativas"] = [url for url in pages if url != row["fonte_cvm"]]
        hashes, approved, all_paths, conflicting_sources = {}, {}, set(), set()
        conflicting, unresolved = [], []
        for url, record in group:
            for source, digest in record["sha256_fontes"].items():
                if source in hashes and hashes[source] != digest:
                    conflicting.append(f"bytes diferentes (sem inferir alteração normativa) para {source}: {hashes[source]} / {digest}")
                    conflicting_sources.add(source)
                hashes[source] = digest
            for name in record["arquivos"]:
                all_paths.add(name)
                data = prepared.get(url, {}).get(name)
                if data is None:
                    data = read_file(name)
                fields, body = parse_document(data)
                comparable = copy.deepcopy(fields)
                for annex in comparable["anexos"]:
                    if annex["url"] == fields["fonte"]:
                        annex["url"], annex["sha256"] = "embedded", "embedded"
                for key in ("fonte", "fonte_cvm", "sha256_fonte", "baixado_em"):
                    comparable.pop(key)
                version = fields["versao_texto"]
                if version in approved:
                    previous = approved[version]
                    previous_fields = parse_document(previous[3])[0]
                    if body != previous[2]:
                        left_words, right_words = body.split(), previous[2].split()
                        boundary = min(len(left_words), len(right_words))
                        difference = next((i for i in range(boundary) if left_words[i] != right_words[i]), boundary)
                        left_excerpt = " ".join(left_words[max(0, difference - 5):difference + 10])
                        right_excerpt = " ".join(right_words[max(0, difference - 5):difference + 10])
                        conflicting.append(f'corpos diferentes para {version}: {fields["fonte"]} declara {left_excerpt!r}; {previous_fields["fonte"]} declara {right_excerpt!r}')
                    if comparable != previous[1]:
                        disagreements = [key for key in comparable if comparable[key] != previous[1][key]]
                        explicit = [key for key in disagreements if key in ("revogada", "data", "numero", "tipo", "unidade")
                                    and comparable[key] is not None and previous[1][key] is not None]
                        details = [f'{key}: {fields["fonte_cvm"]} declara {json.dumps(fields[key], ensure_ascii=False)}; '
                                   f'{previous_fields["fonte_cvm"]} declara {json.dumps(previous_fields[key], ensure_ascii=False)}' for key in disagreements]
                        (conflicting if explicit else unresolved).append("metadados diferentes: " + " / ".join(details))
                else:
                    approved[version] = (name, comparable, body, data)
        observed = [(url, views[url]) for url, _ in group if url in views]
        for index, (left_url, left) in enumerate(observed):
            for right_url, right in observed[index + 1:]:
                for key in ("type", "number", "date", "revoked"):
                    if left.get(key) is not None and right.get(key) is not None and left[key] != right[key]:
                        left_claim = left.get("revocation_evidence") if key == "revoked" else None
                        right_claim = right.get("revocation_evidence") if key == "revoked" else None
                        conflicting.append(f"{key}: {left_url} declara {left_claim or repr(left[key])}; {right_url} declara {right_claim or repr(right[key])}")
        row["sha256_fontes"] = {source: digest for source, digest in hashes.items() if source not in conflicting_sources}
        row["verificado_em"] = max((record["verificado_em"] for _, record in group if record["verificado_em"]), default=None)
        pending_reasons = sorted({record["motivo"] if record["motivo"] and re.match(r"(?:consolidada:|publicação original:|artefato https?://)", record["motivo"])
                                  else f'artefato {record["fonte_cvm"]}: {record["motivo"] or record["estado"]}'
                                  for _, record in group if record["estado"] != "publicado"})
        if any(record["estado"] == "divergente" for _, record in group):
            conflicting.append("divergência oficial já registrada")
        if conflicting:
            row.update(estado="divergente", motivo="fontes-oficiais-conflitantes", arquivos=[])
            findings.append({"id": row["id"], "descricao": "; ".join(sorted(set(conflicting))), "evidencias": pages})
        elif unresolved:
            row.update(estado="pendente", motivo="reconciliacao-de-metadados: " + "; ".join(sorted(set(unresolved))), arquivos=[])
            findings.append({"id": row["id"], "descricao": row["motivo"], "evidencias": pages})
        else:
            row["arquivos"] = sorted(item[0] for item in approved.values())
            if pending_reasons:
                row.update(estado="pendente", motivo="; ".join(pending_reasons))
            else:
                row.update(estado="publicado", motivo=None)
            updates.update({item[0]: item[3] for item in approved.values()})
        for name in all_paths - set(row["arquivos"]):
            updates[name] = None
        merged.append(row)
    return merged, updates, findings


def _record_semantics(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "verificado_em"}


def _semantics(report: dict) -> dict:
    result = copy.deepcopy(report)
    result.pop("gerado_em", None)
    result.pop("coleta", None)
    result["documentos"] = [_record_semantics(record) for record in result["documentos"]]
    return result


def validate_coverage(report: dict) -> tuple[str, ...]:
    errors = []
    required = {"schema_versao", "gerado_em", "coleta", "categorias", "documentos", "divergencias"}
    if not isinstance(report, dict) or set(report) != required:
        return ("coverage-schema",)
    if report["schema_versao"] != "2.0":
        errors.append("coverage-version")
    try:
        stamp = report["gerado_em"]
        if not isinstance(stamp, str) or not stamp.endswith("Z"):
            raise ValueError
        datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        errors.append("coverage-timestamp")
    collection = report["coleta"]
    if (not isinstance(collection, dict) or set(collection) != {"modo", "requisicoes", "falhas_http"} or
            collection["modo"] not in ("completa", "incremental", "documento") or
            any(type(collection[key]) is not int or collection[key] < 0 for key in ("requisicoes", "falhas_http"))):
        errors.append("collection-schema")
    documents, categories = report["documentos"], report["categorias"]
    if not isinstance(documents, list) or not isinstance(categories, list):
        return tuple(errors + ["coverage-arrays"])
    ids, urls, paths = set(), set(), set()
    counts = {counter: 0 for counter in STATES.values()}
    valid_records = True
    for record in documents:
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            errors.append("record-schema")
            valid_records = False
            continue
        identifier = record["id"]
        if identifier is not None:
            if not isinstance(identifier, str) or re.fullmatch(r"cvm-[a-z0-9]+(?:-[a-z0-9]+)*", identifier) is None:
                errors.append("record-identity")
                valid_records = False
            elif identifier in ids:
                errors.append("duplicate-identity")
            else:
                ids.add(identifier)
        url = record["fonte_cvm"]
        if not valid_url(url):
            errors.append("record-url")
            valid_records = False
        elif url in urls:
            errors.append("duplicate-url")
        else:
            urls.add(url)
        state = record["estado"]
        if not isinstance(state, str) or state not in STATES:
            errors.append("record-state")
        else:
            counts[STATES[state]] += 1
        reason = record["motivo"]
        if state in ("pendente", "divergente", "fora-de-escopo") and (not isinstance(reason, str) or not reason.strip()):
            errors.append("record-reason")
        elif reason is not None and not isinstance(reason, str):
            errors.append("record-reason")
        files = record["arquivos"]
        if not isinstance(files, list) or any(not isinstance(path, str) for path in files):
            errors.append("record-files")
        else:
            if len(files) != len(set(files)) or paths.intersection(files):
                errors.append("duplicate-path")
            paths.update(files)
            for path in files:
                parts = PurePosixPath(path)
                if (not path.startswith("reguladores/cvm/") or parts.is_absolute() or
                        ".." in parts.parts or "\\" in path or ":" in path or not path.endswith(".md")):
                    errors.append("record-path")
            if identifier is None and files or state == "publicado" and not files:
                errors.append("unconfirmed-publication")
            if state in ("indisponivel", "divergente", "fora-de-escopo") and files:
                errors.append("forbidden-publication")
            if state == "pendente" and files and (not isinstance(reason, str) or not (
                    any(version + ":" in reason for version in ("consolidada", "publicação original")) or
                    re.search(r"artefato https?://\S+: ", reason))):
                errors.append("missing-version-reason")
        if state == "publicado" and identifier is None:
            errors.append("unconfirmed-publication")
        if record["verificado_em"] is not None and not valid_date(record["verificado_em"]):
            errors.append("record-date")
        if state == "publicado" and record["verificado_em"] is None:
            errors.append("unverified-publication")
        hashes = record["sha256_fontes"]
        if not isinstance(hashes, dict) or any(not valid_url(url) or not valid_hash(digest) for url, digest in hashes.items()):
            errors.append("record-hashes")
        elif state == "publicado" and not hashes:
            errors.append("unverified-publication")
        alternatives = record["urls_alternativas"]
        if (not isinstance(alternatives, list) or any(not valid_url(url) for url in alternatives) or
                len(alternatives) != len(set(alternatives))):
            errors.append("record-aliases")
    if valid_records and documents != sorted(documents, key=record_key):
        errors.append("record-order")
    # The MVP has one category. A later multi-family writer must map each act explicitly.
    if len(categories) != 1:
        errors.append("unsupported-multicategory")
    for category in categories:
        if (not isinstance(category, dict) or set(category) != {"tipo", "catalogo_total", "catalogo_metodo", *STATES.values()} or
                not isinstance(category["tipo"], str) or category["catalogo_metodo"] not in ("contador da busca", "enumeração") or
                any(type(category[key]) is not int or category[key] < 0 for key in ("catalogo_total", *STATES.values()))):
            errors.append("category-schema")
            continue
        if category["catalogo_total"] != len(documents) or any(category[key] != value for key, value in counts.items()):
            errors.append("category-counts")
    if not isinstance(report["divergencias"], list):
        errors.append("divergences-schema")
    else:
        for divergence in report["divergencias"]:
            if (not isinstance(divergence, dict) or set(divergence) != {"id", "descricao", "evidencias"} or
                    not isinstance(divergence["descricao"], str) or not divergence["descricao"].strip() or
                    not isinstance(divergence["evidencias"], list) or not divergence["evidencias"] or
                    any(not valid_url(url) for url in divergence["evidencias"])):
                errors.append("divergence-values")
    return tuple(dict.fromkeys(errors))


def build_coverage(documents: list[dict], catalog_total: int, timestamp: str, collection: dict, *, existing: dict | None = None, divergences: list | None = None, kind: str = "Resolução") -> dict:
    records = copy.deepcopy(documents)
    if existing is not None:
        errors = validate_coverage(existing)
        if errors:
            raise PublicationError(", ".join(errors))
        old_records = {record["fonte_cvm"]: record for record in existing["documentos"]}
        for index, record in enumerate(records):
            old = old_records.get(record["fonte_cvm"])
            if old is not None and _record_semantics(record) == _record_semantics(old):
                records[index] = copy.deepcopy(old)
    records.sort(key=record_key)
    counts = {counter: sum(record["estado"] == state for record in records) for state, counter in STATES.items()}
    report = {
        "schema_versao": "2.0", "gerado_em": timestamp, "coleta": collection,
        "categorias": [{"tipo": kind, "catalogo_total": catalog_total, "catalogo_metodo": "enumeração", **counts}],
        "documentos": records, "divergencias": copy.deepcopy(divergences or []),
    }
    errors = validate_coverage(report)
    if errors:
        raise PublicationError(", ".join(errors))
    return copy.deepcopy(existing) if existing is not None and _semantics(existing) == _semantics(report) else report


def coverage_files(report: dict) -> dict[str, bytes]:
    errors = validate_coverage(report)
    if errors:
        raise PublicationError(", ".join(errors))
    machine = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    def cell(value):
        return escape(str(value if value is not None else "não confirmado"), quote=False).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Cobertura do acervo", "", f'Gerado em {report["gerado_em"]}. Schema {report["schema_versao"]}.', "",
             "| Tipo | Catálogo | Publicados | Pendentes | Indisponíveis | Divergentes | Fora do escopo |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for category in report["categorias"]:
        lines.append("| " + " | ".join(cell(category[key]) for key in ("tipo", "catalogo_total", *STATES.values())) + " |")
    lines.extend(("", "| Identidade | Estado | Motivo | Página oficial | Arquivos aprovados |", "|---|---|---|---|---|"))
    for record in report["documentos"]:
        lines.append("| " + " | ".join(cell(value) for value in (record["id"], record["estado"], record["motivo"], record["fonte_cvm"], ", ".join(record["arquivos"]))) + " |")
    collection = report["coleta"]
    lines.extend(("", "## Coleta registrada", "", f'Modo: {cell(collection["modo"])}. Requisições: {collection["requisicoes"]}. Falhas HTTP: {collection["falhas_http"]}.',
                  "", "## Divergências", ""))
    if report["divergencias"]:
        lines.extend(("| Identidade | Declarações / motivo | Evidências oficiais |", "|---|---|---|"))
        for finding in report["divergencias"]:
            lines.append("| " + " | ".join(cell(value) for value in (finding["id"], finding["descricao"], " ; ".join(finding["evidencias"]))) + " |")
    else:
        lines.append("Nenhuma divergência registrada neste relatório.")
    lines.extend(("", "## Proveniência", "", "| Identidade / página | Verificado em | URLs alternativas | Fontes e SHA-256 |", "|---|---|---|---|"))
    for record in report["documentos"]:
        lines.append("| " + " | ".join(cell(value) for value in (
            record["id"] or record["fonte_cvm"], record["verificado_em"] or "não consultado",
            " ; ".join(record["urls_alternativas"]), " ; ".join(f"{url} : {digest}" for url, digest in sorted(record["sha256_fontes"].items())))) + " |")
    return {"cobertura/cobertura.json": machine, "cobertura/COBERTURA.md": ("\n".join(lines) + "\n").encode("utf-8")}
