from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
MIA_AUTOMATION = ROOT.parent / "mia-automation"
MIA_CONTACT_CRAWLER = ROOT.parent / "mia-contact-crawler"
OUTPUT_PATH = ROOT / "outputs" / "alkes_sirup_leads.xlsx"
MAX_EXPORT_ROWS = 25000
SOURCE_YEAR = 2026

SIRUP_DUCKDB_CANDIDATES = [
    MIA_AUTOMATION / "sirup_2026.duckdb",
]

CONTACT_FILE_CANDIDATES = [
    MIA_AUTOMATION / "institutions_enriched_contacts.csv",
    MIA_AUTOMATION / "contact-qwen-master-clean.csv",
    MIA_AUTOMATION / "tierA_contact_enriched_v2_2026.csv",
    MIA_AUTOMATION / "tierA_contact_enriched_2026.csv",
    MIA_CONTACT_CRAWLER / "contact-qwen-master-clean.csv",
    MIA_CONTACT_CRAWLER / "verified_cache_contacts_1640.csv",
]

KEYWORDS = [
    "alat kesehatan",
    "alkes",
    "kesehatan",
    "rumah sakit",
    "rsud",
    "puskesmas",
    "klinik",
    "laboratorium",
    "lab",
    "medis",
    "medical",
    "hospital",
    "health",
    "diagnostic",
    "diagnostik",
    "patient monitor",
    "monitor pasien",
    "ventilator",
    "oxygen",
    "oksigen",
    "oximeter",
    "tensimeter",
    "sphygmomanometer",
    "stethoscope",
    "stetoskop",
    "infusion",
    "infus",
    "syringe pump",
    "suction",
    "usg",
    "ultrasound",
    "x-ray",
    "rontgen",
    "radiologi",
    "ct scan",
    "dental",
    "gigi",
    "bed pasien",
    "tempat tidur pasien",
    "kursi roda",
    "ambulance",
    "ambulan",
    "autoclave",
    "sterilizer",
    "alat bedah",
    "operasi",
    "ICU",
    "NICU",
    "IGD",
    "UGD",
    "emergency",
    "farmasi",
    "bmhp",
    "hematology analyzer",
    "chemistry analyzer",
    "cathlab",
    "electrocauter",
    "defibrillator",
    "nebulizer",
    "ekg",
    "ecg",
    "endoscopy",
    "endoskopi",
]

EQUIPMENT_KEYWORDS = [
    "alat kesehatan",
    "alkes",
    "peralatan kesehatan",
    "alat medis",
    "bmhp",
    "bahan medis",
    "medical equipment",
    "diagnostic",
    "diagnostik",
    "patient monitor",
    "monitor pasien",
    "ventilator",
    "oxygen",
    "oksigen",
    "oximeter",
    "tensimeter",
    "sphygmomanometer",
    "stethoscope",
    "stetoskop",
    "infusion",
    "infus",
    "syringe pump",
    "suction",
    "usg",
    "ultrasound",
    "x-ray",
    "rontgen",
    "radiologi",
    "ct scan",
    "dental",
    "gigi",
    "bed pasien",
    "tempat tidur pasien",
    "kursi roda",
    "ambulance",
    "ambulan",
    "autoclave",
    "sterilizer",
    "alat bedah",
    "operasi",
    "icu",
    "nicu",
    "igd",
    "ugd",
    "emergency",
    "farmasi",
    "laboratorium",
    "lab",
    "hematology analyzer",
    "chemistry analyzer",
    "cathlab",
    "electrocauter",
    "meja instrumen",
    "incubator",
    "defibrillator",
    "nebulizer",
    "ekg",
    "ecg",
    "endoscopy",
    "endoskopi",
]

HEALTH_CONTEXT_KEYWORDS = [
    "kesehatan",
    "rumah sakit",
    "rsud",
    "puskesmas",
    "klinik",
    "hospital",
    "health",
    "medis",
    "farmasi",
    "laboratorium",
    "lab",
]

