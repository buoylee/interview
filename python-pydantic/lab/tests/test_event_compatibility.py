import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from order_contracts.adapters import project_order_created_v2
from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order
from order_contracts.events.envelope import (
    OrderCreatedEnvelopeV1,
    OrderCreatedEnvelopeV2,
    OrderCreatedMessage,
    parse_order_created,
)
from order_contracts.events.v1 import OrderCreatedV1


def v1_message() -> dict[str, object]:
    message = v2_message()
    message["schema_version"] = 1
    del message["payload"]["item_count"]  # type: ignore[index]
    return message


def v2_message() -> dict[str, object]:
    return {
        "event_id": "msg_0123456789ab",
        "event_type": "order.created",
        "schema_version": 2,
        "occurred_at": "2026-07-15T12:30:00Z",
        "payload": {
            "order_id": "ord_0123456789ab",
            "customer_id": "cus_0123456789ab",
            "total": {"amount": "24.60", "currency": "USD"},
            "item_count": 1,
        },
    }


def make_order() -> Order:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    return Order.create("ord_0123456789ab", command)


def test_type_adapter_selects_v1_envelope() -> None:
    parsed = parse_order_created(json.dumps(v1_message()).encode())
    assert isinstance(parsed, OrderCreatedEnvelopeV1)


def test_type_adapter_selects_v2_envelope() -> None:
    parsed = parse_order_created(json.dumps(v2_message()).encode())
    assert isinstance(parsed, OrderCreatedEnvelopeV2)
    assert parsed.payload.item_count == 1


def test_message_type_adapter_accepts_validated_envelope() -> None:
    event = OrderCreatedEnvelopeV2.model_validate(v2_message())
    parsed = TypeAdapter(OrderCreatedMessage).validate_python(event)
    assert parsed is event


def test_v1_payload_reader_ignores_additive_v2_field() -> None:
    payload = v2_message()["payload"]
    parsed = OrderCreatedV1.model_validate(payload)
    assert parsed.order_id == "ord_0123456789ab"
    assert "item_count" not in parsed.model_dump()


def test_unknown_schema_version_is_incompatible() -> None:
    message = v2_message()
    message["schema_version"] = 3
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    error = caught.value.errors()[0]
    assert error["type"] == "union_tag_invalid"
    assert error["loc"] == ()


def test_missing_schema_version_uses_native_discriminator_error() -> None:
    message = v2_message()
    del message["schema_version"]
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    error = caught.value.errors()[0]
    assert error["type"] == "union_tag_not_found"
    assert error["loc"] == ()


@pytest.mark.parametrize("schema_version", [True, 1.0, 2.0])
def test_schema_version_requires_raw_integer(schema_version: object) -> None:
    message = v2_message()
    message["schema_version"] = schema_version
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("schema_version",)


@pytest.mark.parametrize(
    ("envelope_type", "message"),
    [
        (OrderCreatedEnvelopeV1, {**v1_message(), "schema_version": True}),
        (OrderCreatedEnvelopeV2, {**v2_message(), "schema_version": 2.0}),
    ],
)
def test_versioned_envelope_models_require_raw_integer_schema_versions(
    envelope_type: type[OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2],
    message: dict[str, object],
) -> None:
    with pytest.raises(ValidationError) as caught:
        envelope_type.model_validate(message)
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("schema_version",)


def test_v2_producer_rejects_unknown_payload_field() -> None:
    message = v2_message()
    message["payload"]["internal_note"] = "must not escape"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    error = caught.value.errors()[0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == (2, "payload", "internal_note")


def test_domain_order_is_explicitly_projected_to_v2_event() -> None:
    order = make_order()
    event = project_order_created_v2(
        order,
        event_id="msg_0123456789ab",
        occurred_at=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
    )
    assert event.payload.order_id == order.order_id
    assert event.payload.total.amount == Decimal("24.60")
    assert event.payload.item_count == 1


def test_projected_v2_event_has_stable_json_wire_shape() -> None:
    event = project_order_created_v2(
        make_order(),
        event_id="msg_0123456789ab",
        occurred_at=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
    )
    assert json.loads(event.model_dump_json()) == v2_message()


def test_event_and_payload_are_immutable() -> None:
    parsed = parse_order_created(json.dumps(v2_message()).encode())
    with pytest.raises(ValidationError) as envelope_error:
        parsed.event_id = "msg_abcdef012345"
    assert envelope_error.value.errors()[0]["type"] == "frozen_instance"
    with pytest.raises(ValidationError) as payload_error:
        parsed.payload.item_count = 2
    assert payload_error.value.errors()[0]["type"] == "frozen_instance"


def test_naive_occurred_at_has_stable_error_location() -> None:
    message = v2_message()
    message["occurred_at"] = "2026-07-15T12:30:00"
    with pytest.raises(ValidationError) as caught:
        parse_order_created(json.dumps(message).encode())
    error = caught.value.errors()[0]
    assert error["type"] == "timezone_aware"
    assert error["loc"] == (2, "occurred_at")
