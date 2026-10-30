"""Official source discovery and document metadata."""

from .catalog import (
    CatalogCountError,
    CatalogError,
    CatalogLoopError,
    UnsupportedCategoryError,
    catalog_url,
    enumerate_catalog,
    parse_catalog,
)
from .document import DocumentConflictError, DocumentParseError, parse_document_page

__all__ = [
    "CatalogCountError",
    "CatalogError",
    "CatalogLoopError",
    "DocumentParseError",
    "DocumentConflictError",
    "UnsupportedCategoryError",
    "catalog_url",
    "enumerate_catalog",
    "parse_catalog",
    "parse_document_page",
]
