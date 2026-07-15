from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias
from uuid import UUID

from order_service.domain.order import Money, Order

OrderFactory: TypeAlias = Callable[..., Order]


def make_order(
    *,
    order_id: UUID = UUID("00000000-0000-0000-0000-000000000001"),
    idempotency_key: str = "create-001",
    amount: Decimal = Decimal("10.00"),
    currency: str = "USD",
    created_at: datetime = datetime(2026, 7, 15, tzinfo=UTC),
) -> Order:
    return Order.create(
        order_id=order_id,
        idempotency_key=idempotency_key,
        total=Money(amount, currency),
        created_at=created_at,
    )
