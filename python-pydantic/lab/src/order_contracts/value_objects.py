from decimal import Decimal
import re
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictStr,
    StringConstraints,
    field_serializer,
)


MONEY_STRING_PATTERN = (
    r"^(?:[1-9]\d{0,9}(?:\.\d{1,2})?|0\.(?:0[1-9]|[1-9]\d?))$"
)


def _validate_money_input(value: Any) -> Any:
    if isinstance(value, str):
        if re.fullmatch(MONEY_STRING_PATTERN, value) is None:
            raise ValueError("money amount must be a canonical positive decimal string")
        return value
    if not isinstance(value, Decimal):
        raise ValueError("money amount must be a Decimal or decimal string")
    return value


def _normalize_currency(value: Any) -> Any:
    if isinstance(value, str):
        if not value.isascii():
            raise ValueError("currency code must contain ASCII letters")
        return value.strip().upper()
    return value


OrderId = Annotated[StrictStr, Field(pattern=r"^ord_[0-9a-f]{12}$")]
CustomerId = Annotated[StrictStr, Field(pattern=r"^cus_[0-9a-f]{12}$")]
CurrencyCode = Annotated[
    StrictStr,
    Field(pattern=r"^[A-Z]{3}$"),
    BeforeValidator(
        _normalize_currency,
        json_schema_input_type=Annotated[
            str, Field(pattern=r"^\s*[A-Za-z]{3}\s*$")
        ],
    ),
]
Sku = Annotated[
    StrictStr,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$"),
]
MoneyAmount = Annotated[
    Decimal,
    Field(gt=Decimal("0"), max_digits=12, decimal_places=2),
    BeforeValidator(
        _validate_money_input,
        json_schema_input_type=Annotated[
            str, Field(pattern=MONEY_STRING_PATTERN)
        ],
    ),
]


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: MoneyAmount
    currency: CurrencyCode

    @field_serializer("amount", when_used="json")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")
