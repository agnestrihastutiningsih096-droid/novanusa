from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
OUTREACH_PATH = ROOT / "outputs" / "dashboard" / "mitracom_sirup_institution_outreach_may_june_2026.csv"
ENRICHED_PATH = ROOT / "outputs" / "dashboard" / "mitracom_sirup_institution_outreach_enriched.csv"

CONTACT_SOURCE_CANDIDATES = [
    ROOT.parent / "mia-automation" / "institutions_enriched_contacts.csv",
    ROOT.parent / "mia-automation" / "contact-qwen-master-clean.csv",
    ROOT.parent / "mia-automation" / "tierA_contact_enriched_v2_2026.csv",
    ROOT.parent / "mia-automation" / "tierA_contact_enriched_2026.csv",
    ROOT.parent / "mia-contact-crawler" / "contact-qwen-master-clean.csv",
    ROOT.parent / "mia-contact-crawler" / "verified_cache_contacts_1640.csv",
]

SOURCE_PRIORITY = {
    "institutions_enriched_contacts.csv": 5,
    "verified_cache_contacts_1640.csv": 4,
    "contact-qwen-master-clean.csv": 3,
    "tierA_contact_enriched_v2_2026.csv": 2,
    "tierA_contact_enriched_2026.csv": 2,
}

NATURAL_MATCH_FIELDS = {
    "institution_display_name": "exact_display_name",
    "work_unit_parent": "work_unit_parent_organization",
    "institution_region": "institution_name_region",
    "institution_name": "normalized_institution_name",
}


