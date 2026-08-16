"""Fail-closed canonical contracts for current procurement authority boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import os
from pathlib import Path
import uuid
from typing import Generic, Protocol, TypeVar

from current_procurement_decision_store import (
    DecisionStoreError,
    ProcurementDecisionStore,
    RECORD_SCHEMA,
    RECORD_VERSION,
)

TAXONOMY_SHA256 = "3864ef756fc96aa5e0454335f0ac38154d3a3417a6e5300b781ed550f657ffe0"


class ContractError(ValueError):
    pass


class ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class SourceKind(ValueEnum):
    HISTORICAL_PROCUREMENT = "HISTORICAL_PROCUREMENT"
    CURRENT_SIRUP = "CURRENT_SIRUP"
    SPSE = "SPSE"
    LPSE = "LPSE"
    CONTACT_SOURCE = "CONTACT_SOURCE"
    SUPPLIER_CATALOG = "SUPPLIER_CATALOG"


class SourceMaturity(ValueEnum):
    DISCOVERED = "DISCOVERED"
    CONTRACT_VERIFIED = "CONTRACT_VERIFIED"
    BOUNDED_ACQUISITION_VERIFIED = "BOUNDED_ACQUISITION_VERIFIED"
    PAGINATION_INTEGRITY_VERIFIED = "PAGINATION_INTEGRITY_VERIFIED"
    COMPLETE_COVERAGE_VERIFIED = "COMPLETE_COVERAGE_VERIFIED"
    TRUSTED_ACQUISITION = "TRUSTED_ACQUISITION"


class SourceAvailability(ValueEnum):
    SOURCE_REACHABLE = "SOURCE_REACHABLE"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    SOURCE_COMPLETE_VERIFIED = "SOURCE_COMPLETE_VERIFIED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class CurrentRupState(ValueEnum):
    CURRENT_RUP_VERIFIED = "CURRENT_RUP_VERIFIED"
    CURRENT_RUP_CANDIDATE = "CURRENT_RUP_CANDIDATE"
    CURRENT_RUP_REJECTED = "CURRENT_RUP_REJECTED"


class ExecutionState(ValueEnum):
    EXECUTION_CANDIDATE = "EXECUTION_CANDIDATE"
    EXECUTION_VERIFIED = "EXECUTION_VERIFIED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"


class LinkState(ValueEnum):
    LINK_CANDIDATE = "LINK_CANDIDATE"
    LINK_VERIFIED = "LINK_VERIFIED"
    LINK_REJECTED = "LINK_REJECTED"
    LINK_UNRESOLVED = "LINK_UNRESOLVED"


class LinkEvidenceKind(ValueEnum):
    EXACT_RUP_ID_FROM_EXECUTION_DETAIL = "EXACT_RUP_ID_FROM_EXECUTION_DETAIL"
    EXACT_KODE_RUP_FROM_EXECUTION_DETAIL = "EXACT_KODE_RUP_FROM_EXECUTION_DETAIL"
    EXACT_SOURCE_REFERENCE = "EXACT_SOURCE_REFERENCE"
    TITLE_CANDIDATE_ONLY = "TITLE_CANDIDATE_ONLY"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class CompatibilityState(ValueEnum):
    COMPATIBILITY_CANDIDATE = "COMPATIBILITY_CANDIDATE"
    COMPATIBILITY_VERIFIED = "COMPATIBILITY_VERIFIED"
    COMPATIBILITY_REJECTED = "COMPATIBILITY_REJECTED"
    COMPATIBILITY_UNRESOLVED = "COMPATIBILITY_UNRESOLVED"


class ContactType(ValueEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    WHATSAPP_BUSINESS = "WHATSAPP_BUSINESS"
    WEBSITE_CONTACT = "WEBSITE_CONTACT"
    OTHER = "OTHER"


class ContactState(ValueEnum):
    CONTACT_CANDIDATE = "CONTACT_CANDIDATE"
    CONTACT_VERIFIED = "CONTACT_VERIFIED"
    CONTACT_REJECTED = "CONTACT_REJECTED"
    CONTACT_STALE = "CONTACT_STALE"


class EligibilityState(ValueEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    ELIGIBLE_FOR_REVIEW = "ELIGIBLE_FOR_REVIEW"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


def _required(value: object, name: str) -> None:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ContractError(f"{name} is required")


class AuthorityKind(ValueEnum):
    IDENTITY = "IDENTITY"
    EXECUTION = "EXECUTION"
    LINK = "LINK"
    COMPATIBILITY = "COMPATIBILITY"
    CONTACT = "CONTACT"
    COMPLETENESS = "COMPLETENESS"
    OUTREACH_REVIEW = "OUTREACH_REVIEW"


_DECISION_STORE = ProcurementDecisionStore(
    os.environ.get(
        "NOVANUSA_PROCUREMENT_DECISION_STORE",
        str(Path(__file__).resolve().parents[1] / "data" / "current_procurement_decisions.json"),
    )
)


def configure_decision_store(path: str | os.PathLike[str]) -> None:
    """Select the durable procurement decision store (primarily for isolation/tests)."""
    global _DECISION_STORE
    _DECISION_STORE = ProcurementDecisionStore(path)


def _json_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _decision_record(kind: AuthorityKind, decision_id: str, timestamp: str, subject: str,
                     provenance: tuple[SourceKind, str, str], evidence: tuple[str, ...],
                     bindings: dict[str, object]) -> dict[str, object]:
    return {
        "schema": RECORD_SCHEMA,
        "version": RECORD_VERSION,
        "decision_id": decision_id,
        "kind": kind.value,
        "result": "VERIFIED",
        "subject": subject,
        "provenance": _json_value(provenance),
        "evidence_references": _json_value(evidence),
        "timestamp": timestamp,
        "bindings": _json_value(bindings),
    }


def _persist_decision(kind: AuthorityKind, subject: str, provenance: tuple[SourceKind, str, str],
                      evidence: tuple[str, ...], bindings: dict[str, object]) -> tuple[str, str]:
    decision_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()
    _DECISION_STORE.append(_decision_record(kind, decision_id, timestamp, subject, provenance, evidence, bindings))
    return decision_id, timestamp


def _persisted_exact(proof: object, kind: AuthorityKind, bindings: dict[str, object]) -> bool:
    try:
        return _DECISION_STORE.contains_exact(_decision_record(
            kind, proof.decision_id, proof.timestamp, proof.subject_id,
            proof.provenance_binding, proof.evidence_references, bindings,
        ))
    except (AttributeError, DecisionStoreError, TypeError, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    source_kind: SourceKind
    source_locator: str
    observed_at: str
    acquisition_id: str
    raw_receipt_id: str
    schema_version: str
    source_maturity: SourceMaturity

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, SourceKind):
            raise ContractError("unknown source kind")
        if not isinstance(self.source_maturity, SourceMaturity):
            raise ContractError("invalid source maturity")
        for name in ("source_locator", "observed_at", "acquisition_id", "raw_receipt_id", "schema_version"):
            _required(getattr(self, name), name)
        try:
            datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError("observed_at must be ISO-8601") from exc


def _provenance_binding(value: SourceProvenance) -> tuple[SourceKind, str, str]:
    return value.source_kind, value.acquisition_id, value.raw_receipt_id


@dataclass(frozen=True, slots=True)
class _GateResult:
    decision: str
    subject_id: str
    provenance_binding: tuple[SourceKind, str, str]
    evidence_references: tuple[str, ...]
    decision_id: str
    timestamp: str
    schema: str = field(default=RECORD_SCHEMA, init=False)
    version: int = field(default=RECORD_VERSION, init=False)

    def __post_init__(self) -> None:
        _required(self.subject_id, "subject_id")
        if not self.evidence_references or any(not value.strip() for value in self.evidence_references):
            raise ContractError("deterministic evidence references are required")
        _required(self.decision_id, "decision_id")
        _required(self.timestamp, "timestamp")
        if self.decision != "VERIFIED" or self.schema != RECORD_SCHEMA or self.version != RECORD_VERSION:
            raise ContractError("gate result is not a supported verified decision")
        identified = _proof_bindings(self)
        if identified is None or not _persisted_exact(self, identified[0], identified[1]):
            raise ContractError("gate result has no exact persisted decision")


@dataclass(frozen=True, slots=True)
class IdentityVerificationResult(_GateResult):
    id_satker: str


@dataclass(frozen=True, slots=True)
class ExecutionVerificationResult(_GateResult):
    source_package_id: str


@dataclass(frozen=True, slots=True)
class CompatibilityVerificationResult(_GateResult):
    supplier_product_id: str


@dataclass(frozen=True, slots=True)
class ContactVerificationResult(_GateResult):
    buyer_identity_key: str
    contact_value: str


@dataclass(frozen=True, slots=True)
class CompletenessVerificationResult(_GateResult):
    observed_scope: str


def _proof_bindings(proof: _GateResult) -> tuple[AuthorityKind, dict[str, object]] | None:
    if type(proof) is IdentityVerificationResult:
        return AuthorityKind.IDENTITY, {"id_satker": proof.id_satker}
    if type(proof) is ExecutionVerificationResult:
        return AuthorityKind.EXECUTION, {"source_package_id": proof.source_package_id}
    if type(proof) is CompatibilityVerificationResult:
        return AuthorityKind.COMPATIBILITY, {"supplier_product_id": proof.supplier_product_id}
    if type(proof) is ContactVerificationResult:
        return AuthorityKind.CONTACT, {"buyer_identity_key": proof.buyer_identity_key, "contact_value": proof.contact_value}
    if type(proof) is CompletenessVerificationResult:
        return AuthorityKind.COMPLETENESS, {"observed_scope": proof.observed_scope}
    return None


def _valid_proof(proof: object, expected_kind: AuthorityKind) -> bool:
    if not isinstance(proof, _GateResult) or proof.decision != "VERIFIED":
        return False
    identified = _proof_bindings(proof)
    return identified is not None and identified[0] is expected_kind and _persisted_exact(proof, expected_kind, identified[1])


@dataclass(frozen=True, slots=True)
class RawCurrentRupCandidate:
    planned_procurement_id: str
    source_rup_id: str
    id_satker: str
    id_kldi: str
    institution_name: str
    kldi_name: str
    package_title: str
    budget: Decimal | None
    procurement_type: str
    procurement_method: str
    selection_period: str
    location: str
    source_year: int
    provenance: SourceProvenance


@dataclass(frozen=True, slots=True)
class CurrentPlannedProcurement(RawCurrentRupCandidate):
    authority_state: CurrentRupState
    verification: IdentityVerificationResult | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self.authority_state is CurrentRupState.CURRENT_RUP_VERIFIED:
            proof = self.verification
            if not isinstance(proof, IdentityVerificationResult) or not _valid_proof(proof, AuthorityKind.IDENTITY):
                raise ContractError("CURRENT_RUP_VERIFIED requires persisted identity evidence")
            if proof.subject_id != self.planned_procurement_id or proof.id_satker != self.id_satker or proof.provenance_binding != _provenance_binding(self.provenance):
                raise ContractError("identity evidence is not bound to this procurement")


@dataclass(frozen=True, slots=True)
class RawExecutionCandidate:
    execution_id: str
    source_package_id: str
    source_kind: SourceKind
    id_satker_if_present: str | None
    id_kldi_if_present: str | None
    institution_name_if_present: str | None
    package_title: str
    execution_stage: str
    procurement_method_if_present: str | None
    contract_value_if_present: Decimal | None
    source_year: int
    provenance: SourceProvenance


@dataclass(frozen=True, slots=True)
class ObservedProcurementExecution(RawExecutionCandidate):
    authority_state: ExecutionState
    verification: ExecutionVerificationResult | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self.authority_state is ExecutionState.EXECUTION_VERIFIED:
            proof = self.verification
            if not isinstance(proof, ExecutionVerificationResult) or not _valid_proof(proof, AuthorityKind.EXECUTION):
                raise ContractError("EXECUTION_VERIFIED requires persisted execution evidence")
            if proof.subject_id != self.execution_id or proof.source_package_id != self.source_package_id or proof.provenance_binding != _provenance_binding(self.provenance):
                raise ContractError("execution evidence is not bound to this package")


@dataclass(frozen=True, slots=True)
class ProcurementRealizationLink:
    planned_procurement_id: str
    execution_id: str
    link_state: LinkState
    link_evidence_kind: LinkEvidenceKind
    link_evidence_value: str
    provenance: SourceProvenance
    decision_id: str | None = field(repr=False, compare=False, default=None)
    decision_timestamp: str | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self.link_state is LinkState.LINK_VERIFIED:
            bindings = {"execution_id": self.execution_id, "link_evidence_kind": self.link_evidence_kind, "link_evidence_value": self.link_evidence_value}
            try:
                exact = _DECISION_STORE.contains_exact(_decision_record(AuthorityKind.LINK, self.decision_id, self.decision_timestamp, self.planned_procurement_id, _provenance_binding(self.provenance), (self.link_evidence_value,), bindings))
            except (DecisionStoreError, TypeError, ValueError):
                exact = False
            if not exact:
                raise ContractError("LINK_VERIFIED requires persisted realization evidence")
            if self.link_evidence_kind not in _AUTHORITATIVE_LINK_EVIDENCE:
                raise ContractError("link evidence is not authoritative")


@dataclass(frozen=True, slots=True)
class GovernedDemandClassificationBinding:
    planned_procurement_id: str
    taxonomy_version: str
    taxonomy_sha256: str
    printing_resolver_version: str
    semantic_state: str
    demand_families: tuple[str, ...]
    matched_terms: tuple[str, ...]
    rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _required(self.planned_procurement_id, "planned_procurement_id")
        if self.taxonomy_sha256 != TAXONOMY_SHA256:
            raise ContractError("taxonomy hash is not authoritative")


@dataclass(frozen=True, slots=True)
class SupplierProductCompatibility:
    compatibility_id: str
    planned_procurement_id: str
    supplier_id: str
    supplier_catalog_version: str
    supplier_product_id: str
    compatibility_state: CompatibilityState
    compatibility_basis: str
    provenance: SourceProvenance
    verification: CompatibilityVerificationResult | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self.compatibility_state is CompatibilityState.COMPATIBILITY_VERIFIED:
            proof = self.verification
            if not isinstance(proof, CompatibilityVerificationResult) or not _valid_proof(proof, AuthorityKind.COMPATIBILITY):
                raise ContractError("COMPATIBILITY_VERIFIED requires persisted evidence")
            if proof.subject_id != self.compatibility_id or proof.supplier_product_id != self.supplier_product_id or proof.provenance_binding != _provenance_binding(self.provenance):
                raise ContractError("compatibility evidence is not bound to this product")


@dataclass(frozen=True, slots=True)
class RawContactCandidate:
    contact_evidence_id: str
    buyer_identity_key: str
    contact_type: ContactType
    contact_value: str
    source_kind: SourceKind
    source_locator: str
    observed_at: str
    provenance: SourceProvenance


@dataclass(frozen=True, slots=True)
class ContactEvidence(RawContactCandidate):
    verification_state: ContactState
    verification: ContactVerificationResult | None = field(repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        if self.verification_state is ContactState.CONTACT_VERIFIED:
            proof = self.verification
            if not isinstance(proof, ContactVerificationResult) or not _valid_proof(proof, AuthorityKind.CONTACT):
                raise ContractError("CONTACT_VERIFIED requires persisted evidence")
            if proof.subject_id != self.contact_evidence_id or proof.buyer_identity_key != self.buyer_identity_key or proof.contact_value != self.contact_value or proof.provenance_binding != _provenance_binding(self.provenance):
                raise ContractError("contact evidence is not bound to this contact")


@dataclass(frozen=True, slots=True)
class OutreachEligibility:
    buyer_identity_key: str
    planned_procurement_id: str
    product_compatibility_id_if_present: str | None
    contact_evidence_id_if_present: str | None
    eligibility_state: EligibilityState
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.eligibility_state is EligibilityState.ELIGIBLE:
            raise ContractError("ELIGIBLE is unreachable until an approval gate exists")


@dataclass(frozen=True, slots=True)
class InstitutionIdentityCandidate:
    buyer_identity_key: str
    id_satker: str
    id_kldi: str
    institution_name: str
    provenance: SourceProvenance
    resolution_evidence: str


CandidateT = TypeVar("CandidateT")


@dataclass(frozen=True, slots=True)
class AcquisitionResult(Generic[CandidateT]):
    candidates: tuple[CandidateT, ...]
    provenance: SourceProvenance
    availability: SourceAvailability
    no_result: bool = False
    completeness_verification: CompletenessVerificationResult | None = field(repr=False, default=None)
    deduplicated: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.availability, SourceAvailability):
            raise ContractError("invalid source availability")
        if self.availability is SourceAvailability.SOURCE_UNAVAILABLE and (self.candidates or self.no_result):
            raise ContractError("unavailable source cannot assert an empty result")
        if self.availability is SourceAvailability.SOURCE_COMPLETE_VERIFIED:
            proof = self.completeness_verification
            if not isinstance(proof, CompletenessVerificationResult) or not _valid_proof(proof, AuthorityKind.COMPLETENESS):
                raise ContractError("complete availability requires persisted completeness evidence")
            if proof.subject_id != self.provenance.acquisition_id or proof.provenance_binding != _provenance_binding(self.provenance):
                raise ContractError("completeness evidence is not bound to this acquisition")


class CurrentRupProvider(Protocol):
    def acquire(self) -> AcquisitionResult[RawCurrentRupCandidate]: ...


class ObservedExecutionProvider(Protocol):
    def acquire(self) -> AcquisitionResult[RawExecutionCandidate]: ...


class InstitutionIdentityProvider(Protocol):
    def resolve(self, id_satker: str) -> AcquisitionResult[InstitutionIdentityCandidate]: ...


class ContactEvidenceProvider(Protocol):
    def discover(self, buyer_identity_key: str) -> AcquisitionResult[RawContactCandidate]: ...


def _validate_provider_result(result: AcquisitionResult[object], candidate_type: type, label: str) -> None:
    if not isinstance(result, AcquisitionResult):
        raise ContractError(f"{label} must return AcquisitionResult")
    if any(type(candidate) is not candidate_type for candidate in result.candidates):
        raise ContractError(f"{label} returned a canonical or wrong candidate type")


def validate_current_rup_provider_result(result: AcquisitionResult[RawCurrentRupCandidate]) -> None:
    _validate_provider_result(result, RawCurrentRupCandidate, "CurrentRupProvider")


def validate_observed_execution_provider_result(result: AcquisitionResult[RawExecutionCandidate]) -> None:
    _validate_provider_result(result, RawExecutionCandidate, "ObservedExecutionProvider")


def validate_institution_identity_provider_result(result: AcquisitionResult[InstitutionIdentityCandidate]) -> None:
    _validate_provider_result(result, InstitutionIdentityCandidate, "InstitutionIdentityProvider")


def validate_contact_evidence_provider_result(result: AcquisitionResult[RawContactCandidate]) -> None:
    _validate_provider_result(result, RawContactCandidate, "ContactEvidenceProvider")


def is_current_rup_authorized(value: CurrentPlannedProcurement) -> bool:
    proof = value.verification
    return value.authority_state is CurrentRupState.CURRENT_RUP_VERIFIED and isinstance(proof, IdentityVerificationResult) and _valid_proof(proof, AuthorityKind.IDENTITY) and proof.subject_id == value.planned_procurement_id and proof.id_satker == value.id_satker and proof.provenance_binding == _provenance_binding(value.provenance)


def is_execution_authorized(value: ObservedProcurementExecution) -> bool:
    proof = value.verification
    return value.authority_state is ExecutionState.EXECUTION_VERIFIED and isinstance(proof, ExecutionVerificationResult) and _valid_proof(proof, AuthorityKind.EXECUTION) and proof.subject_id == value.execution_id and proof.source_package_id == value.source_package_id and proof.provenance_binding == _provenance_binding(value.provenance)


def is_realization_link_authorized(value: ProcurementRealizationLink) -> bool:
    if value.link_state is not LinkState.LINK_VERIFIED or value.link_evidence_kind not in _AUTHORITATIVE_LINK_EVIDENCE:
        return False
    bindings = {"execution_id": value.execution_id, "link_evidence_kind": value.link_evidence_kind, "link_evidence_value": value.link_evidence_value}
    try:
        return _DECISION_STORE.contains_exact(_decision_record(AuthorityKind.LINK, value.decision_id, value.decision_timestamp, value.planned_procurement_id, _provenance_binding(value.provenance), (value.link_evidence_value,), bindings))
    except (DecisionStoreError, TypeError, ValueError):
        return False


def is_compatibility_authorized(value: SupplierProductCompatibility) -> bool:
    proof = value.verification
    return value.compatibility_state is CompatibilityState.COMPATIBILITY_VERIFIED and isinstance(proof, CompatibilityVerificationResult) and _valid_proof(proof, AuthorityKind.COMPATIBILITY) and proof.subject_id == value.compatibility_id and proof.supplier_product_id == value.supplier_product_id and proof.provenance_binding == _provenance_binding(value.provenance)


def is_contact_authorized(value: ContactEvidence) -> bool:
    proof = value.verification
    return value.verification_state is ContactState.CONTACT_VERIFIED and isinstance(proof, ContactVerificationResult) and _valid_proof(proof, AuthorityKind.CONTACT) and proof.subject_id == value.contact_evidence_id and proof.buyer_identity_key == value.buyer_identity_key and proof.contact_value == value.contact_value and proof.provenance_binding == _provenance_binding(value.provenance)


def is_complete_acquisition_authorized(value: AcquisitionResult[object]) -> bool:
    proof = value.completeness_verification
    return value.availability is SourceAvailability.SOURCE_COMPLETE_VERIFIED and isinstance(proof, CompletenessVerificationResult) and _valid_proof(proof, AuthorityKind.COMPLETENESS) and proof.subject_id == value.provenance.acquisition_id and proof.provenance_binding == _provenance_binding(value.provenance)


def is_outreach_review_authorized(value: OutreachEligibility) -> bool:
    return False


def validate_identity(candidate: RawCurrentRupCandidate, evidence_references: tuple[str, ...]) -> IdentityVerificationResult:
    for name in ("planned_procurement_id", "source_rup_id", "id_satker", "id_kldi", "institution_name", "kldi_name", "package_title"):
        _required(getattr(candidate, name), name)
    if not isinstance(candidate.provenance, SourceProvenance) or candidate.provenance.source_kind is not SourceKind.CURRENT_SIRUP:
        raise ContractError("current RUP identity requires CURRENT_SIRUP provenance")
    decision_id, timestamp = _persist_decision(AuthorityKind.IDENTITY, candidate.planned_procurement_id, _provenance_binding(candidate.provenance), evidence_references, {"id_satker": candidate.id_satker})
    return IdentityVerificationResult("VERIFIED", candidate.planned_procurement_id, _provenance_binding(candidate.provenance), evidence_references, decision_id, timestamp, candidate.id_satker)


def promote_current_planned_procurement(candidate: RawCurrentRupCandidate, verification: IdentityVerificationResult) -> CurrentPlannedProcurement:
    return CurrentPlannedProcurement(**{name: getattr(candidate, name) for name in RawCurrentRupCandidate.__dataclass_fields__}, authority_state=CurrentRupState.CURRENT_RUP_VERIFIED, verification=verification)


def validate_execution(candidate: RawExecutionCandidate, evidence_references: tuple[str, ...]) -> ExecutionVerificationResult:
    for name in ("execution_id", "source_package_id", "package_title"):
        _required(getattr(candidate, name), name)
    if candidate.source_kind not in {SourceKind.SPSE, SourceKind.LPSE} or candidate.provenance.source_kind is not candidate.source_kind:
        raise ContractError("execution source and provenance must be SPSE or LPSE")
    decision_id, timestamp = _persist_decision(AuthorityKind.EXECUTION, candidate.execution_id, _provenance_binding(candidate.provenance), evidence_references, {"source_package_id": candidate.source_package_id})
    return ExecutionVerificationResult("VERIFIED", candidate.execution_id, _provenance_binding(candidate.provenance), evidence_references, decision_id, timestamp, candidate.source_package_id)


def promote_observed_execution(candidate: RawExecutionCandidate, verification: ExecutionVerificationResult) -> ObservedProcurementExecution:
    return ObservedProcurementExecution(**{name: getattr(candidate, name) for name in RawExecutionCandidate.__dataclass_fields__}, authority_state=ExecutionState.EXECUTION_VERIFIED, verification=verification)


_AUTHORITATIVE_LINK_EVIDENCE = frozenset({LinkEvidenceKind.EXACT_RUP_ID_FROM_EXECUTION_DETAIL, LinkEvidenceKind.EXACT_KODE_RUP_FROM_EXECUTION_DETAIL, LinkEvidenceKind.EXACT_SOURCE_REFERENCE})


def verify_realization_link(link: ProcurementRealizationLink) -> ProcurementRealizationLink:
    _required(link.planned_procurement_id, "planned_procurement_id")
    _required(link.execution_id, "execution_id")
    _required(link.link_evidence_value, "link_evidence_value")
    if link.link_evidence_kind not in _AUTHORITATIVE_LINK_EVIDENCE:
        raise ContractError("link evidence is not authoritative")
    bindings = {"execution_id": link.execution_id, "link_evidence_kind": link.link_evidence_kind, "link_evidence_value": link.link_evidence_value}
    decision_id, timestamp = _persist_decision(AuthorityKind.LINK, link.planned_procurement_id, _provenance_binding(link.provenance), (link.link_evidence_value,), bindings)
    return replace(link, link_state=LinkState.LINK_VERIFIED, decision_id=decision_id, decision_timestamp=timestamp)


def validate_compatibility(candidate: SupplierProductCompatibility, evidence_references: tuple[str, ...]) -> CompatibilityVerificationResult:
    if candidate.compatibility_state is not CompatibilityState.COMPATIBILITY_CANDIDATE:
        raise ContractError("compatibility gate accepts candidates only")
    for name in ("compatibility_id", "planned_procurement_id", "supplier_id", "supplier_product_id", "compatibility_basis"):
        _required(getattr(candidate, name), name)
    if candidate.provenance.source_kind is not SourceKind.SUPPLIER_CATALOG:
        raise ContractError("compatibility requires supplier catalog provenance")
    decision_id, timestamp = _persist_decision(AuthorityKind.COMPATIBILITY, candidate.compatibility_id, _provenance_binding(candidate.provenance), evidence_references, {"supplier_product_id": candidate.supplier_product_id})
    return CompatibilityVerificationResult("VERIFIED", candidate.compatibility_id, _provenance_binding(candidate.provenance), evidence_references, decision_id, timestamp, candidate.supplier_product_id)


def promote_supplier_compatibility(candidate: SupplierProductCompatibility, verification: CompatibilityVerificationResult) -> SupplierProductCompatibility:
    return replace(candidate, compatibility_state=CompatibilityState.COMPATIBILITY_VERIFIED, verification=verification)


def validate_contact(candidate: RawContactCandidate, evidence_references: tuple[str, ...]) -> ContactVerificationResult:
    for name in ("contact_evidence_id", "buyer_identity_key", "contact_value", "source_locator", "observed_at"):
        _required(getattr(candidate, name), name)
    if candidate.source_kind is not SourceKind.CONTACT_SOURCE or candidate.provenance.source_kind is not SourceKind.CONTACT_SOURCE:
        raise ContractError("contact requires CONTACT_SOURCE provenance")
    decision_id, timestamp = _persist_decision(AuthorityKind.CONTACT, candidate.contact_evidence_id, _provenance_binding(candidate.provenance), evidence_references, {"buyer_identity_key": candidate.buyer_identity_key, "contact_value": candidate.contact_value})
    return ContactVerificationResult("VERIFIED", candidate.contact_evidence_id, _provenance_binding(candidate.provenance), evidence_references, decision_id, timestamp, candidate.buyer_identity_key, candidate.contact_value)


def promote_contact_evidence(candidate: RawContactCandidate, verification: ContactVerificationResult) -> ContactEvidence:
    return ContactEvidence(**{name: getattr(candidate, name) for name in RawContactCandidate.__dataclass_fields__}, verification_state=ContactState.CONTACT_VERIFIED, verification=verification)


def validate_completeness(provenance: SourceProvenance, observed_scope: str, evidence_references: tuple[str, ...]) -> CompletenessVerificationResult:
    _required(observed_scope, "observed_scope")
    if provenance.source_maturity not in {SourceMaturity.COMPLETE_COVERAGE_VERIFIED, SourceMaturity.TRUSTED_ACQUISITION}:
        raise ContractError("source maturity has not reached the completeness gate")
    decision_id, timestamp = _persist_decision(AuthorityKind.COMPLETENESS, provenance.acquisition_id, _provenance_binding(provenance), evidence_references, {"observed_scope": observed_scope})
    return CompletenessVerificationResult("VERIFIED", provenance.acquisition_id, _provenance_binding(provenance), evidence_references, decision_id, timestamp, observed_scope)


def evaluate_outreach_eligibility(planned: CurrentPlannedProcurement | None = None, compatibility: SupplierProductCompatibility | None = None, contact: ContactEvidence | None = None) -> OutreachEligibility:
    buyer = contact.buyer_identity_key if contact else (planned.id_satker if planned else "UNRESOLVED")
    procurement_id = planned.planned_procurement_id if planned else "UNRESOLVED"
    reasons: list[str] = []
    if planned is None or not is_current_rup_authorized(planned): reasons.append("CURRENT_RUP_NOT_VERIFIED")
    if compatibility is None or not is_compatibility_authorized(compatibility): reasons.append("PRODUCT_COMPATIBILITY_NOT_VERIFIED")
    if contact is None or not is_contact_authorized(contact): reasons.append("CONTACT_NOT_VERIFIED")
    if not reasons:
        return OutreachEligibility(buyer, procurement_id, compatibility.compatibility_id, contact.contact_evidence_id, EligibilityState.ELIGIBLE_FOR_REVIEW, ("EXPLICIT_APPROVAL_GATE_NOT_IMPLEMENTED",))
    return OutreachEligibility(buyer, procurement_id, compatibility.compatibility_id if compatibility else None, contact.contact_evidence_id if contact else None, EligibilityState.NOT_ELIGIBLE, tuple(reasons))
