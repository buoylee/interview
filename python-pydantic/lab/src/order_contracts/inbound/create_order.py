from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)

from order_contracts.value_objects import CustomerId, Money, Sku


IdempotencyKey = Annotated[
    StrictStr,
    StringConstraints(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"),
]
Quantity = Annotated[StrictInt, Field(ge=1, le=100)]


class CreateOrderItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sku: Sku
    quantity: Quantity
    unit_price: Money


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: CustomerId
    idempotency_key: IdempotencyKey
    items: Annotated[list[CreateOrderItem], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def reject_duplicate_skus(self) -> Self:
        skus = [item.sku for item in self.items]
        if len(skus) != len(set(skus)):
            raise ValueError("duplicate sku is not allowed")
        return self
