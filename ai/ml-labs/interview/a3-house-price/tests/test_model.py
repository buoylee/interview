import os

from dataio import load_housing, make_splits
from metrics import rmse
from model import baseline_predict, fit_linear, fit_poly, fit_ridge_poly, val_rmse

CSV = os.path.join(os.path.dirname(__file__), "..", "data", "california_housing.csv")


def _splits():
    X, y, _ = load_housing(CSV)
    return make_splits(X, y, seed=42)


def test_linear_beats_baseline():
    s = _splits()
    base = rmse(s["y_val"], baseline_predict(s["y_train"], len(s["y_val"])))
    lin = val_rmse(fit_linear(s), s)
    assert lin < base


def test_ridge_reduces_overfit_gap():
    # 高次多项式无正则会过拟合;加 ridge 后 val RMSE 应不升反降
    s = _splits()
    poly = val_rmse(fit_poly(s), s)
    ridge = val_rmse(fit_ridge_poly(s), s)
    assert ridge <= poly
