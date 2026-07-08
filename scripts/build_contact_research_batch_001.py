from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENRICHED_INPUT = ROOT / "outputs" / "dashboard" / "mitracom_sirup_institution_outreach_enriched.csv"
TEMPLATE_INPUT = ROOT / "outputs" / "dashboard" / "contact_import_template_mitracom_may_june_2026.csv"
OUTPUT = ROOT / "outputs" / "dashboard" / "contact_research_batch_001_mitracom_ready.csv"

PRIORITY_CATEGORIES = {
    "LAPTOP",
    "DESKTOP",
    "PRINTER",
    "SCANNER",
    "NETWORKING",
    "SERVER",
    "STORAGE",
    "UPS",
    "CCTV",
    "CAMERA_VIDEO",
}

PREFERRED_TARGET_LEVELS = ["LOCAL_AGENCY", "HOSPITAL", "EDUCATION", "HEALTH_UNIT"]
FALLBACK_TARGET_LEVELS = ["OTHER", "NATIONAL", "PROVINCE", "REVIEW"]


def has_priority_category(value: str) -> bool:
    categories = {part.strip() for part in value.split(";") if part.strip()}
    return any(category in categories for category in PRIORITY_CATEGORIES)


def target_level_rank(value: str) -> int:
    if value in PREFERRED_TARGET_LEVELS:
        return PREFERRED_TARGET_LEVELS.index(value)
    if value in FALLBACK_TARGET_LEVELS:
        return len(PREFERRED_TARGET_LEVELS) + FALLBACK_TARGET_LEVELS.index(value)
    return len(PREFERRED_TARGET_LEVELS) + len(FALLBACK_TARGET_LEVELS)


def resolve_input_path() -> Path:
    return ENRICHED_INPUT if ENRICHED_INPUT.exists() else TEMPLATE_INPUT


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "institution_name",
        "institution_display_name",
        "parent_organization",
        "work_unit",
        "location_hint",
        "target_level",
        "total_relevant_packages",
        "total_pagu",
        "months_found",
        "relevant_categories",
        "official_website",
        "contact_email",
        "contact_phone",
        "contact_person",
        "contact_role",
        "contact_source_url",
        "contact_source_type",
        "contact_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    input_path = resolve_input_path()
    rows = load_rows(input_path)

    selected = [row for row in rows if row.get("target_level") != "REVIEW" and has_priority_category(row.get("relevant_categories", ""))]
    if len(selected) < 100:
        selected = [row for row in rows if has_priority_category(row.get("relevant_categories", ""))]

    selected.sort(
        key=lambda row: (
            target_level_rank(row.get("target_level", "")),
            -int(row.get("total_relevant_packages") or 0),
            -int(row.get("total_pagu") or 0),
            row.get("institution_display_name", "") or row.get("institution_name", ""),
        )
    )
    selected = selected[:100]

    batch_rows: list[dict[str, str]] = []
    for row in selected:
        batch_rows.append(
            {
                "institution_name": row.get("institution_name", ""),
                "institution_display_name": row.get("institution_display_name", "") or row.get("institution_name", ""),
                "parent_organization": row.get("parent_organization", ""),
                "work_unit": row.get("work_unit", ""),
                "location_hint": row.get("location_hint", ""),
                "target_level": row.get("target_level", ""),
                "total_relevant_packages": row.get("total_relevant_packages", ""),
                "total_pagu": row.get("total_pagu", ""),
                "months_found": row.get("months_found", ""),
                "relevant_categories": row.get("relevant_categories", ""),
                "official_website": "",
                "contact_email": "",
                "contact_phone": "",
                "contact_person": "",
                "contact_role": "",
                "contact_source_url": "",
                "contact_source_type": "",
                "contact_notes": "",
            }
        )

    write_rows(OUTPUT, batch_rows)
    print(f"Input source: {input_path}")
    print(f"Wrote {len(batch_rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
