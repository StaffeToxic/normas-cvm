"""Provenance records preserve bytes and reject altered source digests."""

import hashlib
import unittest
from dataclasses import FrozenInstanceError, replace

from cvm_archive.models import Artifact, CatalogEntry, Conversion


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.payload = b"\xef\xbb\xbfArt. 1\xc2\xba\r\n"
        self.artifact = Artifact.from_bytes(
            "https://conteudo.cvm.gov.br/example.htm",
            self.payload,
            "text/html; charset=utf-8",
            "2026-10-22T01:00:00Z",
        )

    def test_exact_bytes_include_bom_and_line_endings(self):
        self.assertEqual(self.artifact.bytes, self.payload)
        self.assertEqual(self.artifact.sha256, hashlib.sha256(self.payload).hexdigest())
        normalized = self.payload.decode("utf-8-sig").replace("\r\n", "\n").encode()
        self.assertNotEqual(self.artifact.sha256, hashlib.sha256(normalized).hexdigest())

    def test_mutated_byte_cannot_reuse_digest(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            replace(self.artifact, bytes=self.payload + b" ")

    def test_digest_cannot_be_output_digest(self):
        with self.assertRaisesRegex(ValueError, "digest"):
            replace(self.artifact, sha256=hashlib.sha256(b"**Art. 1**").hexdigest())

    def test_artifact_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.artifact.url = "https://example.org/other"

    def test_collection_time_requires_utc(self):
        with self.assertRaises(ValueError):
            replace(self.artifact, fetched_at="2026-10-22T01:00:00")
        with self.assertRaises(ValueError):
            replace(self.artifact, fetched_at="2026-10-22T01:00:00-03:00")


class CandidateTests(unittest.TestCase):
    def test_unknown_identity_is_not_invented(self):
        entry = CatalogEntry("https://example.org/manual", "Manual", "manuais", None, None)
        self.assertIsNone(entry.number)
        self.assertIsNone(entry.date)
        self.assertFalse(hasattr(entry, "id"))

    def test_invalid_calendar_date_is_rejected(self):
        with self.assertRaises(ValueError):
            CatalogEntry("https://example.org/act", "Act", "resolucoes", "1", "2026-02-30")

    def test_pending_conversion_remains_a_candidate(self):
        conversion = Conversion("source", "candidate", pending_reason="revisao-manual")
        self.assertEqual(conversion.pending_reason, "revisao-manual")
        self.assertFalse(hasattr(conversion, "published"))


if __name__ == "__main__":
    unittest.main()
