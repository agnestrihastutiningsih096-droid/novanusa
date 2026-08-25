import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sirup_receipt_chain as chain  # noqa: E402


TS = "2026-08-12T01:02:03.004Z"


class ReceiptChainTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.run = Path(self.temporary.name) / "run-1"
        self.run.mkdir()
        self.database = self.run / chain.DATABASE_NAME
        self.database.write_bytes(b"candidate")
        self.digest = hashlib.sha256(b"candidate").hexdigest()

    def tearDown(self):
        self.temporary.cleanup()

    def anchor(self):
        return {
            "endpoint": "https://example.invalid/source", "year": 2026,
            "page_size": 2, "order_column": 11, "order_direction": "desc",
            "full_snapshot": True, "mode": "strict",
        }

    def page(self, start=0, returned=2, source=2):
        return {
            "start": start, "page_size": 2, "returned_row_count": returned,
            "canonical_row_count": returned, "quarantined_row_count": 0,
            "page_rows_digest": hashlib.sha256(f"page-{start}".encode()).hexdigest(),
            "source_count_observed": source,
        }

    def completion(self, processed=2, source=2):
        return {
            "terminal_reason": "NORMAL_COMPLETION", "processed": processed,
            "canonical_total": processed, "quarantine_total": 0,
            "source_count_start": source, "source_count_end": source,
            "drift_status": "NO_DRIFT", "duckdb_sha256": self.digest,
            "promotion_flag": False,
        }

    def abort(self):
        return {
            "terminal_reason": "FIRST_PAGE_ALL_ATTEMPTS_FAILED",
            "error_class": "Timeout", "failure_stage": "FETCH_PAGE",
            "processed": 0, "canonical_total": 0, "quarantined_total": 0,
            "duckdb_sha256": self.digest,
        }

    def build_complete(self, retry=False):
        with chain.ReceiptWriter(self.run) as writer:
            receipts = [writer.append("ANCHOR", self.anchor(), timestamp=TS)]
            if retry:
                receipts.append(writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS))
            receipts.append(writer.append("PAGE", self.page(), timestamp=TS))
            receipts.append(writer.append("COMPLETION", self.completion(), timestamp=TS))
        return receipts

    def rewrite(self, mutate, *, canonical=True, newline=True):
        receipts = [json.loads(line) for line in (self.run / chain.RECEIPTS_NAME).read_text().splitlines()]
        mutate(receipts)
        if canonical:
            text = "\n".join(chain.canonical_json(item) for item in receipts)
        else:
            text = "\n".join(json.dumps(item, sort_keys=False) for item in receipts)
        (self.run / chain.RECEIPTS_NAME).write_text(text + ("\n" if newline else ""), encoding="utf-8")

    @staticmethod
    def resign(receipt):
        receipt["hash"] = chain._receipt_hash(
            {key: receipt[key] for key in chain.HASH_FIELDS}
        )

    def resign_chain(self, receipts, start=0):
        for index in range(start, len(receipts)):
            if index:
                receipts[index]["previous_hash"] = receipts[index - 1]["hash"]
            self.resign(receipts[index])

    def verify(self, **kwargs):
        return chain.verify_receipt_chain(self.run, **kwargs)

    def test_genesis_derivation_and_literal_format(self):
        self.assertEqual(hashlib.sha256(chain.GENESIS_DERIVATION.encode("utf-8")).hexdigest(), chain.GENESIS_PREVIOUS_HASH)
        self.assertRegex(chain.GENESIS_PREVIOUS_HASH, r"^[0-9a-f]{64}$")
        self.assertNotEqual("0" * 64, chain.GENESIS_PREVIOUS_HASH)

    def test_anchor_sequence_genesis_and_rejects_source_count(self):
        other = Path(self.temporary.name) / "bad-anchor"; other.mkdir()
        with chain.ReceiptWriter(other) as writer:
            bad = {**self.anchor(), "source_count_start": 2}
            with self.assertRaisesRegex(chain.ReceiptChainError, "payload fields"):
                writer.append("ANCHOR", bad, timestamp=TS)
        with chain.ReceiptWriter(self.run) as writer:
            receipt = writer.append("ANCHOR", self.anchor(), timestamp=TS)
            self.assertEqual(0, receipt["sequence"])
            self.assertEqual(chain.GENESIS_PREVIOUS_HASH, receipt["previous_hash"])

    def test_canonicalization_is_deterministic_and_rejects_float(self):
        self.assertEqual('{"a":{"x":1},"b":2}', chain.canonical_json({"b": 2, "a": {"x": 1}}))
        with self.assertRaisesRegex(chain.ReceiptChainError, "floats"):
            chain.canonical_json({"value": 1.0})

    def test_timestamp_grammar_and_calendar(self):
        self.assertEqual(TS, chain.validate_timestamp(TS))
        for value in ("2026-08-12T01:02:03Z", "2026-08-12T01:02:03.004+00:00", "2026-02-30T01:02:03.004Z"):
            with self.assertRaises(chain.ReceiptChainError):
                chain.validate_timestamp(value)

    def test_all_receipt_types_sequence_linkage_and_terminal_rejection(self):
        with chain.ReceiptWriter(self.run) as writer:
            values = [writer.append("ANCHOR", self.anchor(), timestamp=TS)]
            values.append(writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS))
            values.append(writer.append("PAGE", self.page(), timestamp=TS))
            snapshot = {"source_rows_processed": 2, "next_start": 2, "last_completed_page": 1, "retries_used": 1}
            values.append(writer.append("RESUME", {"checkpoint_snapshot": snapshot, "processed": 2, "next_start": 2, "last_completed_page": 1, "retries": 1}, timestamp=TS))
            values.append(writer.append("COMPLETION", self.completion(), timestamp=TS))
            for index, receipt in enumerate(values):
                self.assertEqual(index, receipt["sequence"])
                if index:
                    self.assertEqual(values[index - 1]["hash"], receipt["previous_hash"])
            with self.assertRaisesRegex(chain.ReceiptChainError, "after terminal"):
                writer.append("PAGE", self.page(2), timestamp=TS)

    def test_page_requires_source_observation_and_completion_rejects_chain_head(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            bad_page = self.page(); del bad_page["source_count_observed"]
            with self.assertRaisesRegex(chain.ReceiptChainError, "payload fields"):
                writer.append("PAGE", bad_page, timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            bad_completion = {**self.completion(), "chain_head": "0" * 64}
            with self.assertRaisesRegex(chain.ReceiptChainError, "payload fields"):
                writer.append("COMPLETION", bad_completion, timestamp=TS)

    def test_abort_append_and_promotion_invalid(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            writer.append("ABORT", self.abort(), timestamp=TS)
        result = self.verify()
        self.assertTrue(result["valid"])
        self.assertFalse(result["promotion_valid"])

    def test_existing_history_appends_without_overwrite(self):
        with chain.ReceiptWriter(self.run) as writer:
            first = writer.append("ANCHOR", self.anchor(), timestamp=TS)
        before = (self.run / chain.RECEIPTS_NAME).read_bytes()
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("PAGE", self.page(), timestamp=TS)
        self.assertTrue((self.run / chain.RECEIPTS_NAME).read_bytes().startswith(before))
        self.assertEqual(first["hash"], json.loads(before)["hash"])

    def test_fsync_is_exercised(self):
        with mock.patch.object(chain.os, "fsync", wraps=os.fsync) as sync:
            with chain.ReceiptWriter(self.run) as writer:
                writer.append("ANCHOR", self.anchor(), timestamp=TS)
            sync.assert_called_once()

    def test_valid_complete_chain_and_manifest(self):
        receipts = self.build_complete(retry=True)
        manifest = {"run_id": self.run.name, "chain_head": receipts[-1]["hash"], "sha256": self.digest, "row_count": 2, "source_records_filtered": 2}
        result = self.verify(manifest=manifest, require_completion=True)
        self.assertTrue(result["valid"])
        self.assertTrue(result["promotion_valid"])
        self.assertEqual(1, result["retry_total"])

    def test_empty_missing_terminal_and_truncated(self):
        (self.run / chain.RECEIPTS_NAME).write_bytes(b"")
        self.assertIn("empty", self.verify()["failures"][0])
        (self.run / chain.RECEIPTS_NAME).unlink()
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
        self.assertIn("no terminal", self.verify()["failures"][0])
        path = self.run / chain.RECEIPTS_NAME
        path.write_bytes(path.read_bytes().rstrip(b"\n"))
        self.assertIn("truncated", self.verify()["failures"][0])

    def test_malformed_invalid_utf8_and_noncanonical(self):
        path = self.run / chain.RECEIPTS_NAME
        path.write_bytes(b"{bad}\n")
        self.assertIn("malformed", self.verify()["failures"][0])
        path.write_bytes(b"\xff\n")
        self.assertIn("UTF-8", self.verify()["failures"][0])
        path.unlink()
        self.build_complete()
        self.rewrite(lambda _r: None, canonical=False)
        self.assertIn("canonical", self.verify()["failures"][0])

    def test_unknown_field_and_float(self):
        self.build_complete()
        self.rewrite(lambda r: r[0].__setitem__("unknown", 1))
        self.assertIn("envelope fields", self.verify()["failures"][0])
        receipts = [json.loads(line) for line in (self.run / chain.RECEIPTS_NAME).read_text().splitlines()]
        receipts[0].pop("unknown", None); receipts[0]["payload"]["year"] = 2026.0
        (self.run / chain.RECEIPTS_NAME).write_text("\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in receipts) + "\n")
        self.assertIn("floats", self.verify()["failures"][0])

    def test_sequence_gap_duplicate_and_run_mismatch(self):
        for mutate, expected in (
            (lambda r: (r[1].__setitem__("sequence", 2), self.resign(r[1])), "sequence"),
            (lambda r: (r[1].__setitem__("sequence", 0), self.resign(r[1])), "sequence"),
            (lambda r: (r[1].__setitem__("run_id", "other"), self.resign(r[1])), "run_id"),
        ):
            (self.run / chain.RECEIPTS_NAME).unlink(missing_ok=True); self.build_complete(); self.rewrite(mutate)
            self.assertIn(expected, self.verify()["failures"][0])

    def test_previous_hash_hash_genesis_and_timestamp_corruption(self):
        cases = (
            (lambda r: (r[1].__setitem__("previous_hash", "0" * 64), self.resign(r[1])), "previous_hash"),
            (lambda r: r[1].__setitem__("hash", "0" * 64), "hash mismatch"),
            (lambda r: (r[0].__setitem__("previous_hash", "0" * 64), self.resign(r[0])), "previous_hash"),
            (lambda r: r[0].__setitem__("timestamp", "2026-08-12T01:02:03Z"), "timestamp"),
        )
        for mutate, expected in cases:
            (self.run / chain.RECEIPTS_NAME).unlink(missing_ok=True); self.build_complete(); self.rewrite(mutate)
            self.assertIn(expected, self.verify()["failures"][0])

    def test_duplicate_page_offset_and_page_accounting(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(0, 2, 4), timestamp=TS)
            writer.append("PAGE", self.page(2, 2, 4), timestamp=TS)
            writer.append("COMPLETION", self.completion(4, 4), timestamp=TS)
        self.rewrite(lambda r: (r[2]["payload"].__setitem__("start", 0), self.resign_chain(r, 2)))
        self.assertIn("duplicate", self.verify()["failures"][0])
        (self.run / chain.RECEIPTS_NAME).unlink();
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(0, 2, 4), timestamp=TS)
            writer.append("PAGE", self.page(2, 2, 4), timestamp=TS)
            writer.append("COMPLETION", self.completion(4, 4), timestamp=TS)
        self.rewrite(lambda r: (r[2]["payload"].__setitem__("start", 3), self.resign_chain(r, 2)))
        self.assertIn("discontinuity", self.verify()["failures"][0])
        # Writer rejects per-page accounting before persistence.
        other = Path(self.temporary.name) / "other"; other.mkdir()
        with chain.ReceiptWriter(other) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            bad = self.page(); bad["canonical_row_count"] = 1
            with self.assertRaisesRegex(chain.ReceiptChainError, "accounting"):
                writer.append("PAGE", bad, timestamp=TS)

    def test_retry_and_resume_accounting_mismatch(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 2}, timestamp=TS)
            writer.append("ABORT", self.abort(), timestamp=TS)
        self.assertIn("RETRY", self.verify()["failures"][0])
        (self.run / chain.RECEIPTS_NAME).unlink()
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            snapshot = {"source_rows_processed": 1, "next_start": 1, "last_completed_page": 1, "retries_used": 0}
            writer.append("RESUME", {"checkpoint_snapshot": snapshot, "processed": 2, "next_start": 2, "last_completed_page": 1, "retries": 0}, timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        self.assertIn("snapshot", self.verify()["failures"][0])

    def test_short_page_before_completion_and_global_accounting(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(0, 1, 4), timestamp=TS)
            writer.append("PAGE", self.page(2, 2, 4), timestamp=TS)
            writer.append("COMPLETION", self.completion(3, 4), timestamp=TS)
        self.assertIn("short PAGE", self.verify()["failures"][0])
        (self.run / chain.RECEIPTS_NAME).unlink(); self.build_complete()
        def corrupt(receipts):
            receipts[-1]["payload"]["processed"] = 3
            receipts[-1]["payload"]["canonical_total"] = 3
            self.resign_chain(receipts, len(receipts) - 1)
        self.rewrite(corrupt)
        self.assertIn("global accounting", self.verify()["failures"][0])

    def test_checkpoint_and_manifest_retry_mismatch(self):
        receipts = self.build_complete(retry=True)
        manifest = {"run_id": self.run.name, "chain_head": receipts[-1]["hash"], "sha256": self.digest, "row_count": 2, "source_records_filtered": 2, "retries_used": 0}
        self.assertIn("manifest accounting", self.verify(manifest=manifest)["failures"][0])

        (self.run / chain.RECEIPTS_NAME).unlink()
        snapshot = {"source_rows_processed": 0, "next_start": 0, "last_completed_page": 0, "retries_used": 0}
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RESUME", {"checkpoint_snapshot": snapshot, "processed": 0, "next_start": 0, "last_completed_page": 0, "retries": 0}, timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        different = {**snapshot, "next_start": 1}
        self.assertIn("checkpoint mismatch", self.verify(checkpoint=different)["failures"][0])

    def test_receipt_after_terminal_detected(self):
        self.build_complete()
        receipts = [json.loads(x) for x in (self.run / chain.RECEIPTS_NAME).read_text().splitlines()]
        extra = dict(receipts[1]); extra["sequence"] = 3; extra["previous_hash"] = receipts[-1]["hash"]
        preimage = {key: extra[key] for key in chain.HASH_FIELDS}; extra["hash"] = chain._receipt_hash(preimage)
        with (self.run / chain.RECEIPTS_NAME).open("a", encoding="utf-8") as handle:
            handle.write(chain.canonical_json(extra) + "\n")
        self.assertIn("after terminal", self.verify()["failures"][0])

    def test_manifest_chain_run_candidate_and_accounting_mismatches(self):
        receipts = self.build_complete()
        base = {"run_id": self.run.name, "chain_head": receipts[-1]["hash"], "sha256": self.digest, "row_count": 2, "source_records_filtered": 2}
        for change, expected in (
            ({"chain_head": "0" * 64}, "chain_head"),
            ({"run_id": "other"}, "run_id"),
            ({"row_count": 1}, "accounting"),
        ):
            self.assertIn(expected, self.verify(manifest={**base, **change})["failures"][0])
        self.database.write_bytes(b"swapped")
        self.assertIn("digest", self.verify(manifest=base)["failures"][0])

    def test_candidate_run_directory_mismatch(self):
        receipts = self.build_complete()
        renamed = self.run.with_name("other-run"); self.run.rename(renamed); self.run = renamed
        self.assertIn("run_id", self.verify()["failures"][0])

    def test_retry_after_page_rejected(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 999, "error_class": "LateFailure", "retry_index": 1}, timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        self.assertIn("RETRY prefix binding", self.verify()["failures"][0])

    def test_retry_page_size_mismatch_rejected(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 100, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        self.assertIn("following PAGE", self.verify()["failures"][0])

    def test_retry_start_mismatch_rejected(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            page = self.page(); page["start"] = 100
            writer.append("PAGE", page, timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        result = self.verify()
        self.assertFalse(result["valid"])
        self.assertIn("discontinuity", result["failures"][0])

    def test_retry_index_sequence_rejected(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 3}, timestamp=TS)
            writer.append("ABORT", self.abort(), timestamp=TS)
        self.assertIn("RETRY prefix binding", self.verify()["failures"][0])

    def test_valid_retry_sequence_accepted(self):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 2}, timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        result = self.verify(require_completion=True)
        self.assertTrue(result["valid"])
        self.assertEqual(2, result["retry_total"])

    def append_resume_chain(self, *, processed=2, next_start=2, pages=1, retries=0, prefix_retry=False):
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            if prefix_retry:
                writer.append("RETRY", {"start": 0, "page_size": 2, "error_class": "Timeout", "retry_index": 1}, timestamp=TS)
            if pages:
                writer.append("PAGE", self.page(), timestamp=TS)
            snapshot = {
                "source_rows_processed": processed, "next_start": next_start,
                "last_completed_page": pages, "retries_used": retries,
                "canonical_rows_collected": processed, "quarantine_rows": 0,
            }
            writer.append("RESUME", {"checkpoint_snapshot": snapshot, "processed": processed, "next_start": next_start, "last_completed_page": pages, "retries": retries}, timestamp=TS)
            if not pages:
                writer.append("PAGE", self.page(), timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        return snapshot

    def test_resume_fabricated_progress_rejected(self):
        snapshot = self.append_resume_chain(pages=0)
        self.assertIn("RESUME prefix", self.verify(checkpoint=snapshot)["failures"][0])

    def test_resume_prefix_match_accepted(self):
        snapshot = self.append_resume_chain()
        self.assertTrue(self.verify(checkpoint=snapshot, require_completion=True)["valid"])

    def test_resume_processed_mismatch_rejected(self):
        self.append_resume_chain(processed=3, next_start=3)
        self.assertIn("RESUME prefix", self.verify()["failures"][0])

    def test_resume_next_start_mismatch_rejected(self):
        self.append_resume_chain(next_start=3)
        self.assertIn("RESUME prefix", self.verify()["failures"][0])

    def test_resume_last_completed_page_mismatch_rejected(self):
        # Prefix contains one PAGE, while RESUME claims two.
        with chain.ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", self.anchor(), timestamp=TS)
            writer.append("PAGE", self.page(), timestamp=TS)
            snapshot = {"source_rows_processed": 2, "next_start": 2, "last_completed_page": 2, "retries_used": 0}
            writer.append("RESUME", {"checkpoint_snapshot": snapshot, "processed": 2, "next_start": 2, "last_completed_page": 2, "retries": 0}, timestamp=TS)
            writer.append("COMPLETION", self.completion(), timestamp=TS)
        self.assertIn("RESUME prefix", self.verify()["failures"][0])

    def test_resume_retry_count_mismatch_rejected(self):
        self.append_resume_chain(retries=0, prefix_retry=True)
        self.assertIn("RESUME prefix", self.verify()["failures"][0])


if __name__ == "__main__":
    unittest.main()
