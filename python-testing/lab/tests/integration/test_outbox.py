import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from order_service.adapters.sqlalchemy import (
    SQLAlchemyUnitOfWork,
    outbox_messages,
)
from order_service.application.messages import OutboxMessage

pytestmark = [pytest.mark.integration, pytest.mark.docker]


@pytest.mark.asyncio(loop_scope="session")
async def test_two_workers_claim_distinct_messages(session_factory) -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    messages = [
        OutboxMessage(
            id=uuid4(),
            topic="payment_requested",
            aggregate_id=uuid4(),
            payload={"order_id": str(uuid4())},
            occurred_at=now,
            available_at=now,
        )
        for _ in range(2)
    ]
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        for message in messages:
            await uow.outbox.add(message)
        await uow.commit()

    first_uow = SQLAlchemyUnitOfWork(session_factory)
    await first_uow.__aenter__()
    second_started = asyncio.Event()

    async def claim_while_first_transaction_holds_its_lock():
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            second_started.set()
            claimed = await uow.outbox.claim_batch(limit=1, now=now)
            await uow.commit()
            return claimed

    try:
        first = await first_uow.outbox.claim_batch(limit=1, now=now)
        second_task = asyncio.create_task(
            claim_while_first_transaction_holds_its_lock()
        )
        await second_started.wait()
        try:
            second = await asyncio.wait_for(second_task, timeout=2)
        except BaseException:
            second_task.cancel()
            await asyncio.gather(second_task, return_exceptions=True)
            raise
        await first_uow.commit()
    finally:
        await first_uow.__aexit__(None, None, None)

    claimed_ids = [first[0].id, second[0].id]
    assert len(set(claimed_ids)) == 2
    async with session_factory() as session:
        persisted = (
            await session.execute(
                select(
                    outbox_messages.c.id,
                    outbox_messages.c.claimed_at,
                ).where(outbox_messages.c.id.in_(claimed_ids))
            )
        ).all()
    assert len(persisted) == 2
    assert all(row.claimed_at == now for row in persisted)
