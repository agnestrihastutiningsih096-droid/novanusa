"""Deterministic POTENTIAL_MATCH cohort builder over raw current-RUP candidates.

POTENTIAL_MATCH means ONLY that the frozen Demand Taxonomy V1 projection
produced a non-empty ``matched_product_ids``.  The output is
CANDIDATE_DERIVED_SIGNAL_ONLY: it is not procurement truth, verified
compatibility, verified opportunity, actionable opportunity, outreach
eligibility, or procurement realization authority.

This module is pure and local: no network, no credentials, no DB writes,
no decision-store persistence, no routing, and no LPSE collection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from current_procurement_contracts import (
    RawCurrentRupCandidate,
    SourceProvenance,
)
from project_mitracom_product_relevance import (
    OUTPUT_SEMANTIC_STATE,
    ProjectedProductRelevance,
    project_product_relevance,
)

OUTPUT_SEMANTIC_STATE = OUTPUT_SEMANTIC_STATE


class PotentialMatchCohortError(ValueError):
    """The cohort cannot be built without fabricating required semantics."""


@dataclass(frozen=True, slots=True)
class PotentialMatchRow:
    """One deterministic POTENTIAL_MATCH row over one raw current-RUP candidate.

    Local value type only; it is not a canonical schema and carries no
    verification, compatibility, opportunity, or outreach authority.
    """

    planned_procurement_id: str
    id_kldi: str
    institution_name: str
    kldi_name: str
    package_title: str
    procurement_type: str
    source_year: int
    provenance: SourceProvenance
    matched_product_ids: tuple[str, ...]
    taxonomy_version: str
    taxonomy_sha256: str
    semantic_state: str = field(default=OUTPUT_SEMANTIC_STATE, init=False)

    def __post_init__(self) -> None:
        if not self.planned_procurement_id.strip():
            raise PotentialMatchCohortError("planned_procurement_id is required")
        if not isinstance(self.provenance, SourceProvenance):
            raise PotentialMatchCohortError("provenance must be a canonical SourceProvenance")
        if not self.matched_product_ids:
            raise PotentialMatchCohortError("POTENTIAL_MATCH requires non-empty matched_product_ids")
        if not self.taxonomy_sha256.strip():
            raise PotentialMatchCohortError("taxonomy_sha256 is required")


@dataclass(frozen=True, slots=True)
class PotentialMatchCohort:
    """Deterministic, ordered cohort of POTENTIAL_MATCH rows.

    Ordering is frozen as ``planned_procurement_id`` ascending.  Duplicate
    ``planned_procurement_id`` values fail closed because deterministic
    semantics would otherwise be ambiguous.
    """

    rows: tuple[PotentialMatchRow, ...]

    def __post_init__(self) -> None:
        seen: set[str] = set()
        previous: str | None = None
        for row in self.rows:
            if not isinstance(row, PotentialMatchRow):
                raise PotentialMatchCohortError("cohort rows must be PotentialMatchRow")
            if row.planned_procurement_id in seen:
                raise PotentialMatchCohortError(
                    f"duplicate planned_procurement_id in cohort: {row.planned_procurement_id}"
                )
            seen.add(row.planned_procurement_id)
            if previous is not None and row.planned_procurement_id < previous:
                raise PotentialMatchCohortError("cohort rows are not ordered by planned_procurement_id ascending")
            previous = row.planned_procurement_id

    def grouped_by_kldi(self) -> tuple[tuple[str, tuple[PotentialMatchRow, ...]], ...]:
        """Deterministic read-only grouping by ``id_kldi`` for later route bounding.

        Routing preparation only: performs no route lookup, registry lookup,
        network access, LPSE collection, institution verification, or
        realization linking.
        """
        groups: dict[str, list[PotentialMatchRow]] = {}
        for row in self.rows:
            groups.setdefault(row.id_kldi, []).append(row)
        return tuple(
            (kldi_id, tuple(rows))
            for kldi_id, rows in sorted(groups.items())
        )


def _id_kldi_or_blank(candidate: RawCurrentRupCandidate) -> str:
    value = getattr(candidate, "id_kldi", "")
    if value is None:
        return ""
    return str(value).strip()


def build_potential_match_cohort(
    candidates: Iterable[RawCurrentRupCandidate],
) -> PotentialMatchCohort:
    """Project every raw candidate and keep only non-empty product matches.

    Pure and deterministic: no I/O, no mutation of the input candidates,
    and no authority or persistence calls.
    """
    rows: list[PotentialMatchRow] = []
    for candidate in candidates:
        if type(candidate) is not RawCurrentRupCandidate:
            raise PotentialMatchCohortError("cohort input must be RawCurrentRupCandidate objects")
        projection = project_product_relevance(
            candidate.package_title,
            candidate.procurement_type,
        )
        if not projection.matched_product_ids:
            continue
        rows.append(PotentialMatchRow(
            planned_procurement_id=candidate.planned_procurement_id,
            id_kldi=_id_kldi_or_blank(candidate),
            institution_name=candidate.institution_name,
            kldi_name=candidate.kldi_name,
            package_title=candidate.package_title,
            procurement_type=candidate.procurement_type,
            source_year=candidate.source_year,
            provenance=candidate.provenance,
            matched_product_ids=projection.matched_product_ids,
            taxonomy_version=projection.taxonomy_version,
            taxonomy_sha256=projection.taxonomy_sha256,
        ))
    rows.sort(key=lambda row: row.planned_procurement_id)
    return PotentialMatchCohort(rows=tuple(rows))


def routed_verification_prerequisites(
    row: PotentialMatchRow,
) -> dict[str, str]:
    """Explicit routing prerequisites for one POTENTIAL_MATCH row.

    Missing or blank ``id_kldi`` fails closed: routed verification cannot
    proceed without the exact canonical KLDI identifier.  ``id_kldi`` is
    never fabricated or inferred from institution/kldi names.
    """
    if not row.id_kldi:
        raise PotentialMatchCohortError(
            f"routed verification prerequisites require id_kldi for {row.planned_procurement_id}"
        )
    acquisition_id = row.provenance.acquisition_id
    if not acquisition_id.strip():
        raise PotentialMatchCohortError(
            f"routed verification prerequisites require provenance.acquisition_id for {row.planned_procurement_id}"
        )
    return {
        "planned_procurement_id": row.planned_procurement_id,
        "id_kldi": row.id_kldi,
        "kldi_name": row.kldi_name,
        "sirup_acquisition_id": acquisition_id,
    }


__all__ = [
    "OUTPUT_SEMANTIC_STATE",
    "PotentialMatchCohort",
    "PotentialMatchCohortError",
    "PotentialMatchRow",
    "build_potential_match_cohort",
    "routed_verification_prerequisites",
]
