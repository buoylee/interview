from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine

from order_service.db.schema import products, tenants
from order_service.db.statements import product_by_sku_statement
from scenarios.ch03_expression_compiler import run

pytestmark = pytest.mark.integration


def test_equivalent_executions_share_one_compiled_cache_entry(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    tenant_id = uuid4()
    product_id = uuid4()
    cache: dict[Any, Any] = {}
    with engine.begin() as connection:
        connection.execute(tenants.insert().values(id=tenant_id, name="Cache Tenant"))
        connection.execute(
            products.insert().values(
                id=product_id,
                tenant_id=tenant_id,
                sku="CACHE-1",
                name="Cached Product",
                unit_price=Decimal("10.00"),
                attributes={},
            )
        )
        cached_connection = connection.execution_options(compiled_cache=cache)
        statement = product_by_sku_statement()
        cached_connection.execute(statement, {"tenant_id": tenant_id, "sku": "CACHE-1"}).one()
        cached_connection.execute(statement, {"tenant_id": tenant_id, "sku": "CACHE-1"}).one()

    assert len(cache) == 1


def test_compiler_scenario_reports_cache_reuse(
    engine: Engine,
    recreated_schema: None,
) -> None:
    del recreated_schema
    observations = "\n".join(run(engine).observation)
    assert "compiled_cache_entries=1" in observations
    assert "naive_hostile_value_present_in_sql=True" in observations
    assert "corrected_hostile_value_present_in_sql=False" in observations
