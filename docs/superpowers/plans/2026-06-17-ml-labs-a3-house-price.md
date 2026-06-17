# ml-labs 脚手架 + A3 房价预测 Lab 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭起 `ai/ml-labs/` 共享 uv 脚手架,并实现第一个可跑可测的面试 lab —— A3 房价回归(讲透 ML 基本功 + 数据泄漏坑)。

**Architecture:** 一个共享 uv 虚拟工程(`ai/ml-labs/`,`package=false`)用 dependency groups 按需装依赖;A3 lab 拆成小模块(dataio / metrics / model / leakage)各自单测,`train.py` 编排出 commit 进库的产物(指标表 + 图)。纯 sklearn,确定性(固定 seed),离线(数据 bundle 成 CSV)。

**Tech Stack:** Python 3.11、uv 0.7.13、scikit-learn、numpy、pandas、matplotlib、pytest。仅 Apple M4 / MPS,本 lab 不用 torch。

---

## 范围说明

本计划只覆盖 **共享脚手架 + A3**。A2(意图识别)、A1(tiny-GPT)、B1/B2/B3 各自出独立计划。完成判定:`uv run pytest` 全绿 + `train.py` 产出已 commit + README 五段齐全 + roadmap 已链接。

## 文件结构(本计划新建/修改)

```
ai/ml-labs/
  pyproject.toml                       # 新建:uv 虚拟工程 + dependency groups
  .gitignore                           # 新建:忽略 venv/pycache/权重
  README.md                            # 新建:两轨地图 + 面试故事索引
  robotics/README.md                   # 新建:robotics 轨占位横幅
  interview/a3-house-price/
    conftest.py                        # 新建:把 lab 目录加入 sys.path
    dataio.py                          # 新建:加载 CSV + 切分
    metrics.py                         # 新建:rmse / mae
    model.py                           # 新建:baseline/linear/poly/ridge
    leakage.py                         # 新建:target leakage 演示
    prepare_data.py                    # 新建:一次性导出 california housing CSV
    train.py                           # 新建:编排 + 写 outputs/
    README.md                          # 新建:五段(含面试故事)
    data/california_housing.csv        # 新建(commit):bundle 数据集
    outputs/metrics.md + *.png         # 新建(commit):产物
    tests/test_dataio.py               # 新建
    tests/test_metrics.py              # 新建
    tests/test_model.py                # 新建
    tests/test_leakage.py              # 新建
ai/ml-to-llm-roadmap.md                # 修改:加「动手实验」入口
ai/README.md                           # 修改:登记 ml-labs/
```

> 所有 `uv` / `pytest` 命令都从 `ai/ml-labs/` 目录下运行(确保 uv 找到本工程的 pyproject)。

---

## Task 1: 搭共享脚手架 `ai/ml-labs/`

**Files:**
- Create: `ai/ml-labs/pyproject.toml`
- Create: `ai/ml-labs/.gitignore`
- Create: `ai/ml-labs/README.md`
- Create: `ai/ml-labs/robotics/README.md`

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[project]
name = "ml-labs"
version = "0.1.0"
description = "Runnable ML training labs — interview track (A) + robotics track (B)"
requires-python = ">=3.11"
dependencies = [
    "numpy",
    "pandas",
    "matplotlib",
]

# 按需安装:uv sync --group tabular(会自动带上默认 dev 组)
[dependency-groups]
dev = ["pytest"]
tabular = ["scikit-learn"]
nlp = ["torch", "transformers", "datasets", "scikit-learn", "sentence-transformers"]
gpt = ["torch"]
vision = ["torch", "torchvision"]
audio = ["openai-whisper"]

[tool.uv]
package = false
```

- [ ] **Step 2: 写 `.gitignore`**

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.pt
*.pth
*.ckpt
# 模型权重不入库;数据 CSV 和 outputs/ 要入库,故不忽略
```

- [ ] **Step 3: 写 `README.md`(两轨地图)**

