from copy import deepcopy

import pytest
from pydantic import ValidationError

from order_contracts.inbound.create_order import CreateOrderRequest


def valid_payload() -> dict[str, object]:
    return {
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


def test_create_order_normalizes_nested_currency() -> None:
    request = CreateOrderRequest.model_validate(valid_payload())
    assert request.items[0].unit_price.currency == "USD"


def test_quantity_does_not_coerce_string() -> None:
    payload = deepcopy(valid_payload())
    payload["items"][0]["quantity"] = "2"  # type: ignore[index]
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    error = caught.value.errors()[0]
    assert error["type"] == "int_type"
    assert error["loc"] == ("items", 0, "quantity")


def test_http_contract_forbids_unknown_fields() -> None:
    payload = valid_payload()
    payload["is_admin"] = True
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_duplicate_sku_is_rejected() -> None:
    payload = valid_payload()
    first = deepcopy(payload["items"][0])  # type: ignore[index]
    payload["items"] = [first, deepcopy(first)]
    with pytest.raises(ValidationError) as caught:
        CreateOrderRequest.model_validate(payload)
    assert caught.value.errors()[0]["type"] == "value_error"
