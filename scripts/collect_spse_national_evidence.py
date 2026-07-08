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
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "evidence" / "spse" / "nasional" / "raw"
PARSED_DIR = ROOT / "data" / "evidence" / "spse" / "nasional" / "parsed"
DEFAULT_OUTPUT = ROOT / "outputs" / "evidence" / "spse_national_sample.xlsx"

SOURCES = {
    "tender": "https://spse.inaproc.id/nasional/lelang",
    "nontender": "https://spse.inaproc.id/nasional/nontender",
    "darurat": "https://spse.inaproc.id/nasional/darurat",
}

OUTPUT_COLUMNS = [
    "source_url",
    "source_type",
    "package_code",
    "package_name",
    "institution_name",
    "stage_or_status",
    "hps_or_pagu",
    "fiscal_year",
    "collected_at",
    "evidence_level",
    "raw_file_path",
]


@dataclass
class ParsedTable:
    headers: list[str]
    rows: list[list[str]]


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return "" if text.lower() in {"none", "nan", "null"} else text


def normalize_header(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def strip_html(value: Any) -> str:
    text = clean(value)
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean(text)


class HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._in_cell:
            self._current_row.append(clean(" ".join(self._current_cell)))
            self._current_cell = []
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_row = False
        elif tag == "table" and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
            self._in_table = False


def add_year_query(url: str, year: int | None) -> str:
    if not year:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("tahun", str(year))
    return urlunparse(parsed._replace(query=urlencode(query)))


def fetch_html(url: str, timeout: int, opener: Any | None = None) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "NovaNusaEvidenceCollector/1.0 (+audit-friendly small sample)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    started = time.time()
    active_opener = opener or build_opener()
    with active_opener.open(request, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get("Content-Type", "")
        encoding = response.headers.get_content_charset() or "utf-8"
    text = body.decode(encoding, errors="replace")
    return text, {
        "http_status": 200,
        "content_type": content_type,
        "encoding": encoding,
        "bytes": len(body),
        "elapsed_seconds": round(time.time() - started, 3),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def post_form(url: str, referer: str, form: dict[str, str], timeout: int, opener: Any | None = None) -> tuple[str, dict[str, Any]]:
    body = urlencode(form).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "User-Agent": "NovaNusaEvidenceCollector/1.0 (+audit-friendly small sample)",
            "Accept": "application/json,text/javascript,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://spse.inaproc.id",
            "Referer": referer,
        },
        method="POST",
    )
    started = time.time()
    active_opener = opener or build_opener()
    with active_opener.open(request, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get("Content-Type", "")
        encoding = response.headers.get_content_charset() or "utf-8"
    text = body.decode(encoding, errors="replace")
    return text, {
        "datatable_http_status": 200,
        "datatable_content_type": content_type,
        "datatable_encoding": encoding,
        "datatable_bytes": len(body),
        "datatable_elapsed_seconds": round(time.time() - started, 3),
        "datatable_sha256": hashlib.sha256(body).hexdigest(),
    }


def save_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def extract_tables(html: str) -> list[ParsedTable]:
    parser = HTMLTableParser()
    parser.feed(html)
    parsed: list[ParsedTable] = []
    for table in parser.tables:
        if len(table) < 2:
            continue
        headers = [clean(cell) for cell in table[0]]
        rows = table[1:]
        width = max(len(headers), *(len(row) for row in rows))
        headers = headers + [f"column_{idx + 1}" for idx in range(len(headers), width)]
        normalized_rows = [row + [""] * (width - len(row)) for row in rows]
        parsed.append(ParsedTable(headers=headers[:width], rows=normalized_rows))
    return parsed


def extract_datatable_config(html: str, page_url: str) -> tuple[str, str] | None:
    url_match = re.search(r"url\s*:\s*[\"']([^\"']*/nasional/dt/[^\"']+)[\"']", html)
    token_match = re.search(r"authenticityToken\s*=\s*[\"']([^\"']+)[\"']", html)
    if not url_match or not token_match:
        return None
    return urljoin(page_url, url_match.group(1)), token_match.group(1)


def datatable_form(limit: int, token: str) -> dict[str, str]:
    form: dict[str, str] = {
        "draw": "1",
        "start": "0",
        "length": str(max(1, limit)),
        "search[value]": "",
        "search[regex]": "false",
        "authenticityToken": token,
        "order[0][column]": "0",
        "order[0][dir]": "desc",
    }
    for idx in range(15):
        form[f"columns[{idx}][data]"] = str(idx)
        form[f"columns[{idx}][name]"] = ""
        form[f"columns[{idx}][searchable]"] = "true"
        form[f"columns[{idx}][orderable]"] = "true"
        form[f"columns[{idx}][search][value]"] = ""
        form[f"columns[{idx}][search][regex]"] = "false"
    return form


def find_column(headers: list[str], candidates: list[str]) -> int | None:
    normalized = [normalize_header(header) for header in headers]
    for candidate in candidates:
        candidate_norm = normalize_header(candidate)
        for idx, header in enumerate(normalized):
            if header == candidate_norm or candidate_norm in header:
                return idx
    return None


def infer_columns(headers: list[str]) -> dict[str, int | None]:
    return {
        "package_code": find_column(headers, ["kode tender", "kode paket", "kode", "id paket", "id tender", "no"]),
        "package_name": find_column(headers, ["nama paket", "nama tender", "paket", "pekerjaan", "nama pekerjaan"]),
        "institution_name": find_column(headers, ["instansi", "k/l/pd", "klpd", "kldi", "satuan kerja", "satker"]),
        "stage_or_status": find_column(headers, ["tahapan", "tahap", "status", "stage"]),
        "hps_or_pagu": find_column(headers, ["hps", "pagu", "nilai hps", "nilai pagu", "nilai"]),
        "fiscal_year": find_column(headers, ["tahun anggaran", "tahun", "ta"]),
    }


def get_cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return clean(row[idx])


def row_to_evidence(
    row: list[str],
    columns: dict[str, int | None],
    source_url: str,
    source_type: str,
    collected_at: str,
    raw_file_path: Path,
    fallback_year: int | None,
) -> dict[str, str]:
    fiscal_year = get_cell(row, columns["fiscal_year"])
    if not fiscal_year and fallback_year and any(str(fallback_year) in cell for cell in row):
        fiscal_year = str(fallback_year)
    return {
        "source_url": source_url,
        "source_type": source_type,
        "package_code": get_cell(row, columns["package_code"]),
        "package_name": get_cell(row, columns["package_name"]),
        "institution_name": get_cell(row, columns["institution_name"]),
        "stage_or_status": get_cell(row, columns["stage_or_status"]),
        "hps_or_pagu": get_cell(row, columns["hps_or_pagu"]),
        "fiscal_year": fiscal_year,
        "collected_at": collected_at,
        "evidence_level": "SPSE_NATIONAL_PROCESS_FOUND",
        "raw_file_path": str(raw_file_path.relative_to(ROOT)),
    }


def parse_source_html(
    html: str,
    source_url: str,
    source_type: str,
    collected_at: str,
    raw_file_path: Path,
    year: int | None,
    limit: int,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    rows: list[dict[str, str]] = []
    table_notes: list[dict[str, Any]] = []
    for table_index, table in enumerate(extract_tables(html), start=1):
        columns = infer_columns(table.headers)
        usable = columns["package_name"] is not None or columns["package_code"] is not None
        table_notes.append(
            {
                "table_index": table_index,
                "headers": table.headers,
                "row_count": len(table.rows),
                "inferred_columns": columns,
                "used_for_evidence": usable,
            }
        )
        if not usable:
            continue
        for raw_row in table.rows:
            evidence = row_to_evidence(raw_row, columns, source_url, source_type, collected_at, raw_file_path, year)
            if year and evidence["fiscal_year"] and str(year) not in evidence["fiscal_year"]:
                continue
            if evidence["package_code"] or evidence["package_name"]:
                rows.append(evidence)
            if len(rows) >= limit:
                return rows, table_notes
    return rows[:limit], table_notes


def parse_datatable_json(
    payload: str,
    source_url: str,
    source_type: str,
    collected_at: str,
    raw_file_path: Path,
    year: int | None,
    limit: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    parsed = json.loads(payload)
    data = parsed.get("data", [])
    rows: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, list):
            continue
        if source_type == "darurat":
            package_code = strip_html(item[0] if len(item) > 0 else "")
            package_name = strip_html(item[1] if len(item) > 1 else "")
            institution_name = strip_html(item[2] if len(item) > 2 else "")
            hps_or_pagu = strip_html(item[3] if len(item) > 3 else "")
            fiscal_year = strip_html(item[4] if len(item) > 4 else "") or (str(year) if year else "")
            stage_or_status = strip_html(item[7] if len(item) > 7 else item[6] if len(item) > 6 else "")
        else:
            package_code = strip_html(item[0] if len(item) > 0 else "")
            package_name = strip_html(item[1] if len(item) > 1 else "")
            institution_name = strip_html(item[2] if len(item) > 2 else "")
            stage_or_status = strip_html(item[3] if len(item) > 3 else "")
            hps_or_pagu = strip_html(item[4] if len(item) > 4 else "")
            fiscal_year = str(year) if year else ""
        if package_code or package_name:
            rows.append(
                {
                    "source_url": source_url,
                    "source_type": source_type,
                    "package_code": package_code,
                    "package_name": package_name,
                    "institution_name": institution_name,
                    "stage_or_status": stage_or_status,
                    "hps_or_pagu": hps_or_pagu,
                    "fiscal_year": fiscal_year,
                    "collected_at": collected_at,
                    "evidence_level": "SPSE_NATIONAL_PROCESS_FOUND",
                    "raw_file_path": str(raw_file_path.relative_to(ROOT)),
                }
            )
        if len(rows) >= limit:
            break
    return rows, {
        "datatable_records_total": parsed.get("recordsTotal", ""),
        "datatable_records_filtered": parsed.get("recordsFiltered", ""),
        "datatable_rows_received": len(data) if isinstance(data, list) else "",
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_excel(output: Path, evidence_rows: list[dict[str, str]], metadata_rows: list[dict[str, Any]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence = pd.DataFrame(evidence_rows, columns=OUTPUT_COLUMNS)
    metadata = pd.DataFrame(metadata_rows)
    methodology = pd.DataFrame(
        [
            ["Purpose", "Collect small SPSE Nasional sample as downstream evidence after SiRUP."],
            ["Evidence rule", "Tender / Non Tender / Darurat found in SPSE means the package moved beyond SiRUP planning."],
            ["No scoring", "This collector does not create opportunity score or AI score."],
            ["Collection mode", "Small, polite, sequential public HTML plus one DataTables request per source."],
        ],
        columns=["item", "value"],
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        evidence.to_excel(writer, index=False, sheet_name="parsed_evidence")
        metadata.to_excel(writer, index=False, sheet_name="metadata")
        methodology.to_excel(writer, index=False, sheet_name="methodology")


def collect(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stamp = collected_at.replace(":", "").replace("+", "Z")
    all_rows: list[dict[str, str]] = []
    metadata_rows: list[dict[str, Any]] = []
    per_source_limit = max(1, (args.limit + len(SOURCES) - 1) // len(SOURCES))

    for source_type, base_url in SOURCES.items():
        source_url = add_year_query(base_url, args.year)
        raw_file = RAW_DIR / f"{stamp}_{source_type}_{args.year or 'all'}.html"
        metadata: dict[str, Any] = {
            "source_type": source_type,
            "source_url": source_url,
            "base_url": base_url,
            "collected_at": collected_at,
            "raw_file_path": str(raw_file.relative_to(ROOT)),
            "collector": "scripts/collect_spse_national_evidence.py",
            "collection_scope": "small_sample",
            "requested_year": args.year or "",
            "requested_limit": args.limit,
            "evidence_rule": "SPSE National tender/non-tender/darurat record is evidence the package moved beyond SiRUP planning.",
            "access_note": "Public official SPSE Nasional page; no authentication or access-control bypass.",
        }
        try:
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            html, fetch_meta = fetch_html(source_url, timeout=args.timeout, opener=opener)
            save_text(raw_file, html)
            rows, table_notes = parse_source_html(
                html=html,
                source_url=source_url,
                source_type=source_type,
                collected_at=collected_at,
                raw_file_path=raw_file,
                year=args.year,
                limit=per_source_limit,
            )
            metadata.update(fetch_meta)
            datatable_config = extract_datatable_config(html, source_url)
            if datatable_config:
                datatable_url, token = datatable_config
                datatable_file = RAW_DIR / f"{stamp}_{source_type}_{args.year or 'all'}_datatable.json"
                metadata["datatable_url"] = datatable_url
                metadata["datatable_raw_file_path"] = str(datatable_file.relative_to(ROOT))
                try:
                    payload, datatable_fetch_meta = post_form(
                        datatable_url,
                        referer=source_url,
                        form=datatable_form(per_source_limit, token),
                        timeout=args.timeout,
                        opener=opener,
                    )
                    save_text(datatable_file, payload)
                    datatable_rows, datatable_parse_meta = parse_datatable_json(
                        payload=payload,
                        source_url=datatable_url,
                        source_type=source_type,
                        collected_at=collected_at,
                        raw_file_path=datatable_file,
                        year=args.year,
                        limit=per_source_limit,
                    )
                    if datatable_rows:
                        rows = datatable_rows
                    metadata.update(datatable_fetch_meta)
                    metadata.update(datatable_parse_meta)
                except HTTPError as exc:
                    metadata["datatable_http_status"] = exc.code
                    metadata["datatable_parse_status"] = "datatable_fetch_failed"
                    metadata["datatable_error"] = f"HTTPError: {exc.reason}"
                except URLError as exc:
                    metadata["datatable_parse_status"] = "datatable_fetch_failed"
                    metadata["datatable_error"] = f"URLError: {exc.reason}"
                except json.JSONDecodeError as exc:
                    metadata["datatable_parse_status"] = "datatable_parse_failed"
                    metadata["datatable_error"] = f"JSONDecodeError: {exc}"
            metadata["parse_status"] = "parsed"
            metadata["parsed_rows"] = len(rows)
            metadata["tables_found"] = len(table_notes)
            metadata["table_notes_json"] = json.dumps(table_notes, ensure_ascii=False)
            all_rows.extend(rows)
        except HTTPError as exc:
            metadata["http_status"] = exc.code
            metadata["parse_status"] = "fetch_failed"
            metadata["error"] = f"HTTPError: {exc.reason}"
        except URLError as exc:
            metadata["parse_status"] = "fetch_failed"
            metadata["error"] = f"URLError: {exc.reason}"
        except TimeoutError as exc:
            metadata["parse_status"] = "fetch_failed"
            metadata["error"] = f"TimeoutError: {exc}"
        except json.JSONDecodeError as exc:
            metadata["parse_status"] = "datatable_parse_failed"
            metadata["error"] = f"JSONDecodeError: {exc}"
        metadata_rows.append(metadata)
        time.sleep(max(0.0, args.delay))

    return all_rows[: args.limit], metadata_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect a small SPSE Nasional evidence sample and preserve raw HTML plus parsed CSV/XLSX outputs."
    )
    parser.add_argument("--year", type=int, default=None, help="Fiscal year hint/filter, for example 2026.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum total parsed evidence rows to keep.")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between official source requests in seconds.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Excel output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, metadata = collect(args)
    parsed_csv = PARSED_DIR / f"spse_national_sample_{args.year or 'all'}.csv"
    metadata_json = PARSED_DIR / f"spse_national_sample_{args.year or 'all'}_metadata.json"
    write_csv(parsed_csv, rows)
    save_text(metadata_json, json.dumps(metadata, indent=2, ensure_ascii=False))
    write_excel(args.output, rows, metadata)
    print(f"parsed rows: {len(rows)}")
    print(f"parsed csv: {parsed_csv}")
    print(f"metadata: {metadata_json}")
    print(f"excel: {args.output}")


if __name__ == "__main__":
    main()





