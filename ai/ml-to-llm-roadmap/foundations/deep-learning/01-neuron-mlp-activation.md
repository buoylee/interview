# 神经元、MLP 与激活函数

## 这篇只解决什么

这篇只解释神经网络最小组件：线性层、偏置、激活函数、MLP。它不讲 Transformer Block、Pre-Norm、RMSNorm 或 SwiGLU，这些在后续 foundations 中单独讲。

## 你在主线哪里会用到

- [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)
- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)
- [FFN 与门控](./04-ffn-gating-for-transformer.md)

## 最小直觉

神经元先做加权求和，再用激活函数引入非线性。

```text
输入 x -> 线性变换 Wx + b -> 激活函数 -> 输出
```

没有激活函数，多层线性变换仍然等价于一层线性变换，网络无法表达复杂关系。

## 最小公式

```text
z = Wx + b
h = f(z)
```

- `x`：输入向量。
- `W`：权重矩阵。
- `b`：偏置。
- `f`：激活函数。
- `h`：输出向量。

## 逐步例子

```text
输入: [价格, 评分]
线性层: 0.8 * 价格 + 1.2 * 评分 - 0.5
激活: ReLU 只保留正值
输出: 一个新的特征
```

MLP 把多个这样的层堆起来，让模型从简单特征组合出复杂特征。

## 常见误解

| 误解 | 修正 |
|------|------|
| 神经元像生物大脑一样工作 | 工程上可以先理解为可学习的数学函数 |
| 层数越多一定越好 | 更深需要 Residual、Norm 和足够数据支撑 |
| 激活函数只是装饰 | 没有非线性，多层网络会退化成一层线性模型 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 FFN 为什么本质上是 MLP。