```markdown
# ML 动手训练 Labs

> 为面试补「能跑、能训出模型」的 runnable 作品。设计见 `docs/superpowers/specs/2026-06-17-ml-training-labs-design.md`。
> 全部在 Apple M4 / 16GB / MPS 上几分钟内可跑;离线、固定 seed。

## 怎么跑

```bash
# 在本目录(ai/ml-labs/)下
uv sync --group tabular          # 装某个 lab 需要的依赖组
uv run pytest interview/a3-house-price -v
uv run python interview/a3-house-price/train.py
```

依赖组:`tabular`(A3)、`nlp`(A2)、`gpt`(A1)、`vision`(B1)、`audio`(B2)。

## Track A —— 面试核心

| Lab | 一句话面试故事 | 状态 |
|---|---|---|
| [A3 房价回归](interview/a3-house-price/) | 讲透 train/val/test、过拟合、正则、RMSE vs MAE、数据泄漏 | ✅ |
| A2 意图识别 | embedding+轻分类器 vs 微调 DistilBERT,何时不该用 LLM | ⏳ |
| A1 tiny-GPT 从零 | 手写 attention,Mac 上训出会生成文字的 decoder-only | ⏳ |

## Track B —— Robotics / Embodied AI

见 [robotics/](robotics/) —— ⚠️ 非当前面试,长线兴趣。
```

- [ ] **Step 4: 写 `robotics/README.md`(占位横幅)**

```markdown
# 🤖 Robotics / Embodied AI 轨

> ⚠️ **非当前面试** —— 这一轨服务长线的 humanoid / embodied AI 兴趣,与「现在面 AI Engineer」的核心(Track A)分开。

规划中的 lab(各自出独立计划后填充):

- **B1 图像/物体识别** —— 迁移学习微调 ResNet,机器人感知入门。
- **B2 语音回路** —— Whisper(STT)+ 开源 TTS,人机语音接口(整合,不训练 TTS)。
- **B3 RL / 模仿学习 / VLA 路标** —— embodied AI 真正的训练范式地图;A1(transformer)+ B1(感知)是其前置。
```

- [ ] **Step 5: 验证环境可建**

Run(在 `ai/ml-labs/` 下):
```bash
uv sync --group tabular
uv run python -c "import numpy, pandas, matplotlib, sklearn; print('env ok')"
```
Expected: 末行打印 `env ok`(首次会创建 `.venv/` 并解析依赖)。

- [ ] **Step 6: Commit**

```bash
git add ai/ml-labs/pyproject.toml ai/ml-labs/.gitignore ai/ml-labs/README.md ai/ml-labs/robotics/README.md
git commit -m "ml-labs:搭共享 uv 脚手架 + 两轨 README"
```

---

## Task 2: A3 数据层(`dataio.py` + 导出 CSV)

**Files:**
- Create: `ai/ml-labs/interview/a3-house-price/conftest.py`
- Create: `ai/ml-labs/interview/a3-house-price/dataio.py`
- Create: `ai/ml-labs/interview/a3-house-price/prepare_data.py`
- Create: `ai/ml-labs/interview/a3-house-price/tests/test_dataio.py`
- Create(commit): `ai/ml-labs/interview/a3-house-price/data/california_housing.csv`

- [ ] **Step 1: 写 `conftest.py`(让测试能 import lab 模块)**

```python
import os
import sys

# 把 lab 目录加入 sys.path,使 `from dataio import ...` 在 tests/ 下可用
sys.path.insert(0, os.path.dirname(__file__))
```

- [ ] **Step 2: 写失败测试 `tests/test_dataio.py`**

```python
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
    assert np.array_equal(a["y_test"], b["y_test"])
```

- [ ] **Step 3: 运行测试确认失败**

Run(在 `ai/ml-labs/` 下):`uv run pytest interview/a3-house-price/tests/test_dataio.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'dataio'`。

- [ ] **Step 4: 写 `dataio.py`**

```python
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
```

- [ ] **Step 5: 写 `prepare_data.py`(一次性导出 CSV)**

```python
"""一次性把 sklearn 的 california housing 导出成本地 CSV(之后完全离线)。
首次运行需要网络(sklearn 会下载并缓存数据集)。"""
from pathlib import Path

from sklearn.datasets import fetch_california_housing


def main():
    data = fetch_california_housing(as_frame=True)
    df = data.frame  # 含 8 个特征 + 目标列 MedHouseVal
    out = Path(__file__).parent / "data" / "california_housing.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows, {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 运行 `prepare_data.py` 生成 CSV**

Run(在 `ai/ml-labs/` 下):`uv run python interview/a3-house-price/prepare_data.py`
Expected: 打印 `wrote .../data/california_housing.csv (20640 rows, 9 cols)`。

- [ ] **Step 7: 运行测试确认通过**

Run:`uv run pytest interview/a3-house-price/tests/test_dataio.py -v`
Expected: 2 passed。

- [ ] **Step 8: Commit**

```bash
git add ai/ml-labs/interview/a3-house-price/conftest.py \
        ai/ml-labs/interview/a3-house-price/dataio.py \
        ai/ml-labs/interview/a3-house-price/prepare_data.py \
        ai/ml-labs/interview/a3-house-price/tests/test_dataio.py \
        ai/ml-labs/interview/a3-house-price/data/california_housing.csv
