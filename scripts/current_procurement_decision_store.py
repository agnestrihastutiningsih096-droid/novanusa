"""Durable, fail-closed JSON persistence for procurement decisions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


STORE_SCHEMA = "novanusa.procurement-decisions"
STORE_VERSION = 1
RECORD_SCHEMA = "novanusa.procurement-decision"
RECORD_VERSION = 1


class DecisionStoreError(ValueError):
    """The decision history cannot be trusted or updated."""


def _record_key(record: Mapping[str, Any]) -> tuple[str, str]:
    return record["kind"], record["subject"]


def _authoritative_content(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"decision_id", "timestamp"}}


def _validate_record(record: object) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise DecisionStoreError("decision record must be an object")
    required = {
        "schema", "version", "decision_id", "kind", "result", "subject",
        "provenance", "evidence_references", "timestamp", "bindings",
    }
    if set(record) != required:
        raise DecisionStoreError("decision record has an incomplete or unknown shape")
    for name in ("schema", "decision_id", "kind", "result", "subject", "timestamp"):
        if not isinstance(record[name], str) or not record[name].strip():
            raise DecisionStoreError(f"invalid decision {name}")
    if record["schema"] != RECORD_SCHEMA or record["version"] != RECORD_VERSION:
        raise DecisionStoreError("unsupported decision record schema")
    provenance = record["provenance"]
    if not isinstance(provenance, list) or len(provenance) != 3 or any(not isinstance(item, str) or not item for item in provenance):
        raise DecisionStoreError("invalid decision provenance")
    evidence = record["evidence_references"]
    if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
        raise DecisionStoreError("invalid decision evidence references")
    if not isinstance(record["bindings"], dict):
        raise DecisionStoreError("invalid decision bindings")
    return record


class ProcurementDecisionStore:
    """Append-only decision history; reads never rely on process-local state."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)

    def read(self) -> tuple[dict[str, Any], ...]:
        if not self.path.exists():
            return ()
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise DecisionStoreError("decision store is unreadable or corrupt") from exc
        if not isinstance(state, dict) or set(state) != {"schema", "version", "decisions"}:
            raise DecisionStoreError("decision store has an incomplete or unknown shape")
        if state["schema"] != STORE_SCHEMA or state["version"] != STORE_VERSION or not isinstance(state["decisions"], list):
            raise DecisionStoreError("unsupported decision store schema")
        records = tuple(_validate_record(item) for item in state["decisions"])
        ids: set[str] = set()
        authoritative: dict[tuple[str, str], dict[str, Any]] = {}
        for record in records:
            if record["decision_id"] in ids:
                raise DecisionStoreError("duplicate decision id")
            ids.add(record["decision_id"])
            key = _record_key(record)
            previous = authoritative.get(key)
            if previous is not None and _authoritative_content(previous) != _authoritative_content(record):
                raise DecisionStoreError("contradictory authoritative decisions")
            authoritative[key] = record
        return records

    def append(self, record: Mapping[str, Any]) -> None:
        new_record = _validate_record(dict(record))
        records = list(self.read())
        if any(item["decision_id"] == new_record["decision_id"] for item in records):
            raise DecisionStoreError("decision id already exists")
        if any(_record_key(item) == _record_key(new_record) and _authoritative_content(item) != _authoritative_content(new_record) for item in records):
            raise DecisionStoreError("contradictory authoritative decision")
        state = {"schema": STORE_SCHEMA, "version": STORE_VERSION, "decisions": [*records, new_record]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(state, stream, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            raise DecisionStoreError("decision store update failed") from exc

    def contains_exact(self, expected: Mapping[str, Any]) -> bool:
        candidate = _validate_record(dict(expected))
        records = self.read()
        matches = [item for item in records if item["decision_id"] == candidate["decision_id"]]
        return len(matches) == 1 and matches[0] == candidate
