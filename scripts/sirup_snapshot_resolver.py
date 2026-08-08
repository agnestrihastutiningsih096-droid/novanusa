from __future__ import annotations

from pathlib import Path
from typing import Any

from promote_sirup_snapshot import PromotionError, load_object, validate_selection


DEFAULT_CANONICAL_ROOT = Path("data/sirup")
SELECTION_NAME = "selection.json"


class SnapshotResolutionError(RuntimeError):
    """The canonical SiRUP read authority could not be verified."""


def _contained_path(canonical_root: Path, value: str) -> Path:
    candidate = (canonical_root / value).resolve()
    try:
        candidate.relative_to(canonical_root)
    except ValueError as exc:
        raise SnapshotResolutionError(
            f"snapshot artifact path escapes canonical root: {value!r}"
        ) from exc
    return candidate


def _preflight_pointer_paths(pointer: Any, canonical_root: Path) -> None:
    if not isinstance(pointer, dict):
        return
    for field in ("database", "manifest"):
        value = pointer.get(field)
        if isinstance(value, str):
            _contained_path(canonical_root, value)


def resolve_active_sirup_database(
    canonical_root: Path = DEFAULT_CANONICAL_ROOT,
) -> Path:
    """Return the verified active canonical SiRUP DuckDB path."""
    root = canonical_root.resolve()
    selection_path = root / SELECTION_NAME
    try:
        selection = load_object(selection_path)
        _preflight_pointer_paths(selection.get("active"), root)
        _preflight_pointer_paths(selection.get("rollback"), root)
        validate_selection(selection, root)
        return _contained_path(root, selection["active"]["database"])
    except SnapshotResolutionError:
        raise
    except (OSError, PromotionError) as exc:
        raise SnapshotResolutionError(str(exc)) from exc
