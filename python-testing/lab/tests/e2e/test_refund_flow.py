from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from order_service.adapters.memory import FrozenClock, SequenceIdGenerator
from order_service.adapters.outbox import PaymentWorker
from order_service.adapters.payment_http import HTTPPaymentGateway
from order_service.adapters.sqlalchemy import SQLAlchemyUnitOfWork
from order_service.api.app import create_app
from order_service.api.dependencies import get_create_order, get_refund_order
from order_service.application.create_order import CreateOrder
from order_service.application.process_payment import ProcessPayment
from order_service.application.refund_order import RefundOrder
from order_service.domain.order import OrderStatus
from order_service.ports.payment import PaymentUncertain
from tests.contract.fake_provider import create_fake_provider

pytestmark = [pytest.mark.e2e, pytest.mark.docker]


@pytest.mark.asyncio(loop_scope="session")
async def test_two_caller_keys_produce_one_effective_provider_refund(
    session_factory,
) -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    order_id, message_id = uuid4(), uuid4()
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    create_order = CreateOrder(
        uow_factory,
        SequenceIdGenerator(order_id, message_id),
        FrozenClock(now),
    )
    provider = create_fake_provider()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=provider),
        base_url="http://payments.test",
    ) as provider_client:
        gateway = HTTPPaymentGateway(provider_client)
        app = create_app()
        app.dependency_overrides[get_create_order] = lambda: create_order
        app.dependency_overrides[get_refund_order] = lambda: RefundOrder(
            uow_factory, gateway
        )
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://orders.test",
                ) as client:
                    created = await client.post(
                        "/orders",
                        headers={"Idempotency-Key": f"create-{order_id}"},
                        json={"amount": "10.00", "currency": "USD"},
                    )
                    assert created.status_code == 201

                    worker = PaymentWorker(
                        uow_factory,
                        ProcessPayment(uow_factory, gateway).execute,
                        FrozenClock(now),
                    )
                    assert await worker.run_once() == 1

                    responses = [
                        await client.post(
                            f"/orders/{order_id}/refunds",
                            headers={"Idempotency-Key": caller_key},
                        )
                        for caller_key in ("caller-refund-001", "caller-refund-002")
                    ]
        finally:
            app.dependency_overrides.clear()

    assert [response.status_code for response in responses] == [202, 202]
    assert [response.json() for response in responses] == [
        {"order_id": str(order_id), "status": "accepted"},
        {"order_id": str(order_id), "status": "accepted"},
    ]
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        persisted = await uow.orders.get(order_id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUNDED
    assert persisted.refund_reference == "refund-001"
    expected_provider_operation = {
        "payment_reference": "pay-001",
        "amount": "10.00",
        "currency": "USD",
        "idempotency_key": f"refund:{order_id}",
    }
    assert provider.state.refund_attempts == [expected_provider_operation]
    assert provider.state.refund_operations == [expected_provider_operation]


@pytest.mark.asyncio(loop_scope="session")
async def test_uncertain_refund_retries_same_provider_operation(
    session_factory,
) -> None:
    now = datetime(2026, 7, 15, tzinfo=UTC)
    order_id, message_id = uuid4(), uuid4()
    uow_factory = lambda: SQLAlchemyUnitOfWork(session_factory)
    create_order = CreateOrder(
        uow_factory,
        SequenceIdGenerator(order_id, message_id),
        FrozenClock(now),
    )
    provider = create_fake_provider(refund_uncertain_once=True)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=provider),
        base_url="http://payments.test",
    ) as provider_client:
        gateway = HTTPPaymentGateway(provider_client)
        app = create_app()
        app.dependency_overrides[get_create_order] = lambda: create_order
        app.dependency_overrides[get_refund_order] = lambda: RefundOrder(
            uow_factory, gateway
        )
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app),
                    base_url="http://orders.test",
                ) as client:
                    created = await client.post(
                        "/orders",
                        headers={"Idempotency-Key": f"create-{order_id}"},
                        json={"amount": "10.00", "currency": "USD"},
                    )
                    assert created.status_code == 201

                    worker = PaymentWorker(
                        uow_factory,
                        ProcessPayment(uow_factory, gateway).execute,
                        FrozenClock(now),
                    )
                    assert await worker.run_once() == 1

                    with pytest.raises(
                        PaymentUncertain,
                        match="refund response lost",
                    ):
                        await client.post(
                            f"/orders/{order_id}/refunds",
                            headers={"Idempotency-Key": "caller-refund-001"},
                        )

                    async with SQLAlchemyUnitOfWork(session_factory) as uow:
                        in_progress = await uow.orders.get(order_id)
                    assert in_progress is not None
                    assert in_progress.status is OrderStatus.REFUND_IN_PROGRESS

                    retry = await client.post(
                        f"/orders/{order_id}/refunds",
                        headers={"Idempotency-Key": "caller-refund-002"},
                    )
        finally:
            app.dependency_overrides.clear()

    assert retry.status_code == 202
    assert retry.json() == {
        "order_id": str(order_id),
        "status": "accepted",
    }
    async with SQLAlchemyUnitOfWork(session_factory) as uow:
        persisted = await uow.orders.get(order_id)
    assert persisted is not None
    assert persisted.status is OrderStatus.REFUNDED
    assert persisted.refund_reference == "refund-001"
    expected_provider_operation = {
        "payment_reference": "pay-001",
        "amount": "10.00",
        "currency": "USD",
        "idempotency_key": f"refund:{order_id}",
    }
    assert provider.state.refund_attempts == [
        expected_provider_operation,
        expected_provider_operation,
    ]
    assert provider.state.refund_operations == [expected_provider_operation]
