from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from order_service.domain.order import Order


class CreateOrderRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")


class OrderResponse(BaseModel):
    id: UUID
    status: str
    amount: Decimal
    currency: str
    version: int

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)

    @classmethod
    def from_domain(cls, order: Order) -> Self:
        return cls(
            id=order.id,
            status=order.status.value,
            amount=order.total.amount,
            currency=order.total.currency,
            version=order.version,
        )


class RefundResponse(BaseModel):
    order_id: UUID
    status: Literal["accepted"]
