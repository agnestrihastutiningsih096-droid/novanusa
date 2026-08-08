import ast
from contextlib import ExitStack
import hashlib
import io
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import fetch_sirup_staging  # noqa: E402
from fetch_sirup_staging import validate_page  # noqa: E402


class VerifyDatabaseTests(unittest.TestCase):
    def verify_aggregate(self, aggregate):
        connection = mock.Mock()
        connection.execute.return_value.fetchone.return_value = aggregate
        with mock.patch.object(
            fetch_sirup_staging.duckdb, "connect", return_value=connection
        ):
            result = fetch_sirup_staging.verify_database(Path("canonical.duckdb"))
        connection.close.assert_called_once_with()
        return result

    def test_initialized_empty_database_returns_null_bounds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "canonical.duckdb"
            fetch_sirup_staging.initialize_database(database_path)
            self.assertEqual(
                (0, 0, None, None),
                fetch_sirup_staging.verify_database(database_path),
            )

    def test_one_row_database_preserves_existing_semantics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "canonical.duckdb"
            fetch_sirup_staging.initialize_database(database_path)
            fetch_sirup_staging.append_page(database_path, [{"id": 17}])
            self.assertEqual(
                (1, 1, 17, 17), fetch_sirup_staging.verify_database(database_path)
            )

    def test_multiple_row_database_preserves_counts_and_bounds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "canonical.duckdb"
            fetch_sirup_staging.initialize_database(database_path)
            fetch_sirup_staging.append_page(
                database_path, [{"id": 9}, {"id": 2}, {"id": 31}]
            )
            self.assertEqual(
                (3, 3, 2, 31), fetch_sirup_staging.verify_database(database_path)
            )

    def test_query_exception_propagates_unchanged_and_connection_closes(self):
        error = RuntimeError("query failed")
        connection = mock.Mock()
        connection.execute.side_effect = error
        with mock.patch.object(
            fetch_sirup_staging.duckdb, "connect", return_value=connection
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.verify_database(Path("canonical.duckdb"))
        self.assertIs(error, raised.exception)
        connection.close.assert_called_once_with()

    def test_zero_rows_with_nonzero_distinct_count_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "distinct ids"):
            self.verify_aggregate((0, 1, None, None))

    def test_zero_rows_with_nonnull_bounds_fails_closed(self):
        for bounds in ((1, None), (None, 1), (1, 1)):
            with self.subTest(bounds=bounds), self.assertRaisesRegex(
                RuntimeError, "inconsistent empty aggregates"
            ):
                self.verify_aggregate((0, 0, *bounds))

    def test_positive_rows_with_null_bounds_fails_closed(self):
        for bounds in ((None, 1), (1, None), (None, None)):
            with self.subTest(bounds=bounds), self.assertRaisesRegex(
                RuntimeError, "null bounds"
            ):
                self.verify_aggregate((1, 1, *bounds))

    def test_distinct_count_greater_than_row_count_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "distinct ids"):
            self.verify_aggregate((1, 2, 1, 1))

    def test_negative_counts_fail_closed(self):
        for aggregate in ((-1, 0, None, None), (0, -1, None, None)):
            with self.subTest(aggregate=aggregate), self.assertRaisesRegex(
                RuntimeError, "negative counts"
            ):
                self.verify_aggregate(aggregate)


class VerifyQuarantineReplayCandidateTests(unittest.TestCase):
    def prepared(self, valid_rows, invalid_rows):
        return {
            "classification": {
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
            }
        }

    def verify_with_mocks(
        self,
        prepared,
        expected_records,
        canonical_rows_collected=5,
        quarantine_rows=3,
        canonical_state=None,
        database_rows=None,
        quarantine_total=None,
        persisted_records=None,
    ):
        valid_rows = prepared["classification"]["valid_rows"]
        if canonical_state is None:
            canonical_state = "complete" if valid_rows else "absent"
        if database_rows is None:
            database_rows = canonical_rows_collected + len(valid_rows)
        if quarantine_total is None:
            quarantine_total = quarantine_rows + len(expected_records)
        if persisted_records is None:
            persisted_records = expected_records
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "build_page_quarantine_records",
                return_value=expected_records,
            ) as build,
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value={
                    "state": canonical_state,
                    "expected_count": len(valid_rows),
                    "observed_count": len(valid_rows),
                },
            ) as inspect,
            mock.patch.object(
                fetch_sirup_staging,
                "verify_database",
                return_value=(database_rows, database_rows, 1, database_rows),
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "count_quarantine_records",
                return_value=quarantine_total,
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "read_quarantine_record",
                side_effect=persisted_records,
            ) as read,
        ):
            result = fetch_sirup_staging.verify_quarantine_replay_candidate(
                Path("canonical.duckdb"),
                Path("quarantine"),
                prepared,
                canonical_rows_collected,
                quarantine_rows,
                "run-1",
                Path("failure.json"),
            )
        return result, build, inspect, read

    def test_valid_only_prepared_page_verifies(self):
        prepared = self.prepared([{"id": 1}, {"id": 2}], [])
        result, _, inspect, read = self.verify_with_mocks(prepared, [])
        self.assertEqual(
            {
                "verified": True,
                "canonical_page_count": 2,
                "quarantine_page_count": 0,
                "expected_canonical_total": 7,
                "expected_quarantine_total": 3,
            },
            result,
        )
        inspect.assert_called_once_with(
            Path("canonical.duckdb"), prepared["classification"]["valid_rows"]
        )
        read.assert_not_called()

    def test_invalid_only_prepared_page_verifies(self):
        prepared = self.prepared([], [{"row_index": 0}])
        records = [{"quarantine_record_id": "record-1", "value": 1}]
        result, _, _, read = self.verify_with_mocks(prepared, records)
        self.assertEqual(0, result["canonical_page_count"])
        self.assertEqual(1, result["quarantine_page_count"])
        read.assert_called_once_with(Path("quarantine") / "record-1.json")

    def test_mixed_page_verifies_without_mutating_prepared_transaction(self):
        prepared = self.prepared([{"id": 1}], [{"row_index": 1}])
        before = json.loads(json.dumps(prepared))
        records = [{"quarantine_record_id": "record-1", "value": {"a": 1}}]
        result, build, _, _ = self.verify_with_mocks(prepared, records)
        self.assertTrue(result["verified"])
        self.assertEqual(before, prepared)
        build.assert_called_once_with(prepared, "run-1", Path("failure.json"))
        self.assertIs(prepared, build.call_args.args[0])

    def test_canonical_exact_replay_mismatch_fails_closed(self):
        prepared = self.prepared([{"id": 1}], [])
        with self.assertRaisesRegex(RuntimeError, "not exactly present"):
            self.verify_with_mocks(prepared, [], canonical_state="conflict")

    def test_missing_or_corrupt_quarantine_record_failure_propagates(self):
        prepared = self.prepared([], [{"row_index": 0}])
        records = [{"quarantine_record_id": "record-1"}]
        for error in (ValueError("missing record"), ValueError("corrupt record")):
            with self.subTest(error=str(error)), mock.patch.object(
                fetch_sirup_staging,
                "build_page_quarantine_records",
                return_value=records,
            ), mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value={"state": "absent"},
            ), mock.patch.object(
                fetch_sirup_staging, "verify_database", return_value=(5, 5, 1, 5)
            ), mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=4
            ), mock.patch.object(
                fetch_sirup_staging, "read_quarantine_record", side_effect=error
            ):
                with self.assertRaises(ValueError) as raised:
                    fetch_sirup_staging.verify_quarantine_replay_candidate(
                        "db", "quarantine", prepared, 5, 3, "run-1", "failure.json"
                    )
                self.assertIs(error, raised.exception)

    def test_quarantine_content_mismatch_fails_closed(self):
        prepared = self.prepared([], [{"row_index": 0}])
        expected = [{"quarantine_record_id": "record-1", "value": 1}]
        with self.assertRaisesRegex(RuntimeError, "does not match expected replay"):
            self.verify_with_mocks(
                prepared,
                expected,
                persisted_records=[{"quarantine_record_id": "record-1", "value": 2}],
            )

    def test_cumulative_physical_count_mismatches_fail_closed(self):
        prepared = self.prepared([{"id": 1}], [{"row_index": 1}])
        records = [{"quarantine_record_id": "record-1"}]
        cases = (
            {"database_rows": 5},
            {"quarantine_total": 3},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments), self.assertRaisesRegex(
                RuntimeError, "total does not match expected replay total"
            ):
                self.verify_with_mocks(prepared, records, **arguments)

    def test_malformed_checkpoint_accounting_is_rejected_before_boundaries(self):
        prepared = self.prepared([], [])
        for canonical_count, quarantine_count in ((-1, 0), (0, -1), (True, 0), (0, False)):
            with self.subTest(
                canonical_count=canonical_count, quarantine_count=quarantine_count
            ), mock.patch.object(
                fetch_sirup_staging, "build_page_quarantine_records"
            ) as build, mock.patch.object(
                fetch_sirup_staging, "inspect_canonical_page_state"
            ) as inspect:
                with self.assertRaises(ValueError):
                    fetch_sirup_staging.verify_quarantine_replay_candidate(
                        "db",
                        "quarantine",
                        prepared,
                        canonical_count,
                        quarantine_count,
                        "run-1",
                        "failure.json",
                    )
                build.assert_not_called()
                inspect.assert_not_called()

    def test_canonical_inspection_failure_propagates_unchanged(self):
        error = RuntimeError("inspection failed")
        prepared = self.prepared([{"id": 1}], [])
        with mock.patch.object(
            fetch_sirup_staging, "build_page_quarantine_records", return_value=[]
        ), mock.patch.object(
            fetch_sirup_staging, "inspect_canonical_page_state", side_effect=error
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.verify_quarantine_replay_candidate(
                    "db", "quarantine", prepared, 0, 0, "run-1", "failure.json"
                )
        self.assertIs(error, raised.exception)

    def test_proof_helper_calls_no_writers_or_persistence(self):
        prepared = self.prepared([{"id": 1}], [])
        with (
            mock.patch.object(
                fetch_sirup_staging, "build_page_quarantine_records", return_value=[]
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value={"state": "complete"},
            ),
            mock.patch.object(
                fetch_sirup_staging, "verify_database", return_value=(1, 1, 1, 1)
            ),
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=0
            ),
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
            mock.patch.object(
                fetch_sirup_staging, "append_page_quarantine_records"
            ) as quarantine_append,
            mock.patch.object(
                fetch_sirup_staging, "persist_prepared_page_transaction"
            ) as persist,
        ):
            fetch_sirup_staging.verify_quarantine_replay_candidate(
                "db", "quarantine", prepared, 0, 0, "run-1", "failure.json"
            )
        for operation in (checkpoint, append, quarantine_append, persist):
            operation.assert_not_called()


