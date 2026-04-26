# Transformer 最小数学

> **定位**：这里不是完整数学课，只解决读 Transformer 时最容易卡住的几个数学动作：向量、矩阵、点积、logits、softmax 和 Attention 公式。

## 默认学习顺序

1. [向量、矩阵和点积](./01-vector-matrix-dot-product.md)
2. [Logits、Softmax 与概率分布](./02-logits-softmax-probability.md)
3. [Attention 公式的最小数学拆解](./03-attention-math-minimal.md)

## 什么时候读

| 你在主线哪里卡住 | 先读 |
|------------------|------|
| `02-token-to-vector` 里不理解向量和矩阵 | [向量、矩阵和点积](./01-vector-matrix-dot-product.md) |
| `04-self-attention-qkv` 里不理解 `QK^T` | [向量、矩阵和点积](./01-vector-matrix-dot-product.md) |
| 不理解 softmax 为什么输出权重 | [Logits、Softmax 与概率分布](./02-logits-softmax-probability.md) |
| 看见 `softmax(QK^T / sqrt(d_k))V` 就断掉 | [Attention 公式的最小数学拆解](./03-attention-math-minimal.md) |

## 和旧数学资料的关系

读完这里后，如果想补完整数学直觉，再回到：

- [旧版线性代数基础](../../00-math-foundations/01-linear-algebra.md)
- [旧版概率基础](../../00-math-foundations/02-probability.md)

微积分和信息论可以等到训练、损失函数、KL/RLHF 等主题时再读。

> 回到主线：[Transformer 必要基础](../../04-transformer-foundations/)
