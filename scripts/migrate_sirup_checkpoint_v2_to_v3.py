from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb


MIGRATION_VERSION = 1
CHECKPOINT_VERSION = 3
DATABASE_NAME = "sirup_staging.duckdb"
QUARANTINE_NAME = "quarantine"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def require_nonnegative_integer(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError(f"source checkpoint field {field!r} is invalid")
    return value


def read_source_checkpoint(path: Path, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"source checkpoint is not readable: {path}: {exc}") from exc
    observed_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            "source checkpoint SHA-256 mismatch: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    try:
        checkpoint = json.loads(source_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"source checkpoint is not valid JSON: {exc}") from exc
    if not isinstance(checkpoint, dict):
        raise RuntimeError("source checkpoint root is not an object")
    if checkpoint.get("checkpoint_version") != 2:
        raise RuntimeError("source checkpoint version must be 2")
    return checkpoint, source_bytes


def validate_source_checkpoint(checkpoint: dict[str, Any]) -> dict[str, Any]:
    rows_collected = require_nonnegative_integer(
        checkpoint.get("rows_collected"), "rows_collected"
    )
    next_start = require_nonnegative_integer(checkpoint.get("next_start"), "next_start")
    source_count = require_nonnegative_integer(
        checkpoint.get("source_count"), "source_count"
    )
    last_completed_page = require_nonnegative_integer(
        checkpoint.get("last_completed_page"), "last_completed_page"
    )
    retries_used = require_nonnegative_integer(
        checkpoint.get("retries_used"), "retries_used"
    )
    if rows_collected != next_start:
        raise RuntimeError("source checkpoint rows_collected does not equal next_start")
    if rows_collected > source_count:
        raise RuntimeError("source checkpoint rows_collected exceeds source_count")

    started_at = checkpoint.get("started_at")
    run_dir_value = checkpoint.get("run_dir")
    database_path_value = checkpoint.get("database_path")
    config = checkpoint.get("config")
    if not isinstance(started_at, str) or not started_at:
        raise RuntimeError("source checkpoint field 'started_at' is invalid")
    if not isinstance(run_dir_value, str) or not run_dir_value:
        raise RuntimeError("source checkpoint field 'run_dir' is invalid")
    if not isinstance(database_path_value, str) or not database_path_value:
        raise RuntimeError("source checkpoint field 'database_path' is invalid")
    if not isinstance(config, dict):
        raise RuntimeError("source checkpoint field 'config' is invalid")

    return {
        "rows_collected": rows_collected,
        "source_count": source_count,
        "last_completed_page": last_completed_page,
        "retries_used": retries_used,
        "started_at": started_at,
        "run_dir": absolute(Path(run_dir_value)),
        "database_path": absolute(Path(database_path_value)),
        "config": dict(config),
    }


def validate_paths(
    source_path: Path, target_path: Path, values: dict[str, Any]
) -> tuple[Path, Path]:
    source_path = absolute(source_path)
    target_path = absolute(target_path)
    run_dir = values["run_dir"]
    database_path = values["database_path"]
    if source_path == target_path:
        raise RuntimeError("target checkpoint must not equal source checkpoint")
    if not run_dir.is_dir():
        raise RuntimeError(f"run directory does not exist: {run_dir}")
    if not database_path.is_file():
        raise RuntimeError(f"database does not exist: {database_path}")
    if database_path.resolve() != (run_dir / DATABASE_NAME).resolve():
        raise RuntimeError("database path is not the run directory staging database")
    try:
        target_path.relative_to(run_dir)
    except ValueError:
        pass
    else:
        raise RuntimeError("target checkpoint must remain outside the run directory")
    return source_path, target_path


def verify_database(
    path: Path, expected_rows: int, expected_sha256: str
) -> dict[str, int]:
    observed_sha256 = sha256_file(path)
    if observed_sha256 != expected_sha256:
        raise RuntimeError(
            "database SHA-256 mismatch: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    connection = duckdb.connect(str(path), read_only=True)
    try:
        table_exists = connection.execute(
            "select count(*) from information_schema.tables "
            "where table_schema = 'main' and table_name = 'sirup_raw'"
        ).fetchone()[0]
        if table_exists != 1:
            raise RuntimeError("database table sirup_raw does not exist")
        row_count, distinct_id_count, null_id_count = connection.execute(
            "select count(*), count(distinct id), "
            "count(*) filter (where id is null) from sirup_raw"
        ).fetchone()
    finally:
        connection.close()
    row_count = int(row_count)
    distinct_id_count = int(distinct_id_count)
    null_id_count = int(null_id_count)
    duplicate_count = row_count - null_id_count - distinct_id_count
    if row_count != expected_rows:
        raise RuntimeError("DuckDB row count does not match rows_collected")
    if duplicate_count != 0:
        raise RuntimeError("DuckDB contains duplicate IDs")
    if null_id_count != 0:
        raise RuntimeError("DuckDB contains null IDs")
    if distinct_id_count != row_count:
        raise RuntimeError("DuckDB distinct ID count does not match row count")
    return {
        "row_count": row_count,
        "distinct_id_count": distinct_id_count,
        "duplicate_count": duplicate_count,
        "null_id_count": null_id_count,
    }


def verify_quarantine(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        if next(path.iterdir(), None) is not None:
            raise RuntimeError("quarantine artifact already contains records")
        return
    if path.is_file() and path.stat().st_size == 0:
        return
    raise RuntimeError("quarantine artifact already contains records")


def migration_identity(source_identity: str, source_sha256: str) -> str:
    return f"{source_identity}-v3-{source_sha256[:16]}"


def build_plan(
    source_path: Path,
    target_path: Path,
    source_sha256: str,
    database_sha256: str,
) -> dict[str, Any]:
    checkpoint, _ = read_source_checkpoint(source_path, source_sha256)
    values = validate_source_checkpoint(checkpoint)
    source_path, target_path = validate_paths(source_path, target_path, values)
    if target_path.exists():
        raise RuntimeError(f"target checkpoint already exists: {target_path}")
    evidence_path = Path(str(target_path) + ".migration.json")
    if evidence_path.exists():
        raise RuntimeError(f"migration evidence already exists: {evidence_path}")
    quarantine_path = values["run_dir"] / QUARANTINE_NAME
    verify_quarantine(quarantine_path)
    counts = verify_database(
        values["database_path"], values["rows_collected"], database_sha256
    )
    source_identity = values["run_dir"].name
    target_identity = migration_identity(source_identity, source_sha256)
    v3_config = dict(values["config"])
    v3_config["mode"] = "quarantine"
    v3_checkpoint = {
        "checkpoint_version": CHECKPOINT_VERSION,
        "config": v3_config,
        "run_dir": str(values["run_dir"]),
        "database_path": str(values["database_path"]),
        "quarantine_path": str(quarantine_path),
        "source_count": values["source_count"],
        "source_rows_processed": values["rows_collected"],
        "canonical_rows_collected": values["rows_collected"],
        "quarantine_rows": 0,
        "next_start": values["rows_collected"],
        "last_completed_page": values["last_completed_page"],
        "retries_used": values["retries_used"],
        "started_at": values["started_at"],
    }
    return {
        "migration_version": MIGRATION_VERSION,
        "action": "migrate_sirup_checkpoint_v2_to_v3",
        "source_checkpoint": str(source_path),
        "source_checkpoint_sha256": source_sha256,
        "source_v2_run_identity": source_identity,
        "target_v3_run_identity": target_identity,
        "target_checkpoint": str(target_path),
        "migration_evidence": str(evidence_path),
        "database": str(values["database_path"]),
        "database_sha256": database_sha256,
        "verified_duckdb_counts": counts,
        "quarantine_path": str(quarantine_path),
        "v3_checkpoint": v3_checkpoint,
    }


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def apply_plan(plan: dict[str, Any]) -> None:
    target_path = Path(plan["target_checkpoint"])
    evidence_path = Path(plan["migration_evidence"])
    if target_path.exists():
        raise RuntimeError(f"target checkpoint already exists: {target_path}")
    if evidence_path.exists():
        raise RuntimeError(f"migration evidence already exists: {evidence_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    target_temp = Path(str(target_path) + ".tmp")
    evidence_temp = Path(str(evidence_path) + ".tmp")
    evidence = {
        "migration_version": plan["migration_version"],
        "migrated_at": utc_now(),
        "source_checkpoint_absolute_path": plan["source_checkpoint"],
        "source_checkpoint_sha256": plan["source_checkpoint_sha256"],
        "source_checkpoint_version": 2,
        "source_v2_run_identity": plan["source_v2_run_identity"],
        "target_v3_run_identity": plan["target_v3_run_identity"],
        "target_checkpoint_absolute_path": plan["target_checkpoint"],
        "database_absolute_path": plan["database"],
        "database_sha256": plan["database_sha256"],
        "verified_duckdb_counts": plan["verified_duckdb_counts"],
        "source_count": plan["v3_checkpoint"]["source_count"],
        "source_rows_processed": plan["v3_checkpoint"]["source_rows_processed"],
        "canonical_rows_collected": plan["v3_checkpoint"]["canonical_rows_collected"],
        "quarantine_rows": plan["v3_checkpoint"]["quarantine_rows"],
        "last_completed_page": plan["v3_checkpoint"]["last_completed_page"],
        "retries_used": plan["v3_checkpoint"]["retries_used"],
        "config": plan["v3_checkpoint"]["config"],
        "decision": "PASS",
    }
    target_temp.write_bytes(json_bytes(plan["v3_checkpoint"]))
    evidence_temp.write_bytes(json_bytes(evidence))
    if target_path.exists() or evidence_path.exists():
        raise RuntimeError("target checkpoint or migration evidence appeared during apply")
    finalized: list[Path] = []
    try:
        target_temp.replace(target_path)
        finalized.append(target_path)
        evidence_temp.replace(evidence_path)
        finalized.append(evidence_path)
    except Exception:
        for path in finalized:
            try:
                path.unlink()
            except OSError:
                pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate a SiRUP checkpoint from v2 to v3.")
    parser.add_argument("--source-checkpoint", required=True, type=Path)
    parser.add_argument("--target-checkpoint", required=True, type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-database-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for field in ("expected_source_sha256", "expected_database_sha256"):
        value = getattr(args, field).lower()
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            parser.error(f"--{field.replace('_', '-')} must be a SHA-256 hex digest")
        setattr(args, field, value)
    return args


def main() -> int:
    args = parse_args()
    try:
        plan = build_plan(
            args.source_checkpoint,
            args.target_checkpoint,
            args.expected_source_sha256,
            args.expected_database_sha256,
        )
        print(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True))
        if args.apply:
            apply_plan(plan)
    except Exception as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
