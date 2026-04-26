# Attention 公式的最小数学拆解

## 这篇解决什么卡点

读 [为什么 Attention 需要上下文](../../04-transformer-foundations/03-why-attention-needs-context.md) 时，直觉上能理解“词要看上下文”。但读到 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md) 时，`softmax(QK^T / sqrt(d_k))V` 很容易让人断掉。

这篇只把公式拆成动作，不做完整推导。

## 先记住一句话

Attention 先算“该看谁”的分数，再把分数变成读取比例，最后按比例混合真正的内容向量。

## 最小例子

```text
query token: "苹果"
context tokens: ["发布", "吃"]
如果 "苹果" 更像公司，attention 可能更看 "发布"。
如果 "苹果" 更像水果，attention 可能更看 "吃"。
```

这里的重点不是模型真的理解了中文词典，而是当前 token 会根据上下文，给不同 token 分配不同读取权重。

## 这个概念在 Transformer 哪里出现

`softmax(QK^T / sqrt(d_k))V` 可以拆成四步：

1. `QK^T` computes matching scores.
2. `/ sqrt(d_k)` keeps score scale stable.
3. `softmax` turns scores into read weights.
4. multiplying by `V` mixes content vectors.

每一行 attention weights 都表示一个 token 在决定“我要从所有 token 各读多少”。因为经过 softmax，每一行权重都非负且总和为 1，所以它像一组读取比例。

乘以 `V` 之后，模型才真正把被读取 token 的内容向量按权重混合起来，得到当前 token 的新表示。

## 和旧资料的连接

这篇只服务于读懂 Attention 公式。点积和矩阵乘法的完整背景可以看 [旧版线性代数基础](../../00-math-foundations/01-linear-algebra.md)，softmax 和概率分布的背景可以看 [旧版概率基础](../../00-math-foundations/02-probability.md)。

## 自测

1. Attention scores 和 attention weights 有什么区别？
2. 为什么每一行权重和为 1？
3. 为什么乘以 `V` 才得到输出内容？

## 回到主线

回到 [为什么 Attention 需要上下文](../../04-transformer-foundations/03-why-attention-needs-context.md)，再继续读 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md)。
