# 04 Transformer 必要基础

> **定位**：这是第一次系统学习 Transformer 的主线，不是面试速记。系统主线完成后，再进入 [Transformer 面试阅读路径](../interview-paths/ai-engineer-transformer.md) 和 `09-review-notes/` 做压缩复习。

## 你会学到什么

- Token 如何变成向量
- Self-Attention 如何让 token 彼此读取信息
- Q/K/V、softmax、缩放、多头注意力分别解决什么问题
- Transformer Block 里的 Attention、FFN、Residual、LayerNorm/RMSNorm 如何配合
- 为什么现代 LLM 大多是 Decoder-only
- Transformer 知识如何连接模型架构、逐 token 生成、KV Cache、长上下文，以及 RAG/Agent 的上下文处理

## 学习路径

| 顺序 | 文件 | 解决的问题 | 状态 |
|------|------|------------|------|
| 1 | [01-why-ai-engineers-need-transformer.md](./01-why-ai-engineers-need-transformer.md) | 为什么应用工程师也要系统理解 Transformer | 已存在 |
| 2 | [02-token-to-vector.md](./02-token-to-vector.md) | 文本如何变成模型能处理的向量 | 已存在 |
| 3 | [03-why-attention-needs-context.md](./03-why-attention-needs-context.md) | 为什么 token 需要读取上下文 | 已存在 |
| 4 | [04-self-attention-qkv.md](./04-self-attention-qkv.md) | Self-Attention 和 Q/K/V 到底在算什么 | 已存在 |
| 5 | [05-transformer-block.md](./05-transformer-block.md) | 一个 Transformer 层如何把 Attention、FFN、Residual、Norm 组合起来 | 已存在 |
| 6 | [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md) | 原始 Transformer 的 Encoder 和 Decoder 分别负责什么 | 已创建 |
| 7 | [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md) | BERT、T5、GPT 三种架构范式为什么不同 | 已创建/可读 |
| 8 | [08-decoder-only-generation.md](./08-decoder-only-generation.md) | GPT 类模型如何基于已有上下文逐 token 生成 | 已创建/可读 |
| 9 | [09-kv-cache-context-cost.md](./09-kv-cache-context-cost.md) | KV Cache、prefill、decode 和长上下文成本如何关联 | 已创建/可读 |

## 学前检查

如果下面概念不熟，先按需补课：

| 概念 | 补课材料 |
|------|----------|
| 神经元、线性层、激活函数 | [foundations/deep-learning/01-neuron-mlp-activation.md](../foundations/deep-learning/01-neuron-mlp-activation.md) |
| 反向传播、梯度消失/爆炸 | [foundations/deep-learning/02-backprop-gradient-problems.md](../foundations/deep-learning/02-backprop-gradient-problems.md) |
| Residual、LayerNorm、初始化 | [foundations/deep-learning/03-normalization-residual-initialization.md](../foundations/deep-learning/03-normalization-residual-initialization.md) |
| FFN、GELU、SwiGLU | [foundations/deep-learning/04-ffn-gating-for-transformer.md](../foundations/deep-learning/04-ffn-gating-for-transformer.md) |

## 学完后你应该能回答

- 从头讲 Self-Attention 的计算流程。
- 为什么 Attention 要除以 `sqrt(d_k)`。
- Multi-Head Attention 为什么不是简单重复。
- Residual、LayerNorm、FFN 在 Transformer Block 中分别负责什么。
- 原始 Transformer 为什么分 Encoder 和 Decoder。
- Encoder-only、Encoder-Decoder、Decoder-only 分别适合什么任务。
- 为什么 Decoder-only 成为主流 LLM 架构。
- KV Cache 为什么加速 decode，但不消除长 prompt 的 prefill 成本。
- Transformer 的哪些机制会影响上下文长度、延迟和推理成本。

## 复习入口

学完后用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 做面试复盘。

> ⬅️ [返回总路线](../../ml-to-llm-roadmap.md)
