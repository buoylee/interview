from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError

from order_service.adapters.sqlalchemy import ConcurrentOrderUpdate, SQLAlchemyUnitOfWork
from order_service.domain.order import Money, Order

pytestmark = [pytest.mark.integration, pytest.mark.docker]


def make_order(*, order_id: UUID, idempotency_key: str = "create-order") -> Order:
    return Order.create(
        order_id=order_id,
        idempotency_key=idempotency_key,
        total=Money(Decimal("10.00"), "USD"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_committed_order_is_visible_to_a_new_uow(session_factory) -> None:
    order = make_order(order_id=UUID(int=1), idempotency_key="create-001")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        loaded = await uow.orders.get(order.id)
    assert loaded == order


@pytest.mark.asyncio(loop_scope="session")
async def test_add_get_and_get_by_key_map_all_order_fields(session_factory) -> None:
    order = make_order(order_id=UUID(int=2), idempotency_key="lookup")
    order.start_payment()
    order.mark_paid("provider-ref")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.orders.get(order.id) is None
        assert await uow.orders.get_by_idempotency_key("missing") is None
        await uow.orders.add(order)
        loaded = await uow.orders.get_by_idempotency_key("lookup")
        assert loaded == order
        assert loaded is not order
        await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_normal_exit_without_commit_rolls_back(session_factory) -> None:
    order = make_order(order_id=UUID(int=3))
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.orders.get(order.id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_exception_exit_rolls_back(session_factory) -> None:
    order = make_order(order_id=UUID(int=4))
    with pytest.raises(RuntimeError, match="abort"):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.add(order)
            raise RuntimeError("abort")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.orders.get(order.id) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_idempotency_key_uses_real_constraint(session_factory) -> None:
    first = make_order(order_id=UUID(int=5), idempotency_key="same-key")
    second = make_order(order_id=UUID(int=6), idempotency_key="same-key")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(first)
        await uow.commit()
    with pytest.raises(IntegrityError):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.add(second)
            await uow.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_save_maps_committed_status_reference_and_version(session_factory) -> None:
    order = make_order(order_id=UUID(int=7))
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    order.start_payment()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.save(order)
        await uow.commit()
    order.mark_paid("paid-007")
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.save(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.orders.get(order.id) == order


@pytest.mark.asyncio(loop_scope="session")
async def test_stale_save_raises_concurrent_update(session_factory) -> None:
    order = make_order(order_id=UUID(int=8))
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.add(order)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        first = await uow.orders.get(order.id)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        second = await uow.orders.get(order.id)
    assert first is not None and second is not None
    first.start_payment()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.orders.save(first)
        await uow.commit()
    second.start_payment()
    with pytest.raises(ConcurrentOrderUpdate, match=str(order.id)):
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.orders.save(second)


@pytest.mark.parametrize("raises", [False, True], ids=["normal", "exception"])
@pytest.mark.asyncio(loop_scope="session")
async def test_uow_closes_owned_session_exactly_once(async_engine, raises) -> None:
    sessions = []

    class TrackingAsyncSession(AsyncSession):
        close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1
            await super().close()

    def tracked_session_factory():
        session = async_sessionmaker(
            async_engine, class_=TrackingAsyncSession, expire_on_commit=False
        )()
        sessions.append(session)
        return session

    if raises:
        with pytest.raises(RuntimeError, match="abort close"):
            async with SQLAlchemyUnitOfWork(tracked_session_factory):
                raise RuntimeError("abort close")
    else:
        async with SQLAlchemyUnitOfWork(tracked_session_factory):
            pass

    assert len(sessions) == 1
    assert sessions[0].close_calls == 1
