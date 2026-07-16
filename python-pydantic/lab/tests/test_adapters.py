import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from order_contracts.adapters import parse_create_order, to_create_order_command
from order_contracts.inbound.create_order import CreateOrderRequest


def test_mapper_lists_fields_explicitly() -> None:
    request = CreateOrderRequest.model_validate(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "USD"},
                }
            ],
        }
    )
    command = to_create_order_command(request)
    assert command.customer_id == "cus_0123456789ab"
    assert command.lines[0].unit_amount == Decimal("12.30")
    assert command.lines[0].currency == "USD"


def test_parse_create_order_validates_raw_json_bytes() -> None:
    raw = json.dumps(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "usd"},
                }
            ],
        }
    ).encode()
    request = parse_create_order(raw)
    assert request.customer_id == "cus_0123456789ab"
    assert request.items[0].unit_price.currency == "USD"


def test_parse_create_order_rejects_invalid_json() -> None:
    with pytest.raises(ValidationError) as caught:
        parse_create_order(b"not-json")
    assert caught.value.errors()[0]["type"] == "json_invalid"
    assert caught.value.errors()[0]["loc"] == ()
