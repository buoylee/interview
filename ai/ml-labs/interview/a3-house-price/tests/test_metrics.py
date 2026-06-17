import math

import pytest

from metrics import mae, rmse


def test_rmse_zero_when_perfect():
    assert rmse([1, 2, 3], [1, 2, 3]) == 0.0


def test_rmse_known_value():
    # 误差 [1, 3] -> sqrt((1 + 9) / 2) = sqrt(5)
    assert rmse([0, 0], [1, 3]) == pytest.approx(math.sqrt(5))


def test_mae_known_value():
    # 绝对误差 [1, 3] -> 平均 2.0
    assert mae([0, 0], [1, 3]) == pytest.approx(2.0)
