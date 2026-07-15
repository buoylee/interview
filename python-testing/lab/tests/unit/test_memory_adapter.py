from datetime import UTC, datetime, timedelta
from importlib import import_module
from uuid import UUID

import pytest

from order_service.adapters.memory import (
    FrozenClock,
    MemoryOrderRepository,
    MemoryOutboxRepository,
    MemoryStore,
    MemoryUnitOfWork,
    SequenceIdGenerator,
)
from order_service.application.messages import OutboxMessage
from order_service.domain.order import OrderStatus
from tests.factories import make_order


def test_memory_adapter_exposes_required_fakes() -> None:
    memory = import_module("order_service.adapters.memory")

    assert [
        name
        for name in (
            "FrozenClock",
            "MemoryOrderRepository",
            "MemoryOutboxRepository",
            "MemoryStore",
            "MemoryUnitOfWork",
            "SequenceIdGenerator",
        )
        if not hasattr(memory, name)
    ] == []


def test_frozen_clock_returns_exact_datetime() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)

    assert FrozenClock(now).now() is now


def test_sequence_id_generator_returns_values_in_order_then_fails_stably() -> None:
    first = UUID("00000000-0000-0000-0000-000000000001")
    second = UUID("00000000-0000-0000-0000-000000000002")
    ids = SequenceIdGenerator(first, second)

    assert ids.new() == first
    assert ids.new() == second
    with pytest.raises(RuntimeError, match=r"^no IDs remaining$"):
        ids.new()


def test_memory_store_defaults_are_independent() -> None:
    first = MemoryStore()
    second = MemoryStore()
    order = make_order()

    first.orders[order.id] = order
    first.outbox.append(
        OutboxMessage(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            topic="payment_requested",
            aggregate_id=order.id,
            payload={"order_id": str(order.id)},
            occurred_at=datetime(2026, 7, 15, tzinfo=UTC),
        )
    )
    first.commits += 1

    assert second.orders == {}
    assert second.outbox == []
    assert second.commits == 0


@pytest.mark.asyncio
async def test_memory_order_repository_adds_reads_finds_and_saves_real_orders() -> None:
    orders = {}
    repository = MemoryOrderRepository(orders)
    original = make_order()

    assert await repository.get(original.id) is None
    assert await repository.get_by_idempotency_key("create-001") is None

    await repository.add(original)

    assert await repository.get(original.id) is original
    assert await repository.get_by_idempotency_key("create-001") is original
    assert await repository.get_by_idempotency_key("missing") is None

    replacement = make_order(
        order_id=original.id,
        idempotency_key="create-replacement",
    )
    await repository.save(replacement)

    assert await repository.get(original.id) is replacement


def _message(
    number: int,
    *,
    now: datetime,
    available_at: datetime | None = None,
    claimed_at: datetime | None = None,
    done: bool = False,
) -> OutboxMessage:
    return OutboxMessage(
        id=UUID(f"00000000-0000-0000-0000-{number:012d}"),
        topic="payment_requested",
        aggregate_id=UUID("00000000-0000-0000-0000-000000000099"),
        payload={"order_id": "order-099"},
        occurred_at=now,
        available_at=available_at,
        claimed_at=claimed_at,
        done=done,
    )


@pytest.mark.asyncio
async def test_memory_outbox_claims_due_available_messages_with_lease_and_limit() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    due_without_backoff = _message(1, now=now)
    due_at_boundary = _message(2, now=now, available_at=now)
    future = _message(3, now=now, available_at=now + timedelta(seconds=1))
    done = _message(4, now=now, done=True)
    leased = _message(5, now=now, claimed_at=now - timedelta(seconds=29))
    lease_expired = _message(6, now=now, claimed_at=now - timedelta(seconds=30))
    beyond_limit = _message(7, now=now)
    messages = [
        due_without_backoff,
        due_at_boundary,
        future,
        done,
        leased,
        lease_expired,
        beyond_limit,
    ]
    repository = MemoryOutboxRepository(messages)

    claimed = await repository.claim_batch(limit=3, now=now)

    assert claimed == [due_without_backoff, due_at_boundary, lease_expired]
    assert [message.claimed_at for message in claimed] == [now, now, now]
    assert future.claimed_at is None
    assert done.claimed_at is None
    assert leased.claimed_at == now - timedelta(seconds=29)
    assert beyond_limit.claimed_at is None


@pytest.mark.asyncio
async def test_memory_outbox_zero_limit_claims_nothing() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = _message(1, now=now)
    repository = MemoryOutboxRepository([message])

    assert await repository.claim_batch(limit=0, now=now) == []
    assert message.claimed_at is None


@pytest.mark.asyncio
async def test_memory_outbox_rejects_negative_limit_without_claiming() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = _message(1, now=now)
    repository = MemoryOutboxRepository([message])

    with pytest.raises(ValueError, match=r"^limit must not be negative$"):
        await repository.claim_batch(limit=-1, now=now)
    assert message.claimed_at is None