class DeriveQuarantineReplayReconciliationTests(unittest.TestCase):
    def prepared(self, valid, invalid):
        return {
            "classification": {
                "valid_rows": [{"id": index} for index in range(valid)],
                "invalid_rows": [{"row_index": index} for index in range(invalid)],
            }
        }

    def verification(self, valid, invalid, canonical=2, quarantine=3):
        return {
            "verified": True,
            "canonical_page_count": valid,
            "quarantine_page_count": invalid,
            "expected_canonical_total": canonical + valid,
            "expected_quarantine_total": quarantine + invalid,
        }

    def derive(self, valid, invalid, source=5, canonical=2, quarantine=3, **changes):
        verification = self.verification(valid, invalid, canonical, quarantine)
        verification.update(changes)
        return fetch_sirup_staging.derive_quarantine_replay_reconciliation(
            source,
            canonical,
            quarantine,
            self.prepared(valid, invalid),
            verification,
        )

    def test_canonical_only_replay_derives_next_accounting(self):
        self.assertEqual(
            {
                "source_rows_processed": 7,
                "canonical_rows_collected": 4,
                "quarantine_rows": 3,
            },
            self.derive(2, 0),
        )

    def test_quarantine_only_replay_derives_next_accounting(self):
        self.assertEqual(
            {
                "source_rows_processed": 7,
                "canonical_rows_collected": 2,
                "quarantine_rows": 5,
            },
            self.derive(0, 2),
        )

    def test_mixed_replay_derives_next_accounting(self):
        self.assertEqual(
            {
                "source_rows_processed": 10,
                "canonical_rows_collected": 4,
                "quarantine_rows": 6,
            },
            self.derive(2, 3),
        )

    def test_stale_cumulative_invariant_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "existing replay accounting invariant"):
            self.derive(1, 1, source=6)

    def test_verified_must_be_exactly_true(self):
        for value in (False, 1, "true", None):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "verified must be exactly True"
            ):
                self.derive(1, 0, verified=value)

    def test_canonical_page_count_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "canonical_page_count"):
            self.derive(2, 0, canonical_page_count=1)

    def test_quarantine_page_count_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "quarantine_page_count"):
            self.derive(0, 2, quarantine_page_count=1)

    def test_expected_canonical_total_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected_canonical_total"):
            self.derive(1, 0, expected_canonical_total=4)

    def test_expected_quarantine_total_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected_quarantine_total"):
            self.derive(0, 1, expected_quarantine_total=5)

    def test_empty_replay_page_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "at least one source row"):
            self.derive(0, 0)

    def test_invalid_cumulative_accounting_inputs_fail_closed(self):
        cases = (
            (True, 0, 0),
            ("0", 0, 0),
            (-1, 0, 0),
            (0, False, 0),
            (0, "0", 0),
            (0, -1, 0),
            (0, 0, True),
            (0, 0, "0"),
            (0, 0, -1),
        )
        verification = self.verification(1, 0, 0, 0)
        for source, canonical, quarantine in cases:
            with self.subTest(values=(source, canonical, quarantine)), self.assertRaises(
                ValueError
            ):
                fetch_sirup_staging.derive_quarantine_replay_reconciliation(
                    source,
                    canonical,
                    quarantine,
                    self.prepared(1, 0),
                    verification,
                )

    def test_invalid_verification_counts_fail_closed(self):
        fields = (
            "canonical_page_count",
            "quarantine_page_count",
            "expected_canonical_total",
            "expected_quarantine_total",
        )
        for field in fields:
            for value in (True, "1", -1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.derive(1, 0, **{field: value})

    def test_malformed_prepared_transaction_fails_closed(self):
        verification = self.verification(1, 0)
        cases = (None, {}, {"classification": {}}, {"classification": {"valid_rows": [], "invalid_rows": "bad"}})
        for prepared in cases:
            with self.subTest(prepared=prepared), self.assertRaises(ValueError):
                fetch_sirup_staging.derive_quarantine_replay_reconciliation(
                    5, 2, 3, prepared, verification
                )

    def test_helper_performs_no_persistence_or_inspection(self):
        operation_names = (
            "write_checkpoint",
            "persist_account_and_checkpoint_page",
            "append_page",
            "append_canonical_page_replay_safe",
            "append_page_quarantine_records",
            "verify_quarantine_replay_candidate",
            "classify_quarantine_resume_physical_state",
            "inspect_canonical_page_state",
            "count_quarantine_records",
            "read_quarantine_record",
            "build_page_quarantine_records",
        )
        patches = [
            mock.patch.object(fetch_sirup_staging, name) for name in operation_names
        ]
        with mock.patch.object(fetch_sirup_staging.duckdb, "connect") as connect:
            mocks = [patch.start() for patch in patches]
            try:
                self.derive(1, 1)
            finally:
                for patch in reversed(patches):
                    patch.stop()
        connect.assert_not_called()
        for operation in mocks:
            operation.assert_not_called()


class WriteQuarantineReplayReconciliationCheckpointTests(unittest.TestCase):
    def accounting(self):
        return {
            "source_rows_processed": 11,
            "canonical_rows_collected": 7,
            "quarantine_rows": 4,
        }

    def arguments(self, accounting=None):
        return (
            Path("checkpoint.json"),
            {"mode": "quarantine"},
            Path("run-dir"),
            self.accounting() if accounting is None else accounting,
            100,
            3,
            "2026-08-08T00:00:00Z",
            2,
        )

    def test_success_calls_write_checkpoint_exactly_once(self):
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint") as write:
            fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                *self.arguments()
            )
        write.assert_called_once()

    def test_exact_accounting_is_passed_to_checkpoint(self):
        accounting = self.accounting()
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint") as write:
            fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                *self.arguments(accounting)
            )
        self.assertEqual((11, 7, 4), write.call_args.args[3:6])

    def test_checkpoint_metadata_is_passed_unchanged(self):
        checkpoint_path = object()
        config = object()
        run_dir = object()
        source_count = object()
        page_count = object()
        started_at = object()
        retries_used = object()
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint") as write:
            fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                checkpoint_path,
                config,
                run_dir,
                self.accounting(),
                source_count,
                page_count,
                started_at,
                retries_used,
            )
        self.assertIs(checkpoint_path, write.call_args.args[0])
        self.assertIs(config, write.call_args.args[1])
        self.assertIs(run_dir, write.call_args.args[2])
        self.assertEqual(
            (source_count, page_count, started_at, retries_used),
            write.call_args.args[6:],
        )

    def test_returns_exact_deterministic_accounting(self):
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint"):
            result = fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                *self.arguments()
            )
        self.assertEqual(self.accounting(), result)
        self.assertEqual(
            {
                "source_rows_processed",
                "canonical_rows_collected",
                "quarantine_rows",
            },
            set(result),
        )

    def test_invalid_invariant_rejects_before_checkpoint_write(self):
        accounting = self.accounting()
        accounting["source_rows_processed"] = 12
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint") as write:
            with self.assertRaisesRegex(ValueError, "accounting invariant"):
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments(accounting)
                )
        write.assert_not_called()

    def test_negative_accounting_count_is_rejected(self):
        for field in self.accounting():
            accounting = self.accounting()
            accounting[field] = -1
            with self.subTest(field=field), mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write, self.assertRaises(ValueError):
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments(accounting)
                )
            write.assert_not_called()

    def test_bool_accounting_count_is_rejected(self):
        for field in self.accounting():
            accounting = self.accounting()
            accounting[field] = True
            with self.subTest(field=field), mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write, self.assertRaises(ValueError):
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments(accounting)
                )
            write.assert_not_called()

    def test_missing_accounting_field_is_rejected(self):
        for field in self.accounting():
            accounting = self.accounting()
            del accounting[field]
            with self.subTest(field=field), mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write, self.assertRaises(ValueError):
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments(accounting)
                )
            write.assert_not_called()

    def test_malformed_or_extra_accounting_is_rejected(self):
        cases = (None, [], "accounting", {**self.accounting(), "extra": 1})
        for accounting in cases:
            arguments = list(self.arguments())
            arguments[3] = accounting
            with self.subTest(accounting=accounting), mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write, self.assertRaises(ValueError):
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *arguments
                )
            write.assert_not_called()

    def test_write_checkpoint_exception_propagates_unchanged(self):
        error = PermissionError("checkpoint unavailable")
        with mock.patch.object(
            fetch_sirup_staging, "write_checkpoint", side_effect=error
        ) as write:
            with self.assertRaises(PermissionError) as raised:
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments()
                )
        self.assertIs(error, raised.exception)
        write.assert_called_once()

    def test_performs_no_canonical_or_quarantine_persistence(self):
        operation_names = (
            "append_page",
            "append_canonical_page_replay_safe",
            "append_page_quarantine_records",
            "persist_prepared_page_transaction",
            "persist_account_and_checkpoint_page",
            "append_quarantine_record",
            "read_quarantine_record",
        )
        patches = [
            mock.patch.object(fetch_sirup_staging, name) for name in operation_names
        ]
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint"):
            mocks = [patch.start() for patch in patches]
            try:
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments()
                )
            finally:
                for patch in reversed(patches):
                    patch.stop()
        for operation in mocks:
            operation.assert_not_called()

    def test_performs_no_replay_proof_derivation_or_database_access(self):
        operation_names = (
            "verify_quarantine_replay_candidate",
            "derive_quarantine_replay_reconciliation",
            "count_quarantine_records",
            "build_page_quarantine_records",
        )
        patches = [
            mock.patch.object(fetch_sirup_staging, name) for name in operation_names
        ]
        with mock.patch.object(fetch_sirup_staging, "write_checkpoint"), mock.patch.object(
            fetch_sirup_staging.duckdb, "connect"
        ) as connect:
            mocks = [patch.start() for patch in patches]
            try:
                fetch_sirup_staging.write_quarantine_replay_reconciliation_checkpoint(
                    *self.arguments()
                )
            finally:
                for patch in reversed(patches):
                    patch.stop()
        connect.assert_not_called()
        for operation in mocks:
            operation.assert_not_called()


class ClassifyQuarantineResumePhysicalStateTests(unittest.TestCase):
    def classify(
        self,
        canonical_rows_collected=10,
        quarantine_rows=2,
        database_rows=10,
        distinct_ids=10,
        actual_quarantine_count=2,
        page_size=5,
    ):
        return fetch_sirup_staging.classify_quarantine_resume_physical_state(
            canonical_rows_collected,
            quarantine_rows,
            database_rows,
            distinct_ids,
            actual_quarantine_count,
            page_size,
        )

    def test_exact_consistent_state(self):
        self.assertEqual(
            {
                "state": "consistent",
                "canonical_ahead_count": 0,
                "quarantine_ahead_count": 0,
                "physical_ahead_count": 0,
            },
            self.classify(),
        )

    def test_canonical_ahead_by_one_page_is_replay_candidate(self):
        self.assertEqual(
            {
                "state": "replay_candidate",
                "canonical_ahead_count": 5,
                "quarantine_ahead_count": 0,
                "physical_ahead_count": 5,
            },
            self.classify(database_rows=15, distinct_ids=15),
        )

    def test_quarantine_ahead_by_one_page_is_replay_candidate(self):
        result = self.classify(actual_quarantine_count=7)
        self.assertEqual("replay_candidate", result["state"])
        self.assertEqual((0, 5, 5), tuple(result.values())[1:])

    def test_mixed_ahead_within_one_page_returns_exact_deltas(self):
        self.assertEqual(
            {
                "state": "replay_candidate",
                "canonical_ahead_count": 2,
                "quarantine_ahead_count": 2,
                "physical_ahead_count": 4,
            },
            self.classify(
                database_rows=12, distinct_ids=12, actual_quarantine_count=4
            ),
        )

    def test_physical_ahead_exactly_page_size_is_replay_candidate(self):
        result = self.classify(
            database_rows=13,
            distinct_ids=13,
            actual_quarantine_count=4,
            page_size=5,
        )
        self.assertEqual("replay_candidate", result["state"])
        self.assertEqual(5, result["physical_ahead_count"])

    def test_physical_ahead_greater_than_page_size_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "more than one page"):
            self.classify(database_rows=16, distinct_ids=16, page_size=5)

    def test_physical_counts_behind_checkpoint_are_rejected(self):
        cases = (
            {"database_rows": 9, "distinct_ids": 9},
            {"actual_quarantine_count": 1},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(RuntimeError, "trails checkpoint"):
                    self.classify(**arguments)

    def test_distinct_id_mismatch_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "distinct ids"):
            self.classify(database_rows=10, distinct_ids=9)

    def test_invalid_page_sizes_are_rejected(self):
        for page_size in (0, -1, True):
            with self.subTest(page_size=page_size):
                with self.assertRaises(ValueError):
                    self.classify(page_size=page_size)

    def test_negative_and_bool_counters_are_rejected(self):
        names = (
            "canonical_rows_collected",
            "quarantine_rows",
            "database_rows",
            "distinct_ids",
            "actual_quarantine_count",
        )
        for name in names:
            for invalid_value in (-1, True):
                with self.subTest(name=name, invalid_value=invalid_value):
                    with self.assertRaises(ValueError):
                        self.classify(**{name: invalid_value})

    def test_helper_performs_no_io_or_persistence_operations(self):
        with (
            mock.patch.object(fetch_sirup_staging.duckdb, "connect") as connect,
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records"
            ) as quarantine_count,
            mock.patch.object(fetch_sirup_staging, "load_checkpoint") as load,
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as write,
            mock.patch.object(
                fetch_sirup_staging, "inspect_canonical_page_state"
            ) as inspect,
            mock.patch.object(
                fetch_sirup_staging, "append_canonical_page_replay_safe"
            ) as append,
            mock.patch.object(
                fetch_sirup_staging, "persist_prepared_page_transaction"
            ) as persist,
        ):
            result = self.classify(database_rows=11, distinct_ids=11)
        self.assertEqual("replay_candidate", result["state"])
        for operation in (connect, quarantine_count, load, write, inspect, append, persist):
            operation.assert_not_called()


class PersistAccountAndCheckpointPageTests(unittest.TestCase):
    def arguments(self):
        return {
            "database_path": Path("canonical.duckdb"),
            "quarantine_path": Path("quarantine"),
            "prepared_transaction": {"classification": {"valid_rows": []}},
            "expected_prior_quarantine_count": 3,
            "run_id": "run-1",
            "failure_evidence_path": Path("failure.json"),
            "source_rows_processed": 8,
            "canonical_rows_collected": 5,
            "quarantine_rows": 3,
            "checkpoint_path": Path("checkpoint.json"),
            "config": {"mode": "quarantine"},
            "run_dir": Path("run"),
            "source_count": 100,
            "page_count": 4,
            "started_at": "2026-08-07T00:00:00+00:00",
            "retries_used": 2,
        }

    def test_success_calls_boundaries_in_order_and_returns_exact_results(self):
        arguments = self.arguments()
        persistence_result = {
            "canonical_status": "created",
            "canonical_count": 2,
            "quarantine_created_count": 1,
            "quarantine_existing_count": 0,
            "quarantine_total_count": 4,
            "page_valid_row_count": 2,
            "page_invalid_row_count": 1,
        }
        next_accounting = {
            "source_rows_processed": 11,
            "canonical_rows_collected": 7,
            "quarantine_rows": 4,
        }
        order = mock.Mock()
        persist = mock.Mock(return_value=persistence_result)
        accounting = mock.Mock(return_value=next_accounting)
        checkpoint = mock.Mock()
        order.attach_mock(persist, "persist")
        order.attach_mock(accounting, "accounting")
        order.attach_mock(checkpoint, "checkpoint")
        with (
            mock.patch.object(
                fetch_sirup_staging, "persist_prepared_page_transaction", persist
            ),
            mock.patch.object(
                fetch_sirup_staging, "derive_next_page_accounting", accounting
            ),
            mock.patch.object(fetch_sirup_staging, "write_checkpoint", checkpoint),
        ):
            result = fetch_sirup_staging.persist_account_and_checkpoint_page(
                **arguments
            )

        persist.assert_called_once_with(
            arguments["database_path"],
            arguments["quarantine_path"],
            arguments["prepared_transaction"],
            arguments["expected_prior_quarantine_count"],
            arguments["run_id"],
            arguments["failure_evidence_path"],
        )
        accounting.assert_called_once_with(8, 5, 3, persistence_result)
        checkpoint.assert_called_once_with(
            arguments["checkpoint_path"],
            arguments["config"],
            arguments["run_dir"],
            11,
            7,
            4,
            arguments["source_count"],
            arguments["page_count"],
            arguments["started_at"],
            arguments["retries_used"],
        )
        self.assertEqual(
            ["persist", "accounting", "checkpoint"],
            [call[0] for call in order.mock_calls],
        )
        self.assertEqual(
            {
                "persistence_result": persistence_result,
                "next_accounting": next_accounting,
            },
            result,
        )
        self.assertIs(persistence_result, result["persistence_result"])
        self.assertIs(next_accounting, result["next_accounting"])
        self.assertIs(arguments["prepared_transaction"], persist.call_args.args[2])
        self.assertIs(arguments["config"], checkpoint.call_args.args[1])
        self.assertIs(arguments["run_dir"], checkpoint.call_args.args[2])

    def test_persistence_exception_propagates_and_stops(self):
        error = OSError("persistence failed")
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "persist_prepared_page_transaction",
                side_effect=error,
            ),
            mock.patch.object(
                fetch_sirup_staging, "derive_next_page_accounting"
            ) as accounting,
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint,
        ):
            with self.assertRaises(OSError) as raised:
                fetch_sirup_staging.persist_account_and_checkpoint_page(
                    **self.arguments()
                )
        self.assertIs(error, raised.exception)
        accounting.assert_not_called()
        checkpoint.assert_not_called()

    def test_accounting_exception_propagates_and_prevents_checkpoint(self):
        error = ValueError("accounting failed")
        persistence_result = {"result": "persisted"}
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "persist_prepared_page_transaction",
                return_value=persistence_result,
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "derive_next_page_accounting",
                side_effect=error,
            ) as accounting,
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint,
        ):
            with self.assertRaises(ValueError) as raised:
                fetch_sirup_staging.persist_account_and_checkpoint_page(
                    **self.arguments()
                )
        self.assertIs(error, raised.exception)
        accounting.assert_called_once_with(8, 5, 3, persistence_result)
        checkpoint.assert_not_called()

    def test_checkpoint_exception_propagates_without_success_return(self):
        error = PermissionError("checkpoint failed")
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "persist_prepared_page_transaction",
                return_value={"persisted": True},
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "derive_next_page_accounting",
                return_value={
                    "source_rows_processed": 9,
                    "canonical_rows_collected": 6,
                    "quarantine_rows": 3,
                },
            ),
            mock.patch.object(
                fetch_sirup_staging, "write_checkpoint", side_effect=error
            ) as checkpoint,
        ):
            with self.assertRaises(PermissionError) as raised:
                fetch_sirup_staging.persist_account_and_checkpoint_page(
                    **self.arguments()
                )
        self.assertIs(error, raised.exception)
        checkpoint.assert_called_once()


