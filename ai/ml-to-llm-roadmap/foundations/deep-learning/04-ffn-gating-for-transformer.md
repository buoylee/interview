# Transformer FFN、GELU 与 SwiGLU

## 这篇只解决什么

这篇解释 Transformer 里的 FFN 为什么存在，以及 GELU、GLU、SwiGLU 这类激活和门控为什么常见。它不重新讲 Self-Attention。

## 你在主线哪里会用到

- [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)

## 最小直觉

Attention 让 token 之间交换信息，FFN 让每个 token 独立加工刚读到的信息。

```text
Attention = token 之间交流
FFN = 每个 token 自己消化
```

GELU 是 Transformer FFN 中常见的平滑激活函数。和 ReLU 直接把负数变成 0 不同，GELU 会把小的负值柔和压低，而不是硬切掉。

GLU 把 FFN 拆成信息分支和门控分支。信息分支提供要传递的内容，门控分支用连续数值逐元素调节信息分支。SwiGLU 是现代 LLM 常见的 gated FFN 变体，用 SiLU/Swish 风格的 gate 做连续乘法调节；这个 gate 是连续乘法因子，不一定限制在 0 到 1。

## 最小公式

标准 FFN:

```text
FFN(x) = W2 * activation(W1 * x + b1) + b2
```

GELU 直觉公式:

```text
GELU(x) ~= x * Phi(x)
```

GLU 风格:

```text
GLU(x) = A(x) elementwise_multiply sigmoid(B(x))
```

SwiGLU 风格:

```text
FFN(x) = W_down * (SiLU(W_gate * x) elementwise_multiply (W_up * x))
```

- `Phi(x)`：标准正态分布的累积分布值，可以理解为连续保留比例。
- `A(x)`：GLU 里的信息分支。
- `B(x)`：GLU 里的门控分支。
- `W_gate`、`W_up`、`W_down`：FFN projection matrices，不是 Attention 里的 K/V。
- `W_gate * x`：SwiGLU 的门控分支。
- `W_up * x`：SwiGLU 的信息分支。
- `W_down`：把中间维度投回原维度，方便继续 residual 相加。
- `elementwise_multiply`：逐元素相乘，不是矩阵乘法。

## 逐步例子

```text
输入 token 表示
-> 扩维到更大的隐藏维度
-> 非线性激活或门控
-> 投回原维度
```

扩维给模型更多加工空间，投回原维度保证可以继续和 residual 相加。

用 GLU/SwiGLU 时，可以把中间加工看成两路信号：一路产生候选内容，另一路产生连续 gate。SwiGLU 的 gate 是逐元素乘法因子，不是 if/else，也不一定像 sigmoid 一样被限制在 0 到 1。

## 常见误解

| 误解 | 修正 |
|------|------|
| Transformer 只有 Attention 重要 | FFN 通常占大量参数和计算 |
| GELU/SwiGLU 是面试背诵细节 | 它们影响模型表达能力和训练效果 |
| 门控就是 if/else | 门控是连续的逐元素调节，不是硬规则 |
| GLU 和普通激活函数一样只处理一条分支 | GLU 有信息分支和 gate 分支，gate 会调制信息分支 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)，理解 FFN 在 block 中的位置和作用。
