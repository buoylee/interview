from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import Engine, inspect

from order_service.db.engine import build_engine
from order_service.db.schema import metadata
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    unique_names = sorted(
        constraint["name"]
        for constraint in inspector.get_unique_constraints("products")
        if constraint["name"] is not None
    )
    product_attributes_type = next(
        column["type"].__class__.__name__
        for column in inspector.get_columns("products")
        if column["name"] == "attributes"
    )
    outbox_indexes = inspector.get_indexes("outbox_events")
    index_names = sorted(
        index["name"]
        for index in outbox_indexes
        if index["name"] is not None
    )
    claimable_index = next(
        index for index in outbox_indexes if index["name"] == "ix_outbox_events_claimable"
    )
    claimable_predicate = claimable_index["dialect_options"]["postgresql_where"]
    return Evidence(
        title="第 02 章 — Schema 與型別系統",
        hypothesis=(
            "MetaData 命名慣例會產生可預測的 PostgreSQL constraint 名稱。",
            "PostgreSQL Dialect reflection 會保留 JSONB 型別與 partial index predicate。",
        ),
        setup=(
            "資料庫版本為 PostgreSQL 18.4。",
            "M1 Lab 以 SQLAlchemy MetaData.create_all() 建立 schema。",
        ),
        observation=(
            f"table_count={len(table_names)}",
            f"tables={','.join(table_names)}",
            f"product_unique_constraints={','.join(unique_names)}",
            f"outbox_indexes={','.join(index_names)}",
            f"product_attributes_type={product_attributes_type}",
            f"outbox_claimable_predicate={claimable_predicate}",
        ),
        explanation=(
            "具名 constraint 是 migration 與 IntegrityError translation 的穩定識別依據。",
            "TypeDecorator.cache_ok=True 讓 Money 型別可安全參與 statement cache。",
        ),
        decision=(
            "所有與業務相關的 constraint 都要命名。金額則以 Decimal-backed numeric 儲存。",
        ),
        caveat=(
            "create_all() 只用於 Lab bootstrap。production schema evolution 由 M3 的 "
            "Alembic 負責。",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("evidence/ch02-schema-types.md"))
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
