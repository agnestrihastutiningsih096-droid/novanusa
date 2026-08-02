from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font
from procurement_identity_resolution import (
    EvidenceRecord,
    ProcurementRecord,
    canonical_json,
    extract_procurement_status,
    resolve_identity,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SIRUP_DB_CANDIDATES = [
    ROOT.parent / 'mia-automation' / 'sirup_2026.duckdb',
    ROOT.parent / 'mia-automation' / 'sirup.duckdb',
]
DEFAULT_EVIDENCE_CANDIDATES = [
    ROOT / 'data' / 'evidence' / 'spse' / 'nasional' / 'parsed' / 'spse_national_sample_2026.csv',
]
DEFAULT_OUTPUT = ROOT / 'outputs' / 'evidence' / 'sirup_spse_evidence_mapping.xlsx'
DEFAULT_SUMMARY = ROOT / 'outputs' / 'evidence' / 'sirup_spse_evidence_mapping_summary.json'
OUTPUT_COLUMNS = [
    'sirup_package_id',
    'sirup_package_name',
    'sirup_institution_name',
    'sirup_pagu',
    'spse_package_code',
    'spse_package_name',
    'spse_institution_name',
    'spse_hps',
    'spse_source_type',
    'spse_stage_or_status',
    'identity_status',
    'identity_decision_id',
    'identity_decision_evidence',
    'manual_review_record',
    'match_level',
    'match_reason',
    'evidence_status',
    'evidence_source_url',
    'collected_at',
]

STOPWORDS = {
    'belanja', 'pengadaan', 'tender', 'tender ulang', 'non tender', 'non-tender',
    'paket', 'pekerjaan', 'jasa', 'barang', 'konstruksi', 'konsultansi', 'peralatan',
    'dan', 'untuk', 'di', 'pada', 'the', 'of', 'and', 'tahun', 'anggaran', 'ta',
}


@dataclass
class SirupRow:
    rup_id: str
    package_id: str
    package_name: str
    institution_name: str
    institution_alt: str
    pagu: float | None
    year: int | None
    satker: str = ''
    procurement_method: str = ''
    location: str = ''
    category: str = ''


@dataclass
class SpseRow:
    source_url: str
    source_type: str
    package_code: str
    package_name: str
    institution_name: str
    stage_or_status: str
    hps_or_pagu: str
    fiscal_year: int | None
    collected_at: str
    raw_file_path: str
    budget_value: float | None


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
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def normalize_name(value: Any) -> str:
    text = normalize(value)
    if not text:
        return ''
    tokens = [tok for tok in text.split() if tok not in STOPWORDS]
    return ' '.join(tokens)


def parse_budget(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isnan(value) if isinstance(value, float) else False:
            return None
        return float(value)
    text = clean(value)
    if not text:
        return None
    text = text.lower().replace('rp', '').replace('rupiah', '').strip()
    multiplier = 1.0
    if re.search(r'\btriliun\b|\bt\b', text):
        multiplier = 1_000_000_000_000.0
    elif re.search(r'\bmiliar\b|\bb\b', text):
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


def parse_year(text: Any) -> int | None:
    raw = clean(text)
    match = re.search(r'(20\d{2})', raw)
    if match:
        return int(match.group(1))
    return None


def fuzzy_ratio(a: Any, b: Any) -> float:
    left = normalize_name(a)
    right = normalize_name(b)
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def budget_similarity(left: float | None, right: float | None) -> float:
    if left is None or right is None:
        return 0.0
    denom = max(abs(left), abs(right), 1.0)
    return max(0.0, 1.0 - abs(left - right) / denom)


def load_sirup(db_path: Path, year: int | None, limit: int) -> pd.DataFrame:
    if not db_path.exists():
        raise FileNotFoundError(f'SiRUP DuckDB not found: {db_path}')
    con = duckdb.connect(str(db_path), read_only=True)
    where = []
    params: list[Any] = []
    if year:
        year_pattern = str(year)
        where.append("regexp_matches(lower(coalesce(pemilihan,'') || ' ' || coalesce(paket,'') || ' ' || coalesce(satuanKerja,'') || ' ' || coalesce(kldi,'')), ?)")
        params.append(year_pattern)
    where_sql = f"where {' and '.join(where)}" if where else ''
    query = f"""
        select
            cast(id as varchar) as rup_id,
            cast(id_referensi as varchar) as package_id,
            cast(pagu as double) as pagu,
            cast(satuanKerja as varchar) as satuanKerja,
            cast(kldi as varchar) as kldi,
            cast(lokasi as varchar) as lokasi,
            cast(jenisPengadaan as varchar) as jenisPengadaan,
            cast(metode as varchar) as metode,
            cast(sumberDana as varchar) as sumberDana,
            cast(paket as varchar) as paket,
            cast(pemilihan as varchar) as pemilihan,
            cast(idBulan as integer) as idBulan
        from sirup_raw
        {where_sql}
        order by pagu desc nulls last, id desc
        limit {int(limit)}
    """
    df = con.execute(query, params).fetchdf()
    con.close()
    return df


def load_spse_evidence(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if not path.exists():
            continue
        frames.append(pd.read_csv(path))
    if not frames:
        raise FileNotFoundError('No SPSE evidence CSV found.')
    evidence = pd.concat(frames, ignore_index=True)
    evidence['fiscal_year'] = evidence['fiscal_year'].apply(lambda v: parse_year(v) if clean(v) else None)
    evidence['budget_value'] = evidence['hps_or_pagu'].apply(parse_budget)
    return evidence


def to_sirup_rows(df: pd.DataFrame) -> list[SirupRow]:
    rows: list[SirupRow] = []
    for _, row in df.iterrows():
        institution_kldi = clean(row.get('kldi'))
        institution_satker = clean(row.get('satuanKerja'))
        rows.append(
            SirupRow(
                rup_id=clean(row.get('rup_id')),
                package_id=clean(row.get('package_id')),
                package_name=clean(row.get('paket')),
                institution_name=institution_kldi or institution_satker,
                institution_alt=institution_satker if institution_kldi else institution_kldi,
                pagu=parse_budget(row.get('pagu')),
                year=parse_year(row.get('pemilihan')),
                satker=institution_satker,
                procurement_method=clean(row.get('metode')),
                location=clean(row.get('lokasi')),
                category=clean(row.get('jenisPengadaan')),
            )
        )
    return rows


def to_spse_rows(df: pd.DataFrame) -> list[SpseRow]:
    rows: list[SpseRow] = []
    for _, row in df.iterrows():
        rows.append(
            SpseRow(
                source_url=clean(row.get('source_url')),
                source_type=clean(row.get('source_type')),
                package_code=clean(row.get('package_code')),
                package_name=clean(row.get('package_name')),
                institution_name=clean(row.get('institution_name')),
                stage_or_status=clean(row.get('stage_or_status')),
                hps_or_pagu=clean(row.get('hps_or_pagu')),
                fiscal_year=parse_year(row.get('fiscal_year')),
                collected_at=clean(row.get('collected_at')),
                raw_file_path=clean(row.get('raw_file_path')),
                budget_value=parse_budget(row.get('hps_or_pagu')),
            )
        )
    return rows


def same_year(sirup: SirupRow, spse: SpseRow) -> bool:
    return sirup.year is not None and spse.fiscal_year is not None and sirup.year == spse.fiscal_year


def same_institution_score(sirup: SirupRow, spse: SpseRow) -> float:
    candidates = [sirup.institution_name, sirup.institution_alt]
    best = 0.0
    for left in candidates:
        if not left or not spse.institution_name:
            continue
        score = fuzzy_ratio(left, spse.institution_name)
        if normalize(left) == normalize(spse.institution_name):
            return 1.0
        best = max(best, score)
    return best


def name_score(sirup: SirupRow, spse: SpseRow) -> float:
    return max(fuzzy_ratio(sirup.package_name, spse.package_name), fuzzy_ratio(sirup.package_name, spse.stage_or_status))


def budget_score(sirup: SirupRow, spse: SpseRow) -> float:
    return budget_similarity(sirup.pagu, spse.budget_value)


def resolve_match(sirup: SirupRow, evidence: list[SpseRow]):
    record = ProcurementRecord(
        record_id=sirup.rup_id or sirup.package_id,
        rup_id=sirup.rup_id,
        package_id=sirup.package_id,
        package_name=sirup.package_name,
        institution=sirup.institution_name,
        satker=sirup.satker,
        year=sirup.year,
        budget=sirup.pagu,
        procurement_method=sirup.procurement_method,
        location=sirup.location,
        category=sirup.category,
    )
    candidates = [
        EvidenceRecord(
            candidate_id=spse.package_code or f"{spse.raw_file_path}|{spse.source_url}",
            package_name=spse.package_name,
            institution=spse.institution_name,
            year=spse.fiscal_year,
            budget=spse.budget_value,
            evidence_type=spse.source_type,
            source_url=spse.source_url,
            source_file=spse.raw_file_path,
            source_record_id=spse.package_code,
            collected_at=spse.collected_at,
            provenance="SPSE parsed evidence dataset",
            source_status=spse.stage_or_status,
        )
        for spse in evidence
    ]
    identity = resolve_identity(record, candidates, dataset_version="SPRINT1_CONTROLLED_SPSE_DATASET")
    procurement = extract_procurement_status(identity, candidates)
    selected = next(
        (spse for spse in evidence if (spse.package_code or f"{spse.raw_file_path}|{spse.source_url}") == identity.selected_candidate_id),
        None,
    ) if identity.identity_status in {'PROBABLE_MATCH', 'CONFIRMED_MATCH'} else None
    return identity, procurement, selected


def evidence_status_for(match_level: str) -> str:
    if match_level in {'PROBABLE_MATCH', 'CONFIRMED_MATCH'}:
        return 'SPSE_FOUND'
    if match_level == 'NEEDS_MANUAL_REVIEW':
        return 'NEEDS_MANUAL_REVIEW'
    return 'SIRUP_PLANNING_ONLY'


def build_mapping(sirup_rows: list[SirupRow], evidence: list[SpseRow]) -> pd.DataFrame:
    output = []
    for sirup in sirup_rows:
        identity, procurement, spse = resolve_match(sirup, evidence)
        level = identity.identity_status
        reason = identity.decision_explanation
        output.append(
            {
                'sirup_package_id': sirup.package_id or sirup.rup_id,
                'sirup_package_name': sirup.package_name,
                'sirup_institution_name': sirup.institution_name,
                'sirup_pagu': sirup.pagu if sirup.pagu is not None else '',
                'spse_package_code': spse.package_code if spse else '',
                'spse_package_name': spse.package_name if spse else '',
                'spse_institution_name': spse.institution_name if spse else '',
                'spse_hps': spse.hps_or_pagu if spse else '',
                'spse_source_type': spse.source_type if spse else '',
                'spse_stage_or_status': spse.stage_or_status if spse else '',
                'identity_status': level,
                'identity_decision_id': identity.decision_evidence['decision_id'],
                'identity_decision_evidence': canonical_json(identity.decision_evidence),
                'manual_review_record': canonical_json(identity.manual_review_record) if identity.manual_review_record else '',
                'match_level': level,
                'match_reason': reason,
                'evidence_status': procurement['normalized_status'] if spse else evidence_status_for(level),
                'evidence_source_url': spse.source_url if spse else '',
                'collected_at': spse.collected_at if spse else '',
            }
        )
    return pd.DataFrame(output, columns=OUTPUT_COLUMNS)


def normalize_output_sheet(workbook_path: Path) -> None:
    wb = load_workbook(workbook_path)
    if 'mapping' in wb.sheetnames:
        ws = wb['mapping']
        ws.freeze_panes = 'A2'
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
        for col in ws.columns:
            max_len = 0
            column_letter = col[0].column_letter
            for cell in col:
                value = '' if cell.value is None else str(cell.value)
                max_len = max(max_len, len(value))
            ws.column_dimensions[column_letter].width = min(max_len + 2, 60)
    wb.save(workbook_path)


def build_summary(mapping: pd.DataFrame, sirup_count: int, evidence_count: int, args: argparse.Namespace, sirup_db: Path, evidence_files: list[Path]) -> dict[str, Any]:
    return {
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        'year': args.year,
        'limit': args.limit,
        'sirup_db': str(sirup_db),
        'evidence_files': [str(path) for path in evidence_files],
        'sirup_rows_loaded': sirup_count,
        'spse_rows_loaded': evidence_count,
        'output_file': str(args.output),
        'summary_file': str(args.summary),
        'match_level_counts': mapping['match_level'].value_counts(dropna=False).to_dict(),
        'evidence_status_counts': mapping['evidence_status'].value_counts(dropna=False).to_dict(),
        'source_type_counts': mapping['spse_source_type'].value_counts(dropna=False).to_dict(),
        'notes': [
            'Cross-namespace numeric equality is never accepted as identity proof.',
            'Classification is authorized by registered signals after HARD-conflict rejection.',
            'Identity confidence is diagnostic only and procurement status is evaluated afterward.',
            'Canonical decision evidence is stored in the adjacent JSONL sidecar.',
        ],
    }


def resolve_sirup_db(path: str | None) -> Path:
    if path:
        return Path(path)
    for candidate in DEFAULT_SIRUP_DB_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError('No SiRUP DuckDB found in known locations.')


def resolve_evidence_files(paths: list[str] | None, year: int | None) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    candidates: list[Path] = []
    parsed_dir = ROOT / 'data' / 'evidence' / 'spse' / 'nasional' / 'parsed'
    if year:
        candidates.extend(sorted(parsed_dir.glob(f'spse_*{year}.csv')))
        specific = parsed_dir / f'spse_national_sample_{year}.csv'
        if specific.exists():
            candidates.append(specific)
    candidates.extend(DEFAULT_EVIDENCE_CANDIDATES)
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate.exists() and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    if unique:
        return unique
    raise FileNotFoundError('No SPSE evidence CSV found.')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Map SiRUP rows to SPSE Nasional evidence rows.')
    parser.add_argument('--year', type=int, default=2026, help='Target fiscal year filter.')
    parser.add_argument('--limit', type=int, default=1000, help='Maximum SiRUP rows to map.')
    parser.add_argument('--sirup-db', default='', help='Optional explicit SiRUP DuckDB path.')
    parser.add_argument('--evidence-file', nargs='*', default=None, help='Optional explicit SPSE evidence CSV file(s).')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='Excel output path.')
    parser.add_argument('--summary', type=Path, default=DEFAULT_SUMMARY, help='Summary JSON output path.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sirup_db = resolve_sirup_db(args.sirup_db or None)
    evidence_files = resolve_evidence_files(args.evidence_file, args.year)
    sirup_df = load_sirup(sirup_db, args.year, args.limit)
    evidence_df = load_spse_evidence(evidence_files)
    sirup_rows = to_sirup_rows(sirup_df)
    spse_rows = to_spse_rows(evidence_df)
    mapping = build_mapping(sirup_rows, spse_rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    decision_sidecar = args.output.with_suffix('.identity-decisions.jsonl')
    decision_lines = sorted(mapping['identity_decision_evidence'].tolist())
    decision_sidecar.write_text('\n'.join(decision_lines) + '\n', encoding='utf-8')
    review_sidecar = args.output.with_suffix('.manual-review-records.jsonl')
    review_lines = sorted(value for value in mapping['manual_review_record'].tolist() if value)
    review_sidecar.write_text(('\n'.join(review_lines) + '\n') if review_lines else '', encoding='utf-8')
    mapping['identity_decision_evidence'] = mapping['identity_decision_id'].map(
        lambda value: f'{decision_sidecar.name}#{value}'
    )
    mapping['manual_review_record'] = mapping['manual_review_record'].map(
        lambda value: review_sidecar.name if value else ''
    )
    with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
        mapping.to_excel(writer, index=False, sheet_name='mapping')
        pd.DataFrame(
            [[
                'Purpose',
                'Map SiRUP planning rows to SPSE Nasional evidence rows with evidence-first matching.',
            ], [
                'No scoring',
                'This workbook does not contain opportunity scores or AI scores.',
            ], [
                'Evidence status',
                'SPSE_FOUND means downstream evidence exists; PLANNED_ONLY means no match; NEEDS_MANUAL_REVIEW means weak candidate.',
            ]],
            columns=['item', 'value'],
        ).to_excel(writer, index=False, sheet_name='methodology')
        pd.DataFrame(
            [
                ['match_level', 'exact / strong / weak / no_match'],
                ['evidence_status', 'PLANNED_ONLY / SPSE_FOUND / NEEDS_MANUAL_REVIEW'],
                ['input_sirup', str(sirup_db)],
                ['input_spse', ', '.join(str(path) for path in evidence_files)],
                ['generated_at', datetime.now(timezone.utc).replace(microsecond=0).isoformat()],
            ],
            columns=['item', 'value'],
        ).to_excel(writer, index=False, sheet_name='summary')
    normalize_output_sheet(args.output)

    summary = build_summary(mapping, len(sirup_rows), len(spse_rows), args, sirup_db, evidence_files)
    summary['identity_decision_evidence_file'] = str(decision_sidecar)
    summary['identity_decision_evidence_digest'] = hashlib.sha256(
        decision_sidecar.read_bytes()
    ).hexdigest()
    summary['manual_review_records_file'] = str(review_sidecar)
    args.summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'mapped rows: {len(mapping)}')
    print(f'output: {args.output}')
    print(f'summary: {args.summary}')


if __name__ == '__main__':
    main()


