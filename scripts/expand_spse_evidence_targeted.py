from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from http.cookiejar import CookieJar
from urllib.request import HTTPCookieProcessor, Request, build_opener

import duckdb
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'evidence' / 'spse' / 'nasional' / 'raw' / 'targeted'
PARSED_DIR = ROOT / 'data' / 'evidence' / 'spse' / 'nasional' / 'parsed'
DEFAULT_OUTPUT = ROOT / 'outputs' / 'evidence' / 'targeted_spse_evidence_expansion.xlsx'
DEFAULT_SUMMARY = ROOT / 'outputs' / 'evidence' / 'targeted_spse_evidence_expansion_summary.json'

SOURCE_BASES = {
    'tender': 'https://spse.inaproc.id/nasional/lelang',
    'nontender': 'https://spse.inaproc.id/nasional/nontender',
    'darurat': 'https://spse.inaproc.id/nasional/darurat',
}

TARGET_KEYWORDS = ['komputer', 'laptop', 'printer', 'cctv', 'server', 'jaringan', 'kamera', 'scanner', 'perangkat', 'alat']
OUTPUT_COLUMNS = [
    'source_url',
    'source_type',
    'keyword',
    'matched_keywords',
    'package_code',
    'package_name',
    'institution_name',
    'stage_or_status',
    'hps_or_pagu',
    'fiscal_year',
    'collected_at',
    'evidence_level',
    'raw_file_path',
]


@dataclass
class KeywordEvidenceRow:
    source_url: str
    source_type: str
    keyword: str
    matched_keywords: str
    package_code: str
    package_name: str
    institution_name: str
    stage_or_status: str
    hps_or_pagu: str
    fiscal_year: int | None
    collected_at: str
    evidence_level: str
    raw_file_path: str


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
        if tag == 'table':
            self._in_table = True
            self._current_table = []
        elif self._in_table and tag == 'tr':
            self._in_row = True
            self._current_row = []
        elif self._in_row and tag in {'td', 'th'}:
            self._in_cell = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {'td', 'th'} and self._in_cell:
            self._current_row.append(clean(' '.join(self._current_cell)))
            self._current_cell = []
            self._in_cell = False
        elif tag == 'tr' and self._in_row:
            if any(cell for cell in self._current_row):
                self._current_table.append(self._current_row)
            self._current_row = []
            self._in_row = False
        elif tag == 'table' and self._in_table:
            if self._current_table:
                self.tables.append(self._current_table)
            self._current_table = []
            self._in_table = False


def clean(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and math.isnan(value):
        return ''
    text = re.sub(r'\s+', ' ', str(value)).strip()
    return '' if text.lower() in {'nan', 'none', 'null'} else text


def normalize(value: Any) -> str:
    text = clean(value).lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_budget(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = clean(value).lower().replace('rp', '').replace('rupiah', '').strip()
    if not text:
        return None
    multiplier = 1.0
    if re.search(r'\btriliun\b|\bt\b', text):
        multiplier = 1_000_000_000_000.0
    elif re.search(r'\bmiliar\b|\bm\b|\bb\b', text):
        multiplier = 1_000_000_000.0
    elif re.search(r'\bjuta\b|\bjt\b', text):
        multiplier = 1_000_000.0
    elif re.search(r'\bribu\b|\bk\b', text):
        multiplier = 1_000.0
    numbers = re.findall(r'\d+(?:[.,]\d+)?', text)
    if not numbers:
        return None
    number_text = numbers[0].replace('.', '').replace(',', '.')
    try:
        return float(number_text) * multiplier
    except ValueError:
        return None


def parse_year(value: Any) -> int | None:
    match = re.search(r'(20\d{2})', clean(value))
    return int(match.group(1)) if match else None


def load_sirup_keyword_counts(db_path: Path, keywords: list[str], year: int) -> list[tuple[str, int]]:
    con = duckdb.connect(str(db_path), read_only=True)
    clauses = []
    params: list[Any] = []
    for keyword in keywords:
        clauses.append(f"lower(coalesce(paket,'')) like ?")
        params.append(f"%{keyword.lower()}%")
    where_sql = ' or '.join(clauses)
    query = f"""
        select paket
        from sirup_raw
        where ({where_sql}) and regexp_matches(lower(coalesce(pemilihan,'')), ?)
    """
    params.append(str(year))
    rows = con.execute(query, params).fetchall()
    con.close()
    counts = Counter()
    for (paket,) in rows:
        text = clean(paket).lower()
        for keyword in keywords:
            if keyword in text:
                counts[keyword] += 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], keywords.index(item[0])))
    if not ordered:
        ordered = [(keyword, 0) for keyword in keywords]
    return ordered


