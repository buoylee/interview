from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from order_service.adapters.memory import (
    MemoryStore,
    MemoryUnitOfWork,
    StubPaymentGateway,
)
from order_service.application.process_payment import OrderNotFound
from order_service.application.refund_order import RefundOrder
from order_service.domain.order import InvalidOrderTransition, Money, Order


PAID_ORDER_ID = UUID("00000000-0000-0000-0000-000000000101")
TOTAL = Money(Decimal("10.00"), "USD")


def _paid_order() -> Order:
    order = Order.create(
        order_id=PAID_ORDER_ID,
        idempotency_key="create-paid-001",
        total=TOTAL,
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    order.start_payment()
    order.mark_paid("pay-001")
    return order


def _unpaid_order() -> Order:
    return Order.create(
        order_id=PAID_ORDER_ID,
        idempotency_key="create-unpaid-001",
        total=TOTAL,
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


def _unpaid_order_with_stale_reference() -> Order:
    order = _unpaid_order()
    order.payment_reference = "stale-pay"
    return order


@pytest.mark.asyncio
async def test_paid_order_refund_uses_exact_provider_contract() -> None:
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})
    gateway = StubPaymentGateway()
    refund = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    await refund.execute(PAID_ORDER_ID)

    assert gateway.refund_calls == [
        {
            "payment_reference": "pay-001",
            "total": TOTAL,
            "idempotency_key": f"refund:{PAID_ORDER_ID}",
        }
    ]
    assert store.commits == 2


@pytest.mark.asyncio
async def test_missing_order_is_reported_without_calling_provider() -> None:
    gateway = StubPaymentGateway()
    refund = RefundOrder(
        lambda: MemoryUnitOfWork(MemoryStore()), gateway
    )

    with pytest.raises(OrderNotFound, match=str(PAID_ORDER_ID)):
        await refund.execute(PAID_ORDER_ID)

    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_order_without_payment_reference_is_not_refunded() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _unpaid_order()})
    refund = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    with pytest.raises(
        InvalidOrderTransition, match="cannot refund order from PENDING_PAYMENT"
    ):
        await refund.execute(PAID_ORDER_ID)

    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_non_paid_order_with_stale_payment_reference_is_not_refunded() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(
        orders={PAID_ORDER_ID: _unpaid_order_with_stale_reference()}
    )
    refund = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    with pytest.raises(
        InvalidOrderTransition, match="cannot refund order from PENDING_PAYMENT"
    ):
        await refund.execute(PAID_ORDER_ID)

    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_retry_with_new_request_id_does_not_refund_twice() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})
    refund = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    await refund.execute(PAID_ORDER_ID)
    await refund.execute(PAID_ORDER_ID)

    assert len(gateway.refund_calls) == 1
