#!/usr/bin/env python3
import argparse
import difflib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures"
ANSWER_KEY_ROOT = ROOT / "answer-key"

FIXTURES = (
    "01-data-consistency",
    "02-idempotency",
    "03-timeout-retry-fallback",
    "04-interface-coupling",
    "05-error-handling",
    "06-misleading-tests",
)

FAILURE_MARKERS = {
    "01-data-consistency": "CONS-001",
    "02-idempotency": "IDEM-001",
    "03-timeout-retry-fallback": "RES-001",
    "04-interface-coupling": "ARCH-001",
    "05-error-handling": "ERR-001",
    "06-misleading-tests": "TEST-001",
}

REQUIRED_FIXTURE_FILES = (
    "spec.md",
    "project-overlay.md",
    "before.py",
    "buggy.py",
    "fixed.py",
    "project_test.py",
    "verification_test.py",
)

REQUIRED_ANSWER_HEADINGS = (
    "## Defect ID",
    "## Expected lens",
    "## Expected severity",
    "## Evidence",
    "## Why project_test misses it",
    "## Fixed evidence",
    "## Scope boundary",
)


def render_diff(fixture_dir):
    before = (fixture_dir / "before.py").read_text(encoding="utf-8")
    buggy = (fixture_dir / "buggy.py").read_text(encoding="utf-8")
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            buggy.splitlines(keepends=True),
            fromfile="a/implementation.py",
            tofile="b/implementation.py",
            n=0,
        )
    )


def run_suite(fixture_dir, variant, suite):
    environment = os.environ.copy()
    environment["FIXTURE_VARIANT"] = variant
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "unittest", "-q", suite],
        cwd=fixture_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def combined_output(result):
    return f"{result.stdout}\n{result.stderr}"


def validate_fixture(slug, write_diffs):
    fixture_dir = FIXTURE_ROOT / slug
    errors = []

    missing = [
        name for name in REQUIRED_FIXTURE_FILES
        if not (fixture_dir / name).is_file()
    ]
    if missing:
        return [f"missing fixture files: {', '.join(missing)}"]

    expected_diff = render_diff(fixture_dir)
    diff_path = fixture_dir / "change.diff"
    if not expected_diff:
        errors.append("before.py and buggy.py produced an empty review diff")
    if write_diffs:
        diff_path.write_text(expected_diff, encoding="utf-8")
    elif not diff_path.is_file():
        errors.append("missing change.diff")
    elif diff_path.read_text(encoding="utf-8") != expected_diff:
        errors.append("change.diff is stale")

    answer_key = ANSWER_KEY_ROOT / f"{slug}.md"
    if not answer_key.is_file():
        errors.append("missing answer key")
    else:
        answer_text = answer_key.read_text(encoding="utf-8")
        for heading in REQUIRED_ANSWER_HEADINGS:
            if heading not in answer_text:
                errors.append(f"answer key missing heading: {heading}")

    buggy_project = run_suite(fixture_dir, "buggy", "project_test.py")
    if buggy_project.returncode != 0:
        errors.append(
            "buggy project test must pass:\n" + combined_output(buggy_project)
        )

    buggy_verification = run_suite(
        fixture_dir,
        "buggy",
        "verification_test.py",
    )
    marker = FAILURE_MARKERS[slug]
    if buggy_verification.returncode == 0:
        errors.append("buggy verification unexpectedly passed")
    elif marker not in combined_output(buggy_verification):
        errors.append(
            f"buggy verification failed without expected marker {marker}:\n"
            + combined_output(buggy_verification)
        )

    for suite in ("project_test.py", "verification_test.py"):
        fixed_result = run_suite(fixture_dir, "fixed", suite)
        if fixed_result.returncode != 0:
            errors.append(
                f"fixed {suite} failed:\n" + combined_output(fixed_result)
            )

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify deterministic AI Code Review fixtures."
    )
    parser.add_argument(
        "--write-diffs",
        action="store_true",
        help="regenerate deterministic before-to-buggy change.diff files",
    )
    arguments = parser.parse_args(argv)

    failed = False
    for slug in FIXTURES:
        errors = validate_fixture(slug, arguments.write_diffs)
        if errors:
            failed = True
            print(f"[FAIL] {slug}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[PASS] {slug}")

    if failed:
        return 1

    print(f"All {len(FIXTURES)} fixtures are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
