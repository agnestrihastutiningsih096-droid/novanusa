from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import HTTPCookieProcessor, Request, build_opener as urllib_build_opener

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "reference" / "lpse" / "lpse_registry.csv"
DEFAULT_NATIONAL_SAMPLE = ROOT / "data" / "evidence" / "spse" / "nasional" / "parsed" / "spse_national_sample_2026.csv"
RAW_DIR = ROOT / "data" / "evidence" / "lpse" / "raw"
PARSED_DIR = ROOT / "data" / "evidence" / "lpse" / "parsed"
DEFAULT_OUTPUT = ROOT / "outputs" / "evidence" / "lpse_detail_sample_2026.xlsx"
DEFAULT_SUMMARY = ROOT / "outputs" / "evidence" / "lpse_detail_sample_2026_summary.json"
DEFAULT_PARSED = PARSED_DIR / "lpse_detail_sample_2026.csv"

SUPPORTED_SOURCE_TYPES = ("tender", "nontender")
DETAIL_LABELS = {
    "kode_tender": "package_code",
    "kode_paket": "package_code",
    "nama_tender": "package_name",
    "nama_paket": "package_name",
    "k_l_pd_instansi_lainnya": "institution_name",
    "satuan_kerja": "satker",
    "nilai_hps_paket": "hps_or_pagu",
    "nilai_pagu_paket": "hps_or_pagu",
    "tahap_tender_saat_ini": "stage_or_status",
    "tahap_paket_saat_ini": "stage_or_status",
    "metode_pengadaan": "method",
    "tahun_anggaran": "fiscal_year",
    "nama_paket": "package_name",
}
KEYWORD_SECTIONS = {
    "schedule": ("jadwal", "schedule", "tahap"),
    "participants": ("peserta",),
    "winner": ("pemenang", "hasil"),
    "contract": ("kontrak",),
    "document_links": ("dokumen", "lampiran", "download"),
}
OUTPUT_COLUMNS = [
    "lpse_name",
    "lpse_url",
    "source_type",
    "package_code",
    "package_name",
    "institution_name",
    "satker",
    "hps_or_pagu",
    "stage_or_status",
    "method",
    "fiscal_year",
    "detail_url",
    "source_url",
    "collected_at",
    "raw_file_path",
    "evidence_level",
    "schedule",
    "participants",
    "winner",
    "contract",
    "document_links",
    "raw_bundle_json",
]


@dataclass
class ParsedTable:
    headers: list[str]
    rows: list[list[str]]


class HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_stack.append({"table": [], "row": None, "cell": None})
        elif self._table_stack and tag == "tr":
            self._table_stack[-1]["row"] = []
        elif self._table_stack and self._table_stack[-1]["row"] is not None and tag in {"td", "th"}:
            self._table_stack[-1]["cell"] = []

    def handle_data(self, data: str) -> None:
        if self._table_stack and self._table_stack[-1]["cell"] is not None:
            self._table_stack[-1]["cell"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._table_stack:
            return
        state = self._table_stack[-1]
        if tag in {"td", "th"} and state["cell"] is not None:
            state["row"].append(clean(" ".join(state["cell"])))
            state["cell"] = None
        elif tag == "tr" and state["row"] is not None:
            if any(cell for cell in state["row"]):
                state["table"].append(state["row"])
            state["row"] = None
        elif tag == "table":
            state = self._table_stack.pop()
            if state["table"]:
                self.tables.append(state["table"])


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, str]] = []
        self._in_anchor = False
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._in_anchor = True
            self._current_href = ""
            self._current_text = []
            for key, value in attrs:
                if key == "href" and value:
                    self._current_href = value

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            text = clean(" ".join(self._current_text))
            if self._current_href or text:
                self.anchors.append({"href": self._current_href, "text": text})
            self._in_anchor = False
            self._current_href = ""
            self._current_text = []


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "" if text.lower() in {"none", "nan", "null"} else text


def strip_html(value: Any) -> str:
    text = clean(value)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean(text)


