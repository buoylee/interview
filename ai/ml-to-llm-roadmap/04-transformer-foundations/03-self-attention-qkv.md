# 4.3 Self-Attention 与 Q/K/V

## 你为什么要学这个

Self-Attention 是 LLM 理解上下文的核心机制。面试里的 Q/K/V、`sqrt(d_k)`、Multi-Head、长上下文复杂度，都是从这一节展开。

## 学前检查

你需要知道：

- token 已经被表示成向量；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- softmax 会把一组分数变成和为 1 的权重；不熟时回看旧版 [概率基础](../00-math-foundations/02-probability.md)。

## 一个真实问题

在 RAG prompt 里，答案证据、系统指令、用户问题、历史对话同时出现。模型不是平均阅读所有文本，而是每个 token 根据注意力权重从上下文里取信息。上下文组织不好时，关键信息可能被其他内容竞争掉。

## 核心概念

### 一句话公式

直觉上，每个 token 会先从自己的向量生成 Q、K、V。当前 token 用自己的 Q 去和上下文里所有 token 的 K 比较，softmax 把比较分数变成权重，再用这些权重混合所有 token 的 V，得到更新后的表示。

```text
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

在 Decoder-only 生成模型里，未来 token 会被 causal mask 遮住；这里先讲未加 mask 的基础计算，后面 Decoder-only 章节再展开。

符号含义：

- `Q`：Query，当前 token 想找什么信息。
- `K`：Key，每个 token 提供什么匹配标签。
- `V`：Value，每个 token 真正提供的内容。
- `QK^T`：计算每个 token 对其他 token 的匹配分数。
- `sqrt(d_k)`：把点积分数缩放到 softmax 更稳定的范围。
- `softmax`：把分数变成注意力权重。

### 逐步流程

```text
X -> W_Q -> Q
X -> W_K -> K
X -> W_V -> V
QK^T -> scale -> softmax -> weights
weights V -> output
```

### 为什么除以 `sqrt(d_k)`

如果 Q 和 K 的维度很高，点积的方差和典型尺度会随 `d_k` 增大而变大。过大的分数会让 softmax 接近 one-hot，梯度变小，训练不稳定。除以 `sqrt(d_k)` 相当于在进入 softmax 前归一化分数尺度，把它们拉回更合理的范围。

### Multi-Head Attention

单头注意力只能在一个表示空间里计算关系。多头把表示拆到多个子空间，让不同头可以关注不同关系，例如指代、语义相似、格式边界和局部邻近。

### 复杂度

Self-Attention 要计算 token 两两关系，所以序列长度为 `n` 时，注意力分数矩阵是 `n x n`。这就是长上下文成本高的根源之一。

## 和 LLM 应用的连接

| 应用问题 | Attention 视角 |
|----------|----------------|
| RAG 证据被忽略 | 证据 token 没有被关键生成 token 高权重关注 |
| Prompt 太长效果下降 | 无关 token 增加注意力竞争 |
| 长上下文成本高 | 注意力矩阵随 token 数平方增长 |
| KV Cache 占显存 | 每层都要缓存历史 token 的 K/V |

## 面试怎么问

- 从头讲 Self-Attention 的计算过程。
- Q、K、V 分别是什么？
- 为什么要除以 `sqrt(d_k)`？
- Multi-Head Attention 为什么有用？
- Attention 的复杂度瓶颈在哪里？

## 自测

1. `QK^T` 的结果矩阵每一行代表什么？
2. `softmax` 在 Attention 中起什么作用？
3. 为什么长上下文会显著增加计算成本？
4. Multi-Head 和单头 Attention 的核心区别是什么？

## 下一步

下一篇读 [04-transformer-block.md](./04-transformer-block.md)（后续任务创建），把 Attention 放回完整 Transformer 层里。
