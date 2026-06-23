import pytest
from saturate import usl_throughput, usl_curve, peak_n


def test_linear_when_no_contention():
    # σ=0, κ=0 → perfect linear scaling
    assert usl_throughput(10, 0.0, 0.0) == pytest.approx(10.0)


def test_amdahl_plateau_with_sigma():
    # contention only (κ=0): approaches the 1/σ ceiling, never retrogrades
    assert usl_throughput(1000, 0.05, 0.0) < 1 / 0.05
    assert usl_throughput(1000, 0.05, 0.0) > usl_throughput(100, 0.05, 0.0)


def test_kappa_causes_retrograde():
    # with κ>0 throughput peaks then DROPS — the key USL insight
    c = usl_curve(list(range(1, 64)), 0.03, 0.001)
    tputs = [t for _, t in c]
    peak = max(tputs)
    assert tputs[-1] < peak  # retrograde past the peak


def test_peak_n_matches_curve():
    sigma, kappa = 0.03, 0.001
    c = dict(usl_curve(list(range(1, 200)), sigma, kappa))
    pn = peak_n(sigma, kappa)
    assert c[pn] == pytest.approx(max(c.values()), rel=0.02)
