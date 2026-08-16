from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import current_rup_sirup_adapter as adapter  # noqa: E402
from current_procurement_contracts import (  # noqa: E402
    CurrentPlannedProcurement, RawCurrentRupCandidate, SourceAvailability,
    SourceKind, SourceMaturity,
)
from sirup_receipt_chain import ReceiptWriter  # noqa: E402


class CurrentRupSirupAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.run = Path(self.temporary.name) / "run-2026"
        self.run.mkdir()
        self.database = self.run / adapter.DATABASE_NAME
        connection = duckdb.connect(str(self.database))
        connection.execute("""
            create table sirup_raw (
                id bigint not null primary key, id_referensi varchar, pagu double,
                satuanKerja varchar, kldi varchar, lokasi varchar,
                jenisPengadaan varchar, metode varchar, sumberDana varchar,
                paket varchar, pemilihan varchar, idBulan integer,
                idSatker bigint, idKldi varchar
            )
        """)
        connection.executemany(
            "insert into sirup_raw values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (20, "ref-20", 12.5, "Unit B", "KLDI B", "Jakarta", "Barang", "Tender", "APBN", "Package B", "March", 3, 9001, "  K-02  "),
                (10, "ref-10", 7.25, "Unit A", "KLDI A", "Bandung", "Jasa", "Seleksi", "APBD", "Package A", "April", 4, 42, "K-01"),
            ],
        )
        connection.close()
        self._write_evidence()

    def tearDown(self):
        self.temporary.cleanup()

    def _digest(self):
        return hashlib.sha256(self.database.read_bytes()).hexdigest()

    def _write_evidence(self):
        with ReceiptWriter(self.run) as writer:
            writer.append("ANCHOR", {"endpoint": "https://sirup.invalid", "year": 2026, "page_size": 2, "order_column": 11, "order_direction": "desc", "full_snapshot": True, "mode": "strict"}, timestamp="2026-08-17T01:00:00.000Z")
            writer.append("PAGE", {"start": 0, "page_size": 2, "returned_row_count": 2, "canonical_row_count": 2, "quarantined_row_count": 0, "page_rows_digest": "a" * 64, "source_count_observed": 2}, timestamp="2026-08-17T01:01:00.000Z")
            terminal = writer.append("COMPLETION", {"terminal_reason": "NORMAL_COMPLETION", "processed": 2, "canonical_total": 2, "quarantine_total": 0, "source_count_start": 2, "source_count_end": 2, "drift_status": "NO_DRIFT", "duckdb_sha256": self._digest(), "promotion_flag": False}, timestamp="2026-08-17T01:02:00.000Z")
        manifest = {
            "manifest_version": 1, "run_id": self.run.name,
            "status": "validated_staging_sample", "full_snapshot": True,
            "promotion_eligible": False, "database_path": str(self.database),
            "table_name": "sirup_raw", "requested_limit": 2, "row_count": 2,
            "distinct_id_count": 2, "min_id": 10, "max_id": 20,
            "sha256": self._digest(), "validation": {},
            "promotion": {"attempted": False, "result": "not_in_scope"},
            "source_records_filtered": 2, "retries_used": 0,
            "chain_head": terminal["hash"],
        }
        (self.run / adapter.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

    def test_exact_mapping_decimal_identity_and_deterministic_order(self):
        result = adapter.acquire(self.run)
        self.assertEqual(["10", "20"], [row.planned_procurement_id for row in result.candidates])
        row = result.candidates[1]
        self.assertEqual(("ref-20", "9001", "  K-02  "), (row.source_rup_id, row.id_satker, row.id_kldi))
        self.assertEqual(("Unit B", "KLDI B", "Package B"), (row.institution_name, row.kldi_name, row.package_title))
        self.assertEqual((Decimal("12.5"), "Barang", "Tender", "March", "Jakarta", 2026), (row.budget, row.procurement_type, row.procurement_method, row.selection_period, row.location, row.source_year))

    def test_provenance_is_bound_to_validated_evidence(self):
        result = adapter.acquire(self.run, limit=1)
        provenance = result.provenance
        self.assertIs(provenance.source_kind, SourceKind.CURRENT_SIRUP)
        self.assertIs(provenance.source_maturity, SourceMaturity.BOUNDED_ACQUISITION_VERIFIED)
        self.assertEqual((self.run.name, "2026-08-17T01:02:00.000Z", "1"), (provenance.acquisition_id, provenance.observed_at, provenance.schema_version))
        self.assertIn(str(self.database.resolve()), provenance.source_locator)
        self.assertEqual(64, len(provenance.raw_receipt_id))

    def test_is_partial_and_returns_only_raw_candidates(self):
        result = adapter.acquire(self.run, limit=1)
        self.assertIs(result.availability, SourceAvailability.SOURCE_PARTIAL)
        self.assertTrue(all(type(row) is RawCurrentRupCandidate for row in result.candidates))
        self.assertFalse(any(isinstance(row, CurrentPlannedProcurement) for row in result.candidates))
        self.assertIsNone(result.completeness_verification)

    def test_database_connection_is_read_only_and_database_is_unchanged(self):
        before = self.database.read_bytes()
        real_connect = duckdb.connect
        with mock.patch.object(adapter.duckdb, "connect", wraps=real_connect) as connect:
            adapter.acquire(self.run)
        self.assertTrue(any(call.kwargs == {"read_only": True} for call in connect.call_args_list))
        self.assertEqual(before, self.database.read_bytes())

    def test_mismatched_or_invalid_receipt_fails_closed(self):
        manifest_path = self.run / adapter.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["run_id"] = "other-run"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(adapter.CurrentRupSirupAdapterError):
            adapter.acquire(self.run)

    def test_missing_identity_value_fails_closed(self):
        connection = duckdb.connect(str(self.database))
        connection.execute("update sirup_raw set idKldi = null where id = 10")
        connection.close()
        self._replace_evidence_after_database_change()
        with self.assertRaisesRegex(adapter.CurrentRupSirupAdapterError, "identity fields"):
            adapter.acquire(self.run)

    def _replace_evidence_after_database_change(self):
        (self.run / "receipts.jsonl").unlink()
        (self.run / adapter.MANIFEST_NAME).unlink()
        self._write_evidence()

    def test_unexpected_schema_fails_closed(self):
        connection = duckdb.connect(str(self.database))
        connection.execute("alter table sirup_raw drop column idKldi")
        connection.close()
        self._replace_evidence_after_database_change()
        with self.assertRaises(adapter.CurrentRupSirupAdapterError):
            adapter.acquire(self.run)

    def test_invalid_limit_fails_closed(self):
        for value in (0, -1, True):
            with self.subTest(value=value), self.assertRaises(adapter.CurrentRupSirupAdapterError):
                adapter.acquire(self.run, limit=value)


if __name__ == "__main__":
    unittest.main()
