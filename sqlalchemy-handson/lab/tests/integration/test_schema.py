import pytest
from sqlalchemy import Engine, inspect

from order_service.db.schema import metadata
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
