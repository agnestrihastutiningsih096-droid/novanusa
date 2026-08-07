import ast
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

    def test_quarantine_mode_is_rejected_before_collector_setup(self):
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

        session.assert_not_called()
        self.assertEqual("quarantine mode is not implemented\n", stderr.getvalue())


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
                    fetch_sirup_staging, "append_page", side_effect=append_page
                ),
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
