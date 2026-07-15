import sqlalchemy

import order_service


def test_package_and_sqlalchemy_versions_are_pinned() -> None:
    assert order_service.__version__ == "0.1.0"
    assert sqlalchemy.__version__ == "2.0.51"
