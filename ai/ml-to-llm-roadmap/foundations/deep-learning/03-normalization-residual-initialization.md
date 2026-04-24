# Normalization、Residual 与初始化

## 这篇只解决什么

这篇解释深层网络稳定训练的三个基础零件：Residual Connection、Normalization、权重初始化。目标是为 Transformer Block 做铺垫。

## 你在主线哪里会用到

- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)
- [Decoder-only 与逐 Token 生成](../../04-transformer-foundations/05-decoder-only-and-generation.md)

## 最小直觉

深层网络难训练，是因为信号和梯度穿过很多层后容易变形。Residual 保留原信息，Normalization 稳定数值尺度，初始化让训练从合理状态开始。

## 最小公式

Residual:

```text
y = x + F(x)
```

LayerNorm:

```text
normalized_x = (x - mean(x)) / std(x)
```

RMSNorm:

```text
normalized_x = x / rms(x)
```

## 逐步例子

```text
没有 Residual:
x -> F1 -> F2 -> F3 -> 输出
每层都可能丢失原信息

有 Residual:
x -> x + F1(x) -> 继续
原信息始终有直达路径
```

Pre-Norm 把 Norm 放在 Attention/FFN 前面，通常比 Post-Norm 更容易训练深层模型。

## 常见误解

| 误解 | 修正 |
|------|------|
| Residual 只是把输入加回来 | 它同时改善信息流和梯度流 |
| BN 和 LN 可以随便替换 | Transformer 更适合 LN/RMSNorm，因为它不依赖 batch 统计 |
| RMSNorm 是完全不同的机制 | 它是更轻量的归一化方式，省掉均值中心化 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 Pre-Norm、Residual 和 RMSNorm 如何组成现代 LLM block。
