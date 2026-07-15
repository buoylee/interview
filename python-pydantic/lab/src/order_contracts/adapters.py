from datetime import datetime

from order_contracts.application.commands import CreateOrderCommand, CreateOrderLine
from order_contracts.domain.order import Order
from order_contracts.events.envelope import OrderCreatedEnvelopeV2
from order_contracts.events.v2 import OrderCreatedV2
from order_contracts.inbound.create_order import CreateOrderRequest
from order_contracts.outbound.views import CustomerOrderView, InternalOrderView
from order_contracts.value_objects import Money


def to_create_order_command(request: CreateOrderRequest) -> CreateOrderCommand:
    return CreateOrderCommand(
        customer_id=request.customer_id,
        idempotency_key=request.idempotency_key,
        lines=tuple(
            CreateOrderLine(
                sku=item.sku,
                quantity=item.quantity,
                unit_amount=item.unit_price.amount,
                currency=item.unit_price.currency,
            )
            for item in request.items
        ),
    )


def project_customer_order(order: Order) -> CustomerOrderView:
    return CustomerOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
    )


def project_internal_order(
    order: Order,
    provider_reference: str | None,
) -> InternalOrderView:
    return InternalOrderView(
        order_id=order.order_id,
        status=order.status,
        total=Money(amount=order.total_amount, currency=order.currency),
        item_count=len(order.lines),
        customer_id=order.customer_id,
        provider_reference=provider_reference,
        internal_note=order.internal_note,
    )


def project_order_created_v2(
    order: Order,
    event_id: str,
    occurred_at: datetime,
) -> OrderCreatedEnvelopeV2:
    return OrderCreatedEnvelopeV2(
        event_id=event_id,
        event_type="order.created",
        schema_version=2,
        occurred_at=occurred_at,
        payload=OrderCreatedV2(
            order_id=order.order_id,
            customer_id=order.customer_id,
            total=Money(amount=order.total_amount, currency=order.currency),
            item_count=len(order.lines),
        ),
    )
