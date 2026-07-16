"""Explicit SQLAlchemy Core mappings for the Postgres adapter."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CHAR,
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    and_,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from order_service.application.messages import OutboxMessage
from order_service.domain.order import Money, Order, OrderStatus

metadata = MetaData()
orders = Table(
    "orders",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column("amount", Numeric(18, 2), nullable=False),
    Column("currency", CHAR(3), nullable=False),
    Column("status", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payment_reference", Text),
    Column("refund_reference", Text),
    Column("version", Integer, nullable=False),
)
outbox_messages = Table(
    "outbox_messages",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("topic", Text, nullable=False),
    Column("aggregate_id", PG_UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
    Column("available_at", DateTime(timezone=True)),
    Column("claimed_at", DateTime(timezone=True)),
    Column("done", Boolean, nullable=False, default=False),
)


class ConcurrentOrderUpdate(RuntimeError):
    """The stored order version no longer matches the caller's version."""


class SQLAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> None:
        await self._session.execute(insert(orders).values(**_order_values(order)))

    async def get(self, order_id: UUID) -> Order | None:
        row = (await self._session.execute(select(orders).where(orders.c.id == order_id))).mappings().one_or_none()
        return None if row is None else _order_from_row(row)

    async def get_by_idempotency_key(self, key: str) -> Order | None:
        row = (
            await self._session.execute(
                select(orders).where(orders.c.idempotency_key == key)
            )
        ).mappings().one_or_none()
        return None if row is None else _order_from_row(row)

    async def save(self, order: Order) -> None:
        expected = order.version - 1
        result = await self._session.execute(
            update(orders)
            .where(and_(orders.c.id == order.id, orders.c.version == expected))
            .values(**_order_values(order))
        )
        if result.rowcount != 1:
            raise ConcurrentOrderUpdate(order.id)


class SQLAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: OutboxMessage) -> None:
        await self._session.execute(insert(outbox_messages).values(**_message_values(message)))

    async def claim_batch(self, *, limit: int, now: datetime) -> list[OutboxMessage]:
        if limit < 0:
            raise ValueError("limit must not be negative")
        if limit == 0:
            return []
        lease_boundary = now - timedelta(seconds=30)
        rows = (
            await self._session.execute(
                select(outbox_messages)
                .where(
                    and_(
                        outbox_messages.c.done.is_(False),
                        or_(
                            outbox_messages.c.available_at.is_(None),
                            outbox_messages.c.available_at <= now,
                        ),
                        or_(
                            outbox_messages.c.claimed_at.is_(None),
                            outbox_messages.c.claimed_at <= lease_boundary,
                        ),
                    )
                )
                .order_by(outbox_messages.c.occurred_at, outbox_messages.c.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).mappings().all()
        ids = [row["id"] for row in rows]
        if ids:
            await self._session.execute(
                update(outbox_messages)
                .where(outbox_messages.c.id.in_(ids))
                .values(claimed_at=now)
            )
        return [_message_from_row(row, claimed_at=now) for row in rows]

    async def mark_done(self, message_id: UUID) -> None:
        result = await self._session.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(done=True, claimed_at=None)
        )
        if result.rowcount != 1:
            raise KeyError(message_id)

    async def mark_failed(self, message_id: UUID, *, available_at: datetime) -> None:
        result = await self._session.execute(
            update(outbox_messages)
            .where(outbox_messages.c.id == message_id)
            .values(
                attempts=outbox_messages.c.attempts + 1,
                available_at=available_at,
                claimed_at=None,
            )
        )
        if result.rowcount != 1:
            raise KeyError(message_id)


class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        self.session = self._session_factory()
        self.orders = SQLAlchemyOrderRepository(self.session)
        self.outbox = SQLAlchemyOutboxRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        try:
            await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()


def _order_values(order: Order) -> dict[str, object]:
    return {
        "id": order.id,
        "idempotency_key": order.idempotency_key,
        "amount": order.total.amount,
        "currency": order.total.currency,
        "status": order.status.value,
        "created_at": order.created_at,
        "payment_reference": order.payment_reference,
        "refund_reference": order.refund_reference,
        "version": order.version,
    }


def _order_from_row(row) -> Order:
    return Order(
        id=row["id"],
        idempotency_key=row["idempotency_key"],
        total=Money(row["amount"], row["currency"]),
        status=OrderStatus(row["status"]),
        created_at=row["created_at"],
        payment_reference=row["payment_reference"],
        refund_reference=row["refund_reference"],
        version=row["version"],
    )


def _message_values(message: OutboxMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "topic": message.topic,
        "aggregate_id": message.aggregate_id,
        "payload": message.payload,
        "occurred_at": message.occurred_at,
        "attempts": message.attempts,
        "available_at": message.available_at,
        "claimed_at": message.claimed_at,
        "done": message.done,
    }


def _message_from_row(row, *, claimed_at: datetime | None = None) -> OutboxMessage:
    return OutboxMessage(
        id=row["id"],
        topic=row["topic"],
        aggregate_id=row["aggregate_id"],
        payload=row["payload"],
        occurred_at=row["occurred_at"],
        attempts=row["attempts"],
        available_at=row["available_at"],
        claimed_at=claimed_at if claimed_at is not None else row["claimed_at"],
        done=row["done"],
    )
