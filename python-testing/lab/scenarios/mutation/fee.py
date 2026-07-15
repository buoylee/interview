from decimal import Decimal


def fee(amount: Decimal) -> Decimal:
    return amount * Decimal("0.02")
