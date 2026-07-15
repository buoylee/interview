from copy import deepcopy
import hashlib
import hmac
import json

import pytest
from pydantic import SecretStr, ValidationError

from order_contracts.adapters import InvalidWebhookSignature, parse_payment_webhook
from order_contracts.inbound.payment_webhook import (
    PaymentFailed,
    PaymentSucceeded,
    PaymentWebhookEnvelope,
)


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


def failed_payload() -> dict[str, object]:
    return {
        "event_id": "evt_0123456789ab",
        "schema_version": 1,
        "payload": {
            "event_type": "payment.failed",
            "provider_reference": "pay_demo_002",
            "order_id": "ord_0123456789ab",
            "failure_code": "CARD_DECLINED",
            "occurred_at": "2026-07-15T12:30:00Z",
        },
    }


def test_discriminator_selects_succeeded_payload() -> None:
    envelope = PaymentWebhookEnvelope.model_validate(succeeded_payload())
    assert isinstance(envelope.payload, PaymentSucceeded)


def test_discriminator_selects_failed_payload() -> None:
    envelope = PaymentWebhookEnvelope.model_validate(failed_payload())
    assert isinstance(envelope.payload, PaymentFailed)


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
    error = caught.value.errors()[0]
    assert error["type"] == "timezone_aware"
    assert error["loc"] == ("payload", "payment.succeeded", "occurred_at")


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
    error = caught.value.errors()[0]
    assert error["type"] == "missing"
    assert error["loc"] == ("payload", "payment.failed", "failure_code")


@pytest.mark.parametrize("schema_version", [True, 1.0, "1"])
def test_schema_version_requires_raw_integer(schema_version: object) -> None:
    payload = succeeded_payload()
    payload["schema_version"] = schema_version
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("schema_version",)


def test_event_id_rejects_non_string_input() -> None:
    payload = succeeded_payload()
    payload["event_id"] = 123
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "string_type"
    assert error["loc"] == ("event_id",)


def test_envelope_forbids_unknown_fields() -> None:
    payload = succeeded_payload()
    payload["unexpected"] = True
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("unexpected",)


def test_discriminated_payload_forbids_unknown_fields() -> None:
    payload = succeeded_payload()
    payload["payload"]["unexpected"] = True  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        PaymentWebhookEnvelope.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ("payload", "payment.succeeded", "unexpected")


def test_json_mode_preserves_external_webhook_shape() -> None:
    envelope = PaymentWebhookEnvelope.model_validate(succeeded_payload())
    assert envelope.model_dump(mode="json") == succeeded_payload()


def test_webhook_rejects_signature_before_parsing_payload() -> None:
    with pytest.raises(InvalidWebhookSignature):
        parse_payment_webhook(
            b"not-json",
            signature="00" * hashlib.sha256().digest_size,
            secret=SecretStr("demo-secret"),
        )


@pytest.mark.parametrize("signature", ["not-hex", "签名"])
def test_webhook_rejects_malformed_hex_signature(signature: str) -> None:
    with pytest.raises(InvalidWebhookSignature):
        parse_payment_webhook(b"not-json", signature, SecretStr("demo-secret"))


@pytest.mark.parametrize("signature", [None, b"00"])
def test_webhook_rejects_non_string_signature(signature: object) -> None:
    with pytest.raises(InvalidWebhookSignature):
        parse_payment_webhook(
            b"not-json",
            signature,  # type: ignore[arg-type]
            SecretStr("demo-secret"),
        )


def test_valid_signature_then_parses_payload() -> None:
    raw = json.dumps(succeeded_payload(), separators=(",", ":")).encode()
    signature = hmac.new(b"demo-secret", raw, hashlib.sha256).hexdigest()
    parsed = parse_payment_webhook(raw, signature, SecretStr("demo-secret"))
    assert parsed.event_id == "evt_0123456789ab"
