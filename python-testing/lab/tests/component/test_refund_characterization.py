from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from order_service.adapters.memory import (
    MemoryStore,
    MemoryUnitOfWork,
    StubPaymentGateway,
)
from order_service.api.app import create_app
from order_service.api.dependencies import get_legacy_refund
from order_service.application.legacy_refund import LegacyRefund
from order_service.domain.order import Money, Order


PAID_ORDER_ID = UUID("00000000-0000-0000-0000-000000000101")


def _paid_order() -> Order:
    order = Order.create(
        order_id=PAID_ORDER_ID,
        idempotency_key="create-paid-001",
        total=Money(Decimal("10.00"), "USD"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    order.start_payment()
    order.mark_paid("pay-001")
    return order


def _unpaid_order() -> Order:
    return Order.create(
        order_id=PAID_ORDER_ID,
        idempotency_key="create-unpaid-001",
        total=Money(Decimal("10.00"), "USD"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


def _unpaid_order_with_stale_reference() -> Order:
    order = _unpaid_order()
    order.payment_reference = "stale-pay"
    return order


async def _post_refund(
    store: MemoryStore,
    gateway: StubPaymentGateway,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    legacy_refund = LegacyRefund(lambda: MemoryUnitOfWork(store), gateway)
    app = create_app()
    app.dependency_overrides[get_legacy_refund] = lambda: legacy_refund
    transport = httpx.ASGITransport(app=app)
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                return await client.post(
                    f"/orders/{PAID_ORDER_ID}/refunds",
                    headers=headers,
                )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_refund_endpoint_preserves_accepted_response_shape() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})

    response = await _post_refund(
        store,
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "order_id": str(PAID_ORDER_ID),
        "status": "accepted",
    }
    assert gateway.refund_calls == [
        {
            "payment_reference": "pay-001",
            "total": Money(Decimal("10.00"), "USD"),
            "idempotency_key": "caller-attempt-001",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "request_headers",
    [None, {"Idempotency-Key": "   "}],
    ids=["missing", "blank"],
)
async def test_refund_endpoint_rejects_missing_or_blank_idempotency_key(
    request_headers: dict[str, str] | None,
) -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})

    response = await _post_refund(store, gateway, headers=request_headers)

    assert response.status_code == 422
    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_refund_endpoint_maps_missing_order_to_stable_404() -> None:
    gateway = StubPaymentGateway()

    response = await _post_refund(
        MemoryStore(),
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "order not found"}
    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_refund_endpoint_rejects_order_without_captured_payment() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _unpaid_order()})

    response = await _post_refund(
        store,
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "order has no captured payment"}
    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_refund_endpoint_rejects_non_paid_order_with_stale_reference() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(
        orders={PAID_ORDER_ID: _unpaid_order_with_stale_reference()}
    )

    response = await _post_refund(
        store,
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "order has no captured payment"}
    assert gateway.refund_calls == []


def test_unconfigured_refund_dependency_fails_only_when_resolved() -> None:
    app = create_app()

    assert any(route.path == "/orders/{order_id}/refunds" for route in app.routes)
    with pytest.raises(
        RuntimeError, match="LegacyRefund dependency is not configured"
    ):
        get_legacy_refund()


@pytest.mark.asyncio
async def test_caller_request_ids_expose_the_duplicate_refund_behavior() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})
    legacy_refund = LegacyRefund(lambda: MemoryUnitOfWork(store), gateway)

    await legacy_refund.execute(PAID_ORDER_ID, "caller-attempt-001")
    await legacy_refund.execute(PAID_ORDER_ID, "caller-attempt-002")

    assert gateway.refund_calls == [
        {
            "payment_reference": "pay-001",
            "total": Money(Decimal("10.00"), "USD"),
            "idempotency_key": "caller-attempt-001",
        },
        {
            "payment_reference": "pay-001",
            "total": Money(Decimal("10.00"), "USD"),
            "idempotency_key": "caller-attempt-002",
        },
    ]
