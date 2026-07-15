from copy import deepcopy

import pytest
from pydantic import ValidationError

from order_contracts.inbound.payment_webhook import PaymentSucceeded, PaymentWebhookEnvelope


def succeeded_payload() -> dict[str, object]:
    return {
        "event_id": "evt_0123456789ab",
        "schema_version": 1,
        "payload": {
            "event_type": "payment.succeeded",
            "provider_reference": "pay_demo_001",
            "order_id": "ord_0123456789ab",
            "paid_amount": {"amount": "24.60", "currency": "USD"},
            "occurred_at": "2026-07-15T12:30:00Z",
        },
    }


def test_discriminator_selects_succeeded_payload() -> None:
    envelope = PaymentWebhookEnvelope.model_validate(succeeded_payload())
    assert isinstance(envelope.payload, PaymentSucceeded)


def test_unknown_event_type_has_stable_union_error() -> None:
    payload = succeeded_payload()
    payload["payload"]["event_type"] = "payment.refunded"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "union_tag_invalid"
    assert error["loc"] == ("payload",)


def test_naive_datetime_is_rejected() -> None:
    payload = deepcopy(succeeded_payload())
    payload["payload"]["occurred_at"] = "2026-07-15T12:30:00"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "timezone_aware"


def test_failed_payload_requires_failure_code() -> None:
    payload = succeeded_payload()
    payload["payload"] = {
        "event_type": "payment.failed",
        "provider_reference": "pay_demo_002",
        "order_id": "ord_0123456789ab",
        "occurred_at": "2026-07-15T12:30:00Z",
    }
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "missing"
