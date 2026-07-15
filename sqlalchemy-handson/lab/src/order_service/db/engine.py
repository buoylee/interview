from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, create_engine

from order_service.db.settings import DatabaseSettings


def build_engine(settings: DatabaseSettings, **overrides: Any) -> Engine:
    options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 1.0,
        "pool_recycle": 1_800,
    }
    options.update(overrides)
    return create_engine(settings.url, **options)
