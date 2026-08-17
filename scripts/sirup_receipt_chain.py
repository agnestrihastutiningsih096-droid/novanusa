from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


RECEIPTS_NAME = "receipts.jsonl"
DATABASE_NAME = "sirup_staging.duckdb"
GENESIS_DERIVATION = "NOVANUSA-SIRUP-RECEIPT-CHAIN-V1-GENESIS"
GENESIS_PREVIOUS_HASH = hashlib.sha256(GENESIS_DERIVATION.encode("utf-8")).hexdigest()
RECEIPT_TYPES = frozenset({"ANCHOR", "PAGE", "RETRY", "RESUME", "COMPLETION", "ABORT"})
TERMINAL_TYPES = frozenset({"COMPLETION", "ABORT"})
ENVELOPE_FIELDS = frozenset(
    {"receipt_type", "sequence", "run_id", "timestamp", "previous_hash", "payload", "hash"}
)
HASH_FIELDS = frozenset(ENVELOPE_FIELDS - {"hash"})
PAYLOAD_FIELDS = {
    "ANCHOR": frozenset(
        {"endpoint", "year", "page_size", "order_column", "order_direction", "full_snapshot", "mode"}
    ),
    "PAGE": frozenset(
        {"start", "page_size", "returned_row_count", "canonical_row_count", "quarantined_row_count", "page_rows_digest", "source_count_observed"}
    ),
    "RETRY": frozenset({"start", "page_size", "error_class", "retry_index"}),
    "RESUME": frozenset({"checkpoint_snapshot", "processed", "next_start", "last_completed_page", "retries"}),
    "COMPLETION": frozenset(
        {"terminal_reason", "processed", "canonical_total", "quarantine_total", "source_count_start", "source_count_end", "drift_status", "duckdb_sha256", "promotion_flag"}
    ),
    "ABORT": frozenset(
        {"terminal_reason", "error_class", "failure_stage", "processed", "canonical_total", "quarantined_total", "duckdb_sha256"}
    ),
}
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


class ReceiptChainError(RuntimeError):
    pass


def _reject_floats(value: Any) -> None:
    if isinstance(value, float):
        raise ReceiptChainError("floats are forbidden")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ReceiptChainError("object keys must be strings")
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_floats(item)
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise ReceiptChainError("unsupported canonical value")


