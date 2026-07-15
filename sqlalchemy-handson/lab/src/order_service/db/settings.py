from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Self

from sqlalchemy import URL, make_url

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://sqlalchemy:sqlalchemy@localhost:55432/sqlalchemy_handson"
)


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: URL

    @classmethod
    def from_env(cls) -> Self:
        raw_url = os.environ.get("SQLALCHEMY_DATABASE_URL", DEFAULT_DATABASE_URL)
        return cls(url=make_url(raw_url))

    @property
    def safe_url(self) -> str:
        return self.url.render_as_string(hide_password=True)
