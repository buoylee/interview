import pytest

from order_service.db.pool_budget import PoolBudget


def test_pool_budget_counts_every_process_and_overflow_slot() -> None:
    budget = PoolBudget(instances=3, workers=4, pool_size=5, max_overflow=2)

    assert budget.connection_ceiling == 84
    budget.assert_fits(database_budget=100)
    with pytest.raises(ValueError, match="84 exceeds database budget 80"):
        budget.assert_fits(database_budget=80)
    with pytest.raises(ValueError, match="pool_size must be positive"):
        PoolBudget(instances=1, workers=1, pool_size=0, max_overflow=0)