git commit -m "a3:数据层 dataio + bundle california housing CSV"
```

---

## Task 3: A3 指标层(`metrics.py`)

**Files:**
- Create: `ai/ml-labs/interview/a3-house-price/metrics.py`
- Create: `ai/ml-labs/interview/a3-house-price/tests/test_metrics.py`

- [ ] **Step 1: 写失败测试 `tests/test_metrics.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run:`uv run pytest interview/a3-house-price/tests/test_metrics.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'metrics'`。

- [ ] **Step 3: 写 `metrics.py`**

```python
import numpy as np


def rmse(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))
```

- [ ] **Step 4: 运行确认通过**

Run:`uv run pytest interview/a3-house-price/tests/test_metrics.py -v`
Expected: 3 passed。

- [ ] **Step 5: Commit**

```bash
git add ai/ml-labs/interview/a3-house-price/metrics.py \
        ai/ml-labs/interview/a3-house-price/tests/test_metrics.py
git commit -m "a3:指标层 rmse/mae + 单测"
```

---

## Task 4: A3 模型层(`model.py`:baseline/linear/poly/ridge)

**Files:**
- Create: `ai/ml-labs/interview/a3-house-price/model.py`
- Create: `ai/ml-labs/interview/a3-house-price/tests/test_model.py`

- [ ] **Step 1: 写失败测试 `tests/test_model.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run:`uv run pytest interview/a3-house-price/tests/test_model.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'model'`。

- [ ] **Step 3: 写 `model.py`**

```python
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
```

> 备注:若 `test_ridge_reduces_overfit_gap` 偶发不过(ridge 没压住),把 `fit_ridge_poly` 的 `alpha` 调大(如 50.0)即可;这是确定性数据,调一次定值即可。

- [ ] **Step 4: 运行确认通过**

Run:`uv run pytest interview/a3-house-price/tests/test_model.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add ai/ml-labs/interview/a3-house-price/model.py \
        ai/ml-labs/interview/a3-house-price/tests/test_model.py
git commit -m "a3:模型层 baseline/linear/poly/ridge + 过拟合对比测试"
```

---

## Task 5: A3 数据泄漏演示(`leakage.py`)

**Files:**
- Create: `ai/ml-labs/interview/a3-house-price/leakage.py`
- Create: `ai/ml-labs/interview/a3-house-price/tests/test_leakage.py`

- [ ] **Step 1: 写失败测试 `tests/test_leakage.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run:`uv run pytest interview/a3-house-price/tests/test_leakage.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'leakage'`。

- [ ] **Step 3: 写 `leakage.py`**

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run:`uv run pytest interview/a3-house-price/tests/test_leakage.py -v`
Expected: 1 passed。

- [ ] **Step 5: Commit**

```bash
git add ai/ml-labs/interview/a3-house-price/leakage.py \
        ai/ml-labs/interview/a3-house-price/tests/test_leakage.py
git commit -m "a3:target leakage 演示 + 单测"
```

---

## Task 6: A3 编排 `train.py` + 产物 + README

**Files:**
- Create: `ai/ml-labs/interview/a3-house-price/train.py`
- Create(commit): `ai/ml-labs/interview/a3-house-price/outputs/metrics.md`
- Create(commit): `ai/ml-labs/interview/a3-house-price/outputs/train_val_rmse.png`
- Create(commit): `ai/ml-labs/interview/a3-house-price/outputs/residuals.png`
- Create: `ai/ml-labs/interview/a3-house-price/README.md`

- [ ] **Step 1: 写 `train.py`**

