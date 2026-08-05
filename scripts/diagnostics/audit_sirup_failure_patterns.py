"""Audit missing required fields in persisted SiRUP collector failures.

This is an offline diagnostic. It reads JSON evidence files below directories
named ``failures`` and writes a JSON summary; it does not import or invoke the
collector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "audit" / "sirup_failure_pattern_summary.json"
REQUIRED_FIELDS = {
    "id",
    "id_referensi",
    "pagu",
    "satuanKerja",
    "kldi",
    "lokasi",
    "jenisPengadaan",
    "metode",
    "sumberDana",
    "paket",
    "pemilihan",
    "idBulan",
}


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def failure_files(search_root: Path) -> list[Path]:
    return sorted(
        path
        for path in search_root.rglob("*.json")
        if path.is_file() and "failures" in path.parts
    )


def display_value(value: Any) -> Any:
    """Keep scalar source values intact and make unusual values JSON-safe."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def audit(search_root: Path) -> dict[str, Any]:
    files = failure_files(search_root)
    missing_frequency: Counter[str] = Counter()
    jenis_id_frequency: Counter[str] = Counter()
    identifier_occurrences: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    affected_packages: list[dict[str, Any]] = []
    payload_hashes: list[dict[str, Any]] = []
    unreadable_files: list[dict[str, str]] = []

    for path in files:
        relative_path = path.relative_to(search_root).as_posix()
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            unreadable_files.append({"file": relative_path, "error": str(exc)})
            continue

        payload = evidence.get("payload") if isinstance(evidence, dict) else None
        if not isinstance(payload, dict):
            unreadable_files.append(
                {"file": relative_path, "error": "evidence payload is not an object"}
            )
            continue

        payload_hashes.append(
            {"file": relative_path, "sha256": canonical_sha256(payload)}
        )
        rows = payload.get("data")
        if not isinstance(rows, list):
            unreadable_files.append(
                {"file": relative_path, "error": "payload data is not an array"}
            )
            continue

        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue

            package_id = display_value(row.get("id"))
            if "id" in row:
                identifier_key = json.dumps(
                    row["id"], sort_keys=True, ensure_ascii=False
                )
                identifier_occurrences[identifier_key].append(
                    {"file": relative_path, "row_index": row_index}
                )

            missing = sorted(REQUIRED_FIELDS - row.keys())
            if not missing:
                continue

            missing_frequency.update(missing)
            if "jenisPengadaan" in missing:
                jenis_value = display_value(row.get("idJenisPengadaan"))
                jenis_key = json.dumps(jenis_value, sort_keys=True, ensure_ascii=False)
                jenis_id_frequency[jenis_key] += 1

            affected_packages.append(
                {
                    "file": relative_path,
                    "row_index": row_index,
                    "package_id": package_id,
                    "package_name": display_value(row.get("paket")),
                    "missing_fields": missing,
                }
            )

    duplicates = []
    for encoded_id, occurrences in identifier_occurrences.items():
        if len(occurrences) > 1:
            duplicates.append(
                {
                    "package_id": json.loads(encoded_id),
                    "occurrence_count": len(occurrences),
                    "occurrences": occurrences,
                }
            )
    duplicates.sort(key=lambda item: str(item["package_id"]))

    jenis_frequencies = [
        {"idJenisPengadaan": json.loads(key), "count": count}
        for key, count in jenis_id_frequency.items()
    ]
    jenis_frequencies.sort(
        key=lambda item: (-item["count"], str(item["idJenisPengadaan"]))
    )

    return {
        "search_root": str(search_root),
        "required_fields": sorted(REQUIRED_FIELDS),
        "total_failure_files": len(files),
        "readable_payload_files": len(payload_hashes),
        "unreadable_or_invalid_files": unreadable_files,
        "missing_field_frequency": dict(sorted(missing_frequency.items())),
        "idJenisPengadaan_frequency_when_jenisPengadaan_missing": jenis_frequencies,
        "package_ids": [item["package_id"] for item in affected_packages],
        "package_names": [item["package_name"] for item in affected_packages],
        "packages_with_missing_fields": affected_packages,
        "duplicate_ids": duplicates,
        "payload_sha256": payload_hashes,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit required-field patterns in SiRUP failure evidence."
    )
    parser.add_argument(
        "--search-root",
        type=Path,
        default=ROOT,
        help="Tree to scan for failures directories (default: repository root).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Summary JSON path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    search_root = args.search_root.resolve()
    output = args.output.resolve()
    report = audit(search_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {report['total_failure_files']} failure files to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
