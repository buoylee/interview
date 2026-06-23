import pytest
from little import little_l, mm1_response, mm1_curve


def test_little_l_basic():
    # λ=200 req/s, W=50ms → 10 in flight
    assert little_l(200, 0.05) == pytest.approx(10.0)


def test_mm1_blows_up_near_one():
    # R = S/(1-ρ): closer to 1 → super-linear blow-up
    assert mm1_response(0.01, 0.5) == pytest.approx(0.02)
    assert mm1_response(0.01, 0.9) == pytest.approx(0.10)
    assert mm1_response(0.01, 0.99) == pytest.approx(1.0)


def test_mm1_rejects_saturation():
    with pytest.raises(ValueError):
        mm1_response(0.01, 1.0)


def test_curve_is_monotonic_increasing():
    pts = mm1_curve(0.01, [0.1, 0.5, 0.9, 0.95])
    rs = [r for _, r in pts]
    assert rs == sorted(rs) and rs[-1] > rs[0]
