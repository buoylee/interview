from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from order_contracts.value_objects import CurrencyCode, Money, OrderId


def test_currency_is_normalized_to_uppercase() -> None:
    adapter = TypeAdapter(CurrencyCode)
    assert adapter.validate_python("usd") == "USD"


def test_order_id_rejects_non_string_input() -> None:
    adapter = TypeAdapter(OrderId)
    with pytest.raises(ValidationError) as caught:
        adapter.validate_python(123)
    assert caught.value.errors()[0]["type"] == "string_type"


def test_money_accepts_decimal_string_and_serializes_as_string() -> None:
    money = Money.model_validate({"amount": "12.30", "currency": "usd"})
    assert money.amount == Decimal("12.30")
    assert money.model_dump(mode="json") == {"amount": "12.30", "currency": "USD"}


def test_money_rejects_binary_float() -> None:
    with pytest.raises(ValidationError) as caught:
        Money.model_validate({"amount": 12.30, "currency": "USD"})
    error = caught.value.errors()[0]
    assert error["type"] == "value_error"
    assert error["loc"] == ("amount",)
