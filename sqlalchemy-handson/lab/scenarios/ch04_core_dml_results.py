from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine

from order_service.core.catalog import (
    inventory_report,
    replenish_inventory,
    upsert_product,
)
from order_service.db.engine import build_engine
from order_service.db.schema import metadata, tenants
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    product_id = uuid4()
    with engine.begin() as connection:
        metadata.drop_all(connection)
        metadata.create_all(connection)
        executemany_result = connection.execute(
            tenants.insert().execution_options(preserve_rowcount=True),
            [
                {"id": tenant_id, "name": "Core Tenant"},
                {"id": other_tenant_id, "name": "Other Tenant"},
            ],
        )
        original = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            sku="CORE-1",
            name="Original",
            unit_price=Decimal("10.00"),
            attributes={"color": "black"},
        )
        updated = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=uuid4(),
            sku="CORE-1",
            name="Updated",
            unit_price=Decimal("12.50"),
            attributes={"color": "blue"},
        )
        replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=3,
        )
        stock = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=5,
        )
        report = inventory_report(connection, tenant_id=tenant_id)

    return Evidence(
        title="Chapter 04 — Core DML and Result",
        hypothesis=(
            "executemany sends one statement shape with multiple parameter sets.",
            "ON CONFLICT updates the existing tenant/SKU row and RETURNING exposes its identity.",
        ),
        setup=("Two tenants", "One product upserted twice", "Inventory replenished 3 + 5"),
        observation=(
            f"executemany_tenant_rows={executemany_result.rowcount}",
            f"upsert_preserved_product_id={original.id == updated.id == product_id}",
            f"returned_product_name={updated.name}",
            f"inventory_available={stock.available}",
            f"inventory_version={stock.version}",
            f"tenant_stock_value={report[0].tenant_stock_value:.2f}",
        ),
        explanation=(
            "PostgreSQL RETURNING removes a follow-up lookup for server-visible results.",
            "Result.mappings() makes the selected row shape explicit before conversion "
            "to a record type.",
        ),
        decision=(
            "Use Core for explicit set-oriented DML and reports whose SQL shape is the "
            "primary abstraction.",
        ),
        caveat=(
            "ON CONFLICT and JSONB are PostgreSQL dialect capabilities; portability "
            "requires a deliberate fallback.",
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/ch04-core-dml-results.md"),
    )
    args = parser.parse_args()
    engine = build_engine(DatabaseSettings.from_env())
    try:
        write_evidence(args.evidence, run(engine))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
