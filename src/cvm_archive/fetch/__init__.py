"""Polite fetching of official resources; the transport contract lives in fetch.client."""

from cvm_archive.fetch.client import (
    DEFAULT_USER_AGENT,
    BlockedError,
    FetchError,
    PoliteClient,
)

__all__ = ["DEFAULT_USER_AGENT", "BlockedError", "FetchError", "PoliteClient"]
