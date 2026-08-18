"""Deterministic KLDI-to-LPSE acquisition routing authority.

This contract authorizes only which official LPSE endpoint an acquisition
caller may query.  It makes no identity, SATKER, package, or realization claim.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Iterable


NORMALIZATION_RULE_VERSION = "KLDI_LPSE_STRICT_NAME_V1"
ROUTING_AUTHORITY_SCOPE = "ROUTING_ONLY"


class KldiLpseRoutingStatus(str, Enum):
    ROUTING_ACTIVE = "ROUTING_ACTIVE"
    ROUTING_STALE = "ROUTING_STALE"
    ROUTING_AMBIGUOUS = "ROUTING_AMBIGUOUS"
    ROUTING_REJECTED = "ROUTING_REJECTED"


@dataclass(frozen=True, slots=True)
class SirupRoutingEvidence:
    canonical_kldi_id: str
    source_kldi_name: str
    acquisition_run_id: str
    receipt_chain_reference: str
    receipt_chain_hash: str
    source_version: str
    province: str = ""
    government_level: str = ""


@dataclass(frozen=True, slots=True)
class LpseRegistryEvidence:
    lpse_name: str
    official_lpse_url: str
    registry_artifact_id: str
    registry_artifact_hash: str
    registry_version: str
    province: str = ""
    government_level: str = ""


@dataclass(frozen=True, slots=True)
class KldiLpseRoutingBinding:
    status: KldiLpseRoutingStatus
    canonical_kldi_id: str
    source_kldi_name: str
    lpse_name: str
    official_lpse_url: str
    sirup_acquisition_run_id: str
    sirup_receipt_chain_reference: str
    sirup_receipt_chain_hash: str
    sirup_source_version: str
    registry_artifact_id: str
    registry_artifact_hash: str
    registry_version: str
    normalization_rule_version: str
    normalized_organization_name: str
    candidate_count: int
    province: str
    government_level: str
    authority_scope: str
    rejection_reasons: tuple[str, ...]
    binding_digest: str


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", value.strip()) if isinstance(value, str) else ""


def canonicalize_organization_name(value: str) -> str:
    """Apply only enumerated presentation/abbreviation rewrites."""
    text = _text(value)
    text = re.sub(r"^LPSE\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^Kab\.?(?=\s)", "Kabupaten", text, flags=re.IGNORECASE)
    text = re.sub(r"^Kota\.?(?=\s)", "Kota", text, flags=re.IGNORECASE)
    return " ".join(word.capitalize() for word in text.split())


def _canonical_geo(value: str) -> str:
    return " ".join(_text(value).casefold().split())


def _canonical_level(value: str) -> str:
    text = _canonical_geo(value)
    return re.sub(r"^pemerintah\s+", "", text)


def _digest_payload(binding: KldiLpseRoutingBinding) -> str:
    payload = asdict(binding)
    payload.pop("binding_digest")
    payload["status"] = binding.status.value
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_kldi_lpse_routing_binding(
    sirup: SirupRoutingEvidence,
    registry_rows: Iterable[LpseRegistryEvidence],
    *,
    normalization_rule_version: str = NORMALIZATION_RULE_VERSION,
    contradictory_evidence: bool = False,
) -> KldiLpseRoutingBinding:
    rows = tuple(registry_rows)
    normalized = canonicalize_organization_name(sirup.source_kldi_name)
    candidates = tuple(row for row in rows if canonicalize_organization_name(row.lpse_name) == normalized)
    reasons: list[str] = []

    for field in ("canonical_kldi_id", "source_kldi_name", "acquisition_run_id",
                  "receipt_chain_reference", "receipt_chain_hash", "source_version"):
        if not _text(getattr(sirup, field)):
            reasons.append(f"MISSING_SIRUP_{field.upper()}")
    if not _text(normalization_rule_version):
        reasons.append("MISSING_NORMALIZATION_RULE_VERSION")
    if contradictory_evidence:
        reasons.append("CONTRADICTORY_EVIDENCE")

    status = KldiLpseRoutingStatus.ROUTING_REJECTED
    selected = candidates[0] if len(candidates) == 1 else None
    if len(candidates) > 1:
        status = KldiLpseRoutingStatus.ROUTING_AMBIGUOUS
        reasons.append("NORMALIZED_CANDIDATE_COUNT_NOT_ONE")
    elif not candidates:
        reasons.append("NO_EXACT_NORMALIZED_CANDIDATE")

    if selected is not None:
        for field in ("lpse_name", "official_lpse_url", "registry_artifact_id",
                      "registry_artifact_hash", "registry_version"):
            if not _text(getattr(selected, field)):
                reasons.append(f"MISSING_REGISTRY_{field.upper()}")
        if sum(row.official_lpse_url == selected.official_lpse_url for row in rows) != 1:
            reasons.append("LPSE_URL_NOT_UNIQUE")
        if sirup.province and selected.province and _canonical_geo(sirup.province) != _canonical_geo(selected.province):
            reasons.append("PROVINCE_CONFLICT")
        if (sirup.government_level and selected.government_level
                and _canonical_level(sirup.government_level) != _canonical_level(selected.government_level)):
            reasons.append("GOVERNMENT_LEVEL_CONFLICT")
        if not reasons:
            status = KldiLpseRoutingStatus.ROUTING_ACTIVE

    binding = KldiLpseRoutingBinding(
        status=status,
        canonical_kldi_id=_text(sirup.canonical_kldi_id),
        source_kldi_name=_text(sirup.source_kldi_name),
        lpse_name=_text(selected.lpse_name) if selected else "",
        official_lpse_url=_text(selected.official_lpse_url) if selected else "",
        sirup_acquisition_run_id=_text(sirup.acquisition_run_id),
        sirup_receipt_chain_reference=_text(sirup.receipt_chain_reference),
        sirup_receipt_chain_hash=_text(sirup.receipt_chain_hash),
        sirup_source_version=_text(sirup.source_version),
        registry_artifact_id=_text(selected.registry_artifact_id) if selected else "",
        registry_artifact_hash=_text(selected.registry_artifact_hash) if selected else "",
        registry_version=_text(selected.registry_version) if selected else "",
        normalization_rule_version=_text(normalization_rule_version),
        normalized_organization_name=normalized,
        candidate_count=len(candidates),
        province=_text(selected.province) if selected else _text(sirup.province),
        government_level=_text(selected.government_level) if selected else _text(sirup.government_level),
        authority_scope=ROUTING_AUTHORITY_SCOPE,
        rejection_reasons=tuple(sorted(set(reasons))),
        binding_digest="",
    )
    return replace(binding, binding_digest=_digest_payload(binding))


def validate_routing_authority(
    binding: KldiLpseRoutingBinding,
    *,
    normalization_rule_version: str = NORMALIZATION_RULE_VERSION,
    sirup_source_version: str | None = None,
    registry_version: str | None = None,
) -> KldiLpseRoutingBinding:
    expected_digest = _digest_payload(replace(binding, binding_digest=""))
    changed = (
        binding.binding_digest != expected_digest
        or binding.authority_scope != ROUTING_AUTHORITY_SCOPE
        or binding.normalization_rule_version != normalization_rule_version
        or (sirup_source_version is not None and binding.sirup_source_version != sirup_source_version)
        or (registry_version is not None and binding.registry_version != registry_version)
    )
    if changed and binding.status is KldiLpseRoutingStatus.ROUTING_ACTIVE:
        stale = replace(binding, status=KldiLpseRoutingStatus.ROUTING_STALE,
                        rejection_reasons=("AUTHORITY_INPUT_CHANGED",), binding_digest="")
        return replace(stale, binding_digest=_digest_payload(stale))
    return binding


def lookup_lpse_route(binding: KldiLpseRoutingBinding) -> str | None:
    checked = validate_routing_authority(binding)
    if checked.status is not KldiLpseRoutingStatus.ROUTING_ACTIVE:
        return None
    return checked.official_lpse_url