def normalize_header(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def safe_filename(value: Any) -> str:
    text = clean(value)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    return text.strip("._-") or "item"


def boolish(value: Any) -> bool:
    text = clean(value).lower()
    return text in {"1", "true", "yes", "y", "aktif", "available", "available public"}


def infer_slug(lpse_url: str) -> str | None:
    parsed = urlparse(lpse_url)
    if parsed.netloc.lower() != "spse.inaproc.id":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    if parts[0] in {"nasional"}:
        return None
    return parts[0]


def base_lpse_url(lpse_url: str) -> str | None:
    slug = infer_slug(lpse_url)
    if slug:
        return f"https://spse.inaproc.id/{slug}"
    return None


def make_opener() -> Any:
    return urllib_build_opener(HTTPCookieProcessor(CookieJar()))


def fetch_html(url: str, timeout: int, opener: Any) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "NovaNusaLPSEDetailCollector/1.0 (+small-sample; audit-friendly)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    started = time.time()
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get("Content-Type", "")
        encoding = response.headers.get_content_charset() or "utf-8"
        status = getattr(response, "status", 200)
    text = body.decode(encoding, errors="replace")
    return text, {
        "http_status": status,
        "content_type": content_type,
        "encoding": encoding,
        "bytes": len(body),
        "elapsed_seconds": round(time.time() - started, 3),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def post_form(url: str, referer: str, form: dict[str, str], timeout: int, opener: Any) -> tuple[str, dict[str, Any]]:
    body = urlencode(form).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "User-Agent": "NovaNusaLPSEDetailCollector/1.0 (+small-sample; audit-friendly)",
            "Accept": "application/json,text/javascript,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://spse.inaproc.id",
            "Referer": referer,
        },
        method="POST",
    )
    started = time.time()
    with opener.open(request, timeout=timeout) as response:
        body_bytes = response.read()
        content_type = response.headers.get("Content-Type", "")
        encoding = response.headers.get_content_charset() or "utf-8"
        status = getattr(response, "status", 200)
    text = body_bytes.decode(encoding, errors="replace")
    return text, {
        "http_status": status,
        "content_type": content_type,
        "encoding": encoding,
        "bytes": len(body_bytes),
        "elapsed_seconds": round(time.time() - started, 3),
        "sha256": hashlib.sha256(body_bytes).hexdigest(),
    }


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def extract_tables(html: str) -> list[ParsedTable]:
    parser = HTMLTableParser()
    parser.feed(html)
    parsed: list[ParsedTable] = []
    for table in parser.tables:
        if not table:
            continue
        headers = [clean(cell) for cell in table[0]]
        rows = table[1:]
        if not headers and not rows:
            continue
        width = max([len(headers)] + [len(row) for row in rows] or [0])
        headers = headers + [f"column_{idx + 1}" for idx in range(len(headers), width)]
        normalized_rows = [row + [""] * (width - len(row)) for row in rows]
        parsed.append(ParsedTable(headers=headers[:width], rows=normalized_rows))
    return parsed


def extract_token_and_url(html: str, page_url: str) -> tuple[str, str] | None:
    url_match = re.search(r"url\s*:\s*[\"']([^\"']*/dt/[^\"']+)[\"']", html)
    token_match = re.search(r"authenticityToken\s*=\s*[\"']([^\"']+)[\"']", html)
    if not url_match or not token_match:
        return None
    return urljoin(page_url, url_match.group(1)), token_match.group(1)


def datatable_form(limit: int, token: str) -> dict[str, str]:
    return {
        "draw": "1",
        "start": "0",
        "length": str(max(1, limit)),
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "authenticityToken": token,
    }


