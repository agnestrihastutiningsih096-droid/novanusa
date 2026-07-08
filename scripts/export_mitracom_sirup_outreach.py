from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT.parent / "mia-automation" / "sirup_2026.duckdb"
DEFAULT_OUTPUT = ROOT / "outputs" / "dashboard" / "mitracom_sirup_institution_outreach_may_june_2026.csv"
TEMPLATE_PATH = ROOT / "outputs" / "dashboard" / "contact_import_template_mitracom_may_june_2026.csv"

MONTH_LABELS = {
    1: "January 2026",
    2: "February 2026",
    3: "March 2026",
    4: "April 2026",
    5: "May 2026",
    6: "June 2026",
}

NATIONAL_MARKERS = (
    "kementerian",
    "badan pusat statistik",
    "arsip nasional",
    "badan gizi nasional",
    "badan karantina indonesia",
    "badan kepegawaian negara",
    "badan meteorologi",
    "badan narkotika nasional",
    "badan nasional",
    "badan pemeriksa keuangan",
    "badan pengawas obat",
    "badan pengawas pemilihan umum",
    "badan pengawasan keuangan",
    "badan pengusahaan kawasan perdagangan bebas",
    "badan riset dan inovasi nasional",
    "badan siber dan sandi negara",
    "mahkamah",
    "kejaksaan",
    "mabes",
    "tni",
    "polri",
    "dpr",
    "mpr",
    "dewan perwakilan rakyat",
    "sekretariat jenderal",
    "setjen",
    "kantor wilayah",
    "kantor pusat",
    "direktorat jenderal",
    "dirjen",
    "lembaga",
    "komisi",
    "badan otorita",
)

PROVINCE_MARKERS = ("provinsi ", "prov.", "prov ")

HOSPITAL_MARKERS = (
    "rumah sakit",
    "rsud",
    "rsu",
    "rs ",
    "rs-",
)

HEALTH_UNIT_MARKERS = (
    "puskesmas",
    "poskesdes",
    "labkesda",
    "laboratorium kesehatan",
    "balai kesehatan",
)

EDUCATION_MARKERS = (
    "dinas pendidikan",
    "sekolah",
    "madrasah",
    "universitas",
    "institut",
    "politeknik",
    "akademi",
    "kampus",
    "fakultas",
    "sma",
    "smk",
    "smp",
    "sd",
)

LOCAL_MARKERS = (
    "dinas ",
    "badan ",
    "sekretariat daerah",
    "kantor ",
    "kecamatan",
    "kelurahan",
    "kabupaten",
    "kab. ",
    "kab.",
    "kota",
    "uptd",
    "upt ",
    "blud",
    "balai ",
    "bappeda",
    "dishub",
    "diskominfo",
    "dinsos",
    "disper",
    "disdik",
    "bpbd",
    "satpol pp",
    "pemerintah daerah",
    "pemda",
)

CATEGORY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("LAPTOP", ("laptop", "notebook", "chromebook")),
    ("DESKTOP", ("desktop", "pc desktop", "personal computer", "komputer desktop", "komputer pc")),
    ("PRINTER", ("printer", "pencetak", "plotter")),
    ("SCANNER", ("scanner", "pemindai")),
    ("NETWORKING", ("jaringan komputer", "komputer jaringan", "jaringan internet", "jaringan intranet", "network", "internet", "intranet", "router", "switch", "access point", "wireless", "wifi", "firewall", "lan")),
    ("SERVER", ("server", "blade", "rackmount")),
    ("STORAGE", ("storage", "nas", "san", "harddisk", "hard disk", "ssd", "penyimpanan")),
    ("UPS", ("ups", "uninterruptible power", "stabilizer")),
    ("CCTV", ("cctv", "surveillance")),
    ("CAMERA_VIDEO", ("kamera", "camera", "video conference", "videotron", "webcam")),
    ("AUDIO", ("audio", "speaker", "microphone", "mikrofon", "sound system")),
    ("OFFICE_FURNITURE", ("meubel", "mebel", "furniture", "furnitur", "kursi", "meja", "lemari arsip")),
    ("IT_HARDWARE", ("komputer", "perangkat tik", "peralatan tik", "perangkat it", "peralatan it", "hardware", "monitor")),
]

EXCLUDE_PATTERNS = (
    "alat kesehatan",
    "alkes",
    "obat",
    "farmasi",
    "reagen",
    "bahan medis",
    "bmhp",
    "vaksin",
    "ambulance",
    "ambulans",
)