class DeriveNextPageAccountingTests(unittest.TestCase):
    def persistence_result(
        self,
        valid=2,
        invalid=0,
        status="created",
        quarantine_created=None,
        quarantine_existing=0,
        prior_quarantine=0,
    ):
        if quarantine_created is None:
            quarantine_created = invalid - quarantine_existing
        return {
            "canonical_status": status,
            "canonical_count": valid,
            "quarantine_created_count": quarantine_created,
            "quarantine_existing_count": quarantine_existing,
            "quarantine_total_count": prior_quarantine + invalid,
            "page_valid_row_count": valid,
            "page_invalid_row_count": invalid,
        }

    def derive(self, persistence_result, source=0, canonical=0, quarantine=0):
        return fetch_sirup_staging.derive_next_page_accounting(
            source, canonical, quarantine, persistence_result
        )

    def test_all_valid_newly_created_page(self):
        self.assertEqual(
            {
                "source_rows_processed": 3,
                "canonical_rows_collected": 3,
                "quarantine_rows": 0,
            },
            self.derive(self.persistence_result(valid=3)),
        )

    def test_mixed_newly_created_page_and_exact_returned_invariant(self):
        result = self.derive(self.persistence_result(valid=3, invalid=2))
        self.assertEqual(
            {
                "source_rows_processed": 5,
                "canonical_rows_collected": 3,
                "quarantine_rows": 2,
            },
            result,
        )
        self.assertEqual(
            result["source_rows_processed"],
            result["canonical_rows_collected"] + result["quarantine_rows"],
        )

    def test_prior_quarantine_with_all_page_records_newly_created(self):
        result = self.derive(
            self.persistence_result(
                valid=1, invalid=2, quarantine_created=2, prior_quarantine=3
            ),
            source=5,
            canonical=2,
            quarantine=3,
        )
        self.assertEqual(
            {
                "source_rows_processed": 8,
                "canonical_rows_collected": 3,
                "quarantine_rows": 5,
            },
            result,
        )

    def test_canonical_existing_replay_has_same_logical_accounting_as_created(self):
        created = self.derive(self.persistence_result(valid=2, invalid=1))
        existing = self.derive(
            self.persistence_result(valid=2, invalid=1, status="existing")
        )
        self.assertEqual(created, existing)

    def test_existing_quarantine_replay_uses_logical_invalid_count(self):
        result = self.derive(
            self.persistence_result(
                valid=1,
                invalid=2,
                quarantine_created=0,
                quarantine_existing=2,
                prior_quarantine=3,
            ),
            source=5,
            canonical=2,
            quarantine=3,
        )
        self.assertEqual(8, result["source_rows_processed"])
        self.assertEqual(5, result["quarantine_rows"])

    def test_prior_quarantine_with_mixed_created_and_existing_records(self):
        result = self.derive(
            self.persistence_result(
                valid=2,
                invalid=3,
                quarantine_created=1,
                quarantine_existing=2,
                prior_quarantine=4,
            ),
            source=7,
            canonical=3,
            quarantine=4,
        )
        self.assertEqual(12, result["source_rows_processed"])
        self.assertEqual(7, result["quarantine_rows"])

    def test_zero_row_page(self):
        self.assertEqual(
            {
                "source_rows_processed": 0,
                "canonical_rows_collected": 0,
                "quarantine_rows": 0,
            },
            self.derive(self.persistence_result(valid=0, invalid=0)),
        )

    def test_existing_cumulative_quarantine_accounting(self):
        result = self.derive(
            self.persistence_result(valid=2, invalid=1, prior_quarantine=3),
            source=8,
            canonical=5,
            quarantine=3,
        )
        self.assertEqual(
            {
                "source_rows_processed": 11,
                "canonical_rows_collected": 7,
                "quarantine_rows": 4,
            },
            result,
        )

    def test_zero_invalid_page_preserves_existing_quarantine_total(self):
        result = self.derive(
            self.persistence_result(valid=2, invalid=0, prior_quarantine=3),
            source=8,
            canonical=5,
            quarantine=3,
        )
        self.assertEqual(
            {
                "source_rows_processed": 10,
                "canonical_rows_collected": 7,
                "quarantine_rows": 3,
            },
            result,
        )

    def test_invalid_existing_invariant_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "existing page accounting invariant"):
            self.derive(self.persistence_result(), source=4, canonical=3, quarantine=2)

    def test_invalid_cumulative_counter_types_and_values_are_rejected(self):
        cases = ((-1, 0, 0), (True, 0, 0), (0, False, 0), (0, 0, True))
        for source, canonical, quarantine in cases:
            with self.subTest(counters=(source, canonical, quarantine)):
                with self.assertRaises(ValueError):
                    self.derive(
                        self.persistence_result(), source, canonical, quarantine
                    )

    def test_missing_persistence_field_is_rejected(self):
        result = self.persistence_result()
        del result["canonical_count"]
        with self.assertRaisesRegex(ValueError, "missing canonical_count"):
            self.derive(result)

    def test_negative_and_bool_persistence_counts_are_rejected(self):
        for invalid_value in (-1, True):
            for field in (
                "canonical_count",
                "quarantine_created_count",
                "quarantine_existing_count",
                "quarantine_total_count",
                "page_valid_row_count",
                "page_invalid_row_count",
            ):
                with self.subTest(field=field, invalid_value=invalid_value):
                    result = self.persistence_result()
                    result[field] = invalid_value
                    with self.assertRaises(ValueError):
                        self.derive(result)

    def test_unsupported_canonical_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported canonical_status"):
            self.derive(self.persistence_result(status="partial"))

    def test_canonical_count_mismatch_is_rejected(self):
        result = self.persistence_result(valid=2)
        result["canonical_count"] = 1
        with self.assertRaisesRegex(ValueError, "canonical_count"):
            self.derive(result)

    def test_quarantine_total_count_mismatch_is_rejected(self):
        result = self.persistence_result(valid=1, invalid=2, prior_quarantine=3)
        result["quarantine_total_count"] = 4
        with self.assertRaisesRegex(ValueError, "quarantine_total_count"):
            self.derive(result, source=5, canonical=2, quarantine=3)

    def test_quarantine_created_existing_sum_mismatch_is_rejected(self):
        result = self.persistence_result(valid=1, invalid=2)
        result["quarantine_created_count"] = 0
        with self.assertRaisesRegex(ValueError, "page_invalid_row_count"):
            self.derive(result)

    def test_helper_performs_no_io_or_persistence_operations(self):
        with (
            mock.patch.object(fetch_sirup_staging.duckdb, "connect") as connect,
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
            mock.patch.object(
                fetch_sirup_staging, "append_canonical_page_replay_safe"
            ) as canonical_append,
            mock.patch.object(
                fetch_sirup_staging, "append_page_quarantine_records"
            ) as quarantine_append,
        ):
            self.derive(self.persistence_result(valid=1, invalid=1))
        connect.assert_not_called()
        checkpoint.assert_not_called()
        append.assert_not_called()
        canonical_append.assert_not_called()
        quarantine_append.assert_not_called()


class PersistPreparedPageTransactionTests(unittest.TestCase):
    def make_prepared(self, valid_rows, invalid_rows):
        return {
            "classification": {
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "invalid_row_count": len(invalid_rows),
            }
        }

    def persist_with_mocks(
        self,
        prepared,
        canonical_result=None,
        quarantine_records=None,
        quarantine_result=None,
        expected_prior_count=4,
    ):
        canonical_result = canonical_result or {
            "status": "created",
            "canonical_count": len(prepared["classification"]["valid_rows"]),
        }
        if quarantine_records is None:
            quarantine_records = [
                {"record": index}
                for index, _ in enumerate(prepared["classification"]["invalid_rows"])
            ]
        quarantine_result = quarantine_result or {
            "created_count": len(quarantine_records),
            "existing_count": 0,
            "total_count": expected_prior_count + len(quarantine_records),
        }
        order = mock.Mock()
        build = mock.Mock(return_value=quarantine_records)
        canonical = mock.Mock(return_value=canonical_result)
        quarantine = mock.Mock(return_value=quarantine_result)
        order.attach_mock(build, "build")
        order.attach_mock(canonical, "canonical")
        order.attach_mock(quarantine, "quarantine")
        with (
            mock.patch.object(fetch_sirup_staging, "build_page_quarantine_records", build),
            mock.patch.object(
                fetch_sirup_staging, "append_canonical_page_replay_safe", canonical
            ),
            mock.patch.object(
                fetch_sirup_staging, "append_page_quarantine_records", quarantine
            ),
        ):
            result = fetch_sirup_staging.persist_prepared_page_transaction(
                Path("canonical.duckdb"),
                Path("quarantine"),
                prepared,
                expected_prior_count,
                "run-1",
                Path("failure.json"),
            )
        return result, quarantine_records, order, build, canonical, quarantine

    def test_canonical_created_and_quarantine_created_in_required_order(self):
        valid_rows = [{"id": 1}, {"id": 2}]
        invalid_rows = [{"row_index": 2}]
        prepared = self.make_prepared(valid_rows, invalid_rows)
        result, records, order, build, canonical, quarantine = self.persist_with_mocks(
            prepared
        )

        self.assertEqual(
            {
                "canonical_status": "created",
                "canonical_count": 2,
                "quarantine_created_count": 1,
                "quarantine_existing_count": 0,
                "quarantine_total_count": 5,
                "page_valid_row_count": 2,
                "page_invalid_row_count": 1,
            },
            result,
        )
        build.assert_called_once_with(prepared, "run-1", Path("failure.json"))
        canonical.assert_called_once_with(Path("canonical.duckdb"), valid_rows)
        quarantine.assert_called_once_with(Path("quarantine"), records, 4)
        self.assertIs(prepared, build.call_args.args[0])
        self.assertIs(valid_rows, canonical.call_args.args[1])
        self.assertIs(records, quarantine.call_args.args[1])
        self.assertEqual(
            ["build", "canonical", "quarantine"],
            [call[0] for call in order.mock_calls],
        )

    def test_canonical_existing_and_quarantine_replayed(self):
        prepared = self.make_prepared([{"id": 1}], [{"row_index": 1}, {"row_index": 2}])
        result, _, _, _, _, _ = self.persist_with_mocks(
            prepared,
            canonical_result={"status": "existing", "canonical_count": 1},
            quarantine_result={
                "created_count": 0, "existing_count": 2, "total_count": 9,
            },
            expected_prior_count=7,
        )
        self.assertEqual("existing", result["canonical_status"])
        self.assertEqual(0, result["quarantine_created_count"])
        self.assertEqual(2, result["quarantine_existing_count"])
        self.assertEqual(9, result["quarantine_total_count"])

    def test_zero_invalid_rows_still_calls_quarantine_boundary(self):
        valid_rows = [{"id": 1}]
        prepared = self.make_prepared(valid_rows, [])
        result, records, _, _, _, quarantine = self.persist_with_mocks(prepared)
        self.assertEqual([], records)
        quarantine.assert_called_once_with(Path("quarantine"), records, 4)
        self.assertEqual(0, result["page_invalid_row_count"])

    def test_zero_valid_rows_still_calls_canonical_boundary(self):
        prepared = self.make_prepared([], [{"row_index": 0}])
        result, _, _, _, canonical, _ = self.persist_with_mocks(prepared)
        canonical.assert_called_once_with(Path("canonical.duckdb"), prepared["classification"]["valid_rows"])
        self.assertEqual(0, result["page_valid_row_count"])

    def test_completely_empty_classification_uses_both_boundaries(self):
        prepared = self.make_prepared([], [])
        result, records, _, _, canonical, quarantine = self.persist_with_mocks(prepared)
        canonical.assert_called_once_with(Path("canonical.duckdb"), prepared["classification"]["valid_rows"])
        quarantine.assert_called_once_with(Path("quarantine"), records, 4)
        self.assertEqual(0, result["page_valid_row_count"])
        self.assertEqual(0, result["page_invalid_row_count"])

    def test_canonical_exception_prevents_quarantine_append(self):
        error = RuntimeError("canonical failed")
        prepared = self.make_prepared([{"id": 1}], [{"row_index": 1}])
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "build_page_quarantine_records",
                return_value=[{"record": 1}],
            ) as build,
            mock.patch.object(
                fetch_sirup_staging,
                "append_canonical_page_replay_safe",
                side_effect=error,
            ),
            mock.patch.object(
                fetch_sirup_staging, "append_page_quarantine_records"
            ) as quarantine,
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.persist_prepared_page_transaction(
                    "db", "quarantine", prepared, 0, "run-1", "failure.json"
                )
        self.assertIs(error, raised.exception)
        build.assert_called_once()
        quarantine.assert_not_called()

    def test_quarantine_exception_propagates_unchanged(self):
        error = OSError("quarantine failed")
        prepared = self.make_prepared([{"id": 1}], [{"row_index": 1}])
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "build_page_quarantine_records",
                return_value=[{"record": 1}],
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "append_canonical_page_replay_safe",
                return_value={"status": "created", "canonical_count": 1},
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "append_page_quarantine_records",
                side_effect=error,
            ),
        ):
            with self.assertRaises(OSError) as raised:
                fetch_sirup_staging.persist_prepared_page_transaction(
                    "db", "quarantine", prepared, 0, "run-1", "failure.json"
                )
        self.assertIs(error, raised.exception)

    def test_has_no_checkpoint_runtime_preparation_or_validation_side_effects(self):
        prepared = self.make_prepared([{"id": 1}], [])
        with (
            mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint,
            mock.patch.object(fetch_sirup_staging, "prepare_page_transaction") as prepare,
            mock.patch.object(fetch_sirup_staging, "validate_page") as validate,
            mock.patch.object(
                fetch_sirup_staging, "build_page_quarantine_records", return_value=[]
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "append_canonical_page_replay_safe",
                return_value={"status": "created", "canonical_count": 1},
            ),
            mock.patch.object(
                fetch_sirup_staging,
                "append_page_quarantine_records",
                return_value={
                    "created_count": 0, "existing_count": 0, "total_count": 0,
                },
            ),
        ):
            fetch_sirup_staging.persist_prepared_page_transaction(
                "db", "quarantine", prepared, 0, "run-1", "failure.json"
            )
        checkpoint.assert_not_called()
        prepare.assert_not_called()
        validate.assert_not_called()


