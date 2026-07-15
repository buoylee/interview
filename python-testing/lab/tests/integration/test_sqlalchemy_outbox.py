from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from order_service.adapters.sqlalchemy import (
    SQLAlchemyOutboxRepository,
    SQLAlchemyUnitOfWork,
    outbox_messages,
)
from order_service.application.messages import OutboxMessage

pytestmark = [pytest.mark.integration, pytest.mark.docker]
NOW = datetime(2026, 7, 15, tzinfo=UTC)


def message(number: int, **overrides) -> OutboxMessage:
    values = {
        "id": UUID(int=number),
        "topic": "payment_requested",
        "aggregate_id": UUID(int=99),
        "payload": {"order_id": "99"},
        "occurred_at": NOW,
    }
    values.update(overrides)
    return OutboxMessage(**values)


@pytest.mark.asyncio(loop_scope="session")
async def test_add_and_claim_map_full_outbox_row(session_factory) -> None:
    original = message(1, attempts=2, available_at=NOW)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(original)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.outbox.claim_batch(limit=1, now=NOW) == [
            message(1, attempts=2, available_at=NOW, claimed_at=NOW)
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_committed_claim_persists_and_is_not_immediately_reclaimable(
    session_factory,
) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(message(8))
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as claiming_uow:
        claimed = await claiming_uow.outbox.claim_batch(limit=1, now=NOW)
        await claiming_uow.commit()
    assert claimed == [message(8, claimed_at=NOW)]
    async with SQLAlchemyUnitOfWork(session_factory) as fresh_uow:
        assert await fresh_uow.outbox.claim_batch(
            limit=1, now=NOW + timedelta(seconds=29)
        ) == []
    async with session_factory() as fresh_session:
        claimed_at = await fresh_session.scalar(
            select(outbox_messages.c.claimed_at).where(
                outbox_messages.c.id == UUID(int=8)
            )
        )
    assert claimed_at == NOW


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_filters_due_future_done_and_lease_boundary(session_factory) -> None:
    messages = [
        message(1),
        message(2, available_at=NOW),
        message(3, available_at=NOW + timedelta(microseconds=1)),
        message(4, done=True),
        message(5, claimed_at=NOW - timedelta(seconds=29, microseconds=999999)),
        message(6, claimed_at=NOW - timedelta(seconds=30)),
        message(7),
    ]
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        for item in messages:
            await uow.outbox.add(item)
        await uow.commit()
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        claimed = await uow.outbox.claim_batch(limit=3, now=NOW)
    assert [item.id for item in claimed] == [UUID(int=1), UUID(int=2), UUID(int=6)]
    assert all(item.claimed_at == NOW for item in claimed)


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_limit_zero_matches_memory_contract(session_factory) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(message(1))
        assert await uow.outbox.claim_batch(limit=0, now=NOW) == []


@pytest.mark.asyncio(loop_scope="session")
async def test_claim_negative_limit_matches_memory_contract(session_factory) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(message(1))
        with pytest.raises(ValueError, match=r"^limit must not be negative$"):
            await uow.outbox.claim_batch(limit=-1, now=NOW)


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_done_and_failed_transitions_persist(session_factory) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(message(1, claimed_at=NOW))
        await uow.outbox.add(message(2, claimed_at=NOW))
        await uow.commit()
    retry_at = NOW + timedelta(seconds=10)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.mark_done(UUID(int=1))
        await uow.outbox.mark_failed(UUID(int=2), available_at=retry_at)
        await uow.commit()
    async with session_factory() as session:
        rows = (await session.execute(select(outbox_messages).order_by(outbox_messages.c.id))).mappings().all()
    assert rows[0]["done"] is True and rows[0]["claimed_at"] is None
    assert rows[1]["attempts"] == 1
    assert rows[1]["available_at"] == retry_at and rows[1]["claimed_at"] is None


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_done_raises_key_error_for_missing_id(session_factory) -> None:
    missing = UUID(int=404)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        with pytest.raises(KeyError, match=str(missing)):
            await uow.outbox.mark_done(missing)


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_failed_raises_key_error_for_missing_id(session_factory) -> None:
    missing = UUID(int=404)
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        with pytest.raises(KeyError, match=str(missing)):
            await uow.outbox.mark_failed(missing, available_at=NOW)


@pytest.mark.asyncio(loop_scope="session")
async def test_skip_locked_skips_row_locked_by_other_transaction(session_factory) -> None:
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        await uow.outbox.add(message(1))
        await uow.outbox.add(message(2))
        await uow.commit()
    async with session_factory() as locking_session:
        await locking_session.execute(
            select(outbox_messages).where(outbox_messages.c.id == UUID(int=1)).with_for_update()
        )
        async with session_factory() as claiming_session:
            repository = SQLAlchemyOutboxRepository(claiming_session)
            claimed = await repository.claim_batch(limit=2, now=NOW)
            assert [item.id for item in claimed] == [UUID(int=2)]
            await claiming_session.rollback()
        await locking_session.rollback()
