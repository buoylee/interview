from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from inspect import signature
from uuid import UUID

import pytest

from order_service.adapters.memory import (
    FrozenClock,
    MemoryStore,
    MemoryUnitOfWork,
    SequenceIdGenerator,
)
from order_service.application.create_order import CreateOrder
from order_service.application.messages import CreateOrderCommand
from order_service.domain.order import Money, OrderStatus


def test_create_order_use_case_has_stable_public_surface() -> None:
    module = import_module("order_service.application.create_order")

    assert str(signature(module.CreateOrder.__init__)) == (
        "(self, uow_factory: collections.abc.Callable[[], order_service.ports.uow.UnitOfWork], "
        "ids: order_service.ports.system.IdGenerator, "
        "clock: order_service.ports.system.Clock) -> None"
    )
    assert str(signature(module.CreateOrder.execute)) == (
        "(self, command: order_service.application.messages.CreateOrderCommand) "
        "-> order_service.domain.order.Order"
    )


@pytest.mark.asyncio
async def test_create_order_writes_exact_order_and_payment_request_once() -> None:
    order_id = UUID("00000000-0000-0000-0000-000000000001")
    message_id = UUID("00000000-0000-0000-0000-000000000002")
    unused_id = UUID("00000000-0000-0000-0000-000000000003")
    now = datetime(2026, 7, 15, tzinfo=UTC)
    store = MemoryStore()
    ids = SequenceIdGenerator(order_id, message_id, unused_id)
    use_case = CreateOrder(
        uow_factory=lambda: MemoryUnitOfWork(store),
        ids=ids,
        clock=FrozenClock(now),
    )
    command = CreateOrderCommand("create-001", Decimal("10.00"), "USD")

    first = await use_case.execute(command)
    second = await use_case.execute(command)

    assert first.id == order_id
    assert first.idempotency_key == "create-001"
    assert first.total == Money(Decimal("10.00"), "USD")
    assert first.status is OrderStatus.PENDING_PAYMENT
    assert first.created_at == now
    assert second.id == first.id
    assert len(store.orders) == 1
    assert store.orders[order_id] == first
    assert len(store.outbox) == 1
    assert store.outbox[0].id == message_id
    assert store.outbox[0].topic == "payment_requested"
    assert store.outbox[0].aggregate_id == order_id
    assert store.outbox[0].payload == {"order_id": str(order_id)}
    assert store.outbox[0].occurred_at == now
    assert store.outbox[0].available_at == now
    assert store.outbox[0].attempts == 0
    assert store.outbox[0].claimed_at is None
    assert store.outbox[0].done is False
    assert store.commits == 2
    assert ids.new() == unused_id


@pytest.mark.asyncio
async def test_create_order_does_not_publish_partial_state_when_message_id_fails() -> None:
    store = MemoryStore()
    use_case = CreateOrder(
        lambda: MemoryUnitOfWork(store),
        SequenceIdGenerator(UUID("00000000-0000-0000-0000-000000000001")),
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )

    with pytest.raises(RuntimeError, match=r"^no IDs remaining$"):
        await use_case.execute(
            CreateOrderCommand("create-001", Decimal("10.00"), "USD")
        )

    assert store.orders == {}
    assert store.outbox == []
    assert store.commits == 0
