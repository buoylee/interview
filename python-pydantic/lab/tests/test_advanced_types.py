import pytest
from pydantic import TypeAdapter, ValidationError

from order_contracts.advanced_types import ProviderReference


def test_core_schema_type_normalizes_and_returns_subclass() -> None:
    adapter = TypeAdapter(ProviderReference)
    value = adapter.validate_python("  pay_ABC12345  ")
    assert value == "pay_ABC12345"
    assert isinstance(value, ProviderReference)


def test_core_schema_type_validates_json_and_returns_subclass() -> None:
    value = TypeAdapter(ProviderReference).validate_json(b'"  pay_ABC12345  "')
    assert value == "pay_ABC12345"
    assert isinstance(value, ProviderReference)


def test_core_schema_type_has_matching_json_schema() -> None:
    schema = TypeAdapter(ProviderReference).json_schema()
    assert schema["type"] == "string"
    assert schema["pattern"] == r"^pay_[A-Za-z0-9_-]{8,64}$"


def test_core_schema_type_serializes_as_json_string() -> None:
    adapter = TypeAdapter(ProviderReference)
    value = adapter.validate_python("pay_ABC12345")
    assert adapter.dump_python(value, mode="json") == "pay_ABC12345"
    assert adapter.dump_json(value) == b'"pay_ABC12345"'


def test_core_schema_type_rejects_invalid_reference() -> None:
    with pytest.raises(ValidationError) as caught:
        TypeAdapter(ProviderReference).validate_python("wrong")
    assert caught.value.errors()[0]["type"] == "value_error"
