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


class RefundReferenceConflict(RuntimeError):
    pass


def _normalize_money(amount: Decimal, currency: str) -> str:
    if not isinstance(amount, Decimal):
        raise InvalidAmount("amount must be a Decimal")
    if amount <= 0:
        raise InvalidAmount("amount must be positive")
    if len(currency) != 3 or not currency.isalpha():
        raise InvalidCurrency("currency must be a three-letter code")
    return currency.upper()


def _validate_new_order(idempotency_key: str, created_at: datetime) -> None:
    if not idempotency_key.strip():
        raise ValueError("idempotency_key must not be blank")
    if created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", _normalize_money(self.amount, self.currency))


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_IN_PROGRESS = "payment_in_progress"
    PAYMENT_FAILED = "payment_failed"
    PAID = "paid"
    REFUND_IN_PROGRESS = "refund_in_progress"
    REFUNDED = "refunded"


@dataclass(slots=True)
class Order:
    id: UUID
    idempotency_key: str
    total: Money
    status: OrderStatus
    created_at: datetime
    payment_reference: str | None = None
    refund_reference: str | None = None
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
        _validate_new_order(idempotency_key, created_at)
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

    def start_refund(self) -> None:
        if self.status is OrderStatus.REFUND_IN_PROGRESS:
            return
        if self.status is not OrderStatus.PAID:
            self._reject(OrderStatus.REFUND_IN_PROGRESS)
        self.status = OrderStatus.REFUND_IN_PROGRESS
        self.version += 1

    def mark_refunded(self, provider_reference: str) -> None:
        if self.status is OrderStatus.REFUNDED:
            if self.refund_reference == provider_reference:
                return
            raise RefundReferenceConflict(
                "provider refund reference conflicts with completed refund"
            )
        if self.status is not OrderStatus.REFUND_IN_PROGRESS:
            self._reject(OrderStatus.REFUNDED)
        if not provider_reference.strip():
            raise ValueError("provider_reference must not be blank")
        self.status = OrderStatus.REFUNDED
        self.refund_reference = provider_reference
        self.version += 1

    def mark_refund_declined(self) -> None:
        if self.status is not OrderStatus.REFUND_IN_PROGRESS:
            self._reject(OrderStatus.PAID)
        self.status = OrderStatus.PAID
        self.refund_reference = None
        self.version += 1

    def _reject(self, target: OrderStatus) -> None:
        raise InvalidOrderTransition(f"cannot move {self.status.name} to {target.name}")
