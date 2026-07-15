import pytest
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration


def test_engine_connects_to_the_expected_postgresql(engine: Engine) -> None:
    with engine.connect() as connection:
        database, version_num = connection.execute(
            text("SELECT current_database(), current_setting('server_version_num')")
        ).one()

    assert database == "sqlalchemy_handson"
    assert int(version_num) // 10_000 == 18
