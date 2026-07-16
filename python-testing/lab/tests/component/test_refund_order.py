import importlib
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from order_service.adapters.memory import (
    MemoryStore,
    MemoryUnitOfWork,
    StubPaymentGateway,
)
from order_service.adapters.sqlalchemy import ConcurrentOrderUpdate
from order_service.application.process_payment import OrderNotFound
from order_service.application.refund_order import (
    CapturedPaymentMissing,
    RefundOrder,
)
from order_service.domain.order import InvalidOrderTransition, OrderStatus
from order_service.ports.payment import (
    PaymentDeclined,
    PaymentProviderProtocolError,
    PaymentResult,
    PaymentUncertain,
)
from tests.factories import make_order


def paid_order():
    order = make_order()
    order.start_payment()
    order.mark_paid("pay-001")
    return order


class ConflictOnSaveUnitOfWork(MemoryUnitOfWork):
    async def __aenter__(self):
        entered = await super().__aenter__()
        entered.orders.save = AsyncMock(
            side_effect=ConcurrentOrderUpdate("stale refund")
        )
        return entered


def test_refund_order_use_case_is_importable() -> None:
    module = importlib.import_module("order_service.application.refund_order")

    assert isinstance(module.RefundOrder, type)


@pytest.mark.asyncio
async def test_missing_order_does_not_call_provider() -> None:
    gateway = StubPaymentGateway()
    use_case = RefundOrder(lambda: MemoryUnitOfWork(MemoryStore()), gateway)

    with pytest.raises(OrderNotFound):
        await use_case.execute(uuid4())

    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_invalid_order_state_does_not_call_provider() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway()

    with pytest.raises(
        InvalidOrderTransition,
        match="cannot refund order from PENDING_PAYMENT",
    ):
        await RefundOrder(
            lambda: MemoryUnitOfWork(store), gateway
        ).execute(order.id)

    assert gateway.refund_calls == []
    assert store.commits == 0


@pytest.mark.asyncio
async def test_paid_order_without_reference_is_rejected_before_intent_commit() -> None:
    order = paid_order()
    order.payment_reference = None
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway()

    with pytest.raises(CapturedPaymentMissing):
        await RefundOrder(
            lambda: MemoryUnitOfWork(store), gateway
        ).execute(order.id)

    assert store.orders[order.id].status is OrderStatus.PAID
    assert store.commits == 0
    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_already_refunded_replay_returns_without_provider_call() -> None:
    order = paid_order()
    order.start_refund()
    order.mark_refunded("refund-existing")
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway()

    result = await RefundOrder(
        lambda: MemoryUnitOfWork(store), gateway
    ).execute(order.id)

    assert result.refund_reference == "refund-existing"
    assert gateway.refund_calls == []
    assert store.commits == 0


@pytest.mark.asyncio
async def test_paid_order_is_refunded_in_two_transactions() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("refund-001"))

    result = await RefundOrder(
        lambda: MemoryUnitOfWork(store), gateway
    ).execute(order.id)

    assert result.status is OrderStatus.REFUNDED
    assert result.refund_reference == "refund-001"
    assert store.orders[order.id].status is OrderStatus.REFUNDED
    assert store.commits == 2
    assert gateway.refund_calls == [
        {
            "payment_reference": "pay-001",
            "total": order.total,
            "idempotency_key": f"refund:{order.id}",
        }
    ]


@pytest.mark.asyncio
async def test_in_progress_retry_reuses_deterministic_provider_key() -> None:
    order = paid_order()
    order.start_refund()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("refund-reconciled"))

    result = await RefundOrder(
        lambda: MemoryUnitOfWork(store), gateway
    ).execute(order.id)

    assert result.status is OrderStatus.REFUNDED
    assert result.refund_reference == "refund-reconciled"
    assert store.commits == 1
    assert gateway.refund_calls[0]["idempotency_key"] == f"refund:{order.id}"


@pytest.mark.asyncio
async def test_uncertain_refund_stays_in_progress_and_retries_same_key() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentUncertain("refund timeout"))
    use_case = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    for _ in range(2):
        with pytest.raises(PaymentUncertain, match="refund timeout"):
            await use_case.execute(order.id)

    assert store.orders[order.id].status is OrderStatus.REFUND_IN_PROGRESS
    assert store.commits == 1
    assert [call["idempotency_key"] for call in gateway.refund_calls] == [
        f"refund:{order.id}",
        f"refund:{order.id}",
    ]


@pytest.mark.asyncio
async def test_definitive_decline_restores_paid_state_and_re_raises() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentDeclined("refund rejected"))

    with pytest.raises(PaymentDeclined, match="refund rejected"):
        await RefundOrder(
            lambda: MemoryUnitOfWork(store), gateway
        ).execute(order.id)

    persisted = store.orders[order.id]
    assert persisted.status is OrderStatus.PAID
    assert persisted.payment_reference == "pay-001"
    assert persisted.refund_reference is None
    assert store.commits == 2


@pytest.mark.asyncio
async def test_provider_protocol_error_keeps_refund_in_progress() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(
        error=PaymentProviderProtocolError("malformed refund response")
    )

    with pytest.raises(
        PaymentProviderProtocolError,
        match="malformed refund response",
    ):
        await RefundOrder(
            lambda: MemoryUnitOfWork(store), gateway
        ).execute(order.id)

    assert store.orders[order.id].status is OrderStatus.REFUND_IN_PROGRESS
    assert store.commits == 1


@pytest.mark.asyncio
async def test_order_missing_after_provider_success_is_reported() -> None:
    order = paid_order()
    stores = [MemoryStore(orders={order.id: order}), MemoryStore()]
    gateway = StubPaymentGateway(result=PaymentResult("refund-001"))

    with pytest.raises(OrderNotFound, match=str(order.id)):
        await RefundOrder(
            lambda: MemoryUnitOfWork(stores.pop(0)), gateway
        ).execute(order.id)

    assert len(gateway.refund_calls) == 1


@pytest.mark.asyncio
async def test_concurrent_completion_conflict_is_not_reported_as_success() -> None:
    order = paid_order()
    store = MemoryStore(orders={order.id: order})
    uows = [MemoryUnitOfWork(store), ConflictOnSaveUnitOfWork(store)]
    gateway = StubPaymentGateway(result=PaymentResult("refund-001"))

    with pytest.raises(ConcurrentOrderUpdate):
        await RefundOrder(lambda: uows.pop(0), gateway).execute(order.id)

    assert store.orders[order.id].status is OrderStatus.REFUND_IN_PROGRESS
    assert store.commits == 1
    assert len(gateway.refund_calls) == 1
