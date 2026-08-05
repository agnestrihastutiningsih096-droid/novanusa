from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import requests


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENDPOINT = "https://sirup.inaproc.id/sirup/caripaketctr/search"
SOURCE_PAGE = "https://sirup.inaproc.id/sirup/caripaketctr/index"
DEFAULT_STAGING_ROOT = ROOT / "data" / "staging" / "sirup"
TABLE_NAME = "sirup_raw"
MAX_PAGE_SIZE = 100
MAX_ROWS = 10_000
CHECKPOINT_VERSION = 2
CHECKPOINT_REPLACE_ATTEMPTS = 10
CHECKPOINT_REPLACE_DELAY_SECONDS = 0.5
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


def page_request_params(year: int, start: int, length: int, draw: int) -> dict[str, Any]:
    return {
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
        "draw": draw,
        "start": start,
        "length": length,
        "order[0][column]": 11,
        "order[0][dir]": "desc",
        "search[value]": "",
        "search[regex]": "false",
    }


def checkpoint_config(year: int, page_size: int, full_snapshot: bool) -> dict[str, Any]:
    return {
        "year": year,
        "page_size": page_size,
        "full_snapshot": full_snapshot,
        "source_endpoint": SOURCE_ENDPOINT,
        "order_column": 11,
        "order_direction": "desc",
    }


def write_checkpoint(
    path: Path,
    config: dict[str, Any],
    run_dir: Path,
    rows_collected: int,
    source_count: int,
    page_count: int,
    started_at: str,
    retries_used: int,
) -> None:
    checkpoint = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "config": config,
        "run_dir": str(run_dir),
        "database_path": str(run_dir / "sirup_staging.duckdb"),
        "last_completed_page": page_count,
        "next_start": rows_collected,
        "rows_collected": rows_collected,
        "source_count": source_count,
        "started_at": started_at,
        "retries_used": retries_used,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for attempt in range(CHECKPOINT_REPLACE_ATTEMPTS):
        try:
            temporary_path.replace(path)
            break
        except PermissionError:
            if attempt == CHECKPOINT_REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(CHECKPOINT_REPLACE_DELAY_SECONDS)


def load_checkpoint(
    path: Path, expected_config: dict[str, Any]
) -> tuple[Path, int, int, int, str, int]:
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"checkpoint is not readable JSON: {path}: {exc}") from exc
    if not isinstance(checkpoint, dict):
        raise RuntimeError("checkpoint root is not an object")
    if checkpoint.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise RuntimeError("checkpoint version mismatch")
    if checkpoint.get("config") != expected_config:
        raise RuntimeError("checkpoint configuration mismatch")
    run_dir_value = checkpoint.get("run_dir")
    database_path_value = checkpoint.get("database_path")
    rows_collected = checkpoint.get("rows_collected")
    source_count = checkpoint.get("source_count")
    page_count = checkpoint.get("last_completed_page")
    if (
        not isinstance(run_dir_value, str)
        or not isinstance(database_path_value, str)
        or not isinstance(rows_collected, int)
        or not isinstance(source_count, int)
        or not isinstance(page_count, int)
        or checkpoint.get("next_start") != rows_collected
        or rows_collected < 0
        or page_count < 0
        or not isinstance(checkpoint.get("started_at"), str)
        or not isinstance(checkpoint.get("retries_used"), int)
    ):
        raise RuntimeError("checkpoint contents are inconsistent")
    run_dir = Path(run_dir_value).resolve()
    if Path(database_path_value).resolve() != run_dir / "sirup_staging.duckdb":
        raise RuntimeError("checkpoint database path is inconsistent")
    return (
        run_dir,
        rows_collected,
        source_count,
        page_count,
        checkpoint["started_at"],
        checkpoint["retries_used"],
    )