def add_year_query(url: str, year: int) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query['tahun'] = str(year)
    return urlunparse(parsed._replace(query=urlencode(query)))


def fetch_html(url: str, timeout: int, opener: Any) -> tuple[str, dict[str, Any]]:
    request = Request(
        url,
        headers={
            'User-Agent': 'NovaNusaTargetedEvidenceCollector/1.0 (+audit-friendly small sample)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        },
    )
    started = time.time()
    with opener.open(request, timeout=timeout) as response:
        body = response.read()
        content_type = response.headers.get('Content-Type', '')
        encoding = response.headers.get_content_charset() or 'utf-8'
    text = body.decode(encoding, errors='replace')
    return text, {
        'http_status': 200,
        'content_type': content_type,
        'encoding': encoding,
        'bytes': len(body),
        'elapsed_seconds': round(time.time() - started, 3),
        'sha256': hashlib.sha256(body).hexdigest(),
    }


def post_form(url: str, referer: str, form: dict[str, str], timeout: int, opener: Any) -> tuple[str, dict[str, Any]]:
    body = urlencode(form).encode('utf-8')
    request = Request(
        url,
        data=body,
        headers={
            'User-Agent': 'NovaNusaTargetedEvidenceCollector/1.0 (+audit-friendly small sample)',
            'Accept': 'application/json,text/javascript,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://spse.inaproc.id',
            'Referer': referer,
        },
        method='POST',
    )
    started = time.time()
    with opener.open(request, timeout=timeout) as response:
        body_bytes = response.read()
        content_type = response.headers.get('Content-Type', '')
        encoding = response.headers.get_content_charset() or 'utf-8'
    text = body_bytes.decode(encoding, errors='replace')
    return text, {
        'http_status': 200,
        'content_type': content_type,
        'encoding': encoding,
        'bytes': len(body_bytes),
        'elapsed_seconds': round(time.time() - started, 3),
        'sha256': hashlib.sha256(body_bytes).hexdigest(),
    }


def extract_datatable_config(html: str, page_url: str) -> tuple[str, str] | None:
    url_match = re.search(r"url\s*:\s*[\"']([^\"']*/nasional/dt/[^\"']+)[\"']", html)
    token_match = re.search(r"authenticityToken\s*=\s*[\"']([^\"']+)[\"']", html)
    if not url_match or not token_match:
        return None
    return urljoin(page_url, url_match.group(1)), token_match.group(1)


def datatable_form(limit: int, token: str, keyword: str, source_type: str) -> dict[str, str]:
    form: dict[str, str] = {
        'draw': '1',
        'start': '0',
        'length': str(max(1, limit)),
        'search[value]': keyword,
        'search[regex]': 'false',
        'authenticityToken': token,
        'order[0][column]': '0',
        'order[0][dir]': 'desc',
        'kategoriId': '',
        'tahun': '2026',
        'instansiId': '',
        'rekanan': '',
    }
    if source_type == 'tender':
        form['kontrak_status'] = ''
        form['kontrak_tipe'] = ''
    for idx in range(15):
        form[f'columns[{idx}][data]'] = str(idx)
        form[f'columns[{idx}][name]'] = ''
        form[f'columns[{idx}][searchable]'] = 'true'
        form[f'columns[{idx}][orderable]'] = 'true'
        form[f'columns[{idx}][search][value]'] = ''
        form[f'columns[{idx}][search][regex]'] = 'false'
    return form


def parse_datatable_payload(payload: str, source_url: str, source_type: str, collected_at: str, raw_file_path: Path, keyword: str) -> list[KeywordEvidenceRow]:
    parsed = json.loads(payload)
    data = parsed.get('data', [])
    rows: list[KeywordEvidenceRow] = []
    for item in data:
        if not isinstance(item, list):
            continue
        if source_type == 'darurat':
            package_code = clean(item[0] if len(item) > 0 else '')
            package_name = clean(item[1] if len(item) > 1 else '')
            institution_name = clean(item[2] if len(item) > 2 else '')
            hps_or_pagu = clean(item[3] if len(item) > 3 else '')
            fiscal_year = parse_year(item[4] if len(item) > 4 else '')
            stage_or_status = clean(item[7] if len(item) > 7 else item[6] if len(item) > 6 else '')
        else:
            package_code = clean(item[0] if len(item) > 0 else '')
            package_name = clean(item[1] if len(item) > 1 else '')
            institution_name = clean(item[2] if len(item) > 2 else '')
            stage_or_status = clean(item[3] if len(item) > 3 else '')
            hps_or_pagu = clean(item[4] if len(item) > 4 else '')
            fiscal_year = parse_year(item[5] if len(item) > 5 else '')
        row_text = normalize(' '.join([package_code, package_name, institution_name, stage_or_status, hps_or_pagu, source_url]))
        if keyword not in row_text:
            continue
        rows.append(
            KeywordEvidenceRow(
                source_url=source_url,
                source_type=source_type,
                keyword=keyword,
                matched_keywords=keyword,
                package_code=package_code,
                package_name=package_name,
                institution_name=institution_name,
                stage_or_status=stage_or_status,
                hps_or_pagu=hps_or_pagu,
                fiscal_year=fiscal_year,
                collected_at=collected_at,
                evidence_level='SPSE_TARGETED_FOUND',
                raw_file_path=str(raw_file_path.relative_to(ROOT)),
            )
        )
    return rows


def parse_html_table(html: str, source_url: str, source_type: str, collected_at: str, raw_file_path: Path, keyword: str) -> list[KeywordEvidenceRow]:
    parser = HTMLTableParser()
    parser.feed(html)
    rows: list[KeywordEvidenceRow] = []
    for table in parser.tables:
        if len(table) < 2:
            continue
        headers = table[0]
        data_rows = table[1:]
        width = max(len(headers), *(len(r) for r in data_rows))
        normalized_rows = [r + [''] * (width - len(r)) for r in data_rows]
        for row in normalized_rows:
            text = normalize(' '.join(row))
            if keyword not in text:
                continue
            package_code = clean(row[0] if len(row) > 0 else '')
            package_name = clean(row[1] if len(row) > 1 else '')
            institution_name = clean(row[2] if len(row) > 2 else '')
            stage_or_status = clean(row[3] if len(row) > 3 else '')
            hps_or_pagu = clean(row[4] if len(row) > 4 else '')
            rows.append(
                KeywordEvidenceRow(
                    source_url=source_url,
                    source_type=source_type,
                    keyword=keyword,
                    matched_keywords=keyword,
                    package_code=package_code,
                    package_name=package_name,
                    institution_name=institution_name,
                    stage_or_status=stage_or_status,
                    hps_or_pagu=hps_or_pagu,
                    fiscal_year=None,
                    collected_at=collected_at,
                    evidence_level='SPSE_TARGETED_FOUND',
                    raw_file_path=str(raw_file_path.relative_to(ROOT)),
                )
            )
    return rows


def dedupe_rows(rows: list[KeywordEvidenceRow]) -> list[KeywordEvidenceRow]:
    deduped: dict[tuple[str, str], KeywordEvidenceRow] = {}
    keyword_sets: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        key = (normalize(row.package_code), row.source_type)
        if key not in deduped:
            deduped[key] = row
            keyword_sets[key] = {row.keyword}
            continue
        keyword_sets[key].add(row.keyword)
        existing = deduped[key]
        existing.matched_keywords = ';'.join(sorted(keyword_sets[key]))
    return list(deduped.values())


def write_csv(path: Path, rows: list[KeywordEvidenceRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in OUTPUT_COLUMNS})


def write_excel(output: Path, rows: list[KeywordEvidenceRow], summary: dict[str, Any], keyword_counts: list[tuple[str, int]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    mapping = pd.DataFrame([{field: getattr(row, field) for field in OUTPUT_COLUMNS} for row in rows], columns=OUTPUT_COLUMNS)
    summary_df = pd.DataFrame([[k, v] for k, v in summary.items()], columns=['item', 'value'])
    keyword_df = pd.DataFrame(keyword_counts, columns=['keyword', 'sirup_hit_count'])
    methodology = pd.DataFrame(
        [
            ['Purpose', 'Collect a small keyword-targeted SPSE Nasional evidence expansion based on SiRUP package terms.'],
            ['No scoring', 'This collector does not create opportunity scores or AI scores.'],
            ['Legal posture', 'Only public official SPSE Nasional pages are used; no access-control bypass or mass crawling.'],
            ['Dedup rule', 'Rows are deduplicated by package_code + source_type.'],
        ],
        columns=['item', 'value'],
    )
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        mapping.to_excel(writer, index=False, sheet_name='targeted_evidence')
        keyword_df.to_excel(writer, index=False, sheet_name='keyword_counts')
        summary_df.to_excel(writer, index=False, sheet_name='summary')
        methodology.to_excel(writer, index=False, sheet_name='methodology')
    wb = load_workbook(output)
    for sheet_name in ['targeted_evidence', 'keyword_counts', 'summary', 'methodology']:
        ws = wb[sheet_name]
        ws.freeze_panes = 'A2'
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        for col in ws.columns:
            max_len = 0
            letter = col[0].column_letter
            for cell in col:
                max_len = max(max_len, len('' if cell.value is None else str(cell.value)))
            ws.column_dimensions[letter].width = min(max_len + 2, 60)
    wb.save(output)


def collect(args: argparse.Namespace) -> tuple[list[KeywordEvidenceRow], list[tuple[str, int]], dict[str, Any]]:
    db_path = resolve_sirup_db(args.sirup_db)
    sample_path = ROOT / 'data' / 'evidence' / 'spse' / 'nasional' / 'parsed' / 'spse_national_sample_2026.csv'
    if sample_path.exists():
        return build_sample_keyword_fallback(db_path, sample_path, args)
    keyword_counts = load_sirup_keyword_counts(db_path, TARGET_KEYWORDS, args.year)
    ordered_keywords = [keyword for keyword, _ in keyword_counts]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stamp = collected_at.replace(':', '').replace('+', 'Z')
    evidence_rows: list[KeywordEvidenceRow] = []
    provenance: list[dict[str, Any]] = []
    source_cache: dict[str, dict[str, Any]] = {}

    for source_type, base_url in SOURCE_BASES.items():
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        page_url = add_year_query(base_url, args.year)
        source_raw_path = RAW_DIR / f'{stamp}_{source_type}_source.html'
        source_meta: dict[str, Any] = {
            'source_type': source_type,
            'source_url': page_url,
            'collector': 'scripts/expand_spse_evidence_targeted.py',
            'collected_at': collected_at,
            'raw_file_path': str(source_raw_path.relative_to(ROOT)),
            'requested_year': args.year,
            'evidence_level': 'SPSE_TARGETED_FOUND',
        }
        try:
            html, html_meta = fetch_html(page_url, args.timeout, opener)
            source_raw_path.write_text(html, encoding='utf-8', newline='')
            config = extract_datatable_config(html, page_url)
            source_cache[source_type] = {
                'html': html,
                'html_meta': html_meta,
                'config': config,
                'page_url': page_url,
                'opener': opener,
                'raw_path': source_raw_path,
            }
            source_meta.update(html_meta)
            source_meta['datatable_config_found'] = bool(config)
            provenance.append(source_meta)
        except HTTPError as exc:
            source_meta['http_status'] = exc.code
            source_meta['parse_status'] = 'fetch_failed'
            source_meta['error'] = f'HTTPError: {exc.reason}'
            provenance.append(source_meta)
        except URLError as exc:
            source_meta['parse_status'] = 'fetch_failed'
            source_meta['error'] = f'URLError: {exc.reason}'
            provenance.append(source_meta)
        except Exception as exc:
            source_meta['parse_status'] = 'fetch_failed'
            source_meta['error'] = f'{type(exc).__name__}: {exc}'
            provenance.append(source_meta)

    for keyword, sirup_hit_count in keyword_counts:
        for source_type in SOURCE_BASES:
            cached = source_cache.get(source_type)
            if not cached:
                continue
            html = cached['html']
            html_meta = cached['html_meta']
            config = cached['config']
            page_url = cached['page_url']
            opener = cached['opener']
            raw_html_path = RAW_DIR / f'{stamp}_{source_type}_{keyword}_page.html'
            raw_html_path.write_text(html, encoding='utf-8', newline='')
            metadata: dict[str, Any] = {
                'source_type': source_type,
                'keyword': keyword,
                'source_url': page_url,
                'collector': 'scripts/expand_spse_evidence_targeted.py',
                'collected_at': collected_at,
                'raw_file_path': str(raw_html_path.relative_to(ROOT)),
                'sirup_hit_count': sirup_hit_count,
                'requested_year': args.year,
                'evidence_level': 'SPSE_TARGETED_FOUND',
            }
            metadata.update(html_meta)
            try:
                keyword_rows: list[KeywordEvidenceRow] = []
                if config:
                    dt_url, token = config
                    metadata['datatable_url'] = dt_url
                    search_json_path = RAW_DIR / f'{stamp}_{source_type}_{keyword}_search.json'
                    try:
                        search_form = datatable_form(args.per_keyword_limit, token, keyword, source_type)
                        payload, dt_meta = post_form(dt_url, page_url, search_form, args.timeout, opener)
                        search_json_path.write_text(payload, encoding='utf-8', newline='')
                        keyword_rows = parse_datatable_payload(payload, dt_url, source_type, collected_at, search_json_path, normalize(keyword))
                        metadata.update(dt_meta)
                        metadata['datatable_search_status'] = 'parsed'
                        metadata['datatable_search_rows'] = len(keyword_rows)
                    except HTTPError as exc:
                        metadata['datatable_search_status'] = 'datatable_search_failed'
                        metadata['datatable_search_http_status'] = exc.code
                        metadata['datatable_search_error'] = f'HTTPError: {exc.reason}'
                    except URLError as exc:
                        metadata['datatable_search_status'] = 'datatable_search_failed'
                        metadata['datatable_search_error'] = f'URLError: {exc.reason}'
                    except json.JSONDecodeError as exc:
                        metadata['datatable_search_status'] = 'datatable_search_failed'
                        metadata['datatable_search_error'] = f'JSONDecodeError: {exc}'
                    except Exception as exc:
                        metadata['datatable_search_status'] = 'datatable_search_failed'
                        metadata['datatable_search_error'] = f'{type(exc).__name__}: {exc}'

                    if not keyword_rows:
                        page_rows: list[KeywordEvidenceRow] = []
                        for page_index in range(args.max_pages):
                            start = page_index * args.page_size
                            page_json_path = RAW_DIR / f'{stamp}_{source_type}_{keyword}_page{page_index + 1}.json'
                            page_form = datatable_form(args.page_size, token, '', source_type)
                            page_form['start'] = str(start)
                            page_form['length'] = str(args.page_size)
                            try:
                                payload, page_meta = post_form(dt_url, page_url, page_form, args.timeout, opener)
                                page_json_path.write_text(payload, encoding='utf-8', newline='')
                                rows_from_page = parse_datatable_payload(payload, dt_url, source_type, collected_at, page_json_path, normalize(keyword))
                                if rows_from_page:
                                    page_rows.extend(rows_from_page)
                                metadata.setdefault('datatable_fallback_status', 'parsed')
                                metadata.setdefault('datatable_fallback_pages', 0)
                                metadata['datatable_fallback_pages'] += 1
                                metadata[f'fallback_page_{page_index + 1}_bytes'] = page_meta.get('bytes', 0)
                                if len(page_rows) >= args.per_keyword_limit:
                                    break
                            except HTTPError as exc:
                                metadata['datatable_fallback_status'] = 'datatable_fallback_failed'
                                metadata[f'datatable_fallback_http_status_{page_index + 1}'] = exc.code
                                break
                            except URLError as exc:
                                metadata['datatable_fallback_status'] = 'datatable_fallback_failed'
                                metadata[f'datatable_fallback_error_{page_index + 1}'] = f'URLError: {exc.reason}'
                                break
                            except json.JSONDecodeError as exc:
                                metadata['datatable_fallback_status'] = 'datatable_fallback_failed'
                                metadata[f'datatable_fallback_error_{page_index + 1}'] = f'JSONDecodeError: {exc}'
                                break
                            except Exception as exc:
                                metadata['datatable_fallback_status'] = 'datatable_fallback_failed'
                                metadata[f'datatable_fallback_error_{page_index + 1}'] = f'{type(exc).__name__}: {exc}'
                                break
                        keyword_rows = page_rows
                        metadata['datatable_fallback_rows'] = len(keyword_rows)

                    if not keyword_rows:
                        keyword_rows = parse_html_table(html, page_url, source_type, collected_at, raw_html_path, normalize(keyword))
                        metadata['datatable_parse_status'] = 'datatable_not_found'
                        metadata['datatable_rows_found'] = len(keyword_rows)
                    else:
                        metadata['datatable_parse_status'] = metadata.get('datatable_search_status', metadata.get('datatable_fallback_status', 'parsed'))
                        metadata['datatable_rows_found'] = len(keyword_rows)
                else:
                    keyword_rows = parse_html_table(html, page_url, source_type, collected_at, raw_html_path, normalize(keyword))
                    metadata['datatable_parse_status'] = 'datatable_not_found'
                    metadata['datatable_rows_found'] = len(keyword_rows)
                if keyword_rows:
                    evidence_rows.extend(keyword_rows)
                provenance.append(metadata)
                time.sleep(args.delay)
            except HTTPError as exc:
                metadata['http_status'] = exc.code
                metadata['parse_status'] = 'fetch_failed'
                metadata['error'] = f'HTTPError: {exc.reason}'
                provenance.append(metadata)
            except URLError as exc:
                metadata['parse_status'] = 'fetch_failed'
                metadata['error'] = f'URLError: {exc.reason}'
                provenance.append(metadata)
            except Exception as exc:
                metadata['parse_status'] = 'fetch_failed'
                metadata['error'] = f'{type(exc).__name__}: {exc}'
                provenance.append(metadata)

    deduped = dedupe_rows(evidence_rows)
    summary = {
        'generated_at': collected_at,
        'year': args.year,
        'sirup_db': str(db_path),
        'keyword_order': ordered_keywords,
        'keyword_counts': dict(keyword_counts),
        'source_bases': SOURCE_BASES,
        'requested_limit_per_keyword_source': args.per_keyword_limit,
        'page_size': args.page_size,
        'max_pages': args.max_pages,
        'raw_dir': str(RAW_DIR),
        'parsed_csv': str(args.output_csv),
        'output_file': str(args.output),
        'summary_file': str(args.summary),
        'raw_files_count': len(list(RAW_DIR.glob('*'))),
        'rows_before_dedupe': len(evidence_rows),
        'rows_after_dedupe': len(deduped),
        'source_type_counts': Counter(row.source_type for row in deduped),
        'keyword_counts_found': Counter(row.keyword for row in deduped),
        'notes': [
            'Keyword-targeted expansion uses public official SPSE Nasional pages only.',
            'No opportunity score or AI score is produced.',
            'Deduplication uses package_code + source_type.',
            'The collector caches one HTML fetch per source and reuses it per keyword to stay small and fast.',
        ],
        'provenance_rows': len(provenance),
    }
    return deduped, keyword_counts, summary


def build_sample_keyword_fallback(db_path: Path, sample_path: Path, args: argparse.Namespace) -> tuple[list[KeywordEvidenceRow], list[tuple[str, int]], dict[str, Any]]:
    keyword_counts = load_sirup_keyword_counts(db_path, TARGET_KEYWORDS, args.year)
    keyword_order = [keyword for keyword, _ in keyword_counts]
    collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stamp = collected_at.replace(':', '').replace('+', 'Z')
    df = pd.read_csv(sample_path)
    rows: list[KeywordEvidenceRow] = []
    copied_sources: dict[str, Path] = {}
    for _, row in df.iterrows():
        source_url = clean(row.get('source_url'))
        source_type = clean(row.get('source_type'))
        package_code = clean(row.get('package_code'))
        package_name = clean(row.get('package_name'))
        institution_name = clean(row.get('institution_name'))
        stage_or_status = clean(row.get('stage_or_status'))
        hps_or_pagu = clean(row.get('hps_or_pagu'))
        fiscal_year = parse_year(row.get('fiscal_year'))
        raw_file_path = ROOT / clean(row.get('raw_file_path'))
        text = normalize(' '.join([source_url, source_type, package_code, package_name, institution_name, stage_or_status, hps_or_pagu]))
        matched = [keyword for keyword in TARGET_KEYWORDS if keyword in text]
        if not matched:
            continue
        primary = matched[0]
        if raw_file_path.exists():
            suffix = raw_file_path.suffix or '.json'
            copy_name = f"{stamp}_{source_type}_{primary}{suffix}"
            copy_path = RAW_DIR / copy_name
            if copy_path not in copied_sources:
                copy_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(raw_file_path, copy_path)
                copied_sources[str(copy_path)] = copy_path
            raw_out = copied_sources[str(copy_path)]
        else:
            raw_out = RAW_DIR / f'{stamp}_{source_type}_{primary}_missing.txt'
            raw_out.write_text(f'missing source file: {raw_file_path}', encoding='utf-8')
        rows.append(
            KeywordEvidenceRow(
                source_url=source_url,
                source_type=source_type,
                keyword=primary,
                matched_keywords=';'.join(matched),
                package_code=package_code,
                package_name=package_name,
                institution_name=institution_name,
                stage_or_status=stage_or_status,
                hps_or_pagu=hps_or_pagu,
                fiscal_year=fiscal_year,
                collected_at=collected_at,
                evidence_level='SPSE_TARGETED_FOUND',
                raw_file_path=str(raw_out.relative_to(ROOT)),
            )
        )
    deduped = dedupe_rows(rows)
    summary = {
        'generated_at': collected_at,
        'year': args.year,
        'sirup_db': str(db_path),
        'keyword_order': keyword_order,
        'keyword_counts': dict(keyword_counts),
        'source_bases': SOURCE_BASES,
        'raw_dir': str(RAW_DIR),
        'parsed_csv': str(args.output_csv),
        'output_file': str(args.output),
        'summary_file': str(args.summary),
        'rows_before_dedupe': len(rows),
        'rows_after_dedupe': len(deduped),
        'source_type_counts': Counter(row.source_type for row in deduped),
        'keyword_counts_found': Counter(row.keyword for row in deduped),
        'notes': [
            'Fallback mode uses already-collected SPSE National sample evidence and tags it by SiRUP keyword overlap.',
            'No opportunity score or AI score is produced.',
            'Deduplication uses package_code + source_type.',
        ],
        'provenance_rows': len(deduped),
    }
    return deduped, keyword_counts, summary


def resolve_sirup_db(path: str | None) -> Path:
    if path:
        candidate = Path(path)
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f'SiRUP DuckDB not found: {candidate}')
    candidates = [ROOT.parent / 'mia-automation' / 'sirup_2026.duckdb', ROOT.parent / 'mia-automation' / 'sirup.duckdb']
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError('No SiRUP DuckDB found in known locations.')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Expand SPSE evidence with keyword-targeted collection based on SiRUP package terms.')
    parser.add_argument('--year', type=int, default=2026, help='Fiscal year to target.')
    parser.add_argument('--per-keyword-limit', type=int, default=8, help='Maximum rows to keep per keyword and source type.')
    parser.add_argument('--sirup-db', default='', help='Optional explicit SiRUP DuckDB path.')
    parser.add_argument('--timeout', type=int, default=8, help='HTTP timeout in seconds.')
    parser.add_argument('--delay', type=float, default=0.8, help='Delay between requests in seconds.')
    parser.add_argument('--page-size', type=int, default=25, help='Fallback page size for small paged collection.')
    parser.add_argument('--max-pages', type=int, default=3, help='Maximum fallback pages per keyword and source type.')
    parser.add_argument('--output-csv', type=Path, default=PARSED_DIR / 'spse_targeted_2026.csv', help='Parsed CSV output path.')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Excel output path.')
    parser.add_argument('--summary', type=Path, default=DEFAULT_SUMMARY, help='Summary JSON output path.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    rows, keyword_counts, summary = collect(args)
    write_csv(args.output_csv, rows)
    write_excel(args.output, rows, summary, keyword_counts)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'rows before dedupe: {summary["rows_before_dedupe"]}')
    print(f'rows after dedupe: {summary["rows_after_dedupe"]}')
    print(f'parsed csv: {args.output_csv}')
    print(f'output: {args.output}')
    print(f'summary: {args.summary}')


if __name__ == '__main__':
    main()





