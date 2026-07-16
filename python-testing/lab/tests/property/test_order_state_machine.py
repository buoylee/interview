from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import hypothesis.strategies as st
import pytest
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from order_service.domain.order import (
    InvalidOrderTransition,
    Money,
    Order,
    OrderStatus,
)


def make_order() -> Order:
    return Order.create(
        order_id=UUID("00000000-0000-0000-0000-000000000001"),
        idempotency_key="property-order",
        total=Money(Decimal("12.34"), "usd"),
        created_at=datetime(2026, 7, 15, tzinfo=UTC),
    )


references = st.text(
    alphabet=st.characters(blacklist_categories=("C", "Z")),
    min_size=1,
    max_size=24,
)


class OrderMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.order = make_order()
        self.model_status = OrderStatus.PENDING_PAYMENT
        self.model_reference: str | None = None
        self.model_version = 1

    @precondition(
        lambda self: self.model_status
        in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}
    )
    @rule()
    def start_payment(self) -> None:
        self.order.start_payment()
        self.model_status = OrderStatus.PAYMENT_IN_PROGRESS
        self.model_version += 1

    @precondition(lambda self: self.model_status is OrderStatus.PAYMENT_IN_PROGRESS)
    @rule(reference=references)
    def approve(self, reference: str) -> None:
        self.order.mark_paid(reference)
        self.model_status = OrderStatus.PAID
        self.model_reference = reference
        self.model_version += 1

    @precondition(lambda self: self.model_status is OrderStatus.PAYMENT_IN_PROGRESS)
    @rule()
    def decline(self) -> None:
        self.order.mark_payment_failed()
        self.model_status = OrderStatus.PAYMENT_FAILED
        self.model_version += 1

    @precondition(lambda self: self.model_status is not OrderStatus.PAYMENT_IN_PROGRESS)
    @rule()
    def reject_decline_outside_payment(self) -> None:
        with pytest.raises(InvalidOrderTransition):
            self.order.mark_payment_failed()

    @precondition(
        lambda self: self.model_status
        not in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}
    )
    @rule()
    def reject_duplicate_start(self) -> None:
        with pytest.raises(InvalidOrderTransition):
            self.order.start_payment()

    @invariant()
    def implementation_matches_model(self) -> None:
        assert self.order.status is self.model_status
        assert self.order.payment_reference == self.model_reference
        assert self.order.version == self.model_version


TestOrderMachine = pytest.mark.property(OrderMachine.TestCase)
