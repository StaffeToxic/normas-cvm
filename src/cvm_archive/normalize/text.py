"""Editorial normalization shared by every converter.

The normalizer formats legal text, it never rewrites it.  It bolds the device
markers (``Art.``, ``§`` and ``Parágrafo único``), recognizes the structural
headings of the acts, escapes list-like markers so Markdown never renumbers a
legal item, and resolves a line-break hyphen only when the source proves it was
a soft hyphen.  URLs, codes and lexical hyphens are left untouched, because a
missing hyphen changes the legal text while a redundant one is only a visible
artifact.
"""

from __future__ import annotations

import re
import unicodedata
from enum import Enum

__all__ = [
    "BlockKind",
    "LEXICAL_HYPHEN_PREFIXES",
    "bold_device_markers",
    "classify_block",
    "collapse_whitespace",
    "device_marker",
    "escape_leading_list_marker",
    "heading_level",
    "join_hyphenated_lines",
    "normalize_heading",
    "normalize_paragraph",
]


class BlockKind(str, Enum):
    """Editorial role of a block of legal text."""

    HEADING = "heading"
    ANNEX = "annex"
    ARTICLE = "article"
    SECTION = "section"
    UNIQUE_PARAGRAPH = "unique_paragraph"
    ITEM = "item"
    SUBITEM = "subitem"
    PLAIN = "plain"


#: Roman numerals used as inciso markers in the official acts.
ROMAN_NUMERALS: tuple[str, ...] = (
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
    "XIII",
    "XIV",
    "XV",
    "XVI",
    "XVII",
    "XVIII",
    "XIX",
    "XX",
)

