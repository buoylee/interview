# 04 Transformer 必要基础

> **定位**：这不是算法岗训练手册，而是 AI Engineer 面试需要掌握的 Transformer 底层模型。目标是让你能解释 RAG、Agent、结构化输出、上下文长度、推理成本背后的模型机制。

## 你会学到什么

- Token 如何变成向量
- Self-Attention 如何让 token 彼此读取信息
- Q/K/V、softmax、缩放、多头注意力分别解决什么问题
- Transformer Block 里的 Attention、FFN、Residual、LayerNorm/RMSNorm 如何配合
- 为什么现代 LLM 大多是 Decoder-only
- Transformer 知识如何连接 KV Cache、长上下文、工具调用和幻觉排查

## 学习路径

| 顺序 | 文件 | 解决的问题 |
|------|------|------------|
| 1 | [01-why-ai-engineers-need-transformer.md](./01-why-ai-engineers-need-transformer.md) | 为什么应用工程师也要懂 Transformer |
| 2 | [02-token-to-vector.md](./02-token-to-vector.md) | 文本如何进入模型 |
| 3 | [03-self-attention-qkv.md](./03-self-attention-qkv.md) | Self-Attention 到底怎么算 |
| 4 | [04-transformer-block.md](./04-transformer-block.md) | 一个 Transformer 层由哪些零件组成 |
| 5 | [05-decoder-only-and-generation.md](./05-decoder-only-and-generation.md) | 为什么 GPT 类模型能逐 token 生成 |

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
- 为什么 Decoder-only 成为主流 LLM 架构。
- Transformer 的哪些机制会影响上下文长度、延迟和推理成本。

## 复习入口

学完后用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 做面试复盘。

> ⬅️ [返回总路线](../../ml-to-llm-roadmap.md)
