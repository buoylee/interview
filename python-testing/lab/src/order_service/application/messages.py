"""Application message contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    idempotency_key: str
    amount: Decimal
    currency: str


@dataclass(slots=True)
class OutboxMessage:
    id: UUID
    topic: str
    aggregate_id: UUID
    payload: dict[str, str]
    occurred_at: datetime
    attempts: int = 0
    available_at: datetime | None = None
    claimed_at: datetime | None = None
    done: bool = False
