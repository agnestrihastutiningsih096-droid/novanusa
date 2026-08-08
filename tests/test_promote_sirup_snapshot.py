import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import promote_sirup_snapshot as promotion  # noqa: E402


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SnapshotPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo" / "data" / "sirup"
        self.legacy = self.base / "mia-automation" / "sirup_2026.duckdb"
        self.legacy.parent.mkdir(parents=True)
        self.legacy.write_bytes(b"legacy-do-not-touch")

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def eligible(_run, _comparison):
        return {"result": "PASS", "promotion_eligible": True}

    @staticmethod
    def rejected(_run, _comparison):
        return {"result": "FAIL", "promotion_eligible": False}

    def make_run(self, name, database_bytes, baseline_sha256=None):
        run = self.base / "staging" / name
        run.mkdir(parents=True)
        database = run / promotion.STAGING_DATABASE_NAME
        database.write_bytes(database_bytes)
        manifest = {"run_id": name, "sha256": digest(database_bytes)}
        (run / promotion.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        comparison = {"status": "passed", "baseline_sha256": baseline_sha256}
        (run / "comparison.json").write_text(json.dumps(comparison), encoding="utf-8")
        return run

    def promote(self, run, expected=None):
        return promotion.promote(run, self.root, expected, evaluator=self.eligible)

    def selection(self):
        return json.loads((self.root / "selection.json").read_text(encoding="utf-8"))

    def test_first_promotion_has_null_rollback_and_preserves_sources(self):
        run = self.make_run("run-one", b"candidate-one")
        staging_before = (run / promotion.STAGING_DATABASE_NAME).read_bytes()
        legacy_before = self.legacy.read_bytes()
        result = self.promote(run)
        self.assertEqual(result["snapshot_id"], digest(b"candidate-one"))
        selection = self.selection()
        self.assertEqual(selection["active"]["snapshot_id"], digest(b"candidate-one"))
        self.assertIsNone(selection["rollback"])
        self.assertEqual(staging_before, (run / promotion.STAGING_DATABASE_NAME).read_bytes())
        self.assertEqual(legacy_before, self.legacy.read_bytes())

    def test_second_promotion_moves_previous_active_to_rollback(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", digest(b"one"))
        second_id = self.promote(second, first_id)["snapshot_id"]
        selection = self.selection()
        self.assertEqual(selection["rollback"]["snapshot_id"], first_id)
        self.assertEqual(selection["active"]["snapshot_id"], second_id)

    def test_third_promotion_moves_second_active_to_rollback(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", digest(b"one"))
        second_id = self.promote(second, first_id)["snapshot_id"]
        third = self.make_run("run-three", b"three", digest(b"two"))
        third_id = self.promote(third, second_id)["snapshot_id"]
        selection = self.selection()
        self.assertEqual(selection["active"]["snapshot_id"], third_id)
        self.assertEqual(selection["rollback"]["snapshot_id"], second_id)

    def test_selection_replacement_observes_only_complete_old_or_new_json(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", digest(b"one"))
        real_replace = os.replace
        observed = []

        def observing_replace(source, target):
            if Path(target).name == "selection.json":
                observed.append(self.selection())
                result = real_replace(source, target)
                observed.append(self.selection())
                return result
            return real_replace(source, target)

        with mock.patch.object(promotion.os, "replace", side_effect=observing_replace):
            second_id = self.promote(second, first_id)["snapshot_id"]
        self.assertEqual(observed[0]["active"]["snapshot_id"], first_id)
        self.assertIsNone(observed[0]["rollback"])
        self.assertEqual(observed[1]["active"]["snapshot_id"], second_id)
        self.assertEqual(observed[1]["rollback"]["snapshot_id"], first_id)

    def test_validator_rejection_prevents_canonical_mutation(self):
        run = self.make_run("rejected", b"no")
        with self.assertRaisesRegex(promotion.PromotionError, "validator rejected"):
            promotion.promote(run, self.root, None, evaluator=self.rejected)
        self.assertFalse(self.root.exists())

    def test_hash_mismatch_prevents_canonical_mutation(self):
        run = self.make_run("bad-hash", b"before")
        (run / promotion.STAGING_DATABASE_NAME).write_bytes(b"after")
        with self.assertRaisesRegex(promotion.PromotionError, "hash mismatch"):
            self.promote(run)
        self.assertFalse(self.root.exists())

    def test_missing_artifact_prevents_canonical_mutation(self):
        run = self.make_run("missing", b"candidate")
        (run / promotion.MANIFEST_NAME).unlink()
        with self.assertRaisesRegex(promotion.PromotionError, "missing"):
            self.promote(run)
        self.assertFalse(self.root.exists())

    def test_stale_expected_active_prevents_selection_mutation(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        selection_before = (self.root / "selection.json").read_bytes()
        second = self.make_run("run-two", b"two", digest(b"one"))
        with self.assertRaisesRegex(promotion.PromotionError, "stale expected-active"):
            self.promote(second, "0" * 64)
        self.assertEqual(selection_before, (self.root / "selection.json").read_bytes())
        self.assertEqual(first_id, self.selection()["active"]["snapshot_id"])

    def test_selection_replace_failure_leaves_entire_selection_unchanged(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", digest(b"one"))
        selection_before = (self.root / "selection.json").read_bytes()
        real_replace = promotion.os.replace

        def failing_replace(source, target):
            if Path(target).name == "selection.json":
                raise OSError("injected selection replace failure")
            return real_replace(source, target)

        with mock.patch.object(promotion.os, "replace", side_effect=failing_replace):
            with self.assertRaisesRegex(OSError, "injected"):
                self.promote(second, first_id)
        self.assertEqual(selection_before, (self.root / "selection.json").read_bytes())
        self.assertEqual(first_id, self.selection()["active"]["snapshot_id"])

    def test_compatible_inactive_installed_snapshot_can_be_retried(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", digest(b"one"))
        selection_before = (self.root / "selection.json").read_bytes()
        real_replace = promotion.os.replace

        def failing_replace(source, target):
            if Path(target).name == "selection.json":
                raise OSError("injected selection replace failure")
            return real_replace(source, target)

        with mock.patch.object(promotion.os, "replace", side_effect=failing_replace):
            with self.assertRaises(OSError):
                self.promote(second, first_id)
        second_id = digest(b"two")
        self.assertTrue((self.root / "snapshots" / second_id).is_dir())
        self.assertEqual(selection_before, (self.root / "selection.json").read_bytes())
        self.promote(second, first_id)
        self.assertEqual(second_id, self.selection()["active"]["snapshot_id"])

    def test_existing_conflicting_snapshot_is_rejected_without_overwrite(self):
        run = self.make_run("conflict", b"candidate")
        snapshot_id = digest(b"candidate")
        target = self.root / "snapshots" / snapshot_id
        target.mkdir(parents=True)
        (target / promotion.DATABASE_NAME).write_bytes(b"conflict")
        (target / promotion.MANIFEST_NAME).write_bytes(b"conflict")
        with self.assertRaisesRegex(promotion.PromotionError, "incompatible contents"):
            self.promote(run)
        self.assertEqual(b"conflict", (target / promotion.DATABASE_NAME).read_bytes())
        self.assertFalse((self.root / "selection.json").exists())

    def test_comparison_digest_must_match_current_active(self):
        first = self.make_run("run-one", b"one")
        first_id = self.promote(first)["snapshot_id"]
        second = self.make_run("run-two", b"two", "f" * 64)
        with self.assertRaisesRegex(promotion.PromotionError, "comparison baseline"):
            self.promote(second, first_id)
        self.assertEqual(first_id, self.selection()["active"]["snapshot_id"])


if __name__ == "__main__":
    unittest.main()
