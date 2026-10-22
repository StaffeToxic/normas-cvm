<!--
Sync Impact Report
- Version change: template → 1.0.0 (first ratification)
- Principles defined: I. Official Source Prevails; II. Text Fidelity; III. Polite Collection;
  IV. Executed Verification; V. Stable, Versioned Format; VI. Simplicity
- Added sections: Scope and Rights; Development Workflow; Governance
- Removed sections: none
- Templates:
  - ✅ .specify/templates/plan-template.md — "Constitution Check" is generic and reads gates from this file; no edit needed.
  - ✅ .specify/templates/spec-template.md — no mandatory section conflicts.
  - ⚠ .specify/templates/tasks-template.md — states tests are OPTIONAL. This conflicts with Principle IV.
    The template is NOT edited (Spec Kit overwrites templates on upgrade); this constitution prevails
    by the Precedence rule: every user story in tasks.md MUST include test tasks.
  - ✅ .claude/skills/speckit-*/SKILL.md — generic, no agent-specific references to fix.
  - ✅ README.md — consistent with Principles I, II and Scope and Rights.
- Deferred TODOs: none
-->

# normas-cvm Constitution

## Core Principles

### I. Official Source Prevails (NON-NEGOTIABLE)

Every published document MUST record its provenance: official URL (`fonte`), CVM page URL when
different (`fonte_cvm`), SHA-256 of the exact bytes converted (`sha256_fonte`) and collection date
(`baixado_em`). Metadata MUST come from the official source; a value that the source does not state
is `null`, never inferred. `revogada` is `true` or `false` only with explicit evidence on the
official page; otherwise `null`. Relations `alterada_por`/`revogada_por` record only links found on
the source, with their context. When two official pages disagree, both statements are kept and the
divergence is reported; the collector never picks one silently.

Rationale: the archive is used to answer "which rule applies"; an invented field is worse than a
missing one.

### II. Text Fidelity (NON-NEGOTIABLE)

Conversion MUST NOT drop, merge, reorder or rewrite normative content. Each document passes
editorial gates comparing the converted text with the source (token sequence, count of articles,
paragraphs, items and annexes) before it is published; a failed gate becomes an explicit pending
item, never a silent publication. Tables are published as real tables (Markdown or HTML `<table>`)
or not at all; flattened table text is forbidden. Text produced by OCR carries a visible notice.
Hyphen joining preserves URLs, codes and lexical hyphens. Original and consolidated versions are
distinct files.

Rationale: the main requirement of this project is a correct, clean `.md`.

### III. Polite Collection

The collector MUST respect `robots.txt` of every host, send one request at a time per host with a
minimum interval, identify itself in the User-Agent with a link to this repository, back off on
401/403/429/5xx and stop instead of bypassing any block. It MUST NOT call `dados.cvm.gov.br/api/`
(disallowed by robots). Raw downloads are cached and re-checked by hash, so unchanged documents are
not converted again.

### IV. Executed Verification (NON-NEGOTIABLE)

Nothing is "done" without verification that was actually executed and whose output is shown:
tests, a real collection run or a build. Every user story ships with tests. Converters are tested
against versioned fixtures of real CVM documents with expected `.md` output. A new gate is accepted
only after it is shown to fail on a deliberately corrupted input. A green result on a dirty working
tree does not count: verification runs on the committed state. Whatever could not be verified is
reported as UNVERIFIED.

### V. Stable, Versioned Format

One `.md` per document under `reguladores/cvm/<tipo>/<ano>/`, UTF-8 with LF line endings, YAML
front matter followed by `# Título` and the body. The front matter schema is versioned: adding an
optional field is MINOR, renaming, removing or changing the meaning of a field is MAJOR and needs a
migration note. Collection commits carry the real collection date; dates of the act live in the
front matter. History is never rewritten on published branches.

### VI. Simplicity

Python with the standard library plus Poppler is the default toolchain. Any new dependency (for
example a layout model for tables) MUST be justified by a measured gain on real documents recorded
in the feature research. No speculative abstraction, no service or database until a feature needs
one.

## Scope and Rights

- In scope: resolutions, instructions, deliberations, guidance opinions, joint decisions and
  portarias with external normative effect (`norma`); circular letters, explanatory notes, Q&A,
  manuals and guides (`orientação`); public hearings and consultations (`minuta`).
- Out of scope: administrative portarias, Collegiate decisions and sanctioning proceedings,
  federal laws and decrees, CPC/ICPC/OCPC pronouncement texts (phase 2), participant submissions
  to public hearings (linked only, never copied).
- Official normative texts are not protected by copyright (Lei 9.610/1998, art. 8º, IV).
  Annexes and third-party materials keep their rights; their status is recorded per artifact.
- Personal data is not republished.
- Code derived from third-party MIT software keeps its copyright notice in the file header and is
  listed in `THIRD_PARTY_NOTICES.md`. Third-party projects are not mentioned elsewhere.

## Development Workflow

- Spec Kit drives every feature: spec, plan and tasks in `specs/NNN-*/` before code.
- Code, identifiers, comments and commit messages in English; specs and documentation in
  Brazilian Portuguese.
- Conventional Commits; work happens on feature branches; `main` receives only reviewed merges.
- Irreversible operations (force push, history rewrite of a published branch, deletion of
  published data) require explicit maintainer approval.
- Secrets never enter the repository.

## Governance

Precedence: explicit maintainer instruction > this constitution > feature artifacts (spec, plan,
tasks) > tool templates and defaults. Where a Spec Kit template conflicts with this constitution,
the constitution prevails and the conflict is recorded in the Sync Impact Report instead of editing
the template.

Amendments are made by editing this file with a Sync Impact Report, bumping the version
(MAJOR: principle removed or redefined; MINOR: principle or section added or materially expanded;
PATCH: wording) and checking the dependent templates. Every plan runs the Constitution Check; a
NON-NEGOTIABLE principle that fails blocks delivery. A feature cannot amend the constitution as part
of its own deliverable.

**Version**: 1.0.0 | **Ratified**: 2026-10-22 | **Last Amended**: 2026-10-22
