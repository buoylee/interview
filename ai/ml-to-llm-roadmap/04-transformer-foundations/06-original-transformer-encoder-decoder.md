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

## 和 LLM 应用的连接

- 翻译和摘要天然像“输入序列到输出序列”的任务。
- RAG 里的 reader/generator 可以类比为“先读材料，再生成答案”，但现代通用 LLM 通常把材料和问题拼进同一个 Decoder-only prompt。
- 理解 cross-attention 后，更容易理解为什么 Encoder-Decoder 和 Decoder-only 在处理输入信息时方式不同。

## 常见误区

- Encoder 不是“只编码不理解”，它会通过 self-attention 形成上下文表示。
- Decoder 不是只能看自己，它可以通过 cross-attention 读取 Encoder 输出。
- Causal mask 限制的是 Decoder 生成侧，避免它看见未来 target token。

## 自测

1. Source sequence 和 target sequence 分别是什么？
2. Encoder 为什么通常可以双向看输入？
3. Decoder 为什么需要 causal mask？
4. Cross-attention 连接了哪两部分？

## 下一步

下一篇读 `07-transformer-architecture-variants.md`（待创建），看 BERT、T5、GPT 如何从这套结构中选择不同部分。