def canonical_json(value: Any) -> str:
    _reject_floats(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise ReceiptChainError("invalid receipt timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ReceiptChainError("invalid receipt timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" != value:
        raise ReceiptChainError("invalid receipt timestamp")
    return value


def receipt_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _is_int(value: Any, *, minimum: int = 0) -> bool:
    return type(value) is int and value >= minimum


def _validate_payload(receipt_type: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != PAYLOAD_FIELDS[receipt_type]:
        raise ReceiptChainError(f"invalid {receipt_type} payload fields")
    _reject_floats(payload)
    integer_fields = {
        "ANCHOR": ("year", "page_size", "order_column"),
        "PAGE": ("start", "page_size", "returned_row_count", "canonical_row_count", "quarantined_row_count", "source_count_observed"),
        "RETRY": ("start", "page_size", "retry_index"),
        "RESUME": ("processed", "next_start", "last_completed_page", "retries"),
        "COMPLETION": ("processed", "canonical_total", "quarantine_total", "source_count_start", "source_count_end"),
        "ABORT": ("processed", "canonical_total", "quarantined_total"),
    }[receipt_type]
    if any(not _is_int(payload[field]) for field in integer_fields):
        raise ReceiptChainError(f"invalid {receipt_type} integer field")
    if receipt_type in {"ANCHOR", "PAGE", "RETRY"} and payload["page_size"] < 1:
        raise ReceiptChainError("page_size must be positive")
    if receipt_type == "ANCHOR":
        if type(payload["full_snapshot"]) is not bool:
            raise ReceiptChainError("full_snapshot must be boolean")
    if receipt_type == "PAGE":
        if payload["returned_row_count"] != payload["canonical_row_count"] + payload["quarantined_row_count"]:
            raise ReceiptChainError("PAGE accounting mismatch")
        if not LOWER_HEX_64.fullmatch(str(payload["page_rows_digest"])):
            raise ReceiptChainError("invalid page_rows_digest")
    if receipt_type == "RETRY" and payload["retry_index"] < 1:
        raise ReceiptChainError("retry_index must be positive")
    if receipt_type == "RESUME" and not isinstance(payload["checkpoint_snapshot"], dict):
        raise ReceiptChainError("checkpoint_snapshot must be an object")
    if receipt_type == "COMPLETION":
        if payload["terminal_reason"] != "NORMAL_COMPLETION":
            raise ReceiptChainError("invalid completion terminal_reason")
        if payload["promotion_flag"] is not False:
            raise ReceiptChainError("completion promotion_flag must be false")
        if payload["processed"] != payload["canonical_total"] + payload["quarantine_total"]:
            raise ReceiptChainError("COMPLETION accounting mismatch")
        if not LOWER_HEX_64.fullmatch(str(payload["duckdb_sha256"])):
            raise ReceiptChainError("invalid duckdb_sha256")
    if receipt_type == "ABORT":
        if payload["processed"] != payload["canonical_total"] + payload["quarantined_total"]:
            raise ReceiptChainError("ABORT accounting mismatch")
        if not LOWER_HEX_64.fullmatch(str(payload["duckdb_sha256"])):
            raise ReceiptChainError("invalid duckdb_sha256")
    return payload


def _receipt_hash(preimage: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(dict(preimage)).encode("utf-8")).hexdigest()


def _parse_lines(path: Path) -> list[dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ReceiptChainError("receipt file is not readable") from exc
    if not data:
        raise ReceiptChainError("receipt chain is empty")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReceiptChainError("receipt file is not valid UTF-8") from exc
    if not text.endswith("\n"):
        raise ReceiptChainError("receipt file has a truncated line")
    receipts: list[dict[str, Any]] = []
    for raw in text.splitlines():
        try:
            receipt = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReceiptChainError("receipt line is malformed JSON") from exc
        if not isinstance(receipt, dict):
            raise ReceiptChainError("receipt line is not an object")
        if canonical_json(receipt) != raw:
            raise ReceiptChainError("receipt line is not canonical JSON")
        receipts.append(receipt)
    return receipts


def _validate_envelope(receipt: dict[str, Any]) -> None:
    if set(receipt) != ENVELOPE_FIELDS:
        raise ReceiptChainError("invalid receipt envelope fields")
    receipt_type = receipt.get("receipt_type")
    if receipt_type not in RECEIPT_TYPES:
        raise ReceiptChainError("invalid receipt_type")
    if not _is_int(receipt.get("sequence")):
        raise ReceiptChainError("invalid sequence")
    if not isinstance(receipt.get("run_id"), str) or not receipt["run_id"]:
        raise ReceiptChainError("invalid run_id")
    validate_timestamp(receipt.get("timestamp"))
    if not LOWER_HEX_64.fullmatch(str(receipt.get("previous_hash"))):
        raise ReceiptChainError("invalid previous_hash")
    if not LOWER_HEX_64.fullmatch(str(receipt.get("hash"))):
        raise ReceiptChainError("invalid hash")
    _validate_payload(receipt_type, receipt.get("payload"))
    preimage = {field: receipt[field] for field in HASH_FIELDS}
    if _receipt_hash(preimage) != receipt["hash"]:
        raise ReceiptChainError("receipt hash mismatch")


def _validate_history(receipts: list[dict[str, Any]], run_id: str) -> None:
    previous = GENESIS_PREVIOUS_HASH
    for sequence, receipt in enumerate(receipts):
        _validate_envelope(receipt)
        if receipt["sequence"] != sequence:
            raise ReceiptChainError("receipt sequence mismatch")
        if receipt["run_id"] != run_id:
            raise ReceiptChainError("receipt run_id mismatch")
        if sequence == 0 and receipt["receipt_type"] != "ANCHOR":
            raise ReceiptChainError("first receipt is not ANCHOR")
        if receipt["previous_hash"] != previous:
            raise ReceiptChainError("receipt previous_hash mismatch")
        if sequence < len(receipts) - 1 and receipt["receipt_type"] in TERMINAL_TYPES:
            raise ReceiptChainError("receipt exists after terminal")
        previous = receipt["hash"]


class ReceiptWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir.resolve()
        if not self.run_dir.is_dir():
            raise ReceiptChainError("run directory does not exist")
        self.run_id = self.run_dir.name
        self.path = self.run_dir / RECEIPTS_NAME
        self._lock_path = self.run_dir / ".receipts.lock"
        try:
            self._lock_fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError as exc:
            raise ReceiptChainError("receipt writer is already active") from exc
        try:
            self._receipts = _parse_lines(self.path) if self.path.exists() else []
            if self._receipts:
                _validate_history(self._receipts, self.run_id)
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        fd = getattr(self, "_lock_fd", -1)
        if fd >= 0:
            os.close(fd)
            self._lock_fd = -1
            self._lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "ReceiptWriter":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def append(self, receipt_type: str, payload: dict[str, Any], *, timestamp: str | None = None) -> dict[str, Any]:
        if receipt_type not in RECEIPT_TYPES:
            raise ReceiptChainError("invalid receipt_type")
        if self._receipts and self._receipts[-1]["receipt_type"] in TERMINAL_TYPES:
            raise ReceiptChainError("cannot append after terminal receipt")
        if not self._receipts and receipt_type != "ANCHOR":
            raise ReceiptChainError("first receipt must be ANCHOR")
        if self._receipts and receipt_type == "ANCHOR":
            raise ReceiptChainError("ANCHOR already exists")
        payload = _validate_payload(receipt_type, payload)
        value = {
            "receipt_type": receipt_type,
            "sequence": len(self._receipts),
            "run_id": self.run_id,
            "timestamp": validate_timestamp(timestamp or receipt_timestamp()),
            "previous_hash": self._receipts[-1]["hash"] if self._receipts else GENESIS_PREVIOUS_HASH,
            "payload": payload,
        }
        receipt = {**value, "hash": _receipt_hash(value)}
        line = (canonical_json(receipt) + "\n").encode("utf-8")
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            offset = 0
            while offset < len(line):
                written = os.write(fd, line[offset:])
                if written < 1:
                    raise ReceiptChainError("receipt append made no progress")
                offset += written
            os.fsync(fd)
        finally:
            os.close(fd)
        self._receipts.append(receipt)
        return receipt


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_receipt_chain(
    run_dir: Path,
    *,
    manifest: Mapping[str, Any] | None = None,
    checkpoint: Mapping[str, Any] | None = None,
    require_completion: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    try:
        receipts = _parse_lines(run_dir / RECEIPTS_NAME)
        _validate_history(receipts, run_dir.name)
        if receipts[-1]["receipt_type"] not in TERMINAL_TYPES:
            raise ReceiptChainError("receipt chain has no terminal receipt")

        pages = [receipt for receipt in receipts if receipt["receipt_type"] == "PAGE"]
        starts: set[int] = set()
        expected_start = 0
        canonical_total = quarantine_total = processed = 0
        source_counts: list[int] = []
        for page in pages:
            payload = page["payload"]
            if payload["start"] in starts:
                raise ReceiptChainError("duplicate PAGE start")
            if payload["start"] != expected_start:
                raise ReceiptChainError("PAGE offset discontinuity")
            starts.add(payload["start"])
            expected_start += payload["page_size"]
            processed += payload["returned_row_count"]
            canonical_total += payload["canonical_row_count"]
            quarantine_total += payload["quarantined_row_count"]
            source_counts.append(payload["source_count_observed"])
        for page in pages[:-1]:
            if page["payload"]["returned_row_count"] != page["payload"]["page_size"]:
                raise ReceiptChainError("short PAGE before completion")
        if pages and not 0 < pages[-1]["payload"]["returned_row_count"] <= pages[-1]["payload"]["page_size"]:
            raise ReceiptChainError("invalid final PAGE size")

        # Derive retry and resume authority from the receipt prefix itself.
        # A checkpoint or RESUME payload can confirm history, never create it.
        prefix_processed = 0
        prefix_canonical = 0
        prefix_quarantine = 0
        prefix_pages = 0
        retry_total = 0
        pending_retry_start: int | None = None
        pending_retry_page_size: int | None = None
        pending_retry_count = 0
        for receipt in receipts[1:]:
            receipt_type = receipt["receipt_type"]
            payload = receipt["payload"]
            if receipt_type == "RETRY":
                if pending_retry_start is None:
                    pending_retry_start = payload["start"]
                    pending_retry_page_size = payload["page_size"]
                    pending_retry_count = 0
                if (
                    payload["start"] != prefix_processed
                    or payload["start"] != pending_retry_start
                    or payload["page_size"] != pending_retry_page_size
                    or payload["retry_index"] != pending_retry_count + 1
                ):
                    raise ReceiptChainError("RETRY prefix binding mismatch")
                pending_retry_count += 1
                retry_total += 1
                continue

            if receipt_type == "PAGE":
                if pending_retry_start is not None and (
                    payload["start"] != pending_retry_start
                    or payload["page_size"] != pending_retry_page_size
                ):
                    raise ReceiptChainError("RETRY does not bind to following PAGE")
                pending_retry_start = None
                pending_retry_page_size = None
                pending_retry_count = 0
                prefix_processed += payload["returned_row_count"]
                prefix_canonical += payload["canonical_row_count"]
                prefix_quarantine += payload["quarantined_row_count"]
                prefix_pages += 1
                continue

            if receipt_type == "RESUME":
                if pending_retry_start is not None:
                    raise ReceiptChainError("RETRY is not followed by PAGE")
                expected_payload = {
                    "processed": prefix_processed,
                    "next_start": prefix_processed,
                    "last_completed_page": prefix_pages,
                    "retries": retry_total,
                }
                if any(payload[field] != value for field, value in expected_payload.items()):
                    raise ReceiptChainError("RESUME prefix accounting mismatch")
                snapshot = payload["checkpoint_snapshot"]
                expected_snapshot = {
                    "source_rows_processed": prefix_processed,
                    "next_start": prefix_processed,
                    "last_completed_page": prefix_pages,
                    "retries_used": retry_total,
                }
                if any(snapshot.get(key) != value for key, value in expected_snapshot.items()):
                    raise ReceiptChainError("RESUME checkpoint snapshot mismatch")
                optional_snapshot = {
                    "canonical_rows_collected": prefix_canonical,
                    "quarantine_rows": prefix_quarantine,
                }
                if any(
                    key in snapshot and snapshot[key] != value
                    for key, value in optional_snapshot.items()
                ):
                    raise ReceiptChainError("RESUME checkpoint accounting mismatch")
                if checkpoint is not None and dict(checkpoint) != snapshot:
                    raise ReceiptChainError("checkpoint mismatch")
                continue

            if pending_retry_start is not None and receipt_type != "ABORT":
                raise ReceiptChainError("RETRY is not followed by PAGE")

        if pending_retry_start is not None and receipts[-1]["receipt_type"] != "ABORT":
            raise ReceiptChainError("RETRY has no PAGE or ABORT outcome")

        terminal = receipts[-1]
        promotion_valid = terminal["receipt_type"] == "COMPLETION"
        if require_completion and not promotion_valid:
            raise ReceiptChainError("ABORT chain is not promotion-valid")
        if promotion_valid:
            payload = terminal["payload"]
            if payload["processed"] != processed or payload["canonical_total"] != canonical_total or payload["quarantine_total"] != quarantine_total:
                raise ReceiptChainError("global accounting mismatch")
            if not pages or payload["source_count_start"] != source_counts[0] or payload["source_count_end"] != source_counts[-1]:
                raise ReceiptChainError("source count accounting mismatch")
            anchor = receipts[0]["payload"]
            if payload["drift_status"] != "NO_DRIFT" or any(count != source_counts[0] for count in source_counts):
                raise ReceiptChainError("source count drift in COMPLETION chain")
            if anchor["full_snapshot"] and payload["source_count_end"] != processed:
                raise ReceiptChainError("full snapshot source count mismatch")
            database = run_dir / DATABASE_NAME
            if not database.is_file() or sha256_file(database) != payload["duckdb_sha256"]:
                raise ReceiptChainError("candidate DuckDB digest mismatch")
            if manifest is not None:
                if manifest.get("chain_head") != terminal["hash"]:
                    raise ReceiptChainError("manifest chain_head mismatch")
                if manifest.get("run_id") != run_dir.name:
                    raise ReceiptChainError("manifest run_id mismatch")
                if manifest.get("sha256") != payload["duckdb_sha256"] or manifest.get("row_count") != canonical_total or manifest.get("source_records_filtered") != source_counts[-1] or ("retries_used" in manifest and manifest.get("retries_used") != retry_total):
                    raise ReceiptChainError("manifest accounting mismatch")
        return {
            "valid": True,
            "promotion_valid": promotion_valid,
            "terminal_type": terminal["receipt_type"],
            "terminal_hash": terminal["hash"],
            "run_id": run_dir.name,
            "processed": processed,
            "canonical_total": canonical_total,
            "quarantine_total": quarantine_total,
            "retry_total": retry_total,
            "failures": [],
        }
    except (OSError, ReceiptChainError, UnicodeError, ValueError, TypeError) as exc:
        return {"valid": False, "promotion_valid": False, "failures": [str(exc)]}
