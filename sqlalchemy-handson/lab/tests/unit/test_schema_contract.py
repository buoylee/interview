from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from order_service.db.schema import Money, metadata


def test_schema_has_stable_tables_and_constraint_names() -> None:
    assert set(metadata.tables) == {
        "tenants",
        "products",
        "inventories",
        "orders",
        "order_lines",
        "inventory_reservations",
        "idempotency_records",
        "outbox_events",
    }
    product_names = {constraint.name for constraint in metadata.tables["products"].constraints}
    assert "pk_products" in product_names
    assert "uq_products_tenant_id_sku" in product_names


def test_money_quantizes_decimal_and_rejects_float() -> None:
    money = Money()
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    assert money.process_bind_param(Decimal("12.345"), dialect) == Decimal("12.34")
    with pytest.raises(TypeError, match="Decimal"):
        money.process_bind_param(12.34, dialect)  # type: ignore[arg-type]
    assert Money.cache_ok is True
