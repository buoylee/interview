from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from order_service.adapters.memory import FrozenClock, SequenceIdGenerator
from order_service.adapters.outbox import PaymentWorker
from order_service.adapters.payment_http import HTTPPaymentGateway
from order_service.adapters.sqlalchemy import (
    SQLAlchemyUnitOfWork,
    outbox_messages,
)
from order_service.api.app import create_app
from order_service.api.dependencies import get_create_order
from order_service.application.create_order import CreateOrder
from order_service.application.process_payment import ProcessPayment
from order_service.domain.order import OrderStatus
from tests.contract.fake_provider import create_fake_provider

pytestmark = [pytest.mark.e2e, pytest.mark.docker]


@pytest.mark.asyncio(loop_scope="session")
async def test_http_order_is_paid_by_outbox_worker(session_factory) -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    order_id, message_id = uuid4(), uuid4()
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    create_order = CreateOrder(
        uow_factory,
        SequenceIdGenerator(order_id, message_id),
        FrozenClock(now),
    )
    app = create_app()
    app.dependency_overrides[get_create_order] = lambda: create_order

    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://orders.test",
            ) as client:
                response = await client.post(
                    "/orders",
                    headers={"Idempotency-Key": f"create-{order_id}"},
                    json={"amount": "10.00", "currency": "USD"},
                )
        assert response.status_code == 201
        assert response.json()["id"] == str(order_id)

        provider = create_fake_provider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=provider),
            base_url="http://payments.test",
        ) as provider_client:
            process_payment = ProcessPayment(
                uow_factory, HTTPPaymentGateway(provider_client)
            )
            worker = PaymentWorker(
                uow_factory, process_payment.execute, FrozenClock(now)
            )
            assert await worker.run_once() == 1

        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            order = await uow.orders.get(order_id)
        assert order is not None
        assert order.status is OrderStatus.PAID
        assert order.payment_reference == "pay-001"

        async with session_factory() as session:
            done = await session.scalar(
                select(outbox_messages.c.done).where(
                    outbox_messages.c.id == message_id
                )
            )
        assert done is True
    finally:
        app.dependency_overrides.clear()