EXCLUDE_KEYWORDS = [
    "jurnal",
    "surat kabar",
    "majalah",
    "jaminan kesehatan",
    "iuran",
    "konstruksi",
    "gedung",
    "bangunan",
    "pemeliharaan gedung",
    "perjalanan dinas",
    "honor",
    "gaji",
    "makan minum",
    "langganan",
    "listrik",
    "air",
    "internet",
    "cleaning service",
    "keamanan",
    "parkir",
    "sewa gedung",
]

LEADS_COLUMNS = [
    "institution_name",
    "region_or_daerah",
    "province",
    "city_or_regency",
    "sector",
    "institution_type",
    "address",
    "phone",
    "whatsapp",
    "email",
    "website",
    "pic_name",
    "pic_role",
    "package_name",
    "needed_equipment",
    "equipment_category",
    "procurement_description",
    "budget_value",
    "budget_value_idr",
    "procurement_method",
    "source_year",
    "source_system",
    "source_url_or_reference",
    "opportunity_priority",
    "contact_readiness",
    "data_confidence",
    "notes",
    "kldi",
    "satker",
    "work_unit",
    "rup_id",
    "package_id",
    "procurement_status",
    "schedule_or_period",
    "fiscal_year",
    "raw_keywords_matched",
    "recommended_next_action",
]


