import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from metrics import rmse


def add_leaky_feature(X, y, noise=0.01, seed=0):
    """加一个从目标 y 派生的特征 —— 这就是 target leakage。"""
    rng = np.random.default_rng(seed)
    leak = y + rng.normal(0.0, noise, size=len(y))
    return np.column_stack([X, leak])


def honest_val_rmse(splits):
    model = make_pipeline(StandardScaler(), LinearRegression())
    model.fit(splits["X_train"], splits["y_train"])
    return rmse(splits["y_val"], model.predict(splits["X_val"]))


def leaky_val_rmse(splits):
    X_train = add_leaky_feature(splits["X_train"], splits["y_train"])
    X_val = add_leaky_feature(splits["X_val"], splits["y_val"])
    model = make_pipeline(StandardScaler(), LinearRegression())
    model.fit(X_train, splits["y_train"])
    return rmse(splits["y_val"], model.predict(X_val))
