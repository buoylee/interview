import pytest
from starve import mmc_wait, pool_sweep


def test_more_servers_less_wait():
    # offered load a = λS = 8 erlangs; wait drops as c grows past 8
    w9 = mmc_wait(80, 0.1, 9)
    w12 = mmc_wait(80, 0.1, 12)
    assert w9 > w12 > 0


def test_unstable_when_load_exceeds_servers():
    with pytest.raises(ValueError):
        mmc_wait(80, 0.1, 8)   # a=8, c=8 → ρ=1, unstable


def test_wait_explodes_approaching_capacity():
    # c just above load → huge wait vs a comfortable c
    tight = mmc_wait(80, 0.1, 9)
    loose = mmc_wait(80, 0.1, 16)
    assert tight > 10 * loose


def test_pool_sweep_marks_unstable_as_inf():
    sweep = dict(pool_sweep(80, 0.1, [7, 8, 9]))
    assert sweep[7] == float("inf") and sweep[8] == float("inf")
    assert sweep[9] < float("inf")
