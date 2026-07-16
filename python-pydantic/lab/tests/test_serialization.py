from decimal import Decimal

from order_contracts.adapters import project_customer_order, project_internal_order
from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order
from order_contracts.outbound.views import CustomerOrderEnvelope


def make_order() -> Order:
    command = CreateOrderCommand(
        customer_id="cus_0123456789ab",
        idempotency_key="checkout-2026-0001",
        lines=(CreateOrderLine("SKU-RED-1", 2, Decimal("12.30"), "USD"),),
    )
    return Order.create("ord_0123456789ab", command)


def test_customer_projection_is_an_explicit_whitelist() -> None:
    view = project_customer_order(make_order())
    dumped = view.model_dump(mode="json")
    assert dumped == {
        "order_id": "ord_0123456789ab",
        "status": "pending_payment",
        "total": {"amount": "24.60", "currency": "USD"},
        "item_count": 1,
    }


def test_base_annotation_hides_internal_subclass_fields_by_default() -> None:
    internal = project_internal_order(make_order(), provider_reference="pay_demo_001")
    envelope = CustomerOrderEnvelope(order=internal)
    safe = envelope.model_dump(mode="json")
    assert "customer_id" not in safe["order"]
    assert "provider_reference" not in safe["order"]


def test_serialize_as_any_demonstrates_the_leak_risk() -> None:
    internal = project_internal_order(make_order(), provider_reference="pay_demo_001")
    envelope = CustomerOrderEnvelope(order=internal)
    unsafe = envelope.model_dump(mode="json", serialize_as_any=True)
    assert unsafe["order"]["customer_id"] == "cus_0123456789ab"
    assert unsafe["order"]["provider_reference"] == "pay_demo_001"
