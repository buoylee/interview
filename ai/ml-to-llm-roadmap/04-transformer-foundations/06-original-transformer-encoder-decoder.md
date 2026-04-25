# 4.6 原始 Transformer：Encoder 和 Decoder 各自负责什么

## 你为什么要学这个

在比较 BERT、T5、GPT 之前，必须先知道原始 Transformer 为什么有 Encoder 和 Decoder。否则 Encoder-only、Encoder-Decoder、Decoder-only 只是三个需要硬背的名字。

## 学前检查

- 你知道 Transformer Block 是 Attention、FFN、Residual、Norm 的组合；不熟先看 [05-transformer-block.md](./05-transformer-block.md)。
- 你知道 causal mask 会限制 token 看未来；如果还不熟，本篇会先给最小解释。

## 一个真实问题

机器翻译里，输入是中文句子，输出是英文句子。模型需要先读懂完整中文，再逐步生成英文。这就是原始 Encoder-Decoder 架构的核心动机。

## 核心概念

### Source sequence 和 target sequence

Source sequence 是输入序列，例如用户给出的中文句子。Target sequence 是要生成的输出序列，例如英文翻译。

### 从 Transformer Block 到 Encoder/Decoder

Encoder 不是一个单独的神秘模块，而是一层层 Encoder block 叠起来。Encoder block 可以粗略理解为 self-attention + FFN + residual/norm。

Decoder 也是一层层 Decoder block 叠起来。Decoder block 比 Encoder block 多一个读取输入的环节：masked self-attention + cross-attention + FFN + residual/norm。

这个结构差异会让下一篇的 Encoder-only、Encoder-Decoder、Decoder-only 变成具体选择，而不是三个抽象名字。

### Encoder 负责读懂输入

Encoder 读取完整 source sequence。因为输入已经完整给定，source token 之间通常可以双向互看。

### Decoder 负责逐步生成输出

Decoder 生成 target sequence。生成时不能偷看未来答案，所以 Decoder 的 self-attention 需要 causal mask。

### Cross-attention 负责读取 Encoder 结果

Decoder 生成每个输出 token 时，不只看已经生成的 target token，还要读取 Encoder 对 source sequence 的表示。这个“Decoder 读 Encoder 输出”的注意力就是 cross-attention。

## 最小心智模型

输入：source sequence，例如 `我 喜欢 苹果`。

Encoder 输出：每个 source token 的上下文表示。

Decoder 输入：已经生成的 target token，例如 `I like`。

训练时通常喂给 Decoder 的是右移后的 target token；推理时喂给它的是已经生成出来的 token。

Decoder 输出：下一个 target token 的概率，例如 `apples`。

## 原理层：Encoder 和 Decoder 的数据流

先把一个 Transformer block 里的 self-attention 回忆一下：当前 token 会产生一个 Query，用它去和一组 Key 做匹配，再按匹配权重读取对应的 Value。区别在于，不同位置的 Q/K/V 来自哪里，以及哪些位置允许被看见。

### Encoder self-attention：source token 之间互相读

Encoder 处理的是已经完整给定的 source sequence。以 `我 喜欢 苹果` 为例，Encoder 的每一层都会让每个 source token 产生自己的 Q/K/V：

```text
source tokens: 我 | 喜欢 | 苹果

每个 token 都产生:
  Q: 我现在想找什么信息
  K: 我能被别人用什么特征匹配到
  V: 如果别人关注我，我能提供什么内容
```

因为 source sequence 已经完整给定，`我` 可以看 `喜欢` 和 `苹果`，`苹果` 也可以反过来看 `我` 和 `喜欢`。所以 Encoder self-attention 通常是双向的。

这一步的输出不是一个单独向量，而是一组上下文表示：每个 source token 都变成了“结合整句上下文之后的 token 表示”。

### Decoder masked self-attention：target token 只能读已经出现的部分

Decoder 处理的是 target sequence，也就是正在生成的输出。生成英文翻译时，如果当前已经有 `I like`，模型要预测下一个 token，不能提前看到标准答案里的 `apples`。

