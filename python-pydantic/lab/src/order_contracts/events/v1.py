from pydantic import BaseModel, ConfigDict

from order_contracts.value_objects import CustomerId, Money, OrderId


class OrderCreatedV1(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    order_id: OrderId
    customer_id: CustomerId
    total: Money
