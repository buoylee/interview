"""Append-only evidence primitives for the containerized senior scenarios."""

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
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
HISTORICAL_LOSS_FILENAME = "historical-evidence-loss.json"
HISTORICAL_LOSS_STATUS = "LOST_BY_EXTERNAL_TMP_CLEANUP"
PHASE_STATUS = "COMPLETE"

PHASES = (
    "00-seed-freeze",
    "10-kill-smoke",
    "20-controls-calibration",
    "30-buffered",
    "40-chunked",
    "50-resume-audit",
    "60-final",
)


@dataclass(frozen=True)
class EvidenceBinding:
    """The full JSON-compatible identity shared by every phase manifest."""

    scenario_commit: str
    scenario_sha256: str
    mysql_image_id: str
    mysql_container_id: str
    harness_image_id: str
    network_name: str
    volume_name: str
    cpu_limit: str
    memory_limit_bytes: int
    pids_limit: int
    program_sha256: dict[str, str]

    def __post_init__(self) -> None:
        _validate_evidence_binding(self)

    def serialize(self) -> dict[str, object]:
        _validate_evidence_binding(self)
        return {
            "scenario_commit": self.scenario_commit,
            "scenario_sha256": self.scenario_sha256,
            "mysql_image_id": self.mysql_image_id,
            "mysql_container_id": self.mysql_container_id,
            "harness_image_id": self.harness_image_id,
            "network_name": self.network_name,
            "volume_name": self.volume_name,
            "cpu_limit": self.cpu_limit,
            "memory_limit_bytes": self.memory_limit_bytes,
            "pids_limit": self.pids_limit,
            "program_sha256": self.program_sha256,
        }


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


