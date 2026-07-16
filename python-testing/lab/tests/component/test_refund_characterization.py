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
from order_service.api.dependencies import get_refund_order
from order_service.application.refund_order import RefundOrder
from order_service.domain.order import Money, Order
from order_service.ports.payment import PaymentDeclined


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


def _paid_order_without_reference() -> Order:
    order = _paid_order()
    order.payment_reference = None
    return order


async def _post_refund(
    store: MemoryStore,
    gateway: StubPaymentGateway,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    refund_order = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)
    app = create_app()
    app.dependency_overrides[get_refund_order] = lambda: refund_order
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
            "idempotency_key": f"refund:{PAID_ORDER_ID}",
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


@pytest.mark.asyncio
async def test_refund_endpoint_rejects_paid_order_without_reference_before_commit() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(
        orders={PAID_ORDER_ID: _paid_order_without_reference()}
    )

    response = await _post_refund(
        store,
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "order has no captured payment"}
    assert store.orders[PAID_ORDER_ID].status.value == "paid"
    assert store.commits == 0
    assert gateway.refund_calls == []


@pytest.mark.asyncio
async def test_refund_endpoint_maps_definitive_decline_to_stable_409() -> None:
    gateway = StubPaymentGateway(error=PaymentDeclined("provider rejected"))
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})

    response = await _post_refund(
        store,
        gateway,
        headers={"Idempotency-Key": "caller-attempt-001"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "refund declined"}
    assert store.orders[PAID_ORDER_ID].status.value == "paid"
    assert store.commits == 2


def test_unconfigured_refund_dependency_fails_only_when_resolved() -> None:
    app = create_app()

    assert any(route.path == "/orders/{order_id}/refunds" for route in app.routes)
    with pytest.raises(
        RuntimeError, match="RefundOrder dependency is not configured"
    ):
        get_refund_order()


@pytest.mark.asyncio
async def test_caller_request_ids_do_not_control_provider_idempotency() -> None:
    gateway = StubPaymentGateway()
    store = MemoryStore(orders={PAID_ORDER_ID: _paid_order()})
    refund_order = RefundOrder(lambda: MemoryUnitOfWork(store), gateway)

    await refund_order.execute(PAID_ORDER_ID)
    await refund_order.execute(PAID_ORDER_ID)

    assert gateway.refund_calls == [
        {
            "payment_reference": "pay-001",
            "total": Money(Decimal("10.00"), "USD"),
            "idempotency_key": f"refund:{PAID_ORDER_ID}",
        },
    ]
