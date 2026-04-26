# Transformer FFN、GELU 与 SwiGLU

## 这篇解决什么问题

这篇解决 Transformer Block 里 FFN 为什么存在，以及 GELU、GLU、SwiGLU 这几类激活和门控到底在做什么。

先记住分工：

```text
Attention = token 之间交换信息
FFN = 每个 token 独立加工信息
```

Attention 让一个 token 读取其他 token 的信息。FFN 则在每个 token 自己的位置上，对刚读到的表示做更深的非线性加工。

## 学前检查

读这篇前，只需要知道：

- token 会被表示成向量。
- Transformer Block 里既有 Attention，也有 FFN。
- 矩阵乘法可以把向量投影到新的维度。
- 激活函数会给线性变换加入非线性。

如果你想看 FFN 放在整个模块里的位置，回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)。

## 一个真实问题

假设一句话里有一个 token 已经通过 Attention 读到了上下文：

```text
"bank" 读到了 river / money / account 等上下文线索
```

Attention 的工作是把相关 token 的信息聚合过来。但聚合之后，还需要在这个 token 自己的向量里继续判断：哪些特征更重要，哪些组合更有用，哪些中间模式应该被放大或压低。

这就是 FFN 的工作。它不是 Attention 的附属品，而是每个 token 的独立加工层。

## 核心概念

标准 FFN 是 position-wise / 逐位置的：同一套 FFN 会独立应用到每个 token 的向量上。可以写成：

```text
FFN(x) = W_down * activation(W_up * x)
```

实际实现里可能还有 bias、dropout、归一化前后的位置差异，但最小结构就是：

```text
输入 x
-> W_up 扩到更大的中间维度
-> activation 加入非线性
-> W_down 投回原维度
```

GELU 是一种平滑激活函数。它不像硬 cutoff 那样简单地把一侧砍掉，而是用连续曲线柔和地压低或保留输入。直觉上，GELU 会根据数值大小平滑缩放输入：较大的正值保留更多，接近零或负值会被更强压低。

GLU 会把 FFN 的中间层拆成两路：

```text
信息分支：产生候选内容
gate 分支：产生调节因子
```

SwiGLU 是现代 LLM 里常见的 GLU 变体，可以写成：

```text
SwiGLU_FFN(x) = W_down * (SiLU(W_gate * x) elementwise_multiply (W_up * x))
```

其中：

- `W_up` 是信息分支的 FFN projection matrix。
- `W_gate` 是 gate 分支的 FFN projection matrix。
- `W_down` 把中间维度投回模型维度。
- `W_gate`、`W_up`、`W_down` 是 FFN projection matrices，不是 Attention 里的 K/V。

SwiGLU 的 gate 是连续乘法调节，不是 if/else。它也不一定被限制在 0 到 1；和 sigmoid gate 不同，SiLU/Swish 风格的 gate 可以产生更灵活的连续缩放。

## 最小心智模型

把一个 token 的 FFN 想成一个小加工厂：

```text
W_up：把原材料摊开，提供更多加工空间
GELU / SwiGLU：决定哪些中间特征更值得保留或放大
W_down：把加工结果压回 Transformer Block 需要的维度
```

普通 GELU FFN 是“一条信息流 + 平滑激活”。SwiGLU FFN 是“信息分支 + gate 分支 + 连续乘法”。两者都在每个 token 内部独立运行，不在 token 之间传消息。

## 和 Transformer 的连接

在常见 Transformer Block 里，Attention 子层后面通常接 FFN 子层：

```text
token 表示
-> Attention：token 之间交换信息
-> FFN：每个 token 独立加工信息
-> 下一层
```

所以 FFN 不是可有可无的后处理。很多 Transformer 的参数和计算都集中在 FFN 部分，因为它负责把 Attention 聚合来的信息转成更有用的内部特征。

下一步应该把这篇放回 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md) 里看：Attention 负责横向通信，FFN 负责逐 token 的纵向加工。

## 常见误区

| 误区 | 修正 |
|------|------|
| Attention 才是 Transformer 的全部 | Attention 负责 token 间通信，FFN 负责每个 token 内部加工 |
| FFN 只是一个普通 MLP，没必要理解 | FFN 通常占大量参数和计算，直接影响模型表达能力 |
| GELU 是硬阈值函数 | GELU 是 smooth activation，不是 hard cutoff |
| gate 就是 if/else 开关 | SwiGLU gate 是连续乘法调节，不是 if/else |
| gate 一定是 0 到 1 的概率 | SwiGLU gate 不一定限制在 0-1 |
| `W_gate`、`W_up` 是 Attention 参数 | 它们是 FFN projection matrices，不是 Attention 里的 K/V |

## 自测

1. 为什么可以说 `Attention = token 之间交换信息`，而 `FFN = 每个 token 独立加工信息`？
2. 标准 FFN 公式 `FFN(x) = W_down * activation(W_up * x)` 里的 `W_up` 和 `W_down` 分别负责什么？
3. GELU 为什么是 smooth activation，而不是 hard cutoff？
4. GLU/SwiGLU 里的信息分支和 gate 分支分别做什么？
5. 为什么说 SwiGLU gate 是连续乘法，不是 if/else，也不一定限制在 0-1？
6. `W_gate`、`W_up`、`W_down` 为什么不是 Attention 里的 K/V？

## 回到主线

深入参考可回到 [旧版深度学习基础](../../02-deep-learning/)。

回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)，把 FFN 放进完整结构里理解：Attention 先让 token 之间交换信息，FFN 再让每个 token 独立加工信息。
