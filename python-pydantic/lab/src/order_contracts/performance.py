import json
from dataclasses import dataclass
from timeit import timeit

from pydantic import TypeAdapter

from order_contracts.inbound.create_order import CreateOrderRequest


@dataclass(frozen=True, slots=True)
class ValidationTiming:
    """Machine-specific observations from two equivalent validation paths."""

    iterations: int
    direct_json_seconds: float
    loads_then_validate_seconds: float


def compare_json_validation(raw: bytes, iterations: int = 1000) -> ValidationTiming:
    """Time JSON validation paths without asserting that either must be faster.

    The adapter is built once and both paths are warmed once before measurement,
    so schema construction is excluded from the hot loops. Each reported value
    is one sequential ``timeit`` observation over ``iterations`` validations.
    """

    if iterations < 1:
        raise ValueError("iterations must be positive")

    adapter = TypeAdapter(CreateOrderRequest)

    def validate_json() -> None:
        adapter.validate_json(raw)

    def loads_then_validate() -> None:
        adapter.validate_python(json.loads(raw))

    validate_json()
    loads_then_validate()

    direct = timeit(validate_json, number=iterations)
    staged = timeit(loads_then_validate, number=iterations)
    return ValidationTiming(
        iterations=iterations,
        direct_json_seconds=direct,
        loads_then_validate_seconds=staged,
    )
