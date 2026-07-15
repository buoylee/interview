def test_a_mutates_shared_order(shared_order) -> None:
    shared_order.start_payment()


def test_b_expected_fresh_order(shared_order) -> None:
    assert shared_order.status.value == "pending_payment"