@pytest.mark.asyncio
async def test_memory_outbox_add_done_and_failed_transitions_are_observable() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    retry_at = now + timedelta(seconds=10)
    done_message = _message(1, now=now, claimed_at=now)
    failed_message = _message(2, now=now, claimed_at=now)
    messages = [done_message]
    repository = MemoryOutboxRepository(messages)

    await repository.add(failed_message)
    await repository.mark_done(done_message.id)
    await repository.mark_failed(failed_message.id, available_at=retry_at)
    second_retry_at = retry_at + timedelta(seconds=10)
    await repository.mark_failed(failed_message.id, available_at=second_retry_at)

    assert messages == [done_message, failed_message]
    assert done_message.done is True
    assert done_message.claimed_at is None
    assert failed_message.attempts == 2
    assert failed_message.available_at == second_retry_at
    assert failed_message.claimed_at is None


@pytest.mark.asyncio
async def test_memory_outbox_missing_ids_raise_key_error() -> None:
    repository = MemoryOutboxRepository([])
    missing = UUID("00000000-0000-0000-0000-000000000404")
    now = datetime(2026, 7, 15, tzinfo=UTC)

    with pytest.raises(KeyError, match=str(missing)):
        await repository.mark_done(missing)
    with pytest.raises(KeyError, match=str(missing)):
        await repository.mark_failed(missing, available_at=now)


@pytest.mark.asyncio
async def test_uow_isolates_entered_state_and_reads_its_own_writes() -> None:
    persisted = make_order()
    store = MemoryStore(orders={persisted.id: persisted})
    new_order = make_order(
        order_id=UUID("00000000-0000-0000-0000-000000000002"),
        idempotency_key="create-002",
    )
    uow = MemoryUnitOfWork(store)

    async with uow as entered:
        loaded = await entered.orders.get(persisted.id)
        assert entered is uow
        assert loaded == persisted
        assert loaded is not persisted

        loaded.start_payment()
        await entered.orders.add(new_order)

        assert await entered.orders.get(new_order.id) is new_order
        assert store.orders == {persisted.id: persisted}
        assert persisted.status is OrderStatus.PENDING_PAYMENT

    assert store.orders == {persisted.id: persisted}
    assert store.commits == 0


@pytest.mark.asyncio
async def test_uow_rolls_back_local_state_when_context_raises() -> None:
    store = MemoryStore()
    order = make_order()
    uow = MemoryUnitOfWork(store)

    with pytest.raises(ValueError, match="abort transaction"):
        async with uow:
            await uow.orders.add(order)
            raise ValueError("abort transaction")

    assert store.orders == {}
    assert store.outbox == []
    assert store.commits == 0


@pytest.mark.asyncio
async def test_uow_commit_publishes_deep_copies_and_counts_commit() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    store = MemoryStore()
    order = make_order()
    message = _message(1, now=now)
    uow = MemoryUnitOfWork(store)

    async with uow:
        await uow.orders.add(order)
        await uow.outbox.add(message)
        await uow.commit()

        persisted_order = store.orders[order.id]
        persisted_message = store.outbox[0]
        assert persisted_order == order
        assert persisted_order is not order
        assert persisted_message == message
        assert persisted_message is not message
        assert store.commits == 1

        order.start_payment()
        message.done = True
        message.payload["order_id"] = "changed-locally"
        assert persisted_order.status is OrderStatus.PENDING_PAYMENT
        assert persisted_message.done is False
        assert persisted_message.payload == {"order_id": "order-099"}

        persisted_order.start_payment()
        persisted_order.mark_payment_failed()
        persisted_message.attempts = 3
        persisted_message.payload["order_id"] = "changed-in-store"
        assert order.status is OrderStatus.PAYMENT_IN_PROGRESS
        assert message.attempts == 0
        assert message.payload == {"order_id": "changed-locally"}


@pytest.mark.asyncio
async def test_uow_can_reenter_and_discards_uncommitted_prior_snapshot() -> None:
    store = MemoryStore()
    first = make_order()
    uncommitted = make_order(
        order_id=UUID("00000000-0000-0000-0000-000000000002"),
        idempotency_key="create-uncommitted",
    )
    second = make_order(
        order_id=UUID("00000000-0000-0000-0000-000000000003"),
        idempotency_key="create-003",
    )
    uow = MemoryUnitOfWork(store)

    async with uow:
        await uow.orders.add(first)
        await uow.commit()
        await uow.orders.add(uncommitted)

    async with uow:
        assert await uow.orders.get(first.id) == first
        assert await uow.orders.get(uncommitted.id) is None
        await uow.orders.add(second)
        await uow.commit()

    assert set(store.orders) == {first.id, second.id}
    assert store.commits == 2
