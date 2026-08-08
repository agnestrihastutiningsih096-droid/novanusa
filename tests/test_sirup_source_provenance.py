import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sirup_source_provenance import (  # noqa: E402
    append_source_provenance_record,
    build_source_provenance_record,
    read_source_provenance_record,
    validate_source_provenance_record,
)


class SourceProvenanceTests(unittest.TestCase):
    def page_identity(self):
        return {
            "run_id": "run-2026",
            "page_start": 200,
            "requested_length": 100,
            "page_draw": 3,
            "payload_sha256": "a" * 64,
        }

    def record(self, disposition="canonical", raw_row=None):
        return build_source_provenance_record(
            self.page_identity(), 7, disposition,
            {"id": 42, "paket": "jalan"} if raw_row is None else raw_row,
            "2026-08-09T00:00:00+00:00",
        )

    def test_construction_and_fingerprints_are_deterministic(self):
        first = self.record()
        second = self.record()
        self.assertEqual(first, second)
        self.assertEqual(207, first["source_offset"])
        self.assertEqual(first["provenance_record_id"], second["provenance_record_id"])
        self.assertEqual(first["row_sha256"], second["row_sha256"])
        self.assertEqual(first["content_sha256"], second["content_sha256"])

    def test_negative_and_bool_positions_are_rejected(self):
        for field, value in (("page_start", -1), ("row_index", -1),
                             ("page_start", True), ("row_index", False)):
            identity = self.page_identity()
            row_index = 7
            if field == "page_start":
                identity[field] = value
            else:
                row_index = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                ValueError, "non-negative integer"
            ):
                build_source_provenance_record(
                    identity, row_index, "canonical", {"id": 1}, "now"
                )

    def test_disposition_is_closed_and_both_values_are_supported(self):
        self.assertEqual("canonical", self.record("canonical")["disposition"])
        self.assertEqual("quarantine", self.record("quarantine")["disposition"])
        with self.assertRaisesRegex(ValueError, "disposition"):
            self.record("discarded")

    def test_page_identity_and_payload_mismatch_are_rejected(self):
        for mutation, message in (
            (lambda record: record["page_identity"].update(page_start=201), "page_identity"),
            (lambda record: record.update(payload_sha256="b" * 64), "page_identity"),
        ):
            record = self.record()
            mutation(record)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                validate_source_provenance_record(record)

    def test_invalid_payload_hash_is_rejected(self):
        identity = self.page_identity()
        identity["payload_sha256"] = "invalid"
        with self.assertRaisesRegex(ValueError, "payload_sha256"):
            build_source_provenance_record(identity, 0, "canonical", {"id": 1}, "now")

    def test_first_append_and_identical_replay_are_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory) / "provenance"
            record = self.record()
            self.assertEqual("created", append_source_provenance_record(directory, record))
            self.assertEqual("existing", append_source_provenance_record(directory, record))
            self.assertEqual(record, read_source_provenance_record(
                directory / f"{record['provenance_record_id']}.json"
            ))

    def test_same_position_with_different_content_fails_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            original = self.record(raw_row={"id": 42})
            conflict = self.record(raw_row={"id": 43})
            self.assertEqual(original["provenance_record_id"], conflict["provenance_record_id"])
            append_source_provenance_record(directory, original)
            target = directory / f"{original['provenance_record_id']}.json"
            before = target.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "conflict"):
                append_source_provenance_record(directory, conflict)
            self.assertEqual(before, target.read_bytes())

    def test_corrupt_existing_record_fails_closed_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            record = self.record()
            target = directory / f"{record['provenance_record_id']}.json"
            target.write_text("{partial", encoding="utf-8")
            before = target.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "conflict"):
                append_source_provenance_record(directory, record)
            self.assertEqual(before, target.read_bytes())

    def test_tampered_identity_and_content_fingerprint_are_rejected(self):
        for field in ("provenance_record_id", "content_sha256"):
            record = copy.deepcopy(self.record())
            record[field] = "b" * 64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "invalid"):
                validate_source_provenance_record(record)

    def test_module_has_no_duckdb_ordering_dependency(self):
        module_text = (Path(__file__).parents[1] / "scripts" /
                       "sirup_source_provenance.py").read_text(encoding="utf-8")
        self.assertNotIn("duckdb", module_text.lower())
        self.assertNotIn("rowid", module_text.lower())


if __name__ == "__main__":
    unittest.main()
