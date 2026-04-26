# Foundations 解锁层

> **定位**：这里不是默认主线，也不是旧 `00-03` 的替代品。默认先读 [Transformer 必要基础](../04-transformer-foundations/)；卡在数学、NLP 或神经网络前置概念时，再回到这里补一小块，补完立刻回主线。

## 什么时候来这里

| 你卡在哪里 | 先读 |
|------------|------|
| 向量、矩阵、点积、`QK^T` | [Transformer 最小数学](./math-for-transformer/) |
| logits、softmax、概率分布 | [Transformer 最小数学](./math-for-transformer/) |
| token、vocab、token id、embedding table | [Tokenization 与 Embedding 补课](./nlp-tokenization-embedding/) |
| 神经元、线性层、MLP、激活 | [Deep Learning 补课](./deep-learning/) |
| Residual、LayerNorm、FFN、GELU/SwiGLU | [Deep Learning 补课](./deep-learning/) |

## 推荐读法

1. 先读 [Transformer 必要基础](../04-transformer-foundations/)。
2. 只在主线卡住时进入对应 foundation 小文档。
3. 读完小文档后回到原 Transformer 章节。
4. 主线跑通后，再回读旧 `00-03` 深入资料。

## 和旧 `00-03` 的关系

旧 `00-03` 仍然有价值，但它们是解锁后的深入资料：

- [00 数学基础](../00-math-foundations/)：读完最小数学后，用来补线性代数、概率、微积分、信息论的完整直觉。
- [01 机器学习基础](../01-ml-basics/)：读完主线后，用来补训练、评估、泛化和传统 ML 语境。
- [02 深度学习基础](../02-deep-learning/)：读完 Deep Learning 补课后，用来补 CNN/RNN/Attention 演进脉络。
- [03 NLP、Embedding 与检索理论](../03-nlp-embedding-retrieval/)：读完 token/embedding 补课后，用来补文本表示、embedding 和检索理论。

## 不要怎么读

- 不要从这里横向扩散，把所有 foundation 一次性读完。
- 不要把旧 `00-03` 当成进入 Transformer 的硬性前置。
- 不要在第一次学习时追求公式推导完整性。

> 回到主线：[Transformer 必要基础](../04-transformer-foundations/)
