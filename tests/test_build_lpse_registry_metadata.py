from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_lpse_registry import (
    DEFAULT_CSV,
    REGISTRY_ARTIFACT_ID,
    build_registry_artifact_metadata,
    load_registry_artifact_metadata,
)
from scripts.collect_lpse_detail_evidence import REGISTRY_PATH


class LpseRegistryArtifactMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.csv_path = Path(self.temp_dir.name) / REGISTRY_PATH.name
        self.metadata_path = Path(self.temp_dir.name) / "lpse_registry.metadata.json"
        self.content = b"nama_lpse,official_lpse_url\nLPSE Kabupaten Halmahera Tengah,https://spse.inaproc.id/haltengkab\n"
        self.csv_path.write_bytes(self.content)

    def write_metadata(self, metadata: dict[str, str]) -> None:
        self.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    def test_metadata_is_deterministic_and_identity_is_stable(self) -> None:
        first = build_registry_artifact_metadata(self.csv_path)
        second = build_registry_artifact_metadata(self.csv_path)

        self.assertEqual(first, second)
        self.assertEqual(first["registry_artifact_id"], REGISTRY_ARTIFACT_ID)

    def test_hash_binds_exact_collector_csv_and_version_is_content_sensitive(self) -> None:
        first = build_registry_artifact_metadata(self.csv_path)
        expected_digest = hashlib.sha256(self.content).hexdigest()

        self.assertEqual(REGISTRY_PATH, DEFAULT_CSV)
        self.assertEqual(first["registry_artifact_hash"], expected_digest)
        self.assertEqual(first["registry_version"], f"sha256:{expected_digest}")

        self.csv_path.write_bytes(self.content + b"LPSE Lain,https://example.test\n")
        changed = build_registry_artifact_metadata(self.csv_path)
        self.assertEqual(changed["registry_artifact_id"], first["registry_artifact_id"])
        self.assertNotEqual(changed["registry_artifact_hash"], first["registry_artifact_hash"])
        self.assertNotEqual(changed["registry_version"], first["registry_version"])

    def test_missing_or_invalid_metadata_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            load_registry_artifact_metadata(self.csv_path, self.metadata_path)

        valid = build_registry_artifact_metadata(self.csv_path)
        self.write_metadata({**valid, "registry_artifact_hash": "0" * 64})
        with self.assertRaises(ValueError):
            load_registry_artifact_metadata(self.csv_path, self.metadata_path)

        self.write_metadata(valid)
        self.assertEqual(load_registry_artifact_metadata(self.csv_path, self.metadata_path), valid)

    def test_missing_canonical_artifact_fails_closed(self) -> None:
        self.csv_path.unlink()
        with self.assertRaises(FileNotFoundError):
            build_registry_artifact_metadata(self.csv_path)


if __name__ == "__main__":
    unittest.main()
