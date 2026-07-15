import json

import pytest
from pydantic import ValidationError

from order_contracts.errors import (
    MessageFailureKind,
    classify_consume_failure,
    to_error_response,
)
from order_contracts.events.envelope import parse_order_created
from order_contracts.inbound.create_order import CreateOrderRequest


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
    assert "top-secret-customer-value" not in dumped


def test_unknown_event_version_is_incompatible_not_transient() -> None:
    raw = json.dumps(
        {
            "event_id": "msg_0123456789ab",
            "event_type": "order.created",
            "schema_version": 9,
            "occurred_at": "2026-07-15T12:30:00Z",
            "payload": {},
        }
    ).encode()
    with pytest.raises(ValidationError) as caught:
        parse_order_created(raw)
    assert classify_consume_failure(caught.value) is MessageFailureKind.INCOMPATIBLE


def test_field_validation_is_permanent_and_timeout_is_transient() -> None:
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate({})
    assert classify_consume_failure(caught.value) is MessageFailureKind.PERMANENT
    assert classify_consume_failure(TimeoutError("broker unavailable")) is MessageFailureKind.TRANSIENT
