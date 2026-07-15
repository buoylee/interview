from decimal import Decimal

from order_contracts.adapters import to_create_order_command
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
