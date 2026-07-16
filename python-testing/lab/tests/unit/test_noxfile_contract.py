from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import nox

import noxfile


FAST_PYTHONS = ["3.11", "3.12", "3.13", "3.14"]
FAST_SESSIONS = [f"fast-{python}" for python in FAST_PYTHONS]


@dataclass
class RecordingSession:
    posargs: tuple[str, ...] = ()
    calls: list[tuple[str, tuple[str, ...], dict[str, Any]]] = field(
        default_factory=list
    )

    def run_install(self, *args: str, **kwargs: Any) -> None:
        self.calls.append(("run_install", args, kwargs))

    def run(self, *args: str, **kwargs: Any) -> None:
        self.calls.append(("run", args, kwargs))


def _invoke(name: str, *posargs: str) -> RecordingSession:
    session = RecordingSession(posargs=posargs)
    getattr(noxfile, name).func(session)
    return session


def _expected_calls(*run: str) -> list[tuple[str, tuple[str, ...], dict[str, Any]]]:
    return [
        (
            "run_install",
            ("uv", "sync", "--frozen", "--active", "--extra", "dev"),
            {"external": True},
        ),
        ("run", run, {}),
    ]


def test_default_invocation_selects_only_the_four_fast_sessions() -> None:
    assert nox.options.sessions == FAST_SESSIONS


def test_sessions_use_the_exact_interpreter_matrix_and_uv_backend() -> None:
    assert set(nox.registry.get()) == {
        "fast",
        "integration",
        "e2e",
        "coverage",
        "mutation",
    }
    assert noxfile.fast.python == FAST_PYTHONS
    assert noxfile.fast.venv_backend == "uv"

    for name in ("integration", "e2e", "coverage", "mutation"):
        session = getattr(noxfile, name)
        assert session.python == "3.14"
        assert session.venv_backend == "uv"


def test_fast_runtime_uses_frozen_lock_and_forwards_pytest_posargs() -> None:
    session = _invoke("fast", "--junitxml=reports/fast.xml", "--maxfail=1")

    assert session.calls == _expected_calls(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "-q",
        "--junitxml=reports/fast.xml",
        "--maxfail=1",
    )


def test_docker_sessions_use_frozen_lock_and_forward_pytest_posargs() -> None:
    expected_runs = {
        "integration": (
            "pytest",
            "tests/integration",
            "-m",
            "integration and docker",
            "-q",
            "--junitxml=reports/integration.xml",
        ),
        "e2e": (
            "pytest",
            "tests/e2e",
            "-m",
            "e2e and docker",
            "-q",
            "--junitxml=reports/e2e.xml",
        ),
    }

    for name, expected_run in expected_runs.items():
        session = _invoke(name, f"--junitxml=reports/{name}.xml")
        assert session.calls == _expected_calls(*expected_run)


def test_coverage_uses_frozen_lock_and_forwards_pytest_posargs() -> None:
    session = _invoke("coverage", "--cov-report=xml:reports/coverage.xml")

    assert session.calls == _expected_calls(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "--cov=order_service",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=xml:reports/coverage.xml",
    )


def test_mutation_appends_posargs_after_its_default_mutant_selector() -> None:
    session = _invoke("mutation", "--max-children=2")

    assert session.calls == _expected_calls(
        "mutmut",
        "run",
        "order_service.domain.order*",
        "--max-children=2",
    )
