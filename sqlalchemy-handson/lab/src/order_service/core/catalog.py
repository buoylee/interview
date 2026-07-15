from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from order_service.db.schema import inventories, products, tenants


@dataclass(frozen=True, slots=True)
class ProductRecord:
    id: UUID
    tenant_id: UUID
    sku: str
    name: str
    unit_price: Decimal
    attributes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    tenant_id: UUID
    product_id: UUID
    sku: str
    available: int
    reserved: int
    version: int
    tenant_stock_value: Decimal


def create_tenant(connection: Connection, *, tenant_id: UUID, name: str) -> None:
    connection.execute(tenants.insert().values(id=tenant_id, name=name))


def ensure_tenant(connection: Connection, *, tenant_id: UUID, name: str) -> None:
    statement = (
        pg_insert(tenants)
        .values(id=tenant_id, name=name)
        .on_conflict_do_nothing(index_elements=[tenants.c.id])
    )
    connection.execute(statement)


def upsert_product(
    connection: Connection,
    *,
    tenant_id: UUID,
    product_id: UUID,
    sku: str,
    name: str,
    unit_price: Decimal,
    attributes: Mapping[str, Any],
) -> ProductRecord:
    insert_statement = pg_insert(products).values(
        id=product_id,
        tenant_id=tenant_id,
        sku=sku,
        name=name,
        unit_price=unit_price,
        attributes=dict(attributes),
    )
    statement = insert_statement.on_conflict_do_update(
        constraint="uq_products_tenant_id_sku",
        set_={
            "name": insert_statement.excluded.name,
            "unit_price": insert_statement.excluded.unit_price,
            "attributes": insert_statement.excluded.attributes,
        },
    ).returning(
        products.c.id,
        products.c.tenant_id,
        products.c.sku,
        products.c.name,
        products.c.unit_price,
        products.c.attributes,
    )
    row = connection.execute(statement).mappings().one()
    return ProductRecord(
        id=row["id"],
        tenant_id=row["tenant_id"],
        sku=row["sku"],
        name=row["name"],
        unit_price=row["unit_price"],
        attributes=row["attributes"],
    )


def replenish_inventory(
    connection: Connection,
    *,
    tenant_id: UUID,
    product_id: UUID,
    quantity: int,
) -> InventoryRecord:
    insert_statement = pg_insert(inventories).values(
        tenant_id=tenant_id,
        product_id=product_id,
        available=quantity,
        reserved=0,
        version=1,
    )
    statement = insert_statement.on_conflict_do_update(
        index_elements=[inventories.c.tenant_id, inventories.c.product_id],
        set_={
            "available": inventories.c.available + insert_statement.excluded.available,
            "version": inventories.c.version + 1,
        },
    ).returning(
        inventories.c.tenant_id,
        inventories.c.product_id,
        inventories.c.available,
        inventories.c.reserved,
        inventories.c.version,
    )
    stock = connection.execute(statement).mappings().one()
    product = connection.execute(
        select(products.c.sku, products.c.unit_price).where(
            products.c.tenant_id == tenant_id,
            products.c.id == product_id,
        )
    ).mappings().one()
    return InventoryRecord(
        tenant_id=stock["tenant_id"],
        product_id=stock["product_id"],
        sku=product["sku"],
        available=stock["available"],
        reserved=stock["reserved"],
        version=stock["version"],
        tenant_stock_value=(stock["available"] - stock["reserved"])
        * product["unit_price"],
    )


def inventory_report(connection: Connection, *, tenant_id: UUID) -> list[InventoryRecord]:
    stock = (
        select(
            inventories.c.tenant_id,
            inventories.c.product_id,
            products.c.sku,
            inventories.c.available,
            inventories.c.reserved,
            inventories.c.version,
            (
                (inventories.c.available - inventories.c.reserved) * products.c.unit_price
            ).label("stock_value"),
        )
        .join(
            products,
            (products.c.tenant_id == inventories.c.tenant_id)
            & (products.c.id == inventories.c.product_id),
        )
        .cte("stock")
    )
    statement = (
        select(
            stock.c.tenant_id,
            stock.c.product_id,
            stock.c.sku,
            stock.c.available,
            stock.c.reserved,
            stock.c.version,
            func.sum(stock.c.stock_value)
            .over(partition_by=stock.c.tenant_id)
            .label("tenant_stock_value"),
        )
        .where(stock.c.tenant_id == tenant_id)
        .order_by(stock.c.sku)
    )
    return [
        InventoryRecord(
            tenant_id=row["tenant_id"],
            product_id=row["product_id"],
            sku=row["sku"],
            available=row["available"],
            reserved=row["reserved"],
            version=row["version"],
            tenant_stock_value=row["tenant_stock_value"],
        )
        for row in connection.execute(statement).mappings()
    ]
