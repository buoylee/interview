import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from metrics import rmse


def baseline_predict(y_train, n):
    """最朴素 baseline:永远预测训练集均值。"""
    return np.full(n, float(np.mean(y_train)))


def fit_linear(splits):
    model = make_pipeline(StandardScaler(), LinearRegression())
    model.fit(splits["X_train"], splits["y_train"])
    return model


def fit_poly(splits, degree=3):
    """高次多项式 + 无正则线性回归 —— 故意制造过拟合。"""
    model = make_pipeline(
        StandardScaler(), PolynomialFeatures(degree=degree), LinearRegression()
    )
    model.fit(splits["X_train"], splits["y_train"])
    return model


def fit_ridge_poly(splits, degree=3, alpha=10.0):
    """同样高次多项式,但用 Ridge 正则压制过拟合。"""
    model = make_pipeline(
        StandardScaler(), PolynomialFeatures(degree=degree), Ridge(alpha=alpha)
    )
    model.fit(splits["X_train"], splits["y_train"])
    return model


def val_rmse(model, splits):
    return rmse(splits["y_val"], model.predict(splits["X_val"]))
