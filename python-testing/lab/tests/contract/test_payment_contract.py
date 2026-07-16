from decimal import Decimal
import json
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from order_service.adapters.payment_http import HTTPPaymentGateway
from order_service.domain.order import Money
from order_service.ports.payment import (
    PaymentDeclined,
    PaymentProviderProtocolError,
    PaymentUncertain,
)
from tests.contract.fake_provider import create_fake_provider


ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
TOTAL = Money(Decimal("10.00"), "usd")


@pytest_asyncio.fixture
async def gateway() -> HTTPPaymentGateway:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_fake_provider()),
        base_url="http://provider.test",
    ) as client:
        yield HTTPPaymentGateway(client)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_approved_charge_serializes_request_and_maps_reference(gateway) -> None:
    result = await gateway.charge(
        order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-001"
    )
    assert result.reference == "pay-001"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_decline_maps_reason_to_domain_error(gateway) -> None:
    with pytest.raises(PaymentDeclined, match="insufficient_funds"):
        await gateway.charge(
            order_id=ORDER_ID, total=TOTAL, idempotency_key="decline"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_malformed_success_is_protocol_error(gateway) -> None:
    with pytest.raises(PaymentProviderProtocolError, match="invalid provider response"):
        await gateway.charge(
            order_id=ORDER_ID, total=TOTAL, idempotency_key="malformed"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_server_error_is_protocol_error() -> None:
    async def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server_error), base_url="http://provider.test"
    ) as client:
        with pytest.raises(PaymentProviderProtocolError, match="status 503"):
            await HTTPPaymentGateway(client).charge(
                order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-001"
            )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_timeout_is_uncertain() -> None:
    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout), base_url="http://provider.test"
    ) as client:
        with pytest.raises(PaymentUncertain, match="read timed out"):
            await HTTPPaymentGateway(client).charge(
                order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-001"
            )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_refund_uses_provider_contract(gateway) -> None:
    result = await gateway.refund(
        payment_reference="pay-001", total=TOTAL, idempotency_key="refund-001"
    )
    assert result.reference == "refund-001"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_refund_timeout_is_uncertain() -> None:
    async def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.WriteTimeout("write timed out", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(timeout), base_url="http://provider.test"
    ) as client:
        with pytest.raises(PaymentUncertain, match="write timed out"):
            await HTTPPaymentGateway(client).refund(
                payment_reference="pay-001",
                total=TOTAL,
                idempotency_key="refund-001",
            )


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "expected_path", "expected_body", "expected_key"),
    [
        (
            "charge",
            "/charges",
            {
                "order_id": str(ORDER_ID),
                "amount": "10.00",
                "currency": "USD",
            },
            "charge-exact",
        ),
        (
            "refund",
            "/refunds",
            {
                "payment_reference": "pay-original",
                "amount": "10.00",
                "currency": "USD",
            },
            "refund-exact",
        ),
    ],
)
async def test_request_wire_contract_is_exact(
    method: str,
    expected_path: str,
    expected_body: dict[str, str],
    expected_key: str,
) -> None:
    captured: list[httpx.Request] = []

    async def approve(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200, json={"status": "approved", "reference": "provider-ref"}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(approve), base_url="http://provider.test"
    ) as client:
        gateway = HTTPPaymentGateway(client)
        if method == "charge":
            await gateway.charge(
                order_id=ORDER_ID, total=TOTAL, idempotency_key=expected_key
            )
        else:
            await gateway.refund(
                payment_reference="pay-original",
                total=TOTAL,
                idempotency_key=expected_key,
            )

    assert len(captured) == 1
    assert captured[0].url.path == expected_path
    assert captured[0].headers["Idempotency-Key"] == expected_key
    assert json.loads(captured[0].content) == expected_body


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "error"),
    [
        ("charge", httpx.ConnectError("connection refused")),
        ("charge", httpx.NetworkError("network unavailable")),
        ("refund", httpx.RemoteProtocolError("peer disconnected")),
    ],
)
async def test_request_errors_are_uncertain(operation: str, error: Exception) -> None:
    async def fail(request: httpx.Request) -> httpx.Response:
        raise error

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(fail), base_url="http://provider.test"
    ) as client:
        gateway = HTTPPaymentGateway(client)
        with pytest.raises(PaymentUncertain, match=str(error)):
            if operation == "charge":
                await gateway.charge(
                    order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-error"
                )
            else:
                await gateway.refund(
                    payment_reference="pay-001",
                    total=TOTAL,
                    idempotency_key="refund-error",
                )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_non_json_server_error_preserves_status_diagnostic() -> None:
    async def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, content=b"upstream reset")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server_error), base_url="http://provider.test"
    ) as client:
        with pytest.raises(PaymentProviderProtocolError, match="status 502"):
            await HTTPPaymentGateway(client).charge(
                order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-001"
            )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_non_json_402_is_still_a_definitive_decline() -> None:
    async def decline(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, content=b"declined")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(decline), base_url="http://provider.test"
    ) as client:
        with pytest.raises(PaymentDeclined, match="payment declined"):
            await HTTPPaymentGateway(client).charge(
                order_id=ORDER_ID, total=TOTAL, idempotency_key="charge-001"
            )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_fake_provider_replays_same_refund_operation_by_key() -> None:
    provider = create_fake_provider()
    request = {
        "headers": {"Idempotency-Key": "refund-stable"},
        "json": {
            "payment_reference": "pay-001",
            "amount": "10.00",
            "currency": "USD",
        },
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=provider),
        base_url="http://provider.test",
    ) as client:
        first = await client.post("/refunds", **request)
        replay = await client.post("/refunds", **request)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json() == {
        "status": "approved",
        "reference": "refund-001",
    }
    expected_attempt = {
        "payment_reference": "pay-001",
        "amount": "10.00",
        "currency": "USD",
        "idempotency_key": "refund-stable",
    }
    assert provider.state.refund_attempts == [expected_attempt, expected_attempt]
    assert provider.state.refund_operations == [expected_attempt]


@pytest.mark.contract
@pytest.mark.asyncio
async def test_fake_provider_rejects_same_key_with_different_refund_body() -> None:
    provider = create_fake_provider()
    headers = {"Idempotency-Key": "refund-stable"}
    original = {
        "payment_reference": "pay-001",
        "amount": "10.00",
        "currency": "USD",
    }
    conflicting = {**original, "amount": "11.00"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=provider),
        base_url="http://provider.test",
    ) as client:
        first = await client.post("/refunds", headers=headers, json=original)
        conflict = await client.post(
            "/refunds", headers=headers, json=conflicting
        )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "idempotency key reused with different refund body"
    }
    assert len(provider.state.refund_attempts) == 2
    assert len(provider.state.refund_operations) == 1
