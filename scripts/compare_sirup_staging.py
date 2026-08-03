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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_snapshot(path: Path) -> tuple[Path, Path]:
    resolved = path.resolve()
    if resolved.is_dir():
        return resolved / DATABASE_NAME, resolved / MANIFEST_NAME
    return resolved, resolved.parent / MANIFEST_NAME


def canonical_digest(columns: list[str], values: tuple[Any, ...]) -> str:
    content = dict(zip(columns, values))
    encoded = json.dumps(
        content,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_snapshot(database_path: Path) -> tuple[list[tuple[str, str]], dict[int, str]]:
    if not database_path.is_file():
        raise RuntimeError(f"DuckDB does not exist: {database_path}")
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        tables = {row[0] for row in connection.execute("show tables").fetchall()}
        if TABLE_NAME not in tables:
            raise RuntimeError(f"required table {TABLE_NAME!r} is missing: {database_path}")
        schema_rows = connection.execute(f"pragma table_info('{TABLE_NAME}')").fetchall()
        schema = [(str(row[1]), str(row[2]).upper()) for row in schema_rows]
        columns = [name for name, _ in schema]
        if not columns or columns[0] != "id":
            raise RuntimeError(f"first table column must be 'id': {database_path}")
        rows = connection.execute(f"select * from {TABLE_NAME} order by id").fetchall()
    finally:
        connection.close()

    digests: dict[int, str] = {}
    content_columns = columns[1:]
    for row in rows:
        identifier = int(row[0])
        if identifier in digests:
            raise RuntimeError(f"duplicate ID {identifier} in {database_path}")
        digests[identifier] = canonical_digest(content_columns, row[1:])
    return schema, digests


def load_source_count(manifest_path: Path) -> int:
    if not manifest_path.is_file():
        raise RuntimeError(f"manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"manifest is not readable JSON: {manifest_path}: {exc}") from exc
    source_count = manifest.get("source_records_filtered") if isinstance(manifest, dict) else None
    if not isinstance(source_count, int):
        raise RuntimeError(f"manifest source_records_filtered is not an integer: {manifest_path}")
    return source_count


def compare(baseline: Path, candidate: Path) -> dict[str, Any]:
    baseline_db, baseline_manifest = resolve_snapshot(baseline)
    candidate_db, candidate_manifest = resolve_snapshot(candidate)
    baseline_schema, baseline_rows = load_snapshot(baseline_db)
    candidate_schema, candidate_rows = load_snapshot(candidate_db)
    if baseline_schema != candidate_schema:
        raise RuntimeError(
            f"snapshot schema mismatch: baseline={baseline_schema!r}, candidate={candidate_schema!r}"
        )

    baseline_ids = set(baseline_rows)
    candidate_ids = set(candidate_rows)
    added_ids = sorted(candidate_ids - baseline_ids)
    missing_ids = sorted(baseline_ids - candidate_ids)
    shared_ids = baseline_ids & candidate_ids
    changed_ids = sorted(
        identifier
        for identifier in shared_ids
        if baseline_rows[identifier] != candidate_rows[identifier]
    )
    baseline_source_count = load_source_count(baseline_manifest)
    candidate_source_count = load_source_count(candidate_manifest)

    return {
        "baseline": str(baseline_db),
        "candidate": str(candidate_db),
        "baseline_sha256": sha256_file(baseline_db),
        "candidate_sha256": sha256_file(candidate_db),
        "baseline_row_count": len(baseline_rows),
        "candidate_row_count": len(candidate_rows),
        "row_count_difference": len(candidate_rows) - len(baseline_rows),
        "ids_added": added_ids,
        "ids_added_count": len(added_ids),
        "ids_missing": missing_ids,
        "ids_missing_count": len(missing_ids),
        "ids_changed": changed_ids,
        "ids_changed_count": len(changed_ids),
        "shared_id_count": len(shared_ids),
        "baseline_source_count": baseline_source_count,
        "candidate_source_count": candidate_source_count,
        "source_count_difference": candidate_source_count - baseline_source_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two SiRUP staging snapshots using read-only DuckDB connections."
    )
    parser.add_argument("baseline", type=Path, help="Baseline staging run directory or DuckDB.")
    parser.add_argument("candidate", type=Path, help="Candidate staging run directory or DuckDB.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="JSON report path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = compare(args.baseline, args.candidate)
        output_path = args.output.resolve()
        report = {"status": "passed", **result}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (duckdb.Error, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "report": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
