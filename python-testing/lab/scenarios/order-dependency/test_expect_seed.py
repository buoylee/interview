from state import seen


def test_expect_seed() -> None:
    assert seen == ["seed"]
