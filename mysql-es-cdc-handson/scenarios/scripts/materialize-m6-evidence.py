#!/usr/bin/env python3
"""Materialize validated runtime M6 bundles as ordinary canonical directories."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path


FILES = (
    "differences.json",
    "es-snapshot.json",
    "fault.json",
    "input-commands.json",
    "kafka-offsets.json",
    "manifest.json",
    "mysql-snapshot.json",
    "recovery-actions.json",
    "result.json",
)
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def fail(message: str) -> None:
    raise SystemExit(f"unsafe M6 materialization: {message}")


def physical_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        fail(f"{label} is not a physical directory: {path}")
    # Normalize the macOS /var -> /private/var system alias once, then perform
    # every containment and replacement check against the physical pathname.
    return Path(os.path.realpath(path))


def source_bundle(runtime: Path, scenario: str) -> Path:
    link = runtime / scenario
    if not link.is_symlink():
        fail(f"runtime canonical is not a symlink: {scenario}")
    target = os.readlink(link)
    prefix = f".runs/{scenario}/"
    if not target.startswith(prefix) or not UUID4.fullmatch(target[len(prefix) :]):
        fail(f"runtime canonical target is not a locked run: {scenario}")
    bundle = (runtime / target).resolve(strict=True)
    expected_parent = (runtime / ".runs" / scenario).resolve(strict=True)
    if bundle.parent != expected_parent or bundle.is_symlink() or not bundle.is_dir():
        fail(f"runtime bundle escapes its scenario: {scenario}")
    names = sorted(entry.name for entry in bundle.iterdir())
    if names != sorted(FILES):
        fail(f"runtime bundle does not contain exactly nine JSON files: {scenario}")
    for name in FILES:
        metadata = (bundle / name).lstat()
        if not stat.S_ISREG(metadata.st_mode):
            fail(f"runtime evidence is not a regular file: {scenario}/{name}")
    return bundle


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read JSON {path}: {exc}")


def install_directory(staged: Path, destination: Path, scratch: Path) -> None:
    backup = scratch / f"previous-{destination.name}"
    had_previous = destination.exists() or destination.is_symlink()
    if had_previous:
        if destination.is_symlink():
            destination.unlink()
        elif destination.is_dir():
            os.replace(destination, backup)
        else:
            fail(f"canonical destination has unsafe type: {destination}")
    try:
        os.replace(staged, destination)
    except BaseException:
        if backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def main() -> int:
    if len(sys.argv) != 4:
        fail("usage: materialize-m6-evidence.py RUNTIME_ROOT CANONICAL_ROOT CATALOG")
    runtime = physical_directory(Path(sys.argv[1]), "runtime root")
    canonical = physical_directory(Path(sys.argv[2]), "canonical root")
    catalog = load_json(Path(sys.argv[3]))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("scenarios"), list):
        fail("catalog has no scenario list")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    with tempfile.TemporaryDirectory(prefix=".materialize.", dir=canonical) as scratch_name:
        scratch = Path(scratch_name)
        staged_root = scratch / "staged"
        staged_root.mkdir()
        for row in catalog["scenarios"]:
            if not isinstance(row, dict):
                fail("catalog scenario is not an object")
            scenario = row.get("scenario_id")
            design_case = row.get("design_case")
            if not isinstance(scenario, str) or "/" in scenario or scenario in {"", ".", ".."}:
                fail("catalog scenario identity is unsafe")
            if scenario in seen or not isinstance(design_case, int):
                fail(f"catalog scenario is duplicated or unnumbered: {scenario}")
            seen.add(scenario)
            source = source_bundle(runtime, scenario)
            result = load_json(source / "result.json")
            if not isinstance(result, dict) or result.get("scenario_id") != scenario or result.get("result") != "PASS":
                fail(f"runtime result is not a matching PASS: {scenario}")
            staged = staged_root / scenario
            staged.mkdir()
            for name in FILES:
                shutil.copyfile(source / name, staged / name, follow_symlinks=False)
            rows.append({"design_case": design_case, "scenario_id": scenario, "result": "PASS"})
        for row in rows:
            scenario = str(row["scenario_id"])
            install_directory(staged_root / scenario, canonical / scenario, scratch)
        index = {
            "schema_version": 1,
            "scenario_count": len(rows),
            "pass_count": len(rows),
            "fail_count": 0,
            "scenarios": rows,
        }
        index_tmp = scratch / "index.json"
        index_tmp.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(index_tmp, canonical / "index.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
