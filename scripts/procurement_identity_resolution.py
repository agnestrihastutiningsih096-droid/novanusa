"""Deterministic, evidence-first procurement identity resolution.

This module is the canonical Sprint 1 identity boundary.  It deliberately
contains no procurement-status ranking or opportunity logic.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "NOVANUSA_SPRINT1_RULES_1_10"

IDENTITY_SIGNAL_REGISTRY = {
    "PACKAGE_NAME": {"class": "PRIMARY", "purpose": "Corroborate package subject and scope."},
    "INSTITUTION": {"class": "PRIMARY", "purpose": "Corroborate owning K/L/D/I."},
    "SATKER": {"class": "PRIMARY", "purpose": "Corroborate responsible work unit."},
    "YEAR": {"class": "SECONDARY", "purpose": "Corroborate fiscal period."},
    "BUDGET": {"class": "SECONDARY", "purpose": "Corroborate package value."},
    "PROCUREMENT_METHOD": {"class": "SECONDARY", "purpose": "Corroborate procurement route."},
    "LOCATION": {"class": "SECONDARY", "purpose": "Corroborate delivery/work location."},
    "CATEGORY": {"class": "SUPPORTING", "purpose": "Support package category consistency."},
    "VENDOR_HINT": {"class": "SUPPORTING", "purpose": "Support identity from a named vendor reference."},
    "OTHER_METADATA": {"class": "SUPPORTING", "purpose": "Support identity with other source metadata."},
}

CONFLICT_REGISTRY = {
    "INSTITUTION_CONFLICT": {"severity": "HARD", "purpose": "Different owning institution."},
    "SATKER_CONFLICT": {"severity": "HARD", "purpose": "Different responsible work unit."},
    "PACKAGE_IDENTITY_CONFLICT": {"severity": "HARD", "purpose": "Completely different package."},
    "MAJOR_PROCUREMENT_METHOD_CONFLICT": {"severity": "HARD", "purpose": "Incompatible procurement route."},
    "YEAR_CONFLICT": {"severity": "SOFT", "purpose": "Different fiscal year."},
    "BUDGET_DEVIATION": {"severity": "SOFT", "purpose": "Material value deviation."},
    "MINOR_PROCUREMENT_METHOD_DIFFERENCE": {"severity": "SOFT", "purpose": "Related but non-identical method."},
    "LOCATION_DIFFERENCE": {"severity": "SOFT", "purpose": "Different location metadata."},
    "CATEGORY_DIFFERENCE": {"severity": "SOFT", "purpose": "Different category metadata."},
    "METADATA_DIFFERENCE": {"severity": "SOFT", "purpose": "Other metadata differs."},
}

PRIMARY_SIGNALS = frozenset(k for k, v in IDENTITY_SIGNAL_REGISTRY.items() if v["class"] == "PRIMARY")
HARD_CONFLICTS = frozenset(k for k, v in CONFLICT_REGISTRY.items() if v["severity"] == "HARD")


def clean(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    value = re.sub(r"\s+", " ", str(value)).strip()
    return "" if value.lower() in {"nan", "none", "null"} else value


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", clean(value).lower())).strip()


def similarity(left: Any, right: Any) -> float:
    a, b = normalize(left), normalize(right)
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def budget_similarity(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return 0.0
    return max(0.0, 1.0 - abs(left - right) / max(abs(left), abs(right), 1.0))


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ProcurementRecord:
    record_id: str
    package_name: str = ""
    institution: str = ""
    satker: str = ""
    year: int | None = None
    budget: float | None = None
    procurement_method: str = ""
    location: str = ""
    category: str = ""
    vendor_hint: str = ""
    other_metadata: str = ""
    rup_id: str = ""
    package_id: str = ""


@dataclass(frozen=True)
class EvidenceRecord:
    candidate_id: str
    package_name: str = ""
    institution: str = ""
    satker: str = ""
    year: int | None = None
    budget: float | None = None
    procurement_method: str = ""
    location: str = ""
    category: str = ""
    vendor_hint: str = ""
    other_metadata: str = ""
    evidence_type: str = ""
    source_url: str = ""
    source_file: str = ""
    source_record_id: str = ""
    collected_at: str = ""
    provenance: str = ""
    source_status: str = ""

    def evidence_result(self) -> dict[str, Any]:
        source = {
            "evidence_type": self.evidence_type,
            "source_url": self.source_url,
            "source_file": self.source_file,
            "source_record_id": self.source_record_id or self.candidate_id,
            "collected_at": self.collected_at,
            "provenance": self.provenance,
        }
        return {**source, "evidence_digest": digest(source)}


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    match_signals: tuple[str, ...]
    conflicts: tuple[dict[str, str], ...]
    primary_signal_count: int
    total_signal_count: int
    identity_confidence: float
    evidence_reference: dict[str, Any]
    rejected: bool

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IdentityResult:
    identity_status: str
    identity_confidence: float
    candidate_list: tuple[dict[str, Any], ...]
    selected_candidate_id: str | None
    match_signals: tuple[str, ...]
    conflicts: tuple[dict[str, str], ...]
    applied_rules: tuple[str, ...]
    decision_explanation: str
    manual_review_required: bool
    manual_review_reason: str
    dataset_version: str
    dataset_digest: str
    decision_evidence: Mapping[str, Any]
    manual_review_record: Mapping[str, Any] | None = None


def _method_family(value: str) -> str:
    text = normalize(value)
    if any(term in text for term in ("e purchasing", "epurchasing", "katalog")):
        return "E_PURCHASING"
    if "non tender" in text or "pengadaan langsung" in text:
        return "NON_TENDER"
    if "tender" in text or "seleksi" in text:
        return "TENDER"
    return text.upper()


def _positive_signals(sirup: ProcurementRecord, evidence: EvidenceRecord) -> tuple[tuple[str, ...], dict[str, float]]:
    metrics = {
        "PACKAGE_NAME": similarity(sirup.package_name, evidence.package_name),
        "INSTITUTION": similarity(sirup.institution, evidence.institution),
        "SATKER": similarity(sirup.satker, evidence.satker),
        "BUDGET": budget_similarity(sirup.budget, evidence.budget),
        "LOCATION": similarity(sirup.location, evidence.location),
        "CATEGORY": similarity(sirup.category, evidence.category),
        "VENDOR_HINT": similarity(sirup.vendor_hint, evidence.vendor_hint),
        "OTHER_METADATA": similarity(sirup.other_metadata, evidence.other_metadata),
    }
    signals: list[str] = []
    # Thresholds define observable signals only. They never classify by score.
    for name in ("PACKAGE_NAME", "INSTITUTION", "SATKER"):
        if metrics[name] >= 0.80:
            signals.append(name)
    if sirup.year is not None and evidence.year is not None and sirup.year == evidence.year:
        signals.append("YEAR")
    if sirup.budget is not None and evidence.budget is not None and metrics["BUDGET"] >= 0.85:
        signals.append("BUDGET")
    if sirup.procurement_method and evidence.procurement_method and _method_family(sirup.procurement_method) == _method_family(evidence.procurement_method):
        signals.append("PROCUREMENT_METHOD")
    for name, left, right in (
        ("LOCATION", sirup.location, evidence.location),
        ("CATEGORY", sirup.category, evidence.category),
        ("VENDOR_HINT", sirup.vendor_hint, evidence.vendor_hint),
        ("OTHER_METADATA", sirup.other_metadata, evidence.other_metadata),
    ):
        if left and right and metrics[name] >= 0.80:
            signals.append(name)
    return tuple(sorted(signals)), metrics


def _conflicts(sirup: ProcurementRecord, evidence: EvidenceRecord, metrics: Mapping[str, float]) -> tuple[dict[str, str], ...]:
    found: list[dict[str, str]] = []

    def add(kind: str, detail: str) -> None:
        found.append({"type": kind, "severity": CONFLICT_REGISTRY[kind]["severity"], "detail": detail})

    if sirup.institution and evidence.institution and metrics["INSTITUTION"] < 0.65:
        add("INSTITUTION_CONFLICT", f"{sirup.institution!r} != {evidence.institution!r}")
    if sirup.satker and evidence.satker and metrics["SATKER"] < 0.65:
        add("SATKER_CONFLICT", f"{sirup.satker!r} != {evidence.satker!r}")
    if sirup.package_name and evidence.package_name and metrics["PACKAGE_NAME"] < 0.45:
        add("PACKAGE_IDENTITY_CONFLICT", f"{sirup.package_name!r} != {evidence.package_name!r}")
    left_method, right_method = _method_family(sirup.procurement_method), _method_family(evidence.procurement_method)
    if left_method and right_method and left_method != right_method:
        if {left_method, right_method} == {"TENDER", "NON_TENDER"} or "E_PURCHASING" in {left_method, right_method}:
            add("MAJOR_PROCUREMENT_METHOD_CONFLICT", f"{left_method} != {right_method}")
        else:
            add("MINOR_PROCUREMENT_METHOD_DIFFERENCE", f"{left_method} != {right_method}")
    if sirup.year is not None and evidence.year is not None and sirup.year != evidence.year:
        add("YEAR_CONFLICT", f"{sirup.year} != {evidence.year}")
    if sirup.budget is not None and evidence.budget is not None and metrics["BUDGET"] < 0.70:
        add("BUDGET_DEVIATION", f"{sirup.budget} != {evidence.budget}")
    if sirup.location and evidence.location and metrics["LOCATION"] < 0.50:
        add("LOCATION_DIFFERENCE", f"{sirup.location!r} != {evidence.location!r}")
    if sirup.category and evidence.category and metrics["CATEGORY"] < 0.50:
        add("CATEGORY_DIFFERENCE", f"{sirup.category!r} != {evidence.category!r}")
    if sirup.other_metadata and evidence.other_metadata and metrics["OTHER_METADATA"] < 0.50:
        add("METADATA_DIFFERENCE", "Other source metadata differs.")
    return tuple(sorted(found, key=lambda item: (item["severity"], item["type"], item["detail"])))


def evaluate_candidate(sirup: ProcurementRecord, evidence: EvidenceRecord) -> CandidateEvaluation:
    signals, metrics = _positive_signals(sirup, evidence)
    conflicts = _conflicts(sirup, evidence, metrics)
    primary_count = len(PRIMARY_SIGNALS.intersection(signals))
    # Diagnostic only: deterministic description of signal strength.
    diagnostic = round(sum(metrics.values()) / max(len(metrics), 1), 6)
    return CandidateEvaluation(
        candidate_id=clean(evidence.candidate_id),
        match_signals=signals,
        conflicts=conflicts,
        primary_signal_count=primary_count,
        total_signal_count=len(signals),
        identity_confidence=diagnostic,
        evidence_reference=evidence.evidence_result(),
        rejected=any(item["severity"] == "HARD" for item in conflicts),
    )


def _rejection_status(conflicts: Iterable[Mapping[str, str]]) -> str:
    types = {item["type"] for item in conflicts if item["severity"] == "HARD"}
    mapping = (
        ("INSTITUTION_CONFLICT", "REJECTED_INSTITUTION_CONFLICT"),
        ("SATKER_CONFLICT", "REJECTED_SATKER_CONFLICT"),
        ("PACKAGE_IDENTITY_CONFLICT", "REJECTED_PACKAGE_CONFLICT"),
        ("MAJOR_PROCUREMENT_METHOD_CONFLICT", "REJECTED_PROCUREMENT_METHOD_CONFLICT"),
    )
    hits = [status for kind, status in mapping if kind in types]
    return hits[0] if len(hits) == 1 else "REJECTED_IDENTITY_CONFLICT"


def resolve_identity(
    sirup: ProcurementRecord,
    evidence_records: Iterable[EvidenceRecord],
    *,
    dataset_version: str,
    dataset_digest: str | None = None,
) -> IdentityResult:
    evidence = sorted(
        evidence_records,
        key=lambda item: (
            clean(item.candidate_id),
            digest(
                {
                    "package_name": item.package_name,
                    "institution": item.institution,
                    "satker": item.satker,
                    "year": item.year,
                    "budget": item.budget,
                    "procurement_method": item.procurement_method,
                    "location": item.location,
                    "category": item.category,
                }
            ),
        ),
    )
    snapshot = [asdict(item) for item in evidence]
    actual_digest = dataset_digest or digest(snapshot)
    evaluations_by_id: dict[str, CandidateEvaluation] = {}
    for item in evidence:
        evaluations_by_id.setdefault(item.candidate_id, evaluate_candidate(sirup, item))
    evaluations = list(evaluations_by_id.values())
    remaining = [item for item in evaluations if not item.rejected]
    remaining.sort(key=lambda item: (-item.primary_signal_count, -item.total_signal_count, -item.identity_confidence, item.candidate_id))
    rejected = sorted((item for item in evaluations if item.rejected), key=lambda item: item.candidate_id)
    ordered = remaining + rejected

    selected: CandidateEvaluation | None = remaining[0] if remaining else None
    review_reason = ""
    if not evidence:
        decision = "NO_MATCH"
        explanation = "No local procurement evidence candidate was found."
    elif not remaining:
        all_conflicts = tuple(conflict for item in rejected for conflict in item.conflicts)
        decision = _rejection_status(all_conflicts)
        explanation = "All discovered candidates were rejected before ranking by HARD conflict."
        selected = rejected[0] if len(rejected) == 1 else None
    else:
        signals = set(selected.match_signals)
        tied = len(remaining) > 1 and (
            remaining[0].primary_signal_count,
            remaining[0].total_signal_count,
            remaining[0].identity_confidence,
        ) == (
            remaining[1].primary_signal_count,
            remaining[1].total_signal_count,
            remaining[1].identity_confidence,
        )
        if tied:
            decision, review_reason = "NEEDS_MANUAL_REVIEW", "Top candidates have identical deterministic identity rank."
        elif {"PACKAGE_NAME"}.issubset(signals) and {"INSTITUTION", "SATKER"}.intersection(signals) and len(signals) >= 3:
            decision = "CONFIRMED_MATCH"
        elif len(signals) >= 2 and PRIMARY_SIGNALS.intersection(signals):
            decision = "PROBABLE_MATCH"
        elif signals:
            decision, review_reason = "NEEDS_MANUAL_REVIEW", "Candidate evidence is insufficient for signal-based acceptance."
        else:
            decision, selected = "NO_MATCH", None
        explanation = (
            f"Decision follows registered signals after HARD-conflict rejection; "
            f"diagnostic confidence did not authorize classification."
        )

    selected_signals = selected.match_signals if selected else ()
    selected_conflicts = selected.conflicts if selected else tuple(c for item in rejected for c in item.conflicts)
    candidate_list = tuple(item.canonical() for item in ordered)
    applied = (
        "RULE_1_NAMESPACE_SEPARATION",
        "RULE_2_MULTI_SIGNAL",
        "RULE_3_HARD_CONFLICT_REJECTION",
        "RULE_4_IDENTITY_BEFORE_STATUS",
        "RULE_5_STATUS_NOT_RANKED",
        "RULE_7_CONFIDENCE_DIAGNOSTIC_ONLY",
        "RULE_8_HARD_CONFLICT_NEVER_OVERRIDDEN",
        "RULE_9_LOCKED_CONFLICT_REGISTRY",
        "RULE_10_DETERMINISTIC_REPLAY",
    )
    evidence_refs = tuple(item.evidence_reference for item in ordered)
    core = {
        "sirup_record_id": sirup.record_id,
        "decision": decision,
        "candidate_list": candidate_list,
        "selected_candidate_id": selected.candidate_id if selected else None,
        "match_signals": selected_signals,
        "conflicts": selected_conflicts,
        "applied_rules": applied,
        "decision_explanation": explanation,
        "evidence_references": evidence_refs,
        "dataset_version": dataset_version,
        "dataset_digest": actual_digest,
        "created_at": dataset_version,
    }
    decision_evidence = {"decision_id": f"identity-{digest(core)[:24]}", **core}
    manual_record = None
    if decision == "NEEDS_MANUAL_REVIEW":
        review_core = {
            "sirup_record_id": sirup.record_id,
            "candidate_list": candidate_list,
            "match_signals": selected_signals,
            "conflicts": selected_conflicts,
            "evidence_references": evidence_refs,
            "manual_review_reason": review_reason,
            "review_status": "PENDING",
            "created_at": dataset_version,
        }
        manual_record = {"review_record_id": f"review-{digest(review_core)[:24]}", **review_core}
    return IdentityResult(
        identity_status=decision,
        identity_confidence=selected.identity_confidence if selected else 0.0,
        candidate_list=candidate_list,
        selected_candidate_id=selected.candidate_id if selected else None,
        match_signals=selected_signals,
        conflicts=selected_conflicts,
        applied_rules=applied,
        decision_explanation=explanation,
        manual_review_required=decision == "NEEDS_MANUAL_REVIEW",
        manual_review_reason=review_reason,
        dataset_version=dataset_version,
        dataset_digest=actual_digest,
        decision_evidence=decision_evidence,
        manual_review_record=manual_record,
    )


def append_human_review(
    machine_decision_evidence: Mapping[str, Any],
    manual_review_record: Mapping[str, Any],
    decision: str,
    reviewer_id: str,
    reviewed_at: str,
) -> dict[str, Any]:
    if decision not in {"CONFIRM_MATCH", "REJECT_MATCH"}:
        raise ValueError("Human decision must be CONFIRM_MATCH or REJECT_MATCH")
    machine_digest = digest(machine_decision_evidence)
    review_digest = digest(manual_review_record)
    appended = {
        "human_decision": decision,
        "reviewer_id": reviewer_id,
        "reviewed_at": reviewed_at,
        "machine_decision_id": machine_decision_evidence["decision_id"],
        "machine_evidence_digest": machine_digest,
        "manual_review_record_id": manual_review_record["review_record_id"],
        "manual_review_record_digest": review_digest,
    }
    return {**appended, "review_decision_id": f"human-review-{digest(appended)[:24]}"}


def extract_procurement_status(identity: IdentityResult, evidence_records: Iterable[EvidenceRecord]) -> dict[str, Any]:
    """Status consumes canonical identity; it never resolves or ranks identity."""
    if identity.identity_status not in {"PROBABLE_MATCH", "CONFIRMED_MATCH"} or not identity.selected_candidate_id:
        return {
            "source_status": "",
            "normalized_status": "SIRUP_PLANNING_ONLY",
            "observed_at": "",
            "status_evidence": None,
            "status_evidence_digest": "",
        }
    applicable = [item for item in evidence_records if item.candidate_id == identity.selected_candidate_id and item.source_status]
    applicable.sort(key=lambda item: (item.collected_at, item.source_record_id or item.candidate_id), reverse=True)
    if not applicable:
        return {
            "source_status": "",
            "normalized_status": "SIRUP_PLANNING_ONLY",
            "observed_at": "",
            "status_evidence": None,
            "status_evidence_digest": "",
        }
    chosen = applicable[0]
    source_status = clean(chosen.source_status)
    normalized = normalize(source_status)
    status_map = [
        (("batal", "gagal"), "CANCELLED_OR_FAILED"),
        (("selesai",), "COMPLETED"),
        (("kontrak", "berkontrak"), "CONTRACTED"),
        (("pemenang",), "WINNER_SELECTED"),
        (("tender", "evaluasi", "pengumuman", "sanggah"), "IN_PROCESS"),
    ]
    result_status = "OBSERVED_OTHER"
    for terms, value in status_map:
        if any(term in normalized for term in terms):
            result_status = value
            break
    status_evidence = chosen.evidence_result()
    payload = {
        "source_status": source_status,
        "normalized_status": result_status,
        "observed_at": chosen.collected_at,
        "status_evidence": status_evidence,
    }
    return {**payload, "status_evidence_digest": digest(payload)}
