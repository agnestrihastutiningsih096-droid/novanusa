from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb


DATABASE_NAME = "sirup_staging.duckdb"
MANIFEST_NAME = "manifest.json"
DEFAULT_COMPARISON_NAME = "comparison.json"
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
GATE_ORDER = [
    "manifest_exists",
    "duckdb_exists",
    "schema_valid",
    "row_count_nonzero",
    "unique_ids",
    "no_null_ids",
    "manifest_consistent",
    "sha256_verified",
    "source_count_recorded",
    "full_source_count_collected",
    "collection_gates_recorded_passed",
    "comparison_report_available",
    "comparison_report_valid",
    "promotion_flag_remains_false",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def inspect_database(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        connection = duckdb.connect(str(path), read_only=True)
        try:
            tables = {row[0] for row in connection.execute("show tables").fetchall()}
            if TABLE_NAME not in tables:
                return None
            schema_rows = connection.execute(f"pragma table_info('{TABLE_NAME}')").fetchall()
            schema = [
                (str(row[1]), str(row[2]).upper(), bool(row[3]), bool(row[5]))
                for row in schema_rows
            ]
            metrics = connection.execute(
                f"""
                select count(*), count(distinct id),
                       count(*) filter (where id is null), min(id), max(id)
                from {TABLE_NAME}
                """
            ).fetchone()
        finally:
            connection.close()
    except duckdb.Error:
        return None
    if metrics is None:
        return None
    return {
        "schema": schema,
        "row_count": int(metrics[0]),
        "distinct_id_count": int(metrics[1]),
        "null_id_count": int(metrics[2]),
        "min_id": int(metrics[3]) if metrics[3] is not None else None,
        "max_id": int(metrics[4]) if metrics[4] is not None else None,
    }


def evaluate(run_dir: Path, comparison_path: Path) -> dict[str, Any]:
    database_path = run_dir / DATABASE_NAME
    manifest_path = run_dir / MANIFEST_NAME
    manifest = load_json(manifest_path)
    database = inspect_database(database_path)
    comparison = load_json(comparison_path)

    source_count = manifest.get("source_records_filtered") if manifest else None
    validation = manifest.get("validation") if manifest else None
    collection_gates_passed = (
        isinstance(validation, dict)
        and bool(validation)
        and all(value == "passed" for value in validation.values())
    )
    manifest_consistent = bool(
        manifest
        and database
        and manifest.get("run_id") == run_dir.name
        and manifest.get("database_path") == str(database_path)
        and manifest.get("table_name") == TABLE_NAME
        and manifest.get("row_count") == database["row_count"]
        and manifest.get("distinct_id_count") == database["distinct_id_count"]
        and manifest.get("min_id") == database["min_id"]
        and manifest.get("max_id") == database["max_id"]
    )
    comparison_valid = bool(
        comparison
        and comparison.get("status") == "passed"
        and Path(str(comparison.get("candidate", ""))).resolve() == database_path.resolve()
        and isinstance(comparison.get("row_count_difference"), int)
        and isinstance(comparison.get("ids_added_count"), int)
        and isinstance(comparison.get("ids_missing_count"), int)
        and isinstance(comparison.get("ids_changed_count"), int)
        and isinstance(comparison.get("source_count_difference"), int)
    )

    gates = {
        "manifest_exists": manifest_path.is_file() and manifest is not None,
        "duckdb_exists": database_path.is_file() and database is not None,
        "schema_valid": bool(database and database["schema"] == EXPECTED_SCHEMA),
        "row_count_nonzero": bool(database and database["row_count"] > 0),
        "unique_ids": bool(
            database and database["distinct_id_count"] == database["row_count"]
        ),
        "no_null_ids": bool(database and database["null_id_count"] == 0),
        "manifest_consistent": manifest_consistent,
        "sha256_verified": bool(
            manifest
            and database_path.is_file()
            and isinstance(manifest.get("sha256"), str)
            and manifest["sha256"] == sha256_file(database_path)
        ),
        "source_count_recorded": isinstance(source_count, int) and source_count > 0,
        "full_source_count_collected": bool(
            database and isinstance(source_count, int) and database["row_count"] == source_count
        ),
        "collection_gates_recorded_passed": collection_gates_passed,
        "comparison_report_available": comparison_path.is_file() and comparison is not None,
        "comparison_report_valid": comparison_valid,
        "promotion_flag_remains_false": bool(
            manifest and manifest.get("promotion_eligible") is False
        ),
    }
    ordered_gates = {name: "PASS" if gates[name] else "FAIL" for name in GATE_ORDER}
    failures = [name for name in GATE_ORDER if not gates[name]]
    return {
        "result": "PASS" if not failures else "FAIL",
        "promotion_eligible": not failures,
        "run_dir": str(run_dir),
        "comparison_report": str(comparison_path),
        "gates": ordered_gates,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decide SiRUP staging promotion eligibility without modifying artifacts."
    )
    parser.add_argument("run_dir", type=Path, help="Staging run directory.")
    parser.add_argument(
        "--comparison-report",
        type=Path,
        help=f"Persisted comparison JSON; defaults to <run_dir>/{DEFAULT_COMPARISON_NAME}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    comparison_path = (
        args.comparison_report.resolve()
        if args.comparison_report
        else run_dir / DEFAULT_COMPARISON_NAME
    )
    report = evaluate(run_dir, comparison_path)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
