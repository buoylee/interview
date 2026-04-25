# 03 生成控制与结构化输出

> **定位**：这个模块解释 LLM 为什么不是“直接吐答案”，而是在每一步从 token 分布中选择下一个 token；也解释 JSON、Schema、Function Calling 这类结构化输出为什么需要额外控制。

## 默认学习顺序

1. [解码参数：Temperature、Top-k、Top-p](./01-decoding-parameters.md)
2. [结构化输出与约束解码](./02-structured-output-constrained-decoding.md)
3. [Function Calling 的输出形态](./03-function-calling-output-shape.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 为什么逐 token 生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| Softmax 后得到概率分布是什么意思 | [Attention 中的 softmax 直觉](../04-transformer-foundations/04-self-attention-qkv.md) |

如果你关心生成延迟、长上下文和成本，再读 [KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md)。它不是理解本模块三篇文章的前置条件。

## 这个模块要解决的主线问题

LLM 应用里很多问题不是“模型会不会”，而是“如何让模型稳定地按你需要的形式输出”。你需要同时理解三层控制：

```text
Prompt 约束: 告诉模型想要什么
解码约束: 改变 token 选择过程
输出协议: 把自由文本变成系统可消费的结构
```

## 深入参考

旧版材料仍可作为扩展阅读：

- [语言模型与解码](../03-nlp-embedding-retrieval/04-language-model-decoding.md)
- [受控生成与结构化输出](../03-nlp-embedding-retrieval/05-controlled-generation.md)
