from decimal import Decimal


def assert_total(got: Decimal, expected: Decimal) -> None:
    assert got == expected
