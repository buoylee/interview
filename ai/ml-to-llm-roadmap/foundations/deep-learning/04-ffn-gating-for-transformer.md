# Transformer FFN、GELU 与 SwiGLU

## 这篇只解决什么

这篇解释 Transformer 里的 FFN 为什么存在，以及 GELU、GLU、SwiGLU 这类激活和门控为什么常见。它不重新讲 Self-Attention。

## 你在主线哪里会用到

- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)

## 最小直觉

Attention 让 token 之间交换信息，FFN 让每个 token 独立加工刚读到的信息。

```text
Attention = token 之间交流
FFN = 每个 token 自己消化
```

## 最小公式

标准 FFN:

```text
FFN(x) = W2 * activation(W1 * x + b1) + b2
```

SwiGLU 风格:

```text
FFN(x) = W2 * (SiLU(W1 * x) elementwise_multiply (V * x))
```

## 逐步例子

```text
输入 token 表示
-> 扩维到更大的隐藏维度
-> 非线性激活或门控
-> 投回原维度
```

扩维给模型更多加工空间，投回原维度保证可以继续和 residual 相加。

## 常见误解

| 误解 | 修正 |
|------|------|
| Transformer 只有 Attention 重要 | FFN 通常占大量参数和计算 |
| GELU/SwiGLU 是面试背诵细节 | 它们影响模型表达能力和训练效果 |
| 门控就是 if/else | 门控是连续的逐元素调节，不是硬规则 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 FFN 在 block 中的位置和作用。
