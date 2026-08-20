"""Deterministic, NETWORK-FREE bridge from a POTENTIAL_MATCH cohort to existing
KLDI/LPSE routing authority.

POTENTIAL_MATCH_ROUTING_RESOLVED means ONLY that potential-match candidates
plus the existing routing authority resolved to an authorized acquisition
endpoint.  It is NOT procurement truth, execution verification, realization
linking, verified compatibility, actionable opportunity, or outreach
eligibility.

This module performs LOCAL ROUTING RESOLUTION ONLY.  It reuses the canonical
``build_cli_routing_binding`` path against validated SiRUP evidence and the
frozen LPSE registry artifact.  It never performs live LPSE/SPSE collection,
network access, credential access, DB writes, decision-store persistence, or
any authority/promotion call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from scripts.kldi_lpse_routing import (
    KldiLpseRoutingBinding,
    KldiLpseRoutingStatus,
)
from scripts.collect_lpse_detail_evidence import build_cli_routing_binding
from potential_match_cohort import (
    PotentialMatchCohort,
    PotentialMatchRow,
    routed_verification_prerequisites,
)

OUTPUT_SEMANTIC_STATE = "POTENTIAL_MATCH_ROUTING_RESOLVED"


class PotentialMatchRoutingError(ValueError):
    """Routing cannot be resolved without fabricating required semantics."""


@dataclass(frozen=True, slots=True)
class PotentialMatchRoutingResult:
    """One bounded routing result for one KLDI group.

    Module-local derived value type; it is NOT a new canonical schema and
    carries no verification, compatibility, opportunity, outreach, or
    realization authority.
    """

    id_kldi: str
    planned_procurement_ids: tuple[str, ...]
    matched_product_ids: tuple[str, ...]
    routing_status: str
    official_lpse_url: str
    routing_binding_digest: str
    sirup_acquisition_id: str
    registry_artifact_id: str
    registry_artifact_hash: str
    registry_version: str
    semantic_state: str = field(default=OUTPUT_SEMANTIC_STATE, init=False)
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.planned_procurement_ids:
            raise PotentialMatchRoutingError("routing result requires planned_procurement_ids")
        if not self.routing_status.strip():
            raise PotentialMatchRoutingError("routing result requires routing_status")
        # A fail-closed non-routable result may carry a blank id_kldi (a local
        # commercial candidate that cannot be routed).  Any other state must
        # have the exact canonical KLDI identifier.
        if not self.id_kldi.strip() and (
            self.routing_status != KldiLpseRoutingStatus.ROUTING_REJECTED.value
            or self.official_lpse_url
        ):
            raise PotentialMatchRoutingError("routing result requires id_kldi")


def _rows_for_group(cohort: PotentialMatchCohort, id_kldi: str) -> tuple[PotentialMatchRow, ...]:
    """Deterministic member rows for one KLDI group, in cohort order.

    If the group has inconsistent routing prerequisites the group is invalid
    and fails closed; no single candidate is silently chosen.
    """
    members = tuple(row for row in cohort.rows if row.id_kldi == id_kldi)
    if not members:
        raise PotentialMatchRoutingError(f"cohort has no rows for KLDI {id_kldi}")
    # Every member must agree on the canonical KLDI routing evidence so one
    # group resolves through exactly one routing authority lookup.
    acquisition_ids = {row.provenance.acquisition_id for row in members}
    if len(acquisition_ids) != 1:
        raise PotentialMatchRoutingError(
            f"KLDI group {id_kldi} has inconsistent routing prerequisites: {sorted(acquisition_ids)}"
        )
    return members


def _fail_closed_result(
    id_kldi: str,
    members: tuple[PotentialMatchRow, ...],
    reason: str,
) -> PotentialMatchRoutingResult:
    matched: list[str] = []
    seen: set[str] = set()
    for row in members:
        for product_id in row.matched_product_ids:
            if product_id not in seen:
                seen.add(product_id)
                matched.append(product_id)
    return PotentialMatchRoutingResult(
        id_kldi=id_kldi,
        planned_procurement_ids=tuple(row.planned_procurement_id for row in members),
        matched_product_ids=tuple(matched),
        routing_status=KldiLpseRoutingStatus.ROUTING_REJECTED.value,
        official_lpse_url="",
        routing_binding_digest="",
        sirup_acquisition_id="",
        registry_artifact_id="",
        registry_artifact_hash="",
        registry_version="",
        rejection_reasons=(reason,),
    )


def resolve_routing_for_cohort(
    cohort: PotentialMatchCohort,
    sirup_run_directory: str | Path,
) -> tuple[PotentialMatchRoutingResult, ...]:
    """Resolve each KLDI group through the canonical routing authority.

    Pure, local, deterministic: one routing lookup per KLDI group, in
    deterministic group order.  ROUTING_ACTIVE is the only state that exposes
    an LPSE endpoint; every other state fails closed as non-routable.
    """
    results: list[PotentialMatchRoutingResult] = []
    for id_kldi, members in cohort.grouped_by_kldi():
        try:
            group_rows = _rows_for_group(cohort, id_kldi)
        except PotentialMatchRoutingError as exc:
            results.append(_fail_closed_result(id_kldi, members, str(exc)))
            continue
        try:
            for row in members:
                routed_verification_prerequisites(row)
            binding = build_cli_routing_binding(id_kldi, sirup_run_directory)
        except Exception as exc:
            results.append(_fail_closed_result(id_kldi, group_rows, f"{type(exc).__name__}: {exc}"))
            continue
        result = _binding_result(binding, group_rows)
        results.append(result)
    return tuple(results)


def _binding_result(
    binding: KldiLpseRoutingBinding,
    members: tuple[PotentialMatchRow, ...],
) -> PotentialMatchRoutingResult:
    """Derive the module-local routing result from an existing routing binding.

    Only ROUTING_ACTIVE exposes the authorized LPSE URL.  All other states
    remain non-routable with an empty endpoint.
    """
    active = binding.status is KldiLpseRoutingStatus.ROUTING_ACTIVE
    matched: list[str] = []
    seen: set[str] = set()
    for row in members:
        for product_id in row.matched_product_ids:
            if product_id not in seen:
                seen.add(product_id)
                matched.append(product_id)
    return PotentialMatchRoutingResult(
        id_kldi=binding.canonical_kldi_id,
        planned_procurement_ids=tuple(row.planned_procurement_id for row in members),
        matched_product_ids=tuple(matched),
        routing_status=binding.status.value,
        official_lpse_url=binding.official_lpse_url if active else "",
        routing_binding_digest=binding.binding_digest,
        sirup_acquisition_id=binding.sirup_acquisition_run_id,
        registry_artifact_id=binding.registry_artifact_id,
        registry_artifact_hash=binding.registry_artifact_hash,
        registry_version=binding.registry_version,
        rejection_reasons=binding.rejection_reasons if not active else (),
    )


__all__ = [
    "OUTPUT_SEMANTIC_STATE",
    "PotentialMatchRoutingError",
    "PotentialMatchRoutingResult",
    "resolve_routing_for_cohort",
]