def fetch_page(
    session: requests.Session,
    year: int,
    start: int,
    length: int,
    draw: int,
    timeout: float,
    retries: int,
) -> tuple[dict[str, Any], int]:
    params = page_request_params(year, start, length, draw)
    url = f"{SOURCE_ENDPOINT}?{urllib.parse.urlencode(params)}"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code != 200:
                raise RuntimeError(f"unexpected HTTP status {response.status_code}")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
            if content_type != "application/json":
                raise RuntimeError(f"unexpected content type {content_type!r}")
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("response root is not an object")
            return payload, attempt
        except (requests.RequestException, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
    raise RuntimeError(f"source request failed after {retries + 1} attempts: {last_error}")


def validate_rows(payload: dict[str, Any], expected_count: int) -> list[dict[str, Any]]:
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("response field 'data' is not an array")
    if len(rows) != expected_count:
        raise RuntimeError(f"expected {expected_count} rows but source returned {len(rows)}")
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
        identifiers.append(row["id"])
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError("source returned duplicate ids")
    return rows


def verify_source_count(expected: int | None, observed: int) -> int:
    if expected is not None and observed != expected:
        raise RuntimeError(
            f"source record count changed: expected {expected}, observed {observed}"
        )
    return observed if expected is None else expected


def write_validation_failure_evidence(
    run_dir: Path,
    payload: dict[str, Any],
    error: Exception,
    year: int,
    start: int,
    length: int,
    draw: int,
) -> Path:
    canonical_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    evidence = {
        "captured_at": utc_now(),
        "year": year,
        "start": start,
        "length": length,
        "draw": draw,
        "source_endpoint": SOURCE_ENDPOINT,
        "request_parameters": page_request_params(year, start, length, draw),
        "observed_recordsFiltered": payload.get("recordsFiltered"),
        "validation_error": str(error),
        "payload_sha256": hashlib.sha256(canonical_payload).hexdigest(),
        "payload": payload,
    }
    failures_dir = run_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = failures_dir / f"page-start-{start}-draw-{draw}.json"
    temporary_path = evidence_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    temporary_path.replace(evidence_path)
    return evidence_path


def validate_page(
    run_dir: Path,
    payload: dict[str, Any],
    expected_source_count: int | None,
    year: int,
    start: int,
    length: int,
    draw: int,
    full_snapshot: bool,
) -> tuple[list[dict[str, Any]], int]:
    try:
        observed_source_count = payload.get("recordsFiltered")
        if not isinstance(observed_source_count, int):
            raise RuntimeError("response field 'recordsFiltered' is not an integer")
        verified_source_count = verify_source_count(
            expected_source_count, observed_source_count
        )
        expected_page_count = length
        if full_snapshot:
            expected_page_count = min(length, verified_source_count - start)
        rows = validate_rows(payload, expected_page_count)
        return rows, verified_source_count
    except RuntimeError as exc:
        try:
            write_validation_failure_evidence(
                run_dir, payload, exc, year, start, length, draw
            )
        except Exception:
            pass
        raise


def initialize_database(path: Path) -> None:
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
    finally:
        connection.close()


def append_page(path: Path, rows: list[dict[str, Any]]) -> None:
    values = [tuple(row.get(field) for field in (
            "id", "id_referensi", "pagu", "satuanKerja", "kldi", "lokasi",
            "jenisPengadaan", "metode", "sumberDana", "paket", "pemilihan", "idBulan",
        )) for row in rows]
    connection = duckdb.connect(str(path))
    try:
        connection.execute("begin transaction")
        identifiers = [value[0] for value in values]
        placeholders = ", ".join("?" for _ in identifiers)
        if connection.execute(
            f"select count(*) from sirup_raw where id in ({placeholders})", identifiers
        ).fetchone()[0]:
            raise RuntimeError("source returned ids already present in staging")
        connection.executemany(
            "insert into sirup_raw values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values
        )
        connection.execute("commit")
    except Exception:
        connection.execute("rollback")
        raise
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
    parser = argparse.ArgumentParser(description="Fetch SiRUP data into isolated staging.")
    parser.add_argument("--year", type=int, required=True, help="Explicit SiRUP budget year.")
    parser.add_argument("--page-size", type=int, default=100, help="Rows per page (1-100).")
    parser.add_argument(
        "--max-rows", type=int, default=100, help=f"Maximum rows to fetch (1-{MAX_ROWS})."
    )
    parser.add_argument(
        "--full-snapshot",
        action="store_true",
        help="Fetch all rows reported by recordsFiltered; --max-rows is ignored.",
    )
    parser.add_argument(
        "--stop-after-rows",
        type=int,
        help="In full mode, stop after the committed page reaching this row count.",
    )
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries after the first request (0-3).")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between pages (0-5 seconds).")
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    parser.add_argument("--checkpoint", type=Path, help="Persist or resume a fetch checkpoint.")
    args = parser.parse_args()
    if not 1 <= args.page_size <= MAX_PAGE_SIZE:
        parser.error(f"--page-size must be between 1 and {MAX_PAGE_SIZE}")
    if not args.full_snapshot and not 1 <= args.max_rows <= MAX_ROWS:
        parser.error(f"--max-rows must be between 1 and {MAX_ROWS}")
    if args.stop_after_rows is not None:
        if not args.full_snapshot:
            parser.error("--stop-after-rows requires --full-snapshot")
        if args.stop_after_rows < 1:
            parser.error("--stop-after-rows must be at least 1")
        if args.checkpoint is None:
            parser.error("--stop-after-rows requires --checkpoint")
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")
    if not 0 <= args.retries <= 3:
        parser.error("--retries must be between 0 and 3")
    if not 0 <= args.delay <= 5:
        parser.error("--delay must be between 0 and 5 seconds")
    return args