def clean(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize(value: object) -> str:
    text = clean(value).lower()
    text = re.sub(r"[\u2013\u2014\-_/\\|(),.;:]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def key_pair(left: str, right: str) -> str:
    left_norm = normalize(left)
    right_norm = normalize(right)
    if not left_norm or not right_norm:
        return ""
    return f"{left_norm} || {right_norm}"


def build_display_name(work_unit: str, parent_organization: str) -> str:
    work_unit = clean(work_unit)
    parent_organization = clean(parent_organization)
    if work_unit and parent_organization and normalize(work_unit) != normalize(parent_organization):
        return f"{work_unit} — {parent_organization}"
    return work_unit or parent_organization


def parse_numeric_score(value: object, default: float = 0.0) -> float:
    text = clean(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        pass
    lowered = text.lower()
    if lowered in {"high", "strong", "verified_high", "likely_correct"}:
        return 0.9
    if lowered in {"medium", "moderate", "verified_medium", "needs_review"}:
        return 0.7
    if lowered in {"low", "weak", "verified_low"}:
        return 0.5
    if lowered in {"official", "official site", "official_website"}:
        return 0.8
    return default


@dataclass
class CanonicalContact:
    source_file: str
    source_type: str
    source_priority: int
    source_confidence: float
    source_row: int
    institution_name: str
    parent_organization: str
    work_unit: str
    region: str
    institution_display_name: str
    contact_email: str
    official_website: str
    contact_phone: str
    contact_whatsapp: str
    contact_person: str
    contact_role: str
    contact_source_url: str
    contact_notes: str
    contact_source_type: str
    match_keys: dict[str, str]
    completeness_score: float


def best_nonempty(*values: str) -> str:
    for value in values:
        value = clean(value)
        if value:
            return value
    return ""


def choose_contact_source_type(source_name: str) -> str:
    if source_name == "institutions_enriched_contacts.csv":
        return "institution_enriched"
    if source_name == "verified_cache_contacts_1640.csv":
        return "verified_cache"
    if source_name.startswith("tierA_contact_enriched"):
        return "tierA_enriched"
    if source_name == "contact-qwen-master-clean.csv":
        return "master_crawler"
    return "contact_master"


def source_rank(source_name: str) -> int:
    return SOURCE_PRIORITY.get(source_name, 1)


def canonicalize_row(source_path: Path, row: dict[str, str], row_number: int) -> CanonicalContact:
    source_name = source_path.name
    source_type = choose_contact_source_type(source_name)

    institution_name = ""
    parent_organization = ""
    work_unit = ""
    region = ""
    official_website = ""
    contact_email = ""
    contact_phone = ""
    contact_whatsapp = ""
    contact_person = ""
    contact_role = ""
    contact_source_url = ""
    contact_notes = ""
    source_confidence = 0.0

    if source_name == "institutions_enriched_contacts.csv":
        institution_name = best_nonempty(row.get("name"))
        parent_organization = ""
        work_unit = institution_name
        official_website = best_nonempty(row.get("source_url"))
        contact_email = best_nonempty(row.get("email"))
        contact_phone = best_nonempty(row.get("current_phone"), row.get("manual_phone"))
        contact_whatsapp = best_nonempty(row.get("current_whatsapp"), row.get("manual_whatsapp"))
        contact_person = best_nonempty(row.get("contact_person"))
        contact_role = best_nonempty(row.get("position"))
        contact_source_url = best_nonempty(row.get("source_url"))
        contact_notes = best_nonempty(row.get("notes"))
        source_confidence = parse_numeric_score(row.get("match_confidence"))
    elif source_name.startswith("tierA_contact_enriched"):
        institution_name = best_nonempty(row.get("institution_name"))
        parent_organization = best_nonempty(row.get("kldi"))
        work_unit = institution_name
        region = best_nonempty(row.get("province"))
        official_website = best_nonempty(row.get("official_website"), row.get("source_url"))
        contact_email = best_nonempty(
            row.get("research_email"),
            row.get("official_email"),
            row.get("procurement_unit_email"),
            row.get("ppid_email"),
        )
        contact_phone = best_nonempty(
            row.get("research_phone"),
            row.get("official_phone"),
            row.get("procurement_unit_phone"),
            row.get("ppid_phone"),
        )
        contact_whatsapp = best_nonempty(row.get("research_whatsapp"), row.get("official_whatsapp"))
        contact_person = best_nonempty(row.get("research_contact_person"))
        contact_role = best_nonempty(row.get("research_position"))
        contact_source_url = best_nonempty(row.get("research_source_url"), row.get("source_url"))
        contact_notes = best_nonempty(row.get("research_notes"), row.get("evidence_notes"))
        source_confidence = parse_numeric_score(row.get("contact_confidence"))
        if source_confidence == 0:
            source_confidence = parse_numeric_score(row.get("priority_score")) / 100.0
    elif source_name == "verified_cache_contacts_1640.csv":
        institution_name = best_nonempty(row.get("institution_name"), row.get("cache_institution"))
        parent_organization = best_nonempty(row.get("cache_kldi"))
        work_unit = institution_name
        region = best_nonempty(row.get("cache_kldi"), row.get("institution_type"))
        official_website = best_nonempty(row.get("official_website"), row.get("website"))
        contact_email = best_nonempty(row.get("official_email"), row.get("procurement_email"))
        contact_phone = best_nonempty(row.get("phone"))
        contact_whatsapp = best_nonempty(row.get("whatsapp"))
        contact_person = best_nonempty(row.get("pic_name"))
        contact_role = best_nonempty(row.get("pic_title"))
        contact_source_url = best_nonempty(row.get("source_url"))
        contact_notes = best_nonempty(row.get("notes"), row.get("audit_status"))
        source_confidence = parse_numeric_score(row.get("confidence_score"))
    else:
        institution_name = best_nonempty(row.get("institution"), row.get("name"), row.get("institution_name"))
        parent_organization = best_nonempty(row.get("kldi"))
        work_unit = institution_name
        official_website = best_nonempty(row.get("website"), row.get("official_website"), row.get("source_url"))
        contact_email = best_nonempty(row.get("email"), row.get("official_email"), row.get("procurement_email"))
        contact_phone = best_nonempty(row.get("phone"), row.get("official_phone"), row.get("procurement_unit_phone"))
        contact_whatsapp = best_nonempty(row.get("whatsapp"), row.get("official_whatsapp"))
        contact_person = best_nonempty(row.get("pic_name"), row.get("contact_person"))
        contact_role = best_nonempty(row.get("pic_position"), row.get("pic_title"), row.get("position"), row.get("department"))
        contact_source_url = best_nonempty(row.get("source_url"))
        contact_notes = best_nonempty(row.get("notes"), row.get("email_type"), row.get("phone_type"))
        source_confidence = parse_numeric_score(row.get("confidence_score"))

    institution_display_name = build_display_name(work_unit, parent_organization)
    if not region:
        region = best_nonempty(row.get("province"), row.get("region"))

    keys = {
        "institution_display_name": normalize(institution_display_name),
        "work_unit_parent": key_pair(work_unit, parent_organization),
        "institution_region": key_pair(institution_name, region),
        "institution_name": normalize(institution_name),
    }

    completeness_score = 0.0
    completeness_score += 4.0 if official_website else 0.0
    completeness_score += 4.0 if contact_email else 0.0
    completeness_score += 2.0 if contact_phone else 0.0
    completeness_score += 1.0 if contact_whatsapp else 0.0
    completeness_score += 1.0 if contact_person else 0.0
    completeness_score += 1.0 if contact_role else 0.0
    completeness_score += 1.0 if contact_source_url else 0.0
    completeness_score += 1.0 if contact_notes else 0.0
    completeness_score += source_confidence

    return CanonicalContact(
        source_file=source_name,
        source_type=source_type,
        source_priority=source_rank(source_name),
        source_confidence=source_confidence,
        source_row=row_number,
        institution_name=institution_name,
        parent_organization=parent_organization,
        work_unit=work_unit,
        region=region,
        institution_display_name=institution_display_name,
        contact_email=contact_email,
        official_website=official_website,
        contact_phone=contact_phone,
        contact_whatsapp=contact_whatsapp,
        contact_person=contact_person,
        contact_role=contact_role,
        contact_source_url=contact_source_url,
        contact_notes=contact_notes,
        contact_source_type=source_type,
        match_keys=keys,
        completeness_score=completeness_score,
    )


def load_contact_rows(source_path: Path) -> list[CanonicalContact]:
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [canonicalize_row(source_path, row, index + 1) for index, row in enumerate(reader)]


def better_candidate(left: CanonicalContact, right: CanonicalContact) -> CanonicalContact:
    left_key = (
        left.completeness_score,
        left.source_confidence,
        left.source_priority,
        -left.source_row,
    )
    right_key = (
        right.completeness_score,
        right.source_confidence,
        right.source_priority,
        -right.source_row,
    )
    return left if left_key >= right_key else right


def build_index(candidates: Iterable[CanonicalContact]) -> dict[str, CanonicalContact]:
    index: dict[str, CanonicalContact] = {}
    for candidate in candidates:
        for key in candidate.match_keys.values():
            if not key:
                continue
            existing = index.get(key)
            if existing is None:
                index[key] = candidate
            else:
                index[key] = better_candidate(existing, candidate)
    return index


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def enrich_outreach_row(row: dict[str, str], index: dict[str, CanonicalContact]) -> tuple[dict[str, str], str, str]:
    institution_name = clean(row.get("institution_name"))
    institution_display_name = clean(row.get("institution_display_name"))
    parent_organization = clean(row.get("parent_organization"))
    work_unit = clean(row.get("work_unit"))
    region_hint = clean(row.get("province_or_region")) or clean(row.get("location_hint"))

    keys = [
        ("exact_display_name", normalize(institution_display_name)),
        ("work_unit_parent_organization", key_pair(work_unit, parent_organization)),
        ("institution_name_region", key_pair(institution_name, region_hint)),
        ("normalized_institution_name", normalize(institution_name)),
    ]

    matched: CanonicalContact | None = None
    match_type = "unmatched"
    match_key = ""
    for candidate_match_type, key in keys:
        if not key:
            continue
        candidate = index.get(key)
        if candidate is not None:
            matched = candidate
            match_type = candidate_match_type
            match_key = key
            break

    enriched = dict(row)
    if matched is None:
        enriched.update(
            {
                "contact_match_type": "unmatched",
                "contact_match_key": "",
                "contact_match_source_file": "",
                "contact_match_source_type": "",
                "contact_master_institution_name": "",
                "contact_master_display_name": "",
                "contact_master_parent_organization": "",
                "contact_master_work_unit": "",
                "contact_master_region": "",
                "contact_email": "",
                "official_website": "",
                "contact_phone": "",
                "contact_whatsapp": "",
                "contact_person": "",
                "contact_role": "",
                "contact_source_url": "",
                "contact_source_type": "",
                "contact_notes": "",
                "contact_status": "CONTACT_MISSING",
            }
        )
        return enriched, "", ""

    contact_status = "CONTACT_MISSING"
    if matched.contact_email and matched.contact_source_url:
        contact_status = "CONTACT_FOUND"
    elif matched.contact_email and not matched.contact_source_url:
        contact_status = "CONTACT_NEEDS_REVIEW"

    enriched.update(
        {
            "contact_match_type": match_type,
            "contact_match_key": match_key,
            "contact_match_source_file": matched.source_file,
            "contact_match_source_type": matched.source_type,
            "contact_master_institution_name": matched.institution_name,
            "contact_master_display_name": matched.institution_display_name,
            "contact_master_parent_organization": matched.parent_organization,
            "contact_master_work_unit": matched.work_unit,
            "contact_master_region": matched.region,
            "contact_email": matched.contact_email,
            "official_website": matched.official_website,
            "contact_phone": matched.contact_phone,
            "contact_whatsapp": matched.contact_whatsapp,
            "contact_person": matched.contact_person,
            "contact_role": matched.contact_role,
            "contact_source_url": matched.contact_source_url,
            "contact_source_type": matched.contact_source_type,
            "contact_notes": matched.contact_notes,
            "contact_status": contact_status,
        }
    )
    return enriched, match_type, matched.source_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Join the contact master datasets into the Mitracom SiRUP outreach queue.")
    parser.add_argument("--outreach", type=Path, default=OUTREACH_PATH)
    parser.add_argument("--output", type=Path, default=ENRICHED_PATH)
    args = parser.parse_args()

    available_sources = [path for path in CONTACT_SOURCE_CANDIDATES if path.exists()]
    if not available_sources:
        raise FileNotFoundError("No contact master datasets were found in the known candidate locations.")

    all_contacts: list[CanonicalContact] = []
    for source_path in available_sources:
        all_contacts.extend(load_contact_rows(source_path))

    index = build_index(all_contacts)
    outreach_rows = load_rows(args.outreach)

    enriched_rows: list[dict[str, str]] = []
    matched_count = 0
    exact_count = 0
    fuzzy_count = 0

    for row in outreach_rows:
        enriched, match_type, _ = enrich_outreach_row(row, index)
        enriched_rows.append(enriched)
        if match_type and match_type != "unmatched":
            matched_count += 1
            if match_type in {"exact_display_name", "work_unit_parent_organization"}:
                exact_count += 1
            else:
                fuzzy_count += 1

    output_fields = list(outreach_rows[0].keys()) if outreach_rows else []
    output_fields.extend(
        [
            "contact_match_type",
            "contact_match_key",
            "contact_match_source_file",
            "contact_match_source_type",
            "contact_master_institution_name",
            "contact_master_display_name",
            "contact_master_parent_organization",
            "contact_master_work_unit",
            "contact_master_region",
            "contact_email",
            "official_website",
            "contact_phone",
            "contact_whatsapp",
            "contact_person",
            "contact_role",
            "contact_source_url",
            "contact_source_type",
            "contact_notes",
        ]
    )

    write_rows(args.output, enriched_rows, output_fields)

    unmatched = len(outreach_rows) - matched_count
    print(f"Wrote {len(enriched_rows):,} enriched outreach rows to {args.output}")
    print(f"Total contacts matched: {matched_count}")
    print(f"Exact matches: {exact_count}")
    print(f"Fuzzy matches: {fuzzy_count}")
    print(f"Unmatched institutions: {unmatched}")
    print("Columns imported: contact_match_type, contact_match_key, contact_match_source_file, contact_match_source_type, contact_master_institution_name, contact_master_display_name, contact_master_parent_organization, contact_master_work_unit, contact_master_region, contact_email, official_website, contact_phone, contact_whatsapp, contact_person, contact_role, contact_source_url, contact_source_type, contact_notes")
    print("Contact master datasets used:")
    for source_path in available_sources:
        print(f"- {source_path}")


if __name__ == "__main__":
    main()
