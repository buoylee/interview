from __future__ import annotations

import platform
import sys
from pathlib import Path

import psycopg
import sqlalchemy
from sqlalchemy import text

from order_service.db.engine import build_engine
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def main() -> None:
    settings = DatabaseSettings.from_env()
    engine = build_engine(settings)
    try:
        with engine.connect() as connection:
            postgres_version = connection.scalar(text("SHOW server_version"))
        evidence = Evidence(
            title="M1 environment manifest",
            hypothesis=(
                "The committed evidence identifies every behavior-affecting runtime version.",
            ),
            setup=(f"database_url={settings.safe_url}",),
            command="uv run python -m scenarios.environment",
            observation=(
                f"python={platform.python_version()}",
                f"implementation={sys.implementation.name}",
                f"sqlalchemy={sqlalchemy.__version__}",
                f"psycopg={psycopg.__version__}",
                f"postgresql={postgres_version}",
                f"platform={platform.machine()}-{platform.system()}",
            ),
            explanation=(
                "Version and platform context separate reproducible behavior from "
                "host-specific timing.",
            ),
            decision=(
                "Regenerate this manifest whenever the lockfile or database image changes.",
            ),
            caveat=(
                "The rendered database URL hides the password and contains no production secret.",
            ),
        )
        write_evidence(Path("evidence/environment.md"), evidence)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
