from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from compare_sirup_staging import compare
from sirup_receipt_chain import verify_receipt_chain


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
    "receipt_chain_valid",
    "comparison_report_available",
    "comparison_report_valid",
    "promotion_flag_remains_false",
]
GENESIS_GATE_ORDER = [
    "genesis_context_valid",
    "genesis_selection_state_valid",
    "genesis_manifest_contract_valid",
    "genesis_full_source_accounting_valid",
    "genesis_collection_provenance_valid",
    "genesis_promotion_state_valid",
]
COLLECTOR_VALIDATION_GATES = {
    "response_shape",
    "requested_row_count",
    "sequential_pagination",
    "source_count_consistency",
    "source_year_parameter",
    "non_null_ids",
    "unique_ids",
    "database_read_only_reopen",
}
SOURCE_ENDPOINT = "https://sirup.inaproc.id/sirup/caripaketctr/search"
def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _genesis_manifest_checks(
    manifest: dict[str, Any] | None, database: dict[str, Any] | None
) -> dict[str, bool]:
    source_count = manifest.get("source_records_filtered") if manifest else None
    page_size = manifest.get("page_size") if manifest else None
    page_count = manifest.get("page_count") if manifest else None
    started_at = _parse_timestamp(manifest.get("started_at")) if manifest else None
    collected_at = _parse_timestamp(manifest.get("collected_at")) if manifest else None
    required = {
        "manifest_version", "run_id", "status", "full_snapshot",
        "promotion_eligible", "source_endpoint", "requested_year",
        "requested_limit", "page_size", "page_count", "started_at",
        "collected_at", "database_path", "table_name", "row_count",
        "distinct_id_count", "min_id", "max_id", "source_records_filtered",
        "request_count", "retries_used", "sha256", "validation", "promotion",
    }
    contract = bool(
        manifest
        and required.issubset(manifest)
        and manifest.get("manifest_version") == 1
        and manifest.get("status") == "validated_staging_sample"
        and manifest.get("full_snapshot") is True
        and manifest.get("promotion") == {"attempted": False, "result": "not_in_scope"}
        and isinstance(manifest.get("validation"), dict)
        and set(manifest["validation"]) == COLLECTOR_VALIDATION_GATES
        and all(value == "passed" for value in manifest["validation"].values())
    )
    accounting = bool(
        manifest and database and isinstance(source_count, int)
        and not isinstance(source_count, bool) and source_count > 0
        and database["row_count"] == source_count
    )
    provenance = bool(
        manifest
        and manifest.get("source_endpoint") == SOURCE_ENDPOINT
        and isinstance(manifest.get("requested_year"), int)
        and not isinstance(manifest.get("requested_year"), bool)
        and manifest["requested_year"] > 0
        and manifest.get("requested_limit") == source_count
        and isinstance(page_size, int) and not isinstance(page_size, bool) and page_size > 0
        and isinstance(page_count, int) and not isinstance(page_count, bool) and page_count > 0
        and page_count == (source_count + page_size - 1) // page_size
        and manifest.get("request_count") == page_count
        and isinstance(manifest.get("retries_used"), int)
        and not isinstance(manifest.get("retries_used"), bool)
        and manifest["retries_used"] >= 0
        and started_at is not None and collected_at is not None
        and started_at <= collected_at
    )
    return {
        "genesis_manifest_contract_valid": contract,
        "genesis_full_source_accounting_valid": accounting,
        "genesis_collection_provenance_valid": provenance,
        "genesis_promotion_state_valid": bool(
            manifest and manifest.get("promotion_eligible") is False
        ),
    }


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


def _evaluate(
    run_dir: Path,
    comparison_path: Path,
    *,
    _genesis_capability: object | None = None,
    _genesis_run_id: str | None = None,
    _expected_active: str | None = None,
) -> dict[str, Any]:
    database_path = run_dir / DATABASE_NAME
    manifest_path = run_dir / MANIFEST_NAME
    manifest = load_json(manifest_path)
    database = inspect_database(database_path)
    comparison = load_json(comparison_path)
    expected_comparison = None
    if comparison and isinstance(comparison.get("baseline"), str):
        try:
            expected_comparison = compare(Path(comparison["baseline"]), database_path)
        except (duckdb.Error, OSError, RuntimeError, TypeError, ValueError):
            pass

    source_count = manifest.get("source_records_filtered") if manifest else None
    validation = manifest.get("validation") if manifest else None
    collection_gates_passed = (
        isinstance(validation, dict)
        and bool(validation)
        and all(value == "passed" for value in validation.values())
    )
    receipt_chain = verify_receipt_chain(
        run_dir, manifest=manifest, require_completion=True
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
        and expected_comparison
        and comparison == {"status": "passed", **expected_comparison}
    )

    common_gates = {
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
        "receipt_chain_valid": bool(
            receipt_chain.get("valid") and receipt_chain.get("promotion_valid")
        ),
        "promotion_flag_remains_false": bool(
            manifest and manifest.get("promotion_eligible") is False
        ),
    }
    # Imported lazily to avoid the validator/promoter module cycle. Authority
    # is an original live object identity in the promoter's private registry,
    # not this argument's type or caller-supplied metadata.
    from promote_sirup_snapshot import _validate_and_consume_genesis_capability

    capability_valid = _validate_and_consume_genesis_capability(
        _genesis_capability, run_dir, _genesis_run_id, _expected_active
    )
    genesis = capability_valid is not None
    if genesis:
        context_valid = capability_valid
        selection_valid = capability_valid
        gates = {
            **common_gates,
            "genesis_context_valid": context_valid,
            "genesis_selection_state_valid": selection_valid,
            **_genesis_manifest_checks(manifest, database),
        }
        order = GATE_ORDER[:12] + GENESIS_GATE_ORDER + GATE_ORDER[14:]
        mode = "GENESIS"
    else:
        gates = {
            **common_gates,
            "comparison_report_available": comparison_path.is_file() and comparison is not None,
            "comparison_report_valid": comparison_valid,
        }
        order = GATE_ORDER
        mode = "STEADY_STATE"
    ordered_gates = {name: "PASS" if gates[name] else "FAIL" for name in order}
    failures = [name for name in order if not gates[name]]
    return {
        "result": "PASS" if not failures else "FAIL",
        "promotion_eligible": not failures,
        "validation_mode": mode,
        "run_dir": str(run_dir),
        "comparison_report": str(comparison_path),
        "gates": ordered_gates,
        "failures": failures,
    }


def evaluate(run_dir: Path, comparison_path: Path) -> dict[str, Any]:
    """Validate a standalone candidate in steady-state mode only."""
    return _evaluate(run_dir, comparison_path)


def _evaluate_genesis(
    run_dir: Path,
    comparison_path: Path,
    capability: object,
    run_id: str,
    expected_active: str | None,
) -> dict[str, Any]:
    """Internal promoter boundary; registry identity remains authoritative."""
    return _evaluate(
        run_dir,
        comparison_path,
        _genesis_capability=capability,
        _genesis_run_id=run_id,
        _expected_active=expected_active,
    )


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
