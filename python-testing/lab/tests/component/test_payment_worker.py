import asyncio
import tracemalloc
from datetime import UTC, datetime
from uuid import UUID

import pytest

from order_service.adapters.memory import (
    FrozenClock,
    ManualClock,
    MemoryStore,
    MemoryUnitOfWork,
)
from order_service.adapters.outbox import PaymentWorker
from order_service.application.messages import OutboxMessage


def make_outbox_message(*, available_at: datetime) -> OutboxMessage:
    order_id = UUID("00000000-0000-0000-0000-000000000001")
    return OutboxMessage(
        id=UUID("00000000-0000-0000-0000-000000000002"),
        topic="payment_requested",
        aggregate_id=order_id,
        payload={"order_id": str(order_id)},
        occurred_at=available_at,
        available_at=available_at,
    )


@pytest.mark.asyncio
async def test_worker_marks_successful_message_done() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    processed: list[UUID] = []

    async def process(order_id: UUID) -> None:
        processed.append(order_id)

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, FrozenClock(now))
    assert await worker.run_once(limit=10) == 1
    assert processed == [message.aggregate_id]
    assert store.outbox[0].done is True


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, -1])
async def test_worker_rejects_non_positive_limit_before_opening_uow(limit: int) -> None:
    opened = False

    def uow_factory():
        nonlocal opened
        opened = True
        raise AssertionError("invalid input must not open a unit of work")

    async def process(order_id: UUID) -> None:
        raise AssertionError("invalid input must not process a message")

    worker = PaymentWorker(
        uow_factory,
        process,
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )
    with pytest.raises(ValueError, match=r"^limit must be positive$"):
        await worker.run_once(limit=limit)
    assert opened is False


@pytest.mark.asyncio
async def test_failed_message_retries_only_after_backoff() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    clock = ManualClock(now)
    outcomes = iter([RuntimeError("temporary"), None])

    async def process(order_id: UUID) -> None:
        outcome = next(outcomes)
        if outcome is not None:
            raise outcome

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, clock)
    assert await worker.run_once() == 1
    assert store.outbox[0].attempts == 1
    assert store.outbox[0].available_at == now.replace(second=2)
    assert await worker.run_once() == 0
    clock.advance(seconds=1)
    assert await worker.run_once() == 0
    clock.advance(seconds=1)
    assert await worker.run_once() == 1
    assert store.outbox[0].done is True


@pytest.mark.asyncio
async def test_retry_backoff_is_capped_at_sixty_seconds() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    message.attempts = 6
    store = MemoryStore(outbox=[message])

    async def fail(order_id: UUID) -> None:
        raise RuntimeError("still unavailable")

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), fail, FrozenClock(now))
    assert await worker.run_once() == 1
    assert store.outbox[0].attempts == 7
    assert store.outbox[0].available_at == now.replace(minute=1)


@pytest.mark.asyncio
async def test_absurd_attempt_count_is_capped_before_exponentiation() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    message.attempts = 10_000_000
    store = MemoryStore(outbox=[message])

    async def fail(order_id: UUID) -> None:
        raise RuntimeError("still unavailable")

    tracemalloc.start()
    try:
        worker = PaymentWorker(
            lambda: MemoryUnitOfWork(store), fail, FrozenClock(now)
        )
        assert await worker.run_once() == 1
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert peak < 500_000
    assert store.outbox[0].attempts == 10_000_001
    assert store.outbox[0].available_at == now.replace(minute=1)


@pytest.mark.asyncio
async def test_worker_propagates_cancellation_and_recovers_expired_lease() -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    message = make_outbox_message(available_at=now)
    store = MemoryStore(outbox=[message])
    clock = ManualClock(now)
    started = asyncio.Event()
    never = asyncio.Event()

    async def process(order_id: UUID) -> None:
        started.set()
        await never.wait()

    worker = PaymentWorker(lambda: MemoryUnitOfWork(store), process, clock)
    task = asyncio.create_task(worker.run_once())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
    assert store.outbox[0].claimed_at == now

    recovered: list[UUID] = []
    clock.advance(seconds=31)

    async def recover(order_id: UUID) -> None:
        recovered.append(order_id)

    recovery_worker = PaymentWorker(
        lambda: MemoryUnitOfWork(store), recover, clock
    )
    assert await recovery_worker.run_once() == 1
    assert recovered == [message.aggregate_id]
    assert store.outbox[0].done is True
