# 4.9 KV Cache、上下文长度与推理成本

## 你为什么要学这个

学完逐 token 生成后，还需要理解为什么聊天越长越慢、显存为什么被上下文占用、为什么 KV Cache 能加速流式输出但不能让长 prompt 免费。

## 学前检查

- 你知道 Decoder-only 会逐 token 生成；不熟先看 [08-decoder-only-generation.md](./08-decoder-only-generation.md)。
- 你知道 Self-Attention 会计算 Q/K/V；不熟先看 [04-self-attention-qkv.md](./04-self-attention-qkv.md)。

## 一个真实问题

同一个模型，短 prompt 很快，长文档 RAG 或多轮对话会明显变慢、变贵。原因不只是输出 token 多，还包括输入上下文越长，prefill 和 KV Cache 成本越高。

## 核心概念

### Prefill

Prefill 是模型第一次处理完整 prompt 的阶段。所有输入 token 都要经过 Transformer 层，建立初始 hidden states 和 K/V Cache。

### Decode

Decode 是逐步生成新 token 的阶段。每生成一个 token，模型只新增这个 token 的 Q/K/V，并读取历史 K/V。

### KV Cache 缓存什么

KV Cache 缓存每一层历史 token 的 Key 和 Value。Query 来自当前新 token，历史 K/V 可以复用。

### KV Cache 加速什么

KV Cache 加速 decode 阶段，因为不用每一步重新计算所有历史 token 的 K/V。

### KV Cache 不解决什么

KV Cache 不消除长 prompt 的 prefill 成本，也不会让注意力读取历史上下文变成零成本。上下文越长，缓存占用和读取成本越高。

## 最小心智模型

```text
long prompt -> prefill all prompt tokens -> build KV Cache
new token 1 -> reuse old K/V -> append new K/V
new token 2 -> reuse old K/V -> append new K/V
```

## 和 LLM 应用的连接

- RAG 文档塞太多会增加 prefill 成本。
- 多轮对话历史太长会增加 KV Cache 显存占用。
- 流式输出快，是因为 decode 可以复用历史 K/V。
- 成本优化常常要减少无效上下文，而不是只调 temperature。

## 常见误区

- KV Cache 不是缓存最终答案，而是缓存每层历史 token 的 K/V。
- KV Cache 加速 decode，不消除 prefill。
- 长上下文贵，不只是因为输出长，也因为输入 token 多。

## 自测

1. Prefill 和 decode 分别发生在什么时候？
2. KV Cache 缓存的是 Q、K、V 里的哪几个？
3. 为什么长 RAG prompt 即使用 KV Cache 也不免费？
4. 多轮对话为什么会增加显存压力？

## 下一步

系统学习到这里先完成 Transformer 主线。面试前再读 `../interview-paths/ai-engineer-transformer.md`（待创建）和 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。
