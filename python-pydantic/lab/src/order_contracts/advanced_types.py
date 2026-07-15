import re
from typing import Any

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


PROVIDER_REFERENCE_PATTERN = r"^pay_[A-Za-z0-9_-]{8,64}$"


class ProviderReference(str):
    """Provider reference implemented with Pydantic's low-level schema hooks.

    Prefer ``Annotated`` constraints for ordinary application contracts. This
    type exists to isolate the version-sensitive CoreSchema extension example.
    """

    @classmethod
    def validate(cls, value: str) -> "ProviderReference":
        normalized = value.strip()
        if re.fullmatch(PROVIDER_REFERENCE_PATTERN, normalized) is None:
            raise ValueError("invalid provider reference")
        return cls(normalized)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            handler(str),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler.resolve_ref_schema(handler(schema))
        json_schema.update(type="string", pattern=PROVIDER_REFERENCE_PATTERN)
        return json_schema
