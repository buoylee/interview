"""Async outbox worker adapter."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from order_service.ports.system import Clock
from order_service.ports.uow import UnitOfWorkFactory


class PaymentWorker:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        process_payment: Callable[[UUID], Awaitable[object]],
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._process_payment = process_payment
        self._clock = clock

    async def run_once(self, *, limit: int = 10) -> int:
        if limit <= 0:
            raise ValueError("limit must be positive")
        now = self._clock.now()
        async with self._uow_factory() as uow:
            messages = await uow.outbox.claim_batch(limit=limit, now=now)
            await uow.commit()

        for message in messages:
            try:
                await self._process_payment(message.aggregate_id)
            except Exception:
                delay = min(2 ** min(message.attempts + 1, 6), 60)
                async with self._uow_factory() as uow:
                    await uow.outbox.mark_failed(
                        message.id,
                        available_at=self._clock.now()
                        + timedelta(seconds=delay),
                    )
                    await uow.commit()
            else:
                async with self._uow_factory() as uow:
                    await uow.outbox.mark_done(message.id)
                    await uow.commit()
        return len(messages)
