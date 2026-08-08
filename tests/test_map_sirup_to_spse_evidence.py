from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import map_sirup_to_spse_evidence as mapping  # noqa: E402
from sirup_snapshot_resolver import SnapshotResolutionError  # noqa: E402


class SirupDatabaseAuthorityTests(unittest.TestCase):
    def test_default_uses_canonical_resolver_result(self):
        canonical = Path("synthetic/canonical/sirup.duckdb").resolve()
        with mock.patch.object(
            mapping, "resolve_active_sirup_database", return_value=canonical
        ) as resolve:
            result = mapping.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()

    def test_explicit_override_wins_without_canonical_resolution(self):
        requested = "synthetic/explicit/sirup.duckdb"
        with mock.patch.object(mapping, "resolve_active_sirup_database") as resolve:
            result = mapping.resolve_sirup_db(requested)

        self.assertEqual(Path(requested), result)
        resolve.assert_not_called()

    def test_canonical_failure_propagates_without_legacy_fallback(self):
        failure = SnapshotResolutionError("selection authority is invalid")
        with (
            mock.patch.object(
                mapping, "resolve_active_sirup_database", side_effect=failure
            ) as resolve,
            mock.patch.object(mapping.Path, "exists") as exists,
        ):
            with self.assertRaisesRegex(
                SnapshotResolutionError, "selection authority is invalid"
            ):
                mapping.resolve_sirup_db(None)

        resolve.assert_called_once_with()
        exists.assert_not_called()

    def test_existing_legacy_named_database_does_not_influence_default(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy = base / "mia-automation" / "sirup_2026.duckdb"
            legacy.parent.mkdir()
            legacy.write_bytes(b"legacy")
            canonical = base / "canonical" / "sirup.duckdb"

            with mock.patch.object(
                mapping, "resolve_active_sirup_database", return_value=canonical
            ) as resolve:
                result = mapping.resolve_sirup_db(None)

        self.assertEqual(canonical, result)
        resolve.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
