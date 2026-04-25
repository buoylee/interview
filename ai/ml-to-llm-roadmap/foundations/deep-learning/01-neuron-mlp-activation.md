# 神经元、MLP 与激活函数

## 这篇解决什么问题

这篇只教神经网络里最基础的四个组件：线性层、偏置、激活函数和 MLP。它不提前展开反向传播、优化器、Norm、Residual、Attention 或完整 Transformer Block。

学完这一页，你会知道模型如何把一个输入向量变成更有用的表示。这会直接解锁两件主线知识：Token 进入模型后如何以向量形式被处理，以及 Transformer 里的 FFN 为什么本质上是一个作用在每个 token 上的 MLP。

## 学前检查

你只需要知道“向量是一组数字”就够了。暂时不需要理解反向传播，也不需要知道权重是怎么训练出来的。

如果你想先看主线里向量第一次正式出现的位置，可以回到 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)。

## 一个真实问题

模型收到一个 token 向量后，里面已经有一些关于这个 token 的信息。但这个原始表示通常还不够直接有用。

真实问题是：模型怎样把这个向量变成一个更有用的新表示？例如，把“词形、位置、上下文线索压缩后的数字”重新组合成“更适合下一步预测的特征”。

## 核心概念

### 神经元和线性层的关系

一个神经元可以先理解为线性层里的一个输出单元：它接收输入向量 `x`，用一组权重 `w` 做加权求和，再加上偏置 `b`，得到一个数字。

```text
一个神经元: w · x + b -> 一个输出数字
```

多个神经元并排放在一起，就形成一个输出向量。这时把每个神经元的权重排成矩阵 `W`，就得到线性层里的 `Wx + b`。

### 线性层

线性层做的事是：

```text
Wx
```

可以先把它理解为“对输入向量里的数字重新加权、混合、投影”。输入是一个向量，输出也是一个向量，只是维度和含义可能变了。

### 偏置

偏置是在 `Wx` 后面加上的 `b`：

```text
Wx + b
```

对单个线性层来说，偏置提供额外平移自由度，让输出不必总是围绕原点变化。实际 Transformer 实现中有些线性层会省略 bias，这是架构取舍，不影响这里的基本概念。

### 激活函数

激活函数接在线性层之后：

```text
f(Wx + b)
```

它的关键作用是引入非线性。没有激活函数，多层线性层叠在一起仍然等价于一个新的线性层/仿射变换：

```text
W3(W2(W1x + b1) + b2) + b3 = W'x + b'
```

所以激活函数不是装饰，而是让网络能表达复杂关系的必要组件。

### MLP

MLP 是多层感知机，可以先理解为“多层线性层 + 激活函数”的堆叠：

```text
x -> Linear -> Activation -> Linear -> output
```

更深的 MLP 可以重复隐藏层里的 `Linear -> Activation` 块，但 Transformer FFN 通常会在最后投回模型维度，再交给残差连接相加。

它不会自己读取别的 token，也不会做 token 之间的信息交换。它只是在已有向量内部重新组合特征，把当前向量变成更适合后续计算的新向量。

## 最小心智模型

```text
输入向量 x
-> 线性层 Wx + b
-> 激活函数引入非线性
-> 多层堆叠成 MLP
```

## 和 Transformer 的连接

在 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md) 里，Attention 和 FFN 都会处理 token 向量，但它们解决的问题不同。

Transformer FFN 是一个 per-token MLP：它对每个 token 的向量分别做变换，让这个 token 的表示在特征维度上变得更有用。它不负责读取其他 token；读取和混合其他 token 信息主要是 Attention 的职责。

## 常见误区

| 误区 | 修正 |
|------|------|
| 激活函数只是装饰 | 激活函数引入非线性；没有它，多层线性层会退化成一层线性变换 |
| MLP 会读取其他 token | MLP 只处理当前 token 的向量，不做 token 间信息交换 |
| FFN 和 Attention 做的是同一件事 | Attention 在 token 之间交换信息；FFN 在每个 token 内部重组特征 |
| 线性层只是“缩放数字” | 线性层会把输入向量的多个维度重新混合成新的输出维度 |

## 自测

1. 线性层 `Wx + b` 中，`W` 和 `b` 分别起什么作用？
2. 激活函数为什么不能被当作可有可无的装饰？
3. 为什么多层线性层如果没有激活函数，会坍缩成一个线性变换？
4. Transformer FFN 为什么可以理解为 per-token MLP？它和 Attention 的分工是什么？

## 回到主线

读完这一页后，回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)，理解 FFN 在 block 中的位置。

如果你是按系统补课顺序读，下一步读 [反向传播与梯度问题](./02-backprop-gradient-problems.md)。如果你当前只卡在 Transformer FFN，可以直接跳到 [FFN 与门控](./04-ffn-gating-for-transformer.md)，看现代 Transformer 怎样在基础 MLP 上加入门控结构。
