import nox


FAST_PYTHONS = ["3.11", "3.12", "3.13", "3.14"]
FAST_SESSIONS = [f"fast-{python}" for python in FAST_PYTHONS]

nox.options.sessions = FAST_SESSIONS


def install_lab(session: nox.Session) -> None:
    session.run_install(
        "uv",
        "sync",
        "--frozen",
        "--active",
        "--extra",
        "dev",
        external=True,
    )


@nox.session(name="fast", python=FAST_PYTHONS, venv_backend="uv")
def fast(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "-q",
        *session.posargs,
    )


@nox.session(python="3.14", venv_backend="uv")
def integration(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/integration",
        "-m",
        "integration and docker",
        "-q",
        *session.posargs,
    )


@nox.session(python="3.14", venv_backend="uv")
def e2e(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/e2e",
        "-m",
        "e2e and docker",
        "-q",
        *session.posargs,
    )


@nox.session(python="3.14", venv_backend="uv")
def coverage(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "pytest",
        "tests/unit",
        "tests/component",
        "tests/contract",
        "tests/property",
        "--cov=order_service",
        "--cov-branch",
        "--cov-report=term-missing",
        *session.posargs,
    )


@nox.session(python="3.14", venv_backend="uv")
def mutation(session: nox.Session) -> None:
    install_lab(session)
    session.run(
        "mutmut",
        "run",
        "order_service.domain.order*",
        *session.posargs,
    )
