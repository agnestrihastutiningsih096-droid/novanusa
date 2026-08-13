import copy
import hashlib
import json
import os
import pickle
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest import mock

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import promote_sirup_snapshot as promotion  # noqa: E402
import compare_sirup_staging as comparison  # noqa: E402
import validate_sirup_promotion as validator  # noqa: E402
import sirup_receipt_chain as receipts  # noqa: E402


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
    def eligible(_run, _comparison, *_args, **_kwargs):
        return {"result": "PASS", "promotion_eligible": True}

    @staticmethod
    def rejected(_run, _comparison, *_args, **_kwargs):
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
        with (
            mock.patch.object(promotion, "evaluate", side_effect=self.eligible),
            mock.patch.object(
                promotion, "_evaluate_genesis", side_effect=self.eligible
            ),
        ):
            return promotion.promote(run, self.root, expected)

    def selection(self):
        return json.loads((self.root / "selection.json").read_text(encoding="utf-8"))

    def make_valid_run(self, name, identifier, baseline=None):
        run = (self.base / "acceptance" / name).resolve()
        run.mkdir(parents=True)
        database = run / promotion.STAGING_DATABASE_NAME
        connection = duckdb.connect(str(database))
        try:
            connection.execute(
                """
                create table sirup_raw (
                    id bigint primary key,
                    id_referensi varchar,
                    pagu double,
                    satuanKerja varchar,
                    kldi varchar,
                    lokasi varchar,
                    jenisPengadaan varchar,
                    metode varchar,
                    sumberDana varchar,
                    paket varchar,
                    pemilihan varchar,
                    idBulan integer
                )
                """
            )
            connection.execute(
                "insert into sirup_raw values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [identifier, f"ref-{identifier}", 1.0, "satker", "kldi", "lokasi",
                 "barang", "tender", "apbn", "paket", "pemilihan", 1],
            )
        finally:
            connection.close()

        database_hash = promotion.sha256_file(database)
        with receipts.ReceiptWriter(run) as writer:
            writer.append("ANCHOR", {
                "endpoint": validator.SOURCE_ENDPOINT, "year": 2026,
                "page_size": 100, "order_column": 11,
                "order_direction": "desc", "full_snapshot": True,
                "mode": "strict",
            }, timestamp="2026-01-01T00:00:00.000Z")
            writer.append("PAGE", {
                "start": 0, "page_size": 100, "returned_row_count": 1,
                "canonical_row_count": 1, "quarantined_row_count": 0,
                "page_rows_digest": digest(f"page-{identifier}".encode()),
                "source_count_observed": 1,
            }, timestamp="2026-01-01T00:00:30.000Z")
            terminal = writer.append("COMPLETION", {
                "terminal_reason": "NORMAL_COMPLETION", "processed": 1,
                "canonical_total": 1, "quarantine_total": 0,
                "source_count_start": 1, "source_count_end": 1,
                "drift_status": "NO_DRIFT", "duckdb_sha256": database_hash,
                "promotion_flag": False,
            }, timestamp="2026-01-01T00:01:00.000Z")
        manifest = {
            "manifest_version": 1,
            "run_id": name,
            "status": "validated_staging_sample",
            "full_snapshot": True,
            "source_endpoint": validator.SOURCE_ENDPOINT,
            "requested_year": 2026,
            "requested_limit": 1,
            "page_size": 100,
            "page_count": 1,
            "started_at": "2026-01-01T00:00:00+00:00",
            "collected_at": "2026-01-01T00:01:00+00:00",
            "database_path": str(database),
            "table_name": "sirup_raw",
            "row_count": 1,
            "distinct_id_count": 1,
            "min_id": identifier,
            "max_id": identifier,
            "sha256": database_hash,
            "chain_head": terminal["hash"],
            "source_records_filtered": 1,
            "request_count": 1,
            "retries_used": 0,
            "validation": {name: "passed" for name in validator.COLLECTOR_VALIDATION_GATES},
            "promotion_eligible": False,
            "promotion": {"attempted": False, "result": "not_in_scope"},
        }
        (run / promotion.MANIFEST_NAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        if baseline is not None:
            report = {"status": "passed", **comparison.compare(baseline, database)}
            (run / "comparison.json").write_text(json.dumps(report), encoding="utf-8")
        return run

    def receipt_lines(self, run):
        path = run / receipts.RECEIPTS_NAME
        return path, [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def write_receipts(self, path, values):
        path.write_text(
            "\n".join(receipts.canonical_json(value) for value in values) + "\n",
            encoding="utf-8",
        )

    def assert_receipt_gate_fails(self, run):
        report = validator.evaluate(run, run / "comparison.json")
        self.assertEqual("FAIL", report["gates"]["receipt_chain_valid"])
        self.assertIn("receipt_chain_valid", report["failures"])

    def test_valid_complete_receipt_chain_passes_common_gate(self):
        run = self.make_valid_run("receipt-valid", 40)
        report = validator.evaluate(run, run / "comparison.json")
        self.assertEqual("PASS", report["gates"]["receipt_chain_valid"])

    def test_missing_and_malformed_receipts_fail_common_gate(self):
        run = self.make_valid_run("receipt-missing", 41)
        (run / receipts.RECEIPTS_NAME).unlink()
        self.assert_receipt_gate_fails(run)
        run = self.make_valid_run("receipt-malformed", 42)
        (run / receipts.RECEIPTS_NAME).write_text("{bad}\n", encoding="utf-8")
        self.assert_receipt_gate_fails(run)

    def test_receipt_hash_sequence_and_link_tampering_fail_common_gate(self):
        mutations = (
            lambda values: values[1].__setitem__("hash", "0" * 64),
            lambda values: values[1].__setitem__("sequence", 9),
            lambda values: values[1].__setitem__("previous_hash", "0" * 64),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                run = self.make_valid_run(f"receipt-tamper-{index}", 50 + index)
                path, values = self.receipt_lines(run)
                mutate(values)
                self.write_receipts(path, values)
                self.assert_receipt_gate_fails(run)

    def test_wrong_receipt_run_id_and_candidate_digest_fail_common_gate(self):
        run = self.make_valid_run("receipt-run-id", 60)
        path, values = self.receipt_lines(run)
        values[0]["run_id"] = "other"
        values[0]["hash"] = receipts._receipt_hash(
            {key: values[0][key] for key in receipts.HASH_FIELDS}
        )
        values[1]["previous_hash"] = values[0]["hash"]
        values[1]["hash"] = receipts._receipt_hash(
            {key: values[1][key] for key in receipts.HASH_FIELDS}
        )
        values[2]["previous_hash"] = values[1]["hash"]
        values[2]["hash"] = receipts._receipt_hash(
            {key: values[2][key] for key in receipts.HASH_FIELDS}
        )
        self.write_receipts(path, values)
        self.assert_receipt_gate_fails(run)

        run = self.make_valid_run("receipt-digest", 61)
        path, values = self.receipt_lines(run)
        values[-1]["payload"]["duckdb_sha256"] = "0" * 64
        values[-1]["hash"] = receipts._receipt_hash(
            {key: values[-1][key] for key in receipts.HASH_FIELDS}
        )
        self.write_receipts(path, values)
        manifest_path = run / promotion.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["chain_head"] = values[-1]["hash"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_receipt_gate_fails(run)

    def test_manifest_chain_head_mismatch_fails_common_gate(self):
        run = self.make_valid_run("receipt-chain-head", 62)
        manifest_path = run / promotion.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["chain_head"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_receipt_gate_fails(run)

    def test_manifest_receipt_accounting_mismatch_fails_common_gate(self):
        run = self.make_valid_run("receipt-accounting", 64)
        manifest_path = run / promotion.MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["retries_used"] = 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_receipt_gate_fails(run)

    def test_abort_terminal_receipt_fails_promotion_gate(self):
        run = self.make_valid_run("receipt-abort", 63)
        (run / receipts.RECEIPTS_NAME).unlink()
        database_hash = promotion.sha256_file(run / promotion.STAGING_DATABASE_NAME)
        with receipts.ReceiptWriter(run) as writer:
            writer.append("ANCHOR", {
                "endpoint": validator.SOURCE_ENDPOINT, "year": 2026,
                "page_size": 100, "order_column": 11,
                "order_direction": "desc", "full_snapshot": True,
                "mode": "strict",
            }, timestamp="2026-01-01T00:00:00.000Z")
            writer.append("ABORT", {
                "terminal_reason": "FETCH_FAILED", "error_class": "Timeout",
                "failure_stage": "FETCH_PAGE", "processed": 0,
                "canonical_total": 0, "quarantined_total": 0,
                "duckdb_sha256": database_hash,
            }, timestamp="2026-01-01T00:01:00.000Z")
        self.assert_receipt_gate_fails(run)

    def make_valid_acceptance_fixture(self):
        baseline = (self.base / "acceptance" / "baseline").resolve()
        baseline.mkdir(parents=True)
        baseline_database = baseline / promotion.STAGING_DATABASE_NAME
        connection = duckdb.connect(str(baseline_database))
        try:
            connection.execute(
                """
                create table sirup_raw (
                    id bigint primary key, id_referensi varchar, pagu double,
                    satuanKerja varchar, kldi varchar, lokasi varchar,
                    jenisPengadaan varchar, metode varchar, sumberDana varchar,
                    paket varchar, pemilihan varchar, idBulan integer
                )
                """
            )
            connection.execute(
                "insert into sirup_raw values (0, 'baseline', 1, '', '', '', '', '', '', '', '', 1)"
            )
        finally:
            connection.close()
        (baseline / promotion.MANIFEST_NAME).write_text(
            json.dumps({"source_records_filtered": 1}), encoding="utf-8"
        )
        return baseline

    def test_success_path_with_real_validator_installs_candidate_and_evidence(self):
        run = self.make_valid_run("candidate", 1)
        candidate = run / promotion.STAGING_DATABASE_NAME
        candidate_bytes = candidate.read_bytes()
        candidate_hash = promotion.sha256_file(candidate)
        legacy_before = self.legacy.read_bytes()

        result = promotion.promote(run, self.root, None)

        installed = self.root / "snapshots" / candidate_hash
        selection = self.selection()
        self.assertEqual("promoted", result["status"])
        self.assertEqual(candidate_hash, selection["active"]["snapshot_id"])
        self.assertIsNone(selection["rollback"])
        self.assertEqual(candidate_bytes, (installed / promotion.DATABASE_NAME).read_bytes())
        self.assertEqual(candidate_hash, promotion.sha256_file(installed / promotion.DATABASE_NAME))
        self.assertTrue((installed / promotion.MANIFEST_NAME).is_file())
        self.assertEqual(
            promotion.sha256_file(installed / promotion.MANIFEST_NAME),
            selection["active"]["manifest_sha256"],
        )
        self.assertFalse(
            json.loads((installed / promotion.MANIFEST_NAME).read_text(encoding="utf-8"))[
                "promotion_eligible"
            ]
        )
        self.assertEqual(legacy_before, self.legacy.read_bytes())

    def test_real_validator_stale_expected_active_fails_without_authority_change(self):
        baseline = self.make_valid_acceptance_fixture()
        first = self.make_valid_run("candidate-one", 1, baseline)
        first_id = promotion.promote(first, self.root, None)["snapshot_id"]
        second = self.make_valid_run("candidate-two", 2, first)
        self.assertEqual(
            "PASS", validator.evaluate(second, second / "comparison.json")["result"]
        )
        selection_before = (self.root / "selection.json").read_bytes()

        with self.assertRaisesRegex(promotion.PromotionError, "stale expected-active"):
            promotion.promote(second, self.root, "0" * 64)

        self.assertEqual(selection_before, (self.root / "selection.json").read_bytes())
        self.assertEqual(first_id, self.selection()["active"]["snapshot_id"])

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
        with mock.patch.object(promotion, "evaluate", side_effect=self.rejected):
            with self.assertRaisesRegex(promotion.PromotionError, "validator rejected"):
                promotion.promote(run, self.root, None)
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

    def test_valid_genesis_uses_production_manifest_without_comparison(self):
        run = self.make_valid_run("genesis", 10)
        result = promotion.promote(run, self.root, None)
        self.assertEqual("promoted", result["status"])
        self.assertIsNone(self.selection()["rollback"])
        self.assertFalse((run / "comparison.json").exists())

    def test_standalone_validator_has_no_genesis_authority(self):
        run = self.make_valid_run("standalone", 11)
        report = validator.evaluate(run, run / "comparison.json")
        self.assertEqual("STEADY_STATE", report["validation_mode"])
        self.assertIn("comparison_report_available", report["failures"])

    def test_forged_genesis_context_is_not_accepted(self):
        run = self.make_valid_run("forged", 12)
        report = validator._evaluate_genesis(
            run, run / "comparison.json", object(), "forged", None
        )
        self.assertEqual("STEADY_STATE", report["validation_mode"])
        self.assertFalse(report["promotion_eligible"])

    def test_no_public_genesis_issuer_exists(self):
        self.assertFalse(hasattr(validator, "_issue_genesis_context"))
        self.assertFalse(hasattr(validator, "_GENESIS_ISSUER"))

    def acquire_capability(self, run):
        self.root.mkdir(parents=True)
        return promotion._acquire_genesis_capability(self.root / ".promotion.lock", run)

    def evaluate_with_capability(self, run, capability, **overrides):
        values = {
            "_genesis_capability": capability,
            "_genesis_run_id": capability.run_id,
            "_expected_active": None,
        }
        values.update(overrides)
        return validator._evaluate_genesis(
            run, run / "comparison.json", values["_genesis_capability"],
            values["_genesis_run_id"], values["_expected_active"]
        )

    def test_empty_fake_lock_cannot_create_capability(self):
        self.root.mkdir(parents=True)
        lock = self.root / ".promotion.lock"
        lock.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(promotion.PromotionError, "already held"):
            promotion._acquire_genesis_capability(lock, self.base / "candidate")

    def test_direct_constructor_cannot_create_authority(self):
        self.root.mkdir(parents=True)
        with self.assertRaisesRegex(TypeError, "only be created by lock acquisition"):
            promotion._GenesisCapability(
                self.root / ".promotion.lock", self.base / "candidate"
            )

    def test_unregistered_reconstructed_instance_is_rejected(self):
        run = self.make_valid_run("unregistered-instance", 34)
        reconstructed = object.__new__(promotion._GenesisCapability)
        report = validator._evaluate_genesis(
            run, run / "comparison.json", reconstructed, "copied-run-id", None
        )
        self.assertEqual("STEADY_STATE", report["validation_mode"])
        self.assertFalse(report["promotion_eligible"])

    def test_fake_object_with_copied_metadata_is_rejected(self):
        run = self.make_valid_run("fake-metadata", 35)
        capability = self.acquire_capability(run)
        try:
            fake = SimpleNamespace(
                _fd=capability._fd, nonce=capability.nonce,
                candidate_path=capability.candidate_path,
                run_id=capability.run_id, consumed=False,
            )
            report = validator._evaluate_genesis(
                run, run / "comparison.json", fake, fake.run_id, None
            )
            self.assertEqual("STEADY_STATE", report["validation_mode"])
            self.assertFalse(report["promotion_eligible"])
            self.assertFalse(capability.consumed)
        finally:
            capability.close()

    def test_copy_is_intentionally_rejected(self):
        run = self.make_valid_run("copy-rejected", 36)
        capability = self.acquire_capability(run)
        try:
            with self.assertRaisesRegex(TypeError, "cannot be copied"):
                copy.copy(capability)
        finally:
            capability.close()

    def test_deepcopy_is_intentionally_rejected(self):
        run = self.make_valid_run("deepcopy-rejected", 37)
        capability = self.acquire_capability(run)
        try:
            with self.assertRaisesRegex(TypeError, "cannot be deep-copied"):
                copy.deepcopy(capability)
        finally:
            capability.close()

    def test_pickle_is_intentionally_rejected(self):
        run = self.make_valid_run("pickle-rejected", 38)
        capability = self.acquire_capability(run)
        try:
            with self.assertRaisesRegex(TypeError, "cannot be serialized"):
                pickle.dumps(capability)
        finally:
            capability.close()

    def test_existing_lock_causes_atomic_acquisition_failure(self):
        self.test_empty_fake_lock_cannot_create_capability()

    def test_two_concurrent_acquirers_have_exactly_one_winner(self):
        self.root.mkdir(parents=True)
        run = self.base / "candidate"
        barrier = threading.Barrier(2)
        winners = []
        failures = []

        def acquire():
            barrier.wait()
            try:
                winners.append(promotion._acquire_genesis_capability(self.root / ".promotion.lock", run))
            except promotion.PromotionError:
                failures.append(True)

        threads = [threading.Thread(target=acquire) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(1, len(winners))
        self.assertEqual(1, len(failures))
        winners[0].close()

    def test_valid_held_fd_capability_succeeds_once(self):
        run = self.make_valid_run("held-fd", 22)
        capability = self.acquire_capability(run)
        try:
            report = self.evaluate_with_capability(run, capability)
            self.assertTrue(report["promotion_eligible"])
            self.assertTrue(capability.consumed)
        finally:
            capability.close()

    def test_closed_fd_fails(self):
        run = self.make_valid_run("closed-fd", 23)
        capability = self.acquire_capability(run)
        os.close(capability._fd)
        capability._fd = -1
        report = self.evaluate_with_capability(run, capability)
        self.assertIn("genesis_context_valid", report["failures"])

    def test_deleted_lock_fails(self):
        run = self.make_valid_run("deleted-lock", 24)
        capability = self.acquire_capability(run)
        real_stat = promotion.os.stat

        def missing_lock(path, *args, **kwargs):
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(capability.lock_path)):
                raise FileNotFoundError(path)
            return real_stat(path, *args, **kwargs)

        try:
            with mock.patch.object(promotion.os, "stat", side_effect=missing_lock):
                report = self.evaluate_with_capability(run, capability)
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def test_replaced_lock_inode_fails(self):
        run = self.make_valid_run("replaced-lock", 25)
        capability = self.acquire_capability(run)
        real_stat = promotion.os.stat
        try:
            held = os.fstat(capability._fd)
            replacement = list(held)
            replacement[1] = held.st_ino + 1
            fake_stat = os.stat_result(replacement)

            def replaced_lock(path, *args, **kwargs):
                if os.path.normcase(os.path.abspath(path)) == os.path.normcase(str(capability.lock_path)):
                    return fake_stat
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(promotion.os, "stat", side_effect=replaced_lock):
                report = self.evaluate_with_capability(run, capability)
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def test_native_open_lock_cannot_be_deleted_or_replaced_when_platform_denies_it(self):
        run = self.make_valid_run("native-lock-defense", 33)
        capability = self.acquire_capability(run)
        try:
            try:
                capability.lock_path.unlink()
            except PermissionError:
                self.assertTrue(capability.lock_path.exists())
            else:
                self.assertIn(
                    "genesis_context_valid",
                    self.evaluate_with_capability(run, capability)["failures"],
                )
        finally:
            capability.close()

    def test_candidate_binding_mismatch_fails_and_consumes(self):
        first = self.make_valid_run("candidate-a", 26)
        second = self.make_valid_run("candidate-b", 27)
        capability = self.acquire_capability(first)
        try:
            report = self.evaluate_with_capability(second, capability)
            self.assertIn("genesis_context_valid", report["failures"])
            self.assertTrue(capability.consumed)
        finally:
            capability.close()

    def test_run_binding_mismatch_fails_and_consumes(self):
        run = self.make_valid_run("run-binding", 28)
        capability = self.acquire_capability(run)
        try:
            report = self.evaluate_with_capability(
                run, capability, _genesis_run_id="different-run"
            )
            self.assertIn("genesis_context_valid", report["failures"])
            self.assertTrue(capability.consumed)
        finally:
            capability.close()

    def test_capability_reuse_fails(self):
        run = self.make_valid_run("single-use", 29)
        capability = self.acquire_capability(run)
        try:
            self.assertTrue(self.evaluate_with_capability(run, capability)["promotion_eligible"])
            report = self.evaluate_with_capability(run, capability)
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def test_non_none_expected_active_fails_and_consumes(self):
        run = self.make_valid_run("non-none", 30)
        capability = self.acquire_capability(run)
        try:
            report = self.evaluate_with_capability(
                run, capability, _expected_active="a" * 64
            )
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def test_existing_selection_fails(self):
        run = self.make_valid_run("existing-selection", 31)
        capability = self.acquire_capability(run)
        (self.root / "selection.json").write_text("{}", encoding="utf-8")
        try:
            report = self.evaluate_with_capability(run, capability)
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def test_selection_appearing_after_issuance_fails(self):
        run = self.make_valid_run("appearing-selection", 32)
        capability = self.acquire_capability(run)
        (self.root / "selection.json").write_text("{}", encoding="utf-8")
        try:
            report = self.evaluate_with_capability(run, capability)
            self.assertIn("genesis_context_valid", report["failures"])
        finally:
            capability.close()

    def assert_genesis_rejected(self, run):
        with self.assertRaisesRegex(promotion.PromotionError, "validator rejected"):
            promotion.promote(run, self.root, None)
        self.assertFalse((self.root / "selection.json").exists())

    def test_checkpoint_only_candidate_is_rejected(self):
        run = self.base / "checkpoint-only"
        run.mkdir()
        (run / promotion.STAGING_DATABASE_NAME).write_bytes(b"not-a-database")
        (run / "checkpoint.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(promotion.PromotionError, "manifest is missing"):
            promotion.promote(run, self.root, None)

    def test_genesis_missing_source_count_is_rejected(self):
        run = self.make_valid_run("missing-source", 13)
        path = run / promotion.MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        del manifest["source_records_filtered"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_genesis_rejected(run)

    def test_genesis_incomplete_collection_is_rejected(self):
        run = self.make_valid_run("incomplete", 14)
        path = run / promotion.MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["source_records_filtered"] = 2
        manifest["requested_limit"] = 2
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_genesis_rejected(run)

    def test_genesis_invalid_manifest_contract_is_rejected(self):
        run = self.make_valid_run("invalid-manifest", 15)
        path = run / promotion.MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["full_snapshot"] = False
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_genesis_rejected(run)

    def test_genesis_sha256_mismatch_is_rejected(self):
        run = self.make_valid_run("bad-genesis-hash", 16)
        path = run / promotion.MANIFEST_NAME
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sha256"] = "0" * 64
        path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_genesis_rejected(run)

    def make_invalid_id_run(self, name, ids, not_null=True):
        run = (self.base / name).resolve()
        run.mkdir()
        database = run / promotion.STAGING_DATABASE_NAME
        connection = duckdb.connect(str(database))
        try:
            nullability = "not null" if not_null else ""
            connection.execute(
                f"create table sirup_raw (id bigint {nullability}, id_referensi varchar, "
                "pagu double, satuanKerja varchar, kldi varchar, lokasi varchar, "
                "jenisPengadaan varchar, metode varchar, sumberDana varchar, paket varchar, "
                "pemilihan varchar, idBulan integer)"
            )
            for identifier in ids:
                connection.execute("insert into sirup_raw values (?, '', 1, '', '', '', '', '', '', '', '', 1)", [identifier])
        finally:
            connection.close()
        facts = validator.inspect_database(database)
        database_hash = promotion.sha256_file(database)
        with receipts.ReceiptWriter(run) as writer:
            writer.append("ANCHOR", {
                "endpoint": validator.SOURCE_ENDPOINT, "year": 2026,
                "page_size": max(1, len(ids)), "order_column": 11,
                "order_direction": "desc", "full_snapshot": True,
                "mode": "strict",
            }, timestamp="2026-01-01T00:00:00.000Z")
            writer.append("PAGE", {
                "start": 0, "page_size": max(1, len(ids)),
                "returned_row_count": len(ids),
                "canonical_row_count": len(ids), "quarantined_row_count": 0,
                "page_rows_digest": digest(f"invalid-{name}".encode()),
                "source_count_observed": len(ids),
            }, timestamp="2026-01-01T00:00:30.000Z")
            terminal = writer.append("COMPLETION", {
                "terminal_reason": "NORMAL_COMPLETION", "processed": len(ids),
                "canonical_total": len(ids), "quarantine_total": 0,
                "source_count_start": len(ids), "source_count_end": len(ids),
                "drift_status": "NO_DRIFT", "duckdb_sha256": database_hash,
                "promotion_flag": False,
            }, timestamp="2026-01-01T00:01:00.000Z")
        manifest = {
            "manifest_version": 1, "run_id": name, "status": "validated_staging_sample",
            "full_snapshot": True, "promotion_eligible": False,
            "source_endpoint": validator.SOURCE_ENDPOINT, "requested_year": 2026,
            "requested_limit": len(ids), "page_size": 100, "page_count": 1,
            "started_at": "2026-01-01T00:00:00+00:00", "collected_at": "2026-01-01T00:01:00+00:00",
            "database_path": str(database), "table_name": "sirup_raw",
            "row_count": facts["row_count"], "distinct_id_count": facts["distinct_id_count"],
            "min_id": facts["min_id"], "max_id": facts["max_id"],
            "source_records_filtered": len(ids), "request_count": 1, "retries_used": 0,
            "sha256": database_hash, "chain_head": terminal["hash"],
            "validation": {key: "passed" for key in validator.COLLECTOR_VALIDATION_GATES},
            "promotion": {"attempted": False, "result": "not_in_scope"},
        }
        (run / promotion.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        return run

    def test_genesis_duplicate_ids_are_rejected(self):
        self.assert_genesis_rejected(self.make_invalid_id_run("duplicates", [1, 1]))

    def test_genesis_null_ids_are_rejected(self):
        self.assert_genesis_rejected(self.make_invalid_id_run("nulls", [None], not_null=False))

    def test_genesis_ignores_arbitrary_and_self_comparisons(self):
        run = self.make_valid_run("no-baseline-authority", 17)
        (run / "comparison.json").write_text(
            json.dumps({"status": "passed", "baseline": str(run), "baseline_sha256": "f" * 64}),
            encoding="utf-8",
        )
        result = promotion.promote(run, self.root, None)
        self.assertEqual("promoted", result["status"])
        self.assertIsNone(self.selection()["rollback"])

    def test_steady_state_without_comparison_is_rejected(self):
        first = self.make_valid_run("steady-first", 18)
        first_id = promotion.promote(first, self.root, None)["snapshot_id"]
        second = self.make_valid_run("steady-second", 19)
        with self.assertRaisesRegex(promotion.PromotionError, "validator rejected"):
            promotion.promote(second, self.root, first_id)

    def test_steady_state_invalid_comparison_is_rejected(self):
        first = self.make_valid_run("invalid-comparison-first", 20)
        first_id = promotion.promote(first, self.root, None)["snapshot_id"]
        second = self.make_valid_run("invalid-comparison-second", 21)
        (second / "comparison.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(promotion.PromotionError, "validator rejected"):
            promotion.promote(second, self.root, first_id)


if __name__ == "__main__":
    unittest.main()