def write_historical_loss(runtime_root: Path) -> Path:
    """Record the six lost historical roots without claiming verification succeeded."""
    target = runtime_root / HISTORICAL_LOSS_FILENAME
    write_immutable_json(
        target,
        {
            "current_raw_verification": False,
            "historical_paths": list(HISTORICAL_PATHS),
            "status": HISTORICAL_LOSS_STATUS,
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


def _validate_evidence_binding(binding: EvidenceBinding) -> None:
    for field in (
        "scenario_commit",
        "scenario_sha256",
        "mysql_image_id",
        "mysql_container_id",
        "harness_image_id",
        "network_name",
        "volume_name",
        "cpu_limit",
    ):
        value = getattr(binding, field)
        if type(value) is not str or not value:
            raise ValueError(f"binding {field} must be a nonempty exact string")
    for field in ("memory_limit_bytes", "pids_limit"):
        value = getattr(binding, field)
        if type(value) is not int:
            raise ValueError(f"binding {field} must be an exact int")
    if type(binding.program_sha256) is not dict:
        raise ValueError("binding program_sha256 must be an exact dict")
    for filename, digest in binding.program_sha256.items():
        if type(filename) is not str or not filename:
            raise ValueError("binding program_sha256 keys must be nonempty exact strings")
        if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("binding program_sha256 values must be lowercase SHA-256")


def _binding_from_serialized(value: object) -> EvidenceBinding:
    if type(value) is not dict:
        raise ValueError("binding must be an exact dict")
    try:
        return EvidenceBinding(**value)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid serialized binding") from error


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid phase manifest: {path}") from error
    if type(value) is not dict:
        raise ValueError(f"invalid phase manifest: {path}")
    return value


def _verify_manifest(
    runtime_root: Path, phase: str, binding: EvidenceBinding
) -> dict[str, Any]:
    manifest = _read_manifest(_manifest_path(runtime_root, phase))
    if set(manifest) != {
        "binding",
        "byte_count",
        "entries",
        "file_count",
        "phase",
        "status",
        "timestamp",
        "tree_hash",
    }:
        raise ValueError(f"invalid phase manifest fields: {phase}")
    if manifest["phase"] != phase or type(manifest["phase"]) is not str:
        raise ValueError(f"invalid phase manifest phase: {phase}")
    if manifest["status"] != PHASE_STATUS or type(manifest["status"]) is not str:
        raise ValueError(f"invalid phase manifest status: {phase}")
    if (
        type(manifest["timestamp"]) is not str
        or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", manifest["timestamp"])
    ):
        raise ValueError(f"invalid phase manifest timestamp: {phase}")
    try:
        timestamp = datetime.fromisoformat(manifest["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid phase manifest timestamp: {phase}") from error
    if timestamp.tzinfo != timezone.utc:
        raise ValueError(f"invalid phase manifest timestamp: {phase}")
    serialized_binding = _binding_from_serialized(manifest["binding"])
    if not _exact_value_equal(manifest["binding"], binding.serialize()):
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
    if require_exact_int(manifest["file_count"], "file_count") != len(verified_entries):
        raise ValueError(f"phase manifest file count mismatch: {phase}")
    if require_exact_int(manifest["byte_count"], "byte_count") != sum(
        entry["size"] for entry in verified_entries
    ):
        raise ValueError(f"phase manifest byte count mismatch: {phase}")
    if not _exact_value_equal(serialized_binding.serialize(), manifest["binding"]):
        raise ValueError(f"invalid phase manifest binding: {phase}")
    return manifest


def verify_phase_manifests(
    runtime_root: Path, binding: EvidenceBinding
) -> list[dict[str, Any]]:
    """Verify the complete contiguous append-only prefix of phase manifests."""
    if type(binding) is not EvidenceBinding:
        raise ValueError("binding must be EvidenceBinding")
    manifests: list[dict[str, Any]] = []
    missing_phase_seen = False
    for phase in PHASES:
        path = _manifest_path(runtime_root, phase)
        if not path.exists() and not path.is_symlink():
            missing_phase_seen = True
            continue
        if missing_phase_seen or not path.is_file() or path.is_symlink():
            raise ValueError("phase skip or reordering is not allowed")
        manifests.append(_verify_manifest(runtime_root, phase, binding))
    return manifests


def verify_final_coverage(runtime_root: Path, final_manifest: dict[str, Any]) -> None:
    """Require the final manifest to cover every regular file except itself."""
    if type(final_manifest) is not dict:
        raise ValueError("final manifest must be an exact dict")
    target = _manifest_path(runtime_root, "60-final")
    manifest = _read_manifest(target)
    binding = _binding_from_serialized(manifest.get("binding"))
    _verify_manifest(runtime_root, "60-final", binding)
    if not _exact_value_equal(manifest, final_manifest):
        raise ValueError("final manifest argument does not match immutable record")
    actual_entries = _scan_regular_files(runtime_root, target)
    if not _exact_value_equal(manifest["entries"], actual_entries):
        raise ValueError("final manifest does not cover the complete evidence tree")


def create_phase_manifest(
    runtime_root: Path, phase: str, binding: EvidenceBinding
) -> Path:
    """Append the next phase manifest after verifying every prior phase."""
    root = Path(runtime_root)
    if type(phase) is not str or phase not in PHASES:
        raise ValueError("unknown phase")
    if type(binding) is not EvidenceBinding:
        raise ValueError("binding must be EvidenceBinding")
    phase_index = PHASES.index(phase)
    target = _manifest_path(root, phase)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    previous_manifests = verify_phase_manifests(root, binding)
    if len(previous_manifests) != phase_index:
        raise ValueError("phase skip or reordering is not allowed")
    entries = _scan_regular_files(root, target)
    manifest = {
        "binding": binding.serialize(),
        "byte_count": sum(entry["size"] for entry in entries),
        "entries": entries,
        "file_count": len(entries),
        "phase": phase,
        "status": PHASE_STATUS,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tree_hash": _tree_hash(entries),
    }
    write_immutable_json(target, manifest)
    if phase == "60-final":
        verify_phase_manifests(root, binding)
        verify_final_coverage(root, manifest)
    return target
