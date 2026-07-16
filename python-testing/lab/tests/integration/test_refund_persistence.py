from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from order_service.adapters.memory import StubPaymentGateway
from order_service.adapters.sqlalchemy import (
    ConcurrentOrderUpdate,
    SQLAlchemyUnitOfWork,
)
from order_service.application.refund_order import RefundOrder
from order_service.domain.order import Money, Order, OrderStatus
from order_service.domain.order import RefundReferenceConflict
from order_service.ports.payment import PaymentResult, PaymentUncertain

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def paid_order(order_id: UUID) -> Order:
    order = Order.create(
        order_id=order_id,
        idempotency_key=f"create-{order_id}",
        total=Money(Decimal("10.00"), "USD"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    order.start_payment()
    order.mark_paid(f"pay-{order_id}")
    return order


@pytest.mark.asyncio(loop_scope="session")
async def test_refund_timeout_persists_in_progress_across_uows(
    session_factory,
) -> None:
    order = paid_order(UUID(int=1501))
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    async with uow_factory() as uow:
        await uow.orders.add(order)
        await uow.commit()

    with pytest.raises(PaymentUncertain, match="refund timeout"):
        await RefundOrder(
            uow_factory,
            StubPaymentGateway(error=PaymentUncertain("refund timeout")),
        ).execute(order.id)

    async with uow_factory() as uow:
        persisted = await uow.orders.get(order.id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUND_IN_PROGRESS
    assert persisted.refund_reference is None


@pytest.mark.asyncio(loop_scope="session")
async def test_refunded_state_and_provider_reference_persist(
    session_factory,
) -> None:
    order = paid_order(UUID(int=1502))
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    async with uow_factory() as uow:
        await uow.orders.add(order)
        await uow.commit()

    await RefundOrder(
        uow_factory,
        StubPaymentGateway(result=PaymentResult("refund-1502")),
    ).execute(order.id)

    async with uow_factory() as uow:
        persisted = await uow.orders.get(order.id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUNDED
    assert persisted.refund_reference == "refund-1502"


@pytest.mark.asyncio(loop_scope="session")
async def test_stale_concurrent_refund_save_raises_conflict(session_factory) -> None:
    order = paid_order(UUID(int=1503))
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        first = await uow.orders.get(order.id)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        second = await uow.orders.get(order.id)
    assert first is not None and second is not None

    first.start_refund()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.save(first)
        await uow.commit()

    second.start_refund()
    with pytest.raises(ConcurrentOrderUpdate, match=str(order.id)):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.save(second)


@pytest.mark.asyncio(loop_scope="session")
async def test_completion_reload_accepts_same_reference_without_stale_save(
    session_factory,
) -> None:
    order = paid_order(UUID(int=1504))
    order.start_refund()
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    async with uow_factory() as uow:
        await uow.orders.add(order)
        await uow.commit()

    class ConcurrentCompletingGateway:
        async def refund(self, **kwargs) -> PaymentResult:
            async with uow_factory() as concurrent_uow:
                concurrent = await concurrent_uow.orders.get(order.id)
                assert concurrent is not None
                concurrent.mark_refunded("refund-race")
                await concurrent_uow.orders.save(concurrent)
                await concurrent_uow.commit()
            return PaymentResult("refund-race")

    result = await RefundOrder(
        uow_factory,
        ConcurrentCompletingGateway(),  # type: ignore[arg-type]
    ).execute(order.id)

    assert result.status is OrderStatus.REFUNDED
    assert result.refund_reference == "refund-race"
    async with uow_factory() as uow:
        persisted = await uow.orders.get(order.id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUNDED
    assert persisted.refund_reference == "refund-race"


@pytest.mark.asyncio(loop_scope="session")
async def test_completion_reload_rejects_conflicting_provider_reference(
    session_factory,
) -> None:
    order = paid_order(UUID(int=1505))
    order.start_refund()
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    async with uow_factory() as uow:
        await uow.orders.add(order)
        await uow.commit()

    class ConflictingConcurrentGateway:
        async def refund(self, **kwargs) -> PaymentResult:
            async with uow_factory() as concurrent_uow:
                concurrent = await concurrent_uow.orders.get(order.id)
                assert concurrent is not None
                concurrent.mark_refunded("refund-winner")
                await concurrent_uow.orders.save(concurrent)
                await concurrent_uow.commit()
            return PaymentResult("refund-loser")

    with pytest.raises(RefundReferenceConflict):
        await RefundOrder(
            uow_factory,
            ConflictingConcurrentGateway(),  # type: ignore[arg-type]
        ).execute(order.id)

    async with uow_factory() as uow:
        persisted = await uow.orders.get(order.id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUNDED
    assert persisted.refund_reference == "refund-winner"