class AppendCanonicalPageReplaySafeTests(unittest.TestCase):
    def run_with_state(self, state, rows=None, expected_count=2, observed_count=0):
        if rows is None:
            rows = [{"id": 1}, {"id": 2}]
        inspection_result = {
            "state": state,
            "expected_count": expected_count,
            "observed_count": observed_count,
        }
        inspect = mock.Mock(return_value=inspection_result)
        append = mock.Mock()
        with (
            mock.patch.object(
                fetch_sirup_staging, "inspect_canonical_page_state", inspect
            ),
            mock.patch.object(fetch_sirup_staging, "append_page", append),
        ):
            result = fetch_sirup_staging.append_canonical_page_replay_safe(
                Path("canonical.duckdb"), rows
            )
        return result, rows, inspect, append

    def test_absent_appends_once_and_returns_created_with_unchanged_arguments(self):
        database_path = Path("canonical.duckdb")
        rows = [{"id": 1}, {"id": 2}]
        inspection = {"state": "absent", "expected_count": 2, "observed_count": 0}
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value=inspection,
            ) as inspect,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
        ):
            result = fetch_sirup_staging.append_canonical_page_replay_safe(
                database_path, rows
            )

        self.assertEqual({"status": "created", "canonical_count": 2}, result)
        inspect.assert_called_once_with(database_path, rows)
        append.assert_called_once_with(database_path, rows)
        self.assertIs(database_path, inspect.call_args.args[0])
        self.assertIs(rows, inspect.call_args.args[1])
        self.assertIs(database_path, append.call_args.args[0])
        self.assertIs(rows, append.call_args.args[1])

    def test_complete_does_not_append_and_returns_existing(self):
        result, _, inspect, append = self.run_with_state(
            "complete", observed_count=2
        )
        self.assertEqual({"status": "existing", "canonical_count": 2}, result)
        inspect.assert_called_once()
        append.assert_not_called()

    def test_partial_raises_with_counts_and_does_not_append(self):
        inspection = {"state": "partial", "expected_count": 5, "observed_count": 2}
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value=inspection,
            ) as inspect,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
        ):
            with self.assertRaisesRegex(
                RuntimeError, r"partial.*expected_count=5.*observed_count=2"
            ):
                fetch_sirup_staging.append_canonical_page_replay_safe("db", [{"id": 1}])
        inspect.assert_called_once_with("db", [{"id": 1}])
        append.assert_not_called()

    def test_conflict_raises_with_counts_and_does_not_append(self):
        inspection = {"state": "conflict", "expected_count": 3, "observed_count": 3}
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value=inspection,
            ),
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
        ):
            with self.assertRaisesRegex(
                RuntimeError, r"conflict.*expected_count=3.*observed_count=3"
            ):
                fetch_sirup_staging.append_canonical_page_replay_safe("db", [{"id": 1}])
        append.assert_not_called()

    def test_unexpected_inspection_state_raises_without_append(self):
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value={"state": "unknown"},
            ) as inspect,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
        ):
            with self.assertRaisesRegex(RuntimeError, "unexpected canonical page"):
                fetch_sirup_staging.append_canonical_page_replay_safe("db", [])
        inspect.assert_called_once_with("db", [])
        append.assert_not_called()

    def test_inspection_exception_propagates_unchanged(self):
        error = OSError("inspection failed")
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                side_effect=error,
            ) as inspect,
            mock.patch.object(fetch_sirup_staging, "append_page") as append,
        ):
            with self.assertRaises(OSError) as raised:
                fetch_sirup_staging.append_canonical_page_replay_safe("db", [{"id": 1}])
        self.assertIs(error, raised.exception)
        inspect.assert_called_once()
        append.assert_not_called()

    def test_append_exception_propagates_unchanged(self):
        error = RuntimeError("append failed")
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "inspect_canonical_page_state",
                return_value={
                    "state": "absent", "expected_count": 1, "observed_count": 0,
                },
            ) as inspect,
            mock.patch.object(
                fetch_sirup_staging, "append_page", side_effect=error
            ) as append,
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.append_canonical_page_replay_safe("db", [{"id": 1}])
        self.assertIs(error, raised.exception)
        inspect.assert_called_once()
        append.assert_called_once()

    def test_empty_rows_follow_absent_path_and_append_once(self):
        result, rows, inspect, append = self.run_with_state(
            "absent", rows=[], expected_count=0, observed_count=0
        )
        self.assertEqual({"status": "created", "canonical_count": 0}, result)
        inspect.assert_called_once_with(Path("canonical.duckdb"), rows)
        append.assert_called_once_with(Path("canonical.duckdb"), rows)


class InspectCanonicalPageStateTests(unittest.TestCase):
    fields = (
        "id", "id_referensi", "pagu", "satuanKerja", "kldi", "lokasi",
        "jenisPengadaan", "metode", "sumberDana", "paket", "pemilihan", "idBulan",
    )

    def make_row(self, identifier, suffix=""):
        return {
            field: (
                identifier
                if field in {"id", "idBulan"}
                else float(identifier)
                if field == "pagu"
                else f"{field}-{identifier}{suffix}"
            )
            for field in self.fields
        }

    def tuple_for(self, row):
        return fetch_sirup_staging.canonical_storage_row_tuple(row)

    def inspect_with_results(self, rows, stored_rows):
        connection = mock.Mock()
        connection.execute.return_value.fetchall.return_value = stored_rows
        with mock.patch.object(
            fetch_sirup_staging.duckdb, "connect", return_value=connection
        ) as connect:
            result = fetch_sirup_staging.inspect_canonical_page_state(
                Path("canonical.duckdb"), rows
            )
        return result, connect, connection

    def test_empty_rows_returns_absent_without_duckdb_query(self):
        with mock.patch.object(fetch_sirup_staging.duckdb, "connect") as connect:
            result = fetch_sirup_staging.inspect_canonical_page_state("unused", [])
        self.assertEqual(
            {"state": "absent", "expected_count": 0, "observed_count": 0}, result
        )
        connect.assert_not_called()

    def test_no_matching_ids_is_absent_and_opens_read_only(self):
        rows = [self.make_row(1), self.make_row(2)]
        result, connect, connection = self.inspect_with_results(rows, [])
        self.assertEqual(
            {"state": "absent", "expected_count": 2, "observed_count": 0}, result
        )
        connect.assert_called_once_with("canonical.duckdb", read_only=True)
        query, identifiers = connection.execute.call_args.args
        self.assertEqual([1, 2], identifiers)
        self.assertIn("from sirup_raw where id in (?, ?)", query)
        connection.close.assert_called_once_with()

    def test_all_rows_present_and_identical_is_complete(self):
        rows = [self.make_row(1), self.make_row(2)]
        result, _, _ = self.inspect_with_results(
            rows, [self.tuple_for(row) for row in rows]
        )
        self.assertEqual(
            {"state": "complete", "expected_count": 2, "observed_count": 2}, result
        )

    def test_some_rows_present_is_partial_even_if_present_row_conflicts(self):
        rows = [self.make_row(1), self.make_row(2)]
        result, _, _ = self.inspect_with_results(
            rows, [self.tuple_for(self.make_row(1, "-different"))]
        )
        self.assertEqual(
            {"state": "partial", "expected_count": 2, "observed_count": 1}, result
        )

    def test_all_ids_present_but_field_differs_is_conflict(self):
        rows = [self.make_row(1), self.make_row(2)]
        stored = [self.tuple_for(rows[0]), self.tuple_for(self.make_row(2, "-different"))]
        result, _, _ = self.inspect_with_results(rows, stored)
        self.assertEqual(
            {"state": "conflict", "expected_count": 2, "observed_count": 2}, result
        )

    def test_database_return_order_does_not_affect_complete_state(self):
        rows = [self.make_row(1), self.make_row(2)]
        result, _, _ = self.inspect_with_results(
            rows, [self.tuple_for(rows[1]), self.tuple_for(rows[0])]
        )
        self.assertEqual("complete", result["state"])

    def test_duplicate_ids_are_rejected_before_database_open(self):
        with mock.patch.object(fetch_sirup_staging.duckdb, "connect") as connect:
            with self.assertRaisesRegex(ValueError, "duplicate canonical inspection id"):
                fetch_sirup_staging.inspect_canonical_page_state(
                    "unused", [self.make_row(1), self.make_row(1)]
                )
        connect.assert_not_called()

    def test_missing_and_none_ids_are_rejected_before_database_open(self):
        for row in ({"pagu": 1}, {"id": None}):
            with self.subTest(row=row), mock.patch.object(
                fetch_sirup_staging.duckdb, "connect"
            ) as connect:
                with self.assertRaises(ValueError):
                    fetch_sirup_staging.inspect_canonical_page_state("unused", [row])
                connect.assert_not_called()

    def test_database_exception_propagates_unchanged_and_connection_closes(self):
        error = RuntimeError("query failed")
        connection = mock.Mock()
        connection.execute.side_effect = error
        with mock.patch.object(
            fetch_sirup_staging.duckdb, "connect", return_value=connection
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.inspect_canonical_page_state(
                    "canonical.duckdb", [self.make_row(1)]
                )
        self.assertIs(error, raised.exception)
        connection.close.assert_called_once_with()

    def test_integer_id_referensi_matches_persisted_varchar(self):
        row = self.make_row(861)
        row["id_referensi"] = 861
        stored = [self.tuple_for({**row, "id_referensi": "861"})]
        result, _, _ = self.inspect_with_results([row], stored)
        self.assertEqual("complete", result["state"])

    def test_real_duckdb_integer_id_referensi_storage_matches(self):
        row = self.make_row(861)
        row["id_referensi"] = 861
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "canonical.duckdb"
            fetch_sirup_staging.initialize_database(database_path)
            fetch_sirup_staging.append_page(database_path, [row])
            result = fetch_sirup_staging.inspect_canonical_page_state(
                database_path, [row]
            )
        self.assertEqual("complete", result["state"])

    def test_string_id_referensi_matches_persisted_varchar(self):
        row = self.make_row(861)
        row["id_referensi"] = "861"
        result, _, _ = self.inspect_with_results([row], [self.tuple_for(row)])
        self.assertEqual("complete", result["state"])

    def test_none_varchar_remains_none(self):
        row = self.make_row(861)
        row["id_referensi"] = None
        stored = list(self.tuple_for(row))
        self.assertIsNone(stored[1])
        result, _, _ = self.inspect_with_results([row], [tuple(stored)])
        self.assertEqual("complete", result["state"])

    def test_id_referensi_content_difference_remains_conflict(self):
        row = self.make_row(862)
        row["id_referensi"] = 862
        stored = {**row, "id_referensi": "861"}
        result, _, _ = self.inspect_with_results([row], [self.tuple_for(stored)])
        self.assertEqual("conflict", result["state"])

    def test_varchar_normalization_preserves_whitespace_case_and_empty_string(self):
        row = self.make_row(861)
        row["id_referensi"] = "  Mixed Case  "
        normalized = fetch_sirup_staging.canonical_storage_row_tuple(row)
        self.assertEqual("  Mixed Case  ", normalized[1])
        row["id_referensi"] = ""
        self.assertEqual("", fetch_sirup_staging.canonical_storage_row_tuple(row)[1])

    def test_numeric_storage_fields_are_normalized_without_rounding(self):
        row = self.make_row(861)
        row.update({"id": "861", "pagu": "12.5", "idBulan": "7"})
        self.assertEqual(
            (861, "id_referensi-861", 12.5, "satuanKerja-861", "kldi-861",
             "lokasi-861", "jenisPengadaan-861", "metode-861", "sumberDana-861",
             "paket-861", "pemilihan-861", 7),
            fetch_sirup_staging.canonical_storage_row_tuple(row),
        )

    def test_helper_does_not_call_write_methods_or_append_page(self):
        row = self.make_row(1)
        connection = mock.Mock()
        connection.execute.return_value.fetchall.return_value = [self.tuple_for(row)]
        with (
            mock.patch.object(
                fetch_sirup_staging.duckdb, "connect", return_value=connection
            ),
            mock.patch.object(fetch_sirup_staging, "append_page") as append_page,
        ):
            fetch_sirup_staging.inspect_canonical_page_state("canonical.duckdb", [row])
        append_page.assert_not_called()
        connection.executemany.assert_not_called()
        executed_query = connection.execute.call_args.args[0].lower()
        for write_keyword in ("insert", "update", "delete", "create", "begin"):
            self.assertNotIn(write_keyword, executed_query)


class AppendPageQuarantineRecordsTests(unittest.TestCase):
    def call_helper(self, records, expected_prior_count):
        return fetch_sirup_staging.append_page_quarantine_records(
            Path("unused-quarantine"), records, expected_prior_count
        )

    def test_all_records_created(self):
        records = [{"id": 1}, {"id": 2}]
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                side_effect=["created", "created"],
            ) as append,
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=5
            ) as count,
        ):
            result = self.call_helper(records, 3)

        self.assertEqual(
            {"created_count": 2, "existing_count": 0, "total_count": 5}, result
        )
        self.assertEqual(
            [mock.call(Path("unused-quarantine"), record) for record in records],
            append.call_args_list,
        )
        count.assert_called_once_with(Path("unused-quarantine"))

    def test_mix_of_created_and_existing(self):
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                side_effect=["created", "existing", "created"],
            ),
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=7
            ),
        ):
            result = self.call_helper([{"id": 1}, {"id": 2}, {"id": 3}], 4)

        self.assertEqual(
            {"created_count": 2, "existing_count": 1, "total_count": 7}, result
        )

    def test_partial_page_replay_uses_record_count_for_cumulative_invariant(self):
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                side_effect=["existing", "existing", "created"],
            ),
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=13
            ),
        ):
            result = self.call_helper([{"id": 1}, {"id": 2}, {"id": 3}], 10)

        self.assertEqual(
            {"created_count": 1, "existing_count": 2, "total_count": 13}, result
        )

    def test_empty_records_still_counts_once(self):
        with (
            mock.patch.object(
                fetch_sirup_staging, "append_quarantine_record"
            ) as append,
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=4
            ) as count,
        ):
            result = self.call_helper([], 4)

        self.assertEqual(
            {"created_count": 0, "existing_count": 0, "total_count": 4}, result
        )
        append.assert_not_called()
        count.assert_called_once_with(Path("unused-quarantine"))

    def test_invalid_expected_prior_counts_fail_before_store_calls(self):
        for invalid_value in (-1, True, 1.0):
            with self.subTest(invalid_value=invalid_value), mock.patch.object(
                fetch_sirup_staging, "append_quarantine_record"
            ) as append, mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records"
            ) as count:
                with self.assertRaises(ValueError):
                    self.call_helper([{"id": 1}], invalid_value)
                append.assert_not_called()
                count.assert_not_called()

    def test_unexpected_append_status_raises_and_does_not_count(self):
        records = [{"id": 1}, {"id": 2}]
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                side_effect=["created", "invalid"],
            ) as append,
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records"
            ) as count,
        ):
            with self.assertRaisesRegex(RuntimeError, "unexpected quarantine append"):
                self.call_helper(records, 0)

        self.assertEqual(2, append.call_count)
        count.assert_not_called()

    def test_append_exception_propagates_unchanged_and_stops(self):
        error = OSError("append failed")
        records = [{"id": 1}, {"id": 2}, {"id": 3}]
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                side_effect=["created", error, "created"],
            ) as append,
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records"
            ) as count,
        ):
            with self.assertRaises(OSError) as raised:
                self.call_helper(records, 0)

        self.assertIs(error, raised.exception)
        self.assertEqual(2, append.call_count)
        count.assert_not_called()

    def test_cumulative_count_mismatch_reports_expected_and_observed(self):
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "append_quarantine_record",
                return_value="existing",
            ),
            mock.patch.object(
                fetch_sirup_staging, "count_quarantine_records", return_value=8
            ) as count,
        ):
            with self.assertRaisesRegex(RuntimeError, "expected 7, observed 8"):
                self.call_helper([{"id": 1}, {"id": 2}], 5)

        count.assert_called_once_with(Path("unused-quarantine"))


