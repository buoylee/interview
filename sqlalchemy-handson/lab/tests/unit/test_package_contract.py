from pathlib import Path

import sqlalchemy

import order_service


def test_package_and_sqlalchemy_versions_are_pinned() -> None:
    assert order_service.__version__ == "0.1.0"
    assert sqlalchemy.__version__ == "2.0.51"


def test_lower_layers_never_commit_their_callers_transaction() -> None:
    package_root = Path(__file__).parents[2] / "src" / "order_service"
    offenders = [
        path.relative_to(package_root).as_posix()
        for path in package_root.rglob("*.py")
        if ".commit(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
