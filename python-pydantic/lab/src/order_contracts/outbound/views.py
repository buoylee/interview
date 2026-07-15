from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr

from order_contracts.domain.order import OrderStatus
from order_contracts.value_objects import CustomerId, Money, OrderId


class CustomerOrderView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order_id: OrderId
    status: OrderStatus
    total: Money
    item_count: StrictInt


class InternalOrderView(CustomerOrderView):
    customer_id: CustomerId
    provider_reference: StrictStr | None
    internal_note: StrictStr | None


class CustomerOrderEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: CustomerOrderView
