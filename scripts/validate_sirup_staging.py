from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import duckdb


DATABASE_NAME = "sirup_staging.duckdb"
MANIFEST_NAME = "manifest.json"
TABLE_NAME = "sirup_raw"
EXPECTED_SCHEMA = [
    ("id", "BIGINT", True, True),
    ("id_referensi", "VARCHAR", False, False),
    ("pagu", "DOUBLE", False, False),
    ("satuanKerja", "VARCHAR", False, False),
    ("kldi", "VARCHAR", False, False),
    ("lokasi", "VARCHAR", False, False),
    ("jenisPengadaan", "VARCHAR", False, False),
    ("metode", "VARCHAR", False, False),
    ("sumberDana", "VARCHAR", False, False),
    ("paket", "VARCHAR", False, False),
    ("pemilihan", "VARCHAR", False, False),
    ("idBulan", "INTEGER", False, False),
]
REQUIRED_MANIFEST_FIELDS = {
    "manifest_version",
    "run_id",
    "status",
    "promotion_eligible",
    "database_path",
    "table_name",
    "requested_limit",
    "row_count",
    "distinct_id_count",
    "min_id",
    "max_id",
    "sha256",
    "validation",
    "promotion",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"manifest is not readable JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("manifest root is not an object")
    missing = sorted(REQUIRED_MANIFEST_FIELDS - manifest.keys())
    if missing:
        raise RuntimeError(f"manifest is missing fields: {', '.join(missing)}")
    return manifest


def inspect_database(path: Path) -> dict[str, Any]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("show tables").fetchall()}
        if TABLE_NAME not in tables:
            raise RuntimeError(f"required table {TABLE_NAME!r} does not exist")
        schema_rows = connection.execute(f"pragma table_info('{TABLE_NAME}')").fetchall()
        actual_schema = [
            (str(row[1]), str(row[2]).upper(), bool(row[3]), bool(row[5]))
            for row in schema_rows
        ]
        metrics = connection.execute(
            f"""
            select
                count(*),
                count(distinct id),
                count(*) filter (where id is null),
                min(id),
                max(id)
            from {TABLE_NAME}
            """
        ).fetchone()
    finally:
        connection.close()
    if metrics is None:
        raise RuntimeError("database metrics query returned no result")
    return {
        "schema": actual_schema,
        "row_count": int(metrics[0]),
        "distinct_id_count": int(metrics[1]),
        "null_id_count": int(metrics[2]),
        "min_id": int(metrics[3]) if metrics[3] is not None else None,
        "max_id": int(metrics[4]) if metrics[4] is not None else None,
    }


def validate(run_dir: Path) -> tuple[dict[str, Any], list[str]]:
    database_path = run_dir / DATABASE_NAME
    manifest_path = run_dir / MANIFEST_NAME
    checks: dict[str, Any] = {
        "duckdb_exists": database_path.is_file(),
        "manifest_exists": manifest_path.is_file(),
    }
    errors: list[str] = []
    if not checks["duckdb_exists"]:
        errors.append(f"DuckDB does not exist: {database_path}")
    if not checks["manifest_exists"]:
        errors.append(f"manifest does not exist: {manifest_path}")
    if errors:
        return checks, errors

    try:
        manifest = load_manifest(manifest_path)
    except RuntimeError as exc:
        checks["manifest_consistency"] = False
        errors.append(str(exc))
        return checks, errors

    try:
        facts = inspect_database(database_path)
    except (duckdb.Error, RuntimeError) as exc:
        checks["database_read_only_open"] = False
        errors.append(f"DuckDB validation failed: {exc}")
        return checks, errors

    checks["database_read_only_open"] = True
    checks["schema"] = facts["schema"] == EXPECTED_SCHEMA
    checks["row_count"] = facts["row_count"] > 0
    checks["unique_ids"] = facts["distinct_id_count"] == facts["row_count"]
    checks["null_ids"] = facts["null_id_count"] == 0
    if not checks["schema"]:
        errors.append(f"schema mismatch: expected {EXPECTED_SCHEMA!r}, got {facts['schema']!r}")
    if not checks["row_count"]:
        errors.append("row count must be nonzero")
    if not checks["unique_ids"]:
        errors.append("distinct ID count does not equal row count")
    if not checks["null_ids"]:
        errors.append(f"found {facts['null_id_count']} null IDs")

    manifest_matches = {
        "run_id": manifest["run_id"] == run_dir.name,
        "database_path": Path(manifest["database_path"]).resolve() == database_path.resolve(),
        "table_name": manifest["table_name"] == TABLE_NAME,
        "requested_limit": manifest["requested_limit"] == facts["row_count"],
        "row_count": manifest["row_count"] == facts["row_count"],
        "distinct_id_count": manifest["distinct_id_count"] == facts["distinct_id_count"],
        "min_id": manifest["min_id"] == facts["min_id"],
        "max_id": manifest["max_id"] == facts["max_id"],
        "sha256": manifest["sha256"] == sha256_file(database_path),
        "staging_only": manifest["promotion_eligible"] is False
        and manifest["promotion"] == {"attempted": False, "result": "not_in_scope"},
    }
    checks["manifest_consistency"] = all(manifest_matches.values())
    checks["manifest_fields"] = manifest_matches
    for name, passed in manifest_matches.items():
        if not passed:
            errors.append(f"manifest field check failed: {name}")

    checks["metrics"] = facts
    return checks, errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an existing SiRUP staging snapshot read-only.")
    parser.add_argument("run_dir", type=Path, help="Staging run directory containing DuckDB and manifest.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    checks, errors = validate(run_dir)
    result = {
        "run_dir": str(run_dir),
        "status": "passed" if not errors else "failed",
        "checks": checks,
        "errors": errors,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