def main() -> int:
    args = parse_args()
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": SOURCE_PAGE,
        "User-Agent": "NovaNusa-SiRUP-Staging-Fetch/1.0",
        "X-Requested-With": "XMLHttpRequest",
    })
    run_dir = args.staging_root.resolve()
    try:
        config = checkpoint_config(args.year, args.page_size, args.full_snapshot)
        checkpoint_path = args.checkpoint.resolve() if args.checkpoint else None
        if checkpoint_path and checkpoint_path.is_file():
            (
                run_dir,
                rows_collected,
                source_count,
                page_count,
                started_at,
                retries_used,
            ) = load_checkpoint(checkpoint_path, config)
            if run_dir.parent != args.staging_root.resolve():
                raise RuntimeError("checkpoint run directory is outside --staging-root")
            database_path = run_dir / "sirup_staging.duckdb"
            if not database_path.is_file():
                raise RuntimeError("checkpoint staging database does not exist")
            database_rows, distinct_ids, _, _ = verify_database(database_path)
            if database_rows != rows_collected or distinct_ids != database_rows:
                raise RuntimeError("checkpoint offset does not match staging database")
            if not args.full_snapshot and rows_collected > args.max_rows:
                raise RuntimeError("checkpoint contains more rows than --max-rows")
        else:
            started_at = utc_now()
            requested_label = "full" if args.full_snapshot else f"{args.max_rows}rows"
            run_id = (
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + f"-{args.year}-{requested_label}"
            )
            run_dir = args.staging_root.resolve() / run_id
            database_path = run_dir / "sirup_staging.duckdb"
            if run_dir.exists():
                raise RuntimeError(f"staging run already exists: {run_dir}")
            run_dir.mkdir(parents=True)
            initialize_database(database_path)
            rows_collected = 0
            source_count = 0
            page_count = 0
            retries_used = 0
        run_id = run_dir.name
        manifest_path = run_dir / "manifest.json"
        expected_source_count: int | None = source_count if rows_collected else None
        target_row_count = expected_source_count if args.full_snapshot else args.max_rows
        if target_row_count is not None and rows_collected > target_row_count:
            raise RuntimeError("checkpoint contains more rows than the target row count")
        while target_row_count is None or rows_collected < target_row_count:
            length = args.page_size if target_row_count is None else min(
                args.page_size, target_row_count - rows_collected
            )
            payload, page_retries = fetch_page(
                session,
                args.year,
                start=rows_collected,
                length=length,
                draw=page_count + 1,
                timeout=args.timeout,
                retries=args.retries,
            )
            page_rows, expected_source_count = validate_page(
                run_dir,
                payload,
                expected_source_count,
                args.year,
                rows_collected,
                length,
                page_count + 1,
                args.full_snapshot,
            )
            if args.full_snapshot:
                target_row_count = expected_source_count
            append_page(database_path, page_rows)
            rows_collected += len(page_rows)
            retries_used += page_retries
            page_count += 1
            if checkpoint_path:
                write_checkpoint(
                    checkpoint_path,
                    config,
                    run_dir,
                    rows_collected,
                    expected_source_count,
                    page_count,
                    started_at,
                    retries_used,
                )
            if (
                args.stop_after_rows is not None
                and rows_collected >= args.stop_after_rows
                and rows_collected < target_row_count
            ):
                print(f"controlled stop after committed rows: {rows_collected}")
                print(f"staging database: {database_path}")
                print(f"checkpoint: {checkpoint_path}")
                session.close()
                return 0
            if target_row_count is None or rows_collected < target_row_count:
                time.sleep(args.delay)
        if expected_source_count is None:
            raise RuntimeError("source record count was not collected")
        row_count, distinct_ids, min_id, max_id = verify_database(database_path)
        if row_count != target_row_count or distinct_ids != row_count:
            raise RuntimeError("staging database row or unique-id validation failed")
        digest = sha256_file(database_path)
        completed_at = utc_now()
        manifest = {
            "manifest_version": 1,
            "run_id": run_id,
            "status": "validated_staging_sample",
            "full_snapshot": args.full_snapshot,
            "promotion_eligible": False,
            "source_endpoint": SOURCE_ENDPOINT,
            "requested_year": args.year,
            "requested_limit": target_row_count,
            "page_size": args.page_size,
            "page_count": page_count,
            "started_at": started_at,
            "collected_at": completed_at,
            "database_path": str(database_path),
            "table_name": TABLE_NAME,
            "row_count": row_count,
            "distinct_id_count": distinct_ids,
            "min_id": min_id,
            "max_id": max_id,
            "source_records_filtered": expected_source_count,
            "request_count": page_count,
            "retries_used": retries_used,
            "sha256": digest,
            "validation": {
                "response_shape": "passed",
                "requested_row_count": "passed",
                "sequential_pagination": "passed",
                "source_count_consistency": "passed",
                "source_year_parameter": "passed",
                "non_null_ids": "passed",
                "unique_ids": "passed",
                "database_read_only_reopen": "passed",
            },
            "promotion": {"attempted": False, "result": "not_in_scope"},
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception as exc:
        session.close()
        print(f"staging fetch failed: {exc}", file=sys.stderr)
        print(f"failed staging directory: {run_dir}", file=sys.stderr)
        return 1

    session.close()
    print(f"rows: {row_count}")
    print(f"distinct ids: {distinct_ids}")
    print(f"staging database: {database_path}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
