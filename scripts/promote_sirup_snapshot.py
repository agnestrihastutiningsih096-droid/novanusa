from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import threading
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from validate_sirup_promotion import DEFAULT_COMPARISON_NAME, _evaluate_genesis, evaluate


STAGING_DATABASE_NAME = "sirup_staging.duckdb"
DATABASE_NAME = "sirup.duckdb"
MANIFEST_NAME = "manifest.json"
POINTER_VERSION = 1
SELECTION_VERSION = 1
SNAPSHOT_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PromotionError(RuntimeError):
    """A fail-closed promotion rejection."""


_CAPABILITY_REGISTRY: weakref.WeakKeyDictionary[object, dict[str, Any]] = (
    weakref.WeakKeyDictionary()
)
_CAPABILITY_REGISTRY_LOCK = threading.Lock()


class _GenesisCapability:
    """Opaque handle whose authority exists only in the identity registry."""

    __slots__ = ("__weakref__",)

    def __new__(cls, *args: object, **kwargs: object) -> _GenesisCapability:
        raise TypeError("genesis capabilities can only be created by lock acquisition")

    def __copy__(self) -> object:
        raise TypeError("genesis capabilities cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> object:
        raise TypeError("genesis capabilities cannot be deep-copied")

    def __reduce__(self) -> object:
        raise TypeError("genesis capabilities cannot be serialized")

    def __reduce_ex__(self, protocol: int) -> object:
        raise TypeError("genesis capabilities cannot be serialized")

    def __getstate__(self) -> object:
        raise TypeError("genesis capabilities cannot be serialized")

    @property
    def _fd(self) -> int:
        return int(_capability_state(self)["fd"])

    @_fd.setter
    def _fd(self, value: int) -> None:
        _capability_state(self)["fd"] = value

    def __getattr__(self, name: str) -> object:
        if name in {"lock_path", "canonical_root", "candidate_path", "run_id", "nonce", "consumed"}:
            return _capability_state(self)[name]
        raise AttributeError(name)

    def close(self) -> None:
        state = _capability_state(self)
        if state["fd"] < 0:
            return
        try:
            _verify_held_lock(state)
            same_lock = True
        except (OSError, RuntimeError):
            same_lock = False
        os.close(state["fd"])
        state["fd"] = -1
        if same_lock:
            state["lock_path"].unlink(missing_ok=True)


def _capability_state(capability: object) -> dict[str, Any]:
    with _CAPABILITY_REGISTRY_LOCK:
        state = _CAPABILITY_REGISTRY.get(capability)
    if state is None:
        raise RuntimeError("unregistered genesis capability")
    return state


def _acquire_genesis_capability(lock_path: Path, candidate_path: Path) -> _GenesisCapability:
    """Acquire the held-FD authority, then register exactly one opaque handle."""
    lock_path = lock_path.resolve()
    candidate_path = candidate_path.resolve()
    run_id = str(uuid4())
    nonce = uuid4().hex
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    except FileExistsError as exc:
        raise PromotionError("promotion authority is already held") from exc
    metadata = {
            "nonce": nonce,
            "candidate_path": str(candidate_path),
            "run_id": run_id,
            "acquired_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pid": os.getpid(),
        }
    try:
        os.write(fd, (json.dumps(metadata, sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(fd)
        capability = object.__new__(_GenesisCapability)
        with _CAPABILITY_REGISTRY_LOCK:
            _CAPABILITY_REGISTRY[capability] = {
                "fd": fd, "lock_path": lock_path,
                "canonical_root": lock_path.parent,
                "candidate_path": candidate_path, "run_id": run_id,
                "nonce": nonce, "consumed": False,
            }
        return capability
    except BaseException:
        os.close(fd)
        lock_path.unlink(missing_ok=True)
        raise


def _verify_held_lock(state: dict[str, Any]) -> None:
    if state["fd"] < 0:
        raise RuntimeError("genesis promotion lock descriptor is closed")
    held = os.fstat(state["fd"])
    current = os.stat(state["lock_path"])
    if not os.path.samestat(held, current):
        raise RuntimeError("genesis promotion lock path identity changed")


def _validate_and_consume_genesis_capability(
    capability: object, candidate_path: Path, run_id: str | None,
    expected_active: str | None,
) -> bool | None:
    """Return None for non-authority; otherwise burn and validate the handle."""
    with _CAPABILITY_REGISTRY_LOCK:
        try:
            state = _CAPABILITY_REGISTRY.get(capability)
        except (TypeError, AttributeError):
            return None
        if state is None:
            return None
        if state["consumed"]:
            return False
        # Every attempted consumption burns the capability, including a failed
        # binding check, so it can never be replayed against another candidate.
        state["consumed"] = True
    try:
        _verify_held_lock(state)
        if expected_active is not None:
            raise RuntimeError("genesis requires expected active to be none")
        if run_id != state["run_id"]:
            raise RuntimeError("genesis promotion run binding mismatch")
        if candidate_path.resolve() != state["candidate_path"]:
            raise RuntimeError("genesis candidate binding mismatch")
        if (state["canonical_root"] / "selection.json").exists():
            raise RuntimeError("genesis requires absent canonical selection")
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromotionError(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"JSON artifact is not an object: {path}")
    return value


def pointer_for(snapshot_id: str, database_sha256: str, manifest_sha256: str) -> dict[str, Any]:
    if not SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise PromotionError(f"invalid snapshot ID: {snapshot_id!r}")
    base = f"snapshots/{snapshot_id}"
    return {
        "pointer_version": POINTER_VERSION,
        "snapshot_id": snapshot_id,
        "database": f"{base}/{DATABASE_NAME}",
        "database_sha256": database_sha256,
        "manifest": f"{base}/{MANIFEST_NAME}",
        "manifest_sha256": manifest_sha256,
    }


def validate_pointer(pointer: dict[str, Any], canonical_root: Path) -> None:
    snapshot_id = pointer.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise PromotionError("active pointer has an invalid snapshot ID")
    expected = pointer_for(
        snapshot_id,
        str(pointer.get("database_sha256", "")),
        str(pointer.get("manifest_sha256", "")),
    )
    if pointer != expected:
        raise PromotionError("active pointer has invalid or unexpected fields")
    for field in ("database_sha256", "manifest_sha256"):
        if not SNAPSHOT_ID_PATTERN.fullmatch(pointer[field]):
            raise PromotionError(f"active pointer has invalid {field}")
    database = canonical_root / pointer["database"]
    manifest = canonical_root / pointer["manifest"]
    if not database.is_file() or not manifest.is_file():
        raise PromotionError("active pointer references missing snapshot artifacts")
    if sha256_file(database) != pointer["database_sha256"]:
        raise PromotionError("active snapshot database hash mismatch")
    if sha256_file(manifest) != pointer["manifest_sha256"]:
        raise PromotionError("active snapshot manifest hash mismatch")


def selection_for(
    active: dict[str, Any], rollback: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "selection_version": SELECTION_VERSION,
        "active": active,
        "rollback": rollback,
    }


def validate_selection(selection: dict[str, Any], canonical_root: Path) -> None:
    if set(selection) != {"selection_version", "active", "rollback"}:
        raise PromotionError("selection has invalid or unexpected fields")
    if selection.get("selection_version") != SELECTION_VERSION:
        raise PromotionError("selection has an unsupported version")
    active = selection.get("active")
    rollback = selection.get("rollback")
    if not isinstance(active, dict):
        raise PromotionError("selection active pointer is not an object")
    if rollback is not None and not isinstance(rollback, dict):
        raise PromotionError("selection rollback pointer is neither null nor an object")
    validate_pointer(active, canonical_root)
    if rollback is not None:
        validate_pointer(rollback, canonical_root)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def install_snapshot(
    canonical_root: Path,
    source_database: Path,
    source_manifest: Path,
    pointer: dict[str, Any],
) -> Path:
    snapshots = canonical_root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    target = snapshots / pointer["snapshot_id"]
    if target.exists():
        if not target.is_dir():
            raise PromotionError(f"snapshot target is not a directory: {target}")
        database = target / DATABASE_NAME
        manifest = target / MANIFEST_NAME
        if (
            not database.is_file()
            or not manifest.is_file()
            or sha256_file(database) != pointer["database_sha256"]
            or sha256_file(manifest) != pointer["manifest_sha256"]
        ):
            raise PromotionError(f"existing snapshot has incompatible contents: {target}")
        return target

    temporary = Path(tempfile.mkdtemp(prefix=f".{pointer['snapshot_id']}.", dir=snapshots))
    try:
        shutil.copyfile(source_database, temporary / DATABASE_NAME)
        shutil.copyfile(source_manifest, temporary / MANIFEST_NAME)
        if sha256_file(temporary / DATABASE_NAME) != pointer["database_sha256"]:
            raise PromotionError("installed database hash verification failed")
        if sha256_file(temporary / MANIFEST_NAME) != pointer["manifest_sha256"]:
            raise PromotionError("installed manifest hash verification failed")
        os.chmod(temporary / DATABASE_NAME, stat.S_IREAD)
        os.chmod(temporary / MANIFEST_NAME, stat.S_IREAD)
        try:
            os.replace(temporary, target)
        except FileExistsError:
            raise PromotionError(f"snapshot target appeared concurrently: {target}")
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return target


def promote(
    run_dir: Path,
    canonical_root: Path,
    expected_active: str | None,
    comparison_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    canonical_root = canonical_root.resolve()
    comparison_path = (comparison_path or run_dir / DEFAULT_COMPARISON_NAME).resolve()
    database = run_dir / STAGING_DATABASE_NAME
    manifest = run_dir / MANIFEST_NAME
    if not database.is_file() or not manifest.is_file():
        raise PromotionError("required staging database or manifest is missing")

    canonical_root_preexisted = canonical_root.exists()
    canonical_root.mkdir(parents=True, exist_ok=True)
    capability = _acquire_genesis_capability(canonical_root / ".promotion.lock", run_dir)
    try:
        selection_path = canonical_root / "selection.json"
        obsolete_paths = (canonical_root / "active.json", canonical_root / "rollback.json")
        if any(path.exists() for path in obsolete_paths):
            raise PromotionError("obsolete independent pointer file creates ambiguous authority")
        if selection_path.exists():
            committed_selection = load_object(selection_path)
            validate_selection(committed_selection, canonical_root)
            current = committed_selection["active"]
            current_id = current["snapshot_id"]
        else:
            current = None
            current_id = None
        if current_id != expected_active:
            raise PromotionError(
                f"stale expected-active authority: expected {expected_active!r}, found {current_id!r}"
            )
        if current is None:
            eligibility = _evaluate_genesis(
                run_dir,
                comparison_path,
                capability,
                capability.run_id,
                expected_active,
            )
        else:
            eligibility = evaluate(run_dir, comparison_path)
        if eligibility.get("promotion_eligible") is not True or eligibility.get("result") != "PASS":
            raise PromotionError("existing promotion validator rejected the staging run")
        manifest_value = load_object(manifest)
        database_hash = sha256_file(database)
        if manifest_value.get("sha256") != database_hash:
            raise PromotionError("staging manifest/database hash mismatch")
        manifest_hash = sha256_file(manifest)
        snapshot_id = database_hash
        new_pointer = pointer_for(snapshot_id, database_hash, manifest_hash)
        if current_id == snapshot_id:
            raise PromotionError("target snapshot is already active")

        if current is not None:
            comparison = load_object(comparison_path)
            if comparison.get("baseline_sha256") != current["database_sha256"]:
                raise PromotionError("comparison baseline does not match the active snapshot")

        install_snapshot(canonical_root, database, manifest, new_pointer)
        next_selection = selection_for(new_pointer, current)
        validate_selection(next_selection, canonical_root)
        atomic_write_json(selection_path, next_selection)
        return {
            "status": "promoted",
            "snapshot_id": snapshot_id,
            "selection": str(selection_path),
        }
    finally:
        capability.close()
        if not canonical_root_preexisted:
            try:
                canonical_root.rmdir()
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and atomically select an eligible SiRUP snapshot.")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--canonical-root", type=Path, default=Path("data/sirup"))
    parser.add_argument("--comparison-report", type=Path)
    parser.add_argument(
        "--expected-active",
        required=True,
        help="Expected active snapshot ID, or 'none' for first promotion.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = None if args.expected_active == "none" else args.expected_active
    try:
        result = promote(args.run_dir, args.canonical_root, expected, args.comparison_report)
    except (OSError, PromotionError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
