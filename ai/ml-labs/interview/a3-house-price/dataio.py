import pandas as pd
from sklearn.model_selection import train_test_split

FEATURES = [
    "MedInc", "HouseAge", "AveRooms", "AveBedrms",
    "Population", "AveOccup", "Latitude", "Longitude",
]
TARGET = "MedHouseVal"


def load_housing(csv_path):
    """读 bundle 的 CSV,返回 (X, y, feature_names)。"""
    df = pd.read_csv(csv_path)
    X = df[FEATURES].to_numpy(dtype=float)
    y = df[TARGET].to_numpy(dtype=float)
    return X, y, list(FEATURES)


def make_splits(X, y, seed=42, val_size=0.2, test_size=0.2):
    """切成 train/val/test 三份;先切出 test,再从剩下切出 val。"""
    X_tmp, X_test, y_tmp, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed
    )
    val_rel = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_tmp, y_tmp, test_size=val_rel, random_state=seed
    )
    return {
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "X_test": X_test, "y_test": y_test,
    }