#: Left fragments whose hyphen is lexical in Brazilian legal Portuguese and is
#: therefore preserved instead of being joined.
LEXICAL_HYPHEN_PREFIXES: frozenset[str] = frozenset(
    {
        "anti",
        "auto",
        "contra",
        "e",
        "hífen",
        "inter",
        "intra",
        "micro",
        "multi",
        "off",
        "on",
        "pós",
        "pré",
        "self",
        "semi",
        "sub",
        "super",
        "ultra",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")
_NON_BREAKING_SPACE = "\u00a0"

_ARTICLE_MARKER_RE = re.compile(r"^Art\.\s*(?:\d+[º°]?|[IVXLCDM]+)\.?(?=\s|$)")
_SECTION_MARKER_RE = re.compile(r"^§\s*(?:\d+[º°]?)?\.?(?=\s|$)")
_UNIQUE_PARAGRAPH_MARKER_RE = re.compile(
    r"^Par[áa]grafo\s+[úu]nico\.?(?=\s|$)", re.IGNORECASE
)
_DEVICE_MARKER_RE = re.compile(
    r"^(?:"
    r"Art\.\s*(?:\d+[º°]?|[IVXLCDM]+)\.?"
    r"|§\s*(?:\d+[º°]?)?\.?"
    r"|Par[áa]grafo\s+[úu]nico\.?"
    r")"
)

_ROMAN_ALTERNATION = "|".join(ROMAN_NUMERALS)
_ITEM_MARKER_RE = re.compile(rf"^(?:{_ROMAN_ALTERNATION})(?:\s*[-–—])\s")
_SUBITEM_MARKER_RE = re.compile(r"^[a-z]\)\s")

_HEADING_RE = re.compile(
    r"^(?P<kind>T[ÍI]TULO|CAP[ÍI]TULO|SUBSE[ÇC][ÃA]O|SE[ÇC][ÃA]O)"
    r"\s+(?P<number>[IVXLCDM]+|\d+)\b",
    re.IGNORECASE,
)
_ANNEX_RE = re.compile(r"^ANEXO\s+(?P<label>[IVXLCDM]+|[A-Z]|\d+)\b")

_LIST_MARKER_RE = re.compile(r"^(?P<marker>\d+[.)]|[*+-])(?=\s)")
_URL_TOKEN_RE = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.)\S+", re.IGNORECASE)

_HEADING_LEVELS = {"TITULO": 2, "CAPITULO": 3, "SECAO": 4, "SUBSECAO": 5}


def collapse_whitespace(text: str) -> str:
    """Collapse every whitespace run into a single space and trim the result."""

    return _WHITESPACE_RE.sub(" ", text.replace(_NON_BREAKING_SPACE, " ")).strip()


def classify_block(text: str) -> BlockKind:
    """Return the editorial role of a block of legal text."""

    collapsed = collapse_whitespace(text)
    if not collapsed:
        return BlockKind.PLAIN
    if _ANNEX_RE.match(collapsed):
        return BlockKind.ANNEX
    if _HEADING_RE.match(collapsed):
        return BlockKind.HEADING
    if _ARTICLE_MARKER_RE.match(collapsed):
        return BlockKind.ARTICLE
    if _SECTION_MARKER_RE.match(collapsed):
        return BlockKind.SECTION
    if _UNIQUE_PARAGRAPH_MARKER_RE.match(collapsed):
        return BlockKind.UNIQUE_PARAGRAPH
    if _ITEM_MARKER_RE.match(collapsed):
        return BlockKind.ITEM
    if _SUBITEM_MARKER_RE.match(collapsed):
        return BlockKind.SUBITEM
    return BlockKind.PLAIN


def heading_level(text: str) -> int | None:
    """Return the Markdown level of a structural heading, or ``None``."""

    collapsed = collapse_whitespace(text)
    kind = classify_block(collapsed)
    if kind is BlockKind.ANNEX:
        return 2
    if kind is not BlockKind.HEADING:
        return None
    match = _HEADING_RE.match(collapsed)
    if match is None:
        return None
    key = unicodedata.normalize("NFD", match.group("kind").upper())
    return _HEADING_LEVELS["".join(c for c in key if not unicodedata.combining(c))]


def device_marker(text: str) -> str | None:
    """Return the device marker that opens a block, if the block has one."""

    collapsed = collapse_whitespace(text)
    for pattern in (
        _ARTICLE_MARKER_RE,
        _SECTION_MARKER_RE,
        _UNIQUE_PARAGRAPH_MARKER_RE,
    ):
        match = pattern.match(collapsed)
        if match:
            return match.group(0)
    return None


def bold_device_markers(text: str) -> str:
    """Bold the device marker that opens a block, if there is one.

    The marker is reproduced exactly as the source wrote it; no point or
    ordinal is invented and the remaining text is not touched.
    """

    collapsed = collapse_whitespace(text)
    marker = device_marker(collapsed)
    if marker is None:
        return collapsed
    return f"**{marker}**{collapsed[len(marker):]}"


def normalize_paragraph(text: str) -> str:
    """Format a paragraph of legal text for Markdown."""

    return escape_leading_list_marker(bold_device_markers(text))


def escape_leading_list_marker(text: str) -> str:
    """Escape a leading Markdown list marker so legal numbering is literal."""

    match = _LIST_MARKER_RE.match(text)
    if match is None:
        return text
    marker = match.group("marker")
    if marker[0].isdigit():
        escaped = f"{marker[:-1]}\\{marker[-1]}"
    else:
        escaped = f"\\{marker}"
    return escaped + text[len(marker):]


def normalize_heading(text: str) -> str:
    """Format a structural heading for Markdown, keeping its own wording."""

    return collapse_whitespace(text)


def join_hyphenated_lines(text: str) -> str:
    """Join words split by a line-break hyphen when the source allows it.

    A hyphen is removed only when the fragment before it is a plain word, the
    next line starts with a lowercase letter and neither side belongs to a URL
    or to a code.  Lexical compounds listed in ``LEXICAL_HYPHEN_PREFIXES`` keep
    their hyphen, because removing it would change the legal text.
    """

    joined: list[str] = []
    for line in text.split("\n"):
        if joined and _can_join_hyphen(joined[-1], line):
            joined[-1] = joined[-1][:-1] + line.lstrip()
        else:
            joined.append(line)
    return "\n".join(joined)


def _can_join_hyphen(previous: str, following: str) -> bool:
    """Decide whether the trailing hyphen of ``previous`` was a soft hyphen."""

    if not previous.endswith("-") or not following[:1].islower():
        return False
    if previous.endswith(" -"):
        return False
    if _URL_TOKEN_RE.search(previous) or "/" in previous:
        return False
    fragment = previous[:-1]
    if not fragment:
        return False
    word = fragment.rsplit(" ", 1)[-1]
    if not word.isalpha() or any(character.isdigit() for character in fragment):
        return False
    if word.lower() in LEXICAL_HYPHEN_PREFIXES:
        return False
    return True