def normalize(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(kabupaten|kab|kota|provinsi|prov)\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def find_existing(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def pattern_from_keywords(keywords: list[str]) -> str:
    parts = []
    for kw in keywords:
        escaped = re.escape(kw.lower())
        if kw.lower() in {"lab", "icu", "nicu", "igd", "ugd"}:
            parts.append(rf"\b{escaped}\b")
        else:
            parts.append(escaped)
    return "|".join(parts)


def parse_location(location: Any) -> tuple[str, str]:
    text = clean_value(location)
    if not text:
        return "", ""
    parts = [part.strip() for part in text.split(",") if part.strip()]
    province = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""
    return province, city


def classify_sector(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["kesehatan", "rumah sakit", "rsud", "puskesmas", "klinik", "farmasi", "medical", "hospital", "health"]):
        return "Healthcare"
    if any(token in lowered for token in ["pendidikan", "universitas", "sekolah"]):
        return "Education"
    if any(token in lowered for token in ["pertahanan", "tni", "polri"]):
        return "Defense / Public Safety"
    return "Public Sector"


def classify_institution_type(text: str) -> str:
    lowered = text.lower()
    if "rumah sakit" in lowered or "rsud" in lowered or "hospital" in lowered:
        return "Hospital"
    if "puskesmas" in lowered:
        return "Primary Care / Puskesmas"
    if "dinas kesehatan" in lowered:
        return "Health Agency"
    if "klinik" in lowered:
        return "Clinic"
    if "kementerian kesehatan" in lowered:
        return "Central Health Ministry"
    if "farmasi" in lowered:
        return "Pharmacy / Health Supply Unit"
    return "Public Institution"


def matched_keywords(text: str) -> list[str]:
    lowered = text.lower()
    matches = []
    for keyword in KEYWORDS:
        kw = keyword.lower()
        if kw in {"lab", "icu", "nicu", "igd", "ugd"}:
            if re.search(rf"\b{re.escape(kw)}\b", lowered):
                matches.append(keyword)
        elif kw in lowered:
            matches.append(keyword)
    return sorted(set(matches), key=str.lower)


def classify_equipment(text: str, matches: list[str]) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["hematology", "chemistry analyzer", "diagnostic", "diagnostik", "laboratorium", " lab", "x-ray", "rontgen", "radiologi", "ct scan", "usg", "ultrasound", "cathlab", "ekg", "ecg"]):
        return "Diagnostic / Laboratory Equipment"
    if any(token in lowered for token in ["patient monitor", "monitor pasien", "ventilator", "infusion", "infus", "syringe pump", "suction", "icu", "nicu", "bed pasien", "tempat tidur", "troli emergency", "nebulizer", "defibrillator"]):
        return "Patient Care / Monitoring Equipment"
    if any(token in lowered for token in ["dental", "gigi"]):
        return "Dental Equipment"
    if any(token in lowered for token in ["ambulance", "ambulan", "emergency", "igd", "ugd"]):
        return "Emergency / Ambulance Equipment"
    if any(token in lowered for token in ["autoclave", "sterilizer", "sterilisasi"]):
        return "Sterilization Equipment"
    if any(token in lowered for token in ["obat", "farmasi", "vaksin"]):
        return "Pharmacy / Medical Consumables"
    if any(token in lowered for token in ["alat kesehatan", "alkes", "peralatan kesehatan", "alat medis", "bmhp", "bahan medis"]):
        return "Medical Devices / Consumables"
    if any(token.lower() in {m.lower() for m in matches} for token in HEALTH_CONTEXT_KEYWORDS):
        return "Healthcare Equipment / Supplies"
    return "Healthcare Procurement"


def contact_readiness(email: str, phone: str, whatsapp: str) -> str:
    if email and (phone or whatsapp):
        return "Email + phone/WhatsApp available"
    if email:
        return "Email available"
    if phone or whatsapp:
        return "Phone/WhatsApp available"
    return "Missing direct contact"


def priority_for(budget: float, category: str, readiness: str) -> str:
    has_contact = readiness != "Missing direct contact"
    if budget >= 1_000_000_000 and (has_contact or category != "Healthcare Procurement"):
        return "High"
    if budget >= 250_000_000:
        return "High" if has_contact else "Medium"
    if budget >= 50_000_000 or has_contact:
        return "Medium"
    return "Low"


def confidence_for(matches: list[str], readiness: str) -> str:
    strong = {m.lower() for m in matches}.intersection({kw.lower() for kw in EQUIPMENT_KEYWORDS})
    if strong and readiness != "Missing direct contact":
        return "High"
    if strong:
        return "Medium"
    return "Low"


def normalize_contact_frame(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as exc:
        print(f"Skipping contact file {path}: {exc}")
        return pd.DataFrame()

    def first_existing(names: list[str]) -> str | None:
        lowered = {col.lower(): col for col in df.columns}
        for name in names:
            if name.lower() in lowered:
                return lowered[name.lower()]
        return None

    mapping = {
        "institution_name": first_existing(["institution_name", "institution", "name", "contact_institution_name", "cache_institution"]),
        "kldi": first_existing(["kldi", "cache_kldi"]),
        "website": first_existing(["website", "official_website", "source_url"]),
        "email": first_existing(["email", "official_email", "procurement_email"]),
        "phone": first_existing(["phone", "current_phone", "manual_phone"]),
        "whatsapp": first_existing(["whatsapp", "current_whatsapp", "manual_whatsapp"]),
        "pic_name": first_existing(["pic_name", "contact_person"]),
        "pic_role": first_existing(["pic_role", "pic_position", "pic_title", "position"]),
        "address": first_existing(["address", "alamat"]),
        "source_url": first_existing(["source_url", "website", "official_website"]),
        "confidence": first_existing(["confidence_score", "match_confidence", "verified_level"]),
    }

    if not mapping["institution_name"]:
        return pd.DataFrame()

    out = pd.DataFrame()
    for target, source in mapping.items():
        out[target] = df[source] if source else ""
    out["source_file"] = str(path)
    out = out.fillna("")
    out["_score"] = out.apply(score_contact_row, axis=1)
    return out


def score_contact_row(row: pd.Series) -> float:
    score = 0.0
    for field in ["email", "phone", "whatsapp", "website", "pic_name"]:
        if clean_value(row.get(field)):
            score += 1.0
    try:
        confidence = float(row.get("confidence") or 0)
        score += confidence
    except Exception:
        pass
    return score


def build_contact_index(paths: list[Path]) -> tuple[dict[str, dict[str, str]], list[str]]:
    frames = [normalize_contact_frame(path) for path in paths]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return {}, []
    contacts = pd.concat(frames, ignore_index=True).fillna("")
    contacts = contacts.sort_values("_score", ascending=False)
    index: dict[str, dict[str, str]] = {}
    for _, row in contacts.iterrows():
        inst = clean_value(row.get("institution_name"))
        kldi = clean_value(row.get("kldi"))
        keys = {
            normalize(inst),
            normalize(f"{inst} {kldi}"),
            f"{normalize(inst)}|{normalize(kldi)}" if kldi else "",
        }
        contact = {field: clean_value(row.get(field)) for field in ["website", "email", "phone", "whatsapp", "pic_name", "pic_role", "address", "source_url", "source_file"]}
        for key in keys:
            if key and key not in index:
                index[key] = contact
    return index, [str(path) for path in paths]


def lookup_contact(index: dict[str, dict[str, str]], satker: str, kldi: str) -> dict[str, str]:
    keys = [
        f"{normalize(satker)}|{normalize(kldi)}",
        normalize(f"{satker} {kldi}"),
        normalize(satker),
    ]
    for key in keys:
        if key in index:
            return index[key]
    return {field: "" for field in ["website", "email", "phone", "whatsapp", "pic_name", "pic_role", "address", "source_url", "source_file"]}


def load_sirup_rows(db_path: Path) -> tuple[pd.DataFrame, int]:
    equipment_pattern = pattern_from_keywords(EQUIPMENT_KEYWORDS)
    health_pattern = pattern_from_keywords(HEALTH_CONTEXT_KEYWORDS)
    exclude_pattern = pattern_from_keywords(EXCLUDE_KEYWORDS)

    con = duckdb.connect(str(db_path), read_only=True)
    text_expr = "lower(coalesce(paket,'') || ' ' || coalesce(satuanKerja,'') || ' ' || coalesce(kldi,'') || ' ' || coalesce(lokasi,'') || ' ' || coalesce(jenisPengadaan,''))"
    package_expr = "lower(coalesce(paket,''))"
    where = f"regexp_matches({text_expr}, ?) and not regexp_matches({package_expr}, ?) and (regexp_matches({package_expr}, ?) or (regexp_matches({text_expr}, ?) and jenisPengadaan='Barang'))"
    params = [health_pattern, exclude_pattern, equipment_pattern, health_pattern]
    candidate_count = con.execute(f"select count(*) from sirup_raw where {where}", params).fetchone()[0]
    query = f"""
        select
            id as rup_id,
            id_referensi as package_id,
            pagu,
            satuanKerja,
            kldi,
            lokasi,
            jenisPengadaan,
            metode,
            sumberDana,
            paket,
            pemilihan,
            idKldi,
            idSatker
        from sirup_raw
        where {where}
        order by pagu desc nulls last, id desc
        limit {MAX_EXPORT_ROWS}
    """
    df = con.execute(query, params).fetchdf()
    con.close()
    return df, int(candidate_count)


def build_leads(raw: pd.DataFrame, contact_index: dict[str, dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source in raw.iterrows():
        satker = clean_value(source.get("satuanKerja"))
        kldi = clean_value(source.get("kldi"))
        package = clean_value(source.get("paket"))
        location = clean_value(source.get("lokasi"))
        province, city = parse_location(location)
        combined = " ".join([package, satker, kldi, location, clean_value(source.get("jenisPengadaan"))])
        matches = matched_keywords(combined)
        category = classify_equipment(combined, matches)
        contact = lookup_contact(contact_index, satker, kldi)
        email = clean_value(contact.get("email"))
        phone = clean_value(contact.get("phone"))
        whatsapp = clean_value(contact.get("whatsapp"))
        readiness = contact_readiness(email, phone, whatsapp)
        budget = float(source.get("pagu") or 0)
        priority = priority_for(budget, category, readiness)
        source_ref = f"{SIRUP_DUCKDB_CANDIDATES[0]}::sirup_raw.rup_id={clean_value(source.get('rup_id'))}"
        contact_source = clean_value(contact.get("source_file"))
        notes = "Verify institution fit and contact details before any outreach."
        if contact_source:
            notes += f" Contact enriched from local file: {Path(contact_source).name}."
        rows.append(
            {
                "institution_name": satker,
                "region_or_daerah": kldi or location,
                "province": province,
                "city_or_regency": city,
                "sector": classify_sector(combined),
                "institution_type": classify_institution_type(combined),
                "address": clean_value(contact.get("address")),
                "phone": phone,
                "whatsapp": whatsapp,
                "email": email,
                "website": clean_value(contact.get("website")),
                "pic_name": clean_value(contact.get("pic_name")),
                "pic_role": clean_value(contact.get("pic_role")),
                "package_name": package,
                "needed_equipment": ", ".join(matches[:8]) if matches else category,
                "equipment_category": category,
                "procurement_description": package,
                "budget_value": budget,
                "budget_value_idr": budget,
                "procurement_method": clean_value(source.get("metode")),
                "source_year": SOURCE_YEAR,
                "source_system": "SiRUP local DuckDB export",
                "source_url_or_reference": source_ref,
                "opportunity_priority": priority,
                "contact_readiness": readiness,
                "data_confidence": confidence_for(matches, readiness),
                "notes": notes,
                "kldi": kldi,
                "satker": satker,
                "work_unit": satker,
                "rup_id": clean_value(source.get("rup_id")),
                "package_id": clean_value(source.get("package_id")),
                "procurement_status": "",
                "schedule_or_period": clean_value(source.get("pemilihan")),
                "fiscal_year": SOURCE_YEAR,
                "raw_keywords_matched": ", ".join(matches),
                "recommended_next_action": recommended_action(priority, readiness),
            }
        )
    leads = pd.DataFrame(rows, columns=LEADS_COLUMNS)
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    leads["_priority_sort"] = leads["opportunity_priority"].map(priority_order).fillna(9)
    leads = leads.sort_values(["_priority_sort", "budget_value_idr"], ascending=[True, False]).drop(columns=["_priority_sort"])
    return leads


def recommended_action(priority: str, readiness: str) -> str:
    if readiness == "Missing direct contact":
        return "Research official contact before outreach"
    if priority == "High":
        return "Review package fit and prepare targeted B2B introduction"
    if priority == "Medium":
        return "Validate need and institution context before outreach"
    return "Keep for monitoring"


def build_summary_rows(leads: pd.DataFrame, candidate_count: int) -> list[list[Any]]:
    total_budget = float(leads["budget_value_idr"].fillna(0).sum()) if not leads.empty else 0
    rows = [
        ["Metric", "Value"],
        ["Candidate rows matched before export cap", candidate_count],
        ["Rows exported", len(leads)],
        ["Unique institutions", leads["institution_name"].nunique() if not leads.empty else 0],
        ["Total budget exported", total_budget],
        ["Rows with email", int((leads["email"].fillna("") != "").sum()) if not leads.empty else 0],
        ["Rows with phone", int((leads["phone"].fillna("") != "").sum()) if not leads.empty else 0],
        ["Rows with whatsapp", int((leads["whatsapp"].fillna("") != "").sum()) if not leads.empty else 0],
        ["Export cap", MAX_EXPORT_ROWS],
        [],
        ["Top provinces/regions", "Rows"],
    ]
    for key, value in Counter(leads["province"].fillna("")).most_common(10):
        if key:
            rows.append([key, value])
    rows.append([])
    rows.append(["Top equipment categories", "Rows"])
    for key, value in Counter(leads["equipment_category"].fillna("")).most_common(10):
        if key:
            rows.append([key, value])
    return rows


def methodology_rows(input_files: list[str], contact_files: list[str], candidate_count: int) -> list[list[Any]]:
    rows = [
        ["Section", "Detail"],
        ["Purpose", "Local-only SiRUP healthcare / medical-device procurement leads for ethical B2B sales research."],
        ["Primary procurement source", input_files[0] if input_files else ""],
        ["Rows matched before export cap", candidate_count],
        ["Rows exported", MAX_EXPORT_ROWS],
        ["Contact enrichment files", " | ".join(contact_files)],
        ["No fabrication rule", "Blank contact/PIC fields mean no matching local value was found."],
        ["Exclusions", ", ".join(EXCLUDE_KEYWORDS)],
        [],
        ["Keyword list", "Included in matching"],
    ]
    rows.extend([[keyword, "Yes"] for keyword in KEYWORDS])
    return rows


def write_sheet(ws, rows: list[list[Any]], freeze: str = "A2") -> None:
    for row in rows:
        ws.append(row)
    ws.freeze_panes = freeze
    if rows and rows[0]:
        ws.auto_filter.ref = ws.dimensions
    style_header(ws)
    auto_width(ws)


def style_header(ws) -> None:
    fill = PatternFill("solid", fgColor="0F172A")
    font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 24


def auto_width(ws, max_width: int = 48) -> None:
    for column_cells in ws.columns:
        letter = get_column_letter(column_cells[0].column)
        width = 10
        for cell in column_cells[:200]:
            value = "" if cell.value is None else str(cell.value)
            width = max(width, min(max_width, len(value) + 2))
        ws.column_dimensions[letter].width = width
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def create_workbook(leads: pd.DataFrame, candidate_count: int, input_files: list[str], contact_files: list[str]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    leads_ws = wb.active
    leads_ws.title = "Leads"
    write_sheet(leads_ws, [LEADS_COLUMNS] + leads[LEADS_COLUMNS].values.tolist())
    for col_name in ["budget_value", "budget_value_idr"]:
        idx = LEADS_COLUMNS.index(col_name) + 1
        for cell in leads_ws.iter_cols(min_col=idx, max_col=idx, min_row=2, max_row=leads_ws.max_row):
            for c in cell:
                c.number_format = 'Rp #,##0'

    summary_ws = wb.create_sheet("Summary")
    write_sheet(summary_ws, build_summary_rows(leads, candidate_count))
    for row in summary_ws.iter_rows(min_row=2, max_col=2):
        if row[0].value == "Total budget exported":
            row[1].number_format = 'Rp #,##0'

    methodology_ws = wb.create_sheet("Keyword_Methodology")
    write_sheet(methodology_ws, methodology_rows(input_files, contact_files, candidate_count))

    missing = leads[(leads["email"].fillna("") == "") & (leads["phone"].fillna("") == "") & (leads["whatsapp"].fillna("") == "")]
    missing_cols = [
        "institution_name",
        "region_or_daerah",
        "province",
        "package_name",
        "equipment_category",
        "budget_value_idr",
        "opportunity_priority",
        "recommended_next_action",
        "source_url_or_reference",
    ]
    missing_ws = wb.create_sheet("Missing_Contacts")
    write_sheet(missing_ws, [missing_cols] + missing[missing_cols].values.tolist())
    budget_idx = missing_cols.index("budget_value_idr") + 1
    for cell in missing_ws.iter_cols(min_col=budget_idx, max_col=budget_idx, min_row=2, max_row=missing_ws.max_row):
        for c in cell:
            c.number_format = 'Rp #,##0'

    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
    wb.save(OUTPUT_PATH)


def validate_workbook() -> None:
    wb = load_workbook(OUTPUT_PATH, read_only=True, data_only=True)
    print(f"Excel file created: {OUTPUT_PATH}")
    print(f"Workbook sheets: {wb.sheetnames}")
    ws = wb["Leads"]
    print(f"Rows exported: {ws.max_row - 1}")
    columns = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    print("Columns:")
    print(columns)
    print("Top 10 rows preview:")
    preview_cols = ["institution_name", "province", "package_name", "equipment_category", "budget_value_idr", "email", "phone", "opportunity_priority"]
    indexes = [columns.index(col) for col in preview_cols]
    for row in ws.iter_rows(min_row=2, max_row=min(ws.max_row, 11), values_only=True):
        print({col: row[index] for col, index in zip(preview_cols, indexes)})
    wb.close()


def main() -> None:
    sirup_files = find_existing(SIRUP_DUCKDB_CANDIDATES)
    if not sirup_files:
        raise FileNotFoundError("No local SiRUP DuckDB source found.")
    contact_files = find_existing(CONTACT_FILE_CANDIDATES)
    print("Using primary SiRUP source:", sirup_files[0])
    print("Using contact files:", contact_files)
    contact_index, used_contact_files = build_contact_index(contact_files)
    raw, candidate_count = load_sirup_rows(sirup_files[0])
    leads = build_leads(raw, contact_index)
    create_workbook(leads, candidate_count, [str(sirup_files[0])], used_contact_files)
    validate_workbook()


if __name__ == "__main__":
    main()
