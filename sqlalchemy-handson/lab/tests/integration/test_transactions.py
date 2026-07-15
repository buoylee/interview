from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select

from order_service.application import catalog_service
from order_service.application.catalog_service import RegisterStockCommand
from order_service.db.schema import inventories, products, tenants
from scenarios.ch05_connection_transactions import run

pytestmark = pytest.mark.integration


def command() -> RegisterStockCommand:
    return RegisterStockCommand(
        tenant_id=uuid4(),
        tenant_name="Transaction Tenant",
        product_id=uuid4(),
        sku="TX-1",
        product_name="Transaction Product",
        unit_price=Decimal("20.00"),
        attributes={},
        quantity=4,
    )


def test_application_service_commits_the_complete_operation(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    value = command()

    result = catalog_service.register_product_with_stock(engine, value)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(products)) == 1
        assert connection.scalar(select(func.count()).select_from(inventories)) == 1
    assert result.available == 4


def test_application_service_registers_two_products_for_one_tenant(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    first = command()
    second = RegisterStockCommand(
        tenant_id=first.tenant_id,
        tenant_name=first.tenant_name,
        product_id=uuid4(),
        sku="TX-2",
        product_name="Second Product",
        unit_price=Decimal("30.00"),
        attributes={},
        quantity=2,
    )

    first_result = catalog_service.register_product_with_stock(engine, first)
    second_result = catalog_service.register_product_with_stock(engine, second)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(tenants)) == 1
        assert connection.scalar(select(func.count()).select_from(products)) == 2
        assert connection.scalar(select(func.count()).select_from(inventories)) == 2
    assert first_result.product_id == first.product_id
    assert second_result.product_id == second.product_id


def test_application_service_reuses_canonical_product_id_for_repeated_sku(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    first = command()
    requested_replacement_id = uuid4()
    second = RegisterStockCommand(
        tenant_id=first.tenant_id,
        tenant_name=first.tenant_name,
        product_id=requested_replacement_id,
        sku=first.sku,
        product_name="Updated Product",
        unit_price=Decimal("25.00"),
        attributes={"updated": True},
        quantity=3,
    )

    first_result = catalog_service.register_product_with_stock(engine, first)
    second_result = catalog_service.register_product_with_stock(engine, second)

    with engine.connect() as connection:
        stored_product_ids = connection.scalars(select(products.c.id)).all()
        stored_inventory = connection.execute(
            select(inventories.c.product_id, inventories.c.available)
        ).one()
    assert stored_product_ids == [first.product_id]
    assert requested_replacement_id not in stored_product_ids
    assert first_result.product_id == first.product_id
    assert second_result.product_id == first.product_id
    assert stored_inventory == (first.product_id, 7)


def test_application_service_rolls_back_every_prior_write(
    engine: Engine,
    recreated_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del recreated_schema
    value = command()

    def fail_after_product(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("failure injection after product upsert")

    monkeypatch.setattr(catalog_service, "replenish_inventory", fail_after_product)

    with pytest.raises(RuntimeError, match="failure injection"):
        catalog_service.register_product_with_stock(engine, value)

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(tenants)) == 0
        assert connection.scalar(select(func.count()).select_from(products)) == 0


def test_transaction_scenario_records_autobegin_and_savepoint(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "in_transaction_before_execute=False" in observations
    assert "in_transaction_after_execute=True" in observations
    assert "exception_block_rolled_back=True" in observations
    assert "savepoint_preserved_outer=True" in observations
    assert "failed_transaction_active=True" in observations
    assert "failed_transaction_rejected_statement=True" in observations
    assert "in_transaction_after_rollback=False" in observations
    assert "connection_reusable_after_rollback=True" in observations
    assert "naive_failed_transaction_rejected=True" in observations
    assert "corrected_connection_reusable=True" in observations
