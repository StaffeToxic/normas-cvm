"""Validate schema 1.0 and exact artifact provenance before publication."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from urllib.parse import urlsplit

from cvm_archive.models import Artifact


FIELDS = (
    "schema_versao", "id", "classe", "tipo", "titulo", "orgao", "unidade", "numero",
    "data", "revogada", "revogada_por", "alterada_por", "versao_texto", "publicacao",
    "data_publicacao", "edicao", "ementa", "fonte", "fonte_cvm", "sha256_fonte",
    "formato_fonte", "ocr", "baixado_em", "anexos",
)
TYPES = {
    "Resolução": ("norma", "resolucao", "resolucoes"),
    "Instrução": ("norma", "instrucao", "instrucoes"),
    "Deliberação": ("norma", "deliberacao", "deliberacoes"),
    "Parecer de Orientação": ("norma", "parecer-de-orientacao", "pareceres-orientacao"),
    "Decisão Conjunta": ("norma", "decisao-conjunta", "decisoes-conjuntas"),
    "Portaria": ("norma", "portaria", "portarias"),
    "Ofício Circular": ("orientação", "oficio-circular", "oficios-circulares"),
    "Nota Explicativa": ("orientação", "nota-explicativa", "notas-explicativas"),
    "Perguntas e Respostas": ("orientação", "perguntas-e-respostas", "perguntas-e-respostas"),
    "Manual": ("orientação", "manual", "manuais"),
    "Guia": ("orientação", "guia", "manuais"),
    "Audiência Pública": ("minuta", "audiencia-publica", "audiencias-publicas"),
    "Consulta Pública": ("minuta", "consulta-publica", "audiencias-publicas"),
}
VERSIONS = ("publicação original", "consolidada")


def valid_url(value) -> bool:
    if not isinstance(value, str) or any(char.isspace() for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def valid_hash(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def valid_date(value) -> bool:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def slug(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value.replace("º", "").replace("°", "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def confirmed_id(kind: str, number: str | None, act_date: str | None, unit: str | None = None) -> str:
    """No identity is invented when the official number or year is unknown."""
    if (not isinstance(kind, str) or kind not in TYPES or not isinstance(number, str) or
            not number or not valid_date(act_date) or unit is not None and not isinstance(unit, str)):
        raise ValueError("identity needs an official type, number and date")
    code = TYPES[kind][1]
    middle = f"{slug(unit)}-" if unit else ""
    return f"cvm-{code}-{middle}{slug(number)}-{act_date[:4]}"


def validate_metadata(metadata: dict, artifact: Artifact | None = None, *, revocation_evidence: str | None = None, require_evidence: bool = True) -> tuple[str, ...]:
    errors = []
    if not isinstance(metadata, dict):
        return ("metadata-object",)
    optional = {"natureza", "fase", "resultou_em", "manifestacoes_url"}
    errors.extend(f"missing:{key}" for key in FIELDS if key not in metadata)
    errors.extend(f"unknown:{key}" for key in metadata if key not in set(FIELDS) | optional)
    if errors:
        return tuple(errors)
    if metadata["schema_versao"] != "1.0":
        errors.append("schema-version")
    for key in ("id", "tipo", "titulo", "orgao", "fonte"):
        if not isinstance(metadata[key], str) or not metadata[key].strip():
            errors.append(f"string:{key}")
    for key in ("unidade", "numero", "publicacao", "edicao", "ementa"):
        if metadata[key] is not None and (not isinstance(metadata[key], str) or not metadata[key].strip()):
            errors.append(f"nullable-string:{key}")
    for key in ("data", "data_publicacao"):
        if metadata[key] is not None and not valid_date(metadata[key]):
            errors.append(f"date:{key}")
    if not valid_date(metadata["baixado_em"]):
        errors.append("date:baixado_em")
    kind = metadata["tipo"]
    if not isinstance(kind, str) or kind not in TYPES or metadata["classe"] != TYPES[kind][0]:
        errors.append("class-type")
    else:
        try:
            expected = confirmed_id(kind, metadata["numero"], metadata["data"], metadata["unidade"])
            if metadata["id"] != expected:
                errors.append("identity")
        except (ValueError, TypeError):
            errors.append("unconfirmed-identity")
    if metadata["revogada"] is not None and type(metadata["revogada"]) is not bool:
        errors.append("revocation-type")
    if require_evidence and metadata["revogada"] is not None and not revocation_evidence:
        errors.append("revocation-evidence")
    if metadata["versao_texto"] not in VERSIONS:
        errors.append("text-version")
    if not valid_url(metadata["fonte"]):
        errors.append("source-url")
    if metadata["fonte_cvm"] is not None and not valid_url(metadata["fonte_cvm"]):
        errors.append("page-url")
    if not valid_hash(metadata["sha256_fonte"]):
        errors.append("source-hash")
    if metadata["formato_fonte"] not in ("html", "pdf", "docx", "doc"):
        errors.append("source-format")
    if type(metadata["ocr"]) is not bool:
        errors.append("ocr-type")
    if metadata["ocr"] is True and metadata["formato_fonte"] != "pdf":
        errors.append("ocr-source-format")
    organization = metadata["orgao"]
    if isinstance(organization, str) and "Comissão de Valores Mobiliários" not in organization.split(" / "):
        errors.append("organization")
    for key in ("revogada_por", "alterada_por", "resultou_em"):
        if key not in metadata:
            continue
        relations = metadata[key]
        if not isinstance(relations, list):
            errors.append(f"relations:{key}")
            continue
        for relation in relations:
            if not isinstance(relation, dict) or set(relation) != {"id", "titulo", "url", "contexto"}:
                errors.append(f"relation-schema:{key}")
                continue
            if (relation["id"] is not None and not isinstance(relation["id"], str) or
                    not valid_url(relation["url"]) or
                    any(not isinstance(relation[name], str) or not relation[name].strip() for name in ("titulo", "contexto"))):
                errors.append(f"relation-value:{key}")
    annexes = metadata["anexos"]
    if not isinstance(annexes, list):
        errors.append("annexes")
    else:
        for annex in annexes:
            if not isinstance(annex, dict) or set(annex) != {"rotulo", "url", "sha256", "formato"}:
                errors.append("annex-schema")
                continue
            if (not isinstance(annex["rotulo"], str) or not annex["rotulo"].strip() or
                    not valid_url(annex["url"]) or not valid_hash(annex["sha256"]) or
                    annex["formato"] not in ("html", "pdf", "docx", "doc", "xlsx")):
                errors.append("annex-value")
    if metadata["classe"] == "orientação":
        if "natureza" not in metadata or metadata["natureza"] not in (None, "determinação"):
            errors.append("orientation-nature")
    elif "natureza" in metadata:
        errors.append("unexpected-nature")
    if metadata["classe"] == "minuta":
        if metadata.get("fase") not in ("aberta", "em análise", "norma publicada", "encerrada sem norma"):
            errors.append("consultation-phase")
        if "resultou_em" not in metadata or "manifestacoes_url" not in metadata:
            errors.append("consultation-fields")
        if metadata.get("manifestacoes_url") is not None and not valid_url(metadata["manifestacoes_url"]):
            errors.append("submissions-url")
    elif any(key in metadata for key in ("fase", "resultou_em", "manifestacoes_url")):
        errors.append("unexpected-consultation-fields")
    if artifact is not None:
        if metadata["fonte"] != artifact.url:
            errors.append("artifact-url")
        if metadata["sha256_fonte"] != hashlib.sha256(artifact.bytes).hexdigest():
            errors.append("artifact-hash")
        if metadata["baixado_em"] != artifact.fetched_at[:10]:
            errors.append("artifact-date")
    return tuple(dict.fromkeys(errors))
