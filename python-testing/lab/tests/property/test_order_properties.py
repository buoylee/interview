from decimal import Decimal

import hypothesis.strategies as st
import pytest
from hypothesis import given

from order_service.domain.order import Money

pytestmark = pytest.mark.property


amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
currencies = st.sampled_from(["usd", "Usd", "USD", "eur", "EUR"])


@given(amount=amounts, currency=currencies)
def test_money_normalizes_valid_currency(amount: Decimal, currency: str) -> None:
    money = Money(amount, currency)

    assert money.amount == amount
    assert money.currency == currency.upper()
