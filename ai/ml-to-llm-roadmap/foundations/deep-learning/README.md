# Deep Learning 补课

> **定位**：这是一个补课 layer，不是第一默认路线。默认路径是先走 [Transformer mainline](../../04-transformer-foundations/)；遇到卡点时进入对应 foundation page；补完后回到原来的 lesson。

## 什么时候需要回来补

下面四页按依赖顺序排列：

| 你卡在哪里 | 先读 |
|------------|------|
| 1. 不理解 Neuron、MLP、activation | [01-neuron-mlp-activation.md](./01-neuron-mlp-activation.md) |
| 2. 不理解 Backprop、gradient problems | [02-backprop-gradient-problems.md](./02-backprop-gradient-problems.md) |
| 3. 不理解 Residual、Norm、initialization | [03-normalization-residual-initialization.md](./03-normalization-residual-initialization.md) |
| 4. 不理解 FFN、GELU、SwiGLU 为什么出现在 Transformer 里 | [04-ffn-gating-for-transformer.md](./04-ffn-gating-for-transformer.md) |

## 推荐读法

1. 默认先走 [Transformer mainline](../../04-transformer-foundations/)。
2. 遇到不懂的概念，再按上表进入具体 foundation page。
3. 补完后回到原来的 lesson，不要在 foundation 里横向扩散。

## 读完后你应该能解释

- 一个神经元、线性层和 MLP 的关系。
- 激活函数为什么让网络具备非线性表达能力。
- 反向传播为什么依赖链式法则，梯度消失/爆炸为什么会影响深层网络。
- Residual、Normalization 和初始化如何帮助 Transformer 堆深。
- FFN 和门控激活为什么是 Transformer block 的重要组成部分。

> ⬅️ [返回 Transformer 必要基础](../../04-transformer-foundations/)
