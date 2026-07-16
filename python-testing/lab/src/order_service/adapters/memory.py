"""Deterministic in-memory application adapters."""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from order_service.application.messages import OutboxMessage
from order_service.domain.order import Order
from order_service.ports.payment import PaymentResult


@dataclass
class MemoryStore:
    orders: dict[UUID, Order] = field(default_factory=dict)
    outbox: list[OutboxMessage] = field(default_factory=list)
    commits: int = 0


class MemoryOrderRepository:
    def __init__(self, orders: dict[UUID, Order]) -> None:
        self._orders = orders

    async def get(self, order_id: UUID) -> Order | None:
        return self._orders.get(order_id)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        return next(
            (
                order
                for order in self._orders.values()
                if order.idempotency_key == key
            ),
            None,
        )

    async def add(self, order: Order) -> None:
        self._orders[order.id] = order

    async def save(self, order: Order) -> None:
        self._orders[order.id] = order


class MemoryOutboxRepository:
    def __init__(self, messages: list[OutboxMessage]) -> None:
        self._messages = messages

    async def add(self, message: OutboxMessage) -> None:
        self._messages.append(message)

    async def claim_batch(
        self, *, limit: int, now: datetime
    ) -> list[OutboxMessage]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []

        eligible: list[OutboxMessage] = []
        for message in self._messages:
            due = message.available_at is None or message.available_at <= now
            lease_available = (
                message.claimed_at is None
                or message.claimed_at <= now - timedelta(seconds=30)
            )
            if not message.done and lease_available and due:
                eligible.append(message)

        claimed = sorted(
            eligible,
            key=lambda message: (message.occurred_at, message.id),
        )[:limit]
        for message in claimed:
            message.claimed_at = now
        return claimed

    async def mark_done(self, message_id: UUID) -> None:
        message = self._get(message_id)
        message.done = True
        message.claimed_at = None

    async def mark_failed(
        self, message_id: UUID, *, available_at: datetime
    ) -> None:
        message = self._get(message_id)
        message.attempts += 1
        message.available_at = available_at
        message.claimed_at = None

    def _get(self, message_id: UUID) -> OutboxMessage:
        try:
            return next(
                message for message in self._messages if message.id == message_id
            )
        except StopIteration as exc:
            raise KeyError(message_id) from exc


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    async def __aenter__(self) -> "MemoryUnitOfWork":
        self._orders = deepcopy(self._store.orders)
        self._outbox = deepcopy(self._store.outbox)
        self.orders = MemoryOrderRepository(self._orders)
        self.outbox = MemoryOutboxRepository(self._outbox)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self._store.orders = deepcopy(self._orders)
        self._store.outbox = deepcopy(self._outbox)
        self._store.commits += 1


@dataclass(frozen=True)
class FrozenClock:
    value: datetime

    def now(self) -> datetime:
        return self.value


@dataclass
class ManualClock:
    value: datetime

    def now(self) -> datetime:
        return self.value

    def advance(self, *, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class SequenceIdGenerator:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)

    def new(self) -> UUID:
        try:
            return next(self._values)
        except StopIteration as exc:
            raise RuntimeError("no IDs remaining") from exc


class StubPaymentGateway:
    def __init__(
        self,
        *,
        result: PaymentResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or PaymentResult("pay-stub")
        self.error = error
        self.charge_calls: list[dict[str, object]] = []
        self.refund_calls: list[dict[str, object]] = []

    async def charge(self, **kwargs) -> PaymentResult:
        self.charge_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result

    async def refund(self, **kwargs) -> PaymentResult:
        self.refund_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result
