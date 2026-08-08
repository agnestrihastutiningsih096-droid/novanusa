"""Immutable source-position provenance records for SiRUP collection."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from sirup_quarantine_store import canonical_json_bytes


PROVENANCE_RECORD_VERSION = 1
_DISPOSITIONS = {"canonical", "quarantine"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PAGE_IDENTITY_KEYS = {
    "run_id", "page_start", "requested_length", "page_draw", "payload_sha256"
}
_RECORD_KEYS = {
    "provenance_record_version", "provenance_record_id", "run_id",
    "source_offset", "page_start", "requested_length", "page_draw",
    "row_index", "disposition", "package_id", "row_sha256",
    "payload_sha256", "page_identity", "captured_at", "content_sha256",
}


def _require_nonempty_string(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


def _require_nonnegative_int(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _require_sha256(value: Any, name: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _record_id(run_id: str, source_offset: int) -> str:
    return _sha256({
        "provenance_record_version": PROVENANCE_RECORD_VERSION,
        "run_id": run_id,
        "source_offset": source_offset,
    })


def _content_sha256(record: dict[str, Any]) -> str:
    return _sha256({
        key: value for key, value in record.items() if key != "content_sha256"
    })


def build_source_provenance_record(
    page_identity: dict[str, Any],
    row_index: int,
    disposition: str,
    raw_row: Any,
    captured_at: str,
) -> dict[str, Any]:
    if not isinstance(page_identity, dict) or set(page_identity) != _PAGE_IDENTITY_KEYS:
        raise ValueError("page_identity has an invalid schema")
    run_id = page_identity["run_id"]
    page_start = page_identity["page_start"]
    requested_length = page_identity["requested_length"]
    page_draw = page_identity["page_draw"]
    payload_sha256 = page_identity["payload_sha256"]
    _require_nonempty_string(run_id, "run_id")
    for name, value in (
        ("page_start", page_start),
        ("requested_length", requested_length),
        ("page_draw", page_draw),
        ("row_index", row_index),
    ):
        _require_nonnegative_int(value, name)
    if row_index >= requested_length:
        raise ValueError("row_index must be less than requested_length")
    if disposition not in _DISPOSITIONS:
        raise ValueError("disposition must be 'canonical' or 'quarantine'")
    _require_sha256(payload_sha256, "payload_sha256")
    _require_nonempty_string(captured_at, "captured_at")
    row_sha256 = _sha256(raw_row)
    source_offset = page_start + row_index
    record = {
        "provenance_record_version": PROVENANCE_RECORD_VERSION,
        "provenance_record_id": _record_id(run_id, source_offset),
        "run_id": run_id,
        "source_offset": source_offset,
        "page_start": page_start,
        "requested_length": requested_length,
        "page_draw": page_draw,
        "row_index": row_index,
        "disposition": disposition,
        "package_id": raw_row.get("id") if isinstance(raw_row, dict) else None,
        "row_sha256": row_sha256,
        "payload_sha256": payload_sha256,
        "page_identity": dict(page_identity),
        "captured_at": captured_at,
    }
    record["content_sha256"] = _content_sha256(record)
    return record


def validate_source_provenance_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("provenance record must be a JSON object")
    if set(record) != _RECORD_KEYS:
        raise ValueError("provenance record has an invalid schema")
    if record["provenance_record_version"] != PROVENANCE_RECORD_VERSION:
        raise ValueError("unsupported provenance_record_version")
    _require_nonempty_string(record["run_id"], "run_id")
    for name in (
        "source_offset", "page_start", "requested_length", "page_draw", "row_index"
    ):
        _require_nonnegative_int(record[name], name)
    if record["row_index"] >= record["requested_length"]:
        raise ValueError("row_index must be less than requested_length")
    if record["source_offset"] != record["page_start"] + record["row_index"]:
        raise ValueError("invalid source_offset")
    if record["disposition"] not in _DISPOSITIONS:
        raise ValueError("invalid disposition")
    _require_sha256(record["row_sha256"], "row_sha256")
    _require_sha256(record["payload_sha256"], "payload_sha256")
    _require_nonempty_string(record["captured_at"], "captured_at")
    page_identity = record["page_identity"]
    if not isinstance(page_identity, dict) or set(page_identity) != _PAGE_IDENTITY_KEYS:
        raise ValueError("page_identity has an invalid schema")
    for name in _PAGE_IDENTITY_KEYS:
        if type(page_identity[name]) is not type(record[name]) or page_identity[name] != record[name]:
            raise ValueError(f"page_identity {name} does not match record")
    expected_id = _record_id(record["run_id"], record["source_offset"])
    if record["provenance_record_id"] != expected_id:
        raise ValueError("invalid provenance_record_id")
    if record["content_sha256"] != _content_sha256(record):
        raise ValueError("invalid content_sha256")
    canonical_json_bytes(record["package_id"])
    return record


def read_source_provenance_record(path: os.PathLike[str] | str) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            record = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid provenance record file") from error
    return validate_source_provenance_record(record)


def append_source_provenance_record(
    provenance_path: os.PathLike[str] | str,
    record: dict[str, Any],
) -> str:
    validate_source_provenance_record(record)
    directory = Path(provenance_path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{record['provenance_record_id']}.json"
    data = canonical_json_bytes(record) + b"\n"
    if target.exists():
        try:
            existing = read_source_provenance_record(target)
        except ValueError as error:
            raise RuntimeError("provenance record conflict") from error
        if canonical_json_bytes(existing) + b"\n" == data:
            return "existing"
        raise RuntimeError("provenance record conflict")

    temporary = directory / f".{record['provenance_record_id']}.json.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if temporary.read_bytes() != data:
            raise RuntimeError("provenance temporary record conflict")
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    try:
        os.link(temporary, target)
    except FileExistsError:
        try:
            existing = read_source_provenance_record(target)
        except ValueError as error:
            raise RuntimeError("provenance record conflict") from error
        if canonical_json_bytes(existing) + b"\n" != data:
            raise RuntimeError("provenance record conflict")
        temporary.unlink(missing_ok=True)
        return "existing"
    except OSError:
        raise
    temporary.unlink()
    return "created"