def clean(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalized(value: object) -> str:
    return clean(value).lower()


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def term_matches(text: str, term: str) -> bool:
    escaped = re.escape(term.lower())
    if " " in term:
        return term.lower() in text
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def categories_for(package_name: str) -> list[str]:
    text = normalized(package_name)
    if any(term_matches(text, term) for term in EXCLUDE_PATTERNS):
        return []

    categories: list[str] = []
    for category, terms in CATEGORY_PATTERNS:
        if any(term_matches(text, term) for term in terms):
            categories.append(category)
    return categories


def classify_target_level(institution_name: str) -> str:
    text = normalized(institution_name)

    if contains_any(text, PROVINCE_MARKERS):
        return "PROVINCE"
    if contains_any(text, NATIONAL_MARKERS):
        return "NATIONAL"
    if contains_any(text, HOSPITAL_MARKERS):
        return "HOSPITAL"
    if contains_any(text, HEALTH_UNIT_MARKERS):
        return "HEALTH_UNIT"
    if contains_any(text, EDUCATION_MARKERS):
        return "EDUCATION"
    if contains_any(text, LOCAL_MARKERS):
        return "LOCAL_AGENCY"
    return "OTHER"


def extract_province_or_region(location_hint: str) -> str:
    if not location_hint:
        return ""
    return clean(location_hint.split(",", 1)[0])


def build_display_name(work_unit: str, parent_organization: str) -> str:
    if work_unit and parent_organization and work_unit.lower() != parent_organization.lower():
        return f"{work_unit} — {parent_organization}"
    return work_unit or parent_organization


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Mitracom-relevant SiRUP 2026 outreach queue grouped by institution.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--months", type=int, nargs="+", default=[5, 6], choices=sorted(MONTH_LABELS))
    return parser.parse_args()


def fetch_rows(db_path: Path, month_labels: list[str]) -> list[dict[str, object]]:
    with duckdb.connect(str(db_path), read_only=True) as con:
        columns = {row[0] for row in con.execute("describe sirup_raw").fetchall()}
        if "pemilihan" not in columns:
            raise RuntimeError("sirup_raw.pemilihan is required for month-year filtering and was not found.")

        placeholders = ", ".join(["?"] * len(month_labels))
        sql = f"""
            select
                id,
                kldi,
                satuanKerja,
                paket,
                pagu,
                pemilihan,
                idBulan,
                jenisPengadaan,
                metode,
                lokasi,
                idSatker
            from sirup_raw
            where pemilihan in ({placeholders})
        """
        result = con.execute(sql, month_labels)
        cols = [column[0] for column in result.description]
        return [dict(zip(cols, row)) for row in result.fetchall()]


def build_export(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    examples: dict[str, list[str]] = defaultdict(list)
    categories: dict[str, set[str]] = defaultdict(set)
    months: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        package_name = clean(row.get("paket"))
        row_categories = categories_for(package_name)
        if not row_categories:
            continue

        work_unit = clean(row.get("satuanKerja"))
        parent_organization = clean(row.get("kldi"))
        location_hint = clean(row.get("lokasi"))
        province_or_region = extract_province_or_region(location_hint)
        institution_name = work_unit or parent_organization or "UNKNOWN_INSTITUTION"
        institution_display_name = build_display_name(work_unit, parent_organization) or institution_name
        target_level = classify_target_level(institution_display_name or institution_name)
        send_readiness = "READY_FOR_CONTACT_SEARCH" if target_level != "OTHER" else "NEEDS_REVIEW"
        exclusion_reason = "REVIEW_REQUIRED" if target_level == "OTHER" else "NONE"

        record = grouped.setdefault(
            institution_name,
            {
                "institution_name": institution_name,
                "institution_display_name": institution_display_name,
                "parent_organization": parent_organization,
                "work_unit": work_unit,
                "province_or_region": province_or_region,
                "location_hint": location_hint,
                "target_level": target_level,
                "send_readiness": send_readiness,
                "exclusion_reason": exclusion_reason,
                "total_relevant_packages": 0,
                "total_pagu": 0,
                "evidence_status": "SIRUP_PLANNING_ONLY",
                "spse_status": "SPSE_NOT_CHECKED_NATIONALLY",
                "contact_status": "CONTACT_MISSING",
                "outreach_status": "NOT_CONTACTED",
            },
        )

        record["total_relevant_packages"] = int(record["total_relevant_packages"]) + 1
        record["total_pagu"] = int(float(record["total_pagu"]) + float(row.get("pagu") or 0))
        categories[institution_name].update(row_categories)
        months[institution_name].add(clean(row.get("pemilihan")))

        if len(examples[institution_name]) < 5:
            package_id = clean(row.get("id"))
            label = f"{package_name} [{package_id}]" if package_id else package_name
            examples[institution_name].append(label)

    export_rows: list[dict[str, object]] = []
    for institution_name, record in grouped.items():
        record["months_found"] = "; ".join(sorted(months[institution_name]))
        record["relevant_categories"] = "; ".join(sorted(categories[institution_name]))
        record["example_package_names"] = " | ".join(examples[institution_name])
        export_rows.append(record)

    return sorted(export_rows, key=lambda item: str(item["institution_display_name"]))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_contact_template(rows: list[dict[str, object]]) -> None:
    template_rows = []
    for row in rows:
        template_rows.append(
            {
                "institution_name": row["institution_name"],
                "institution_display_name": row["institution_display_name"],
                "parent_organization": row["parent_organization"],
                "work_unit": row["work_unit"],
                "location_hint": row["location_hint"],
                "target_level": row["target_level"],
                "total_relevant_packages": row["total_relevant_packages"],
                "total_pagu": row["total_pagu"],
                "months_found": row["months_found"],
                "relevant_categories": row["relevant_categories"],
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

    write_csv(
        TEMPLATE_PATH,
        template_rows,
        [
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
        ],
    )


def main() -> None:
    args = parse_args()
    month_labels = [MONTH_LABELS[month] for month in args.months]
    rows = fetch_rows(args.db, month_labels)
    export_rows = build_export(rows)

    write_csv(
        args.output,
        export_rows,
        [
            "institution_name",
            "institution_display_name",
            "parent_organization",
            "work_unit",
            "province_or_region",
            "location_hint",
            "target_level",
            "send_readiness",
            "exclusion_reason",
            "total_relevant_packages",
            "total_pagu",
            "months_found",
            "relevant_categories",
            "example_package_names",
            "evidence_status",
            "spse_status",
            "contact_status",
            "outreach_status",
        ],
    )
    build_contact_template(export_rows)

    print(f"Wrote {len(export_rows):,} institution rows to {args.output}")
    print(f"Wrote contact template to {TEMPLATE_PATH}")
    print(f"Months: {', '.join(month_labels)}")


if __name__ == "__main__":
    main()
