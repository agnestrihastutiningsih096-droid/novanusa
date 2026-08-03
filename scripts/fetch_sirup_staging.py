from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENDPOINT = "https://sirup.inaproc.id/sirup/caripaketctr/search"
SOURCE_PAGE = "https://sirup.inaproc.id/sirup/caripaketctr/index"
DEFAULT_STAGING_ROOT = ROOT / "data" / "staging" / "sirup"
TABLE_NAME = "sirup_raw"
MAX_LIMIT = 100
REQUIRED_FIELDS = {
    "id",
    "id_referensi",
    "pagu",
    "satuanKerja",
    "kldi",
    "lokasi",
    "jenisPengadaan",
    "metode",
    "sumberDana",
    "paket",
    "pemilihan",
    "idBulan",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_page(year: int, limit: int, timeout: float, retries: int) -> tuple[dict[str, Any], int]:
    params = {
        "tahunAnggaran": year,
        "jenisPengadaan": "",
        "metodePengadaan": "",
        "minPagu": "",
        "maxPagu": "",
        "bulan": "",
        "lokasi": "",
        "kldi": "",
        "pdn": "",
        "ukm": "",
        "draw": 1,
        "start": 0,
        "length": limit,
        "order[0][column]": 5,
        "order[0][dir]": "desc",
        "search[value]": "",
        "search[regex]": "false",
    }
    request = urllib.request.Request(
        f"{SOURCE_ENDPOINT}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": SOURCE_PAGE,
            "User-Agent": "NovaNusa-SiRUP-Staging-Fetch/1.0",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"unexpected HTTP status {response.status}")
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise RuntimeError(f"unexpected content type {content_type!r}")
                body = response.read()
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("response root is not an object")
            return payload, attempt
        except (OSError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
    raise RuntimeError(f"source request failed after {retries + 1} attempts: {last_error}")


def validate_rows(payload: dict[str, Any], year: int, limit: int) -> list[dict[str, Any]]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("response field 'data' is not an array")
    if len(rows) != limit:
        raise RuntimeError(f"expected {limit} rows but source returned {len(rows)}")
    if not isinstance(payload.get("recordsFiltered"), int):
        raise RuntimeError("response field 'recordsFiltered' is not an integer")

    identifiers: list[Any] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"row {index} is not an object")
        missing = sorted(REQUIRED_FIELDS - row.keys())
        if missing:
            raise RuntimeError(f"row {index} is missing fields: {', '.join(missing)}")
        if row["id"] is None:
            raise RuntimeError(f"row {index} has a null id")
        if str(year) not in str(row["pemilihan"]):
            raise RuntimeError(f"row {index} does not match requested year {year}")
        identifiers.append(row["id"])
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("source returned duplicate ids")
    return rows


def write_database(path: Path, rows: list[dict[str, Any]]) -> None:
    connection = duckdb.connect(str(path))
    try:
        connection.execute(
            """
            create table sirup_raw (
                id bigint not null primary key,
                id_referensi varchar,
                pagu double,
                satuanKerja varchar,
                kldi varchar,
                lokasi varchar,
                jenisPengadaan varchar,
                metode varchar,
                sumberDana varchar,
                paket varchar,
                pemilihan varchar,
                idBulan integer
            )
            """
        )
        values = [tuple(row.get(field) for field in (
            "id", "id_referensi", "pagu", "satuanKerja", "kldi", "lokasi",
            "jenisPengadaan", "metode", "sumberDana", "paket", "pemilihan", "idBulan",
        )) for row in rows]
        connection.executemany(
            "insert into sirup_raw values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values
        )
        connection.execute("checkpoint")
    finally:
        connection.close()


def verify_database(path: Path) -> tuple[int, int, int, int]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        row = connection.execute(
            "select count(*), count(distinct id), min(id), max(id) from sirup_raw"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("database verification returned no result")
    return int(row[0]), int(row[1]), int(row[2]), int(row[3])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a bounded SiRUP sample into isolated staging.")
    parser.add_argument("--year", type=int, required=True, help="Explicit SiRUP budget year.")
    parser.add_argument("--limit", type=int, default=10, help=f"Rows to fetch (1-{MAX_LIMIT}).")
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries after the first request (0-3).")
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_LIMIT:
        parser.error(f"--limit must be between 1 and {MAX_LIMIT}")
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    if not 0 <= args.retries <= 3:
        parser.error("--retries must be between 0 and 3")
    return args


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{args.year}-{args.limit}rows"
    run_dir = args.staging_root.resolve() / run_id
    database_path = run_dir / "sirup_staging.duckdb"
    manifest_path = run_dir / "manifest.json"
    if run_dir.exists():
        raise RuntimeError(f"staging run already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    try:
        payload, retries_used = fetch_page(args.year, args.limit, args.timeout, args.retries)
        rows = validate_rows(payload, args.year, args.limit)
        write_database(database_path, rows)
        row_count, distinct_ids, min_id, max_id = verify_database(database_path)
        if row_count != args.limit or distinct_ids != row_count:
            raise RuntimeError("staging database row or unique-id validation failed")
        digest = sha256_file(database_path)
        completed_at = utc_now()
        manifest = {
            "manifest_version": 1,
            "run_id": run_id,
            "status": "validated_staging_sample",
            "promotion_eligible": False,
            "source_endpoint": SOURCE_ENDPOINT,
            "requested_year": args.year,
            "requested_limit": args.limit,
            "started_at": started_at,
            "collected_at": completed_at,
            "database_path": str(database_path),
            "table_name": TABLE_NAME,
            "row_count": row_count,
            "distinct_id_count": distinct_ids,
            "min_id": min_id,
            "max_id": max_id,
            "source_records_filtered": payload["recordsFiltered"],
            "request_count": 1,
            "retries_used": retries_used,
            "sha256": digest,
            "validation": {
                "response_shape": "passed",
                "requested_row_count": "passed",
                "requested_year": "passed",
                "non_null_ids": "passed",
                "unique_ids": "passed",
                "database_read_only_reopen": "passed",
            },
            "promotion": {"attempted": False, "result": "not_in_scope"},
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"staging fetch failed: {exc}", file=sys.stderr)
        print(f"failed staging directory: {run_dir}", file=sys.stderr)
        return 1

    print(f"rows: {row_count}")
    print(f"distinct ids: {distinct_ids}")
    print(f"staging database: {database_path}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
