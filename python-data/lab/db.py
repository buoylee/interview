"""Engine factories shared by every demo.

URLs default to the docker-compose Postgres (localhost:5432/datalab,
postgres/postgres). Override via PG_HOST/PG_USER/PG_PASSWORD if you point
the lab at a different cluster.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

_HOST = os.environ.get("PG_HOST", "localhost:5432/datalab")
_USER = os.environ.get("PG_USER", "postgres")
_PWD = os.environ.get("PG_PASSWORD", "postgres")

SYNC_URL = f"postgresql+psycopg://{_USER}:{_PWD}@{_HOST}"
ASYNC_URL = f"postgresql+asyncpg://{_USER}:{_PWD}@{_HOST}"


def make_engine(**kw):
    """Sync engine on psycopg3."""
    return create_engine(SYNC_URL, **kw)


def make_async_engine(**kw):
    """Async engine on asyncpg."""
    return create_async_engine(ASYNC_URL, **kw)
