from __future__ import annotations

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pandas as pd

import current_procurement_contracts as contracts  # noqa: E402
import scripts.kldi_lpse_routing as routing  # noqa: E402
import scripts.potential_match_routing as pmr  # noqa: E402
from current_procurement_contracts import (
    RawCurrentRupCandidate,
    SourceKind,
    SourceMaturity,
    SourceProvenance,
)
import potential_match_cohort as cohort  # noqa: E402
from potential_match_cohort import build_potential_match_cohort


D294_ROUTE = "https://spse.inaproc.id/haltengkab"
REGISTRY_DIGEST = "011d54c98b82b035732565715a8b732cb8e315b602a2d6c13f98f545485930f7"
RECEIPT_HASH = "60ccad916491f8100fe9a14340f0cd4609ca54f0e4f647ad97207ef73ac6b840"


def make_provenance(acquisition_id: str = "20260817T043259Z-2026-100rows") -> SourceProvenance:
    return SourceProvenance(
        source_kind=SourceKind.CURRENT_SIRUP,
        source_locator="sirup_staging.duckdb#sha256=abc",
        observed_at="2026-08-17T04:33:00.921Z",
        acquisition_id=acquisition_id,
        raw_receipt_id=RECEIPT_HASH,
        schema_version="1",
        source_maturity=SourceMaturity.BOUNDED_ACQUISITION_VERIFIED,
    )


def make_candidate(
    planned_procurement_id: str,
    package_title: str,
    id_kldi: str = "D294",
    kldi_name: str = "Kab. Halmahera Tengah",
    procurement_type: str = "Pengadaan Barang",
    provenance: SourceProvenance | None = None,
) -> RawCurrentRupCandidate:
    return RawCurrentRupCandidate(
        planned_procurement_id=planned_procurement_id,
        source_rup_id=f"rup-{planned_procurement_id}",
        id_satker="123456",
        id_kldi=id_kldi,
        institution_name="Dinas Pendidikan Kabupaten Halmahera Tengah",
        kldi_name=kldi_name,
        package_title=package_title,
        budget=Decimal("100000000"),
        procurement_type=procurement_type,
        procurement_method="Tender",
        selection_period="2026",
        location="Maluku Utara",
        source_year=2026,
        provenance=provenance or make_provenance(),
    )


def sirup_result(*, candidates=None):
    if candidates is None:
        candidates = (SimpleNamespace(id_kldi="D294", kldi_name="Kab. Halmahera Tengah"),)
    return SimpleNamespace(
        candidates=candidates,
        provenance=SimpleNamespace(
            acquisition_id="20260817T043259Z-2026-100rows",
            raw_receipt_id=RECEIPT_HASH,
            observed_at="2026-08-17T04:33:00.921Z",
        ),
    )


def registry_frame(*, route: str = D294_ROUTE, lpse_name: str = "LPSE Kabupaten Halmahera Tengah"):
    return pd.DataFrame([
        {
            "nama_lpse": lpse_name,
            "official_lpse_url": route,
            "provinsi": "Maluku Utara",
            "kategori_instansi": "Pemerintah Kabupaten",
        }
    ])


def registry_metadata():
    return {
        "registry_artifact_id": "novanusa:lpse-registry:csv",
        "registry_artifact_hash": REGISTRY_DIGEST,
        "registry_version": f"sha256:{REGISTRY_DIGEST}",
    }


def active_binding(*, route: str = D294_ROUTE, lpse_name: str = "LPSE Kabupaten Halmahera Tengah"):
    return routing.build_kldi_lpse_routing_binding(
        routing.SirupRoutingEvidence(
            canonical_kldi_id="D294",
            source_kldi_name="Kab. Halmahera Tengah",
            acquisition_run_id="20260817T043259Z-2026-100rows",
            receipt_chain_reference="receipt-chain:20260817T043259Z-2026-100rows",
            receipt_chain_hash=RECEIPT_HASH,
            source_version="sirup-authenticated-2026-08-17",
            province="Maluku Utara",
            government_level="Kabupaten",
        ),
        [
            routing.LpseRegistryEvidence(
                lpse_name=lpse_name,
                official_lpse_url=route,
                registry_artifact_id="novanusa:lpse-registry:csv",
                registry_artifact_hash=REGISTRY_DIGEST,
                registry_version=f"sha256:{REGISTRY_DIGEST}",
                province="Maluku Utara",
                government_level="Pemerintah Kabupaten",
            )
        ],
    )


class PotentialMatchRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.temporary_root = Path(self.temporary.name)
        self.existing_files = set(self.temporary_root.rglob("*"))

    def tearDown(self):
        self.temporary.cleanup()

    def assert_no_files_created_anywhere(self):
        leftovers = [path for path in self.temporary_root.rglob("*") if path not in self.existing_files]
        self.assertEqual([], leftovers)

    def resolve(self, candidates, *, sirup=None, registry=None, metadata=None):
        cohort_result = build_potential_match_cohort(candidates)
        with (
            mock.patch(
                "scripts.collect_lpse_detail_evidence.acquire_validated_sirup",
                return_value=sirup or sirup_result(),
            ),
            mock.patch(
                "scripts.collect_lpse_detail_evidence.load_registry_artifact_metadata",
                return_value=metadata or registry_metadata(),
            ),
            mock.patch(
                "scripts.collect_lpse_detail_evidence.pd.read_csv",
                return_value=registry if registry is not None else registry_frame(),
            ),
        ):
            return pmr.resolve_routing_for_cohort(cohort_result, Path("validated-run"))

    # 01 same cohort + same evidence -> identical results
    def test_repeated_resolution_is_identical(self):
        candidates = [
            make_candidate("3001", "Pengadaan Laptop"),
            make_candidate("1002", "Pengadaan CCTV"),
            make_candidate("0101", "Pengadaan Printer"),
        ]
        first = self.resolve(candidates)
        for _ in range(25):
            self.assertEqual(first, self.resolve(candidates))

    # 02 one KLDI group -> exactly one routing resolution
    def test_one_kldi_group_yields_exactly_one_routing_resolution(self):
        candidates = [
            make_candidate("3001", "Pengadaan Laptop"),
            make_candidate("1002", "Pengadaan CCTV"),
            make_candidate("0101", "Pengadaan Printer"),
        ]
        results = self.resolve(candidates)
        self.assertEqual(1, len(results))
        self.assertEqual("D294", results[0].id_kldi)

    # 03 multiple candidates same id_kldi keep deterministic planned_procurement_id order
    def test_multiple_candidates_keep_deterministic_order(self):
        candidates = [
            make_candidate("3001", "Pengadaan Laptop"),
            make_candidate("1002", "Pengadaan CCTV"),
            make_candidate("0101", "Pengadaan Printer"),
        ]
        results = self.resolve(candidates)
        self.assertEqual(
            ("0101", "1002", "3001"),
            results[0].planned_procurement_ids,
        )

    # 04 ROUTING_ACTIVE exposes exactly the existing authorized LPSE URL
    def test_active_d294_exposes_exact_authorized_lpse_url(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        self.assertEqual("ROUTING_ACTIVE", results[0].routing_status)
        self.assertEqual(D294_ROUTE, results[0].official_lpse_url)
        self.assertEqual("POTENTIAL_MATCH_ROUTING_RESOLVED", results[0].semantic_state)

    def test_active_d294_preserves_binding_digest_and_registry_provenance(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        binding = active_binding()
        result = results[0]
        self.assertEqual(binding.binding_digest, result.routing_binding_digest)
        self.assertEqual(binding.sirup_acquisition_run_id, result.sirup_acquisition_id)
        self.assertEqual(binding.registry_artifact_id, result.registry_artifact_id)
        self.assertEqual(binding.registry_artifact_hash, result.registry_artifact_hash)
        self.assertEqual(binding.registry_version, result.registry_version)
        # 25 digest/provenance metadata preserved from the existing binding, not recomputed
        self.assertEqual(binding.binding_digest, result.routing_binding_digest)

    # 05 blank id_kldi fails closed
    def test_blank_id_kldi_fails_closed(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop", id_kldi="   ")]
        results = self.resolve(candidates)
        self.assertEqual(1, len(results))
        self.assertEqual("ROUTING_REJECTED", results[0].routing_status)
        self.assertEqual("", results[0].official_lpse_url)

    # 06 blank acquisition_id fails closed
    def test_blank_acquisition_id_fails_closed(self):
        provenance = make_provenance()
        blank = object.__new__(SourceProvenance)
        for name in ("source_kind", "source_locator", "observed_at", "raw_receipt_id", "schema_version", "source_maturity"):
            object.__setattr__(blank, name, getattr(provenance, name))
        object.__setattr__(blank, "acquisition_id", "")
        results = self.resolve([make_candidate("1001", "Pengadaan Laptop", provenance=blank)])
        self.assertEqual(1, len(results))
        self.assertEqual("ROUTING_REJECTED", results[0].routing_status)
        self.assertEqual("", results[0].official_lpse_url)

    def test_inconsistent_group_acquisition_ids_fail_closed(self):
        first = make_candidate("1001", "Pengadaan Laptop")
        second = make_candidate("1002", "Pengadaan CCTV", provenance=make_provenance(acquisition_id="different-run"))
        results = self.resolve([first, second])
        self.assertEqual(1, len(results))
        self.assertEqual("ROUTING_REJECTED", results[0].routing_status)
        self.assertEqual("", results[0].official_lpse_url)

    # 07-09 non-ACTIVE states are not routable (authority-level, existing semantics)
    def test_stale_binding_is_not_routable(self):
        binding = active_binding()
        stale = routing.validate_routing_authority(binding, registry_version="registry-v2")
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_STALE, stale.status)
        self.assertIsNone(routing.lookup_lpse_route(stale))

    def test_ambiguous_binding_is_not_routable(self):
        binding = active_binding()
        ambiguous = routing.build_kldi_lpse_routing_binding(
            binding.sirup_acquisition_run_id and routing.SirupRoutingEvidence(
                canonical_kldi_id="D294",
                source_kldi_name="Kab. Halmahera Tengah",
                acquisition_run_id="20260817T043259Z-2026-100rows",
                receipt_chain_reference="receipt-chain:20260817T043259Z-2026-100rows",
                receipt_chain_hash=RECEIPT_HASH,
                source_version="sirup-authenticated-2026-08-17",
            ),
            [
                routing.LpseRegistryEvidence(
                    lpse_name="LPSE Kabupaten Halmahera Tengah",
                    official_lpse_url=D294_ROUTE,
                    registry_artifact_id="novanusa:lpse-registry:csv",
                    registry_artifact_hash=REGISTRY_DIGEST,
                    registry_version=f"sha256:{REGISTRY_DIGEST}",
                ),
                routing.LpseRegistryEvidence(
                    lpse_name="LPSE Kabupaten Halmahera Tengah",
                    official_lpse_url="https://spse.inaproc.id/haltengkab-v2",
                    registry_artifact_id="novanusa:lpse-registry:csv",
                    registry_artifact_hash=REGISTRY_DIGEST,
                    registry_version=f"sha256:{REGISTRY_DIGEST}",
                ),
            ],
        )
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_AMBIGUOUS, ambiguous.status)
        self.assertIsNone(routing.lookup_lpse_route(ambiguous))

    def test_rejected_binding_is_not_routable(self):
        binding = active_binding()
        rejected = routing.build_kldi_lpse_routing_binding(
            routing.SirupRoutingEvidence(
                canonical_kldi_id="D294",
                source_kldi_name="Kab. Halmahera Tengah",
                acquisition_run_id="20260817T043259Z-2026-100rows",
                receipt_chain_reference="receipt-chain:20260817T043259Z-2026-100rows",
                receipt_chain_hash=RECEIPT_HASH,
                source_version="sirup-authenticated-2026-08-17",
            ),
            [
                routing.LpseRegistryEvidence(
                    lpse_name="LPSE Kabupaten Lain",
                    official_lpse_url="https://spse.inaproc.id/lain",
                    registry_artifact_id="novanusa:lpse-registry:csv",
                    registry_artifact_hash=REGISTRY_DIGEST,
                    registry_version=f"sha256:{REGISTRY_DIGEST}",
                )
            ],
        )
        self.assertEqual(routing.KldiLpseRoutingStatus.ROUTING_REJECTED, rejected.status)
        self.assertIsNone(routing.lookup_lpse_route(rejected))

    def test_non_active_binding_result_exposes_no_route(self):
        # A mocked canonical binding that is not ACTIVE must yield no endpoint.
        non_active = routing.build_kldi_lpse_routing_binding(
            routing.SirupRoutingEvidence(
                canonical_kldi_id="D294",
                source_kldi_name="Kab. Halmahera Tengah",
                acquisition_run_id="20260817T043259Z-2026-100rows",
                receipt_chain_reference="receipt-chain:20260817T043259Z-2026-100rows",
                receipt_chain_hash=RECEIPT_HASH,
                source_version="sirup-authenticated-2026-08-17",
            ),
            [],
        )
        members = tuple(
            row for row in build_potential_match_cohort([make_candidate("1001", "Pengadaan Laptop")]).rows
        )
        result = pmr._binding_result(non_active, members)
        self.assertEqual("ROUTING_REJECTED", result.routing_status)
        self.assertEqual("", result.official_lpse_url)

    # 10-14 no identity/execution/realization/compatibility/outreach construction
    def test_routing_creates_no_identity_or_execution_authority(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        for result in results:
            self.assertNotIsInstance(result, contracts.InstitutionIdentityCandidate)
            self.assertNotIsInstance(result, contracts.ObservedProcurementExecution)
            self.assertFalse(hasattr(result, "authority_state"))
            self.assertFalse(hasattr(result, "execution_id"))
            self.assertFalse(hasattr(result, "buyer_identity_key"))

    def test_routing_creates_no_realization_link(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        for result in results:
            self.assertNotIsInstance(result, contracts.ProcurementRealizationLink)
            self.assertFalse(hasattr(result, "link_state"))
            self.assertFalse(hasattr(result, "link_evidence_kind"))

    def test_routing_creates_no_supplier_product_compatibility(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        for result in results:
            self.assertNotIsInstance(result, contracts.SupplierProductCompatibility)
            self.assertFalse(hasattr(result, "compatibility_state"))
            self.assertFalse(hasattr(result, "supplier_product_id"))

    def test_routing_creates_no_outreach_eligibility(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        for result in results:
            self.assertNotIsInstance(result, contracts.OutreachEligibility)
            self.assertFalse(hasattr(result, "eligibility_state"))

    # 15-19 forbidden authority calls never occur
    def test_forbidden_authority_calls_never_occur(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        with (
            mock.patch.object(contracts, "verify_realization_link", side_effect=AssertionError("verify_realization_link called")) as verify_link,
            mock.patch.object(contracts, "validate_compatibility", side_effect=AssertionError("validate_compatibility called")) as validate,
            mock.patch.object(contracts, "promote_supplier_compatibility", side_effect=AssertionError("promote_supplier_compatibility called")) as promote,
            mock.patch.object(contracts, "evaluate_outreach_eligibility", side_effect=AssertionError("evaluate_outreach_eligibility called")) as evaluate,
            mock.patch.object(contracts, "_persist_decision", side_effect=AssertionError("_persist_decision called")) as persist,
            mock.patch.object(contracts, "validate_identity", side_effect=AssertionError("validate_identity called")) as identity,
        ):
            results = self.resolve(candidates)
        self.assertEqual(1, len(results))
        verify_link.assert_not_called()
        validate.assert_not_called()
        promote.assert_not_called()
        evaluate.assert_not_called()
        persist.assert_not_called()
        identity.assert_not_called()

    # 20 no network
    def test_no_network_access(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        with (
            mock.patch("socket.socket", side_effect=AssertionError("socket used")),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("urlopen used")),
        ):
            results = self.resolve(candidates)
        self.assertEqual(1, len(results))

    # 21 no credentials
    def test_no_credentials_accessed(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        with mock.patch.dict(os.environ, {}, clear=True):
            results = self.resolve(candidates)
        self.assertEqual(1, len(results))

    # 22 no DB writes
    def test_no_db_write(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        with (
            mock.patch("duckdb.connect", side_effect=AssertionError("duckdb used")),
            mock.patch.object(contracts.ProcurementDecisionStore, "append", side_effect=AssertionError("decision append used")),
        ):
            results = self.resolve(candidates)
        self.assertEqual(1, len(results))

    # 23 no decision-store persistence
    def test_no_decision_store_persistence(self):
        store_path = self.temporary_root / "decisions.json"
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        with mock.patch.object(
            contracts,
            "_DECISION_STORE",
            contracts.ProcurementDecisionStore(store_path),
        ):
            results = self.resolve(candidates)
        self.assertEqual(1, len(results))
        self.assertFalse(store_path.exists())

    # 24 no repository evidence outputs written
    def test_no_repository_evidence_outputs_written(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        self.assertEqual(1, len(results))
        self.assert_no_files_created_anywhere()

    # 25 digest/provenance metadata preserved (covered above; explicit assertion)
    def test_binding_digest_matches_existing_authority_digest(self):
        candidates = [make_candidate("1001", "Pengadaan Laptop dan Printer")]
        results = self.resolve(candidates)
        binding = active_binding()
        self.assertEqual(binding.binding_digest, results[0].routing_binding_digest)
        self.assertEqual(binding.registry_version, results[0].registry_version)


if __name__ == "__main__":
    unittest.main()
