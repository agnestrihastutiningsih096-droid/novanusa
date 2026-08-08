import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import promote_sirup_snapshot as promotion  # noqa: E402
import sirup_snapshot_resolver as resolver  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SirupSnapshotResolverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "canonical"
        self.legacy = self.base / "mia-automation" / "sirup_2026.duckdb"
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_bytes(b"legacy-must-not-be-read")

    def tearDown(self):
        self.temporary.cleanup()

    def install_valid_authority(self):
        database_bytes = b"synthetic-duckdb"
        manifest_bytes = b'{"synthetic": true}\n'
        snapshot_id = digest(database_bytes)
        snapshot = self.root / "snapshots" / snapshot_id
        snapshot.mkdir(parents=True)
        database = snapshot / promotion.DATABASE_NAME
        manifest = snapshot / promotion.MANIFEST_NAME
        database.write_bytes(database_bytes)
        manifest.write_bytes(manifest_bytes)
        active = promotion.pointer_for(
            snapshot_id, digest(database_bytes), digest(manifest_bytes)
        )
        selection = promotion.selection_for(active, None)
        (self.root / "selection.json").write_text(
            json.dumps(selection), encoding="utf-8"
        )
        return database.resolve(), manifest, selection

    def assert_resolution_fails(self, pattern=None):
        context = self.assertRaises(resolver.SnapshotResolutionError)
        with context:
            resolver.resolve_active_sirup_database(self.root)
        if pattern is not None:
            self.assertRegex(str(context.exception), pattern)

    def test_valid_active_snapshot_resolves_to_absolute_database_path(self):
        database, _, _ = self.install_valid_authority()
        selection_before = (self.root / "selection.json").read_bytes()
        database_before = database.read_bytes()

        resolved = resolver.resolve_active_sirup_database(self.root)

        self.assertEqual(database, resolved)
        self.assertTrue(resolved.is_absolute())
        self.assertEqual(selection_before, (self.root / "selection.json").read_bytes())
        self.assertEqual(database_before, database.read_bytes())

    def test_missing_selection_fails_closed(self):
        self.assert_resolution_fails("invalid JSON artifact")

    def test_malformed_selection_json_fails_closed(self):
        self.root.mkdir()
        (self.root / "selection.json").write_text("{broken", encoding="utf-8")
        self.assert_resolution_fails("invalid JSON artifact")

    def test_missing_active_database_fails_closed(self):
        database, _, _ = self.install_valid_authority()
        database.unlink()
        self.assert_resolution_fails("missing snapshot artifacts")

    def test_missing_active_manifest_fails_closed(self):
        _, manifest, _ = self.install_valid_authority()
        manifest.unlink()
        self.assert_resolution_fails("missing snapshot artifacts")

    def test_database_hash_mismatch_fails_closed(self):
        database, _, _ = self.install_valid_authority()
        database.write_bytes(b"tampered")
        self.assert_resolution_fails("database hash mismatch")

    def test_manifest_hash_mismatch_fails_closed(self):
        _, manifest, _ = self.install_valid_authority()
        manifest.write_bytes(b"tampered")
        self.assert_resolution_fails("manifest hash mismatch")

    def test_unsupported_selection_version_fails_closed(self):
        self.install_valid_authority()
        path = self.root / "selection.json"
        selection = json.loads(path.read_text(encoding="utf-8"))
        selection["selection_version"] = 2
        path.write_text(json.dumps(selection), encoding="utf-8")
        self.assert_resolution_fails("unsupported version")

    def test_malformed_active_pointer_fails_closed(self):
        self.install_valid_authority()
        path = self.root / "selection.json"
        selection = json.loads(path.read_text(encoding="utf-8"))
        selection["active"]["unexpected"] = True
        path.write_text(json.dumps(selection), encoding="utf-8")
        self.assert_resolution_fails("invalid or unexpected fields")

    def test_escaping_active_path_fails_before_external_artifact_is_read(self):
        _, _, selection = self.install_valid_authority()
        selection["active"]["database"] = str(self.legacy)
        (self.root / "selection.json").write_text(
            json.dumps(selection), encoding="utf-8"
        )
        legacy_before = self.legacy.read_bytes()

        self.assert_resolution_fails("escapes canonical root")

        self.assertEqual(legacy_before, self.legacy.read_bytes())

    def test_missing_selection_never_falls_back_to_legacy_database(self):
        legacy_before = self.legacy.read_bytes()
        self.assert_resolution_fails()
        self.assertEqual(legacy_before, self.legacy.read_bytes())


if __name__ == "__main__":
    unittest.main()
