from decimal import Decimal

from fee import fee


def test_fee_executes() -> None:
    assert fee(Decimal("100.00")) == Decimal("2.0000")
