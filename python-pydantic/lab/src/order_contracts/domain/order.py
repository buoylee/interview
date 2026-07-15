from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from order_contracts.application.commands import CreateOrderCommand


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"


@dataclass(frozen=True, slots=True)
class OrderLine:
    sku: str
    quantity: int
    unit_amount: Decimal

    @property
    def subtotal(self) -> Decimal:
        return self.unit_amount * self.quantity


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    customer_id: str
    lines: tuple[OrderLine, ...]
    currency: str
    status: OrderStatus
    internal_note: str | None = None

    @classmethod
    def create(cls, order_id: str, command: CreateOrderCommand) -> "Order":
        currencies = {line.currency for line in command.lines}
        if len(currencies) != 1:
            raise ValueError("an order must use a single currency")
        lines = tuple(
            OrderLine(
                sku=line.sku,
                quantity=line.quantity,
                unit_amount=line.unit_amount,
            )
            for line in command.lines
        )
        return cls(
            order_id=order_id,
            customer_id=command.customer_id,
            lines=lines,
            currency=next(iter(currencies)),
            status=OrderStatus.PENDING_PAYMENT,
        )

    @property
    def total_amount(self) -> Decimal:
        return sum((line.subtotal for line in self.lines), start=Decimal("0"))
