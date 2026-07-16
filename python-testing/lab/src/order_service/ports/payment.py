from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from order_service.domain.order import Money


class PaymentDeclined(RuntimeError):
    """Provider definitively rejected the operation."""

    pass


class PaymentUncertain(RuntimeError):
    """No definitive provider result was received.

    Gateways conservatively map every transport/request failure here because the
    port cannot prove whether the provider observed or committed the operation.
    Callers must reconcile or retry with the same idempotency key.
    """

    pass


class PaymentProviderProtocolError(RuntimeError):
    """A provider response was received but violated the expected contract."""

    pass


@dataclass(frozen=True, slots=True)
class PaymentResult:
    reference: str


class PaymentGateway(Protocol):
    async def charge(
        self, *, order_id: UUID, total: Money, idempotency_key: str
    ) -> PaymentResult: ...

    async def refund(
        self, *, payment_reference: str, total: Money, idempotency_key: str
    ) -> PaymentResult: ...
