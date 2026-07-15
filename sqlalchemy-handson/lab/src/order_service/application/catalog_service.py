from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Engine

from order_service.core.catalog import (
    InventoryRecord,
    ensure_tenant,
    replenish_inventory,
    upsert_product,
)


@dataclass(frozen=True, slots=True)
class RegisterStockCommand:
    tenant_id: UUID
    tenant_name: str
    product_id: UUID
    sku: str
    product_name: str
    unit_price: Decimal
    attributes: Mapping[str, Any]
    quantity: int


def register_product_with_stock(
    engine: Engine,
    command: RegisterStockCommand,
) -> InventoryRecord:
    if command.quantity <= 0:
        raise ValueError("quantity must be positive")
    with engine.begin() as connection:
        ensure_tenant(
            connection,
            tenant_id=command.tenant_id,
            name=command.tenant_name,
        )
        product = upsert_product(
            connection,
            tenant_id=command.tenant_id,
            product_id=command.product_id,
            sku=command.sku,
            name=command.product_name,
            unit_price=command.unit_price,
            attributes=command.attributes,
        )
        return replenish_inventory(
            connection,
            tenant_id=command.tenant_id,
            product_id=product.id,
            quantity=command.quantity,
        )
