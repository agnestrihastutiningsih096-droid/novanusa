from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from current_procurement_contracts import (
    AcquisitionResult,
    InstitutionIdentityCandidate,
    RawCurrentRupCandidate,
    SourceAvailability,
    validate_institution_identity_provider_result,
)
from procurement_identity_resolution import (
    EvidenceRecord,
    ProcurementRecord,
    canonical_json,
    digest,
    resolve_identity,
)


class InstitutionIdentityProviderError(RuntimeError):
    pass


def _required_exact_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise InstitutionIdentityProviderError(f"{field} must be a non-empty string")
    return value


@dataclass(frozen=True, slots=True)
class CurrentInstitutionIdentityProvider:
    sirup_candidate: RawCurrentRupCandidate
    evidence_records: tuple[EvidenceRecord, ...]
    dataset_version: str

    def __init__(
        self,
        sirup_candidate: RawCurrentRupCandidate,
        evidence_records: Iterable[EvidenceRecord],
        *,
        dataset_version: str,
    ) -> None:
        if type(sirup_candidate) is not RawCurrentRupCandidate:
            raise InstitutionIdentityProviderError("canonical SiRUP candidate is required")
        records = tuple(evidence_records)
        if any(type(record) is not EvidenceRecord for record in records):
            raise InstitutionIdentityProviderError("identity evidence records are malformed")
        _required_exact_string(dataset_version, "dataset_version")
        object.__setattr__(self, "sirup_candidate", sirup_candidate)
        object.__setattr__(self, "evidence_records", records)
        object.__setattr__(self, "dataset_version", dataset_version)

    def resolve(self, id_satker: str) -> AcquisitionResult[InstitutionIdentityCandidate]:
        requested_id = _required_exact_string(id_satker, "id_satker")
        source = self.sirup_candidate
        canonical_id_satker = _required_exact_string(source.id_satker, "canonical id_satker")
        id_kldi = _required_exact_string(source.id_kldi, "canonical id_kldi")
        institution_name = _required_exact_string(
            source.institution_name, "canonical institution_name"
        )
        if requested_id != canonical_id_satker:
            raise InstitutionIdentityProviderError("requested id_satker conflicts with canonical SiRUP")

        sirup = ProcurementRecord(
            record_id=_required_exact_string(
                source.planned_procurement_id, "planned_procurement_id"
            ),
            package_name=source.package_title,
            institution=source.kldi_name,
            satker=institution_name,
            year=source.source_year,
            budget=float(source.budget) if source.budget is not None else None,
            procurement_method=source.procurement_method,
            location=source.location,
            category=source.procurement_type,
            rup_id=source.source_rup_id,
        )
        resolution = resolve_identity(
            sirup,
            self.evidence_records,
            dataset_version=self.dataset_version,
        )
        accepted = (
            resolution.identity_status == "CONFIRMED_MATCH"
            and {"INSTITUTION", "SATKER"}.issubset(resolution.match_signals)
            and resolution.selected_candidate_id is not None
        )
        candidates: tuple[InstitutionIdentityCandidate, ...] = ()
        if accepted:
            identity = {"id_kldi": id_kldi, "id_satker": canonical_id_satker}
            candidates = (InstitutionIdentityCandidate(
                buyer_identity_key=f"sirup-institution-{digest(identity)}",
                id_satker=canonical_id_satker,
                id_kldi=id_kldi,
                institution_name=institution_name,
                provenance=source.provenance,
                resolution_evidence=canonical_json(resolution.decision_evidence),
            ),)
        result = AcquisitionResult(
            candidates=candidates,
            provenance=source.provenance,
            availability=SourceAvailability.SOURCE_REACHABLE,
            no_result=not accepted,
        )
        validate_institution_identity_provider_result(result)
        return result
