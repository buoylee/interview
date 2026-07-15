from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    with PostgresContainer("postgres:16-alpine", driver=None) as postgres:
        yield postgres.get_connection_url().replace(
            "postgresql://", "postgresql+psycopg://", 1
        )


@pytest.fixture(scope="session")
def alembic_config(postgres_url: str) -> Config:
    root = Path(__file__).parents[2]
    config = Config(root / "alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def async_engine(alembic_config: Config, postgres_url: str) -> AsyncIterator[AsyncEngine]:
    command.upgrade(alembic_config, "head")
    engine = create_async_engine(postgres_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def session_factory(async_engine: AsyncEngine):
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def clean_database(async_engine: AsyncEngine) -> AsyncIterator[None]:
    original_error: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        original_error = exc
        raise
    finally:
        try:
            async with async_engine.begin() as connection:
                await connection.execute(
                    text(
                        """DO $$
                        BEGIN
                            IF to_regclass('public.orders') IS NOT NULL
                               AND to_regclass('public.outbox_messages') IS NOT NULL THEN
                                TRUNCATE TABLE outbox_messages, orders CASCADE;
                            END IF;
                        END $$"""
                    )
                )
        except BaseException:
            if original_error is None:
                raise
