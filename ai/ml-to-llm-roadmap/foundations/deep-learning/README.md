# Deep Learning 补课

> **定位**：这里不是重新学完整深度学习，而是补齐读 Transformer 时最容易卡住的神经网络基础。主线遇到不懂再回来查，不需要一开始全部读完。

## 什么时候需要回来补

| 你卡在哪里 | 先读 |
|------------|------|
| 不理解向量、线性层、MLP、激活函数 | [01-neuron-mlp-activation.md](./01-neuron-mlp-activation.md) |
| 不理解为什么深层网络难训练 | [02-backprop-gradient-problems.md](./02-backprop-gradient-problems.md) |
| 不理解 Residual、LayerNorm、RMSNorm、初始化 | [03-normalization-residual-initialization.md](./03-normalization-residual-initialization.md) |
| 不理解 FFN、GELU、SwiGLU 为什么出现在 Transformer 里 | [04-ffn-gating-for-transformer.md](./04-ffn-gating-for-transformer.md) |

## 推荐读法

1. 先走 [Transformer 必要基础](../../04-transformer-foundations/)。
2. 遇到不懂的概念，再按上表回到对应补课材料。
3. 补完后回到原来的 Transformer 章节，不要在 foundation 里横向扩散。

## 读完后你应该能解释

- 一个神经元、线性层和 MLP 的关系。
- 激活函数为什么让网络具备非线性表达能力。
- 反向传播为什么依赖链式法则，梯度消失/爆炸为什么会影响深层网络。
- Residual、Normalization 和初始化如何帮助 Transformer 堆深。
- FFN 和门控激活为什么是 Transformer block 的重要组成部分。

> ⬅️ [返回 Transformer 必要基础](../../04-transformer-foundations/)
