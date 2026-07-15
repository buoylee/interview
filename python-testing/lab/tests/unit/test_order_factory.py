from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from order_service.domain.order import Money, Order, OrderStatus
from tests.factories import OrderFactory, make_order


DEFAULT_ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_CREATED_AT = datetime(2026, 7, 15, tzinfo=UTC)


def test_order_factory_fixture_exposes_callable(request: pytest.FixtureRequest) -> None:
    try:
        factory = request.getfixturevalue("order_factory")
    except pytest.FixtureLookupError:
        pytest.fail("order_factory fixture is missing")

    assert callable(factory)


def test_make_order_returns_real_order_with_deterministic_defaults() -> None:
    order = make_order()

    assert isinstance(order, Order)
    assert order.id == DEFAULT_ORDER_ID
    assert order.idempotency_key == "create-001"
    assert order.total == Money(Decimal("10.00"), "USD")
    assert order.created_at == DEFAULT_CREATED_AT
    assert order.status is OrderStatus.PENDING_PAYMENT
    assert order.version == 1


def test_make_order_returns_distinct_mutable_instances() -> None:
    first = make_order()
    second = make_order()

    first.start_payment()

    assert first is not second
    assert first.status is OrderStatus.PAYMENT_IN_PROGRESS
    assert second.status is OrderStatus.PENDING_PAYMENT


def test_order_factory_preserves_keyword_overrides(
    order_factory: OrderFactory,
) -> None:
    order_id = UUID("00000000-0000-0000-0000-000000000099")
    created_at = datetime(2026, 7, 16, 12, 30, tzinfo=UTC)

    order = order_factory(
        order_id=order_id,
        idempotency_key="create-099",
        amount=Decimal("42.50"),
        currency="eur",
        created_at=created_at,
    )

    assert order.id == order_id
    assert order.idempotency_key == "create-099"
    assert order.total == Money(Decimal("42.50"), "EUR")
    assert order.created_at == created_at


def test_order_factory_is_callable_and_returns_fresh_orders(
    order_factory: OrderFactory,
) -> None:
    first = order_factory()
    second = order_factory()

    first.start_payment()

    assert callable(order_factory)
    assert first is not second
    assert second.status is OrderStatus.PENDING_PAYMENT


def test_order_factory_is_function_scoped(pytester: pytest.Pytester) -> None:
    test_file = Path(__file__).resolve()
    result = pytester.runpytest_subprocess(
        "--setup-show",
        "-q",
        f"{test_file}::test_order_factory_preserves_keyword_overrides",
        f"{test_file}::test_order_factory_is_callable_and_returns_fresh_orders",
    )

    result.assert_outcomes(passed=2)
    output = result.stdout.str()
    lifecycle_counts = (
        output.count("SETUP    F order_factory"),
        output.count("TEARDOWN F order_factory"),
    )

    assert lifecycle_counts == (2, 2), output
