from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, select

from order_service.core.catalog import (
    inventory_report,
    replenish_inventory,
    upsert_product,
)
from order_service.db.engine import build_engine
from order_service.db.schema import metadata, products, tenants
from order_service.db.settings import DatabaseSettings
from scenarios._evidence import Evidence, write_evidence


def run(engine: Engine) -> Evidence:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    product_id = uuid4()
    second_product_id = uuid4()
    other_product_id = uuid4()
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
        single_product_report = inventory_report(connection, tenant_id=tenant_id)
        upsert_product(
            connection,
            tenant_id=other_tenant_id,
            product_id=other_product_id,
            sku="CORE-1",
            name="Other Tenant Product",
            unit_price=Decimal("99.00"),
            attributes={},
        )
        naive_matches = connection.scalars(
            select(products.c.tenant_id).where(products.c.sku == "CORE-1")
        ).all()
        corrected_matches = connection.scalars(
            select(products.c.tenant_id).where(
                products.c.tenant_id == tenant_id,
                products.c.sku == "CORE-1",
            )
        ).all()
        upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=second_product_id,
            sku="CORE-2",
            name="Companion",
            unit_price=Decimal("5.00"),
            attributes={},
        )
        replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=second_product_id,
            quantity=6,
        )
        report = inventory_report(connection, tenant_id=tenant_id)

    return Evidence(
        title="Chapter 04 — Core DML and Result",
        hypothesis=(
            "executemany sends one statement shape with multiple parameter sets.",
            "ON CONFLICT updates the existing tenant/SKU row and RETURNING exposes its identity.",
        ),
        setup=(
            "Two tenants",
            "One product upserted twice plus one companion product",
            "Inventory replenished to 8 and 6 units",
        ),
        command="uv run python -m scenarios.ch04_core_dml_results",
        observation=(
            f"executemany_tenant_rows={executemany_result.rowcount}",
            f"upsert_preserved_product_id={original.id == updated.id == product_id}",
            f"returned_product_name={updated.name}",
            f"inventory_available={stock.available}",
            f"inventory_version={stock.version}",
            "tenant_stock_value="
            f"{single_product_report[0].tenant_stock_value:.2f}",
            f"tenant_report_rows={len(report)}",
            "tenant_stock_values="
            + ",".join(f"{row.tenant_stock_value:.2f}" for row in report),
            f"naive_unscoped_matches={len(naive_matches)}",
            f"naive_cross_tenant_ambiguous={len(set(naive_matches)) > 1}",
            f"corrected_tenant_matches={len(corrected_matches)}",
            f"corrected_tenant_isolated={corrected_matches == [tenant_id]}",
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
