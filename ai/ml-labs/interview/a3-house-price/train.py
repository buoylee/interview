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

    # 图1:各模型 train vs val RMSE。poly 无正则的 val 会数值爆炸(~10^3),
    # 故用 log 轴,否则其他柱子被压成看不见。
    names = [r[0] for r in rows]
    tr_vals = [r[1] for r in rows]
    va_vals = [r[2] for r in rows]
    x = np.arange(len(names))
    width = 0.35
    plt.figure(figsize=(8, 4))
    plt.bar(x - width / 2, tr_vals, width, label="train")
    plt.bar(x + width / 2, va_vals, width, label="val")
    plt.yscale("log")
    plt.ylim(bottom=0.1)
    plt.xticks(x, names, rotation=20)
    plt.ylabel("RMSE (log scale)")
    plt.title("train vs val RMSE (log scale: overfit & regularization)")
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
        "",
        "怎么读这张表:",
        "",
        "- **baseline**:永远预测均值,train≈val,是任何模型要赢过的地板。",
        "- **linear**:train/val 都最低且接近 —— 复杂度刚好,**它才是这题的最优解**。",
        "- **poly3(no reg)**:3 次多项式把 8 个特征炸成 165 个高度共线的特征,无正则的线性回归"
        "系数失控,val RMSE 数值爆炸到 ~10^3(外推灾难)。train 不算差但 val 崩 = 教科书级过拟合。",
        "- **poly3+ridge**:同样的多项式加 L2 正则,把 val 从 ~1449 压回 ~70 —— 正则**缓解**了过度复杂,"
        "但仍远差于 linear。**资深结论:正则不能替代「选对模型复杂度」**;先把复杂度配对问题,再谈调正则。",
        "",
        "## 最终模型(linear)在 test 上", "",
        f"- RMSE = {t_rmse:.4f}",
        f"- MAE  = {t_mae:.4f}", "",
        "RMSE 比 MAE 大,因为平方放大了少数大误差(高价房尾部)。"
        "关心典型误差选 MAE,想重罚大错选 RMSE。", "",
        "## 数据泄漏演示(target leakage)", "",
        f"- 诚实管线 val RMSE = {honest:.4f}",
        f"- 泄漏管线 val RMSE = {leaky:.4f}(混入了从 y 派生的特征)", "",
        "泄漏管线分数好得不真实 —— 上线即翻车。面试要能一眼认出这种坑:"
        "任何「上线时拿不到、却由目标推导出来」的特征都是泄漏。", "",
        "![train vs val](train_val_rmse.png)", "",
        "![residuals](residuals.png)", "",
    ]
    (OUT / "metrics.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT / "metrics.md")


if __name__ == "__main__":
    main()
