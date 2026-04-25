# Normalization、Residual 与初始化

## 这篇解决什么问题

深层网络不只是“层数更多”。信息要穿过很多层到达输出，梯度也要从损失函数一路传回前面的层。层数变深以后，信息流可能逐层变形或丢失，梯度流可能逐层放大或衰减。

这篇只解释 Transformer Block 前需要的三个基础零件：Residual、LayerNorm/RMSNorm、初始化。它们共同解决一个问题：让深层网络在训练开始和训练过程中保持稳定的信息流和梯度流。

## 学前检查

读这篇前，你只需要知道：

- 神经网络由多层函数组合而成。
- 训练时用反向传播更新参数。
- Attention 和 FFN 是 Transformer Block 里的两个主要子层。
- 向量可以表示一个 token 当前携带的信息。

## 一个真实问题

假设一个模型有几十层甚至上百层。第 1 层看到的 token 表示，要经过很多次变换才能影响最终预测；最终损失产生的梯度，也要经过很多次链式求导才能回到第 1 层。

如果每一层都把信号稍微放大一点，深层后数值可能爆炸。如果每一层都把信号稍微压小一点，深层后信息和梯度可能几乎消失。即使数值没有爆炸或消失，模型也可能因为所有神经元起点太相似而学到重复模式。

Residual、Normalization 和初始化就是为这个问题服务的：让模型足够深，同时仍然能训练。

## 核心概念

Residual Connection 的核心形式是：

```text
y = x + F(x)
```

`F(x)` 是某个子层学到的新变换，`x` 是原始输入。相加以后，子层不必从零重建全部信息，只需要学习“在原信息上改什么”。这给信息流一条直达路径，也给梯度流一条更短的回传路径。

LayerNorm 是在一个 token 的表示内部做归一化。它不是跨 batch 统计不同样本，而是对同一个 token 向量的各个维度计算均值和方差，再把这个 token 表示调整到更稳定的尺度。Transformer 常用 LayerNorm，因为生成时 batch 大小和序列形态可能变化，依赖 batch 统计会不方便。

真实实现通常还会加入 `epsilon` 防止除以 0，并带有可学习的 scale；LayerNorm 通常也有可学习的 bias/shift。

RMSNorm 是更轻量的归一化变体。它通常不做 mean-centering，不先减去均值，而是用 root-mean-square 控制向量整体尺度：

```text
normalized_x = x / rms(x)
```

直觉上，LayerNorm 同时调整“中心”和“尺度”，RMSNorm 主要调整“尺度”。很多 LLM 使用 RMSNorm，是因为它计算更简单，通常也足够稳定。

初始化控制训练刚开始时信号的尺度，并打破对称。权重太大可能让激活和梯度逐层放大；权重太小可能让信息和梯度逐层变弱。另一方面，如果同一层神经元用完全相同的初始权重，它们会得到相同梯度并学到相同东西。随机初始化让它们从不同起点出发，才能分工学习不同模式。初始化主要管训练刚开始的尺度，Residual 和 Norm 则帮助尺度在很多 block 之间继续保持可控。

Pre-Norm 指在 Transformer Block 里，把归一化放在 Attention/FFN 之前。常见结构可以简化理解为：

```text
x = x + Attention(Norm(x))
x = x + FFN(Norm(x))
```

这里的 residual stream 是逐步更新的：Attention 更新后的 `x` 会继续作为 FFN 的输入，而不是 Attention 和 FFN 从同一个旧 `x` 并行运行。

对于深层 Transformer，Pre-Norm 往往比把 Norm 放在子层之后更稳定，因为每个 Attention/FFN 子层收到的输入尺度更可控。

## 最小心智模型

可以把深层网络想成一条很长的传送带：

- Residual 保留原始货物的直达通道：新层可以修改信息，但不必每次都重新搬运全部信息。
- LayerNorm/RMSNorm 像给每个 token 表示做尺度校准：让进入后续子层的数值不要忽大忽小。
- 初始化决定传送带刚启动时的力度：既不能一开始就把信号推爆，也不能弱到传不动，还要让不同参数从不同位置开始。
- Pre-Norm 把校准放在 Attention/FFN 之前：先稳定输入，再交给子层处理。

## 和 Transformer 的连接

Transformer Block 通常由 Attention、FFN、Residual Add 和 Norm 组合而成。你不需要先记住所有工程细节，但要抓住这个关系：

```text
稳定的 token 表示 -> Attention/FFN 处理 -> Residual 保留路径 -> 下一层继续
```

现代 LLM block 经常使用 Pre-Norm，并在 LayerNorm 或 RMSNorm 中选择一种归一化方式。读懂这篇以后，再看 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md) 时，重点关注 Norm 放在哪里、Residual 怎么加回去、Attention/FFN 如何被包在这个稳定结构里。

## 常见误区

| 误区 | 修正 |
|------|------|
| Residual 只是“把输入加回来” | 它同时改善信息流和梯度流，让深层网络更容易训练 |
| LayerNorm 是跨 batch 做归一化 | LayerNorm 是在一个 token 表示内部归一化，不依赖 batch 统计 |
| RMSNorm 和 LayerNorm 完全无关 | RMSNorm 是更轻量的归一化变体，通常用均方根控制尺度并跳过 mean-centering |
| 初始化只是随机给个值 | 初始化要控制训练开始时的信号尺度，并打破对称 |
| Pre-Norm 是无关紧要的摆放细节 | 在深层 Transformer 中，Norm 放在 Attention/FFN 前面经常能提升训练稳定性 |

## 自测

1. 为什么深层网络同时需要稳定的信息流和梯度流？
2. 在 `y = x + F(x)` 里，`x` 和 `F(x)` 分别代表什么？
3. LayerNorm 为什么说是在一个 token 表示内部做归一化，而不是跨 batch？
4. RMSNorm 相比 LayerNorm 通常省掉了哪一步？它主要控制什么？
5. 初始化为什么既要控制信号尺度，又要打破对称？
6. Pre-Norm 为什么会帮助深层 Transformer Block 稳定训练？

## 回到主线

现在回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)。阅读时，把每个 block 看成“Norm 先稳定输入，Attention/FFN 做变换，Residual 保留路径”的组合，而不是一堆孤立模块。
