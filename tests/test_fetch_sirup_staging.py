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
