import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from procurement_identity_resolution import (  # noqa: E402
    EvidenceRecord,
    ProcurementRecord,
    append_human_review,
    extract_procurement_status,
    resolve_identity,
)

VERSION = "2026-07-26T05:17:27+00:00"


def sirup(**overrides):
    values = dict(
        record_id="sirup-1",
        package_name="Pengadaan Server Data Center",
        institution="Kementerian Contoh",
        satker="Pusat Data",
        year=2026,
        budget=1_000_000_000,
        procurement_method="Tender",
        location="Jakarta",
        package_id="777",
        rup_id="888",
    )
    values.update(overrides)
    return ProcurementRecord(**values)


def evidence(candidate_id="spse-100", **overrides):
    values = dict(
        candidate_id=candidate_id,
        package_name="Pengadaan Server Data Center",
        institution="Kementerian Contoh",
        satker="Pusat Data",
        year=2026,
        budget=980_000_000,
        procurement_method="Tender",
        location="Jakarta",
        evidence_type="SPSE",
        source_url="https://example.invalid/spse-100",
        source_file="controlled-sample.csv",
        source_record_id=candidate_id,
        collected_at="2026-07-01T00:00:00+00:00",
        provenance="controlled regression fixture",
        source_status="Tender berjalan",
    )
    values.update(overrides)
    return EvidenceRecord(**values)


