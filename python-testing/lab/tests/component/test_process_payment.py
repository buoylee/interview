import pytest
from uuid import uuid4

from order_service.adapters.memory import MemoryStore, MemoryUnitOfWork, StubPaymentGateway
from order_service.application.process_payment import OrderNotFound, ProcessPayment
from order_service.domain.order import InvalidOrderTransition, OrderStatus
from order_service.ports.payment import PaymentDeclined, PaymentResult, PaymentUncertain
from tests.factories import make_order


@pytest.mark.asyncio
async def test_timeout_leaves_order_in_progress_for_reconciliation() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentUncertain("provider timeout"))

    with pytest.raises(PaymentUncertain, match="provider timeout"):
        await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert store.orders[order.id].status.value == "payment_in_progress"
    assert store.commits == 1
    assert gateway.charge_calls[0]["idempotency_key"] == f"charge:{order.id}"


@pytest.mark.asyncio
async def test_approved_payment_commits_provider_reference() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("pay-001"))

    paid = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert paid.status is OrderStatus.PAID
    assert paid.payment_reference == "pay-001"
    assert store.commits == 2


@pytest.mark.asyncio
async def test_declined_payment_commits_failed_state() -> None:
    order = make_order()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(error=PaymentDeclined("insufficient_funds"))

    failed = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert failed.status is OrderStatus.PAYMENT_FAILED
    assert store.commits == 2


@pytest.mark.asyncio
async def test_already_paid_replay_does_not_call_gateway() -> None:
    order = make_order()
    order.start_payment()
    order.mark_paid("pay-existing")
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("must-not-be-used"))

    replayed = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert replayed.payment_reference == "pay-existing"
    assert gateway.charge_calls == []
    assert store.commits == 0


@pytest.mark.asyncio
async def test_in_progress_replay_reuses_same_idempotency_key() -> None:
    order = make_order()
    order.start_payment()
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway(result=PaymentResult("pay-reconciled"))

    paid = await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert paid.status is OrderStatus.PAID
    assert store.commits == 1
    assert gateway.charge_calls[0]["idempotency_key"] == f"charge:{order.id}"


@pytest.mark.asyncio
async def test_missing_order_does_not_call_gateway() -> None:
    gateway = StubPaymentGateway()

    with pytest.raises(OrderNotFound):
        await ProcessPayment(lambda: MemoryUnitOfWork(MemoryStore()), gateway).execute(uuid4())

    assert gateway.charge_calls == []


@pytest.mark.asyncio
async def test_invalid_state_does_not_call_gateway() -> None:
    order = make_order()
    order.status = "cancelled"  # type: ignore[assignment]
    store = MemoryStore(orders={order.id: order})
    gateway = StubPaymentGateway()

    with pytest.raises(InvalidOrderTransition, match="cannot process payment"):
        await ProcessPayment(lambda: MemoryUnitOfWork(store), gateway).execute(order.id)

    assert gateway.charge_calls == []
