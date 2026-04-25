# 2.1 神经网络基础：新版阅读入口

> **定位**：这篇不再作为长篇教材入口。新版路线把神经网络基础拆成更小的 foundation 文档，方便你按 Transformer 主线遇到的问题补课。

## 为什么要改

旧版 `01-neural-network-basics.md` 把神经元、MLP、激活函数、反向传播、梯度问题、Normalization、Residual、初始化等内容放在同一篇里。第一次学习时很容易感觉概念连续出现，但没有足够时间消化。

新版默认读法是：先走 Transformer 主线，卡住哪个前置概念，再回到对应 foundation。

## 默认补课路径

| 你卡在哪里 | 读这篇 |
|------------|--------|
| 不理解神经元、线性层、MLP、激活函数 | [神经元、MLP 与激活函数](../foundations/deep-learning/01-neuron-mlp-activation.md) |
| 不理解 loss、梯度、反向传播、梯度消失/爆炸 | [反向传播、梯度消失与梯度爆炸](../foundations/deep-learning/02-backprop-gradient-problems.md) |
| 不理解 Residual、LayerNorm、RMSNorm、初始化 | [Normalization、Residual 与初始化](../foundations/deep-learning/03-normalization-residual-initialization.md) |
| 不理解 FFN、GELU、SwiGLU、门控 | [Transformer FFN、GELU 与 SwiGLU](../foundations/deep-learning/04-ffn-gating-for-transformer.md) |

## 建议读法

1. 先读 [Transformer 必要基础](../04-transformer-foundations/)。
2. 遇到不懂的前置概念，再回到本页选择对应 foundation。
3. 补完后回到原来的 Transformer 章节，不要在旧版深度学习目录里横向扩散。

## 旧版参考

旧版长文已经保留为参考资料：[legacy/01-neural-network-basics-reference.md](./legacy/01-neural-network-basics-reference.md)。

它适合在你已经读完新版 foundation 后，想查更完整的激活函数、BN/LN、Dropout、初始化和面试问法时使用；不建议作为第一次学习入口。

> ⬅️ [返回本阶段 README](./README.md)
