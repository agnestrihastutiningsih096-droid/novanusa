"""Pure projection of collected LPSE detail rows into canonical candidates."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from current_procurement_contracts import (
    RawExecutionCandidate,
    SourceKind,
    SourceProvenance,
)


class LpseExecutionProjectionError(ValueError):
    """The LPSE row cannot be projected without fabricating required data."""


def _required_text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LpseExecutionProjectionError(f"{field} is required")
    return value


def _optional_text(row: Mapping[str, object], field: str) -> str | None:
    value = row.get(field)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise LpseExecutionProjectionError(f"{field} must be text when present")
    return value


def _source_year(row: Mapping[str, object]) -> int:
    value = row.get("fiscal_year")
    if isinstance(value, bool):
        raise LpseExecutionProjectionError("fiscal_year is required")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise LpseExecutionProjectionError("fiscal_year is required")


def _contract_value(row: Mapping[str, object]) -> Decimal | None:
    # The collector deliberately combines HPS and pagu in one field. Even a
    # numeric representation cannot establish canonical contract-value meaning.
    return None


def project_lpse_row_to_raw_execution_candidate(
    row: Mapping[str, object], provenance: SourceProvenance
) -> RawExecutionCandidate:
    """Return a canonical raw candidate without I/O, mutation, or authority calls."""
    if not isinstance(row, Mapping):
        raise LpseExecutionProjectionError("row must be a mapping")
    if not isinstance(provenance, SourceProvenance):
        raise LpseExecutionProjectionError("usable SourceProvenance is required")
    if provenance.source_kind is not SourceKind.LPSE:
        raise LpseExecutionProjectionError("provenance must identify an LPSE source")

    package_code = _required_text(row, "package_code")
    package_title = _required_text(row, "package_name")
    execution_stage = _required_text(row, "stage_or_status")

    return RawExecutionCandidate(
        execution_id=f"lpse:{package_code}",
        source_package_id=package_code,
        source_kind=SourceKind.LPSE,
        id_satker_if_present=None,
        id_kldi_if_present=None,
        institution_name_if_present=_optional_text(row, "institution_name"),
        package_title=package_title,
        execution_stage=execution_stage,
        procurement_method_if_present=_optional_text(row, "method"),
        contract_value_if_present=_contract_value(row),
        source_year=_source_year(row),
        provenance=provenance,
    )
