from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

from current_procurement_contracts import (
    AcquisitionResult,
    RawCurrentRupCandidate,
    SourceAvailability,
    SourceKind,
    SourceMaturity,
    SourceProvenance,
    validate_current_rup_provider_result,
)
from sirup_receipt_chain import RECEIPTS_NAME, _parse_lines, verify_receipt_chain
from validate_sirup_staging import (
    DATABASE_NAME,
    MANIFEST_NAME,
    TABLE_NAME,
    load_manifest,
    validate,
)


class CurrentRupSirupAdapterError(RuntimeError):
    pass


def _validated_evidence(run_dir: Path) -> tuple[dict, dict, dict]:
    checks, errors = validate(run_dir)
    if errors or checks.get("schema") is not True:
        raise CurrentRupSirupAdapterError(
            "invalid canonical SiRUP run: " + "; ".join(errors or ["schema mismatch"])
        )
    manifest = load_manifest(run_dir / MANIFEST_NAME)
    if manifest.get("manifest_version") != 1:
        raise CurrentRupSirupAdapterError("unsupported manifest schema version")
    chain = verify_receipt_chain(run_dir, manifest=manifest, require_completion=True)
    if not chain.get("valid") or not chain.get("promotion_valid"):
        raise CurrentRupSirupAdapterError(
            "invalid terminal receipt evidence: " + "; ".join(chain.get("failures", []))
        )
    try:
        receipts = _parse_lines(run_dir / RECEIPTS_NAME)
        anchor, terminal = receipts[0], receipts[-1]
        if (
            chain["run_id"] != run_dir.name
            or anchor["run_id"] != chain["run_id"]
            or terminal["run_id"] != chain["run_id"]
            or terminal["hash"] != chain["terminal_hash"]
            or terminal["receipt_type"] != "COMPLETION"
        ):
            raise CurrentRupSirupAdapterError("receipt/run identity mismatch")
        year = anchor["payload"]["year"]
        if not isinstance(year, int) or isinstance(year, bool):
            raise CurrentRupSirupAdapterError("validated acquisition year is invalid")
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise CurrentRupSirupAdapterError("malformed validated receipt evidence") from exc
    return manifest, chain, {"observed_at": terminal["timestamp"], "year": year}


def acquire(run_directory: str | Path, *, limit: int | None = None) -> AcquisitionResult[RawCurrentRupCandidate]:
    run_dir = Path(run_directory).resolve()
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
        raise CurrentRupSirupAdapterError("limit must be a positive integer")
    manifest, chain, receipt = _validated_evidence(run_dir)
    database_path = run_dir / DATABASE_NAME
    provenance = SourceProvenance(
        source_kind=SourceKind.CURRENT_SIRUP,
        source_locator=f"{database_path.resolve()}#sha256={manifest['sha256']}",
        observed_at=receipt["observed_at"],
        acquisition_id=chain["run_id"],
        raw_receipt_id=chain["terminal_hash"],
        schema_version=str(manifest["manifest_version"]),
        source_maturity=SourceMaturity.BOUNDED_ACQUISITION_VERIFIED,
    )
    sql = (
        "select id, id_referensi, idSatker, idKldi, satuanKerja, kldi, paket, "
        "cast(pagu as varchar), jenisPengadaan, metode, pemilihan, lokasi "
        f"from {TABLE_NAME} order by id"
    )
    parameters: list[int] = []
    if limit is not None:
        sql += " limit ?"
        parameters.append(limit)
    try:
        connection = duckdb.connect(str(database_path), read_only=True)
        try:
            rows = connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()
    except duckdb.Error as exc:
        raise CurrentRupSirupAdapterError(f"canonical SiRUP database read failed: {exc}") from exc

    candidates = []
    for row in rows:
        if len(row) != 12 or any(row[index] is None for index in (0, 1, 2, 3)):
            raise CurrentRupSirupAdapterError("row is missing required SiRUP identity fields")
        if any(row[index] is None or not isinstance(row[index], str) for index in (3, 4, 5, 6, 8, 9, 10, 11)):
            raise CurrentRupSirupAdapterError("row cannot preserve required contract text semantics")
        try:
            budget = None if row[7] is None else Decimal(row[7])
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise CurrentRupSirupAdapterError("row budget is not Decimal-compatible") from exc
        candidates.append(RawCurrentRupCandidate(
            planned_procurement_id=str(row[0]), source_rup_id=str(row[0]),
            id_satker=str(row[2]), id_kldi=row[3], institution_name=row[4],
            kldi_name=row[5], package_title=row[6], budget=budget,
            procurement_type=row[8], procurement_method=row[9],
            selection_period=row[10], location=row[11],
            source_year=receipt["year"], provenance=provenance,
        ))
    result = AcquisitionResult(
        candidates=tuple(candidates), provenance=provenance,
        availability=SourceAvailability.SOURCE_PARTIAL,
        no_result=False, deduplicated=False,
    )
    validate_current_rup_provider_result(result)
    return result
