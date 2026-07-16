from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from decimal import Decimal
from importlib import import_module
from inspect import signature
from typing import get_args, get_origin
from uuid import UUID

import pytest

from order_service.application.messages import CreateOrderCommand, OutboxMessage


def test_application_messages_have_stable_fields() -> None:
    messages = import_module("order_service.application.messages")

    assert [field.name for field in fields(messages.CreateOrderCommand)] == [
        "idempotency_key",
        "amount",
        "currency",
    ]
    assert [field.name for field in fields(messages.OutboxMessage)] == [
        "id",
        "topic",
        "aggregate_id",
        "payload",
        "occurred_at",
        "attempts",
        "available_at",
        "claimed_at",
        "done",
    ]


def test_public_ports_keep_later_adapter_signatures() -> None:
    system = import_module("order_service.ports.system")
    uow = import_module("order_service.ports.uow")

    assert str(signature(system.Clock.now)) == "(self) -> datetime.datetime"
    assert str(signature(system.IdGenerator.new)) == "(self) -> uuid.UUID"
    assert str(signature(uow.OrderRepository.get)) == (
        "(self, order_id: uuid.UUID) -> order_service.domain.order.Order | None"
    )
    assert str(signature(uow.OrderRepository.get_by_idempotency_key)) == (
        "(self, key: str) -> order_service.domain.order.Order | None"
    )
    assert str(signature(uow.OrderRepository.add)) == (
        "(self, order: order_service.domain.order.Order) -> None"
    )
    assert str(signature(uow.OrderRepository.save)) == (
        "(self, order: order_service.domain.order.Order) -> None"
    )
    assert str(signature(uow.OutboxRepository.add)) == (
        "(self, message: order_service.application.messages.OutboxMessage) -> None"
    )
    assert str(signature(uow.OutboxRepository.claim_batch)) == (
        "(self, *, limit: int, now: datetime.datetime) -> list[order_service.application.messages.OutboxMessage]"
    )
    assert str(signature(uow.OutboxRepository.mark_done)) == (
        "(self, message_id: uuid.UUID) -> None"
    )
    assert str(signature(uow.OutboxRepository.mark_failed)) == (
        "(self, message_id: uuid.UUID, *, available_at: datetime.datetime) -> None"
    )
    assert str(signature(uow.UnitOfWork.__aenter__)) == (
        "(self) -> 'UnitOfWork'"
    )
    assert str(signature(uow.UnitOfWork.__aexit__)) == (
        "(self, exc_type, exc, traceback) -> None"
    )
    assert str(signature(uow.UnitOfWork.commit)) == "(self) -> None"
    assert get_origin(uow.UnitOfWorkFactory) is Callable
    assert get_args(uow.UnitOfWorkFactory) == ([], uow.UnitOfWork)


def test_create_order_command_is_a_frozen_slotted_value() -> None:
    command = CreateOrderCommand("create-001", Decimal("10.00"), "USD")

    assert (
        command.idempotency_key,
        command.amount,
        command.currency,
    ) == ("create-001", Decimal("10.00"), "USD")
    assert not hasattr(command, "__dict__")
    with pytest.raises(FrozenInstanceError):
        command.currency = "EUR"


def test_outbox_message_has_mutable_delivery_defaults_and_slots() -> None:
    occurred_at = datetime(2026, 7, 15, tzinfo=UTC)
    message = OutboxMessage(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        topic="payment_requested",
        aggregate_id=UUID("00000000-0000-0000-0000-000000000002"),
        payload={"order_id": "order-001"},
        occurred_at=occurred_at,
    )

    assert (
        message.attempts,
        message.available_at,
        message.claimed_at,
        message.done,
    ) == (0, None, None, False)
    assert not hasattr(message, "__dict__")

    message.attempts = 1
    message.claimed_at = occurred_at
    message.done = True

    assert (message.attempts, message.claimed_at, message.done) == (
        1,
        occurred_at,
        True,
    )
