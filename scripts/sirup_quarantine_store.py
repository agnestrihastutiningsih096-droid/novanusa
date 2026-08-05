"""Immutable, replay-safe storage for SiRUP quarantine records."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECORD_KEYS = {
    "quarantine_record_version", "quarantine_record_id", "run_id",
    "page_identity", "source_offset", "page_start", "requested_length",
    "page_draw", "row_index", "package_id", "raw_row", "missing_fields",
    "invalid_fields", "validation_error", "captured_at", "payload_sha256",
    "request_parameters", "failure_evidence_path", "content_sha256",
}
_PAGE_IDENTITY_KEYS = {
    "run_id", "page_start", "requested_length", "page_draw", "payload_sha256"
}


def canonical_json_bytes(value: Any) -> bytes:
    """Return the deterministic UTF-8 JSON representation of *value*."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_nonempty_string(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_nonnegative_int(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_sha256(value: Any, name: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")


def _normalise_field_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(f"{name} must be a list of non-empty strings")
    return sorted(set(value))


def _identity_digest(run_id: str, page_start: int, row_index: int,
                     payload_sha256: str) -> str:
    identity = {
        "identity_version": 1,
        "run_id": run_id,
        "page_start": page_start,
        "row_index": row_index,
        "payload_sha256": payload_sha256,
    }
    return hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


def _content_digest(record: dict[str, Any]) -> str:
    content = {key: value for key, value in record.items()
               if key != "content_sha256"}
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def build_quarantine_record(
    run_id: str, page_start: int, requested_length: int, page_draw: int,
    row_index: int, raw_row: dict[str, Any], missing_fields: list[str],
    invalid_fields: list[str], validation_error: str, captured_at: str,
    payload_sha256: str, request_parameters: dict[str, Any],
    failure_evidence_path: str,
) -> dict[str, Any]:
    _require_nonempty_string(run_id, "run_id")
    for name, value in (("page_start", page_start),
                        ("requested_length", requested_length),
                        ("page_draw", page_draw), ("row_index", row_index)):
        _require_nonnegative_int(value, name)
    if row_index >= requested_length:
        raise ValueError("row_index must be less than requested_length")
    _require_sha256(payload_sha256, "payload_sha256")
    _require_nonempty_string(validation_error, "validation_error")
    _require_nonempty_string(captured_at, "captured_at")
    _require_nonempty_string(failure_evidence_path, "failure_evidence_path")
    if not isinstance(raw_row, dict):
        raise ValueError("raw_row must be a JSON object")
    if not isinstance(request_parameters, dict):
        raise ValueError("request_parameters must be a JSON object")
    missing = _normalise_field_list(missing_fields, "missing_fields")
    invalid = _normalise_field_list(invalid_fields, "invalid_fields")
    # Validate all supplied JSON values before constructing a record.
    canonical_json_bytes(raw_row)
    canonical_json_bytes(request_parameters)

    record: dict[str, Any] = {
        "quarantine_record_version": 1,
        "quarantine_record_id": _identity_digest(
            run_id, page_start, row_index, payload_sha256),
        "run_id": run_id,
        "page_identity": {
            "run_id": run_id, "page_start": page_start,
            "requested_length": requested_length, "page_draw": page_draw,
            "payload_sha256": payload_sha256,
        },
        "source_offset": page_start + row_index,
        "page_start": page_start,
        "requested_length": requested_length,
        "page_draw": page_draw,
        "row_index": row_index,
        "package_id": raw_row.get("id"),
        "raw_row": raw_row,
        "missing_fields": missing,
        "invalid_fields": invalid,
        "validation_error": validation_error,
        "captured_at": captured_at,
        "payload_sha256": payload_sha256,
        "request_parameters": request_parameters,
        "failure_evidence_path": failure_evidence_path,
    }
    record["content_sha256"] = _content_digest(record)
    return record