```python
"""A3 房价回归:从 baseline 到正则,演示过拟合、指标选择、数据泄漏。
跑完写出 outputs/metrics.md + 两张图。确定性(固定 seed)。"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示后端,直接存图
import matplotlib.pyplot as plt
import numpy as np

from dataio import load_housing, make_splits
from leakage import honest_val_rmse, leaky_val_rmse
from metrics import mae, rmse
from model import baseline_predict, fit_linear, fit_poly, fit_ridge_poly

HERE = Path(__file__).parent
CSV = HERE / "data" / "california_housing.csv"
OUT = HERE / "outputs"


def main():
    OUT.mkdir(exist_ok=True)
    X, y, _ = load_housing(CSV)
    s = make_splits(X, y, seed=42)

    rows = []
    b_tr = rmse(s["y_train"], baseline_predict(s["y_train"], len(s["y_train"])))
    b_va = rmse(s["y_val"], baseline_predict(s["y_train"], len(s["y_val"])))
    rows.append(("baseline(mean)", b_tr, b_va))

    models = {
        "linear": fit_linear(s),
        "poly3(no reg)": fit_poly(s),
        "poly3+ridge": fit_ridge_poly(s),
    }
    for name, m in models.items():
        tr = rmse(s["y_train"], m.predict(s["X_train"]))
        va = rmse(s["y_val"], m.predict(s["X_val"]))
        rows.append((name, tr, va))

    lin = models["linear"]
    t_rmse = rmse(s["y_test"], lin.predict(s["X_test"]))
    t_mae = mae(s["y_test"], lin.predict(s["X_test"]))

    honest = honest_val_rmse(s)
    leaky = leaky_val_rmse(s)

    # 图1:各模型 train vs val RMSE
    names = [r[0] for r in rows]
    tr_vals = [r[1] for r in rows]
    va_vals = [r[2] for r in rows]
    x = np.arange(len(names))
    width = 0.35
    plt.figure(figsize=(8, 4))
    plt.bar(x - width / 2, tr_vals, width, label="train")
    plt.bar(x + width / 2, va_vals, width, label="val")
    plt.xticks(x, names, rotation=20)
    plt.ylabel("RMSE")
    plt.title("train vs val RMSE(过拟合与正则)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "train_val_rmse.png", dpi=120)
    plt.close()

    # 图2:linear 在 test 上的残差分布
    resid = s["y_test"] - lin.predict(s["X_test"])
    plt.figure(figsize=(6, 4))
    plt.hist(resid, bins=40)
    plt.xlabel("residual (true - pred)")
    plt.ylabel("count")
    plt.title("Test residuals (linear)")
    plt.tight_layout()
    plt.savefig(OUT / "residuals.png", dpi=120)
    plt.close()

    # metrics.md
    lines = [
        "# A3 房价预测 · 结果", "",
        "> 由 `train.py` 生成,固定 seed,可复现。", "",
        "## train vs val RMSE", "",
        "| 模型 | train RMSE | val RMSE | gap(val-train) |",
        "|---|---|---|---|",
    ]
    for name, t, v in rows:
        lines.append(f"| {name} | {t:.4f} | {v:.4f} | {v - t:+.4f} |")
    lines += [
        "", "gap 越大越过拟合:`poly3(no reg)` gap 最大,`poly3+ridge` 被正则压回。", "",
        "## 最终模型(linear)在 test 上", "",
        f"- RMSE = {t_rmse:.4f}",
        f"- MAE  = {t_mae:.4f}", "",
        "RMSE 比 MAE 大,因为平方放大了少数大误差(高价房尾部)。"
        "关心典型误差选 MAE,想重罚大错选 RMSE。", "",
        "## 数据泄漏演示(target leakage)", "",
        f"- 诚实管线 val RMSE = {honest:.4f}",
        f"- 泄漏管线 val RMSE = {leaky:.4f}(混入了从 y 派生的特征)", "",
        "泄漏管线分数好得不真实 —— 上线即翻车。面试要能一眼认出这种坑。", "",
        "![train vs val](train_val_rmse.png)", "",
        "![residuals](residuals.png)", "",
    ]
    (OUT / "metrics.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT / "metrics.md")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑 `train.py` 生成产物**

Run(在 `ai/ml-labs/` 下):`uv run python interview/a3-house-price/train.py`
Expected: 打印 `wrote .../outputs/metrics.md`,且 `outputs/` 下出现 `metrics.md`、`train_val_rmse.png`、`residuals.png`。

- [ ] **Step 3: 写 `README.md`(五段)**

````markdown
# A3 · 房价预测(tabular 回归)

## ① 这是什么 / 答哪道面试题

用 california housing 做回归,主线不是模型多强,而是**方法论**。
答的是面试官那句 *"你只会调 API,还是真懂 ML 基本功?"* —— train/val/test、过拟合、
正则、指标选择、数据泄漏,全部能用本 lab 的代码和产出说清楚。

## ② 白板故事

- **切分**:先切 test 锁起来,再从训练集切 val 调参;test 只在最后碰一次。
- **baseline**:先用"永远预测均值"定地板,任何模型至少要赢它。
- **过拟合**:把特征升到 3 次多项式、不加正则 → train RMSE 降但 val RMSE 升、gap 拉大。
- **正则**:同样的多项式换 Ridge(L2)→ gap 被压回,val 反而更好。
- **指标**:RMSE 平方放大大误差、对高价房尾部敏感;MAE 看典型误差。按业务选。
- **数据泄漏**:任何由目标 y 派生、上线时拿不到的特征,都会让离线分数虚高 → 上线翻车。

## ③ 怎么跑

```bash
# 在 ai/ml-labs/ 下
uv sync --group tabular
uv run pytest interview/a3-house-price -v      # 全绿
uv run python interview/a3-house-price/train.py
```

数据已 bundle(`data/california_housing.csv`),离线可跑。重新导出:
`uv run python interview/a3-house-price/prepare_data.py`(首次需联网)。

## ④ 产出

见 [`outputs/metrics.md`](outputs/metrics.md):各模型 train/val RMSE 对比表、
test 上 RMSE vs MAE、数据泄漏前后对比,以及两张图(过拟合柱状图、残差分布)。

## ⑤ 面试追问(自检,不在这里学新东西)

- 为什么需要独立的 test 集,只有 train/val 不够吗?
- 怎么从 train/val 的 gap 判断过拟合还是欠拟合?
- L1 和 L2 正则的区别?各自什么时候用?
- 什么时候该看 MAE 而不是 RMSE?反过来呢?
- 举一个你代码之外的真实数据泄漏例子,以及怎么防。

> 连回 roadmap:`ai/ml-to-llm-roadmap/01-ml-basics/`、`.../01-ml-basics/03-evaluation-tuning.md`。
````

- [ ] **Step 4: 验证测试整体仍全绿**

Run:`uv run pytest interview/a3-house-price -v`
Expected: 8 passed(dataio 2 + metrics 3 + model 2 + leakage 1)。

- [ ] **Step 5: Commit**

```bash
git add ai/ml-labs/interview/a3-house-price/train.py \
        ai/ml-labs/interview/a3-house-price/README.md \
        ai/ml-labs/interview/a3-house-price/outputs/
