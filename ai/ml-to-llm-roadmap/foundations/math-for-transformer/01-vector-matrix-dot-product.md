# 向量、矩阵和点积

## 这篇解决什么卡点

读 [token 如何变成向量](../../04-transformer-foundations/02-token-to-vector.md) 时，最容易卡住的是：为什么一个词能变成一串数字，以及模型为什么能拿这些数字做比较。

读 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md) 时，另一个卡点是 `QK^T`：它看起来像数学符号，其实是在批量计算 token 之间的匹配分数。

## 先记住一句话

向量是一串代表对象的数字，矩阵可以改变向量的表示方式，点积可以当作两个向量的简单匹配分数。

## 最小例子

```text
q = [1, 0]
k1 = [1, 0] -> q · k1 = 1
k2 = [0, 1] -> q · k2 = 0
```

这里 `q` 和 `k1` 方向相同，匹配分数更高；`q` 和 `k2` 不对齐，匹配分数更低。

矩阵可以作用在一个向量上，把它变成另一种表示；也可以一次作用在很多向量上，比如把一批 token embedding 同时变成 Q、K、V。

## 这个概念在 Transformer 哪里出现

在 `02-token-to-vector` 里，token embedding 就是用向量表示 token。向量不是词本身，而是模型可以计算的数字表示。

在 `04-self-attention-qkv` 里，`QK^T` 会把每个 query 向量和每个 key 向量做点积，得到一个 token 对 token 的分数矩阵：每一格都表示“这个 token 有多想看那个 token”。

## 和旧资料的连接

这篇只保留读 Transformer 必要的直觉。如果想补完整线性代数背景，再读 [旧版线性代数基础](../../00-math-foundations/01-linear-algebra.md)。

## 自测

1. 向量为什么可以表示 token？
2. 点积为什么可以当作匹配分数？
3. `QK^T` 为什么会得到一个 token 对 token 的分数矩阵？

## 回到主线

回到 [token 如何变成向量](../../04-transformer-foundations/02-token-to-vector.md)，再继续读 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md)。
