from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import requests

from sirup_page_classifier import classify_page_rows
from sirup_quarantine_store import (
    append_quarantine_record,
    build_quarantine_record,
    canonical_json_bytes,
    count_quarantine_records,
    read_quarantine_record,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ENDPOINT = "https://sirup.inaproc.id/sirup/caripaketctr/search"
SOURCE_PAGE = "https://sirup.inaproc.id/sirup/caripaketctr/index"
DEFAULT_STAGING_ROOT = ROOT / "data" / "staging" / "sirup"
TABLE_NAME = "sirup_raw"
MAX_PAGE_SIZE = 100
MAX_ROWS = 10_000
CHECKPOINT_VERSION = 3
CHECKPOINT_REPLACE_ATTEMPTS = 10
CHECKPOINT_REPLACE_DELAY_SECONDS = 0.5
QUARANTINE_PATH_NAME = "quarantine"
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


def checkpoint_config(
    year: int, page_size: int, full_snapshot: bool, mode: str = "strict"
) -> dict[str, Any]:
    return {
        "year": year,
        "page_size": page_size,
        "full_snapshot": full_snapshot,
        "mode": mode,
        "source_endpoint": SOURCE_ENDPOINT,
        "order_column": 11,
        "order_direction": "desc",
    }


def write_checkpoint(
    path: Path,
    config: dict[str, Any],
    run_dir: Path,
    source_rows_processed: int,
    canonical_rows_collected: int,
    quarantine_rows: int,
    source_count: int,
    page_count: int,
    started_at: str,
    retries_used: int,
) -> None:
    mode = config.get("mode")
    if mode == "strict":
        if source_rows_processed != canonical_rows_collected:
            raise RuntimeError(
                "strict checkpoint requires source_rows_processed to equal "
                "canonical_rows_collected"
            )
        if quarantine_rows != 0:
            raise RuntimeError("strict checkpoint requires quarantine_rows to be zero")
    elif mode == "quarantine":
        counters = (
            source_rows_processed,
            canonical_rows_collected,
            quarantine_rows,
            source_count,
            page_count,
            retries_used,
        )
        if any(type(counter) is not int or counter < 0 for counter in counters):
            raise RuntimeError("quarantine checkpoint counters must be non-negative integers")
        if source_rows_processed != canonical_rows_collected + quarantine_rows:
            raise RuntimeError(
                "quarantine checkpoint requires source_rows_processed to equal "
                "canonical_rows_collected plus quarantine_rows"
            )
    else:
        raise RuntimeError(f"unsupported checkpoint mode: {mode!r}")
    checkpoint = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "config": config,
        "run_dir": str(run_dir),
        "database_path": str(run_dir / "sirup_staging.duckdb"),
        "quarantine_path": str(run_dir / QUARANTINE_PATH_NAME),
        "source_count": source_count,
        "source_rows_processed": source_rows_processed,
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
        "next_start": source_rows_processed,
        "last_completed_page": page_count,
        "retries_used": retries_used,
        "started_at": started_at,
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
) -> tuple[Path, int, int, int, int, int, str, int]:
    try:
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"checkpoint is not readable JSON: {path}: {exc}") from exc
    if not isinstance(checkpoint, dict):
        raise RuntimeError("checkpoint root is not an object")
    if checkpoint.get("checkpoint_version") == 2:
        raise RuntimeError("checkpoint v2 requires explicit migration")
    if checkpoint.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise RuntimeError("checkpoint version mismatch")
    checkpoint_config_value = checkpoint.get("config")
    if (
        isinstance(checkpoint_config_value, dict)
        and checkpoint_config_value.get("mode") != expected_config.get("mode")
    ):
        raise RuntimeError("checkpoint mode mismatch")
    if checkpoint_config_value != expected_config:
        raise RuntimeError("checkpoint configuration mismatch")
    mode = checkpoint["config"].get("mode")
    if mode not in {"strict", "quarantine"}:
        raise RuntimeError(f"unsupported checkpoint mode: {mode!r}")
    run_dir_value = checkpoint.get("run_dir")
    database_path_value = checkpoint.get("database_path")
    quarantine_path_value = checkpoint.get("quarantine_path")
    source_rows_processed = checkpoint.get("source_rows_processed")
    canonical_rows_collected = checkpoint.get("canonical_rows_collected")
    quarantine_rows = checkpoint.get("quarantine_rows")
    source_count = checkpoint.get("source_count")
    page_count = checkpoint.get("last_completed_page")
    quarantine_accounting_is_invalid = mode == "quarantine" and (
        any(
            type(counter) is not int or counter < 0
            for counter in (
                source_rows_processed,
                canonical_rows_collected,
                quarantine_rows,
                source_count,
                page_count,
                checkpoint.get("next_start"),
                checkpoint.get("retries_used"),
            )
        )
        or source_rows_processed != canonical_rows_collected + quarantine_rows
    )
    strict_accounting_is_invalid = mode == "strict" and (
        source_rows_processed != canonical_rows_collected or quarantine_rows != 0
    )
    if (
        not isinstance(run_dir_value, str)
        or not isinstance(database_path_value, str)
        or not isinstance(quarantine_path_value, str)
        or not isinstance(source_rows_processed, int)
        or not isinstance(canonical_rows_collected, int)
        or not isinstance(quarantine_rows, int)
        or not isinstance(source_count, int)
        or not isinstance(page_count, int)
        or checkpoint.get("next_start") != source_rows_processed
        or strict_accounting_is_invalid
        or quarantine_accounting_is_invalid
        or source_rows_processed < 0
        or source_count < 0
        or page_count < 0
        or not isinstance(checkpoint.get("started_at"), str)
        or not isinstance(checkpoint.get("retries_used"), int)
        or checkpoint["retries_used"] < 0
    ):
        raise RuntimeError("checkpoint contents are inconsistent")
    run_dir = Path(run_dir_value).resolve()
    if Path(database_path_value).resolve() != run_dir / "sirup_staging.duckdb":
        raise RuntimeError("checkpoint database path is inconsistent")
    if Path(quarantine_path_value).resolve() != run_dir / QUARANTINE_PATH_NAME:
        raise RuntimeError("checkpoint quarantine path is inconsistent")
    return (
        run_dir,
        source_rows_processed,
        canonical_rows_collected,
        quarantine_rows,
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


def classify_page(
    payload: dict[str, Any],
    expected_source_count: int | None,
    start: int,
    length: int,
    full_snapshot: bool,
) -> tuple[dict[str, Any], int]:
    observed_source_count = payload.get("recordsFiltered")
    if not isinstance(observed_source_count, int):
        raise RuntimeError("response field 'recordsFiltered' is not an integer")
    verified_source_count = verify_source_count(
        expected_source_count, observed_source_count
    )
    expected_page_count = length
    if full_snapshot:
        expected_page_count = min(length, verified_source_count - start)
    classification = classify_page_rows(payload, expected_page_count, REQUIRED_FIELDS)
    return classification, verified_source_count


def prepare_page_transaction(
    payload: dict[str, Any],
    expected_source_count: int | None,
    run_id: str,
    year: int,
    start: int,
    length: int,
    draw: int,
    full_snapshot: bool,
) -> dict[str, Any]:
    classification, verified_source_count = classify_page(
        payload, expected_source_count, start, length, full_snapshot
    )
    canonical_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload_sha256 = hashlib.sha256(canonical_payload).hexdigest()
    request_parameters = page_request_params(year, start, length, draw)
    captured_at = utc_now()
    return {
        "classification": classification,
        "verified_source_count": verified_source_count,
        "payload_sha256": payload_sha256,
        "request_parameters": request_parameters,
        "page_identity": {
            "run_id": run_id,
            "page_start": start,
            "requested_length": length,
            "page_draw": draw,
            "payload_sha256": payload_sha256,
        },
        "captured_at": captured_at,
    }


def build_page_quarantine_records(
    prepared_transaction: dict[str, Any],
    run_id: str,
    failure_evidence_path: Path | str,
) -> list[dict[str, Any]]:
    classification = prepared_transaction["classification"]
    payload_sha256 = prepared_transaction["payload_sha256"]
    request_parameters = prepared_transaction["request_parameters"]
    page_identity = prepared_transaction["page_identity"]
    captured_at = prepared_transaction["captured_at"]
    return [
        build_quarantine_record(
            run_id=run_id,
            page_start=page_identity["page_start"],
            requested_length=page_identity["requested_length"],
            page_draw=page_identity["page_draw"],
            row_index=invalid_row["row_index"],
            raw_row=invalid_row["raw_row"],
            missing_fields=invalid_row["missing_fields"],
            invalid_fields=invalid_row["invalid_fields"],
            validation_error=invalid_row["validation_error"],
            captured_at=captured_at,
            payload_sha256=payload_sha256,
            request_parameters=request_parameters,
            failure_evidence_path=str(failure_evidence_path),
        )
        for invalid_row in classification["invalid_rows"]
    ]


def append_page_quarantine_records(
    quarantine_path,
    quarantine_records,
    expected_prior_count,
):
    if type(expected_prior_count) is not int or expected_prior_count < 0:
        raise ValueError("expected_prior_count must be a non-negative integer")

    created_count = 0
    existing_count = 0
    for record in quarantine_records:
        append_result = append_quarantine_record(quarantine_path, record)
        if append_result == "created":
            created_count += 1
        elif append_result == "existing":
            existing_count += 1
        else:
            raise RuntimeError(f"unexpected quarantine append result: {append_result!r}")

    actual_total_count = count_quarantine_records(quarantine_path)
    expected_total_count = expected_prior_count + len(quarantine_records)
    if actual_total_count != expected_total_count:
        raise RuntimeError(
            "quarantine record count mismatch: "
            f"expected {expected_total_count}, observed {actual_total_count}"
        )
    return {
        "created_count": created_count,
        "existing_count": existing_count,
        "total_count": actual_total_count,
    }


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
        classification, verified_source_count = classify_page(
            payload, expected_source_count, start, length, full_snapshot
        )
        if classification["invalid_row_count"] > 0:
            detail = "; ".join(
                row["validation_error"] for row in classification["invalid_rows"]
            )
            raise RuntimeError(f"page row validation failed: {detail}")
        return classification["valid_rows"], verified_source_count
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


def inspect_canonical_page_state(database_path, rows):
    canonical_fields = (
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
    )
    expected_rows = []
    identifiers = []
    seen_identifiers = set()
    for row in rows:
        if not isinstance(row, dict) or "id" not in row or row["id"] is None:
            raise ValueError("each canonical inspection row must have a non-null id")
        identifier = row["id"]
        try:
            is_duplicate = identifier in seen_identifiers
        except TypeError as exc:
            raise ValueError("canonical inspection row id must be hashable") from exc
        if is_duplicate:
            raise ValueError(f"duplicate canonical inspection id: {identifier!r}")
        seen_identifiers.add(identifier)
        identifiers.append(identifier)
        expected_rows.append(tuple(row.get(field) for field in canonical_fields))

    expected_count = len(expected_rows)
    if expected_count == 0:
        return {"state": "absent", "expected_count": 0, "observed_count": 0}

    placeholders = ", ".join("?" for _ in identifiers)
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        stored_rows = connection.execute(
            f"select {', '.join(canonical_fields)} "
            f"from sirup_raw where id in ({placeholders})",
            identifiers,
        ).fetchall()
    finally:
        connection.close()

    observed_count = len(stored_rows)
    if observed_count == 0:
        state = "absent"
    elif observed_count < expected_count:
        state = "partial"
    else:
        expected_by_id = {row[0]: row for row in expected_rows}
        stored_by_id = {row[0]: tuple(row) for row in stored_rows}
        state = "complete" if stored_by_id == expected_by_id else "conflict"
    return {
        "state": state,
        "expected_count": expected_count,
        "observed_count": observed_count,
    }


def append_canonical_page_replay_safe(database_path, rows):
    inspection = inspect_canonical_page_state(database_path, rows)
    state = inspection["state"]
    if state == "absent":
        append_page(database_path, rows)
        return {"status": "created", "canonical_count": len(rows)}
    if state == "complete":
        return {"status": "existing", "canonical_count": len(rows)}
    if state in {"partial", "conflict"}:
        raise RuntimeError(
            f"canonical page state is {state}: "
            f"expected_count={inspection['expected_count']}, "
            f"observed_count={inspection['observed_count']}"
        )
    raise RuntimeError(f"unexpected canonical page inspection state: {state!r}")


def persist_prepared_page_transaction(
    database_path,
    quarantine_path,
    prepared_transaction,
    expected_prior_quarantine_count,
    run_id,
    failure_evidence_path,
):
    classification = prepared_transaction["classification"]
    valid_rows = classification["valid_rows"]
    quarantine_records = build_page_quarantine_records(
        prepared_transaction, run_id, failure_evidence_path
    )
    canonical_result = append_canonical_page_replay_safe(database_path, valid_rows)
    quarantine_result = append_page_quarantine_records(
        quarantine_path,
        quarantine_records,
        expected_prior_quarantine_count,
    )
    return {
        "canonical_status": canonical_result["status"],
        "canonical_count": canonical_result["canonical_count"],
        "quarantine_created_count": quarantine_result["created_count"],
        "quarantine_existing_count": quarantine_result["existing_count"],
        "quarantine_total_count": quarantine_result["total_count"],
        "page_valid_row_count": len(valid_rows),
        "page_invalid_row_count": len(classification["invalid_rows"]),
    }


def derive_next_page_accounting(
    source_rows_processed,
    canonical_rows_collected,
    quarantine_rows,
    persistence_result,
):
    cumulative_counters = {
        "source_rows_processed": source_rows_processed,
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
    }
    for name, value in cumulative_counters.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if source_rows_processed != canonical_rows_collected + quarantine_rows:
        raise ValueError("existing page accounting invariant is invalid")
    if not isinstance(persistence_result, dict):
        raise ValueError("persistence_result must be a dict")

    count_fields = (
        "canonical_count",
        "quarantine_created_count",
        "quarantine_existing_count",
        "quarantine_total_count",
        "page_valid_row_count",
        "page_invalid_row_count",
    )
    required_fields = ("canonical_status", *count_fields)
    for field in required_fields:
        if field not in persistence_result:
            raise ValueError(f"persistence_result is missing {field}")
    for field in count_fields:
        value = persistence_result[field]
        if type(value) is not int or value < 0:
            raise ValueError(f"persistence_result {field} must be a non-negative integer")

    canonical_status = persistence_result["canonical_status"]
    if canonical_status not in {"created", "existing"}:
        raise ValueError(f"unsupported canonical_status: {canonical_status!r}")
    page_valid_row_count = persistence_result["page_valid_row_count"]
    page_invalid_row_count = persistence_result["page_invalid_row_count"]
    if persistence_result["canonical_count"] != page_valid_row_count:
        raise ValueError("canonical_count must equal page_valid_row_count")
    if (
        persistence_result["quarantine_created_count"]
        + persistence_result["quarantine_existing_count"]
        != page_invalid_row_count
    ):
        raise ValueError(
            "quarantine created and existing counts must equal page_invalid_row_count"
        )
    expected_quarantine_total_count = quarantine_rows + page_invalid_row_count
    if persistence_result["quarantine_total_count"] != expected_quarantine_total_count:
        raise ValueError(
            "quarantine_total_count must equal prior quarantine_rows plus "
            "page_invalid_row_count"
        )

    next_accounting = {
        "source_rows_processed": (
            source_rows_processed + page_valid_row_count + page_invalid_row_count
        ),
        "canonical_rows_collected": (
            canonical_rows_collected + page_valid_row_count
        ),
        "quarantine_rows": quarantine_rows + page_invalid_row_count,
    }
    if next_accounting["source_rows_processed"] != (
        next_accounting["canonical_rows_collected"]
        + next_accounting["quarantine_rows"]
    ):
        raise ValueError("derived page accounting invariant is invalid")
    return next_accounting


def persist_account_and_checkpoint_page(
    database_path,
    quarantine_path,
    prepared_transaction,
    expected_prior_quarantine_count,
    run_id,
    failure_evidence_path,
    source_rows_processed,
    canonical_rows_collected,
    quarantine_rows,
    checkpoint_path,
    config,
    run_dir,
    source_count,
    page_count,
    started_at,
    retries_used,
):
    persistence_result = persist_prepared_page_transaction(
        database_path,
        quarantine_path,
        prepared_transaction,
        expected_prior_quarantine_count,
        run_id,
        failure_evidence_path,
    )
    next_accounting = derive_next_page_accounting(
        source_rows_processed,
        canonical_rows_collected,
        quarantine_rows,
        persistence_result,
    )
    write_checkpoint(
        checkpoint_path,
        config,
        run_dir,
        next_accounting["source_rows_processed"],
        next_accounting["canonical_rows_collected"],
        next_accounting["quarantine_rows"],
        source_count,
        page_count,
        started_at,
        retries_used,
    )
    return {
        "persistence_result": persistence_result,
        "next_accounting": next_accounting,
    }


def classify_quarantine_resume_physical_state(
    canonical_rows_collected,
    quarantine_rows,
    database_rows,
    distinct_ids,
    actual_quarantine_count,
    page_size,
):
    numeric_arguments = {
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
        "database_rows": database_rows,
        "distinct_ids": distinct_ids,
        "actual_quarantine_count": actual_quarantine_count,
        "page_size": page_size,
    }
    for name, value in numeric_arguments.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")

    if distinct_ids != database_rows:
        raise RuntimeError("physical canonical row count does not match distinct ids")
    if database_rows < canonical_rows_collected:
        raise RuntimeError("physical canonical count trails checkpoint")
    if actual_quarantine_count < quarantine_rows:
        raise RuntimeError("physical quarantine count trails checkpoint")

    canonical_ahead_count = database_rows - canonical_rows_collected
    quarantine_ahead_count = actual_quarantine_count - quarantine_rows
    physical_ahead_count = canonical_ahead_count + quarantine_ahead_count
    if physical_ahead_count == 0:
        state = "consistent"
    elif physical_ahead_count <= page_size:
        state = "replay_candidate"
    else:
        raise RuntimeError("physical persistence is ahead by more than one page")
    return {
        "state": state,
        "canonical_ahead_count": canonical_ahead_count,
        "quarantine_ahead_count": quarantine_ahead_count,
        "physical_ahead_count": physical_ahead_count,
    }


def verify_quarantine_replay_candidate(
    database_path,
    quarantine_path,
    prepared_transaction,
    canonical_rows_collected,
    quarantine_rows,
    run_id,
    failure_evidence_path,
):
    checkpoint_counts = {
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
    }
    for name, value in checkpoint_counts.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")

    valid_rows = prepared_transaction["classification"]["valid_rows"]
    expected_quarantine_records = build_page_quarantine_records(
        prepared_transaction, run_id, failure_evidence_path
    )
    canonical_inspection = inspect_canonical_page_state(database_path, valid_rows)
    expected_canonical_state = "complete" if valid_rows else "absent"
    if canonical_inspection["state"] != expected_canonical_state:
        raise RuntimeError(
            "prepared canonical page is not exactly present for replay: "
            f"observed {canonical_inspection['state']!r}"
        )

    canonical_page_count = len(valid_rows)
    quarantine_page_count = len(expected_quarantine_records)
    expected_canonical_total = canonical_rows_collected + canonical_page_count
    expected_quarantine_total = quarantine_rows + quarantine_page_count
    database_rows, distinct_ids, _, _ = verify_database(database_path)
    prepared_page_count = canonical_page_count + quarantine_page_count
    if prepared_page_count < 1:
        raise RuntimeError("an empty prepared page cannot prove a replay candidate")
    actual_quarantine_total = count_quarantine_records(quarantine_path)
    physical_state = classify_quarantine_resume_physical_state(
        canonical_rows_collected,
        quarantine_rows,
        database_rows,
        distinct_ids,
        actual_quarantine_total,
        prepared_page_count,
    )
    if database_rows != expected_canonical_total:
        raise RuntimeError(
            "physical canonical total does not match expected replay total"
        )
    if actual_quarantine_total != expected_quarantine_total:
        raise RuntimeError(
            "physical quarantine total does not match expected replay total"
        )
    if (
        physical_state["state"] != "replay_candidate"
        or physical_state["canonical_ahead_count"] != canonical_page_count
        or physical_state["quarantine_ahead_count"] != quarantine_page_count
    ):
        raise RuntimeError("physical state does not exactly match the prepared replay page")

    quarantine_directory = Path(quarantine_path)
    for expected_record in expected_quarantine_records:
        record_path = quarantine_directory / (
            f"{expected_record['quarantine_record_id']}.json"
        )
        persisted_record = read_quarantine_record(record_path)
        if canonical_json_bytes(persisted_record) != canonical_json_bytes(
            expected_record
        ):
            raise RuntimeError("persisted quarantine record does not match expected replay")
    return {
        "verified": True,
        "canonical_page_count": canonical_page_count,
        "quarantine_page_count": quarantine_page_count,
        "expected_canonical_total": expected_canonical_total,
        "expected_quarantine_total": expected_quarantine_total,
    }


def derive_quarantine_replay_reconciliation(
    source_rows_processed,
    canonical_rows_collected,
    quarantine_rows,
    prepared_transaction,
    replay_verification,
):
    cumulative_counters = {
        "source_rows_processed": source_rows_processed,
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
    }
    for name, value in cumulative_counters.items():
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    if source_rows_processed != canonical_rows_collected + quarantine_rows:
        raise ValueError("existing replay accounting invariant is invalid")

    if not isinstance(prepared_transaction, Mapping):
        raise ValueError("prepared_transaction must be a mapping")
    classification = prepared_transaction.get("classification")
    if not isinstance(classification, Mapping):
        raise ValueError("prepared_transaction classification must be a mapping")
    for field in ("valid_rows", "invalid_rows"):
        if field not in classification or not isinstance(classification[field], list):
            raise ValueError(f"prepared transaction {field} must be a list")
    prepared_valid_count = len(classification["valid_rows"])
    prepared_invalid_count = len(classification["invalid_rows"])

    if not isinstance(replay_verification, Mapping):
        raise ValueError("replay_verification must be a mapping")
    if replay_verification.get("verified") is not True:
        raise ValueError("replay_verification verified must be exactly True")
    count_fields = (
        "canonical_page_count",
        "quarantine_page_count",
        "expected_canonical_total",
        "expected_quarantine_total",
    )
    for field in count_fields:
        if field not in replay_verification:
            raise ValueError(f"replay_verification is missing {field}")
        value = replay_verification[field]
        if type(value) is not int or value < 0:
            raise ValueError(
                f"replay_verification {field} must be a non-negative integer"
            )

    canonical_page_count = replay_verification["canonical_page_count"]
    quarantine_page_count = replay_verification["quarantine_page_count"]
    expected_canonical_total = replay_verification["expected_canonical_total"]
    expected_quarantine_total = replay_verification["expected_quarantine_total"]
    if canonical_page_count != prepared_valid_count:
        raise ValueError("canonical_page_count must equal prepared valid-row count")
    if quarantine_page_count != prepared_invalid_count:
        raise ValueError("quarantine_page_count must equal prepared invalid-row count")
    if canonical_page_count + quarantine_page_count == 0:
        raise ValueError("replay page must contain at least one source row")
    if expected_canonical_total != canonical_rows_collected + canonical_page_count:
        raise ValueError("expected_canonical_total does not match replay accounting")
    if expected_quarantine_total != quarantine_rows + quarantine_page_count:
        raise ValueError("expected_quarantine_total does not match replay accounting")

    next_accounting = {
        "source_rows_processed": (
            source_rows_processed + canonical_page_count + quarantine_page_count
        ),
        "canonical_rows_collected": expected_canonical_total,
        "quarantine_rows": expected_quarantine_total,
    }
    if next_accounting["source_rows_processed"] != (
        next_accounting["canonical_rows_collected"]
        + next_accounting["quarantine_rows"]
    ):
        raise ValueError("derived replay accounting invariant is invalid")
    return next_accounting


def write_quarantine_replay_reconciliation_checkpoint(
    checkpoint_path,
    config,
    run_dir,
    reconciliation_accounting,
    source_count,
    page_count,
    started_at,
    retries_used,
):
    if not isinstance(reconciliation_accounting, Mapping):
        raise ValueError("reconciliation_accounting must be a mapping")
    accounting_fields = {
        "source_rows_processed",
        "canonical_rows_collected",
        "quarantine_rows",
    }
    if set(reconciliation_accounting) != accounting_fields:
        raise ValueError(
            "reconciliation_accounting must contain exactly the cumulative "
            "accounting fields"
        )
    for field in accounting_fields:
        value = reconciliation_accounting[field]
        if type(value) is not int or value < 0:
            raise ValueError(
                f"reconciliation_accounting {field} must be a non-negative integer"
            )

    source_rows_processed = reconciliation_accounting["source_rows_processed"]
    canonical_rows_collected = reconciliation_accounting[
        "canonical_rows_collected"
    ]
    quarantine_rows = reconciliation_accounting["quarantine_rows"]
    if source_rows_processed != canonical_rows_collected + quarantine_rows:
        raise ValueError("reconciliation accounting invariant is invalid")

    write_checkpoint(
        checkpoint_path,
        config,
        run_dir,
        source_rows_processed,
        canonical_rows_collected,
        quarantine_rows,
        source_count,
        page_count,
        started_at,
        retries_used,
    )
    return {
        "source_rows_processed": source_rows_processed,
        "canonical_rows_collected": canonical_rows_collected,
        "quarantine_rows": quarantine_rows,
    }


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


def verify_database(path: Path) -> tuple[int, int, int | None, int | None]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        row = connection.execute(
            "select count(*), count(distinct id), min(id), max(id) from sirup_raw"
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise RuntimeError("database verification returned no result")
    try:
        row_count = int(row[0])
        distinct_id_count = int(row[1])
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("database verification returned invalid counts") from exc
    if row_count < 0 or distinct_id_count < 0:
        raise RuntimeError("database verification returned negative counts")
    if distinct_id_count > row_count:
        raise RuntimeError("database verification returned too many distinct ids")

    min_id, max_id = row[2], row[3]
    if row_count == 0:
        if distinct_id_count != 0 or min_id is not None or max_id is not None:
            raise RuntimeError("database verification returned inconsistent empty aggregates")
        return 0, 0, None, None
    if min_id is None or max_id is None:
        raise RuntimeError("database verification returned null bounds for non-empty table")
    try:
        return row_count, distinct_id_count, int(min_id), int(max_id)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RuntimeError("database verification returned invalid bounds") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch SiRUP data into isolated staging.")
    parser.add_argument("--year", type=int, required=True, help="Explicit SiRUP budget year.")
    parser.add_argument(
        "--mode",
        choices=("strict", "quarantine"),
        default="strict",
        help="Collection mode (default: strict).",
    )
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
        config = checkpoint_config(
            args.year, args.page_size, args.full_snapshot, args.mode
        )
        checkpoint_path = args.checkpoint.resolve() if args.checkpoint else None
        if args.mode == "quarantine" and checkpoint_path is None:
            raise RuntimeError("quarantine mode requires --checkpoint")
        if checkpoint_path and checkpoint_path.is_file():
            (
                run_dir,
                source_rows_processed,
                canonical_rows_collected,
                quarantine_rows,
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
            if (
                database_rows != canonical_rows_collected
                or distinct_ids != database_rows
            ):
                raise RuntimeError("checkpoint canonical count does not match staging database")
            if not args.full_snapshot and canonical_rows_collected > args.max_rows:
                raise RuntimeError("checkpoint contains more rows than --max-rows")
            if args.mode == "quarantine":
                actual_quarantine_count = count_quarantine_records(
                    run_dir / QUARANTINE_PATH_NAME
                )
                if actual_quarantine_count != quarantine_rows:
                    raise RuntimeError(
                        "checkpoint quarantine count does not match quarantine store"
                    )
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
            source_rows_processed = 0
            canonical_rows_collected = 0
            quarantine_rows = 0
            source_count = 0
            page_count = 0
            retries_used = 0
        run_id = run_dir.name
        manifest_path = run_dir / "manifest.json"
        expected_source_count: int | None = (
            source_count if source_rows_processed else None
        )
        target_row_count = expected_source_count if args.full_snapshot else args.max_rows
        if target_row_count is not None and source_rows_processed > target_row_count:
            raise RuntimeError("checkpoint contains more rows than the target row count")
        while target_row_count is None or source_rows_processed < target_row_count:
            length = args.page_size if target_row_count is None else min(
                args.page_size, target_row_count - source_rows_processed
            )
            payload, page_retries = fetch_page(
                session,
                args.year,
                start=source_rows_processed,
                length=length,
                draw=page_count + 1,
                timeout=args.timeout,
                retries=args.retries,
            )
            if args.mode == "strict":
                page_rows, expected_source_count = validate_page(
                    run_dir,
                    payload,
                    expected_source_count,
                    args.year,
                    source_rows_processed,
                    length,
                    page_count + 1,
                    args.full_snapshot,
                )
                if args.full_snapshot:
                    target_row_count = expected_source_count
                append_page(database_path, page_rows)
                source_rows_processed += len(page_rows)
                canonical_rows_collected += len(page_rows)
                retries_used += page_retries
                page_count += 1
                if checkpoint_path:
                    write_checkpoint(
                        checkpoint_path,
                        config,
                        run_dir,
                        source_rows_processed=source_rows_processed,
                        canonical_rows_collected=canonical_rows_collected,
                        quarantine_rows=quarantine_rows,
                        source_count=expected_source_count,
                        page_count=page_count,
                        started_at=started_at,
                        retries_used=retries_used,
                    )
            else:
                prepared_transaction = prepare_page_transaction(
                    payload,
                    expected_source_count,
                    run_id,
                    args.year,
                    source_rows_processed,
                    length,
                    page_count + 1,
                    args.full_snapshot,
                )
                expected_source_count = prepared_transaction["verified_source_count"]
                if args.full_snapshot:
                    target_row_count = expected_source_count
                failure_evidence_path = (
                    run_dir
                    / "failures"
                    / (
                        f"page-start-{source_rows_processed}-"
                        f"draw-{page_count + 1}.json"
                    )
                )
                page_result = persist_account_and_checkpoint_page(
                    database_path,
                    run_dir / QUARANTINE_PATH_NAME,
                    prepared_transaction,
                    quarantine_rows,
                    run_id,
                    failure_evidence_path,
                    source_rows_processed,
                    canonical_rows_collected,
                    quarantine_rows,
                    checkpoint_path,
                    config,
                    run_dir,
                    expected_source_count,
                    page_count + 1,
                    started_at,
                    retries_used + page_retries,
                )
                next_accounting = page_result["next_accounting"]
                source_rows_processed = next_accounting["source_rows_processed"]
                canonical_rows_collected = next_accounting[
                    "canonical_rows_collected"
                ]
                quarantine_rows = next_accounting["quarantine_rows"]
                retries_used += page_retries
                page_count += 1
            if (
                args.stop_after_rows is not None
                and source_rows_processed >= args.stop_after_rows
                and source_rows_processed < target_row_count
            ):
                print(
                    "controlled stop after source rows processed: "
                    f"{source_rows_processed}"
                )
                print(f"staging database: {database_path}")
                print(f"checkpoint: {checkpoint_path}")
                session.close()
                return 0
            if target_row_count is None or source_rows_processed < target_row_count:
                time.sleep(args.delay)
        if expected_source_count is None:
            raise RuntimeError("source record count was not collected")
        row_count, distinct_ids, min_id, max_id = verify_database(database_path)
        if row_count != canonical_rows_collected or distinct_ids != row_count:
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
