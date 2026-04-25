# 4.7 三种 Transformer 架构范式：BERT、T5、GPT 为什么不同

## 你为什么要学这个

面试经常问 BERT、T5、GPT 的区别。这个问题不能只背表格，因为它本质是在问：不同任务为什么需要不同的 Transformer 结构。

上一节已经看过原始 Transformer 的两个主要部分：Encoder 负责读取 source sequence，Decoder 负责在 causal mask 下逐步生成 target sequence，并通过 cross-attention 读取 Encoder 输出。本节要做的不是重新发明三个名字，而是看不同任务会从这套 Encoder/Decoder block 结构里保留哪些能力。

## 学前检查

- 你知道原始 Transformer 的 Encoder 和 Decoder 分工；不熟先看 [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md)。
- 你知道 self-attention 和 causal mask 的基本作用。

## 一个真实问题

同样是文本模型，为什么 embedding/rerank 常见 BERT 类模型，翻译/摘要可以用 T5，而 ChatGPT/LLaMA 主要是 GPT 类 Decoder-only？因为这些任务对“读输入”和“生成输出”的要求不同。

如果任务主要是把一段文本读成可比较、可分类、可检索的表示，就更需要完整理解输入。如果任务是把一个输入序列转换成另一个输出序列，就需要清晰的“读 source，再生成 target”链路。如果任务是开放式对话和通用生成，就可以把所有输入材料放进同一个上下文序列，再不断预测下一个 token。

## 核心概念

### Encoder-only：保留理解侧

Encoder-only 只保留 Encoder。它适合把输入文本读成上下文表示。典型代表是 BERT。

从上一节的结构看，Encoder block 的重点是让输入 token 之间充分互看，形成每个 token 的上下文表示。因为它不负责天然的逐 token 生成，所以它不需要 Decoder 那套 masked self-attention 和 cross-attention 生成链路。

适合任务：分类、NER、embedding、rerank、语义匹配。

BERT 类模型适合 embedding/rerank，不是因为名字叫 BERT，而是因为这些任务的目标通常是“读懂输入，然后输出表示或判断”。例如 embedding 要把文本压成向量用于相似度比较，rerank 要比较 query 和 candidate document 的语义匹配程度，它们更像理解任务，而不是从左到右写一段新文本。

### Encoder-Decoder：保留输入到输出转换链路

Encoder 读 source sequence，Decoder 生成 target sequence，并用 cross-attention 读取 Encoder 输出。典型代表是 T5。

这基本保留了上一节的原始 Transformer 分工：Encoder 先读完整输入，Decoder 在生成每个 target token 时，通过 cross-attention 回看 Encoder 的 source 表示。因此它很适合“输入和输出是两段不同序列”的任务形状。

适合任务：翻译、摘要、改写、结构化转换。

T5 适合这类任务，是因为它把很多 NLP 问题统一成 text-to-text：输入是一段文本，输出也是一段文本。翻译要从 source language 转成 target language，摘要要从长文转成短文，结构化转换要从非结构化输入转成固定格式输出。这些任务都需要明确区分“要读的 source”和“要生成的 target”，cross-attention 正是连接两者的桥。

### Decoder-only：保留自回归生成侧

Decoder-only 把 prompt、历史对话、检索材料、工具 schema 都放进同一个序列，然后预测下一个 token。典型代表是 GPT、LLaMA。

Decoder-only 保留的是生成侧能力：masked self-attention 让当前位置只能看过去和当前上下文，然后模型不断预测下一个 token。它通常不再单独放一个 Encoder，也不需要通过 cross-attention 读取另一套 source 表示，而是把输入、上下文和已生成内容统一放进同一个 token 序列。

适合任务：对话、通用生成、代码生成、工具调用。

GPT 类模型适合通用 LLM 应用，是因为 prompt、system instruction、用户问题、历史对话、RAG 检索材料、工具 schema 和模型回答都可以排成一个连续上下文。模型不需要先显式建一个 Encoder 输出再让 Decoder 读取，而是在同一条序列里用 attention 读取已有上下文，并继续生成后续 token。

## 最小心智模型

```text
Encoder-only:
  input text -> contextual representation

Encoder-Decoder:
  source text -> encoder representation -> decoder output text

Decoder-only:
  prompt + history + context -> next token -> next token -> ...
```

## 和 LLM 应用的连接

- RAG embedding 和 rerank 常常更接近 Encoder-only 用法，因为目标是理解和比较文本。
- 通用聊天模型多是 Decoder-only，因为 prompt、上下文和输出可以统一成一个 token 序列。
- Encoder-Decoder 仍然适合明确的输入到输出转换任务，但通用 LLM 应用里不一定是默认架构。

在应用工程里，这三类结构也对应三种常见判断方式：你是要拿到一个可比较的表示，还是要做稳定的 source-to-target 转换，还是要把上下文接到 prompt 后面继续生成。BERT、T5、GPT 的差异，本质就是这些任务形状对 Transformer block 组合方式的不同要求。

## 常见误区

- Encoder-only 不是“对生成完全没用”，而是它并非天然自回归生成。
- Decoder-only 不是“没有 Encoder 所以不能理解输入”，它把输入放在同一个上下文序列里读取。
- Encoder-Decoder 不是过时架构，它在 seq2seq 任务里仍然有清晰优势。

## 自测

1. 为什么 BERT 适合 embedding/rerank？
2. T5 为什么需要 cross-attention？
3. GPT 为什么可以把检索文档和用户问题放进同一个 prompt？
4. 三种架构的输入输出形式分别是什么？

## 下一步

下一篇读 [08-decoder-only-generation.md](./08-decoder-only-generation.md)，在已经理解三种架构后，专门看 Decoder-only 如何逐 token 生成。