class BuildPageQuarantineRecordsTests(unittest.TestCase):
    def make_prepared_transaction(self, invalid_rows):
        return {
            "classification": {
                "valid_rows": [],
                "invalid_rows": invalid_rows,
                "invalid_row_count": len(invalid_rows),
            },
            "verified_source_count": 10,
            "payload_sha256": "a" * 64,
            "request_parameters": {"start": 100, "length": 2},
            "page_identity": {
                "run_id": "prepared-run",
                "page_start": 100,
                "requested_length": 2,
                "page_draw": 3,
                "payload_sha256": "a" * 64,
            },
            "captured_at": "2026-08-06T01:02:03+00:00",
        }

    def test_builds_each_record_in_source_order_with_exact_arguments(self):
        first_raw = ["unparsed", 1]
        first_missing = ["id"]
        first_invalid = []
        second_raw = {"id": 9, "pagu": "bad"}
        second_missing = []
        second_invalid = ["pagu"]
        invalid_rows = [
            {
                "row_index": 0,
                "raw_row": first_raw,
                "missing_fields": first_missing,
                "invalid_fields": first_invalid,
                "validation_error": "row is not an object",
            },
            {
                "row_index": 1,
                "raw_row": second_raw,
                "missing_fields": second_missing,
                "invalid_fields": second_invalid,
                "validation_error": "invalid pagu",
            },
        ]
        prepared = self.make_prepared_transaction(invalid_rows)
        prepared_before = json.loads(json.dumps(prepared))
        first_record = {"record": 1}
        second_record = {"record": 2}
        evidence_path = Path("evidence") / "page.json"
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "build_quarantine_record",
                side_effect=[first_record, second_record],
            ) as builder,
            mock.patch.object(fetch_sirup_staging, "append_page") as append_page,
            mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write_checkpoint,
            mock.patch.object(
                fetch_sirup_staging, "write_validation_failure_evidence"
            ) as write_evidence,
        ):
            result = fetch_sirup_staging.build_page_quarantine_records(
                prepared, "run-1", evidence_path
            )

        self.assertEqual(2, builder.call_count)
        expected_common = {
            "run_id": "run-1",
            "page_start": 100,
            "requested_length": 2,
            "page_draw": 3,
            "captured_at": "2026-08-06T01:02:03+00:00",
            "payload_sha256": "a" * 64,
            "request_parameters": prepared["request_parameters"],
            "failure_evidence_path": str(evidence_path),
        }
        expected_calls = [
            mock.call(
                row_index=0, raw_row=first_raw, missing_fields=first_missing,
                invalid_fields=first_invalid,
                validation_error="row is not an object", **expected_common,
            ),
            mock.call(
                row_index=1, raw_row=second_raw, missing_fields=second_missing,
                invalid_fields=second_invalid,
                validation_error="invalid pagu", **expected_common,
            ),
        ]
        self.assertEqual(expected_calls, builder.call_args_list)
        self.assertIs(first_raw, builder.call_args_list[0].kwargs["raw_row"])
        self.assertIs(first_missing, builder.call_args_list[0].kwargs["missing_fields"])
        self.assertIs(second_invalid, builder.call_args_list[1].kwargs["invalid_fields"])
        self.assertIs(first_record, result[0])
        self.assertIs(second_record, result[1])
        self.assertEqual(prepared_before, prepared)
        append_page.assert_not_called()
        write_checkpoint.assert_not_called()
        write_evidence.assert_not_called()

    def test_empty_invalid_rows_returns_empty_without_builder_call(self):
        prepared = self.make_prepared_transaction([])
        with mock.patch.object(
            fetch_sirup_staging, "build_quarantine_record"
        ) as builder:
            result = fetch_sirup_staging.build_page_quarantine_records(
                prepared, "run-1", "evidence/page.json"
            )

        self.assertEqual([], result)
        builder.assert_not_called()

    def test_builder_error_propagates_unchanged(self):
        invalid_row = {
            "row_index": 0,
            "raw_row": "bad",
            "missing_fields": [],
            "invalid_fields": [],
            "validation_error": "bad row",
        }
        error = ValueError("builder rejected row")
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "build_quarantine_record",
                side_effect=error,
            ),
            mock.patch.object(
                fetch_sirup_staging, "write_validation_failure_evidence"
            ) as write_evidence,
        ):
            with self.assertRaises(ValueError) as raised:
                fetch_sirup_staging.build_page_quarantine_records(
                    self.make_prepared_transaction([invalid_row]),
                    "run-1",
                    "evidence/page.json",
                )

        self.assertIs(error, raised.exception)
        write_evidence.assert_not_called()


class PreparePageTransactionTests(unittest.TestCase):
    def test_prepares_read_only_transaction_with_exact_values(self):
        payload = {
            "recordsFiltered": 7,
            "data": [{"name": "Paket é", "id": 2}],
            "draw": 4,
        }
        payload_before = json.loads(json.dumps(payload))
        classification = {
            "valid_rows": payload["data"],
            "invalid_rows": [],
            "invalid_row_count": 0,
        }
        canonical_payload = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        expected_digest = hashlib.sha256(canonical_payload).hexdigest()
        expected_parameters = fetch_sirup_staging.page_request_params(
            2026, 5, 2, 4
        )
        with (
            mock.patch.object(
                fetch_sirup_staging,
                "classify_page",
                return_value=(classification, 7),
            ) as classify,
            mock.patch.object(
                fetch_sirup_staging,
                "page_request_params",
                wraps=fetch_sirup_staging.page_request_params,
            ) as request_parameters,
            mock.patch.object(
                fetch_sirup_staging,
                "utc_now",
                return_value="2026-08-06T01:02:03+00:00",
            ) as utc_now,
            mock.patch.object(fetch_sirup_staging, "append_page") as append_page,
            mock.patch.object(
                fetch_sirup_staging, "write_checkpoint"
            ) as write_checkpoint,
            mock.patch.object(
                fetch_sirup_staging, "write_validation_failure_evidence"
            ) as write_evidence,
        ):
            result = fetch_sirup_staging.prepare_page_transaction(
                payload, None, "run-1", 2026, 5, 2, 4, True
            )

        self.assertEqual(
            {
                "classification",
                "verified_source_count",
                "payload_sha256",
                "request_parameters",
                "page_identity",
                "captured_at",
            },
            set(result),
        )
        classify.assert_called_once_with(payload, None, 5, 2, True)
        self.assertIs(classification, result["classification"])
        self.assertEqual(7, result["verified_source_count"])
        self.assertEqual(expected_digest, result["payload_sha256"])
        request_parameters.assert_called_once_with(2026, 5, 2, 4)
        self.assertEqual(expected_parameters, result["request_parameters"])
        self.assertEqual(
            {
                "run_id": "run-1",
                "page_start": 5,
                "requested_length": 2,
                "page_draw": 4,
                "payload_sha256": expected_digest,
            },
            result["page_identity"],
        )
        self.assertEqual("2026-08-06T01:02:03+00:00", result["captured_at"])
        utc_now.assert_called_once_with()
        self.assertEqual(payload_before, payload)
        append_page.assert_not_called()
        write_checkpoint.assert_not_called()
        write_evidence.assert_not_called()

    def test_classification_error_propagates_unchanged(self):
        error = RuntimeError("classification failed")
        with (
            mock.patch.object(
                fetch_sirup_staging, "classify_page", side_effect=error
            ),
            mock.patch.object(fetch_sirup_staging, "utc_now") as utc_now,
            mock.patch.object(
                fetch_sirup_staging, "write_validation_failure_evidence"
            ) as write_evidence,
        ):
            with self.assertRaises(RuntimeError) as raised:
                fetch_sirup_staging.prepare_page_transaction(
                    {"recordsFiltered": 1, "data": []},
                    None, "run-1", 2026, 0, 1, 1, False,
                )

        self.assertIs(error, raised.exception)
        utc_now.assert_not_called()
        write_evidence.assert_not_called()


