import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import migrate_sirup_checkpoint_v2_to_v3 as migration  # noqa: E402


class MigrationTests(unittest.TestCase):
    def make_fixture(
        self,
        root: Path,
        ids=(1, 2, 3),
        rows_collected=None,
        next_start=None,
        checkpoint_version=2,
    ):
        run_dir = root / "v2-run"
        run_dir.mkdir()
        database_path = run_dir / "sirup_staging.duckdb"
        connection = duckdb.connect(str(database_path))
        try:
            connection.execute("create table sirup_raw (id bigint)")
            connection.executemany("insert into sirup_raw values (?)", [(value,) for value in ids])
        finally:
            connection.close()
        row_total = len(ids) if rows_collected is None else rows_collected
        checkpoint = {
            "checkpoint_version": checkpoint_version,
            "config": {
                "year": 2026,
                "page_size": 100,
                "full_snapshot": True,
                "source_endpoint": "https://example.invalid/source",
            },
            "run_dir": str(run_dir),
            "database_path": str(database_path),
            "rows_collected": row_total,
            "next_start": row_total if next_start is None else next_start,
            "source_count": 10,
            "last_completed_page": 1,
            "retries_used": 0,
            "started_at": "2026-08-04T00:00:00+00:00",
        }
        source_path = root / "checkpoint-v2.json"
        source_path.write_text(json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8")
        return {
            "run_dir": run_dir,
            "database_path": database_path,
            "source_path": source_path,
            "source_sha256": migration.sha256_file(source_path),
            "database_sha256": migration.sha256_file(database_path),
            "target_path": root / "checkpoint-v3.json",
        }

    def arguments(self, fixture, apply=False):
        arguments = [
            "migrate_sirup_checkpoint_v2_to_v3.py",
            "--source-checkpoint",
            str(fixture["source_path"]),
            "--target-checkpoint",
            str(fixture["target_path"]),
            "--expected-source-sha256",
            fixture["source_sha256"],
            "--expected-database-sha256",
            fixture["database_sha256"],
        ]
        if apply:
            arguments.append("--apply")
        return arguments

    def run_main(self, fixture, apply=False):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(sys, "argv", self.arguments(fixture, apply)),
            mock.patch("sys.stdout", stdout),
            mock.patch("sys.stderr", stderr),
        ):
            result = migration.main()
        return result, stdout.getvalue(), stderr.getvalue()

    def test_successful_dry_run_changes_no_files_and_prints_deterministic_plan(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fixture = self.make_fixture(root)
            before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}

            first_result, first_output, first_error = self.run_main(fixture)
            second_result, second_output, second_error = self.run_main(fixture)

            after = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            self.assertEqual(0, first_result)
            self.assertEqual(0, second_result)
            self.assertEqual(first_output, second_output)
            self.assertEqual("", first_error)
            self.assertEqual("", second_error)
            self.assertEqual(before, after)
            self.assertFalse(fixture["target_path"].exists())
            self.assertFalse(Path(str(fixture["target_path"]) + ".migration.json").exists())

    def test_successful_apply_creates_reconciled_v3_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory))
            source_bytes = fixture["source_path"].read_bytes()

            result, _, error = self.run_main(fixture, apply=True)

            self.assertEqual(0, result)
            self.assertEqual("", error)
            self.assertEqual(source_bytes, fixture["source_path"].read_bytes())
            checkpoint = json.loads(fixture["target_path"].read_text(encoding="utf-8"))
            evidence_path = Path(str(fixture["target_path"]) + ".migration.json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
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
                set(checkpoint),
            )
            self.assertNotIn("rows_collected", checkpoint)
            self.assertEqual("quarantine", checkpoint["config"]["mode"])
            self.assertEqual(
                checkpoint["source_rows_processed"], checkpoint["next_start"]
            )
            self.assertEqual(
                checkpoint["source_rows_processed"],
                checkpoint["canonical_rows_collected"] + checkpoint["quarantine_rows"],
            )
            self.assertEqual(3, checkpoint["canonical_rows_collected"])
            self.assertEqual(0, checkpoint["quarantine_rows"])
            self.assertEqual("PASS", evidence["decision"])
            self.assertEqual(fixture["source_sha256"], evidence["source_checkpoint_sha256"])
            self.assertEqual(fixture["database_sha256"], evidence["database_sha256"])
            self.assertEqual(
                {
                    "row_count": 3,
                    "distinct_id_count": 3,
                    "duplicate_count": 0,
                    "null_id_count": 0,
                },
                evidence["verified_duckdb_counts"],
            )
            self.assertFalse((fixture["run_dir"] / "quarantine").exists())

    def assert_plan_rejected(self, fixture, message):
        with self.assertRaisesRegex(RuntimeError, message):
            migration.build_plan(
                fixture["source_path"],
                fixture["target_path"],
                fixture["source_sha256"],
                fixture["database_sha256"],
            )

    def test_wrong_checkpoint_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory))
            fixture["source_sha256"] = "0" * 64
            self.assert_plan_rejected(fixture, "source checkpoint SHA-256 mismatch")

    def test_wrong_database_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory))
            fixture["database_sha256"] = "0" * 64
            self.assert_plan_rejected(fixture, "database SHA-256 mismatch")

    def test_duckdb_count_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory), rows_collected=2)
            self.assert_plan_rejected(fixture, "row count does not match rows_collected")

    def test_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory), ids=(1, 1, 2))
            self.assert_plan_rejected(fixture, "duplicate IDs")

    def test_null_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory), ids=(1, None, 2))
            self.assert_plan_rejected(fixture, "null IDs")

    def test_rows_collected_must_equal_next_start(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory), next_start=2)
            self.assert_plan_rejected(fixture, "rows_collected does not equal next_start")

    def test_non_v2_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory), checkpoint_version=3)
            self.assert_plan_rejected(fixture, "version must be 2")

    def test_existing_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory))
            fixture["target_path"].write_text("existing", encoding="utf-8")
            self.assert_plan_rejected(fixture, "target checkpoint already exists")

    def test_target_equal_to_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = self.make_fixture(Path(temporary_directory))
            fixture["target_path"] = fixture["source_path"]
            self.assert_plan_rejected(fixture, "must not equal source checkpoint")


if __name__ == "__main__":
    unittest.main()
