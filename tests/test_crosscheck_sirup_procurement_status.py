import argparse
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import crosscheck_sirup_procurement_status as crosscheck  # noqa: E402
from sirup_snapshot_resolver import SnapshotResolutionError  # noqa: E402


class SirupDatabaseAuthorityTests(unittest.TestCase):
    def test_default_returns_canonical_resolver_result(self):
        canonical = Path("synthetic/canonical/sirup.duckdb").resolve()
        with mock.patch.object(
            crosscheck, "resolve_active_sirup_database", return_value=canonical
        ) as resolve:
            result = crosscheck.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()

    def test_explicit_path_wins_without_canonical_resolution(self):
        requested = "synthetic/explicit/sirup.duckdb"
        with mock.patch.object(
            crosscheck, "resolve_active_sirup_database"
        ) as resolve:
            result = crosscheck.resolve_sirup_db(requested)

        self.assertEqual(Path(requested), result)
        resolve.assert_not_called()

    def test_explicit_missing_path_preserves_load_boundary_failure(self):
        missing = Path("synthetic/missing.duckdb")
        args = argparse.Namespace(sirup_db=missing)

        with self.assertRaisesRegex(FileNotFoundError, "SiRUP DuckDB not found"):
            crosscheck.load_sirup(args)

    def test_canonical_resolver_failure_propagates_closed(self):
        failure = SnapshotResolutionError("canonical selection is invalid")
        with mock.patch.object(
            crosscheck, "resolve_active_sirup_database", side_effect=failure
        ) as resolve:
            with self.assertRaisesRegex(
                SnapshotResolutionError, "canonical selection is invalid"
            ):
                crosscheck.resolve_sirup_db(None)

        resolve.assert_called_once_with()

    def test_existing_legacy_named_database_does_not_influence_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy = base / "mia-automation" / "sirup_2026.duckdb"
            legacy.parent.mkdir()
            legacy.write_bytes(b"legacy")
            canonical = base / "canonical" / "sirup.duckdb"
            with mock.patch.object(
                crosscheck, "resolve_active_sirup_database", return_value=canonical
            ) as resolve:
                result = crosscheck.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()

    def test_argparse_sirup_database_default_is_optional(self):
        with mock.patch.object(sys, "argv", ["crosscheck_sirup_procurement_status.py"]):
            args = crosscheck.parse_args()

        self.assertIsNone(args.sirup_db)

    def test_default_resolution_does_not_scan_filesystem(self):
        canonical = Path("synthetic/canonical/sirup.duckdb")
        with (
            mock.patch.object(
                crosscheck, "resolve_active_sirup_database", return_value=canonical
            ),
            mock.patch.object(crosscheck.Path, "exists") as exists,
        ):
            result = crosscheck.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
