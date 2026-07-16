from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from order_service.adapters.memory import (
    FrozenClock,
    MemoryStore,
    MemoryUnitOfWork,
    SequenceIdGenerator,
)
from order_service.api.app import create_app
from order_service.api.dependencies import get_create_order
from order_service.api.schemas import CreateOrderRequest, OrderResponse
from order_service.application.create_order import CreateOrder


def test_api_symbols_are_importable() -> None:
    assert callable(create_app)
    assert callable(get_create_order)
    assert CreateOrderRequest.__name__ == "CreateOrderRequest"
    assert OrderResponse.__name__ == "OrderResponse"


def test_unconfigured_dependency_fails_clearly() -> None:
    with pytest.raises(RuntimeError, match="CreateOrder dependency is not configured"):
        get_create_order()


@pytest.fixture
def use_case() -> CreateOrder:
    store = MemoryStore()
    return CreateOrder(
        lambda: MemoryUnitOfWork(store),
        SequenceIdGenerator(
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ),
        FrozenClock(datetime(2026, 7, 15, tzinfo=UTC)),
    )


@contextmanager
def configured_app(use_case: CreateOrder) -> Iterator[FastAPI]:
    application = create_app()
    application.dependency_overrides[get_create_order] = lambda: use_case
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
def app(use_case: CreateOrder) -> Iterator[FastAPI]:
    with configured_app(use_case) as application:
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as value:
            yield value


def test_app_exposes_contractual_metadata_and_route() -> None:
    application = create_app()
    assert application.title == "Order Service Testing Lab"
    assert application.version == "1.0.0"
    assert any(route.path == "/orders" for route in application.routes)


@pytest.mark.asyncio
async def test_lifespan_marks_ready_only_inside_context() -> None:
    application = create_app()
    assert getattr(application.state, "ready", False) is False
    async with application.router.lifespan_context(application):
        assert application.state.ready is True
    assert application.state.ready is False


@pytest.mark.asyncio
async def test_lifespan_clears_ready_when_context_body_raises() -> None:
    application = create_app()
    with pytest.raises(RuntimeError, match="lifespan sentinel"):
        async with application.router.lifespan_context(application):
            assert application.state.ready is True
            raise RuntimeError("lifespan sentinel")
    assert application.state.ready is False


@pytest.mark.asyncio
async def test_asgi_transport_does_not_own_lifespan(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test"):
        assert getattr(app.state, "ready", False) is False


@pytest.mark.asyncio
async def test_create_order_returns_public_contract(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/orders",
        headers={"Idempotency-Key": "create-001"},
        json={"amount": "10.00", "currency": "usd"},
    )
    assert response.status_code == 201
    assert response.json() == {
        "id": "00000000-0000-0000-0000-000000000001",
        "status": "pending_payment",
        "amount": "10.00",
        "currency": "USD",
        "version": 1,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({}, {"amount": "10.00", "currency": "USD"}),
        ({"Idempotency-Key": "   "}, {"amount": "10.00", "currency": "USD"}),
        ({"Idempotency-Key": "create-001"}, {"amount": "0", "currency": "USD"}),
        ({"Idempotency-Key": "create-001"}, {"amount": "10.00", "currency": "US1"}),
    ],
    ids=["missing-header", "blank-header", "zero-amount", "invalid-currency"],
)
async def test_invalid_http_input_is_rejected_with_422(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    body: dict[str, str],
) -> None:
    response = await client.post("/orders", headers=headers, json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_key_returns_same_complete_order_without_more_ids(
    client: httpx.AsyncClient,
) -> None:
    request = {
        "headers": {"Idempotency-Key": "create-001"},
        "json": {"amount": "10.00", "currency": "usd"},
    }
    first = await client.post("/orders", **request)
    second = await client.post("/orders", **request)
    assert first.status_code == second.status_code == 201
    assert second.json() == first.json()


def test_configured_app_clears_override_when_context_body_raises(
    use_case: CreateOrder,
) -> None:
    application: FastAPI | None = None
    with pytest.raises(RuntimeError, match="override sentinel"):
        with configured_app(use_case) as application:
            assert get_create_order in application.dependency_overrides
            raise RuntimeError("override sentinel")
    assert application is not None
    assert application.dependency_overrides == {}
