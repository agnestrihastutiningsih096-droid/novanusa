from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import duckdb
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from procurement_identity_resolution import (
    EvidenceRecord,
    ProcurementRecord,
    canonical_json,
    extract_procurement_status,
    resolve_identity,
)
from sirup_snapshot_resolver import resolve_active_sirup_database

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs" / "sirup_procurement_status_crosscheck.xlsx"
DEFAULT_ROOTS = [
    ROOT,
    ROOT.parent / "mia-automation",
    ROOT.parent / "mia-contact-crawler",
]

STATUS_TERMS = [
    "tender",
    "non tender",
    "non-tender",
    "pengadaan langsung",
    "e-purchasing",
    "katalog",
    "epurchasing",
    "pemenang",
    "pemenang berkontrak",
    "kontrak",
    "selesai",
    "gagal",
    "batal",
    "dibatalkan",
    "evaluasi",
    "pengumuman",
    "sanggah",
    "tanda tangan kontrak",
]

REAL_EVIDENCE_SOURCE_HINTS = [
    "spse",
    "lpse",
    "tender",
    "non_tender",
    "non-tender",
    "epurchasing",
    "e-purchasing",
    "katalog",
    "pemenang",
    "kontrak",
    "berkontrak",
    "pengumuman",
    "sanggah",
]

DERIVED_SOURCE_HINTS = [
    "sirup_",
    "institution_opportunities",
    "mitracom_opportunities",
    "mitracom_scored",
    "contact",
    "contacts",
    "qwen",
    "sendable",
    "outreach",
    "alkes_sirup_leads",
    "master_institutions",
    "sales_fit",
]

OUTPUT_COLUMNS = [
    "institution_name",
    "region_or_daerah",
    "work_unit/satker",
    "rup_id",
    "package_id",
    "package_name",
    "procurement_description",
    "budget_value",
    "method_from_sirup",
    "planned_month_or_date",
    "source_year",
    "identity_status",
    "identity_decision_id",
    "identity_decision_evidence",
    "manual_review_record",
    "factual_status",
    "evidence_source_type",
    "evidence_file",
    "evidence_url_or_reference",
    "evidence_matched_text",
    "match_basis",
    "match_confidence",
    "manual_check_url_sirup",
    "manual_check_url_spse_nasional_search",
    "manual_check_notes",
]