class ValidatePageClassifierIntegrationTests(unittest.TestCase):
    def test_classify_page_returns_complete_classifier_result_unchanged(self):
        payload = {"recordsFiltered": 5, "data": [{"source": 1}]}
        classification = {
            "valid_rows": [],
            "invalid_rows": [{"validation_error": "invalid"}],
            "invalid_row_count": 1,
        }
        with mock.patch.object(
            fetch_sirup_staging,
            "classify_page_rows",
            return_value=classification,
        ) as classify:
            result, source_count = fetch_sirup_staging.classify_page(
                payload, None, 4, 3, True
            )

        classify.assert_called_once_with(payload, 1, fetch_sirup_staging.REQUIRED_FIELDS)
        self.assertIs(classification, result)
        self.assertEqual(5, source_count)

    def test_classify_page_preserves_source_count_verification(self):
        payload = {"recordsFiltered": 3, "data": []}
        with mock.patch.object(fetch_sirup_staging, "classify_page_rows") as classify:
            with self.assertRaisesRegex(
                RuntimeError, "source record count changed: expected 2, observed 3"
            ):
                fetch_sirup_staging.classify_page(payload, 2, 0, 1, False)

        classify.assert_not_called()

    def test_classify_page_has_no_failure_evidence_side_effect(self):
        payload = {"recordsFiltered": "invalid", "data": []}
        with mock.patch.object(
            fetch_sirup_staging, "write_validation_failure_evidence"
        ) as write_evidence:
            with self.assertRaisesRegex(RuntimeError, "is not an integer"):
                fetch_sirup_staging.classify_page(payload, None, 0, 1, False)

        write_evidence.assert_not_called()

    def test_validate_page_remains_the_strict_wrapper(self):
        payload = {"recordsFiltered": 1, "data": ["bad"]}
        classification = {
            "valid_rows": [],
            "invalid_rows": [{"validation_error": "strict invalid row"}],
            "invalid_row_count": 1,
        }
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(
                fetch_sirup_staging,
                "classify_page",
                return_value=(classification, 1),
            ) as classify,
            mock.patch.object(
                fetch_sirup_staging, "write_validation_failure_evidence"
            ) as write_evidence,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "page row validation failed: strict invalid row"
            ):
                validate_page(
                    Path(temporary_directory), payload, None, 2026, 0, 1, 1, False
                )

        classify.assert_called_once_with(payload, None, 0, 1, False)
        write_evidence.assert_called_once()

    def test_delegates_classification_and_returns_valid_rows_unchanged(self):
        payload = {"recordsFiltered": 2, "data": [{"source": 1}, {"source": 2}]}
        valid_rows = payload["data"]
        classification = {
            "valid_rows": valid_rows,
            "invalid_rows": [],
            "invalid_row_count": 0,
        }
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(
                fetch_sirup_staging,
                "classify_page_rows",
                return_value=classification,
            ) as classify,
        ):
            result, source_count = validate_page(
                Path(temporary_directory), payload, None, 2026, 0, 2, 1, False
            )

        classify.assert_called_once_with(payload, 2, fetch_sirup_staging.REQUIRED_FIELDS)
        self.assertIs(valid_rows, result)
        self.assertEqual(2, source_count)

    def test_invalid_classifier_result_raises_with_validation_detail(self):
        payload = {"recordsFiltered": 1, "data": ["bad"]}
        classification = {
            "valid_rows": [],
            "invalid_rows": [{"validation_error": "row 0 is not an object"}],
            "invalid_row_count": 1,
        }
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(
                fetch_sirup_staging,
                "classify_page_rows",
                return_value=classification,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "row 0 is not an object"):
                validate_page(
                    Path(temporary_directory), payload, None, 2026, 0, 1, 1, False
                )

    def test_source_count_mismatch_is_rejected_before_classification(self):
        payload = {"recordsFiltered": 3, "data": []}
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            mock.patch.object(fetch_sirup_staging, "classify_page_rows") as classify,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "source record count changed: expected 2, observed 3"
            ):
                validate_page(
                    Path(temporary_directory), payload, 2, 2026, 0, 1, 1, False
                )

        classify.assert_not_called()


class CliModeBoundaryTests(unittest.TestCase):
    def test_mode_defaults_to_strict(self):
        with mock.patch.object(sys, "argv", ["fetch_sirup_staging.py", "--year", "2026"]):
            self.assertEqual("strict", fetch_sirup_staging.parse_args().mode)

    def test_explicit_strict_mode(self):
        arguments = [
            "fetch_sirup_staging.py",
            "--year",
            "2026",
            "--mode",
            "strict",
        ]
        with mock.patch.object(sys, "argv", arguments):
            self.assertEqual("strict", fetch_sirup_staging.parse_args().mode)

    def test_checkpoint_mode_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            strict_config = fetch_sirup_staging.checkpoint_config(
                2026, 100, True, "strict"
            )
            fetch_sirup_staging.write_checkpoint(
                checkpoint,
                strict_config,
                root / "run",
                source_rows_processed=200,
                canonical_rows_collected=200,
                quarantine_rows=0,
                source_count=300,
                page_count=2,
                started_at="2026-08-04T00:00:00+00:00",
                retries_used=0,
            )

            with self.assertRaisesRegex(RuntimeError, "checkpoint mode mismatch"):
                fetch_sirup_staging.load_checkpoint(
                    checkpoint,
                    fetch_sirup_staging.checkpoint_config(
                        2026, 100, True, "quarantine"
                    ),
                )

    def test_quarantine_mode_requires_checkpoint_without_old_runtime_guard(self):
        arguments = [
            "fetch_sirup_staging.py",
            "--year",
            "2026",
            "--mode",
            "quarantine",
        ]
        with (
            mock.patch.object(sys, "argv", arguments),
            mock.patch.object(fetch_sirup_staging.requests, "Session") as session,
            mock.patch("sys.stderr", io.StringIO()) as stderr,
        ):
            self.assertEqual(1, fetch_sirup_staging.main())

        session.assert_called_once_with()
        self.assertIn("quarantine mode requires --checkpoint", stderr.getvalue())
        self.assertNotIn("quarantine mode is not implemented", stderr.getvalue())