def parse_datatable_rows(payload: str, source_type: str, year: int | None, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parsed = json.loads(payload)
    rows: list[dict[str, Any]] = []
    data = parsed.get("data", [])
    for item in data:
        if not isinstance(item, list):
            continue
        package_code = strip_html(item[0] if len(item) > 0 else "")
        package_name = strip_html(item[1] if len(item) > 1 else "")
        institution_name = strip_html(item[2] if len(item) > 2 else "")
        stage_or_status = strip_html(item[3] if len(item) > 3 else "")
        hps_or_pagu = strip_html(item[4] if len(item) > 4 else "")
        method = strip_html(item[5] if len(item) > 5 else "")
        fiscal_year = str(year) if year else ""
        if package_code or package_name:
            rows.append(
                {
                    "package_code": package_code,
                    "package_name": package_name,
                    "institution_name": institution_name,
                    "stage_or_status": stage_or_status,
                    "hps_or_pagu": hps_or_pagu,
                    "method": method,
                    "fiscal_year": fiscal_year,
                    "source_type": source_type,
                    "evidence_level": "LPSE_PUBLIC_DETAIL_FOUND",
                }
            )
        if len(rows) >= limit:
            break
    return rows, {
        "datatable_records_total": parsed.get("recordsTotal", ""),
        "datatable_records_filtered": parsed.get("recordsFiltered", ""),
        "datatable_rows_received": len(data) if isinstance(data, list) else 0,
    }


def rows_to_pairs(table: ParsedTable) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in table.rows:
        cells = [clean(cell) for cell in row if clean(cell)]
        if len(cells) >= 2:
            if len(cells) == 2:
                pairs.append((cells[0], cells[1]))
            else:
                for idx in range(0, len(cells) - 1, 2):
                    left = cells[idx]
                    right = cells[idx + 1]
                    if left and right:
                        pairs.append((left, right))
    return pairs


def parse_detail_fields(html: str, page_url: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for table in extract_tables(html):
        for label, value in rows_to_pairs(table):
            key = normalize_header(label)
            mapped = DETAIL_LABELS.get(key)
            if mapped and mapped not in fields:
                fields[mapped] = strip_html(value)
    fields.setdefault("package_code", "")
    fields.setdefault("package_name", "")
    fields.setdefault("institution_name", "")
    fields.setdefault("hps_or_pagu", "")
    fields.setdefault("stage_or_status", "")
    fields.setdefault("method", "")
    fields.setdefault("fiscal_year", "")
    fields["detail_page_url"] = page_url
    return fields


def summarize_tables(html: str, max_rows: int = 3) -> str:
    tables = extract_tables(html)
    snippets: list[str] = []
    for table in tables:
        for row in table.rows[:max_rows]:
            cells = [clean(cell) for cell in row if clean(cell)]
            if cells:
                snippets.append(" | ".join(cells))
        if snippets:
            break
    return " || ".join(snippets)


def parse_anchors(html: str) -> list[dict[str, str]]:
    parser = AnchorParser()
    parser.feed(html)
    return parser.anchors


def categorize_links(html: str, page_url: str) -> dict[str, list[str]]:
    anchors = parse_anchors(html)
    categorized: dict[str, list[str]] = {key: [] for key in KEYWORD_SECTIONS}
    seen: set[str] = set()
    for anchor in anchors:
        href = anchor.get("href", "")
        text = clean(anchor.get("text", ""))
        if not href:
            continue
        absolute = urljoin(page_url, href)
        lowered = f"{text} {href}".lower()
        for category, keywords in KEYWORD_SECTIONS.items():
            if any(keyword in lowered for keyword in keywords):
                if absolute not in seen:
                    categorized[category].append(absolute)
                    seen.add(absolute)
                break
    return categorized


def fetch_subpage_snapshot(url: str, opener: Any, timeout: int) -> tuple[str, dict[str, Any]]:
    try:
        html, meta = fetch_html(url, timeout=timeout, opener=opener)
        return html, meta
    except (HTTPError, URLError, TimeoutError) as exc:
        return "", {
            "http_status": getattr(exc, "code", ""),
            "error": f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}",
        }


def select_registry_rows(df: pd.DataFrame, limit_lpse: int) -> list[dict[str, Any]]:
    frame = df.copy()
    frame["official_lpse_url"] = frame["official_lpse_url"].fillna("").astype(str).str.strip()
    if "menggunakan_spse" in frame.columns:
        frame = frame[frame["menggunakan_spse"].apply(boolish)]
    if "dapat_diakses" in frame.columns:
        accessible = frame[frame["dapat_diakses"].apply(boolish)]
        if not accessible.empty:
            frame = accessible
    frame = frame[frame["official_lpse_url"] != ""]
    frame["slug"] = frame["official_lpse_url"].map(infer_slug)
    frame["base_lpse_url"] = frame["official_lpse_url"].map(base_lpse_url)
    frame = frame[frame["slug"].notna()]
    frame = frame.drop_duplicates(subset=["base_lpse_url", "nama_lpse"], keep="first")
    frame = frame.sort_values(["nama_lpse", "official_lpse_url"], kind="stable")
    return frame.head(limit_lpse).to_dict(orient="records")


def collect_package_detail(
    registry_row: dict[str, Any],
    source_type: str,
    package_row: dict[str, Any],
    year: int,
    opener: Any,
    timeout: int,
    sleep_seconds: float,
    collected_at: str,
    source_artifacts: dict[str, Any],
) -> dict[str, Any]:
    lpse_name = clean(registry_row.get("nama_lpse", ""))
    lpse_url = clean(registry_row.get("official_lpse_url", ""))
    base_url = clean(registry_row.get("base_lpse_url", "")) or base_lpse_url(lpse_url) or lpse_url
    slug = clean(registry_row.get("slug", ""))
    package_code = clean(package_row.get("package_code", ""))
    package_name = clean(package_row.get("package_name", ""))
    detail_path = "pengumumanlelang" if source_type == "tender" else "pengumumanpl"
    detail_url = f"{base_url}/{source_type}/{package_code}/{detail_path}"
    package_dir = RAW_DIR / safe_filename(slug or lpse_name) / str(year) / source_type / safe_filename(package_code)
    package_dir.mkdir(parents=True, exist_ok=True)
    raw_detail_path = package_dir / "detail.html"
    raw_schedule_path = package_dir / "schedule.html"
    raw_participants_path = package_dir / "participants.html"
    raw_winner_path = package_dir / "winner.html"
    raw_contract_path = package_dir / "contract.html"
    manifest_path = package_dir / "manifest.json"

    evidence_level = "LPSE_PUBLIC_DETAIL_FOUND"
    detail_fields: dict[str, str] = {}
    subpage_snapshots: dict[str, str] = {"schedule": "", "participants": "", "winner": "", "contract": "", "document_links": ""}
    raw_meta: dict[str, Any] = {
        "lpse_name": lpse_name,
        "lpse_url": lpse_url,
        "base_url": base_url,
        "slug": slug,
        "source_type": source_type,
        "package_code": package_code,
        "package_name": package_name,
        "year": year,
        "collected_at": collected_at,
        "detail_url": detail_url,
        "source_list_url": source_artifacts.get("list_url", ""),
        "source_datatable_url": source_artifacts.get("datatable_url", ""),
        "evidence_level": evidence_level,
    }

    try:
        detail_html, detail_meta = fetch_html(detail_url, timeout=timeout, opener=opener)
        save_text(raw_detail_path, detail_html)
        raw_meta["detail_fetch"] = detail_meta
        detail_fields = parse_detail_fields(detail_html, detail_url)

        links = categorize_links(detail_html, detail_url)
        document_links = links.get("document_links", [])
        if links.get("schedule"):
            schedule_html, schedule_meta = fetch_subpage_snapshot(links["schedule"][0], opener=opener, timeout=timeout)
            raw_meta["schedule_fetch"] = schedule_meta
            if schedule_html:
                save_text(raw_schedule_path, schedule_html)
                subpage_snapshots["schedule"] = summarize_tables(schedule_html) or strip_html(schedule_html[:2000])
        if links.get("participants"):
            participants_html, participants_meta = fetch_subpage_snapshot(links["participants"][0], opener=opener, timeout=timeout)
            raw_meta["participants_fetch"] = participants_meta
            if participants_html:
                save_text(raw_participants_path, participants_html)
                subpage_snapshots["participants"] = summarize_tables(participants_html) or strip_html(participants_html[:2000])
        if links.get("winner"):
            winner_html, winner_meta = fetch_subpage_snapshot(links["winner"][0], opener=opener, timeout=timeout)
            raw_meta["winner_fetch"] = winner_meta
            if winner_html:
                save_text(raw_winner_path, winner_html)
                subpage_snapshots["winner"] = summarize_tables(winner_html) or strip_html(winner_html[:2000])
        if links.get("contract"):
            contract_html, contract_meta = fetch_subpage_snapshot(links["contract"][0], opener=opener, timeout=timeout)
            raw_meta["contract_fetch"] = contract_meta
            if contract_html:
                save_text(raw_contract_path, contract_html)
                subpage_snapshots["contract"] = summarize_tables(contract_html) or strip_html(contract_html[:2000])
        if document_links:
            subpage_snapshots["document_links"] = json.dumps(document_links, ensure_ascii=False)
        raw_meta["document_links"] = document_links
    except HTTPError as exc:
        evidence_level = "LIMITED_PUBLIC_ACCESS"
        raw_meta["error"] = f"HTTPError: {exc.code} {exc.reason}"
    except URLError as exc:
        evidence_level = "LIMITED_PUBLIC_ACCESS"
        raw_meta["error"] = f"URLError: {exc.reason}"
    except TimeoutError as exc:
        evidence_level = "LIMITED_PUBLIC_ACCESS"
        raw_meta["error"] = f"TimeoutError: {exc}"
    except json.JSONDecodeError as exc:
        evidence_level = "LIMITED_PUBLIC_ACCESS"
        raw_meta["error"] = f"JSONDecodeError: {exc}"

    raw_meta["final_evidence_level"] = evidence_level
    save_text(manifest_path, json.dumps(raw_meta, indent=2, ensure_ascii=False))

    raw_bundle = {
        "manifest": str(manifest_path.relative_to(ROOT)),
        "source_list_html": str(source_artifacts.get("list_path", "")),
        "source_datatable_json": str(source_artifacts.get("datatable_path", "")),
        "detail_html": str(raw_detail_path.relative_to(ROOT)) if raw_detail_path.exists() else "",
        "schedule_html": str(raw_schedule_path.relative_to(ROOT)) if raw_schedule_path.exists() else "",
        "participants_html": str(raw_participants_path.relative_to(ROOT)) if raw_participants_path.exists() else "",
        "winner_html": str(raw_winner_path.relative_to(ROOT)) if raw_winner_path.exists() else "",
        "contract_html": str(raw_contract_path.relative_to(ROOT)) if raw_contract_path.exists() else "",
    }
    row = {
        "lpse_name": lpse_name,
        "lpse_url": lpse_url,
        "source_type": source_type,
        "package_code": clean(detail_fields.get("package_code") or package_code),
        "package_name": clean(detail_fields.get("package_name") or package_name),
        "institution_name": clean(detail_fields.get("institution_name") or package_row.get("institution_name", "")),
        "satker": clean(detail_fields.get("satker", "")),
        "hps_or_pagu": clean(detail_fields.get("hps_or_pagu") or package_row.get("hps_or_pagu", "")),
        "stage_or_status": clean(detail_fields.get("stage_or_status") or package_row.get("stage_or_status", "")),
        "method": clean(detail_fields.get("method") or package_row.get("method", "")),
        "fiscal_year": clean(detail_fields.get("fiscal_year") or year),
        "detail_url": detail_url,
        "source_url": source_artifacts.get("list_url", ""),
        "collected_at": collected_at,
        "raw_file_path": str(manifest_path.relative_to(ROOT)),
        "evidence_level": evidence_level,
        "schedule": subpage_snapshots["schedule"],
        "participants": subpage_snapshots["participants"],
        "winner": subpage_snapshots["winner"],
        "contract": subpage_snapshots["contract"],
        "document_links": subpage_snapshots["document_links"],
        "raw_bundle_json": json.dumps(raw_bundle, ensure_ascii=False),
    }
    time.sleep(max(0.0, sleep_seconds))
    return row


def collect(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = pd.read_csv(REGISTRY_PATH)
    if args.national_sample and args.national_sample.exists():
        sample_context = pd.read_csv(args.national_sample)
    else:
        sample_context = pd.DataFrame()
    selected = select_registry_rows(registry, args.limit_lpse)
    opener = make_opener()
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {key: 0 for key in SUPPORTED_SOURCE_TYPES}
    lpse_status: list[dict[str, Any]] = []

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)

    for registry_row in selected:
        if len(rows) >= args.limit_packages:
            break
        base_url = clean(registry_row.get("base_lpse_url", ""))
        slug = clean(registry_row.get("slug", ""))
        lpse_name = clean(registry_row.get("nama_lpse", ""))
        lpse_url = clean(registry_row.get("official_lpse_url", ""))
        if not base_url or not slug:
            lpse_status.append({"lpse_name": lpse_name, "lpse_url": lpse_url, "status": "skipped_unsupported_url"})
            continue

        for source_type in SUPPORTED_SOURCE_TYPES:
            if len(rows) >= args.limit_packages:
                break
            source_dir = RAW_DIR / safe_filename(slug) / str(args.year) / source_type / "_source"
            source_dir.mkdir(parents=True, exist_ok=True)
            list_url = f"{base_url}/{source_type}?tahun={args.year}"
            try:
                list_html, list_meta = fetch_html(list_url, timeout=args.timeout, opener=opener)
                list_path = source_dir / "list.html"
                save_text(list_path, list_html)
                token_and_url = extract_token_and_url(list_html, list_url)
                if not token_and_url:
                    lpse_status.append({"lpse_name": lpse_name, "lpse_url": lpse_url, "source_type": source_type, "status": "no_public_datatable_token"})
                    continue
                datatable_url, token = token_and_url
                payload, datatable_meta = post_form(
                    datatable_url,
                    referer=list_url,
                    form=datatable_form(args.limit_packages, token),
                    timeout=args.timeout,
                    opener=opener,
                )
                datatable_path = source_dir / "datatable.json"
                save_text(datatable_path, payload)
                package_rows, datatable_parse_meta = parse_datatable_rows(payload, source_type=source_type, year=args.year, limit=args.limit_packages)
                source_artifacts = {
                    "list_url": list_url,
                    "datatable_url": datatable_url,
                    "list_path": str(list_path.relative_to(ROOT)),
                    "datatable_path": str(datatable_path.relative_to(ROOT)),
                    "list_fetch": list_meta,
                    "datatable_fetch": datatable_meta,
                    "datatable_parse": datatable_parse_meta,
                }
                collected_any = 0
                for package_row in package_rows:
                    if len(rows) >= args.limit_packages:
                        break
                    row = collect_package_detail(
                        registry_row={**registry_row, "base_lpse_url": base_url, "slug": slug},
                        source_type=source_type,
                        package_row=package_row,
                        year=args.year,
                        opener=opener,
                        timeout=args.timeout,
                        sleep_seconds=args.sleep,
                        collected_at=collected_at,
                        source_artifacts=source_artifacts,
                    )
                    rows.append(row)
                    source_counts[source_type] = source_counts.get(source_type, 0) + 1
                    collected_any += 1
                    if len(rows) >= args.limit_packages:
                        break
                lpse_status.append({
                    "lpse_name": lpse_name,
                    "lpse_url": lpse_url,
                    "source_type": source_type,
                    "status": "collected" if collected_any else "no_rows",
                    "list_fetch": list_meta,
                    "datatable_fetch": datatable_meta,
                    "datatable_parse": datatable_parse_meta,
                })
            except HTTPError as exc:
                lpse_status.append({"lpse_name": lpse_name, "lpse_url": lpse_url, "source_type": source_type, "status": "http_error", "error": f"HTTPError: {exc.code} {exc.reason}"})
            except URLError as exc:
                lpse_status.append({"lpse_name": lpse_name, "lpse_url": lpse_url, "source_type": source_type, "status": "url_error", "error": f"URLError: {exc.reason}"})
            except json.JSONDecodeError as exc:
                lpse_status.append({"lpse_name": lpse_name, "lpse_url": lpse_url, "source_type": source_type, "status": "json_error", "error": f"JSONDecodeError: {exc}"})

    evidence_counts = pd.Series([clean(row.get("evidence_level", "")) for row in rows]).value_counts().to_dict()
    summary = {
        "generated_at": collected_at,
        "year": args.year,
        "limit_lpse": args.limit_lpse,
        "limit_packages": args.limit_packages,
        "sleep_seconds": args.sleep,
        "registry_source": str(REGISTRY_PATH.relative_to(ROOT)),
        "national_sample_source": str(args.national_sample.relative_to(ROOT)) if args.national_sample and args.national_sample.exists() else "",
        "national_sample_rows": int(len(sample_context)) if not sample_context.empty else 0,
        "selected_lpse": len(selected),
        "collected_packages": len(rows),
        "source_type_counts": source_counts,
        "evidence_level_counts": evidence_counts,
        "lpse_status": lpse_status,
    }
    return rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_excel(output: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    detail_df = pd.DataFrame(rows)
    summary_df = pd.DataFrame(
        [
            ["Generated at", summary["generated_at"]],
            ["Year", summary["year"]],
            ["Limit LPSE", summary["limit_lpse"]],
            ["Limit packages", summary["limit_packages"]],
            ["Selected LPSE", summary["selected_lpse"]],
            ["Collected packages", summary["collected_packages"]],
            ["National sample rows", summary["national_sample_rows"]],
        ],
        columns=["metric", "value"],
    )
    source_type_df = pd.DataFrame(
        [{"source_type": key, "count": value} for key, value in summary["source_type_counts"].items()]
    )
    evidence_df = pd.DataFrame(
        [{"evidence_level": key, "count": value} for key, value in summary["evidence_level_counts"].items()]
    )
    methodology = pd.DataFrame(
        [
            ["Purpose", "Collect a small, public LPSE detail sample with provenance for downstream evidence mapping."],
            ["Evidence rule", "Public LPSE detail pages show the package moved beyond planning evidence."],
            ["No scoring", "This collector does not create opportunity score or AI score."],
            ["Access rule", "Do not bypass authentication, login walls, or other access controls."],
        ],
        columns=["item", "value"],
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        detail_df.to_excel(writer, index=False, sheet_name="lpse_detail")
        summary_df.to_excel(writer, index=False, sheet_name="summary")
        source_type_df.to_excel(writer, index=False, sheet_name="source_types")
        evidence_df.to_excel(writer, index=False, sheet_name="evidence_levels")
        methodology.to_excel(writer, index=False, sheet_name="methodology")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a small, audit-friendly LPSE detail evidence sample.")
    parser.add_argument("--year", type=int, default=2026, help="Fiscal year filter, for example 2026.")
    parser.add_argument("--limit-lpse", type=int, default=5, help="Maximum LPSE registry rows to sample.")
    parser.add_argument("--limit-packages", type=int, default=10, help="Maximum package rows to collect.")
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between package-level requests in seconds.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Workbook output path.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY, help="Summary JSON path.")
    parser.add_argument("--parsed-csv", type=Path, default=DEFAULT_PARSED, help="Parsed CSV output path.")
    parser.add_argument(
        "--national-sample",
        type=Path,
        default=DEFAULT_NATIONAL_SAMPLE,
        help="Optional SPSE Nasional sample CSV used only as contextual input if present.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, summary = collect(args)
    write_csv(args.parsed_csv, rows)
    save_text(args.summary, json.dumps(summary, indent=2, ensure_ascii=False))
    write_excel(args.output, rows, summary)
    print(f"parsed rows: {len(rows)}")
    print(f"parsed csv: {args.parsed_csv}")
    print(f"summary: {args.summary}")
    print(f"excel: {args.output}")


if __name__ == "__main__":
    main()

