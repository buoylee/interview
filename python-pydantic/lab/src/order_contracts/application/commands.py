from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateOrderLine:
    sku: str
    quantity: int
    unit_amount: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    customer_id: str
    idempotency_key: str
    lines: tuple[CreateOrderLine, ...]