class CheckpointAtomicWriteTests(unittest.TestCase):
    def write_checkpoint(self, checkpoint: Path) -> None:
        fetch_sirup_staging.write_checkpoint(
            checkpoint,
            fetch_sirup_staging.checkpoint_config(2026, 100, True),
            checkpoint.parent / "run",
            source_rows_processed=244_500,
            canonical_rows_collected=244_500,
            quarantine_rows=0,
            source_count=300_000,
            page_count=2_445,
            started_at="2026-08-04T00:00:00+00:00",
            retries_used=3,
        )

    def test_transient_permission_error_is_retried_then_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            original_replace = Path.replace
            replace_attempts = 0

            def transient_replace(source, target):
                nonlocal replace_attempts
                replace_attempts += 1
                if replace_attempts == 1:
                    raise PermissionError("temporarily locked")
                return original_replace(source, target)

            with (
                mock.patch.object(Path, "replace", autospec=True, side_effect=transient_replace),
                mock.patch.object(fetch_sirup_staging.time, "sleep") as sleep,
            ):
                self.write_checkpoint(checkpoint)

            self.assertEqual(2, replace_attempts)
            sleep.assert_called_once_with(0.5)
            written = json.loads(checkpoint.read_text())
            self.assertEqual(244_500, written["canonical_rows_collected"])
            self.assertFalse(checkpoint.with_suffix(".json.tmp").exists())

    def test_repeated_permission_error_exhausts_attempts_and_leaves_temp(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            error = PermissionError("still locked")

            with (
                mock.patch.object(Path, "replace", autospec=True, side_effect=error) as replace,
                mock.patch.object(fetch_sirup_staging.time, "sleep") as sleep,
            ):
                with self.assertRaises(PermissionError) as raised:
                    self.write_checkpoint(checkpoint)

            self.assertIs(error, raised.exception)
            self.assertEqual(10, replace.call_count)
            self.assertEqual(9, sleep.call_count)
            self.assertTrue(checkpoint.with_suffix(".json.tmp").is_file())

    def test_non_permission_error_is_not_retried(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            error = OSError("unexpected failure")

            with (
                mock.patch.object(Path, "replace", autospec=True, side_effect=error) as replace,
                mock.patch.object(fetch_sirup_staging.time, "sleep") as sleep,
            ):
                with self.assertRaises(OSError) as raised:
                    self.write_checkpoint(checkpoint)

            self.assertIs(error, raised.exception)
            replace.assert_called_once()
            sleep.assert_not_called()
            self.assertTrue(checkpoint.with_suffix(".json.tmp").is_file())


class CheckpointV3Tests(unittest.TestCase):
    def config(self) -> dict[str, object]:
        return fetch_sirup_staging.checkpoint_config(2026, 100, True)

    def write_checkpoint(self, checkpoint: Path, run_dir: Path) -> dict[str, object]:
        fetch_sirup_staging.write_checkpoint(
            checkpoint,
            self.config(),
            run_dir,
            source_rows_processed=200,
            canonical_rows_collected=200,
            quarantine_rows=0,
            source_count=3_300_013,
            page_count=2,
            started_at="2026-08-04T00:00:00+00:00",
            retries_used=1,
        )
        return json.loads(checkpoint.read_text(encoding="utf-8"))

    def test_checkpoint_contains_exact_v3_fields_and_strict_invariants(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            run_dir = root / "run"
            written = self.write_checkpoint(checkpoint, run_dir)

            self.assertEqual(
                {
                    "checkpoint_version",
                    "config",
                    "run_dir",
                    "database_path",
                    "quarantine_path",
                    "source_count",
                    "source_rows_processed",
                    "canonical_rows_collected",
                    "quarantine_rows",
                    "next_start",
                    "last_completed_page",
                    "retries_used",
                    "started_at",
                },
                set(written),
            )
            self.assertEqual(3, written["checkpoint_version"])
            self.assertEqual("strict", written["config"]["mode"])
            self.assertEqual(200, written["source_rows_processed"])
            self.assertEqual(200, written["canonical_rows_collected"])
            self.assertEqual(0, written["quarantine_rows"])
            self.assertEqual(written["source_rows_processed"], written["next_start"])
            self.assertNotIn("rows_collected", written)

    def test_write_rejects_invalid_strict_accounting_before_temporary_write(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            base_arguments = {
                "path": checkpoint,
                "config": self.config(),
                "run_dir": root / "run",
                "source_count": 3_300_013,
                "page_count": 2,
                "started_at": "2026-08-04T00:00:00+00:00",
                "retries_used": 1,
            }

            with self.assertRaisesRegex(
                RuntimeError, "source_rows_processed to equal canonical_rows_collected"
            ):
                fetch_sirup_staging.write_checkpoint(
                    source_rows_processed=200,
                    canonical_rows_collected=199,
                    quarantine_rows=0,
                    **base_arguments,
                )
            self.assertFalse(checkpoint.with_suffix(".json.tmp").exists())

            with self.assertRaisesRegex(
                RuntimeError, "quarantine_rows to be zero"
            ):
                fetch_sirup_staging.write_checkpoint(
                    source_rows_processed=200,
                    canonical_rows_collected=200,
                    quarantine_rows=1,
                    **base_arguments,
                )
            self.assertFalse(checkpoint.with_suffix(".json.tmp").exists())

    def test_quarantine_path_is_deterministic_inside_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run_dir = root / "run"
            written = self.write_checkpoint(root / "checkpoint.json", run_dir)

            self.assertEqual(
                run_dir / fetch_sirup_staging.QUARANTINE_PATH_NAME,
                Path(written["quarantine_path"]),
            )
            self.assertFalse(Path(written["quarantine_path"]).exists())

    def test_v2_checkpoint_requires_explicit_migration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            checkpoint.write_text(
                json.dumps({"checkpoint_version": 2}), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                RuntimeError, "checkpoint v2 requires explicit migration"
            ):
                fetch_sirup_staging.load_checkpoint(checkpoint, self.config())

    def test_invalid_v3_accounting_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            written = self.write_checkpoint(checkpoint, root / "run")
            invalid_values = {
                "canonical_rows_collected": 199,
                "quarantine_rows": 1,
                "next_start": 199,
            }
            for field, value in invalid_values.items():
                with self.subTest(field=field):
                    invalid = dict(written)
                    invalid[field] = value
                    checkpoint.write_text(json.dumps(invalid), encoding="utf-8")
                    with self.assertRaisesRegex(
                        RuntimeError, "contents are inconsistent"
                    ):
                        fetch_sirup_staging.load_checkpoint(checkpoint, self.config())

    def test_load_returns_existing_runtime_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            run_dir = root / "run"
            self.write_checkpoint(checkpoint, run_dir)

            loaded = fetch_sirup_staging.load_checkpoint(checkpoint, self.config())

            self.assertEqual(
                (
                    run_dir.resolve(),
                    200,
                    200,
                    0,
                    3_300_013,
                    2,
                    "2026-08-04T00:00:00+00:00",
                    1,
                ),
                loaded,
            )

    def test_valid_quarantine_checkpoint_write_and_load(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            config = fetch_sirup_staging.checkpoint_config(
                2026, 100, True, mode="quarantine"
            )
            fetch_sirup_staging.write_checkpoint(
                checkpoint,
                config,
                root / "run",
                source_rows_processed=200,
                canonical_rows_collected=197,
                quarantine_rows=3,
                source_count=3_300_013,
                page_count=2,
                started_at="2026-08-04T00:00:00+00:00",
                retries_used=1,
            )

            written = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(200, written["next_start"])
            self.assertEqual(
                (root / "run").resolve(),
                fetch_sirup_staging.load_checkpoint(checkpoint, config)[0],
            )

    def test_invalid_quarantine_accounting_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checkpoint = root / "checkpoint.json"
            config = fetch_sirup_staging.checkpoint_config(
                2026, 100, True, mode="quarantine"
            )
            with self.assertRaisesRegex(RuntimeError, "quarantine checkpoint requires"):
                fetch_sirup_staging.write_checkpoint(
                    checkpoint, config, root / "run", 200, 198, 3, 300, 2, "now", 0
                )
            fetch_sirup_staging.write_checkpoint(
                checkpoint, config, root / "run", 200, 197, 3, 300, 2, "now", 0
            )
            invalid = json.loads(checkpoint.read_text(encoding="utf-8"))
            invalid["canonical_rows_collected"] = 198
            checkpoint.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "contents are inconsistent"):
                fetch_sirup_staging.load_checkpoint(checkpoint, config)

    def test_strict_behavior_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            with self.assertRaisesRegex(RuntimeError, "quarantine_rows to be zero"):
                fetch_sirup_staging.write_checkpoint(
                    checkpoint, self.config(), checkpoint.parent / "run",
                    200, 200, 1, 300, 2, "now", 0,
                )

    def test_unsupported_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            checkpoint = Path(temporary_directory) / "checkpoint.json"
            config = fetch_sirup_staging.checkpoint_config(
                2026, 100, True, mode="future"
            )
            with self.assertRaisesRegex(RuntimeError, "unsupported checkpoint mode"):
                fetch_sirup_staging.write_checkpoint(
                    checkpoint, config, checkpoint.parent / "run",
                    0, 0, 0, 0, 0, "now", 0,
                )
            written = self.write_checkpoint(checkpoint, checkpoint.parent / "run")
            written["config"] = config
            checkpoint.write_text(json.dumps(written), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsupported checkpoint mode"):
                fetch_sirup_staging.load_checkpoint(checkpoint, config)


class QuarantineRuntimeIntegrationTests(unittest.TestCase):
    def arguments(self, staging_root, checkpoint):
        return [
            "fetch_sirup_staging.py",
            "--year",
            "2026",
            "--mode",
            "quarantine",
            "--page-size",
            "2",
            "--max-rows",
            "2",
            "--staging-root",
            str(staging_root),
            "--checkpoint",
            str(checkpoint),
        ]

    def test_one_page_uses_prepare_then_orchestration_and_advances_accounting(self):
        payload = {"recordsFiltered": 2, "data": [{"id": 1}, {"bad": True}]}
        prepared = {
            "verified_source_count": 2,
            "classification": {
                "valid_rows": [{"id": 1}],
                "invalid_rows": [{"row_index": 1}],
            },
        }
        events = []

        def prepare(*args):
            events.append("prepare")
            return prepared

        def persist(*args):
            events.append("persist")
            self.assertEqual(0, args[6])
            self.assertEqual(0, args[7])
            self.assertEqual(0, args[8])
            self.assertEqual(2, args[12])
            self.assertEqual(1, args[13])
            self.assertEqual(1, args[15])
            return {
                "persistence_result": {"persisted": True},
                "next_accounting": {
                    "source_rows_processed": 2,
                    "canonical_rows_collected": 1,
                    "quarantine_rows": 1,
                },
            }

        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            checkpoint = staging_root / "checkpoint.json"
            with (
                mock.patch.object(sys, "argv", self.arguments(staging_root, checkpoint)),
                mock.patch.object(fetch_sirup_staging, "initialize_database"),
                mock.patch.object(
                    fetch_sirup_staging, "fetch_page", return_value=(payload, 1)
                ) as fetch,
                mock.patch.object(
                    fetch_sirup_staging,
                    "prepare_page_transaction",
                    side_effect=prepare,
                ) as prepare_page,
                mock.patch.object(
                    fetch_sirup_staging,
                    "persist_account_and_checkpoint_page",
                    side_effect=persist,
                ) as persist_page,
                mock.patch.object(fetch_sirup_staging, "validate_page") as validate,
                mock.patch.object(fetch_sirup_staging, "append_page") as append,
                mock.patch.object(fetch_sirup_staging, "write_checkpoint") as checkpoint_write,
                mock.patch.object(
                    fetch_sirup_staging,
                    "verify_database",
                    return_value=(1, 1, 1, 1),
                ) as verify,
                mock.patch.object(fetch_sirup_staging, "sha256_file", return_value="digest"),
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                self.assertEqual(0, fetch_sirup_staging.main())

            self.assertEqual(["prepare", "persist"], events)
            fetch.assert_called_once()
            prepare_page.assert_called_once()
            prepare_args = prepare_page.call_args.args
            self.assertIs(payload, prepare_args[0])
            self.assertEqual((None, mock.ANY, 2026, 0, 2, 1, False), prepare_args[1:])
            persist_page.assert_called_once()
            persist_args = persist_page.call_args.args
            run_dir = persist_args[11]
            self.assertEqual(run_dir / "sirup_staging.duckdb", persist_args[0])
            self.assertEqual(run_dir / fetch_sirup_staging.QUARANTINE_PATH_NAME, persist_args[1])
            self.assertIs(prepared, persist_args[2])
            self.assertEqual(
                run_dir / "failures" / "page-start-0-draw-1.json",
                persist_args[5],
            )
            validate.assert_not_called()
            append.assert_not_called()
            checkpoint_write.assert_not_called()
            verify.assert_called_once()
            self.assertNotIn("quarantine mode is not implemented", stderr.getvalue())

    def test_preparation_failure_prevents_persistence(self):
        error = RuntimeError("preparation failed")
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            checkpoint = staging_root / "checkpoint.json"
            with (
                mock.patch.object(sys, "argv", self.arguments(staging_root, checkpoint)),
                mock.patch.object(fetch_sirup_staging, "initialize_database"),
                mock.patch.object(
                    fetch_sirup_staging,
                    "fetch_page",
                    return_value=({"recordsFiltered": 2, "data": []}, 0),
                ),
                mock.patch.object(
                    fetch_sirup_staging,
                    "prepare_page_transaction",
                    side_effect=error,
                ),
                mock.patch.object(
                    fetch_sirup_staging, "persist_account_and_checkpoint_page"
                ) as persist,
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                self.assertEqual(1, fetch_sirup_staging.main())
            persist.assert_not_called()
            self.assertIn("preparation failed", stderr.getvalue())

    def test_orchestration_failure_does_not_reach_final_validation(self):
        error = OSError("page persistence failed")
        prepared = {"verified_source_count": 2, "classification": {}}
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            checkpoint = staging_root / "checkpoint.json"
            with (
                mock.patch.object(sys, "argv", self.arguments(staging_root, checkpoint)),
                mock.patch.object(fetch_sirup_staging, "initialize_database"),
                mock.patch.object(
                    fetch_sirup_staging,
                    "fetch_page",
                    return_value=({"recordsFiltered": 2, "data": []}, 1),
                ),
                mock.patch.object(
                    fetch_sirup_staging,
                    "prepare_page_transaction",
                    return_value=prepared,
                ),
                mock.patch.object(
                    fetch_sirup_staging,
                    "persist_account_and_checkpoint_page",
                    side_effect=error,
                ) as persist,
                mock.patch.object(fetch_sirup_staging, "verify_database") as verify,
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                self.assertEqual(1, fetch_sirup_staging.main())
            persist.assert_called_once()
            self.assertEqual((0, 0, 0), persist.call_args.args[6:9])
            verify.assert_not_called()
            self.assertIn("page persistence failed", stderr.getvalue())

    def test_resume_reconciles_quarantine_store_before_fetch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            run_dir = staging_root.resolve() / "run"
            run_dir.mkdir()
            (run_dir / "sirup_staging.duckdb").touch()
            checkpoint = staging_root / "checkpoint.json"
            checkpoint.touch()
            arguments = self.arguments(staging_root, checkpoint)
            loaded = (run_dir, 2, 1, 1, 10, 1, "started", 0)
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    fetch_sirup_staging, "load_checkpoint", return_value=loaded
                ),
                mock.patch.object(
                    fetch_sirup_staging, "verify_database", return_value=(1, 1, 1, 1)
                ),
                mock.patch.object(
                    fetch_sirup_staging, "count_quarantine_records", return_value=0
                ) as count,
                mock.patch.object(fetch_sirup_staging, "fetch_page") as fetch,
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                self.assertEqual(1, fetch_sirup_staging.main())
            count.assert_called_once_with(run_dir / fetch_sirup_staging.QUARANTINE_PATH_NAME)
            fetch.assert_not_called()
            self.assertIn("quarantine count", stderr.getvalue())


class QuarantineResumeRecoveryWiringTests(unittest.TestCase):
    def arguments(self, staging_root, checkpoint, max_rows):
        return [
            "fetch_sirup_staging.py",
            "--year",
            "2026",
            "--mode",
            "quarantine",
            "--page-size",
            "2",
            "--max-rows",
            str(max_rows),
            "--staging-root",
            str(staging_root),
            "--checkpoint",
            str(checkpoint),
        ]

    def run_recovery(
        self,
        valid,
        invalid,
        proof_error=None,
        derivation_error=None,
        repair_error=None,
        base_canonical=1,
        base_quarantine=1,
        continue_rows=0,
    ):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        staging_root = Path(temporary_directory.name)
        run_dir = staging_root.resolve() / "run"
        run_dir.mkdir()
        (run_dir / "sirup_staging.duckdb").touch()
        checkpoint = staging_root / "checkpoint.json"
        checkpoint.touch()
        page_size = valid + invalid
        base_source = base_canonical + base_quarantine
        target_count = base_source + page_size + continue_rows
        repaired = {
            "source_rows_processed": base_source + page_size,
            "canonical_rows_collected": base_canonical + valid,
            "quarantine_rows": base_quarantine + invalid,
        }
        prepared = {
            "verified_source_count": target_count,
            "classification": {
                "valid_rows": [{"id": index} for index in range(valid)],
                "invalid_rows": [{"row_index": index} for index in range(invalid)],
            },
        }
        normal_prepared = {
            "verified_source_count": target_count,
            "classification": {
                "valid_rows": [{"id": "next-valid"}],
                "invalid_rows": [{"row_index": "next-invalid"}],
            },
        }
        verification = {
            "verified": True,
            "canonical_page_count": valid,
            "quarantine_page_count": invalid,
            "expected_canonical_total": repaired["canonical_rows_collected"],
            "expected_quarantine_total": repaired["quarantine_rows"],
        }
        events = []
        real_classifier = (
            fetch_sirup_staging.classify_quarantine_resume_physical_state
        )

        def classify(*args):
            events.append("classify")
            return real_classifier(*args)

        def fetch(*args, **kwargs):
            events.append("fetch_page")
            return {"recordsFiltered": target_count, "data": []}, 2

        def prepare(*args):
            events.append("prepare_page_transaction")
            return prepared if events.count("prepare_page_transaction") == 1 else normal_prepared

        def prove(*args):
            events.append("verify_quarantine_replay_candidate")
            if proof_error is not None:
                raise proof_error
            return verification

        def derive(*args):
            events.append("derive_quarantine_replay_reconciliation")
            if derivation_error is not None:
                raise derivation_error
            return repaired

        def repair(*args):
            events.append("write_quarantine_replay_reconciliation_checkpoint")
            if repair_error is not None:
                raise repair_error
            return repaired

        def persist(*args):
            events.append("persist_account_and_checkpoint_page")
            return {
                "persistence_result": {"persisted": True},
                "next_accounting": {
                    "source_rows_processed": target_count,
                    "canonical_rows_collected": repaired[
                        "canonical_rows_collected"
                    ] + 1,
                    "quarantine_rows": repaired["quarantine_rows"] + 1,
                },
            }

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    sys,
                    "argv",
                    self.arguments(staging_root, checkpoint, target_count),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "load_checkpoint",
                    return_value=(
                        run_dir,
                        base_source,
                        base_canonical,
                        base_quarantine,
                        target_count,
                        1,
                        "started",
                        5,
                    ),
                )
            )
            database_result = (
                base_canonical + valid,
                base_canonical + valid,
                None if base_canonical + valid == 0 else 1,
                None if base_canonical + valid == 0 else 10,
            )
            final_database_result = (
                base_canonical + valid + (1 if continue_rows else 0),
                base_canonical + valid + (1 if continue_rows else 0),
                None
                if base_canonical + valid + (1 if continue_rows else 0) == 0
                else 1,
                None
                if base_canonical + valid + (1 if continue_rows else 0) == 0
                else 10,
            )
            verify_database = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "verify_database",
                    side_effect=[database_result, final_database_result],
                )
            )
            stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "count_quarantine_records",
                    return_value=base_quarantine + invalid,
                )
            )
            classifier = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "classify_quarantine_resume_physical_state",
                    side_effect=classify,
                )
            )
            fetch_page = stack.enter_context(
                mock.patch.object(fetch_sirup_staging, "fetch_page", side_effect=fetch)
            )
            prepare_page = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "prepare_page_transaction",
                    side_effect=prepare,
                )
            )
            replay_proof = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "verify_quarantine_replay_candidate",
                    side_effect=prove,
                )
            )
            reconciliation = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "derive_quarantine_replay_reconciliation",
                    side_effect=derive,
                )
            )
            checkpoint_repair = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "write_quarantine_replay_reconciliation_checkpoint",
                    side_effect=repair,
                )
            )
            persist = stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "persist_account_and_checkpoint_page",
                    side_effect=persist,
                )
            )
            stack.enter_context(
                mock.patch.object(fetch_sirup_staging, "sha256_file", return_value="digest")
            )
            stderr = stack.enter_context(mock.patch("sys.stderr", io.StringIO()))
            result = fetch_sirup_staging.main()
        return {
            "result": result,
            "stderr": stderr.getvalue(),
            "events": events,
            "run_dir": run_dir,
            "checkpoint": checkpoint,
            "prepared": prepared,
            "normal_prepared": normal_prepared,
            "verification": verification,
            "repaired": repaired,
            "classifier": classifier,
            "fetch": fetch_page,
            "prepare": prepare_page,
            "proof": replay_proof,
            "derive": reconciliation,
            "repair": checkpoint_repair,
            "persist": persist,
            "verify_database": verify_database,
        }

    def test_replay_candidate_exact_order_and_checkpoint_metadata(self):
        outcome = self.run_recovery(1, 1)
        self.assertEqual(0, outcome["result"])
        self.assertEqual(
            [
                "classify",
                "fetch_page",
                "prepare_page_transaction",
                "verify_quarantine_replay_candidate",
                "derive_quarantine_replay_reconciliation",
                "write_quarantine_replay_reconciliation_checkpoint",
            ],
            outcome["events"],
        )
        outcome["classifier"].assert_called_once_with(1, 1, 2, 2, 2, 2)
        self.assertEqual(
            {"start": 2, "length": 2, "draw": 2, "timeout": 30, "retries": 2},
            outcome["fetch"].call_args.kwargs,
        )
        self.assertEqual(
            (4, "run", 2026, 2, 2, 2, False),
            outcome["prepare"].call_args.args[1:],
        )
        self.assertEqual(
            outcome["run_dir"] / "failures" / "page-start-2-draw-2.json",
            outcome["proof"].call_args.args[6],
        )
        repair_args = outcome["repair"].call_args.args
        self.assertIs(outcome["repaired"], repair_args[3])
        self.assertEqual((4, 2, "started", 7), repair_args[4:])

    def test_recovered_page_is_not_double_persisted(self):
        outcome = self.run_recovery(1, 1)
        outcome["persist"].assert_not_called()
        outcome["fetch"].assert_called_once()
        self.assertEqual(2, outcome["repair"].call_args.args[5])
        self.assertEqual(7, outcome["repair"].call_args.args[7])

    def test_next_normal_fetch_starts_at_repaired_offset(self):
        outcome = self.run_recovery(1, 1, continue_rows=2)
        self.assertEqual(0, outcome["result"])
        self.assertEqual(
            [2, 4], [call.kwargs["start"] for call in outcome["fetch"].call_args_list]
        )
        outcome["persist"].assert_called_once()
        self.assertIs(outcome["normal_prepared"], outcome["persist"].call_args.args[2])
        self.assertIsNot(outcome["prepared"], outcome["persist"].call_args.args[2])
        self.assertEqual((4, 2, 2), outcome["persist"].call_args.args[6:9])
        self.assertEqual(3, outcome["persist"].call_args.args[13])
        self.assertEqual(9, outcome["persist"].call_args.args[15])

    def test_invalid_only_first_page_with_zero_canonical_database_recovers(self):
        outcome = self.run_recovery(0, 2, base_canonical=0, base_quarantine=0)
        self.assertEqual(0, outcome["result"])
        outcome["classifier"].assert_called_once_with(0, 0, 0, 0, 2, 2)
        self.assertEqual(0, outcome["repaired"]["canonical_rows_collected"])

    def test_canonical_only_recovery_succeeds(self):
        outcome = self.run_recovery(2, 0)
        self.assertEqual(0, outcome["result"])
        self.assertEqual((3, 1), tuple(outcome["repaired"].values())[1:])

    def test_mixed_recovery_succeeds(self):
        outcome = self.run_recovery(1, 1)
        self.assertEqual(
            {
                "source_rows_processed": 4,
                "canonical_rows_collected": 2,
                "quarantine_rows": 2,
            },
            outcome["repaired"],
        )

    def test_proof_failure_prevents_derivation_and_checkpoint_repair(self):
        outcome = self.run_recovery(1, 1, proof_error=RuntimeError("proof failed"))
        self.assertEqual(1, outcome["result"])
        outcome["derive"].assert_not_called()
        outcome["repair"].assert_not_called()
        outcome["persist"].assert_not_called()

    def test_derivation_failure_prevents_checkpoint_repair(self):
        outcome = self.run_recovery(
            1, 1, derivation_error=ValueError("derivation failed")
        )
        self.assertEqual(1, outcome["result"])
        outcome["repair"].assert_not_called()
        outcome["persist"].assert_not_called()

    def test_checkpoint_repair_failure_stops_before_accounting_continues(self):
        error = PermissionError("repair failed")
        outcome = self.run_recovery(1, 1, repair_error=error)
        self.assertEqual(1, outcome["result"])
        self.assertIn("repair failed", outcome["stderr"])
        outcome["persist"].assert_not_called()
        self.assertEqual(1, outcome["verify_database"].call_count)

    def test_consistent_resume_performs_no_recovery_work(self):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        staging_root = Path(temporary_directory.name)
        run_dir = staging_root.resolve() / "run"
        run_dir.mkdir()
        (run_dir / "sirup_staging.duckdb").touch()
        checkpoint = staging_root / "checkpoint.json"
        checkpoint.touch()
        recovery_names = (
            "fetch_page",
            "prepare_page_transaction",
            "verify_quarantine_replay_candidate",
            "derive_quarantine_replay_reconciliation",
            "write_quarantine_replay_reconciliation_checkpoint",
        )
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(sys, "argv", self.arguments(staging_root, checkpoint, 2))
            )
            stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging,
                    "load_checkpoint",
                    return_value=(run_dir, 2, 1, 1, 2, 1, "started", 0),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging, "verify_database", return_value=(1, 1, 1, 1)
                )
            )
            stack.enter_context(
                mock.patch.object(
                    fetch_sirup_staging, "count_quarantine_records", return_value=1
                )
            )
            stack.enter_context(
                mock.patch.object(fetch_sirup_staging, "sha256_file", return_value="digest")
            )
            operations = [
                stack.enter_context(mock.patch.object(fetch_sirup_staging, name))
                for name in recovery_names
            ]
            self.assertEqual(0, fetch_sirup_staging.main())
        for operation in operations:
            operation.assert_not_called()

    def test_unsafe_and_behind_physical_states_fail_before_fetch(self):
        cases = (
            ((4, 4, 1, 4), 1, "more than one page"),
            ((0, 0, None, None), 1, "canonical count trails"),
            ((1, 1, 1, 1), 0, "quarantine count trails"),
        )
        for database_result, quarantine_count, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                staging_root = Path(directory)
                run_dir = staging_root.resolve() / "run"
                run_dir.mkdir()
                (run_dir / "sirup_staging.duckdb").touch()
                checkpoint = staging_root / "checkpoint.json"
                checkpoint.touch()
                with (
                    mock.patch.object(
                        sys, "argv", self.arguments(staging_root, checkpoint, 4)
                    ),
                    mock.patch.object(
                        fetch_sirup_staging,
                        "load_checkpoint",
                        return_value=(run_dir, 2, 1, 1, 4, 1, "started", 0),
                    ),
                    mock.patch.object(
                        fetch_sirup_staging,
                        "verify_database",
                        return_value=database_result,
                    ),
                    mock.patch.object(
                        fetch_sirup_staging,
                        "count_quarantine_records",
                        return_value=quarantine_count,
                    ),
                    mock.patch.object(fetch_sirup_staging, "fetch_page") as fetch,
                    mock.patch("sys.stderr", io.StringIO()) as stderr,
                ):
                    self.assertEqual(1, fetch_sirup_staging.main())
                fetch.assert_not_called()
                self.assertIn(message, stderr.getvalue())

    def test_strict_resume_never_uses_recovery_helpers(self):
        source = inspect.getsource(fetch_sirup_staging.main)
        tree = ast.parse(source)
        recovery_calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {
                "classify_quarantine_resume_physical_state",
                "verify_quarantine_replay_candidate",
                "derive_quarantine_replay_reconciliation",
                "write_quarantine_replay_reconciliation_checkpoint",
            }
        }
        self.assertEqual(
            {
                "classify_quarantine_resume_physical_state",
                "verify_quarantine_replay_candidate",
                "derive_quarantine_replay_reconciliation",
                "write_quarantine_replay_reconciliation_checkpoint",
            },
            recovery_calls,
        )
        quarantine_guard = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "args.mode == 'quarantine'"
            and any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "classify_quarantine_resume_physical_state"
                for child in ast.walk(node)
            )
        )
        guarded_calls = {
            child.func.id
            for child in ast.walk(quarantine_guard)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }
        self.assertTrue(recovery_calls.issubset(guarded_calls))


