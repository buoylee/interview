import os

from dataio import load_housing, make_splits
from leakage import honest_val_rmse, leaky_val_rmse

CSV = os.path.join(os.path.dirname(__file__), "..", "data", "california_housing.csv")


def test_target_leakage_inflates_score():
    # 用从 y 派生的特征会让 val 分数好得不真实 —— 经典面试坑
    X, y, _ = load_housing(CSV)
    s = make_splits(X, y, seed=42)
    honest = honest_val_rmse(s)
    leaky = leaky_val_rmse(s)
    assert leaky < honest * 0.2
