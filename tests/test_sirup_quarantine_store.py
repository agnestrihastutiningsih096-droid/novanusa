import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from scripts.sirup_quarantine_store import (
    append_quarantine_record, build_quarantine_record, canonical_json_bytes,
    count_quarantine_records, read_quarantine_record,
)


class QuarantineStoreTests(unittest.TestCase):
    def make_record(self, **changes):
        values = dict(
            run_id="run-1", page_start=100, requested_length=10, page_draw=2,
            row_index=3, raw_row={"id": 42, "name": "Paket"},
            missing_fields=["z", "a", "z"], invalid_fields=["b", "b"],
            validation_error="invalid row", captured_at="2026-08-05T00:00:00Z",
            payload_sha256="a" * 64, request_parameters={"start": 100},
            failure_evidence_path="evidence/page.json",
        )
        values.update(changes)
        return build_quarantine_record(**values)

    def assert_record_rejected(self, record):
        with TemporaryDirectory() as temporary:
            path = Path(temporary, "record.json")
            try:
                path.write_bytes(canonical_json_bytes(record) + b"\n")
            except (TypeError, ValueError):
                with self.assertRaises((TypeError, ValueError)):
                    append_quarantine_record(Path(temporary, "store"), record)
            else:
                with self.assertRaises(ValueError):
                    read_quarantine_record(path)

    def test_deterministic_identity_and_content_digest(self):
        first = self.make_record()
        second = self.make_record()
        identity = {"identity_version": 1, "run_id": "run-1",
                    "page_start": 100, "row_index": 3,
                    "payload_sha256": "a" * 64}
        self.assertEqual(first["quarantine_record_id"], hashlib.sha256(
            canonical_json_bytes(identity)).hexdigest())
        self.assertEqual(first, second)
        content = {k: v for k, v in first.items() if k != "content_sha256"}
        self.assertEqual(first["content_sha256"], hashlib.sha256(
            canonical_json_bytes(content)).hexdigest())

    def test_fields_offset_and_package_id(self):
        record = self.make_record()
        self.assertEqual(record["missing_fields"], ["a", "z"])
        self.assertEqual(record["invalid_fields"], ["b"])
        self.assertEqual(record["source_offset"], 103)
        self.assertEqual(record["package_id"], 42)
        self.assertIsNone(self.make_record(raw_row={})["package_id"])

    def test_append_replay_and_conflict_never_overwrites(self):
        with TemporaryDirectory() as temporary:
            record = self.make_record()
            self.assertEqual(append_quarantine_record(temporary, record), "created")
            target = Path(temporary, record["quarantine_record_id"] + ".json")
            original = target.read_bytes()
            modified = target.stat().st_mtime_ns
            temp = Path(temporary, "." + record["quarantine_record_id"] +
                        ".json.tmp")
            self.assertFalse(temp.exists())
            self.assertEqual(append_quarantine_record(temporary, record), "existing")
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target.stat().st_mtime_ns, modified)
            conflict = self.make_record(validation_error="another error")
            with self.assertRaisesRegex(RuntimeError, "quarantine record conflict"):
                append_quarantine_record(temporary, conflict)
            self.assertEqual(target.read_bytes(), original)

    def test_existing_malformed_final_is_conflict_without_overwrite(self):
        with TemporaryDirectory() as temporary:
            record = self.make_record()
            target = Path(temporary, record["quarantine_record_id"] + ".json")
            target.write_bytes(b"malformed\n")
            original = target.read_bytes()
            with self.assertRaisesRegex(RuntimeError, "quarantine record conflict"):
                append_quarantine_record(temporary, record)
            self.assertEqual(target.read_bytes(), original)

    def test_tampered_record_rejected(self):
        with TemporaryDirectory() as temporary:
            record = self.make_record()
            path = Path(temporary, "record.json")
            altered = dict(record, validation_error="tampered")
            path.write_text(json.dumps(altered), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_quarantine_record(path)

    def test_malformed_inputs_and_constraints_rejected(self):
        bad = [{"run_id": ""}, {"payload_sha256": "A" * 64},
               {"row_index": 10}, {"raw_row": []},
               {"missing_fields": [""]}]
        for change in bad:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.make_record(**change)
        with self.assertRaises((TypeError, ValueError)):
            canonical_json_bytes({"bad": object()})

    def test_direct_scalar_and_digest_invariants_rejected(self):
        cases = [
            ("version", {"quarantine_record_version": 2}),
            ("identity", {"quarantine_record_id": "0" * 64}),
            ("content digest", {"content_sha256": "0" * 64}),
            ("source offset", {"source_offset": 999}),
            ("package id", {"package_id": "wrong"}),
            ("request parameters", {"request_parameters": []}),
            ("failure evidence", {"failure_evidence_path": ""}),
            ("captured at", {"captured_at": ""}),
            ("validation error", {"validation_error": ""}),
        ]
        for name, changes in cases:
            with self.subTest(name=name):
                record = self.make_record()
                record.update(changes)
                self.assert_record_rejected(record)

    def test_page_identity_invariants_rejected(self):
        record = self.make_record()
        cases = []
        cases.append(("wrong type", []))
        missing = dict(record["page_identity"])
        missing.pop("page_draw")
        cases.append(("missing key", missing))
        extra = dict(record["page_identity"], extra="value")
        cases.append(("extra key", extra))
        mismatch = dict(record["page_identity"], page_start=101)
        cases.append(("value mismatch", mismatch))
        for name, page_identity in cases:
            with self.subTest(name=name):
                altered = dict(record, page_identity=page_identity)
                self.assert_record_rejected(altered)

    def test_stored_field_lists_must_be_sorted_and_unique(self):
        cases = [
            ("missing unsorted", "missing_fields", ["z", "a"]),
            ("missing duplicate", "missing_fields", ["a", "a"]),
            ("invalid unsorted", "invalid_fields", ["z", "a"]),
            ("invalid duplicate", "invalid_fields", ["a", "a"]),
        ]
        for name, field, value in cases:
            with self.subTest(name=name):
                record = self.make_record()
                record[field] = value
                self.assert_record_rejected(record)

    def test_nonserializable_record_rejected_before_append(self):
        with TemporaryDirectory() as temporary:
            store = Path(temporary, "store")
            record = self.make_record()
            record["raw_row"]["bad"] = object()
            with self.assertRaises((TypeError, ValueError)):
                append_quarantine_record(store, record)
            self.assertFalse(store.exists())

    def test_count_absent_valid_temporary_and_invalid_final(self):
        with TemporaryDirectory() as temporary:
            absent = Path(temporary, "absent")
            self.assertEqual(count_quarantine_records(absent), 0)
            absent.mkdir()
            first = self.make_record()
            second = self.make_record(row_index=4)
            append_quarantine_record(absent, first)
            append_quarantine_record(absent, second)
            (absent / ".ignored.json.tmp").write_text("bad", encoding="utf-8")
            self.assertEqual(count_quarantine_records(absent), 2)
            (absent / "invalid.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValueError):
                count_quarantine_records(absent)

    def test_atomic_finalization_failure_preserves_temp_and_existing_records(self):
        with TemporaryDirectory() as temporary:
            first = self.make_record()
            append_quarantine_record(temporary, first)
            existing = Path(temporary, first["quarantine_record_id"] + ".json")
            original = existing.read_bytes()
            second = self.make_record(row_index=4)
            with mock.patch("scripts.sirup_quarantine_store.os.link",
                            side_effect=OSError("injected failure")):
                with self.assertRaises(OSError):
                    append_quarantine_record(temporary, second)
            temp = Path(temporary, "." + second["quarantine_record_id"] +
                        ".json.tmp")
            self.assertTrue(temp.exists())
            self.assertEqual(existing.read_bytes(), original)
            self.assertFalse(Path(temporary,
                second["quarantine_record_id"] + ".json").exists())


if __name__ == "__main__":
    unittest.main()
