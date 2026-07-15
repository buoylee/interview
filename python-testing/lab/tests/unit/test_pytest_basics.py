from collections.abc import Iterator

import pytest


def add(left: int, right: int) -> int:
    return left + right


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


@pytest.fixture
def sample_order() -> Iterator[dict[str, object]]:
    order = {"id": "order-1", "paid": False}
    yield order
    order.clear()


def test_fixture_supplies_isolated_order(sample_order: dict[str, object]) -> None:
    assert sample_order["paid"] is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" paid ", "paid"), ("PENDING", "pending"), ("", "")],
)
def test_normalize_status(raw: str, expected: str) -> None:
    assert raw.strip().lower() == expected
