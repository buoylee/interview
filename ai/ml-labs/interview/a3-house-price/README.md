# A3 · 房价预测(tabular 回归)

## ① 这是什么 / 答哪道面试题

用 california housing 做回归,主线不是模型多强,而是**方法论**。
答的是面试官那句 *"你只会调 API,还是真懂 ML 基本功?"* —— train/val/test、过拟合、
正则、指标选择、数据泄漏,全部能用本 lab 的代码和产出说清楚。

## ② 白板故事

- **切分**:先切 test 锁起来,再从训练集切 val 调参;test 只在最后碰一次。
- **baseline**:先用"永远预测均值"定地板,任何模型至少要赢它。
- **过拟合**:把特征升到 3 次多项式、不加正则 → 165 个高度共线特征、系数失控,
  val RMSE 数值爆炸到 ~10³(外推灾难),train 不差但 val 崩。
- **正则**:同样的多项式换 Ridge(L2)→ val 从 ~1449 压回 ~70。但仍远差于 linear ——
  **正则只能缓解过度复杂,不能替代「选对复杂度」**;这题 linear 才是最优解。
- **指标**:RMSE 平方放大大误差、对高价房尾部敏感;MAE 看典型误差。按业务选。
- **数据泄漏**:任何由目标 y 派生、上线时拿不到的特征,都会让离线分数虚高 → 上线翻车。

## ③ 怎么跑

```bash
# 在 ai/ml-labs/ 下
uv sync --group tabular
uv run pytest interview/a3-house-price -v      # 8 passed
uv run python interview/a3-house-price/train.py
```

数据已 bundle(`data/california_housing.csv`),离线可跑。重新导出:
`uv run python interview/a3-house-price/prepare_data.py`(首次需联网)。

## ④ 产出

见 [`outputs/metrics.md`](outputs/metrics.md):各模型 train/val RMSE 对比表(含怎么读)、
test 上 RMSE vs MAE、数据泄漏前后对比,以及两张图(train/val RMSE 的 log 轴柱状图、
linear 的残差分布)。实测数字(seed=42):

| 模型 | val RMSE |
|---|---|
| baseline | 1.17 |
| linear(最优) | 0.73 |
| poly3 无正则 | 1449.9(爆炸) |
| poly3+ridge | 69.8 |

数据泄漏:诚实 0.73 → 泄漏 0.01(好得不真实)。

## ⑤ 面试追问(自检,不在这里学新东西)

- 为什么需要独立的 test 集,只有 train/val 不够吗?
- 怎么从 train/val 的 gap 判断过拟合还是欠拟合?
- L1 和 L2 正则的区别?各自什么时候用?
- 既然 ridge 能压过拟合,为什么这题还是 linear 最好?(复杂度 vs 正则)
- 什么时候该看 MAE 而不是 RMSE?反过来呢?
- 举一个你代码之外的真实数据泄漏例子,以及怎么防。

> 连回 roadmap:`ai/ml-to-llm-roadmap/01-ml-basics/`、`.../01-ml-basics/03-evaluation-tuning.md`。