def _validate_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("quarantine record must be a JSON object")
    if set(record) != _RECORD_KEYS:
        raise ValueError("quarantine record has an invalid schema")
    if record["quarantine_record_version"] != 1:
        raise ValueError("unsupported quarantine_record_version")

    _require_nonempty_string(record["run_id"], "run_id")
    for name in ("page_start", "requested_length", "page_draw", "row_index"):
        _require_nonnegative_int(record[name], name)
    if record["row_index"] >= record["requested_length"]:
        raise ValueError("row_index must be less than requested_length")
    if record["source_offset"] != record["page_start"] + record["row_index"]:
        raise ValueError("invalid source_offset")
    if not isinstance(record["raw_row"], dict):
        raise ValueError("raw_row must be a JSON object")
    if not isinstance(record["request_parameters"], dict):
        raise ValueError("request_parameters must be a JSON object")
    for name in ("missing_fields", "invalid_fields"):
        value = record[name]
        if (not isinstance(value, list)
                or any(not isinstance(item, str) or not item for item in value)
                or value != sorted(set(value))):
            raise ValueError(f"{name} must be sorted and deduplicated")
    _require_nonempty_string(record["validation_error"], "validation_error")
    _require_nonempty_string(record["captured_at"], "captured_at")
    _require_nonempty_string(
        record["failure_evidence_path"], "failure_evidence_path")
    _require_sha256(record["payload_sha256"], "payload_sha256")
    if record["package_id"] != record["raw_row"].get("id"):
        raise ValueError("invalid package_id")
    if (not isinstance(record["page_identity"], dict)
            or set(record["page_identity"]) != _PAGE_IDENTITY_KEYS):
        raise ValueError("page_identity has an invalid schema")
    for name in _PAGE_IDENTITY_KEYS:
        page_value = record["page_identity"][name]
        if type(page_value) is not type(record[name]) or page_value != record[name]:
            raise ValueError(f"page_identity {name} does not match record")
    expected_id = _identity_digest(
        record["run_id"], record["page_start"], record["row_index"],
        record["payload_sha256"])
    if record["quarantine_record_id"] != expected_id:
        raise ValueError("invalid quarantine_record_id")
    # Computing the digest also proves every part of the record is canonical-JSON
    # serializable. Stored content is inspected as-is and is never normalized.
    expected_content_digest = _content_digest(record)
    if record["content_sha256"] != expected_content_digest:
        raise ValueError("invalid content_sha256")
    return record


def append_quarantine_record(quarantine_path: os.PathLike[str] | str,
                             record: dict[str, Any]) -> str:
    _validate_record(record)
    directory = Path(quarantine_path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{record['quarantine_record_id']}.json"
    data = canonical_json_bytes(record) + b"\n"

    if target.exists():
        try:
            existing = read_quarantine_record(target)
        except ValueError as error:
            raise RuntimeError("quarantine record conflict") from error
        if canonical_json_bytes(existing) + b"\n" == data:
            return "existing"
        raise RuntimeError("quarantine record conflict")

    temporary = directory / f".{record['quarantine_record_id']}.json.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if temporary.read_bytes() != data:
            raise RuntimeError("quarantine temporary record conflict")
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    try:
        os.link(temporary, target)
    except FileExistsError:
        try:
            existing = read_quarantine_record(target)
        except ValueError as error:
            raise RuntimeError("quarantine record conflict") from error
        if canonical_json_bytes(existing) + b"\n" != data:
            raise RuntimeError("quarantine record conflict")
        temporary.unlink(missing_ok=True)
        return "existing"
    except OSError:
        # Preserve the complete deterministic temporary file for diagnosis.
        raise
    temporary.unlink()
    return "created"


def read_quarantine_record(path: os.PathLike[str] | str) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid quarantine record file") from error
    return _validate_record(value)


def count_quarantine_records(quarantine_path: os.PathLike[str] | str) -> int:
    directory = Path(quarantine_path)
    if not directory.exists():
        return 0
    if not directory.is_dir():
        raise ValueError("quarantine_path is not a directory")
    count = 0
    for path in directory.glob("*.json"):
        read_quarantine_record(path)
        count += 1
    return count
