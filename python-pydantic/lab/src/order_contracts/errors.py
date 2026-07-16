from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str
    path: list[str | int]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal["invalid_request"] = "invalid_request"
    details: list[ErrorDetail]


def to_error_response(error: ValidationError) -> ErrorResponse:
    return ErrorResponse(
        details=[
            ErrorDetail(
                reason=item["type"],
                path=list(item["loc"]),
            )
            for item in error.errors(include_url=False)
        ]
    )


class MessageFailureKind(StrEnum):
    INCOMPATIBLE = "incompatible"
    PERMANENT = "permanent"
    TRANSIENT = "transient"


def classify_consume_failure(error: Exception) -> MessageFailureKind:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return MessageFailureKind.TRANSIENT
    if isinstance(error, ValidationError):
        errors = error.errors(include_url=False)
        if any(
            item["type"] in {"union_tag_invalid", "union_tag_not_found"}
            or (
                item["type"] == "literal_error"
                and item["loc"]
                and item["loc"][-1] in {"schema_version", "event_type"}
            )
            for item in errors
        ):
            return MessageFailureKind.INCOMPATIBLE
        return MessageFailureKind.PERMANENT
    raise error