@dataclass
class EvidenceRow:
    source_type: str
    evidence_file: str
    url_or_reference: str
    matched_text: str
    rup_id: str
    package_id: str
    package_name: str
    institution_name: str
    budget_value: float | None
    year: str
    factual_status: str
    source_record_id: str = ""
    collected_at: str = ""


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def normalize(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_budget(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9,.-]", "", str(value))
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def parse_location(location: str) -> tuple[str, str]:
    parts = [part.strip() for part in clean(location).split(",") if part.strip()]
    province = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""
    return province, city


def month_number(value: Any) -> int | None:
    text = clean(value).lower()
    month_map = {
        "january": 1,
        "januari": 1,
        "february": 2,
        "februari": 2,
        "march": 3,
        "maret": 3,
        "april": 4,
        "may": 5,
        "mei": 5,
        "june": 6,
        "juni": 6,
        "july": 7,
        "juli": 7,
        "august": 8,
        "agustus": 8,
        "september": 9,
        "october": 10,
        "oktober": 10,
        "november": 11,
        "december": 12,
        "desember": 12,
    }
    for name, number in month_map.items():
        if name in text:
            return number
    match = re.search(r"\b(1[0-2]|0?[1-9])\b", text)
    return int(match.group(1)) if match else None


def factual_status_from_text(text: str) -> str | None:
    lowered = text.lower()
    if any(term in lowered for term in ["batal", "dibatalkan", "gagal"]):
        return "FOUND_CANCELLED_OR_FAILED"
    if any(term in lowered for term in ["pemenang berkontrak", "tanda tangan kontrak", "berkontrak"]):
        return "FOUND_CONTRACT"
    if "kontrak" in lowered:
        return "FOUND_CONTRACT"
    if "selesai" in lowered:
        return "FOUND_COMPLETED"
    if "pemenang" in lowered:
        return "FOUND_WINNER"
    if any(term in lowered for term in ["e-purchasing", "epurchasing", "katalog", "e katalog", "e-katalog"]):
        return "FOUND_E_PURCHASING_PROCESS"
    if any(term in lowered for term in ["non tender", "non-tender", "pengadaan langsung"]):
        return "FOUND_NON_TENDER_PROCESS"
    if any(term in lowered for term in ["tender", "evaluasi", "pengumuman", "sanggah"]):
        return "FOUND_TENDER_PROCESS"
    return None


def source_type_for(path: Path, row_text: str, columns: list[str]) -> str:
    combined = f"{path.name} {' '.join(columns)} {row_text}".lower()
    if "lpse" in combined:
        return "LPSE_LOCAL_EXPORT"
    if "spse" in combined:
        return "SPSE_LOCAL_EXPORT"
    if any(term in combined for term in ["e-purchasing", "epurchasing", "katalog", "e katalog", "e-katalog"]):
        return "E_PURCHASING_OR_KATALOG_LOCAL_EXPORT"
    if any(term in combined for term in ["pemenang", "kontrak", "tender", "sanggah", "pengumuman"]):
        return "PROCUREMENT_STATUS_LOCAL_EXPORT"
    return "LOCAL_FILE"


def looks_derived(path: Path) -> bool:
    lowered = path.name.lower()
    return any(hint in lowered for hint in DERIVED_SOURCE_HINTS)


def has_real_source_hint(path: Path) -> bool:
    lowered = path.name.lower()
    return any(hint in lowered for hint in REAL_EVIDENCE_SOURCE_HINTS)


def text_file_has_status_terms(path: Path, max_bytes: int = 2_000_000) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            sample = handle.read(max_bytes).lower()
        return any(term in sample for term in STATUS_TERMS)
    except Exception:
        return False


def discover_local_files(roots: list[Path], explicit_files: list[Path] | None = None, scan_generic_content: bool = False) -> list[Path]:
    exts = {".csv", ".xlsx", ".xls", ".html", ".htm", ".json"}
    excluded_dirs = {"node_modules", ".next", ".venv", ".codex_tmp", "email_attachments", "__pycache__", ".git"}
    files: list[Path] = []
    seen: set[Path] = set()
    for explicit in explicit_files or []:
        if explicit.exists() and explicit.is_file():
            resolved = explicit.resolve()
            if resolved not in seen:
                files.append(explicit)
                seen.add(resolved)
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in excluded_dirs]
            for filename in filenames:
                path = Path(dirpath) / filename
                if path.suffix.lower() not in exts:
                    continue
                resolved = path.resolve()
                if resolved in seen or resolved == DEFAULT_OUTPUT.resolve():
                    continue
                generic_hit = scan_generic_content and path.suffix.lower() in {".csv", ".html", ".htm", ".json"} and not looks_derived(path) and text_file_has_status_terms(path)
                if has_real_source_hint(path) or generic_hit:
                    files.append(path)
                    seen.add(resolved)
    return files

