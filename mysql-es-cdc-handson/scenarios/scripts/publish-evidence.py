#!/usr/bin/env python3
"""Race-safe evidence publication using pinned, no-follow directory handles."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile


UNSAFE_EXIT = 74
UUID4 = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
EVIDENCE_FILES = (
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


class UnsafePublication(RuntimeError):
    pass


def fail(message: str) -> None:
    raise UnsafePublication(message)


def identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


class PinnedDirectory:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            self.fd = os.open(self.path, flags)
        except OSError as exc:
            fail(f"cannot pin directory: {exc.strerror}")
        current = os.fstat(self.fd)
        try:
            named = os.stat(self.path, follow_symlinks=False)
        except OSError as exc:
            os.close(self.fd)
            fail(f"cannot inspect pinned directory: {exc.strerror}")
        if not stat.S_ISDIR(named.st_mode) or identity(current) != identity(named):
            os.close(self.fd)
            fail("pinned directory identity mismatch")
        if os.path.realpath(self.path) != self.path:
            os.close(self.fd)
            fail("pinned directory traverses a symlink")
        self.expected = identity(current)

    def verify(self) -> None:
        try:
            named = os.stat(self.path, follow_symlinks=False)
            current = os.fstat(self.fd)
        except OSError as exc:
            fail(f"pinned directory disappeared: {exc.strerror}")
        if (
            not stat.S_ISDIR(named.st_mode)
            or identity(named) != self.expected
            or identity(current) != self.expected
            or os.path.realpath(self.path) != self.path
        ):
            fail("pinned directory pathname was replaced")

    def close(self) -> None:
        os.close(self.fd)


def open_child_directory(parent: PinnedDirectory, name: str) -> int:
    if not name or name in {".", ".."} or "/" in name:
        fail("unsafe child directory name")
    try:
        return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent.fd)
    except OSError as exc:
        fail(f"cannot open child directory without following links: {exc.strerror}")


def rename_exclusive(source_fd: int, source: str, target_fd: int, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    system = platform.system()
    if system == "Darwin" and hasattr(libc, "renameatx_np"):
        operation = libc.renameatx_np
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        rc = operation(source_fd, os.fsencode(source), target_fd, os.fsencode(target), 0x00000004)
    elif system == "Linux" and hasattr(libc, "renameat2"):
        operation = libc.renameat2
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        rc = operation(source_fd, os.fsencode(source), target_fd, os.fsencode(target), 0x00000001)
    else:
        fail("exclusive directory rename is unavailable")
    if rc != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def controlled_hold(
    stage: str,
    path_variable: str = "M6_RUNNER_PUBLISH_HOLD_DIR",
    stage_variable: str = "M6_RUNNER_PUBLISH_HOLD_STAGE",
) -> None:
    hold_path = os.environ.get(path_variable, "")
    selected_stage = os.environ.get(stage_variable, "")
    hooks_allowed = (
        os.environ.get("M6_RUNNER_INTERNAL_TEST_HOOKS") == "fixture-fail-v1"
        and os.environ.get("M6_RUNNER_EXECUTION_MODE", "fixture") == "fixture"
        and bool(os.environ.get("M6_RUNNER_FIXTURE"))
    )
    if not hooks_allowed or not hold_path or selected_stage != stage:
        return
    # The hook is test coordination only; normalize macOS's /var -> /private/var
    # alias before applying the same pinned-directory checks.
    hold = PinnedDirectory(os.path.realpath(hold_path))
    ready = f"{stage}.ready"
    release = f"{stage}.release"
    try:
        descriptor = os.open(ready, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=hold.fd)
        os.close(descriptor)
        while not entry_exists(hold.fd, release):
            hold.verify()
        hold.verify()
    finally:
        hold.close()


def file_digest(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def open_version(root: PinnedDirectory, scenario: str, token: str, canonical: bool) -> int:
    if not scenario or scenario in {".", ".."} or "/" in scenario or not UUID4.fullmatch(token):
        fail("unsafe evidence gate identity")
    expected = f".runs/{scenario}/{token}"
    if canonical:
        try:
            if os.readlink(scenario, dir_fd=root.fd) != expected:
                fail("canonical evidence target changed")
        except OSError as exc:
            fail(f"canonical evidence is not a readable symlink: {exc.strerror}")
    runs_fd = scenario_fd = -1
    try:
        runs_fd = os.open(".runs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root.fd)
        scenario_fd = os.open(scenario, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=runs_fd)
        return os.open(token, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=scenario_fd)
    except OSError as exc:
        fail(f"evidence gate target is not physical: {exc.strerror}")
    finally:
        if scenario_fd >= 0:
            os.close(scenario_fd)
        if runs_fd >= 0:
            os.close(runs_fd)


def pin_evidence_files(version_fd: int) -> dict[str, tuple[int, tuple[int, int], int, str]]:
    try:
        names = os.listdir(version_fd)
    except OSError as exc:
        fail(f"cannot list pinned evidence target: {exc.strerror}")
    if sorted(names) != sorted(EVIDENCE_FILES):
        fail("pinned evidence target does not contain exactly the locked files")
    pinned: dict[str, tuple[int, tuple[int, int], int, str]] = {}
    try:
        for name in EVIDENCE_FILES:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=version_fd)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                os.close(descriptor)
                fail("pinned evidence entry is not a regular file")
            pinned[name] = (descriptor, identity(metadata), metadata.st_size, file_digest(descriptor))
    except (OSError, UnsafePublication) as exc:
        for descriptor, _, _, _ in pinned.values():
            os.close(descriptor)
        if isinstance(exc, UnsafePublication):
            raise
        fail(f"cannot pin evidence file: {exc.strerror}")
    return pinned


def verify_pinned_target(
    root: PinnedDirectory,
    scenario: str,
    token: str,
    canonical: bool,
    expected_directory: tuple[int, int],
    pinned: dict[str, tuple[int, tuple[int, int], int, str]],
) -> None:
    root.verify()
    current_fd = open_version(root, scenario, token, canonical)
    try:
        if identity(os.fstat(current_fd)) != expected_directory:
            fail("evidence gate target directory identity changed")
        if sorted(os.listdir(current_fd)) != sorted(EVIDENCE_FILES):
            fail("evidence gate target entries changed")
        for name in EVIDENCE_FILES:
            pinned_fd, expected_identity, expected_size, expected_digest = pinned[name]
            pinned_metadata = os.fstat(pinned_fd)
            named_metadata = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
            if (
                identity(pinned_metadata) != expected_identity
                or pinned_metadata.st_size != expected_size
                or not stat.S_ISREG(named_metadata.st_mode)
                or identity(named_metadata) != expected_identity
                or named_metadata.st_size != expected_size
                or file_digest(pinned_fd) != expected_digest
            ):
                fail("evidence gate file identity or content changed")
            current_file = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
            try:
                current_metadata = os.fstat(current_file)
                if (
                    identity(current_metadata) != expected_identity
                    or current_metadata.st_size != expected_size
                    or file_digest(current_file) != expected_digest
                ):
                    fail("evidence gate reopened file changed")
            finally:
                os.close(current_file)
    except OSError as exc:
        fail(f"cannot verify pinned evidence target: {exc.strerror}")
    finally:
        os.close(current_fd)
    root.verify()


def copy_pinned_snapshot(
    snapshot: str, pinned: dict[str, tuple[int, tuple[int, int], int, str]]
) -> None:
    for name in EVIDENCE_FILES:
        descriptor, _, expected_size, expected_digest = pinned[name]
        destination = os.path.join(snapshot, name)
        digest = hashlib.sha256()
        written = 0
        os.lseek(descriptor, 0, os.SEEK_SET)
        with open(destination, "xb") as output:
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                written += len(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if written != expected_size or digest.hexdigest() != expected_digest:
            fail("pinned evidence changed while creating gate snapshot")


def run_gate(command: list[str], label: str) -> None:
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except OSError as exc:
        fail(f"cannot execute {label} gate: {exc.strerror}")
    if result.returncode != 0:
        fail(f"{label} gate rejected pinned evidence")


def gate_evidence(
    root_path: str,
    scenario: str,
    token: str,
    canonical: bool,
    evidence_contract: str,
    secret_contract: str,
) -> None:
    root = PinnedDirectory(root_path)
    version_fd = -1
    pinned: dict[str, tuple[int, tuple[int, int], int, str]] = {}
    try:
        version_fd = open_version(root, scenario, token, canonical)
        expected_directory = identity(os.fstat(version_fd))
        pinned = pin_evidence_files(version_fd)
        verify_pinned_target(root, scenario, token, canonical, expected_directory, pinned)
        with tempfile.TemporaryDirectory(prefix="m6-evidence-gate-") as snapshot:
            copy_pinned_snapshot(snapshot, pinned)
            verify_pinned_target(root, scenario, token, canonical, expected_directory, pinned)
            run_gate(["bash", evidence_contract, snapshot], "schema")
            verify_pinned_target(root, scenario, token, canonical, expected_directory, pinned)
            controlled_hold(
                "canonical-between-gates",
                "M6_RUNNER_GATE_HOLD_DIR",
                "M6_RUNNER_GATE_HOLD_STAGE",
            ) if canonical else None
            verify_pinned_target(root, scenario, token, canonical, expected_directory, pinned)
            run_gate(
                ["bash", secret_contract, *[os.path.join(snapshot, name) for name in EVIDENCE_FILES]],
                "secret",
            )
            verify_pinned_target(root, scenario, token, canonical, expected_directory, pinned)
    finally:
        for descriptor, _, _, _ in pinned.values():
            os.close(descriptor)
        if version_fd >= 0:
            os.close(version_fd)
        root.close()


def ensure_contained(root: PinnedDirectory, child: PinnedDirectory) -> None:
    prefix = root.path + os.sep
    if not child.path.startswith(prefix):
        fail("publication directory escapes evidence root")


def publish_version(root_path: str, bundle_path: str, runs_path: str, token: str) -> None:
    if not UUID4.fullmatch(token):
        fail("unsafe evidence version identity")
    root = PinnedDirectory(root_path)
    source_parent = PinnedDirectory(os.path.dirname(bundle_path))
    runs = PinnedDirectory(runs_path)
    source_name = os.path.basename(bundle_path)
    source_fd = open_child_directory(source_parent, source_name)
    source_identity = identity(os.fstat(source_fd))
    staging = f".incoming.{token}"
    staged = False
    published = False
    try:
        ensure_contained(root, source_parent)
        ensure_contained(root, runs)
        root.verify()
        source_parent.verify()
        runs.verify()
        controlled_hold("parent-opened")
        root.verify()
        source_parent.verify()
        runs.verify()
        rename_exclusive(source_parent.fd, source_name, runs.fd, staging)
        staged = True
        root.verify()
        source_parent.verify()
        runs.verify()
        controlled_hold("version-staged")
        root.verify()
        source_parent.verify()
        runs.verify()
        rename_exclusive(runs.fd, staging, runs.fd, token)
        staged = False
        published = True
        root.verify()
        runs.verify()
        version_fd = open_child_directory(runs, token)
        try:
            if identity(os.fstat(version_fd)) != source_identity:
                fail("published version identity changed")
        finally:
            os.close(version_fd)
    except (OSError, UnsafePublication) as exc:
        rollback_name = token if published else staging if staged else None
        if rollback_name is not None:
            try:
                rename_exclusive(runs.fd, rollback_name, source_parent.fd, source_name)
            except OSError:
                pass
        if isinstance(exc, UnsafePublication):
            raise
        fail(f"exclusive evidence version publication failed: {exc.strerror}")
    finally:
        os.close(source_fd)
        runs.close()
        source_parent.close()
        root.close()


def canonical_target(root: PinnedDirectory, scenario: str) -> tuple[str, str, int]:
    try:
        value = os.readlink(scenario, dir_fd=root.fd)
    except OSError as exc:
        fail(f"canonical evidence is not a readable symlink: {exc.strerror}")
    prefix = f".runs/{scenario}/"
    if not value.startswith(prefix):
        fail("canonical evidence target escapes scenario versions")
    token = value[len(prefix) :]
    if not UUID4.fullmatch(token):
        fail("canonical evidence target has unsafe identity")
    runs_fd = open_child_directory(root, ".runs")
    scenario_fd = -1
    version_fd = -1
    try:
        scenario_fd = os.open(scenario, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=runs_fd)
        version_fd = os.open(token, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=scenario_fd)
    except OSError as exc:
        if version_fd >= 0:
            os.close(version_fd)
        if scenario_fd >= 0:
            os.close(scenario_fd)
        os.close(runs_fd)
        fail(f"canonical evidence target is not physical: {exc.strerror}")
    os.close(scenario_fd)
    os.close(runs_fd)
    return value, token, version_fd


def publish_canonical(root_path: str, scenario: str, token: str) -> str:
    if not UUID4.fullmatch(token) or not scenario or "/" in scenario or scenario in {".", ".."}:
        fail("unsafe canonical publication identity")
    root = PinnedDirectory(root_path)
    expected = f".runs/{scenario}/{token}"
    temporary = f".link.{scenario}.{token}"
    created = False
    published = False
    try:
        root.verify()
        if entry_exists(root.fd, scenario):
            _, _, version_fd = canonical_target(root, scenario)
            os.close(version_fd)
            root.verify()
            return "unchanged"
        if entry_exists(root.fd, temporary):
            fail("canonical staging name already exists")
        os.symlink(expected, temporary, dir_fd=root.fd)
        created = True
        root.verify()
        controlled_hold("canonical-staged")
        root.verify()
        rename_exclusive(root.fd, temporary, root.fd, scenario)
        created = False
        published = True
        root.verify()
        value, actual_token, version_fd = canonical_target(root, scenario)
        os.close(version_fd)
        if value != expected or actual_token != token:
            fail("canonical evidence target changed")
        return "published"
    except (OSError, UnsafePublication) as exc:
        if created:
            try:
                os.unlink(temporary, dir_fd=root.fd)
            except OSError:
                pass
        if published:
            try:
                if os.readlink(scenario, dir_fd=root.fd) == expected:
                    os.unlink(scenario, dir_fd=root.fd)
            except OSError:
                pass
        if isinstance(exc, UnsafePublication):
            raise
        fail(f"exclusive canonical publication failed: {exc.strerror}")
    finally:
        root.close()


def verify_canonical(root_path: str, scenario: str) -> str:
    root = PinnedDirectory(root_path)
    try:
        root.verify()
        _, token, version_fd = canonical_target(root, scenario)
        os.close(version_fd)
        root.verify()
        return os.path.join(root.path, ".runs", scenario, token)
    finally:
        root.close()


def remove_canonical(root_path: str, scenario: str, token: str) -> None:
    root = PinnedDirectory(root_path)
    expected = f".runs/{scenario}/{token}"
    try:
        root.verify()
        if os.readlink(scenario, dir_fd=root.fd) != expected:
            fail("refusing to remove a different canonical target")
        os.unlink(scenario, dir_fd=root.fd)
        root.verify()
    finally:
        root.close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version")
    version.add_argument("root")
    version.add_argument("bundle")
    version.add_argument("runs")
    version.add_argument("token")
    canonical = commands.add_parser("canonical")
    canonical.add_argument("root")
    canonical.add_argument("scenario")
    canonical.add_argument("token")
    verify = commands.add_parser("verify")
    verify.add_argument("root")
    verify.add_argument("scenario")
    gate = commands.add_parser("gate")
    gate.add_argument("root")
    gate.add_argument("scenario")
    gate.add_argument("token")
    gate.add_argument("mode", choices=("version", "canonical"))
    gate.add_argument("evidence_contract")
    gate.add_argument("secret_contract")
    remove = commands.add_parser("remove")
    remove.add_argument("root")
    remove.add_argument("scenario")
    remove.add_argument("token")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "version":
            publish_version(args.root, args.bundle, args.runs, args.token)
        elif args.command == "canonical":
            print(publish_canonical(args.root, args.scenario, args.token))
        elif args.command == "verify":
            print(verify_canonical(args.root, args.scenario))
        elif args.command == "gate":
            gate_evidence(
                args.root,
                args.scenario,
                args.token,
                args.mode == "canonical",
                args.evidence_contract,
                args.secret_contract,
            )
        else:
            remove_canonical(args.root, args.scenario, args.token)
        return 0
    except UnsafePublication as exc:
        print(f"unsafe evidence publication: {exc}", file=sys.stderr)
        return UNSAFE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
