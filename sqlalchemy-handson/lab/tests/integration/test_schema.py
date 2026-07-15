from decimal import Decimal
from uuid import uuid4

import pytest
from psycopg.errors import ForeignKeyViolation
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from order_service.db.schema import (
    inventories,
    inventory_reservations,
    metadata,
    order_lines,
    orders,
    products,
    tenants,
)
from scenarios.ch02_schema_types import run

pytestmark = pytest.mark.integration


def test_metadata_round_trips_through_postgresql(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == set(metadata.tables)
    product_types = {
        column["name"]: column["type"].__class__.__name__
        for column in inspector.get_columns("products")
    }
    assert product_types["attributes"] == "JSONB"


def test_schema_scenario_records_reflected_contract(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "table_count=8" in observations
    assert "uq_products_tenant_id_sku" in observations
    assert "ix_outbox_events_claimable" in observations
    assert "product_attributes_type=JSONB" in observations
    assert "outbox_claimable_predicate=((status)::text = 'pending'::text)" in observations
    assert "naive_cross_tenant_rejected=True" in observations
    assert "corrected_tenant_scoped_reference=True" in observations


def test_composite_foreign_keys_reject_cross_tenant_references(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    product_id = uuid4()
    other_product_id = uuid4()
    order_id = uuid4()
    other_order_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            tenants.insert(),
            [
                {"id": tenant_id, "name": "Tenant A"},
                {"id": other_tenant_id, "name": "Tenant B"},
            ],
        )
        connection.execute(
            products.insert(),
            [
                {
                    "id": product_id,
                    "tenant_id": tenant_id,
                    "sku": "A-1",
                    "name": "Product A",
                    "unit_price": Decimal("10.00"),
                    "attributes": {},
                },
                {
                    "id": other_product_id,
                    "tenant_id": other_tenant_id,
                    "sku": "B-1",
                    "name": "Product B",
                    "unit_price": Decimal("20.00"),
                    "attributes": {},
                },
            ],
        )
        connection.execute(
            orders.insert(),
            [
                {
                    "id": order_id,
                    "tenant_id": tenant_id,
                    "status": "pending",
                    "total": Decimal("10.00"),
                    "idempotency_key": "order-a",
                },
                {
                    "id": other_order_id,
                    "tenant_id": other_tenant_id,
                    "status": "pending",
                    "total": Decimal("20.00"),
                    "idempotency_key": "order-b",
                },
            ],
        )

    invalid_inserts = (
        (
            inventories.insert().values(
                tenant_id=tenant_id,
                product_id=other_product_id,
                available=1,
                reserved=0,
                version=1,
            ),
            "fk_inventories_tenant_id_product_id_products",
        ),
        (
            order_lines.insert().values(
                tenant_id=tenant_id,
                order_id=other_order_id,
                line_number=1,
                product_id=product_id,
                quantity=1,
                unit_price=Decimal("10.00"),
            ),
            "fk_order_lines_tenant_id_order_id_orders",
        ),
        (
            inventory_reservations.insert().values(
                id=uuid4(),
                tenant_id=tenant_id,
                order_id=order_id,
                product_id=other_product_id,
                quantity=1,
                status="held",
            ),
            "fk_inventory_reservations_tenant_id_product_id_products",
        ),
    )
    for statement, expected_constraint in invalid_inserts:
        with engine.connect() as connection:
            with pytest.raises(IntegrityError) as raised:
                connection.execute(statement)
            assert isinstance(raised.value.orig, ForeignKeyViolation)
            assert raised.value.orig.diag.constraint_name == expected_constraint
            connection.rollback()
            assert connection.scalar(text("SELECT 1")) == 1
            connection.rollback()
