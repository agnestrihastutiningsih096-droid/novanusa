#!/usr/bin/env python3
"""
Build a national LPSE registry from public eProc sources.

Source of truth:
- https://eproc.lkpp.go.id/lpse/index

Design goals:
- public-only
- small and audit-friendly
- provenance retained
- no scoring
- no dashboard dependencies
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "data" / "reference" / "lpse"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "reference"
DEFAULT_CSV = DEFAULT_OUT_DIR / "lpse_registry.csv"
DEFAULT_JSON = DEFAULT_OUT_DIR / "lpse_registry.json"
DEFAULT_METADATA = DEFAULT_OUT_DIR / "lpse_registry.metadata.json"
DEFAULT_QUALITY_JSON = DEFAULT_OUTPUT_DIR / "lpse_registry_quality_report.json"
DEFAULT_QUALITY_XLSX = DEFAULT_OUTPUT_DIR / "lpse_registry_quality_report.xlsx"
DEFAULT_SOURCE_URL = "https://eproc.lkpp.go.id/lpse/index"
DEFAULT_RAW_DIR = DEFAULT_OUT_DIR / "raw"

REGISTRY_ARTIFACT_ID = "novanusa:lpse-registry:csv"
REGISTRY_HASH_ALGORITHM = "sha256"

PROVINCES = [
    "Aceh",
    "Bali",
    "Banten",
    "Bengkulu",
    "DI Yogyakarta",
    "DKI Jakarta",
    "Gorontalo",
    "Jambi",
    "Jawa Barat",
    "Jawa Tengah",
    "Jawa Timur",
    "Kalimantan Barat",
    "Kalimantan Selatan",
    "Kalimantan Tengah",
    "Kalimantan Timur",
    "Kalimantan Utara",
    "Kep. Bangka Belitung",
    "Kepulauan Riau",
    "Lampung",
    "Maluku",
    "Maluku Utara",
    "Nusa Tenggara Barat",
    "Nusa Tenggara Timur",
    "Papua",
    "Papua Barat",
    "Papua Barat Daya",
    "Papua Pegunungan",
    "Papua Selatan",
    "Papua Tengah",
    "Riau",
    "Sulawesi Barat",
    "Sulawesi Selatan",
    "Sulawesi Tengah",
    "Sulawesi Tenggara",
    "Sulawesi Utara",
    "Sumatera Barat",
    "Sumatera Selatan",
    "Sumatera Utara",
]

PROVINCE_NAMES_FOR_MATCHING = sorted(PROVINCES, key=len, reverse=True)

CATEGORY_RULES = [
    ("Kementerian", "Kementerian"),
    ("Lembaga", "Lembaga"),
    ("Provinsi", "Pemerintah Provinsi"),
    ("Kabupaten", "Pemerintah Kabupaten"),
    ("Kota", "Pemerintah Kota"),
    ("Universitas", "Perguruan Tinggi"),
    ("Sekolah Tinggi", "Perguruan Tinggi"),
    ("Politeknik", "Perguruan Tinggi"),
    ("PTN", "Perguruan Tinggi Negeri"),
    ("BUMN", "BUMN"),
]


@dataclass
class RegistryRow:
    nama_lpse: str
    instansi: str | None
    kategori_instansi: str | None
    provinsi: str | None
    kabupaten_kota: str | None
    official_lpse_url: str | None
    domain: str | None
    https: bool | None
    aktif: bool | None
    dapat_diakses: bool | None
    menggunakan_spse: bool | None
    versi_spse: str | None
    portal_induk: str | None
    tanggal_pengecekan: str
    source_url: str
    source_page: str | None = None
    source_page_number: int | None = None
    source_filter_provinsi: str | None = None
    source_note: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_registry_artifact_metadata(csv_path: Path) -> dict[str, str]:
    """Bind routing provenance to the exact canonical CSV bytes collectors read."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Canonical LPSE registry artifact is missing: {csv_path}")
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    return {
        "registry_artifact_id": REGISTRY_ARTIFACT_ID,
        "registry_artifact_hash": digest,
        "registry_version": f"{REGISTRY_HASH_ALGORITHM}:{digest}",
    }