git commit -m "a3:train.py 编排 + 产物入库 + README 五段"
```

---

## Task 7: 集成进 roadmap

**Files:**
- Modify: `ai/ml-to-llm-roadmap.md`(在「迁移成果」表后加一节)
- Modify: `ai/README.md`(顶层目录登记)

- [ ] **Step 1: 在 `ai/ml-to-llm-roadmap.md` 加「动手实验」入口**

在 `## 面试冲刺路径` 这一节标题**之前**插入:

```markdown
## 动手实验(ml-labs)

理论之外的 runnable 作品,补「能训出模型」的缺口。详见 [ai/ml-labs/](./ml-labs/)。

| Lab | 一句话面试故事 | 连回模块 | 状态 |
|---|---|---|---|
| [A3 房价回归](./ml-labs/interview/a3-house-price/) | train/val/test、过拟合、正则、RMSE vs MAE、数据泄漏 | 01-ml-basics | ✅ |
| A2 意图识别 | 何时不该用 LLM(router/guardrail) | 02-agent-tool-use | ⏳ |
| A1 tiny-GPT 从零 | 手写 attention,Mac 上训出生成模型 | 04-transformer-foundations | ⏳ |
| Robotics 轨 | 感知 / 语音 / RL 路标(非当前面试) | —— | ⏳ |
```

- [ ] **Step 2: 在 `ai/README.md` 登记 `ml-labs/`**

找到 `ai/README.md` 中列举 `ai/` 子目录的位置(如有目录表/列表),加入一行:

```markdown
- `ml-labs/` —— 动手训练 labs(面试核心 A 轨 + robotics B 轨),runnable 产物
```

> 若 `ai/README.md` 没有现成的目录清单,则在文件末尾新增一个 `## 子项目` 小节,只放上面这一行。

- [ ] **Step 3: Commit**

```bash
git add ai/ml-to-llm-roadmap.md ai/README.md
git commit -m "roadmap:登记 ml-labs 动手实验入口"
```

---

## Self-Review 结果

**Spec 覆盖**:脚手架(§5)→ Task 1;A3 内容要点(§6:baseline/split/过拟合/正则/指标/泄漏)→ Task 2-6;离线确定性(§2)→ bundle CSV + 固定 seed;产物入库(§5 决定2)→ Task 6;roadmap 集成(§8)→ Task 7。A2/A1/B* 明确划到后续独立计划。✅ 无遗漏。

**占位符扫描**:无 TBD/TODO;每个改代码的步骤都给了完整代码与期望输出。✅

**类型一致性**:`make_splits` 返回的 dict key(`X_train/y_train/X_val/y_val/X_test/y_test`)在 model/leakage/train 全程一致;`load_housing` 返回三元组、`val_rmse(model, splits)` 签名在 model.py 定义并在 test_model 使用一致;模块名用 `dataio`(非 `data`)以避免与 `data/` 目录冲突。✅
