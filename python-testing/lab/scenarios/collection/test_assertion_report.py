from decimal import Decimal

from helpers import assert_total


def test_assert_rewrite_shows_both_operands() -> None:
    assert_total(Decimal("9.99"), Decimal("10.00"))
