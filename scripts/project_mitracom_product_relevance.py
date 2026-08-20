"""Deterministic projection of frozen Demand Taxonomy V1 families onto existing Mitracom seed product IDs.

CANDIDATE_DERIVED_SIGNAL_ONLY: a module-local derived projection, not a canonical
domain schema and not product, compatibility, procurement, or outreach authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from demand_taxonomy_v1_classifier import (
    DEMAND_FAMILIES,
    TAXONOMY_SHA256,
    classify_demand,
)

OUTPUT_SEMANTIC_STATE = "CANDIDATE_DERIVED_SIGNAL_ONLY"

# Existing Mitracom seed product IDs from apps/dashboard/src/lib/product-intelligence.ts
# (evidence_status MANUAL_SEED_V1 / PRODUCT_DATA_PENDING_INAPROC_VERIFICATION).
MITRACOM_SEED_PRODUCT_IDS = frozenset({
    "mitracom-laptop-general",
    "mitracom-printer-general",
    "mitracom-scanner-general",
    "mitracom-cctv-general",
    "mitracom-networking-general",
    "mitracom-server-general",
    "mitracom-ups-general",
    "mitracom-storage-general",
    "mitracom-camera-video-general",
    "mitracom-office-furniture-general",
})

# Frozen taxonomy family -> existing Mitracom seed product ID(s). Families
# without a matching existing seed produce no product (fail closed).
DEMAND_FAMILY_TO_MITRACOM_PRODUCT: dict[str, tuple[str, ...]] = {
    "AUDIO_CONFERENCE": ("mitracom-camera-video-general",),
    "CAMERA": ("mitracom-camera-video-general",),
    "CCTV": ("mitracom-cctv-general",),
    "COMPUTING": ("mitracom-laptop-general",),
    "NETWORKING": ("mitracom-networking-general",),
    "NETWORK_MATERIAL": ("mitracom-networking-general",),
    "OFFICE_FURNITURE": ("mitracom-office-furniture-general",),
    "POWER": ("mitracom-ups-general",),
    "PRINTING_CONSUMABLES": ("mitracom-printer-general",),
    "PRINTING_HARDWARE": ("mitracom-printer-general",),
    "SERVER": ("mitracom-server-general",),
    "STORAGE": ("mitracom-storage-general",),
    "VIDEO_CONFERENCE_HARDWARE": ("mitracom-camera-video-general",),
}


def _validate_mapping() -> None:
    frozen_families = frozenset(DEMAND_FAMILIES)
    for family, product_ids in DEMAND_FAMILY_TO_MITRACOM_PRODUCT.items():
        if family not in frozen_families:
            raise ValueError(f"mapping references a non-frozen taxonomy family: {family}")
        unknown = [product_id for product_id in product_ids if product_id not in MITRACOM_SEED_PRODUCT_IDS]
        if unknown:
            raise ValueError(f"mapping references an unknown Mitracom seed product id: {unknown}")


_validate_mapping()


@dataclass(frozen=True, slots=True)
class ProjectedProductRelevance:
    package_title: str
    procurement_type: str | None
    demand_families: tuple[str, ...]
    semantic_state: str
    matched_product_ids: tuple[str, ...]
    taxonomy_version: str
    taxonomy_sha256: str

    def __post_init__(self) -> None:
        if self.semantic_state != OUTPUT_SEMANTIC_STATE:
            raise ValueError("projection semantic state must be CANDIDATE_DERIVED_SIGNAL_ONLY")
        if self.taxonomy_sha256 != TAXONOMY_SHA256:
            raise ValueError("projection taxonomy hash is not the frozen taxonomy")


def project_product_relevance(package_title: str, procurement_type: str | None = None) -> ProjectedProductRelevance:
    """Classify the package title with frozen Demand Taxonomy V1 and project matched families
    onto existing Mitracom seed product IDs. Pure and deterministic; no I/O, no persistence,
    no verification, and no promotion of any authority."""
    classification = classify_demand(package_title, procurement_type)
    matched: list[str] = []
    seen: set[str] = set()
    for family in classification.demand_families:
        for product_id in DEMAND_FAMILY_TO_MITRACOM_PRODUCT.get(family, ()):
            if product_id not in seen:
                seen.add(product_id)
                matched.append(product_id)
    return ProjectedProductRelevance(
        package_title=package_title,
        procurement_type=procurement_type,
        demand_families=classification.demand_families,
        semantic_state=OUTPUT_SEMANTIC_STATE,
        matched_product_ids=tuple(matched),
        taxonomy_version=classification.taxonomy_version,
        taxonomy_sha256=classification.taxonomy_sha256,
    )


__all__ = [
    "DEMAND_FAMILY_TO_MITRACOM_PRODUCT",
    "MITRACOM_SEED_PRODUCT_IDS",
    "OUTPUT_SEMANTIC_STATE",
    "ProjectedProductRelevance",
    "project_product_relevance",
]
