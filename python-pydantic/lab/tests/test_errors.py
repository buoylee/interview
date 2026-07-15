import json
from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError

from order_contracts.errors import (
    MessageFailureKind,
    classify_consume_failure,
    to_error_response,
)
from order_contracts.events.envelope import OrderCreatedEnvelopeV1, parse_order_created
from order_contracts.inbound.create_order import CreateOrderRequest


class DeliveryPreference(BaseModel):
    speed: Literal["standard"]


def order_created_message() -> dict[str, object]:
    return {
        "event_id": "msg_0123456789ab",
        "event_type": "order.created",
        "schema_version": 1,
        "occurred_at": "2026-07-15T12:30:00Z",
        "payload": {
            "order_id": "ord_0123456789ab",
            "customer_id": "cus_0123456789ab",
            "total": {"amount": "24.60", "currency": "USD"},
        },
    }


def test_error_response_exposes_type_and_loc_but_not_input() -> None:
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(
            {
                "customer_id": "top-secret-customer-value",
                "idempotency_key": "checkout-2026-0001",
                "items": [],
            }
        )
    response = to_error_response(caught.value)
    dumped = response.model_dump_json()
    assert response.details[0].reason in {"string_pattern_mismatch", "too_short"}
    assert set(response.details[0].model_dump()) == {"reason", "path"}
    assert "top-secret-customer-value" not in dumped


def test_unknown_event_version_is_incompatible_not_transient() -> None:
    message = order_created_message()
    message["schema_version"] = 9
    raw = json.dumps(message).encode()
    with pytest.raises(ValidationError) as caught:
        parse_order_created(raw)
    assert classify_consume_failure(caught.value) is MessageFailureKind.INCOMPATIBLE


def test_missing_event_version_is_incompatible() -> None:
    message = order_created_message()
    del message["schema_version"]
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    assert caught.value.errors()[0]["type"] == "union_tag_not_found"
    assert classify_consume_failure(caught.value) is MessageFailureKind.INCOMPATIBLE


def test_protocol_header_literal_error_is_incompatible() -> None:
    message = order_created_message()
    message["event_type"] = "order.cancelled"
    with pytest.raises(ValidationError) as caught:
        OrderCreatedEnvelopeV1.model_validate(message)
    assert caught.value.errors()[0]["loc"] == ("event_type",)
    assert caught.value.errors()[0]["type"] == "literal_error"
    assert classify_consume_failure(caught.value) is MessageFailureKind.INCOMPATIBLE


def test_ordinary_literal_error_is_permanent() -> None:
    with pytest.raises(ValidationError) as caught:
        DeliveryPreference.model_validate({"speed": "express"})
    assert caught.value.errors()[0]["loc"] == ("speed",)
    assert caught.value.errors()[0]["type"] == "literal_error"
    assert classify_consume_failure(caught.value) is MessageFailureKind.PERMANENT


def test_field_validation_is_permanent() -> None:
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate({})
    assert classify_consume_failure(caught.value) is MessageFailureKind.PERMANENT


@pytest.mark.parametrize("error_type", [TimeoutError, ConnectionError])
def test_transport_failure_is_transient(error_type: type[Exception]) -> None:
    error = error_type("broker unavailable")
    assert classify_consume_failure(error) is MessageFailureKind.TRANSIENT


@pytest.mark.parametrize("error_type", [TypeError, KeyError, AssertionError])
def test_unknown_failure_is_propagated(error_type: type[Exception]) -> None:
    error = error_type("unexpected consumer bug")
    with pytest.raises(error_type) as caught:
        classify_consume_failure(error)
    assert caught.value is error