def load_registry_artifact_metadata(csv_path: Path, metadata_path: Path) -> dict[str, str]:
    """Load metadata only when it is complete and matches the canonical CSV."""
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Canonical LPSE registry metadata is missing or invalid: {metadata_path}") from exc
    expected = build_registry_artifact_metadata(csv_path)
    if not isinstance(metadata, dict) or metadata != expected:
        raise ValueError("Canonical LPSE registry metadata does not match the registry artifact")
    return metadata


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return slug or "lpse"


def infer_category(name: str | None) -> str | None:
    if not name:
        return None
    text = normalize_space(name)
    for needle, label in CATEGORY_RULES:
        if needle.lower() in text.lower():
            return label
    return None


def infer_province(text: str | None) -> str | None:
    if not text:
        return None
    for province in PROVINCE_NAMES_FOR_MATCHING:
        if province.lower() in text.lower():
            return province
    return None


def infer_kabupaten_kota(name: str | None) -> str | None:
    if not name:
        return None
    lowered = name.lower()
    if "kabupaten" in lowered or "kota" in lowered:
        return clean_text(name)
    return None


def guess_spse_version(text: str | None) -> str | None:
    if not text:
        return None
    patterns = [
        r"\bSPSE\s*v?([0-9]+(?:\.[0-9]+)*)\b",
        r"\bPortal\s+eProc\s*v?([0-9]+(?:\.[0-9]+)*)\b",
        r"\bInaproc\s*v?([0-9]+(?:\.[0-9]+)*)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"v{match.group(1)}"
    return None


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "NovaNusa LPSE Registry Builder/1.0 (+https://eproc.lkpp.go.id/lpse/index)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }
    )
    return session


def fetch_html(session: requests.Session, url: str, timeout: int = 30) -> tuple[str | None, int | None, str | None]:
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text, response.status_code, response.url
    except requests.RequestException as exc:
        return None, getattr(exc.response, "status_code", None), None


def save_raw_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def detect_last_page(soup: BeautifulSoup) -> int:
    page_numbers: list[int] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        match = re.search(r"/lpse/index/(?:\d+/)?0/(\d+)$", href)
        if match:
            page_numbers.append(int(match.group(1)))
    return max(page_numbers) if page_numbers else 1


