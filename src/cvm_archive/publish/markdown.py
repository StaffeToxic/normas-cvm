"""Emit schema 1.0 YAML using JSON flow values, without a runtime YAML dependency."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from cvm_archive.gates.fidelity import check_fidelity, check_html_structure, read_html_text
from cvm_archive.gates.metadata import FIELDS, TYPES, slug, validate_metadata
from cvm_archive.models import Artifact, Conversion


OCR_NOTICE = "> Texto obtido por OCR a partir de PDF sem camada de texto; pode conter erros de reconhecimento."


class PublicationError(ValueError):
    """One or more editorial gates rejected the proposed publication."""


def decode_html(artifact: Artifact) -> str:
    return decode_html_bytes(artifact.bytes, artifact.content_type)


def decode_html_bytes(data: bytes, content_type: str = "text/html") -> str:
    """Honor a declared charset; never replace undecodable normative bytes."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    header = re.search(r"charset\s*=\s*[\"']?([\w.-]+)", content_type, re.I)
    declaration = re.search(rb"charset\s*=\s*[\"']?([\w.-]+)", data[:8192], re.I)
    declared = header[1] if header else declaration[1].decode("ascii") if declaration else None
    if declared:
        try:
            return data.decode(declared)
        except (LookupError, UnicodeError) as exc:
            raise PublicationError("source-encoding") from exc
    for encoding in ("utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise PublicationError("source-encoding")


def check_identity(source_text: str, metadata: dict) -> tuple[str, ...]:
    errors = []
    pattern = (r"^" + re.escape(metadata["tipo"]) +
               r"\s+(?:CVM\s+)?(?:N[º°o.]?\s*)?0*(\d+)\b")
    epigraphs = [match[1] for line in source_text.splitlines()
                 if (match := re.match(pattern, line, re.I))]
    if epigraphs != [metadata["numero"]]:
        errors.append("artifact-identity")
    months = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
    for line in source_text.splitlines():
        if re.match(pattern, line, re.I):
            act_date = re.search(r"\bDE\s+(\d{1,2})\s+DE\s+(\w+)\s+DE\s+(\d{4})\b", line, re.I)
            if act_date:
                month = act_date[2].lower()
                if month not in months or metadata["data"] != f"{act_date[3]}-{months.index(month) + 1:02d}-{int(act_date[1]):02d}":
                    errors.append("artifact-act-date")
    return tuple(errors)


def embedded_annexes(source_text: str, source_url: str, source_hash: str, source_format: str) -> list[dict]:
    """An embedded annex points to the exact integral artifact containing it."""
    labels = [line.strip() for line in source_text.splitlines()
              if re.match(r"^ANEXO\s+(?:NORMATIVO\s+)?(?:[A-Z]+|\d+)\b", line.strip())]
    return [{"rotulo": label, "url": source_url, "sha256": source_hash, "formato": source_format} for label in labels]


def check_embedded_annexes(source_text: str, metadata: dict) -> tuple[str, ...]:
    expected = embedded_annexes(source_text, metadata["fonte"], metadata["sha256_fonte"], metadata["formato_fonte"])
    declared = [annex for annex in metadata["anexos"] if annex["url"] == metadata["fonte"]]
    return () if declared == expected else ("embedded-annex-provenance",)


def document_path(metadata: dict) -> str:
    """Use the official title slug only when that title includes its date."""
    year = metadata["data"][:4] if metadata["data"] else "sem-data"
    title_has_date = re.search(r"\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b", metadata["titulo"], re.I)
    stem = slug(metadata["titulo"]) if title_has_date else metadata["id"]
    if metadata["versao_texto"] == "consolidada":
        stem += ".consolidada"
    return str(PurePosixPath("reguladores", "cvm", TYPES[metadata["tipo"]][2], year, stem + ".md"))


def render_document(metadata: dict, artifact: Artifact, conversion: Conversion, *, discovered_annex_urls: tuple[str, ...] | None, revocation_evidence: str | None = None, source_html: str | None = None, annex_artifacts: tuple[Artifact, ...] = ()) -> bytes:
    errors = list(validate_metadata(metadata, artifact, revocation_evidence=revocation_evidence))
    if errors:
        raise PublicationError(", ".join(errors))
    if conversion.pending_reason:
        errors.append(conversion.pending_reason)
    body = conversion.markdown
    if metadata.get("ocr") is True:
        if not body.startswith(OCR_NOTICE + "\n"):
            errors.append("ocr-notice")
        else:
            body = body[len(OCR_NOTICE):].lstrip("\n")
    errors.extend(check_fidelity(conversion.source_text, body))
    if metadata.get("formato_fonte") == "html":
        exact_source = decode_html(artifact)
        if source_html is not None and exact_source != source_html:
            errors.append("source-text-does-not-match-artifact")
        errors.extend(check_html_structure(exact_source, body, artifact.url))
        errors.extend(check_embedded_annexes(read_html_text(exact_source), metadata))
    errors.extend(check_identity(conversion.source_text, metadata))
    if discovered_annex_urls is None:
        errors.append("annex-discovery-unverified")
    elif isinstance(metadata.get("anexos"), list):
        declared = [annex.get("url") for annex in metadata["anexos"] if isinstance(annex, dict)]
        if sorted(declared) != sorted(discovered_annex_urls):
            errors.append("missing-annex-provenance")
    artifacts = {item.url: item for item in (artifact, *annex_artifacts)}
    for annex in metadata["anexos"]:
        source = artifacts.get(annex["url"])
        if source is None or annex["sha256"] != source.sha256:
            errors.append("annex-artifact-provenance")
    if errors:
        raise PublicationError(", ".join(dict.fromkeys(errors)))
    header = ["---"]
    for key in (*FIELDS, "natureza", "fase", "resultou_em", "manifestacoes_url"):
        if key in metadata:
            header.append(f"{key}: {json.dumps(metadata[key], ensure_ascii=False)}")
    header.extend(("---", f'# {metadata["titulo"]}', "", conversion.markdown.rstrip(), ""))
    text = "\n".join(header)
    if "\r" in text or any(line.rstrip() != line for line in text.splitlines()):
        raise PublicationError("noncanonical-whitespace")
    return text.encode("utf-8")


def parse_document(data: bytes) -> tuple[dict, str]:
    """Read the emitted YAML profile; reject unsupported edits conservatively."""
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n"):
        raise PublicationError("document-encoding")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicationError("document-encoding") from exc
    if not text.startswith("---\n"):
        raise PublicationError("front-matter-delimiter")
    header, separator, rest = text[4:].partition("\n---\n")
    if not separator:
        raise PublicationError("front-matter-delimiter")
    metadata = {}
    for line in header.splitlines():
        key, colon, value = line.partition(": ")
        if not colon or key in metadata:
            raise PublicationError("front-matter-key")
        try:
            metadata[key] = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PublicationError("unsupported-yaml-value") from exc
    if rest.startswith(f'# {metadata.get("titulo")}\n\n'):
        body = rest.split("\n\n", 1)[1]
    else:
        raise PublicationError("document-heading")
    if not body.strip():
        raise PublicationError("empty-content")
    return metadata, body
