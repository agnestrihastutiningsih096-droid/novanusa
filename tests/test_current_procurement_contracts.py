import dataclasses
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import current_procurement_contracts as contracts  # noqa: E402
from current_procurement_contracts import *  # noqa: E402,F403


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        configure_decision_store(Path(self.temporary_directory.name) / "decisions.json")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def p(self, kind=SourceKind.CURRENT_SIRUP, maturity=SourceMaturity.BOUNDED_ACQUISITION_VERIFIED, acquisition="acq-1"):
        return SourceProvenance(kind, "public://fixture", "2026-08-15T00:00:00+00:00", acquisition, "receipt-1", "v1", maturity)

    def rup(self, **changes):
        values = dict(planned_procurement_id="planned-1", source_rup_id="62724616", id_satker="338553", id_kldi="D181", institution_name="Dinas Kesehatan", kldi_name="Kota Surabaya", package_title="Service Printer", budget=Decimal("1000"), procurement_type="Jasa Lainnya", procurement_method="Pengadaan Langsung", selection_period="2026", location="Surabaya", source_year=2026, provenance=self.p())
        values.update(changes)
        return RawCurrentRupCandidate(**values)

    def execution(self, **changes):
        values = dict(execution_id="execution-1", source_package_id="spse-1", source_kind=SourceKind.SPSE, id_satker_if_present=None, id_kldi_if_present=None, institution_name_if_present=None, package_title="Service Printer", execution_stage="PUBLISHED", procurement_method_if_present=None, contract_value_if_present=None, source_year=2026, provenance=self.p(SourceKind.SPSE))
        values.update(changes)
        return RawExecutionCandidate(**values)

    def compatibility(self, supplier="supplier-1"):
        return SupplierProductCompatibility("compat-" + supplier, "planned-1", supplier, "catalog-v1", "product-1", CompatibilityState.COMPATIBILITY_CANDIDATE, "catalog rule", self.p(SourceKind.SUPPLIER_CATALOG))

    def contact(self, value="buyer@example.go.id", buyer="338553"):
        p = self.p(SourceKind.CONTACT_SOURCE)
        return RawContactCandidate("contact-1", buyer, ContactType.EMAIL, value, SourceKind.CONTACT_SOURCE, p.source_locator, p.observed_at, p)

    def verified_bundle(self):
        raw = self.rup()
        planned = promote_current_planned_procurement(raw, validate_identity(raw, ("sirup-row-1",)))
        candidate = self.compatibility()
        compatibility = promote_supplier_compatibility(candidate, validate_compatibility(candidate, ("catalog-row-1",)))
        raw_contact = self.contact()
        contact = promote_contact_evidence(raw_contact, validate_contact(raw_contact, ("directory-row-1",)))
        return planned, compatibility, contact

    def test_valid_gate_promotions_and_separation(self):
        planned, compatibility, contact = self.verified_bundle()
        execution = self.execution()
        promoted_execution = promote_observed_execution(execution, validate_execution(execution, ("spse-row-1",)))
        self.assertEqual(CurrentRupState.CURRENT_RUP_VERIFIED, planned.authority_state)
        self.assertEqual(ExecutionState.EXECUTION_VERIFIED, promoted_execution.authority_state)
        self.assertFalse(hasattr(planned, "supplier_id"))
        self.assertFalse(hasattr(planned, "contact_value"))
        self.assertFalse(hasattr(promoted_execution, "source_rup_id"))
        self.assertEqual(CompatibilityState.COMPATIBILITY_VERIFIED, compatibility.compatibility_state)
        self.assertEqual(ContactState.CONTACT_VERIFIED, contact.verification_state)

    def test_required_fields_and_taxonomy(self):
        with self.assertRaises(ContractError): validate_identity(self.rup(id_satker="   "), ("row",))
        with self.assertRaises(ContractError): validate_execution(self.execution(source_package_id=""), ("row",))
        with self.assertRaises(ContractError): validate_contact(self.contact(""), ("row",))
        binding = GovernedDemandClassificationBinding("planned-1", "v1", TAXONOMY_SHA256, "resolver-v1", "GOVERNED", ("printing",), ("printer",), ("rule-1",))
        self.assertFalse(hasattr(binding, "execution_id"))
        with self.assertRaises(ContractError): dataclasses.replace(binding, taxonomy_sha256="wrong")

    def test_unknown_authority_fields_fail_closed(self):
        values = {name: getattr(self.rup(), name) for name in RawCurrentRupCandidate.__dataclass_fields__}
        for name in ("opportunityScore", "aiScore", "contactEmail", "contactPhone", "supplierId", "outreachEligible", "executionVerified", "releaseDecision", "authorityOverride"):
            with self.subTest(name=name):
                with self.assertRaises(TypeError): RawCurrentRupCandidate(**{**values, name: True})

    def test_direct_current_rup_verified_blocked_case_a(self):
        values = {name: getattr(self.rup(), name) for name in RawCurrentRupCandidate.__dataclass_fields__}
        with self.assertRaises(ContractError): CurrentPlannedProcurement(**values, authority_state=CurrentRupState.CURRENT_RUP_VERIFIED)

    def test_direct_execution_verified_blocked_case_b(self):
        values = {name: getattr(self.execution(), name) for name in RawExecutionCandidate.__dataclass_fields__}
        with self.assertRaises(ContractError): ObservedProcurementExecution(**values, authority_state=ExecutionState.EXECUTION_VERIFIED)

    def test_link_verified_direct_title_and_manual_blocked_cases_c_d_s(self):
        for kind in (LinkEvidenceKind.TITLE_CANDIDATE_ONLY, LinkEvidenceKind.MANUAL_REVIEW):
            with self.subTest(kind=kind):
                with self.assertRaises(ContractError): ProcurementRealizationLink("p", "e", LinkState.LINK_VERIFIED, kind, "value", self.p(SourceKind.SPSE))
                candidate = ProcurementRealizationLink("p", "e", LinkState.LINK_CANDIDATE, kind, "value", self.p(SourceKind.SPSE))
                with self.assertRaises(ContractError): verify_realization_link(candidate)
        exact = ProcurementRealizationLink("p", "e", LinkState.LINK_CANDIDATE, LinkEvidenceKind.EXACT_RUP_ID_FROM_EXECUTION_DETAIL, "627", self.p(SourceKind.SPSE))
        verified = verify_realization_link(exact)
        self.assertEqual(LinkState.LINK_VERIFIED, verified.link_state)
        self.assertTrue(is_realization_link_authorized(verified))
        object.__setattr__(verified, "execution_id", "forged")
        self.assertFalse(is_realization_link_authorized(verified))

    def test_direct_compatibility_verified_blocked_case_e(self):
        with self.assertRaises(ContractError): dataclasses.replace(self.compatibility(), compatibility_state=CompatibilityState.COMPATIBILITY_VERIFIED)

    def test_direct_contact_verified_blocked_case_f(self):
        values = {name: getattr(self.contact(), name) for name in RawContactCandidate.__dataclass_fields__}
        with self.assertRaises(ContractError): ContactEvidence(**values, verification_state=ContactState.CONTACT_VERIFIED)

    def test_direct_eligible_blocked_case_g(self):
        with self.assertRaises(ContractError): OutreachEligibility("b", "p", "c", "e", EligibilityState.ELIGIBLE, ())

    def test_completeness_boolean_and_binding_blocked_cases_h_r(self):
        complete_p = self.p(maturity=SourceMaturity.COMPLETE_COVERAGE_VERIFIED)
        with self.assertRaises(TypeError): AcquisitionResult((), complete_p, SourceAvailability.SOURCE_COMPLETE_VERIFIED, completeness_verified=True)
        proof = validate_completeness(complete_p, "bounded-fixture", ("page-ledger",))
        other = self.p(maturity=SourceMaturity.COMPLETE_COVERAGE_VERIFIED, acquisition="acq-2")
        with self.assertRaises(ContractError): AcquisitionResult((), other, SourceAvailability.SOURCE_COMPLETE_VERIFIED, completeness_verification=proof)
        self.assertEqual(SourceAvailability.SOURCE_COMPLETE_VERIFIED, AcquisitionResult((), complete_p, SourceAvailability.SOURCE_COMPLETE_VERIFIED, completeness_verification=proof).availability)

    def test_provider_canonical_injection_blocked_cases_i_j_k(self):
        planned, _, contact = self.verified_bundle()
        raw_execution = self.execution()
        execution = promote_observed_execution(raw_execution, validate_execution(raw_execution, ("row",)))
        with self.assertRaises(ContractError): validate_current_rup_provider_result(AcquisitionResult((planned,), planned.provenance, SourceAvailability.SOURCE_REACHABLE))
        with self.assertRaises(ContractError): validate_observed_execution_provider_result(AcquisitionResult((execution,), execution.provenance, SourceAvailability.SOURCE_REACHABLE))
        with self.assertRaises(ContractError): validate_contact_evidence_provider_result(AcquisitionResult((contact,), contact.provenance, SourceAvailability.SOURCE_REACHABLE))
        validate_current_rup_provider_result(AcquisitionResult((self.rup(),), self.p(), SourceAvailability.SOURCE_REACHABLE))

    def test_legacy_boolean_and_string_authority_removed_cases_l_m_n(self):
        with self.assertRaises(TypeError): promote_current_planned_procurement(self.rup(), identity_verified=True)
        with self.assertRaises(TypeError): promote_observed_execution(self.execution(), execution_verified=True)
        with self.assertRaises(TypeError): promote_contact_evidence(self.contact(), verification_evidence="arbitrary")

    def test_subject_binding_cases_o_p_q(self):
        raw_a = self.rup()
        proof_a = validate_identity(raw_a, ("row",))
        with self.assertRaises(ContractError): promote_current_planned_procurement(self.rup(planned_procurement_id="planned-2"), proof_a)
        execution_a = self.execution()
        execution_proof = validate_execution(execution_a, ("row",))
        with self.assertRaises(ContractError): promote_observed_execution(self.execution(source_package_id="spse-2"), execution_proof)
        contact_a = self.contact()
        contact_proof = validate_contact(contact_a, ("row",))
        with self.assertRaises(ContractError): promote_contact_evidence(self.contact(buyer="other"), contact_proof)

    def test_outreach_fail_closed_and_review_only_case_t(self):
        planned, compatibility, contact = self.verified_bundle()
        self.assertEqual(EligibilityState.NOT_ELIGIBLE, evaluate_outreach_eligibility(planned=planned).eligibility_state)
        self.assertEqual(EligibilityState.NOT_ELIGIBLE, evaluate_outreach_eligibility(compatibility=compatibility).eligibility_state)
        self.assertEqual(EligibilityState.NOT_ELIGIBLE, evaluate_outreach_eligibility(contact=contact).eligibility_state)
        result = evaluate_outreach_eligibility(planned, compatibility, contact)
        self.assertEqual(EligibilityState.ELIGIBLE_FOR_REVIEW, result.eligibility_state)
        self.assertNotEqual(EligibilityState.ELIGIBLE, result.eligibility_state)

    def test_source_states_and_multi_supplier(self):
        p = self.p()
        self.assertNotEqual(AcquisitionResult((), p, SourceAvailability.SOURCE_UNAVAILABLE).availability, AcquisitionResult((), p, SourceAvailability.SOURCE_REACHABLE, no_result=True).availability)
        self.assertNotEqual(SourceAvailability.SOURCE_PARTIAL, SourceAvailability.SOURCE_COMPLETE_VERIFIED)
        first, second = self.compatibility("one"), self.compatibility("two")
        self.assertEqual(first.planned_procurement_id, second.planned_procurement_id)
        self.assertNotEqual(first.supplier_id, second.supplier_id)

    def test_persisted_decisions_are_non_rebindable_and_state_mutation_is_not_authority(self):
        raw = self.rup()
        proof = validate_identity(raw, ("row",))
        self.assertTrue(is_current_rup_authorized(promote_current_planned_procurement(raw, proof)))
        with self.assertRaises(ContractError): dataclasses.replace(proof, subject_id="planned-2")
        candidate = CurrentPlannedProcurement(**{name: getattr(raw, name) for name in RawCurrentRupCandidate.__dataclass_fields__}, authority_state=CurrentRupState.CURRENT_RUP_CANDIDATE)
        object.__setattr__(candidate, "authority_state", CurrentRupState.CURRENT_RUP_VERIFIED)
        self.assertFalse(is_current_rup_authorized(candidate))
        self.assertFalse(hasattr(contracts, "_issue_seal"))

    def test_store_rejects_forged_proof_and_rebound_completeness(self):
        p = self.p(maturity=SourceMaturity.COMPLETE_COVERAGE_VERIFIED)
        with self.assertRaises(ContractError):
            AcquisitionResult((), p, SourceAvailability.SOURCE_COMPLETE_VERIFIED, completeness_verification=CompletenessVerificationResult("VERIFIED", "a", (p.source_kind, p.acquisition_id, p.raw_receipt_id), ("fake",), "caller-id", "2026-08-16T00:00:00+00:00", "scope"))
        proof = validate_completeness(p, "scope", ("ledger",))
        with self.assertRaises(ContractError): dataclasses.replace(proof, subject_id="other")

    def test_outreach_state_mutation_does_not_authorize(self):
        planned, compatibility, contact = self.verified_bundle()
        result = evaluate_outreach_eligibility(planned, compatibility, contact)
        self.assertFalse(is_outreach_review_authorized(result))
        object.__setattr__(result, "eligibility_state", EligibilityState.ELIGIBLE)
        self.assertFalse(is_outreach_review_authorized(result))
        self.assertTrue(is_current_rup_authorized(planned))

    def test_authority_uses_fresh_persisted_lookup_and_survives_reconfiguration(self):
        raw = self.rup()
        proof = validate_identity(raw, ("row",))
        planned = promote_current_planned_procurement(raw, proof)
        store_path = Path(self.temporary_directory.name) / "decisions.json"
        configure_decision_store(store_path)
        self.assertTrue(is_current_rup_authorized(planned))
        state = __import__("json").loads(store_path.read_text(encoding="utf-8"))
        state["decisions"][0]["bindings"]["id_satker"] = "attacker"
        store_path.write_text(__import__("json").dumps(state), encoding="utf-8")
        self.assertFalse(is_current_rup_authorized(planned))

    def test_mutated_or_wrong_kind_decision_fails_closed(self):
        raw = self.rup()
        proof = validate_identity(raw, ("row",))
        planned = promote_current_planned_procurement(raw, proof)
        object.__setattr__(proof, "decision_id", "forged")
        self.assertFalse(is_current_rup_authorized(planned))
        execution = self.execution(execution_id=raw.planned_procurement_id)
        values = {name: getattr(execution, name) for name in RawExecutionCandidate.__dataclass_fields__}
        forged = ObservedProcurementExecution(**values, authority_state=ExecutionState.EXECUTION_CANDIDATE)
        object.__setattr__(forged, "authority_state", ExecutionState.EXECUTION_VERIFIED)
        object.__setattr__(forged, "verification", proof)
        self.assertFalse(is_execution_authorized(forged))


if __name__ == "__main__":
    unittest.main()
