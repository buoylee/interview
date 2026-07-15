"""Persistence and unit-of-work ports."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, TypeAlias
from uuid import UUID

from order_service.application.messages import OutboxMessage
from order_service.domain.order import Order


class OrderRepository(Protocol):
    async def get(self, order_id: UUID) -> Order | None: ...

    async def get_by_idempotency_key(self, key: str) -> Order | None: ...

    async def add(self, order: Order) -> None: ...

    async def save(self, order: Order) -> None: ...


class OutboxRepository(Protocol):
    async def add(self, message: OutboxMessage) -> None: ...

    async def claim_batch(
        self, *, limit: int, now: datetime
    ) -> list[OutboxMessage]: ...

    async def mark_done(self, message_id: UUID) -> None: ...

    async def mark_failed(
        self, message_id: UUID, *, available_at: datetime
    ) -> None: ...


class UnitOfWork(Protocol):
    orders: OrderRepository
    outbox: OutboxRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]
