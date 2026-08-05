"""Deterministic, side-effect-free classification of parsed SiRUP pages."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any


def _same_id(left: Any, right: Any) -> bool:
    """Compare source IDs without requiring them to be hashable."""
    try:
        result = left == right
        return result if isinstance(result, bool) else False
    except Exception:
        return False


def classify_page_rows(
    payload: Any,
    expected_count: int,
    required_fields: Collection[str],
) -> dict[str, Any]:
    """Classify a parsed page without modifying it or performing I/O."""
    if isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise ValueError("expected_count must be a non-negative integer")
    if expected_count < 0:
        raise ValueError("expected_count must be a non-negative integer")
    if (isinstance(required_fields, (str, bytes))
            or not isinstance(required_fields, Collection)
            or not required_fields
            or any(not isinstance(field, str) or not field
                   for field in required_fields)):
        raise ValueError(
            "required_fields must be a non-empty collection of non-empty strings")
    required = sorted(set(required_fields))

    if not isinstance(payload, dict):
        raise RuntimeError("response payload is not an object")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("response field 'data' is not an array")
    if len(rows) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} rows but source returned {len(rows)}")
    records_filtered = payload.get("recordsFiltered")
    if isinstance(records_filtered, bool) or not isinstance(records_filtered, int):
        raise RuntimeError("response field 'recordsFiltered' is not an integer")

    duplicate_indexes: set[int] = set()
    candidates = [
        (index, row["id"])
        for index, row in enumerate(rows)
        if isinstance(row, dict) and "id" in row and row["id"] is not None
    ]
    for position, (index, package_id) in enumerate(candidates):
        for other_index, other_id in candidates[position + 1:]:
            if _same_id(package_id, other_id):
                duplicate_indexes.add(index)
                duplicate_indexes.add(other_index)

    valid_rows: list[Any] = []
    invalid_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            invalid_rows.append({
                "row_index": index,
                "raw_row": row,
                "package_id": None,
                "missing_fields": [],
                "invalid_fields": ["row"],
                "validation_error": f"row {index} is not an object",
            })
            continue

        missing = sorted(field for field in required if field not in row)
        invalid: list[str] = []
        errors: list[str] = []
        if missing:
            errors.append(f"row {index} is missing fields: {', '.join(missing)}")
        if "id" in row and row["id"] is None:
            invalid.append("id")
            errors.append(f"row {index} has a null id")
        if index in duplicate_indexes:
            invalid.append("id")
            errors.append(f"row {index} has a duplicate id: {row['id']}")

        if errors:
            invalid_rows.append({
                "row_index": index,
                "raw_row": row,
                "package_id": row.get("id"),
                "missing_fields": missing,
                "invalid_fields": sorted(set(invalid)),
                "validation_error": "; ".join(errors),
            })
        else:
            valid_rows.append(row)

    source_row_count = len(rows)
    return {
        "records_filtered": records_filtered,
        "source_row_count": source_row_count,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "valid_row_count": len(valid_rows),
        "invalid_row_count": len(invalid_rows),
    }