class Sprint1RegressionCases(unittest.TestCase):
    def resolve(self, record, rows):
        return resolve_identity(record, rows, dataset_version=VERSION)

    def assert_conflict(self, result, conflict_type, severity):
        conflicts = {
            conflict["type"]: conflict["severity"]
            for candidate in result.candidate_list
            for conflict in candidate["conflicts"]
        }
        self.assertEqual(severity, conflicts.get(conflict_type))

    def test_case_1_same_package_id_different_package(self):
        result = self.resolve(
            sirup(package_name="Pembangunan Jalan KSPEAN Wanam - Muting Segmen I"),
            [evidence(candidate_id="777", package_name="Pengadaan Barrier Gate dan Alat Kamera")],
        )
        self.assertEqual("REJECTED_PACKAGE_CONFLICT", result.identity_status)

    def test_case_2_same_package_id_different_institution(self):
        result = self.resolve(sirup(), [evidence(candidate_id="777", institution="Pemerintah Kabupaten Lain")])
        self.assertEqual("REJECTED_INSTITUTION_CONFLICT", result.identity_status)

    def test_case_3_cross_namespace_numeric_equality_has_no_authority(self):
        result = self.resolve(
            sirup(package_name="", institution="", satker="", year=None, budget=None, procurement_method="", location=""),
            [evidence(candidate_id="888", package_name="", institution="", satker="", year=None, budget=None, procurement_method="", location="")],
        )
        self.assertIn(result.identity_status, {"NO_MATCH", "NEEDS_MANUAL_REVIEW"})

    def test_case_4_strong_multi_signal_identity(self):
        self.assertEqual("CONFIRMED_MATCH", self.resolve(sirup(), [evidence()]).identity_status)

    def test_case_5_status_uses_only_canonical_identity(self):
        old = evidence(source_record_id="old", collected_at="2026-06-01T00:00:00+00:00", source_status="Tender")
        latest = evidence(source_record_id="latest", collected_at="2026-07-01T00:00:00+00:00", source_status="Pemenang berkontrak")
        unrelated = evidence(
            "spse-other",
            package_name="Pembangunan Jalan Desa",
            institution="Pemerintah Kabupaten Lain",
            satker="Dinas Pekerjaan Umum",
            source_status="Selesai",
        )
        identity = self.resolve(sirup(), [old, latest, unrelated])
        status = extract_procurement_status(identity, [unrelated, latest, old])
        self.assertEqual("CONTRACTED", status["normalized_status"])
        self.assertEqual("latest", status["status_evidence"]["source_record_id"])

    def test_case_6_no_evidence_found(self):
        identity = self.resolve(sirup(), [])
        self.assertEqual("NO_MATCH", identity.identity_status)
        self.assertEqual("SIRUP_PLANNING_ONLY", extract_procurement_status(identity, [])["normalized_status"])

    def test_case_7_hard_conflict_overrides_positive_signals(self):
        result = self.resolve(sirup(), [evidence(institution="Pemerintah Kabupaten Lain")])
        self.assertEqual("REJECTED_INSTITUTION_CONFLICT", result.identity_status)
        self.assertIn("PACKAGE_NAME", result.match_signals)

    def test_case_8_stable_tie_break(self):
        rows = [evidence("spse-b"), evidence("spse-a")]
        first = self.resolve(sirup(), rows)
        second = self.resolve(sirup(), list(reversed(rows)))
        self.assertEqual("NEEDS_MANUAL_REVIEW", first.identity_status)
        self.assertEqual(
            [item["candidate_id"] for item in first.candidate_list],
            ["spse-a", "spse-b"],
        )
        self.assertEqual(first.candidate_list, second.candidate_list)

    def test_case_9_manual_review_is_append_only(self):
        identity = self.resolve(sirup(), [evidence("spse-b"), evidence("spse-a")])
        machine_before = copy.deepcopy(identity.decision_evidence)
        review_before = copy.deepcopy(identity.manual_review_record)
        appended = append_human_review(machine_before, review_before, "CONFIRM_MATCH", "reviewer-1", VERSION)
        self.assertEqual(machine_before, identity.decision_evidence)
        self.assertEqual(review_before, identity.manual_review_record)
        self.assertEqual("CONFIRM_MATCH", appended["human_decision"])

    def test_case_10_deterministic_replay(self):
        rows = [evidence("spse-b"), evidence("spse-a")]
        first = self.resolve(sirup(), rows)
        second = self.resolve(sirup(), list(reversed(rows)))
        self.assertEqual(
            json.dumps(first.decision_evidence, sort_keys=True),
            json.dumps(second.decision_evidence, sort_keys=True),
        )

    def test_rule_9_year_conflict_is_soft_and_does_not_reject(self):
        result = self.resolve(sirup(), [evidence(year=2025)])

        self.assert_conflict(result, "YEAR_CONFLICT", "SOFT")
        self.assertEqual("CONFIRMED_MATCH", result.identity_status)
        self.assertFalse(result.candidate_list[0]["rejected"])

    def test_rule_9_major_procurement_method_conflict_is_hard_and_rejects(self):
        result = self.resolve(sirup(), [evidence(procurement_method="E-Purchasing")])

        self.assert_conflict(result, "MAJOR_PROCUREMENT_METHOD_CONFLICT", "HARD")
        self.assertEqual("REJECTED_PROCUREMENT_METHOD_CONFLICT", result.identity_status)
        self.assertTrue(result.candidate_list[0]["rejected"])

    def test_rule_9_minor_procurement_method_difference_is_soft_and_does_not_reject(self):
        result = self.resolve(sirup(procurement_method="Swakelola"), [evidence(procurement_method="Penunjukan Langsung")])

        self.assert_conflict(result, "MINOR_PROCUREMENT_METHOD_DIFFERENCE", "SOFT")
        self.assertEqual("CONFIRMED_MATCH", result.identity_status)
        self.assertFalse(result.candidate_list[0]["rejected"])

    def test_rule_9_satker_conflict_is_hard_and_rejects(self):
        result = self.resolve(sirup(), [evidence(satker="Dinas Pekerjaan Umum")])

        self.assert_conflict(result, "SATKER_CONFLICT", "HARD")
        self.assertEqual("REJECTED_SATKER_CONFLICT", result.identity_status)
        self.assertTrue(result.candidate_list[0]["rejected"])


if __name__ == "__main__":
    unittest.main()
