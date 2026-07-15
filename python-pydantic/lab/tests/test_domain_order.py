from decimal import Decimal

import pytest

from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order, OrderStatus


def test_order_calculates_total_from_command() -> None:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    order = Order.create("ord_0123456789ab", command)
    assert order.total_amount == Decimal("24.60")
    assert order.currency == "USD"
    assert order.status is OrderStatus.PENDING_PAYMENT


def test_mixed_currency_is_a_domain_error() -> None:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(
            CreateOrderLine("SKU-RED-1", 1, Decimal("12.30"), "USD"),
            CreateOrderLine("SKU-BLUE-1", 1, Decimal("10.00"), "EUR"),
        ),
    )
    with pytest.raises(ValueError, match="single currency"):
        Order.create("ord_0123456789ab", command)
