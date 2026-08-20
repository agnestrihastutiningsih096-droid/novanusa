from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import demand_taxonomy_v1_classifier as taxonomy  # noqa: E402
import current_procurement_contracts as contracts  # noqa: E402
import potential_match_cohort as cohort  # noqa: E402
from current_procurement_contracts import (
    RawCurrentRupCandidate,
    SourceKind,
    SourceMaturity,
    SourceProvenance,
)
from project_mitracom_product_relevance import (
    ProjectedProductRelevance,
    project_product_relevance,
)


def make_provenance(acquisition_id: str = "run-2026-100rows") -> SourceProvenance:
    return SourceProvenance(
        source_kind=SourceKind.CURRENT_SIRUP,
        source_locator="sirup_staging.duckdb#sha256=abc",
        observed_at="2026-08-17T04:33:00.921Z",
        acquisition_id=acquisition_id,
        raw_receipt_id="60ccad916491f8100fe9a14340f0cd4609ca54f0e4f647ad97207ef73ac6b840",
        schema_version="1",
        source_maturity=SourceMaturity.BOUNDED_ACQUISITION_VERIFIED,
    )


def make_candidate(
    planned_procurement_id: str,
    package_title: str,
    id_kldi: str = "D294",
    procurement_type: str = "Pengadaan Barang",
    source_year: int = 2026,
    provenance: SourceProvenance | None = None,
    kldi_name: str = "Kab. Halmahera Tengah",
    institution_name: str = "Dinas Pendidikan Kabupaten Halmahera Tengah",
) -> RawCurrentRupCandidate:
    return RawCurrentRupCandidate(
        planned_procurement_id=planned_procurement_id,
        source_rup_id=f"rup-{planned_procurement_id}",
        id_satker="123456",
        id_kldi=id_kldi,
        institution_name=institution_name,
        kldi_name=kldi_name,
        package_title=package_title,
        budget=Decimal("100000000"),
        procurement_type=procurement_type,
        procurement_method="Tender",
        selection_period="2026",
        location="Maluku Utara",
        source_year=source_year,
        provenance=provenance or make_provenance(),
    )


class PotentialMatchCohortTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary.name)
        self.existing_files = set(self.temporary_root.rglob("*"))

    def tearDown(self):
        self.temporary.cleanup()

    def assert_no_files_created_anywhere(self):
        leftovers = [path for path in self.temporary_root.rglob("*") if path not in self.existing_files]
        self.assertEqual([], leftovers)

    # 01 deterministic replay
    def test_same_input_sequence_yields_identical_cohort_across_runs(self):
        candidates = [
            make_candidate("1003", "Pengadaan Laptop dan Printer"),
            make_candidate("1001", "Pengadaan Jasa Konsultansi"),
            make_candidate("1002", "Pengadaan Server dan UPS"),
        ]
        first = cohort.build_potential_match_cohort(candidates)
        for _ in range(25):
            self.assertEqual(first, cohort.build_potential_match_cohort(candidates))

    # 02 empty projection excluded
    def test_candidate_with_empty_matched_product_ids_is_excluded(self):
        result = cohort.build_potential_match_cohort([
            make_candidate("1001", "Pengadaan Jasa Konsultansi"),
            make_candidate("1002", "Pengadaan Laptop"),
        ])
        ids = [row.planned_procurement_id for row in result.rows]
        self.assertNotIn("1001", ids)
        self.assertIn("1002", ids)

    # 03 non-empty projection included
    def test_candidate_with_non_empty_matched_product_ids_is_included(self):
        result = cohort.build_potential_match_cohort([
            make_candidate("1001", "Pengadaan Laptop dan Printer"),
        ])
        self.assertEqual(1, len(result.rows))
        self.assertEqual(("mitracom-laptop-general", "mitracom-printer-general"), result.rows[0].matched_product_ids)

    # 04 deterministic ordering by planned_procurement_id ascending
    def test_ordering_is_deterministic_by_planned_procurement_id_ascending(self):
        candidates = [
            make_candidate("3001", "Pengadaan Laptop"),
            make_candidate("0009", "Pengadaan Server dan UPS"),
            make_candidate("1002", "Pengadaan CCTV"),
            make_candidate("0101", "Pengadaan Printer"),
        ]
        result = cohort.build_potential_match_cohort(candidates)
        self.assertEqual(
            ["0009", "0101", "1002", "3001"],
            [row.planned_procurement_id for row in result.rows],
        )

    def test_duplicate_planned_procurement_id_fails_closed(self):
        candidates = [
            make_candidate("1001", "Pengadaan Laptop"),
            make_candidate("1001", "Pengadaan Printer"),
        ]
        with self.assertRaises(cohort.PotentialMatchCohortError):
            cohort.build_potential_match_cohort(candidates)

    def test_non_candidate_input_fails_closed(self):
        with self.assertRaises(cohort.PotentialMatchCohortError):
            cohort.build_potential_match_cohort([object()])

    # 05 not SupplierProductCompatibility
    def test_output_is_not_supplier_product_compatibility(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        for row in result.rows:
            self.assertNotIsInstance(row, contracts.SupplierProductCompatibility)

    # 06 no compatibility authority fields
    def test_output_exposes_no_compatibility_authority(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        for row in result.rows:
            self.assertFalse(hasattr(row, "compatibility_state"))
            self.assertFalse(hasattr(row, "supplier_product_id"))
            self.assertFalse(hasattr(row, "compatibility_basis"))

    # 07 not OutreachEligibility, no outreach authority
    def test_output_is_not_outreach_eligibility(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        for row in result.rows:
            self.assertNotIsInstance(row, contracts.OutreachEligibility)
            self.assertFalse(hasattr(row, "eligibility_state"))
            self.assertFalse(hasattr(row, "buyer_identity_key"))

    # 08 routed rows expose routing prerequisites
    def test_routed_rows_expose_routing_prerequisites(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        row = result.rows[0]
        self.assertTrue(row.id_kldi)
        self.assertTrue(row.kldi_name)
        self.assertTrue(row.provenance.acquisition_id)
        prereqs = cohort.routed_verification_prerequisites(row)
        self.assertEqual("D294", prereqs["id_kldi"])
        self.assertEqual("run-2026-100rows", prereqs["sirup_acquisition_id"])

    # 09 missing/blank id_kldi fails closed for routed verification
    def test_missing_or_blank_id_kldi_fails_closed(self):
        for missing in ("", "   "):
            with self.subTest(missing=missing):
                candidate = make_candidate("1001", "Pengadaan Laptop", id_kldi=missing)
                result = cohort.build_potential_match_cohort([candidate])
                self.assertEqual(1, len(result.rows))
                with self.assertRaises(cohort.PotentialMatchCohortError):
                    cohort.routed_verification_prerequisites(result.rows[0])

    def test_id_kldi_never_fabricated_or_inferred(self):
        candidate = make_candidate(
            "1001",
            "Pengadaan Laptop",
            id_kldi="",
            kldi_name="Kab. Halmahera Tengah",
            institution_name="Dinas Pendidikan Kabupaten Halmahera Tengah",
        )
        result = cohort.build_potential_match_cohort([candidate])
        self.assertEqual("", result.rows[0].id_kldi)
        with self.assertRaises(cohort.PotentialMatchCohortError):
            cohort.routed_verification_prerequisites(result.rows[0])

    def test_missing_acquisition_id_fails_closed(self):
        provenance = make_provenance()
        candidate = make_candidate("1001", "Pengadaan Laptop", provenance=provenance)
        # The canonical SourceProvenance contract forbids a blank acquisition_id,
        # so blank it directly to prove the cohort boundary still fails closed.
        blank_provenance = object.__new__(SourceProvenance)
        object.__setattr__(blank_provenance, "source_kind", provenance.source_kind)
        object.__setattr__(blank_provenance, "source_locator", provenance.source_locator)
        object.__setattr__(blank_provenance, "observed_at", provenance.observed_at)
        object.__setattr__(blank_provenance, "acquisition_id", "")
        object.__setattr__(blank_provenance, "raw_receipt_id", provenance.raw_receipt_id)
        object.__setattr__(blank_provenance, "schema_version", provenance.schema_version)
        object.__setattr__(blank_provenance, "source_maturity", provenance.source_maturity)
        blank_candidate = RawCurrentRupCandidate(
            **{name: getattr(candidate, name) for name in RawCurrentRupCandidate.__dataclass_fields__ if name != "provenance"},
            provenance=blank_provenance,
        )
        result = cohort.build_potential_match_cohort([blank_candidate])
        with self.assertRaises(cohort.PotentialMatchCohortError):
            cohort.routed_verification_prerequisites(result.rows[0])

    # 10-14 authority calls never occur
    def test_forbidden_authority_calls_never_occur(self):
        with (
            mock.patch.object(contracts, "verify_realization_link", side_effect=AssertionError("verify_realization_link called")) as verify_link,
            mock.patch.object(contracts, "evaluate_outreach_eligibility", side_effect=AssertionError("evaluate_outreach_eligibility called")) as evaluate,
            mock.patch.object(contracts, "validate_compatibility", side_effect=AssertionError("validate_compatibility called")) as validate,
            mock.patch.object(contracts, "promote_supplier_compatibility", side_effect=AssertionError("promote_supplier_compatibility called")) as promote,
            mock.patch.object(contracts, "_persist_decision", side_effect=AssertionError("_persist_decision called")) as persist,
            mock.patch.object(contracts, "validate_identity", side_effect=AssertionError("validate_identity called")) as identity,
        ):
            candidates = [
                make_candidate("1001", "Pengadaan Laptop dan Printer"),
                make_candidate("1002", "Pengadaan Jasa Konsultansi"),
                make_candidate("1003", "Pengadaan Server dan UPS"),
            ]
            result = cohort.build_potential_match_cohort(candidates)
            for row in result.rows:
                cohort.routed_verification_prerequisites(row)
            for group in result.grouped_by_kldi():
                pass
        verify_link.assert_not_called()
        evaluate.assert_not_called()
        validate.assert_not_called()
        promote.assert_not_called()
        persist.assert_not_called()
        identity.assert_not_called()

    # 15 no network
    def test_no_network_access(self):
        with (
            mock.patch("socket.socket", side_effect=AssertionError("socket used")),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("urlopen used")),
        ):
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        self.assertEqual(1, len(result.rows))

    # 16 no credentials
    def test_no_credentials_accessed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
            self.assertEqual(1, len(result.rows))

    # 17 no DB write
    def test_no_db_write(self):
        with (
            mock.patch("duckdb.connect", side_effect=AssertionError("duckdb used")),
            mock.patch.object(contracts.ProcurementDecisionStore, "append", side_effect=AssertionError("decision append used")),
        ):
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        self.assertEqual(1, len(result.rows))

    # 18 no decision-store persistence
    def test_no_decision_store_persistence(self):
        store_path = self.temporary_root / "decisions.json"
        with mock.patch.object(
            contracts,
            "_DECISION_STORE",
            contracts.ProcurementDecisionStore(store_path),
        ):
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
            for row in result.rows:
                cohort.routed_verification_prerequisites(row)
        self.assertEqual(1, len(result.rows))
        self.assertFalse(store_path.exists())

    # 19 no repository data files written
    def test_no_repository_data_files_written(self):
        with mock.patch("duckdb.connect", side_effect=AssertionError("duckdb used")):
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        self.assertEqual(1, len(result.rows))
        self.assert_no_files_created_anywhere()

    # 20 taxonomy version and sha256 preserved exactly
    def test_taxonomy_version_and_sha256_preserved_exactly(self):
        candidate = make_candidate("1001", "Pengadaan Laptop dan Printer")
        projection = project_product_relevance(candidate.package_title, candidate.procurement_type)
        result = cohort.build_potential_match_cohort([candidate])
        row = result.rows[0]
        self.assertEqual(projection.taxonomy_version, row.taxonomy_version)
        self.assertEqual(projection.taxonomy_sha256, row.taxonomy_sha256)
        self.assertEqual(taxonomy.TAXONOMY_SHA256, row.taxonomy_sha256)
        self.assertEqual("3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0", row.taxonomy_sha256)

    def test_semantic_state_is_candidate_derived_signal_only(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        self.assertEqual("CANDIDATE_DERIVED_SIGNAL_ONLY", result.rows[0].semantic_state)
        self.assertEqual(cohort.OUTPUT_SEMANTIC_STATE, result.rows[0].semantic_state)

    # 21 provenance remains original/source-bound
    def test_provenance_remains_original_object(self):
        provenance = make_provenance(acquisition_id="run-specific")
        candidate = make_candidate("1001", "Pengadaan Laptop", provenance=provenance)
        result = cohort.build_potential_match_cohort([candidate])
        self.assertIs(provenance, result.rows[0].provenance)
        self.assertEqual("run-specific", result.rows[0].provenance.acquisition_id)

    # 22 grouping deterministic and routing-free
    def test_grouping_by_kldi_is_deterministic_and_does_not_route(self):
        candidates = [
            make_candidate("3001", "Pengadaan Laptop", id_kldi="D294"),
            make_candidate("0009", "Pengadaan Server dan UPS", id_kldi="D777"),
            make_candidate("1002", "Pengadaan CCTV", id_kldi="D294"),
            make_candidate("0101", "Pengadaan Printer", id_kldi="D294"),
        ]
        first = cohort.build_potential_match_cohort(candidates).grouped_by_kldi()
        for _ in range(25):
            self.assertEqual(first, cohort.build_potential_match_cohort(candidates).grouped_by_kldi())
        keys = [key for key, _ in first]
        self.assertEqual(["D294", "D777"], keys)
        self.assertEqual(
            ["0101", "1002", "3001"],
            [row.planned_procurement_id for row in first[0][1]],
        )
        self.assertEqual(["0009"], [row.planned_procurement_id for row in first[1][1]])

    def test_grouping_is_read_only_and_never_performs_route_lookup(self):
        with mock.patch.object(cohort, "routed_verification_prerequisites", side_effect=AssertionError("route lookup attempted")) as route:
            result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
            grouped = result.grouped_by_kldi()
        self.assertEqual(1, len(grouped))
        route.assert_not_called()

    # output row type is the local value type only
    def test_output_row_is_local_value_type_only(self):
        result = cohort.build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")])
        for row in result.rows:
            self.assertIs(type(row), cohort.PotentialMatchRow)


if __name__ == "__main__":
    unittest.main()
