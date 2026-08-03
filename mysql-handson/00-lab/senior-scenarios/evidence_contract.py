"""Append-only evidence primitives for the containerized senior scenarios."""

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


PROGRAM_MARKERS = {
    "export_runner.py": "EXPORT_SQL",
    "scenario_controller.py": "KILL_PREFLIGHT_SQL",
    "freeze_audit.py": "def audit_task10_freeze",
}

HISTORICAL_PATHS = (
    "/private/tmp/mysql-senior-scenarios.SJ38zd",
    "/private/tmp/mysql-senior-scenarios.LxogM8",
    "/private/tmp/mysql-senior-scenarios.UJXwDE",
    "/private/tmp/mysql-senior-scenarios.VW9rGt",
    "/private/tmp/mysql-senior-scenarios.rmovUN",
    "/private/tmp/mysql-senior-scenarios.LjCY6E",
)
HISTORICAL_LOSS_FILENAME = "historical-loss.json"
HISTORICAL_LOSS_STATUS = "historical_evidence_lost"

PHASES = (
    "00-seed-freeze",
    "10-kill-smoke",
    "20-controls-calibration",
    "30-buffered",
    "40-chunked",
    "50-resume-audit",
    "60-final",
)


def extract_programs(markdown: str) -> dict[str, str]:
    """Extract the three fenced programs by their stable ownership markers."""
    blocks = re.findall(r"```python\n(.*?)```", markdown, flags=re.DOTALL)
    result: dict[str, str] = {}
    for filename, marker in PROGRAM_MARKERS.items():
        matches = [block for block in blocks if marker in block]
        if len(matches) != 1:
            raise ValueError(
                f"expected exactly one Python fence for {marker!r}, got {len(matches)}"
            )
        result[filename] = matches[0]
    return result


def require_exact_int(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{field} must be exact int")
    return value


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_replaceable_json(path: Path, value: object) -> None:
    """Atomically replace bootstrap JSON after making its bytes durable."""
    encoded = _json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_immutable_json(path: Path, value: object) -> None:
    """Create a JSON file once; its path can never be replaced."""
    encoded = _json_bytes(value)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())


def create_historical_loss(runtime_root: Path) -> Path:
    """Record the six lost historical roots without claiming verification succeeded."""
    target = runtime_root / HISTORICAL_LOSS_FILENAME
    write_immutable_json(
        target,
        {
            "historical_paths": list(HISTORICAL_PATHS),
            "status": HISTORICAL_LOSS_STATUS,
            "verification_succeeded": False,
        },
    )
    return target


def _manifest_path(runtime_root: Path, phase: str) -> Path:
    return runtime_root / f"phase-manifest-{phase}.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_regular_files(runtime_root: Path, excluded: Path) -> list[dict[str, Any]]:
    """Return all regular files in deterministic relative-path order, rejecting others."""
    root = runtime_root.resolve()
    if not root.is_dir():
        raise ValueError("runtime root must be a directory")
    excluded_relative = excluded.relative_to(root).as_posix()
    entries: list[dict[str, Any]] = []

    def visit(directory: Path) -> None:
        with os.scandir(directory) as children:
            for child in sorted(children, key=lambda item: item.name):
                child_path = Path(child.path)
                child_stat = child.stat(follow_symlinks=False)
                if stat.S_ISDIR(child_stat.st_mode):
                    visit(child_path)
                    continue
                if not stat.S_ISREG(child_stat.st_mode):
                    raise ValueError(f"non-regular evidence entry: {child_path}")
                relative_path = child_path.relative_to(root).as_posix()
                if relative_path == excluded_relative:
                    continue
                entries.append(
                    {
                        "path": relative_path,
                        "size": require_exact_int(child_stat.st_size, "size"),
                        "sha256": _sha256_file(child_path),
                    }
                )

    visit(root)
    return sorted(entries, key=lambda entry: entry["path"])


