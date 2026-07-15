from collections.abc import Mapping
from typing import Annotated, Generic, Literal, TypeAlias, TypeVar

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    TypeAdapter,
    field_validator,
    model_validator,
)

from order_contracts.events.v1 import OrderCreatedV1
from order_contracts.events.v2 import OrderCreatedV2


PayloadT = TypeVar("PayloadT")
MessageId = Annotated[StrictStr, Field(pattern=r"^msg_[0-9a-f]{12}$")]


class _SchemaVersionHeader(BaseModel):
    schema_version: int

    @field_validator("schema_version", mode="before")
    @classmethod
    def require_integer_schema_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


def _validate_schema_version_header(value: object) -> object:
    _SchemaVersionHeader.model_validate(value, from_attributes=True)
    return value


def _validate_discriminator_header(value: object) -> object:
    if isinstance(value, Mapping) and "schema_version" not in value:
        return value
    return _validate_schema_version_header(value)


class EventEnvelope(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: MessageId
    event_type: StrictStr
    schema_version: StrictInt
    occurred_at: AwareDatetime
    payload: PayloadT

    @model_validator(mode="before")
    @classmethod
    def require_integer_schema_version(cls, value: object) -> object:
        return _validate_schema_version_header(value)


class OrderCreatedEnvelopeV1(EventEnvelope[OrderCreatedV1]):
    event_type: Literal["order.created"]
    schema_version: Literal[1]


class OrderCreatedEnvelopeV2(EventEnvelope[OrderCreatedV2]):
    event_type: Literal["order.created"]
    schema_version: Literal[2]


_DiscriminatedOrderCreatedMessage: TypeAlias = Annotated[
    OrderCreatedEnvelopeV1 | OrderCreatedEnvelopeV2,
    Field(discriminator="schema_version"),
]
OrderCreatedMessage: TypeAlias = Annotated[
    _DiscriminatedOrderCreatedMessage,
    BeforeValidator(_validate_discriminator_header),
]
ORDER_CREATED_ADAPTER = TypeAdapter(OrderCreatedMessage)


def parse_order_created(raw: bytes) -> OrderCreatedMessage:
    return ORDER_CREATED_ADAPTER.validate_json(raw)
