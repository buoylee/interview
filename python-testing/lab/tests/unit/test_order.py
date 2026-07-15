import importlib
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 7, 15, tzinfo=UTC)


def test_order_module_exposes_money_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.Money, type)


def test_money_accepts_positive_decimal() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("10.00"), "USD")

    assert money.amount == Decimal("10.00")
    assert money.currency == "USD"


def test_money_is_immutable() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    money = order_module.Money(Decimal("10.00"), "USD")

    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("11.00")

    assert money.amount == Decimal("10.00")


def test_money_uses_slots_without_instance_dict() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("10.00"), "USD")

    assert not hasattr(money, "__dict__")


def test_order_module_exposes_invalid_amount_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidAmount, ValueError)


def test_money_rejects_float_amount() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidAmount, match="Decimal"):
        order_module.Money(1.0, "USD")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1"), Decimal("-0.01")])
def test_money_rejects_non_positive_amount(amount: Decimal) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidAmount, match="positive"):
        order_module.Money(amount, "USD")


def test_money_normalizes_valid_currency() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    money = order_module.Money(Decimal("1.00"), "usd")

    assert money.currency == "USD"


def test_order_module_exposes_invalid_currency_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidCurrency, ValueError)


@pytest.mark.parametrize("currency", ["", "US", "US1", "USDD"])
def test_money_rejects_invalid_currency_code(currency: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(order_module.InvalidCurrency, match="three-letter"):
        order_module.Money(Decimal("1.00"), currency)


def test_order_module_exposes_order_status_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.OrderStatus, type)


def test_order_status_has_exact_public_members_and_values() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert [(status.name, status.value) for status in order_module.OrderStatus] == [
        ("PENDING_PAYMENT", "pending_payment"),
        ("PAYMENT_IN_PROGRESS", "payment_in_progress"),
        ("PAYMENT_FAILED", "payment_failed"),
        ("PAID", "paid"),
    ]


def test_order_status_interoperates_with_strings() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    paid = order_module.OrderStatus.PAID

    assert isinstance(paid, str)
    assert paid == "paid"
    assert {"paid": "settled"}[paid] == "settled"


def test_order_module_exposes_order_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert isinstance(order_module.Order, type)


def test_order_type_exposes_create_factory() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.create)


def test_order_create_rejects_positional_invocation() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(TypeError, match="positional"):
        order_module.Order.create(
            ORDER_ID,
            "create-001",
            order_module.Money(Decimal("10.00"), "USD"),
            NOW,
        )


@pytest.mark.parametrize(
    "missing_field", ["order_id", "idempotency_key", "total", "created_at"]
)
def test_order_create_requires_each_named_field(missing_field: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")
    arguments: dict[str, object] = {
        "order_id": ORDER_ID,
        "idempotency_key": "create-001",
        "total": order_module.Money(Decimal("10.00"), "USD"),
        "created_at": NOW,
    }
    del arguments[missing_field]

    with pytest.raises(TypeError, match=missing_field):
        order_module.Order.create(**arguments)


def test_order_create_preserves_required_fields_at_version_one() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    total = order_module.Money(Decimal("10.00"), "USD")

    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=total,
        created_at=NOW,
    )

    assert order.id == ORDER_ID
    assert order.idempotency_key == "create-001"
    assert order.total == total
    assert order.status is order_module.OrderStatus.PENDING_PAYMENT
    assert order.created_at == NOW
    assert order.payment_reference is None
    assert order.version == 1


@pytest.mark.parametrize("idempotency_key", ["", "   "])
def test_order_create_rejects_blank_idempotency_key(idempotency_key: str) -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(ValueError, match="idempotency_key.*blank"):
        order_module.Order.create(
            order_id=ORDER_ID,
            idempotency_key=idempotency_key,
            total=order_module.Money(Decimal("10.00"), "USD"),
            created_at=NOW,
        )


def test_order_create_rejects_naive_timestamp() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    with pytest.raises(ValueError, match="timezone-aware"):
        order_module.Order.create(
            order_id=ORDER_ID,
            idempotency_key="create-001",
            total=order_module.Money(Decimal("10.00"), "USD"),
            created_at=datetime(2026, 7, 15),
        )


def test_order_module_exposes_invalid_order_transition_type() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert issubclass(order_module.InvalidOrderTransition, RuntimeError)


def test_order_type_exposes_start_payment_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.start_payment)