def column_by_candidates(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {col.lower().strip(): col for col in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for col in columns:
        norm_col = normalize(col)
        if any(normalize(candidate) in norm_col for candidate in candidates):
            return col
    return None


def rows_from_dataframe(df: pd.DataFrame, path: Path, max_rows: int = 10000) -> list[EvidenceRow]:
    evidence: list[EvidenceRow] = []
    if df.empty:
        return evidence
    df = df.head(max_rows).fillna("")
    columns = [str(col) for col in df.columns]
    rup_col = column_by_candidates(columns, ["rup_id", "id_rup", "id", "kode_rup"])
    package_id_col = column_by_candidates(columns, ["package_id", "paket_id", "id_paket", "id_referensi"])
    package_col = column_by_candidates(columns, ["package_name", "nama_paket", "paket", "nama tender", "tender", "procurement_description"])
    inst_col = column_by_candidates(columns, ["institution_name", "satuanKerja", "satker", "unit_kerja", "kldi", "instansi", "agency"])
    budget_col = column_by_candidates(columns, ["budget_value", "budget", "pagu", "nilai", "nilai_pagu", "hps"])
    year_col = column_by_candidates(columns, ["source_year", "fiscal_year", "tahun", "year"])
    url_col = column_by_candidates(columns, ["url", "source_url", "link", "source_url_or_reference", "reference"])
    status_col = column_by_candidates(columns, ["status", "factual_status", "tahapan", "hasil", "keterangan"])

    for idx, row in df.iterrows():
        values = [clean(v) for v in row.tolist()]
        row_text = " | ".join(v for v in values if v)
        if not row_text:
            continue
        lowered = row_text.lower()
        if not any(term in lowered for term in STATUS_TERMS):
            continue
        status = factual_status_from_text(row_text)
        if not status:
            continue
        if looks_derived(path) and not has_real_source_hint(path):
            continue
        evidence.append(
            EvidenceRow(
                source_type=source_type_for(path, row_text, columns),
                evidence_file=str(path),
                url_or_reference=clean(row.get(url_col)) if url_col else f"{path.name} row {idx + 2}",
                matched_text=(clean(row.get(status_col)) if status_col else row_text)[:1000],
                rup_id=clean(row.get(rup_col)) if rup_col else "",
                package_id=clean(row.get(package_id_col)) if package_id_col else "",
                package_name=clean(row.get(package_col)) if package_col else "",
                institution_name=clean(row.get(inst_col)) if inst_col else "",
                budget_value=parse_budget(row.get(budget_col)) if budget_col else None,
                year=clean(row.get(year_col)) if year_col else "",
                factual_status=status,
                source_record_id=f"{path.name}#{idx + 2}",
            )
        )
    return evidence


def read_evidence_file(path: Path) -> tuple[list[EvidenceRow], str]:
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, low_memory=False, encoding_errors="ignore")
            return rows_from_dataframe(df, path), "scanned_csv"
        if path.suffix.lower() in {".xlsx", ".xls"}:
            frames = []
            sheets = pd.read_excel(path, sheet_name=None, nrows=10000)
            for sheet_name, frame in sheets.items():
                frame = frame.copy()
                frame["_sheet_name"] = sheet_name
                frames.append(frame)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            return rows_from_dataframe(df, path), "scanned_excel"
        if path.suffix.lower() in {".html", ".htm", ".json"}:
            text = path.read_text(encoding="utf-8", errors="ignore")[:2_000_000]
            if any(term in text.lower() for term in STATUS_TERMS) and (has_real_source_hint(path) or not looks_derived(path)):
                status = factual_status_from_text(text)
                if status:
                    return [EvidenceRow(source_type=source_type_for(path, text[:1000], []), evidence_file=str(path), url_or_reference=str(path), matched_text=re.sub(r"\s+", " ", text[:1000]), rup_id="", package_id="", package_name="", institution_name="", budget_value=None, year="", factual_status=status)], "scanned_text"
            return [], "scanned_text"
    except Exception as exc:
        return [], f"error: {type(exc).__name__}: {exc}"
    return [], "unsupported"


def load_evidence(roots: list[Path], explicit_files: list[Path] | None = None, scan_generic_content: bool = False) -> tuple[list[EvidenceRow], list[dict[str, Any]]]:
    evidence: list[EvidenceRow] = []
    source_rows: list[dict[str, Any]] = []
    files = discover_local_files(roots, explicit_files=explicit_files, scan_generic_content=scan_generic_content)
    for path in files:
        rows, scan_status = read_evidence_file(path)
        evidence.extend(rows)
        source_rows.append(
            {
                "file_path": str(path),
                "file_type": path.suffix.lower(),
                "scan_status": scan_status,
                "evidence_rows_found": len(rows),
                "source_hint": "real_status_hint" if has_real_source_hint(path) else "generic_or_derived",
                "used_for_matching": "yes" if rows else "no",
            }
        )
    if not source_rows:
        source_rows.append({"file_path": "", "file_type": "", "scan_status": "no candidate local SPSE/LPSE/e-purchasing evidence files found", "evidence_rows_found": 0, "source_hint": "none", "used_for_matching": "no"})
    return evidence, source_rows


def resolve_sirup_db(path: str | None) -> Path:
    if path:
        return Path(path)
    return resolve_active_sirup_database()


def load_sirup(args: argparse.Namespace) -> tuple[pd.DataFrame, list[str]]:
    db_path = Path(args.sirup_db)
    if not db_path.exists():
        raise FileNotFoundError(f"SiRUP DuckDB not found: {db_path}")
    con = duckdb.connect(str(db_path), read_only=True)
    fields = [row[0] for row in con.execute("describe sirup_raw").fetchall()]
    where = []
    params: list[Any] = []
    if args.year:
        where.append("regexp_matches(lower(coalesce(pemilihan,'')), ?)")
        params.append(str(args.year).lower())
    if args.keyword:
        where.append("regexp_matches(lower(coalesce(paket,'') || ' ' || coalesce(jenisPengadaan,'') || ' ' || coalesce(metode,'')), ?)")
        params.append(args.keyword.lower())
    if args.institution:
        where.append("regexp_matches(lower(coalesce(satuanKerja,'') || ' ' || coalesce(kldi,'')), ?)")
        params.append(args.institution.lower())
    if args.package_name:
        where.append("regexp_matches(lower(coalesce(paket,'')), ?)")
        params.append(args.package_name.lower())
    if args.month:
        where.append("(idBulan = ? or regexp_matches(lower(coalesce(pemilihan,'')), ?))")
        params.extend([int(args.month), str(args.month)])
    where_sql = "where " + " and ".join(where) if where else ""
    query = f"""
        select
            id as rup_id,
            id_referensi as package_id,
            idBulan,
            pemilihan,
            pagu,
            satuanKerja,
            kldi,
            lokasi,
            metode,
            paket,
            jenisPengadaan,
            sumberDana
        from sirup_raw
        {where_sql}
        order by pagu desc nulls last, id desc
        limit {int(args.limit)}
    """
    df = con.execute(query, params).fetchdf()
    con.close()
    return df, fields


def fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def budget_similarity(a: float | None, b: float | None) -> float:
    if not a or not b:
        return 0.0
    denom = max(abs(a), abs(b), 1.0)
    diff = abs(a - b) / denom
    return max(0.0, 1.0 - diff)


def resolve_row(row: pd.Series, evidence_rows: list[EvidenceRow]):
    rup_id = clean(row.get("rup_id"))
    package_id = clean(row.get("package_id"))
    package_name = clean(row.get("paket"))
    institution = clean(row.get("satuanKerja"))
    kldi = clean(row.get("kldi"))
    budget = parse_budget(row.get("pagu"))
    year = "2026" if "2026" in clean(row.get("pemilihan")) else ""

    sirup_record = ProcurementRecord(
        record_id=rup_id or package_id,
        rup_id=rup_id,
        package_id=package_id,
        package_name=package_name,
        institution=kldi,
        satker=institution,
        year=int(year) if year else None,
        budget=budget,
        procurement_method=clean(row.get("metode")),
        location=clean(row.get("lokasi")),
        category=clean(row.get("jenisPengadaan")),
    )
    candidates = [
        EvidenceRecord(
            candidate_id=ev.source_record_id or f"{ev.evidence_file}|{ev.url_or_reference}",
            package_name=ev.package_name,
            institution=ev.institution_name,
            year=int(ev.year[:4]) if ev.year[:4].isdigit() else None,
            budget=ev.budget_value,
            evidence_type=ev.source_type,
            source_url=ev.url_or_reference,
            source_file=ev.evidence_file,
            source_record_id=ev.source_record_id,
            collected_at=ev.collected_at,
            provenance="Local public procurement evidence export",
            source_status=ev.factual_status,
        )
        for ev in evidence_rows
    ]
    identity = resolve_identity(sirup_record, candidates, dataset_version="SPRINT1_CONTROLLED_LOCAL_DATASET")
    procurement = extract_procurement_status(identity, candidates)
    selected = next(
        (
            ev
            for ev in evidence_rows
            if (ev.source_record_id or f"{ev.evidence_file}|{ev.url_or_reference}") == identity.selected_candidate_id
        ),
        None,
    ) if identity.identity_status in {"PROBABLE_MATCH", "CONFIRMED_MATCH"} else None
    return identity, procurement, selected


def sirup_url(rup_id: str, package_name: str) -> str:
    query = rup_id or package_name
    return f"https://sirup.lkpp.go.id/sirup/ro/penyedia?search={quote_plus(query)}"


def spse_search_url(package_name: str) -> str:
    return f"https://spse.inaproc.id/?q={quote_plus(package_name)}"


def build_crosscheck(sirup: pd.DataFrame, evidence_rows: list[EvidenceRow]) -> pd.DataFrame:
    output = []
    for _, row in sirup.iterrows():
        province, city = parse_location(clean(row.get("lokasi")))
        identity, procurement, evidence = resolve_row(row, evidence_rows)
        package_name = clean(row.get("paket"))
        rup_id = clean(row.get("rup_id"))
        output.append(
            {
                "institution_name": clean(row.get("kldi")),
                "region_or_daerah": clean(row.get("lokasi")) or province or city,
                "work_unit/satker": clean(row.get("satuanKerja")),
                "rup_id": rup_id,
                "package_id": clean(row.get("package_id")),
                "package_name": package_name,
                "procurement_description": package_name,
                "budget_value": parse_budget(row.get("pagu")) or 0,
                "method_from_sirup": clean(row.get("metode")),
                "planned_month_or_date": clean(row.get("pemilihan")) or clean(row.get("idBulan")),
                "source_year": 2026 if "2026" in clean(row.get("pemilihan")) else "",
                "identity_status": identity.identity_status,
                "identity_decision_id": identity.decision_evidence["decision_id"],
                "identity_decision_evidence": canonical_json(identity.decision_evidence),
                "manual_review_record": canonical_json(identity.manual_review_record) if identity.manual_review_record else "",
                "factual_status": procurement["normalized_status"],
                "evidence_source_type": evidence.source_type if evidence else "NO_LOCAL_EVIDENCE",
                "evidence_file": evidence.evidence_file if evidence else "",
                "evidence_url_or_reference": evidence.url_or_reference if evidence else "",
                "evidence_matched_text": evidence.matched_text if evidence else "",
                "match_basis": ", ".join(identity.match_signals),
                "match_confidence": identity.identity_confidence,
                "manual_check_url_sirup": sirup_url(rup_id, package_name),
                "manual_check_url_spse_nasional_search": spse_search_url(package_name),
                "manual_check_notes": identity.manual_review_reason or identity.decision_explanation,
            }
        )
    return pd.DataFrame(output, columns=OUTPUT_COLUMNS)


def summary_rows(crosscheck: pd.DataFrame) -> list[list[Any]]:
    total = len(crosscheck)
    real_evidence = int((crosscheck["evidence_source_type"] != "NO_LOCAL_EVIDENCE").sum())
    planning = int((crosscheck["factual_status"] == "PLANNING_ONLY_SIRUP").sum())
    month_counts = Counter()
    for value in crosscheck["planned_month_or_date"]:
        month = month_number(value)
        if month:
            month_counts[month] += 1
    may_june = month_counts[5] + month_counts[6]
    jan_apr = sum(month_counts[m] for m in [1, 2, 3, 4])
    count_2025 = int(crosscheck["planned_month_or_date"].astype(str).str.contains("2025", case=False, na=False).sum())
    rows = [
        ["Metric", "Value"],
        ["Total SiRUP rows checked", total],
        ["Rows with real local evidence beyond SiRUP", real_evidence],
        ["Rows planning-only because no local evidence was found", planning],
        ["Count May 2026", month_counts[5]],
        ["Count June 2026", month_counts[6]],
        ["Percentage May+June 2026 of checked rows", may_june / total if total else 0],
        ["Count Jan-Apr 2026", jan_apr],
        ["Count 2025 if present", count_2025],
        [],
        ["factual_status", "Count"],
    ]
    for status, count in Counter(crosscheck["factual_status"]).most_common():
        rows.append([status, count])
    rows.append([])
    rows.append(["Planned month", "Count"])
    for month in range(1, 13):
        rows.append([month, month_counts[month]])
    return rows


def methodology_rows(args: argparse.Namespace, sirup_fields: list[str], evidence_count: int) -> list[list[Any]]:
    return [
        ["Section", "Detail"],
        ["Purpose", "Crosscheck selected local SiRUP rows against local public procurement evidence exports."],
        ["Primary SiRUP source", str(args.sirup_db)],
        ["SiRUP fields found", ", ".join(sirup_fields)],
        ["Date/month fields used", "idBulan and pemilihan"],
        ["Interpretation of PLANNING_ONLY_SIRUP", "Only means no local evidence was found; it does not mean not purchased or still open."],
        ["Evidence rows loaded", evidence_count],
        ["Status terms searched", ", ".join(STATUS_TERMS)],
        ["Matching basis", "Locked Identity Signal Registry; cross-namespace numeric equality is not an identity signal."],
        ["No scraping/API rule", "No external websites or APIs are called. Manual search URLs are references only."],
        ["Default row limit", args.limit],
        ["Filters", f"year={args.year or ''}; keyword={args.keyword or ''}; institution={args.institution or ''}; package_name={args.package_name or ''}; month={args.month or ''}"],
    ]


def write_sheet(ws, rows: list[list[Any]]) -> None:
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
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
    ws.row_dimensions[1].height = 26


def auto_width(ws, max_width: int = 52) -> None:
    for column_cells in ws.columns:
        letter = get_column_letter(column_cells[0].column)
        width = 10
        for cell in column_cells[:250]:
            value = "" if cell.value is None else str(cell.value)
            width = max(width, min(max_width, len(value) + 2))
        ws.column_dimensions[letter].width = width
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def create_excel(crosscheck: pd.DataFrame, source_files: list[dict[str, Any]], args: argparse.Namespace, sirup_fields: list[str], evidence_count: int) -> None:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Crosscheck"
    write_sheet(ws, [OUTPUT_COLUMNS] + crosscheck[OUTPUT_COLUMNS].values.tolist())
    budget_idx = OUTPUT_COLUMNS.index("budget_value") + 1
    confidence_idx = OUTPUT_COLUMNS.index("match_confidence") + 1
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        row[budget_idx - 1].number_format = 'Rp #,##0'
        row[confidence_idx - 1].number_format = '0.000'

    summary = wb.create_sheet("Summary")
    write_sheet(summary, summary_rows(crosscheck))
    for row in summary.iter_rows(min_row=2, max_col=2):
        if row[0].value == "Percentage May+June 2026 of checked rows":
            row[1].number_format = "0.0%"

    manual = wb.create_sheet("Manual_Check_Queue")
    manual_df = crosscheck[
        crosscheck["identity_status"].eq("NEEDS_MANUAL_REVIEW")
        | crosscheck["factual_status"].eq("SIRUP_PLANNING_ONLY")
    ].copy()
    manual_cols = [
        "institution_name",
        "work_unit/satker",
        "rup_id",
        "package_name",
        "budget_value",
        "planned_month_or_date",
        "factual_status",
        "identity_status",
        "manual_check_url_sirup",
        "manual_check_url_spse_nasional_search",
        "manual_check_notes",
    ]
    write_sheet(manual, [manual_cols] + manual_df[manual_cols].values.tolist())
    manual_budget_idx = manual_cols.index("budget_value") + 1
    for row in manual.iter_rows(min_row=2, max_row=manual.max_row):
        row[manual_budget_idx - 1].number_format = 'Rp #,##0'

    source = wb.create_sheet("Source_Files")
    source_cols = ["file_path", "file_type", "scan_status", "evidence_rows_found", "source_hint", "used_for_matching"]
    source_rows = [[item.get(col, "") for col in source_cols] for item in source_files]
    write_sheet(source, [source_cols] + source_rows)

    methodology = wb.create_sheet("Methodology")
    write_sheet(methodology, methodology_rows(args, sirup_fields, evidence_count))

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = False
    wb.save(output)


def validate_output(output: Path) -> None:
    wb = load_workbook(output, read_only=True, data_only=True)
    ws = wb["Crosscheck"]
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    status_idx = headers.index("factual_status")
    evidence_idx = headers.index("evidence_source_type")
    month_idx = headers.index("planned_month_or_date")
    print("input row count:", len(rows))
    print("matched evidence count:", sum(1 for row in rows if row[evidence_idx] != "NO_LOCAL_EVIDENCE"))
    print("status distribution:", dict(Counter(row[status_idx] for row in rows)))
    month_dist = Counter(month_number(row[month_idx]) for row in rows if month_number(row[month_idx]))
    print("month distribution:", dict(sorted(month_dist.items())))
    print("Excel output path:", output)
    wb.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crosscheck selected SiRUP packages against local SPSE/LPSE/e-purchasing evidence exports.")
    parser.add_argument("--sirup-db", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--keyword", default="")
    parser.add_argument("--institution", default="")
    parser.add_argument("--package-name", default="")
    parser.add_argument("--month", type=int, default=None)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--roots", nargs="*", default=[str(root) for root in DEFAULT_ROOTS])
    parser.add_argument("--evidence-files", nargs="*", default=[], help="Explicit local SPSE/LPSE/e-purchasing CSV/XLSX/HTML/JSON files to scan even if filename is generic.")
    parser.add_argument("--scan-generic-content", action="store_true", help="Also scan generic text files for status terms. Slower; useful for manually downloaded CSV/HTML exports with generic names.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.sirup_db = resolve_sirup_db(args.sirup_db)
    roots = [Path(root) for root in args.roots]
    sirup, sirup_fields = load_sirup(args)
    explicit_files = [Path(path) for path in args.evidence_files]
    evidence_rows, source_files = load_evidence(roots, explicit_files=explicit_files, scan_generic_content=args.scan_generic_content)
    crosscheck = build_crosscheck(sirup, evidence_rows)
    output_path = Path(args.output)
    decision_sidecar = output_path.with_suffix(".identity-decisions.jsonl")
    decision_sidecar.parent.mkdir(parents=True, exist_ok=True)
    decision_lines = sorted(crosscheck["identity_decision_evidence"].tolist())
    decision_sidecar.write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    review_sidecar = output_path.with_suffix(".manual-review-records.jsonl")
    review_lines = sorted(value for value in crosscheck["manual_review_record"].tolist() if value)
    review_sidecar.write_text(("\n".join(review_lines) + "\n") if review_lines else "", encoding="utf-8")
    crosscheck["identity_decision_evidence"] = crosscheck["identity_decision_id"].map(
        lambda value: f"{decision_sidecar.name}#{value}"
    )
    crosscheck["manual_review_record"] = crosscheck["manual_review_record"].map(
        lambda value: review_sidecar.name if value else ""
    )
    create_excel(crosscheck, source_files, args, sirup_fields, len(evidence_rows))
    print("identity decision evidence digest:", hashlib.sha256(decision_sidecar.read_bytes()).hexdigest())
    validate_output(output_path)


if __name__ == "__main__":
    main()
