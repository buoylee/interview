# 4.4 Self-Attention 与 Q/K/V

## 你为什么要学这个

上一篇已经把 Attention 的动机拆成四个问题：当前 token 想找什么、其他 token 声明自己有什么、其他 token 真正提供什么内容、当前 token 应该从每个 token 读取多少。本篇把前三个问题具体落到 Q、K、V，并解释读取比例如何由 attention weights 得到。

Self-Attention 是 LLM 理解上下文的核心机制。面试里的 Q/K/V、`sqrt(d_k)`、Multi-Head、长上下文复杂度，都是从这一节展开。

## 学前检查

你需要知道：

- token 已经被表示成向量，并理解为什么需要上下文读取；不熟先看 [03-why-attention-needs-context.md](./03-why-attention-needs-context.md)。
- 点积和 `QK^T` 是怎么得到匹配分数的；不熟先看 [向量、矩阵和点积](../foundations/math-for-transformer/01-vector-matrix-dot-product.md)。
- softmax 会把一组分数变成和为 1 的权重；不熟先看 [Logits、Softmax 与概率分布](../foundations/math-for-transformer/02-logits-softmax-probability.md)。
- 如果看到完整公式会断掉，先看 [Attention 公式的最小数学拆解](../foundations/math-for-transformer/03-attention-math-minimal.md)。

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

### Q、K、V 为什么要分开（软字典直觉）

最容易卡的地方是：既然有了 Q 和 V，为什么还要 K？把 Attention 想成一个「软字典」就通了。

普通字典（HashMap）是精确查找：

```text
value = dict[key]               # 拿 key 精确匹配，取回对应 value
```

Attention 是它的「模糊版」：

```text
output = Σ 相似度(Q, K) × V     # 拿 Q 和所有 K 比相似度，按相似度混合所有 V
```

对号入座：

- `Q` = 你递进去查询的 key（`dict[?]` 里的 `?`）
- `K` = 每个条目挂在外面、用来被比对的标签 key
- `V` = 每个条目内部真正被取回的货

所以 **K 和 V 是两套独立的表示，各管一件事**：

- **K 决定权重**：该不该关注、给多少注意力——只参与 `QK^T` 打分。
- **V 决定内容**：被关注后实际取回什么——只参与最后的加权求和。

「判断该不该关注一个 token」和「关注后从它身上取走什么」是两件不同的事，所以用 `W_K`、`W_V` 两个矩阵把它们解耦，让模型分别学好「怎么被匹配」和「传递什么内容」。如果只有 V 没有 K，就像字典只有 value 没有 key，没法决定该取哪个、取多少。

### 一个常见困惑：Q、K 数值相同，输出为什么不同？

`QK^T` 只产出一个**分数**（经 softmax 变成权重），它决定「水龙头开多大」，不决定「流出什么水」。真正流出来的是 **V**，活在和 Q/K 完全不同的表示空间里。

所以即使某个 token 的 Q 和另一个 token 的 K 数值正好相等（完美匹配、权重很高），最终输出仍是各 token 的 V 加权混合出来的结果，和 Q/K 的具体数值毫不相干。**「用来匹配的东西相同」不等于「输出相同」**——匹配只管权重，V 才是内容。

> 补充：Q 和 K 也分开（而非共用一个矩阵），是为了让「A 关注 B」可以不等于「B 关注 A」——注意力是有方向的。强行 Q=K 会把注意力矩阵逼成对称，表达力下降。后续 GQA/MQA 等变体则是在「K、V 要不要省着共享」上做权衡。

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
5. 为什么 K 和 V 要用两个不同的矩阵？只有 Q 和 V 行不行？如果两个 token 的 Q、K 数值正好相等，输出会一样吗？

## 下一步

下一篇读 [05-transformer-block.md](./05-transformer-block.md)，把 Attention 放回完整 Transformer 层里。