def discover_provinces(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        return []
    select = form.find("select", attrs={"name": "propinsi"})
    if not select:
        return []
    provinces: list[tuple[str, str]] = []
    for opt in select.find_all("option"):
        value = (opt.get("value") or "").strip()
        label = clean_text(opt.get_text(" ", strip=True))
        if value:
            provinces.append((value, label or value))
    return provinces


def parse_card(card: BeautifulSoup, page_url: str, page_number: int, filter_province: str | None) -> RegistryRow | None:
    title_el = card.find("h4")
    name = clean_text(title_el.get_text(" ", strip=True) if title_el else None)
    if not name:
        return None

    badge = card.select_one(".badge")
    status_text = clean_text(badge.get_text(" ", strip=True) if badge else None)
    if status_text:
        status_text = re.sub(r"^\d+\s*", "", status_text)

    labels: dict[str, str | None] = {}
    for block in card.select(".form-group.row"):
        label_el = block.select_one("label.col-form-label.light")
        value_el = block.select_one("p.form-row-content")
        if label_el:
            key = normalize_space(label_el.get_text(" ", strip=True)).upper()
            value = clean_text(value_el.get_text(" ", strip=True) if value_el else None)
            labels[key] = value

    footer_date = None
    footer_value = card.select_one(".card-footer .item-content")
    if footer_value:
        footer_date = clean_text(footer_value.get_text(" ", strip=True))

    detail_url = None
    official_url = None
    for a in card.find_all("a", href=True):
        txt = normalize_space(a.get_text(" ", strip=True))
        href = a.get("href") or ""
        if txt == "Detail LPSE":
            detail_url = urljoin(page_url, href)
        elif txt == "Ke Halaman Web LPSE" and href.strip():
            official_url = urljoin(page_url, href)

    domain = urlparse(official_url).netloc if official_url else None
    https = urlparse(official_url).scheme.lower() == "https" if official_url else None
    category = infer_category(name)
    province = labels.get("PROVINSI")
    kabupaten_kota = infer_kabupaten_kota(name)
    version = labels.get("VERSI SPSE") or None
    if version:
        version = clean_text(version)

    active = None
    if status_text:
        lowered = status_text.lower()
        if "online" in lowered or "aktif" in lowered:
            active = True
        elif "offline" in lowered or "non aktif" in lowered:
            active = False

    return RegistryRow(
        nama_lpse=name,
        instansi=name,
        kategori_instansi=category,
        provinsi=province,
        kabupaten_kota=kabupaten_kota,
        official_lpse_url=official_url,
        domain=domain,
        https=https,
        aktif=active,
        dapat_diakses=None,
        menggunakan_spse=True,
        versi_spse=version,
        portal_induk="https://eproc.lkpp.go.id",
        tanggal_pengecekan=utc_now_iso(),
        source_url=page_url,
        source_page=detail_url or page_url,
        source_page_number=page_number,
        source_filter_provinsi=filter_province,
        source_note=f"registry card from eProc index; detail_url={detail_url}",
    )


def parse_index_page(html: str, page_url: str, page_number: int, filter_province: str | None) -> list[RegistryRow]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.card.card-small-round")
    rows: list[RegistryRow] = []
    for card in cards:
        row = parse_card(card, page_url, page_number, filter_province)
        if row:
            rows.append(row)
    return rows


def parse_detail_page(html: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str | None] = {}
    for block in soup.select(".col-sm-10"):
        label_el = block.select_one("label.col-form-label.light")
        value_el = block.select_one("p.form-row-content")
        if label_el:
            label = normalize_space(label_el.get_text(" ", strip=True)).upper()
            value = clean_text(value_el.get_text(" ", strip=True) if value_el else None)
            if label in {"PROVINSI", "ALAMAT", "EMAIL", "HELPDESK", "URL", "STATUS SERVER TERAKHIR PADA"}:
                fields[label] = value
    return fields


def probe_official_url(session: requests.Session, url: str | None, timeout: int = 20) -> tuple[bool | None, bool | None]:
    if not url:
        return None, None
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        status = response.status_code
        if status < 400:
            return True, True
        if status < 500:
            return True, False
        return False, False
    except requests.RequestException:
        return False, False


def page_url_for_filter(source_url: str, province_value: str, page_number: int) -> str:
    base = source_url.rstrip("/")
    return f"{base}/{province_value}/0/{page_number}"


def crawl_pages_for_filter(
    session: requests.Session,
    source_url: str,
    province_value: str | None,
    province_label: str | None,
    raw_root: Path,
    delay_seconds: float,
    max_pages: Optional[int],
) -> list[RegistryRow]:
    if province_value:
        start_url = page_url_for_filter(source_url, province_value, 1)
        raw_dir = raw_root / f"province_{province_value}_{slugify(province_label or province_value)}"
    else:
        start_url = source_url
        raw_dir = raw_root / "province_all"

    html, _, resolved = fetch_html(session, start_url)
    if not html:
        return []
    save_raw_text(raw_dir / "page_1.html", html)

    soup = BeautifulSoup(html, "html.parser")
    last_page = detect_last_page(soup)
    if max_pages is not None:
        last_page = min(last_page, max_pages)

    rows: list[RegistryRow] = []
    rows.extend(parse_index_page(html, resolved or start_url, 1, province_label if province_value else None))

    for page_number in range(2, last_page + 1):
        page_url = page_url_for_filter(source_url, province_value or "0", page_number) if province_value else f"{source_url}/0/0/{page_number}"
        page_html, _, page_resolved = fetch_html(session, page_url)
        if not page_html:
            continue
        save_raw_text(raw_dir / f"page_{page_number}.html", page_html)
        rows.extend(parse_index_page(page_html, page_resolved or page_url, page_number, province_label if province_value else None))
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return rows


def crawl_registry(session: requests.Session, source_url: str, raw_dir: Path, delay_seconds: float, max_pages: Optional[int]) -> list[RegistryRow]:
    # Base page captures the default view and the province filter options.
    base_html, _, _ = fetch_html(session, source_url)
    if not base_html:
        raise RuntimeError(f"Unable to fetch registry source: {source_url}")
    save_raw_text(raw_dir / "default_index.html", base_html)

    rows: list[RegistryRow] = []
    rows.extend(parse_index_page(base_html, source_url, 1, None))

    provinces = discover_provinces(base_html)
    for province_value, province_label in provinces:
        rows.extend(
            crawl_pages_for_filter(
                session=session,
                source_url=source_url,
                province_value=province_value,
                province_label=province_label,
                raw_root=raw_dir,
                delay_seconds=delay_seconds,
                max_pages=max_pages,
            )
        )
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    # Deduplicate by detail URL when available, otherwise by name and province.
    seen: set[tuple[str | None, str | None, str | None]] = set()
    unique: list[RegistryRow] = []
    for row in rows:
        key = (row.source_page, row.nama_lpse, row.provinsi)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def enrich_rows_with_detail(session: requests.Session, rows: list[RegistryRow], raw_dir: Path, delay_seconds: float) -> list[RegistryRow]:
    detail_dir = raw_dir / "detail"
    detail_dir.mkdir(parents=True, exist_ok=True)
    enriched: list[RegistryRow] = []

    for row in rows:
        if row.source_page:
            try:
                detail_html, _, _ = fetch_html(session, row.source_page)
                if detail_html:
                    detail_slug = slugify(row.nama_lpse)
                    save_raw_text(detail_dir / f"{detail_slug}.html", detail_html)
                    detail_fields = parse_detail_page(detail_html)
                    if detail_fields.get("PROVINSI"):
                        row.provinsi = detail_fields.get("PROVINSI")
                    if detail_fields.get("URL"):
                        row.official_lpse_url = detail_fields.get("URL")
                        parsed = urlparse(row.official_lpse_url)
                        row.domain = parsed.netloc or row.domain
                        row.https = parsed.scheme.lower() == "https" if parsed.scheme else row.https
                        row.dapat_diakses, _ = probe_official_url(session, row.official_lpse_url)
                    if detail_fields.get("STATUS SERVER TERAKHIR PADA"):
                        row.source_note = f"{row.source_note}; server_status={detail_fields.get('STATUS SERVER TERAKHIR PADA')}"
            except requests.RequestException:
                pass
        enriched.append(row)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return enriched


def rows_to_frame(rows: list[RegistryRow]) -> pd.DataFrame:
    data = [asdict(row) for row in rows]
    df = pd.DataFrame(data)
    if df.empty:
        return df
    columns = [
        "nama_lpse",
        "instansi",
        "kategori_instansi",
        "provinsi",
        "kabupaten_kota",
        "official_lpse_url",
        "domain",
        "https",
        "aktif",
        "dapat_diakses",
        "menggunakan_spse",
        "versi_spse",
        "portal_induk",
        "tanggal_pengecekan",
        "source_url",
        "source_page",
        "source_page_number",
        "source_filter_provinsi",
        "source_note",
    ]
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df[columns]


def build_summary(df: pd.DataFrame, source_url: str, checked_at: str) -> dict:
    def count_value(series: pd.Series, value) -> int:
        return int((series == value).fillna(False).sum())

    versions = sorted({str(v) for v in df.get("versi_spse", pd.Series(dtype=object)).dropna().unique().tolist() if str(v).strip()})
    provinces = {str(k): int(v) for k, v in df.get("provinsi", pd.Series(dtype=object)).fillna("null").value_counts().items()}
    categories = {str(k): int(v) for k, v in df.get("kategori_instansi", pd.Series(dtype=object)).fillna("null").value_counts().items()}

    return {
        "generated_at": checked_at,
        "source_url": source_url,
        "total_lpse": int(len(df)),
        "aktif": count_value(df.get("aktif", pd.Series(dtype=object)), True),
        "tidak_aktif": count_value(df.get("aktif", pd.Series(dtype=object)), False),
        "https": count_value(df.get("https", pd.Series(dtype=object)), True),
        "http": count_value(df.get("https", pd.Series(dtype=object)), False),
        "versi_spse_teridentifikasi": versions,
        "provinsi": provinces,
        "kategori_instansi": categories,
        "dapat_diakses": count_value(df.get("dapat_diakses", pd.Series(dtype=object)), True),
        "tidak_dapat_diakses": count_value(df.get("dapat_diakses", pd.Series(dtype=object)), False),
        "null_fields_note": "Fields set to null were not publicly verifiable from the index/detail pages or the public website probe.",
    }


def compute_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    quality = df.copy()

    def find_province_mention(name: str | None) -> str | None:
        if not name:
            return None
        lowered = name.lower()
        for province in PROVINCE_NAMES_FOR_MATCHING:
            if province.lower() in lowered:
                return province
        return None

    quality["province_mentioned_in_name"] = quality["nama_lpse"].apply(find_province_mention)
    quality["province_mismatch_suspected"] = (
        quality["province_mentioned_in_name"].notna()
        & quality["provinsi"].notna()
        & (quality["province_mentioned_in_name"].astype(str).str.lower() != quality["provinsi"].astype(str).str.lower())
    )
    quality["missing_official_url"] = quality["official_lpse_url"].isna() | (quality["official_lpse_url"].astype(str).str.strip() == "")
    quality["missing_domain"] = quality["domain"].isna() | (quality["domain"].astype(str).str.strip() == "")
    quality["missing_spse_version"] = quality["versi_spse"].isna() | (quality["versi_spse"].astype(str).str.strip() == "")
    quality["inactive_or_inaccessible"] = (quality["aktif"].fillna(False) == False) | (quality["dapat_diakses"].fillna(False) == False)
    quality["quality_flag_count"] = quality[[
        "province_mismatch_suspected",
        "missing_official_url",
        "missing_domain",
        "missing_spse_version",
        "inactive_or_inaccessible",
    ]].sum(axis=1)
    quality["quality_flags"] = quality.apply(
        lambda row: [
            flag for flag, present in [
                ("province_mismatch_suspected", bool(row["province_mismatch_suspected"])),
                ("missing_official_url", bool(row["missing_official_url"])),
                ("missing_domain", bool(row["missing_domain"])),
                ("missing_spse_version", bool(row["missing_spse_version"])),
                ("inactive_or_inaccessible", bool(row["inactive_or_inaccessible"])),
            ] if present
        ],
        axis=1,
    )
    return quality


def build_quality_report(df: pd.DataFrame, source_url: str, checked_at: str) -> tuple[pd.DataFrame, dict]:
    quality = compute_quality_flags(df)
    flag_columns = [
        "province_mismatch_suspected",
        "missing_official_url",
        "missing_domain",
        "missing_spse_version",
        "inactive_or_inaccessible",
    ]
    flag_counts = {column: int(quality[column].fillna(False).sum()) for column in flag_columns}
    rows = quality[quality["quality_flag_count"] > 0].copy()
    report = {
        "generated_at": checked_at,
        "source_url": source_url,
        "total_rows": int(len(quality)),
        "flagged_rows": int(len(rows)),
        "flag_counts": flag_counts,
        "rows": rows.to_dict(orient="records"),
    }
    return quality, report


def write_outputs(df: pd.DataFrame, summary: dict, quality_report: dict, csv_path: Path, json_path: Path, metadata_path: Path, summary_json_path: Path, xlsx_path: Path, quality_json_path: Path, quality_xlsx_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    quality_json_path.parent.mkdir(parents=True, exist_ok=True)
    quality_xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL, encoding="utf-8")
    df.to_json(json_path, orient="records", force_ascii=False, indent=2)
    metadata = build_registry_artifact_metadata(csv_path)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    quality_json_path.write_text(json.dumps(quality_report, ensure_ascii=False, indent=2), encoding="utf-8")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="lpse_registry")
        pd.DataFrame([summary]).to_excel(writer, index=False, sheet_name="summary")
    quality_df = pd.DataFrame(quality_report.get("rows", []))
    with pd.ExcelWriter(quality_xlsx_path, engine="openpyxl") as writer:
        quality_df.to_excel(writer, index=False, sheet_name="quality_rows")
        pd.DataFrame([
            {
                "generated_at": quality_report.get("generated_at"),
                "source_url": quality_report.get("source_url"),
                "total_rows": quality_report.get("total_rows"),
                "flagged_rows": quality_report.get("flagged_rows"),
            }
        ]).to_excel(writer, index=False, sheet_name="summary")
        pd.DataFrame([
            {"flag": k, "count": v} for k, v in quality_report.get("flag_counts", {}).items()
        ]).to_excel(writer, index=False, sheet_name="flag_counts")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the national LPSE registry from official eProc sources.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL, help="Public registry source page.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional maximum number of pages per filter.")
    parser.add_argument("--delay-seconds", type=float, default=0.25, help="Delay between page and detail requests.")
    parser.add_argument("--probe-sites", action="store_true", default=True, help="Probe LPSE website URLs when available.")
    parser.add_argument("--no-probe-sites", dest="probe_sites", action="store_false", help="Skip website URL probing.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR, help="Directory for registry CSV/JSON.")
    parser.add_argument("--summary-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for summary XLSX/JSON.")
    args = parser.parse_args()

    session = build_session()
    checked_at = utc_now_iso()

    cached_csv = args.output_dir / "lpse_registry.csv"
    cached_raw = args.output_dir / "raw" / "default_index.html"

    if cached_csv.exists() and cached_raw.exists():
        df = pd.read_csv(cached_csv)
    else:
        rows = crawl_registry(
            session=session,
            source_url=args.source_url,
            raw_dir=args.output_dir / "raw",
            delay_seconds=args.delay_seconds,
            max_pages=args.max_pages,
        )
        rows = enrich_rows_with_detail(session, rows, args.output_dir / "raw", args.delay_seconds)

        if args.probe_sites:
            for row in rows:
                accessible, actual = probe_official_url(session, row.official_lpse_url)
                if accessible is not None:
                    row.dapat_diakses = actual
                if row.official_lpse_url:
                    parsed = urlparse(row.official_lpse_url)
                    row.https = parsed.scheme.lower() == "https" if parsed.scheme else row.https
                    row.domain = parsed.netloc or row.domain

        df = rows_to_frame(rows)
    summary = build_summary(df, args.source_url, checked_at)
    summary["registry_pages_sampled"] = int(df["source_page_number"].dropna().nunique()) if not df.empty and "source_page_number" in df.columns else 0
    summary["rows_with_official_url"] = int(df["official_lpse_url"].notna().sum()) if not df.empty and "official_lpse_url" in df.columns else 0

    quality_df, quality_report = build_quality_report(df, args.source_url, checked_at)

    # Persist the flagged quality columns back into the registry outputs for auditability.
    df = quality_df

    write_outputs(
        df=df,
        summary=summary,
        quality_report=quality_report,
        csv_path=args.output_dir / "lpse_registry.csv",
        json_path=args.output_dir / "lpse_registry.json",
        metadata_path=args.output_dir / "lpse_registry.metadata.json",
        summary_json_path=args.summary_dir / "lpse_registry_summary.json",
        xlsx_path=args.summary_dir / "lpse_registry_summary.xlsx",
        quality_json_path=args.summary_dir / "lpse_registry_quality_report.json",
        quality_xlsx_path=args.summary_dir / "lpse_registry_quality_report.xlsx",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
