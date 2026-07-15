from uuid import uuid4

from sqlalchemy.dialects import postgresql

from order_service.db.statements import product_by_sku_statement


def test_product_lookup_keeps_hostile_value_out_of_sql_text() -> None:
    tenant_id = uuid4()
    hostile_sku = "x'; DROP TABLE products; --"
    statement = product_by_sku_statement().params(tenant_id=tenant_id, sku=hostile_sku)
    compiled = statement.compile(
        dialect=postgresql.dialect()  # type: ignore[no-untyped-call]
    )

    assert hostile_sku not in str(compiled)
    assert compiled.params["tenant_id"] == tenant_id
    assert compiled.params["sku"] == hostile_sku


def test_structurally_equal_lookups_compile_to_the_same_sql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    first = product_by_sku_statement().compile(dialect=dialect)
    second = product_by_sku_statement().compile(dialect=dialect)

    assert str(first) == str(second)