def _tree_hash(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(
            f"{entry['path']}\0{entry['size']}\0{entry['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _exact_value_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        left_dict = left
        right_dict = right
        if set(left_dict) != set(right_dict):
            return False
        return all(_exact_value_equal(left_dict[key], right_dict[key]) for key in left_dict)
    if type(left) in (list, tuple):
        left_sequence = left
        right_sequence = right
        return len(left_sequence) == len(right_sequence) and all(
            _exact_value_equal(left_item, right_item)
            for left_item, right_item in zip(left_sequence, right_sequence)
        )
    return left == right


def _require_json_value(value: object, field: str) -> None:
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _require_json_value(item, f"{field}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{field} has non-string key")
            _require_json_value(item, f"{field}.{key}")
        return
    raise ValueError(f"{field} is not JSON-compatible")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid phase manifest: {path}") from error
    if type(value) is not dict:
        raise ValueError(f"invalid phase manifest: {path}")
    return value


def _verify_manifest(runtime_root: Path, phase: str, binding: object) -> None:
    manifest = _read_manifest(_manifest_path(runtime_root, phase))
    if set(manifest) != {"binding", "entries", "phase", "tree_hash"}:
        raise ValueError(f"invalid phase manifest fields: {phase}")
    if manifest["phase"] != phase or type(manifest["phase"]) is not str:
        raise ValueError(f"invalid phase manifest phase: {phase}")
    _require_json_value(manifest["binding"], "binding")
    _require_json_value(binding, "binding")
    if not _exact_value_equal(manifest["binding"], binding):
        raise ValueError(f"phase manifest binding mismatch: {phase}")
    entries = manifest["entries"]
    if type(entries) is not list:
        raise ValueError(f"invalid phase manifest entries: {phase}")
    previous_path = ""
    verified_entries: list[dict[str, Any]] = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "size", "sha256"}:
            raise ValueError(f"invalid phase manifest entry: {phase}")
        entry_path = entry["path"]
        entry_size = entry["size"]
        entry_hash = entry["sha256"]
        if type(entry_path) is not str or not entry_path or entry_path <= previous_path:
            raise ValueError(f"invalid phase manifest entry order: {phase}")
        relative_path = Path(entry_path)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative_path.as_posix() != entry_path
        ):
            raise ValueError(f"invalid phase manifest entry path: {phase}")
        if type(entry_hash) is not str or len(entry_hash) != 64:
            raise ValueError(f"invalid phase manifest entry hash: {phase}")
        require_exact_int(entry_size, "size")
        candidate = runtime_root / relative_path
        try:
            candidate_stat = candidate.stat(follow_symlinks=False)
        except OSError as error:
            raise ValueError(f"recorded evidence file missing: {entry_path}") from error
        if not stat.S_ISREG(candidate_stat.st_mode):
            raise ValueError(f"recorded evidence file is not regular: {entry_path}")
        actual = {
            "path": entry_path,
            "size": candidate_stat.st_size,
            "sha256": _sha256_file(candidate),
        }
        if not _exact_value_equal(entry, actual):
            raise ValueError(f"recorded evidence file changed: {entry_path}")
        verified_entries.append(entry)
        previous_path = entry_path
    if type(manifest["tree_hash"]) is not str or manifest["tree_hash"] != _tree_hash(verified_entries):
        raise ValueError(f"phase manifest tree hash mismatch: {phase}")


def verify_final_coverage(runtime_root: Path, binding: object) -> None:
    """Require the final manifest to cover every regular file except itself."""
    target = _manifest_path(runtime_root, "60-final")
    _verify_manifest(runtime_root, "60-final", binding)
    manifest = _read_manifest(target)
    actual_entries = _scan_regular_files(runtime_root, target)
    if not _exact_value_equal(manifest["entries"], actual_entries):
        raise ValueError("final manifest does not cover the complete evidence tree")


def create_phase_manifest(runtime_root: Path, phase: str, binding: object) -> Path:
    """Append the next phase manifest after verifying every prior phase."""
    root = Path(runtime_root)
    if type(phase) is not str or phase not in PHASES:
        raise ValueError("unknown phase")
    _require_json_value(binding, "binding")
    phase_index = PHASES.index(phase)
    target = _manifest_path(root, phase)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    for later_phase in PHASES[phase_index + 1 :]:
        if _manifest_path(root, later_phase).exists() or _manifest_path(root, later_phase).is_symlink():
            raise ValueError("phase skip or reordering is not allowed")
    for previous_phase in PHASES[:phase_index]:
        previous_manifest = _manifest_path(root, previous_phase)
        if not previous_manifest.is_file() or previous_manifest.is_symlink():
            raise ValueError("phase skip or reordering is not allowed")
        _verify_manifest(root, previous_phase, binding)
    entries = _scan_regular_files(root, target)
    manifest = {
        "binding": binding,
        "entries": entries,
        "phase": phase,
        "tree_hash": _tree_hash(entries),
    }
    write_immutable_json(target, manifest)
    if phase == "60-final":
        verify_final_coverage(root, binding)
    return target
