from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    field_validator,
)

from order_contracts.value_objects import Money, OrderId


EventId = Annotated[StrictStr, Field(pattern=r"^evt_[0-9a-f]{12}$")]
ProviderReference = Annotated[
    StrictStr,
    StringConstraints(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"),
]
FailureCode = Annotated[
    StrictStr,
    StringConstraints(min_length=3, max_length=40, pattern=r"^[A-Z0-9_]+$"),
]


class PaymentSucceeded(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["payment.succeeded"]
    provider_reference: ProviderReference
    order_id: OrderId
    paid_amount: Money
    occurred_at: AwareDatetime


class PaymentFailed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["payment.failed"]
    provider_reference: ProviderReference
    order_id: OrderId
    failure_code: FailureCode
    occurred_at: AwareDatetime


PaymentPayload = Annotated[PaymentSucceeded | PaymentFailed, Field(discriminator="event_type")]


class PaymentWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: EventId
    schema_version: Literal[1]
    payload: PaymentPayload

    @field_validator("schema_version", mode="before")
    @classmethod
    def require_integer_schema_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value
