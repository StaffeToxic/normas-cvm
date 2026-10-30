"""Text normalization used by the converters before publication."""

from cvm_archive.normalize.text import (
    BlockKind,
    bold_device_markers,
    classify_block,
    collapse_whitespace,
    heading_level,
    join_hyphenated_lines,
    normalize_heading,
    normalize_paragraph,
)

__all__ = [
    "BlockKind",
    "bold_device_markers",
    "classify_block",
    "collapse_whitespace",
    "heading_level",
    "join_hyphenated_lines",
    "normalize_heading",
    "normalize_paragraph",
]
