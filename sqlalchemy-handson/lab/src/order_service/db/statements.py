from typing import Any

from sqlalchemy import Select, bindparam, select

from order_service.db.schema import products


def product_by_sku_statement() -> Select[Any]:
    return select(
        products.c.id,
        products.c.tenant_id,
        products.c.sku,
        products.c.name,
        products.c.unit_price,
        products.c.attributes,
    ).where(
        products.c.tenant_id == bindparam("tenant_id"),
        products.c.sku == bindparam("sku"),
    )
