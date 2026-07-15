from collections.abc import Iterator

import pytest
from sqlalchemy import Engine

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    value = build_engine(DatabaseSettings.from_env())
    try:
        yield value
    finally:
        value.dispose()
