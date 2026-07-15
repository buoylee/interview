from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class InvalidAmount(ValueError):
    pass


class InvalidCurrency(ValueError):
    pass


class InvalidOrderTransition(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise InvalidAmount("amount must be a Decimal")
        if self.amount <= 0:
            raise InvalidAmount("amount must be positive")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise InvalidCurrency("currency must be a three-letter code")
        object.__setattr__(self, "currency", self.currency.upper())


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_IN_PROGRESS = "payment_in_progress"
    PAYMENT_FAILED = "payment_failed"
    PAID = "paid"


@dataclass(slots=True)
class Order:
    id: UUID
    idempotency_key: str
    total: Money
    status: OrderStatus
    created_at: datetime
    payment_reference: str | None = None
    version: int = 1

    @classmethod
    def create(
        cls,
        *,
        order_id: UUID,
        idempotency_key: str,
        total: Money,
        created_at: datetime,
    ) -> "Order":
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be blank")
        if created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return cls(
            id=order_id,
            idempotency_key=idempotency_key,
            total=total,
            status=OrderStatus.PENDING_PAYMENT,
            created_at=created_at,
        )

    def start_payment(self) -> None:
        if self.status not in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}:
            self._reject(OrderStatus.PAYMENT_IN_PROGRESS)
        self.status = OrderStatus.PAYMENT_IN_PROGRESS
        self.version += 1

    def mark_paid(self, provider_reference: str) -> None:
        if self.status is OrderStatus.PAID and self.payment_reference == provider_reference:
            return
        if self.status is not OrderStatus.PAYMENT_IN_PROGRESS:
            self._reject(OrderStatus.PAID)
        if not provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        self.status = OrderStatus.PAID
        self.payment_reference = provider_reference
        self.version += 1

    def mark_payment_failed(self) -> None:
        if self.status is not OrderStatus.PAYMENT_IN_PROGRESS:
            self._reject(OrderStatus.PAYMENT_FAILED)
        self.status = OrderStatus.PAYMENT_FAILED
        self.version += 1

    def _reject(self, target: OrderStatus) -> None:
        raise InvalidOrderTransition(f"cannot move {self.status.name} to {target.name}")