所以 Decoder self-attention 也会从 target token 产生 Q/K/V，但会加 causal mask：

```text
Decoder 输入: <BOS> | I | like

位置 <BOS>:
  只能看 <BOS>
  输出用于预测 I

位置 I:
  可以看 <BOS>, I
  输出用于预测 like

位置 like:
  可以看 <BOS>, I, like
  输出用于预测 apples
```

这就是 masked self-attention。它不是让 Decoder “少理解一点”，而是强制模型遵守生成任务的时间顺序：只能根据已经出现的 target prefix 预测下一个 token。这里不是有一个真实的 ? token 在产生 Query；mask 挡住的是训练序列里当前位置之后的未来 target token。

### Cross-attention：Decoder 用当前生成需求去读 Encoder 结果

Decoder block 比 Encoder block 多一个 cross-attention。它连接的是两条序列：

```text
Encoder 输出:
  source 表示: 我' | 喜欢' | 苹果'

Decoder 当前状态:
  target prefix 表示: I' | like'

Cross-attention:
  Q 来自 Decoder 当前状态
  K/V 来自 Encoder 的 source 表示
```

这句话很关键：cross-attention 里的 Query 来自 Decoder，Key 和 Value 来自 Encoder。

直觉上，它在问：

> 我现在正在生成 target 里的这个位置，为了决定下一个词，应该回看 source sequence 的哪些部分？

当 Decoder 根据 `I like` 预测 `apples` 时，当前 prefix 末尾位置的 Query 可能会更关注 Encoder 输出里和 `苹果` 对应的 Key，然后读取那个位置的 Value。

### 训练时和推理时为什么不一样

训练时，标准答案已经存在。例如目标句子是 `I like apples`。模型通常会看到右移后的 target prefix：

```text
Decoder 输入: <BOS> | I | like
预测目标:       I | like | apples
```

这叫 teacher forcing。模型不是一次性复制答案，而是在每个位置学习“看到前面的 token 后，下一个 token 应该是什么”。

推理时没有标准答案，只有模型自己已经生成的内容：

```text
第 1 步: <BOS> -> I
第 2 步: <BOS> I -> like
第 3 步: <BOS> I like -> apples
```

所以推理必须逐 token 进行。这个区别会在后面的 Decoder-only 和 KV Cache 中继续出现。

## 和 LLM 应用的连接

- 翻译和摘要天然像“输入序列到输出序列”的任务。
- RAG 里的 reader/generator 可以类比为“先读材料，再生成答案”，但现代通用 LLM 通常把材料和问题拼进同一个 Decoder-only prompt。
- 理解 cross-attention 后，更容易理解为什么 Encoder-Decoder 和 Decoder-only 在处理输入信息时方式不同。

## 常见误区

- Encoder 不是“只编码不理解”，它会通过 self-attention 形成上下文表示。
- Decoder 不是只能看自己，它可以通过 cross-attention 读取 Encoder 输出。
- Causal mask 限制的是 Decoder 生成侧，避免它看见未来 target token。
- Cross-attention 不是 Encoder 自己内部的 attention，而是 Decoder 用自己的 Query 去读取 Encoder 输出的 Key/Value。
- 训练时 Decoder 可以拿到右移后的标准答案前缀；推理时只能拿到模型已经生成的前缀。

## 自测

1. Source sequence 和 target sequence 分别是什么？
2. Encoder self-attention 的 Q/K/V 都来自哪里？
3. Decoder masked self-attention 为什么不能看未来 target token？
4. Cross-attention 中 Q、K、V 分别来自哪里？
5. 训练时右移后的 target prefix 和推理时已生成 prefix 有什么区别？

## 深入参考

本篇已经覆盖主线需要的 Encoder/Decoder 数据流。读完后，如果你想看更公式化、更完整的 attention 计算，可以再读：

- [Transformer 核心架构](../04-transformer-architecture/01-transformer-core.md)

## 下一步

下一篇读 [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md)，看 BERT、T5、GPT 如何从这套结构中选择不同部分。
