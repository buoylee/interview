import numpy as np

from dataio import make_splits


def _xy(n=100):
    X = np.arange(n * 3, dtype=float).reshape(n, 3)
    y = np.arange(n, dtype=float)
    return X, y


def test_make_splits_sizes_and_no_overlap():
    X, y = _xy(100)
    s = make_splits(X, y, seed=42, val_size=0.2, test_size=0.2)
    assert len(s["y_train"]) == 60
    assert len(s["y_val"]) == 20
    assert len(s["y_test"]) == 20
    # y 在这里是唯一索引,可用来检查三份不重叠
    train, val, test = set(s["y_train"]), set(s["y_val"]), set(s["y_test"])
    assert train.isdisjoint(val)
    assert train.isdisjoint(test)
    assert val.isdisjoint(test)


def test_make_splits_deterministic():
    X, y = _xy(100)
    a = make_splits(X, y, seed=42)
    b = make_splits(X, y, seed=42)
    assert np.array_equal(a["y_train"], b["y_train"])
    assert np.array_equal(a["y_val"], b["y_val"])
    assert np.array_equal(a["y_test"], b["y_test"])