def test_start_payment_retries_failed_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order(
        id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        status=order_module.OrderStatus.PAYMENT_FAILED,
        created_at=NOW,
        version=3,
    )

    order.start_payment()

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 4


def test_start_payment_moves_pending_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )

    order.start_payment()

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 2


def test_order_type_exposes_mark_payment_failed_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.mark_payment_failed)


def test_mark_payment_failed_moves_in_progress_order_and_increments_version() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    order.mark_payment_failed()

    assert order.status is order_module.OrderStatus.PAYMENT_FAILED
    assert order.payment_reference is None
    assert order.version == 3


def test_order_type_exposes_mark_paid_method() -> None:
    order_module = importlib.import_module("order_service.domain.order")

    assert callable(order_module.Order.mark_paid)


def test_mark_paid_moves_in_progress_order_and_records_reference() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    order.mark_paid("provider-001")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_same_reference_replay_preserves_paid_state() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()
    order.mark_paid("provider-001")

    order.mark_paid("provider-001")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_rejects_different_reference_and_preserves_paid_state() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()
    order.mark_paid("provider-001")

    with pytest.raises(order_module.InvalidOrderTransition, match="PAID.*PAID"):
        order.mark_paid("provider-002")

    assert order.status is order_module.OrderStatus.PAID
    assert order.payment_reference == "provider-001"
    assert order.version == 3


def test_mark_paid_rejects_blank_provider_reference_without_mutation() -> None:
    order_module = importlib.import_module("order_service.domain.order")
    order = order_module.Order.create(
        order_id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        created_at=NOW,
    )
    order.start_payment()

    with pytest.raises(ValueError, match="provider_reference.*blank"):
        order.mark_paid("   ")

    assert order.status is order_module.OrderStatus.PAYMENT_IN_PROGRESS
    assert order.payment_reference is None
    assert order.version == 2


@pytest.mark.parametrize(
    (
        "operation",
        "source_name",
        "target_name",
        "payment_reference",
        "version",
    ),
    [
        (
            "start_payment",
            "PAYMENT_IN_PROGRESS",
            "PAYMENT_IN_PROGRESS",
            None,
            2,
        ),
        ("start_payment", "PAID", "PAYMENT_IN_PROGRESS", "provider-001", 3),
        ("mark_payment_failed", "PENDING_PAYMENT", "PAYMENT_FAILED", None, 1),
        ("mark_payment_failed", "PAYMENT_FAILED", "PAYMENT_FAILED", None, 3),
        ("mark_payment_failed", "PAID", "PAYMENT_FAILED", "provider-001", 3),
        ("mark_paid", "PENDING_PAYMENT", "PAID", None, 1),
        ("mark_paid", "PAYMENT_FAILED", "PAID", None, 3),
    ],
)
def test_illegal_transition_matrix_preserves_order_state(
    operation: str,
    source_name: str,
    target_name: str,
    payment_reference: str | None,
    version: int,
) -> None:
    order_module = importlib.import_module("order_service.domain.order")
    source = getattr(order_module.OrderStatus, source_name)
    target = getattr(order_module.OrderStatus, target_name)
    order = order_module.Order(
        id=ORDER_ID,
        idempotency_key="create-001",
        total=order_module.Money(Decimal("10.00"), "USD"),
        status=source,
        created_at=NOW,
        payment_reference=payment_reference,
        version=version,
    )
    before = (order.status, order.payment_reference, order.version)

    with pytest.raises(
        order_module.InvalidOrderTransition,
        match=f"{source.name}.*{target.name}",
    ):
        if operation == "start_payment":
            order.start_payment()
        elif operation == "mark_payment_failed":
            order.mark_payment_failed()
        else:
            order.mark_paid("provider-002")

    assert (order.status, order.payment_reference, order.version) == before


def test_domain_package_exposes_public_order_symbols() -> None:
    domain_module = importlib.import_module("order_service.domain")

    for name in (
        "InvalidAmount",
        "InvalidCurrency",
        "InvalidOrderTransition",
        "Money",
        "Order",
        "OrderStatus",
    ):
        assert hasattr(domain_module, name), name


def test_domain_package_all_is_exact_public_order_api() -> None:
    domain_module = importlib.import_module("order_service.domain")

    assert domain_module.__all__ == [
        "InvalidAmount",
        "InvalidCurrency",
        "InvalidOrderTransition",
        "Money",
        "Order",
        "OrderStatus",
    ]