class StrictRuntimeAccountingTests(unittest.TestCase):
    @staticmethod
    def valid_row(identifier: int) -> dict[str, object]:
        return {
            "id": identifier,
            "id_referensi": "ref",
            "pagu": 1.0,
            "satuanKerja": "unit",
            "kldi": "agency",
            "lokasi": "location",
            "jenisPengadaan": "goods",
            "metode": "method",
            "sumberDana": "fund",
            "paket": "package",
            "pemilihan": "selection",
            "idBulan": 1,
        }

    def test_main_initializes_only_explicit_runtime_counters(self):
        source = inspect.getsource(fetch_sirup_staging.main)
        tree = ast.parse(source)
        zero_initialized = {
            node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and node.value.value == 0
        }

        self.assertTrue(
            {
                "source_rows_processed",
                "canonical_rows_collected",
                "quarantine_rows",
            }.issubset(zero_initialized)
        )
        self.assertNotIn(
            "rows_collected",
            {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)},
        )

    def test_new_run_uses_explicit_counters_and_advances_after_append(self):
        payload = {"recordsFiltered": 1, "data": [self.valid_row(123)]}
        events = []

        def append_page(*_args):
            events.append("append")

        def write_checkpoint(*_args, **kwargs):
            events.append("checkpoint")
            self.assertEqual(1, kwargs["source_rows_processed"])
            self.assertEqual(1, kwargs["canonical_rows_collected"])
            self.assertEqual(0, kwargs["quarantine_rows"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            checkpoint = staging_root / "checkpoint.json"
            arguments = [
                "fetch_sirup_staging.py",
                "--year",
                "2026",
                "--page-size",
                "1",
                "--max-rows",
                "1",
                "--staging-root",
                str(staging_root),
                "--checkpoint",
                str(checkpoint),
            ]
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(fetch_sirup_staging, "initialize_database"),
                mock.patch.object(
                    fetch_sirup_staging, "fetch_page", return_value=(payload, 0)
                ) as fetch_page,
                mock.patch.object(
                    fetch_sirup_staging,
                    "validate_page",
                    wraps=fetch_sirup_staging.validate_page,
                ) as validate_page,
                mock.patch.object(
                    fetch_sirup_staging, "append_page", side_effect=append_page
                ) as append,
                mock.patch.object(
                    fetch_sirup_staging, "prepare_page_transaction"
                ) as prepare,
                mock.patch.object(
                    fetch_sirup_staging, "persist_account_and_checkpoint_page"
                ) as quarantine_persist,
                mock.patch.object(
                    fetch_sirup_staging,
                    "write_checkpoint",
                    side_effect=write_checkpoint,
                ),
                mock.patch.object(
                    fetch_sirup_staging,
                    "verify_database",
                    return_value=(1, 1, 123, 123),
                ),
                mock.patch.object(fetch_sirup_staging, "sha256_file", return_value="digest"),
            ):
                self.assertEqual(0, fetch_sirup_staging.main())

            self.assertEqual(0, fetch_page.call_args.kwargs["start"])
            self.assertEqual(["append", "checkpoint"], events)
            validate_page.assert_called_once()
            append.assert_called_once()
            prepare.assert_not_called()
            quarantine_persist.assert_not_called()

    def test_resume_reconciles_database_with_canonical_counter(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            run_dir = staging_root.resolve() / "run"
            run_dir.mkdir()
            (run_dir / "sirup_staging.duckdb").touch()
            checkpoint = staging_root / "checkpoint.json"
            checkpoint.touch()
            arguments = [
                "fetch_sirup_staging.py",
                "--year",
                "2026",
                "--page-size",
                "100",
                "--full-snapshot",
                "--staging-root",
                str(staging_root),
                "--checkpoint",
                str(checkpoint),
            ]
            loaded = (run_dir, 200, 199, 0, 300, 2, "started", 0)
            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(
                    fetch_sirup_staging, "load_checkpoint", return_value=loaded
                ),
                mock.patch.object(
                    fetch_sirup_staging,
                    "verify_database",
                    return_value=(200, 200, 1, 200),
                ),
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                self.assertEqual(1, fetch_sirup_staging.main())

            self.assertIn("canonical count", stderr.getvalue())

class ValidationFailureEvidenceTests(unittest.TestCase):
    def test_missing_required_field_creates_evidence_without_advancing_state(self):
        payload = {
            "recordsFiltered": 10,
            "data": [{"id": 123}],
        }
        canonical_payload = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as temporary_directory:
            staging_root = Path(temporary_directory)
            checkpoint = staging_root / "checkpoint.json"
            stderr = io.StringIO()
            arguments = [
                "fetch_sirup_staging.py",
                "--year",
                "2026",
                "--page-size",
                "1",
                "--max-rows",
                "1",
                "--staging-root",
                str(staging_root),
                "--checkpoint",
                str(checkpoint),
            ]

            with (
                mock.patch.object(sys, "argv", arguments),
                mock.patch.object(fetch_sirup_staging, "initialize_database"),
                mock.patch.object(
                    fetch_sirup_staging, "fetch_page", return_value=(payload, 0)
                ),
                mock.patch.object(fetch_sirup_staging, "append_page") as append_page,
                mock.patch.object(
                    fetch_sirup_staging, "write_checkpoint"
                ) as write_checkpoint,
                mock.patch("sys.stderr", stderr),
            ):
                self.assertEqual(1, fetch_sirup_staging.main())

            append_page.assert_not_called()
            write_checkpoint.assert_not_called()
            self.assertIn("missing fields", stderr.getvalue())

            run_directories = [path for path in staging_root.iterdir() if path.is_dir()]
            self.assertEqual(1, len(run_directories))
            run_dir = run_directories[0]

            evidence_path = run_dir / "failures" / "page-start-0-draw-1.json"
            self.assertTrue(evidence_path.is_file())
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            self.assertEqual(0, evidence["start"])
            self.assertEqual(1, evidence["draw"])
            self.assertIn("missing fields", evidence["validation_error"])
            self.assertEqual(payload, evidence["payload"])
            self.assertEqual(
                hashlib.sha256(canonical_payload).hexdigest(),
                evidence["payload_sha256"],
            )

    def test_evidence_write_failure_preserves_original_validation_error(self):
        payload = {"recordsFiltered": 1, "data": [{"id": 123}]}
        with tempfile.TemporaryDirectory() as temporary_directory:
            with mock.patch(
                "fetch_sirup_staging.write_validation_failure_evidence",
                side_effect=OSError("disk unavailable"),
            ):
                with self.assertRaisesRegex(RuntimeError, "missing fields"):
                    validate_page(
                        Path(temporary_directory),
                        payload,
                        expected_source_count=None,
                        year=2026,
                        start=0,
                        length=1,
                        draw=1,
                        full_snapshot=False,
                    )


if __name__ == "__main__":
    unittest.main()
