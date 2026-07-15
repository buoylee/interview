from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select

from order_service.core.catalog import (
    InventoryRecord,
    ProductRecord,
    create_tenant,
    inventory_report,
    replenish_inventory,
    upsert_product,
)
from order_service.db.schema import inventories, products, tenants
from scenarios.ch04_core_dml_results import run

pytestmark = pytest.mark.integration


def test_product_upsert_returns_existing_identity_and_updated_values(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    original_id = uuid4()
    with engine.begin() as connection:
        create_tenant(connection, tenant_id=tenant_id, name="Core Tenant")
        first = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=original_id,
            sku="CORE-1",
            name="Original",
            unit_price=Decimal("10.00"),
            attributes={"color": "black"},
        )
        second = upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=uuid4(),
            sku="CORE-1",
            name="Updated",
            unit_price=Decimal("12.50"),
            attributes={"color": "blue"},
        )

    assert isinstance(first, ProductRecord)
    assert first.id == original_id
    assert second.id == original_id
    assert second.name == "Updated"
    assert second.unit_price == Decimal("12.50")
    assert second.attributes == {"color": "blue"}
    with pytest.raises(FrozenInstanceError):
        second.name = "Mutable"  # type: ignore[misc]


def test_product_upsert_conflict_key_is_scoped_by_tenant(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    first_tenant_id = uuid4()
    second_tenant_id = uuid4()
    first_product_id = uuid4()
    second_product_id = uuid4()
    with engine.begin() as connection:
        create_tenant(connection, tenant_id=first_tenant_id, name="First Tenant")
        create_tenant(connection, tenant_id=second_tenant_id, name="Second Tenant")
        first = upsert_product(
            connection,
            tenant_id=first_tenant_id,
            product_id=first_product_id,
            sku="SHARED-SKU",
            name="First Product",
            unit_price=Decimal("10.00"),
            attributes={},
        )
        second = upsert_product(
            connection,
            tenant_id=second_tenant_id,
            product_id=second_product_id,
            sku="SHARED-SKU",
            name="Second Product",
            unit_price=Decimal("20.00"),
            attributes={},
        )

    assert first.id == first_product_id
    assert second.id == second_product_id
    assert first.tenant_id == first_tenant_id
    assert second.tenant_id == second_tenant_id


def test_inventory_upsert_and_report_are_tenant_scoped(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    product_id = uuid4()
    second_product_id = uuid4()
    other_product_id = uuid4()
    with engine.begin() as connection:
        create_tenant(connection, tenant_id=tenant_id, name="Stock Tenant")
        create_tenant(connection, tenant_id=other_tenant_id, name="Other Tenant")
        upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            sku="STOCK-1",
            name="Stock Product",
            unit_price=Decimal("5.00"),
            attributes={},
        )
        upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=second_product_id,
            sku="STOCK-2",
            name="Second Stock Product",
            unit_price=Decimal("7.50"),
            attributes={},
        )
        upsert_product(
            connection,
            tenant_id=other_tenant_id,
            product_id=other_product_id,
            sku="STOCK-1",
            name="Other Product",
            unit_price=Decimal("100.00"),
            attributes={},
        )
        first = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=3,
        )
        second = replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=5,
        )
        replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=second_product_id,
            quantity=2,
        )
        replenish_inventory(
            connection,
            tenant_id=other_tenant_id,
            product_id=other_product_id,
            quantity=7,
        )
        report = inventory_report(connection, tenant_id=tenant_id)

    assert isinstance(first, InventoryRecord)
    assert first.available == 3
    assert second.available == 8
    assert second.version == 2
    assert [row.sku for row in report] == ["STOCK-1", "STOCK-2"]
    assert all(row.tenant_id == tenant_id for row in report)
    assert all(row.tenant_stock_value == Decimal("55.00") for row in report)
    with pytest.raises(FrozenInstanceError):
        second.available = 0  # type: ignore[misc]


def test_catalog_operations_leave_transaction_ownership_to_caller(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    product_id = uuid4()
    with engine.connect() as connection:
        transaction = connection.begin()
        create_tenant(connection, tenant_id=tenant_id, name="Rollback Tenant")
        upsert_product(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            sku="ROLLBACK-1",
            name="Rollback Product",
            unit_price=Decimal("3.00"),
            attributes={},
        )
        replenish_inventory(
            connection,
            tenant_id=tenant_id,
            product_id=product_id,
            quantity=2,
        )
        transaction.rollback()

        assert connection.scalar(select(func.count()).select_from(tenants)) == 0
        assert connection.scalar(select(func.count()).select_from(products)) == 0
        assert connection.scalar(select(func.count()).select_from(inventories)) == 0


def test_core_dml_scenario_records_expected_result_shapes(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "executemany_tenant_rows=2" in observations
    assert "upsert_preserved_product_id=True" in observations
    assert "returned_product_name=Updated" in observations
    assert "inventory_available=8" in observations
    assert "inventory_version=2" in observations
    assert "tenant_stock_value=100.00" in observations
    assert "tenant_report_rows=2" in observations
    assert "tenant_stock_values=130.00,130.00" in observations
