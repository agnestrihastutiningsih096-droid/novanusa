from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import expand_spse_evidence_targeted as expansion  # noqa: E402
from sirup_snapshot_resolver import SnapshotResolutionError  # noqa: E402


class SirupDatabaseAuthorityTests(unittest.TestCase):
    def test_default_returns_canonical_resolver_result(self):
        canonical = Path("synthetic/canonical/sirup.duckdb").resolve()
        with mock.patch.object(
            expansion, "resolve_active_sirup_database", return_value=canonical
        ) as resolve:
            result = expansion.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()

    def test_explicit_existing_path_wins_without_canonical_resolution(self):
        with tempfile.TemporaryDirectory() as temporary:
            requested = Path(temporary) / "explicit.duckdb"
            requested.write_bytes(b"synthetic")
            with mock.patch.object(
                expansion, "resolve_active_sirup_database"
            ) as resolve:
                result = expansion.resolve_sirup_db(str(requested))

        self.assertEqual(requested, result)
        resolve.assert_not_called()

    def test_explicit_missing_path_preserves_fail_closed_validation(self):
        requested = Path("synthetic/missing.duckdb")
        with mock.patch.object(
            expansion, "resolve_active_sirup_database"
        ) as resolve:
            with self.assertRaisesRegex(FileNotFoundError, "SiRUP DuckDB not found"):
                expansion.resolve_sirup_db(str(requested))

        resolve.assert_not_called()

    def test_canonical_resolver_failure_propagates_closed(self):
        failure = SnapshotResolutionError("canonical selection is invalid")
        with mock.patch.object(
            expansion, "resolve_active_sirup_database", side_effect=failure
        ) as resolve:
            with self.assertRaisesRegex(
                SnapshotResolutionError, "canonical selection is invalid"
            ):
                expansion.resolve_sirup_db(None)

        resolve.assert_called_once_with()

    def test_existing_legacy_named_database_does_not_influence_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy = base / "mia-automation" / "sirup_2026.duckdb"
            legacy.parent.mkdir()
            legacy.write_bytes(b"legacy")
            canonical = base / "canonical" / "sirup.duckdb"
            with mock.patch.object(
                expansion, "resolve_active_sirup_database", return_value=canonical
            ) as resolve:
                result = expansion.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()

    def test_default_resolution_does_not_scan_filesystem(self):
        canonical = Path("synthetic/canonical/sirup.duckdb")
        with (
            mock.patch.object(
                expansion, "resolve_active_sirup_database", return_value=canonical
            ),
            mock.patch.object(expansion.Path, "exists") as exists,
        ):
            result = expansion.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
