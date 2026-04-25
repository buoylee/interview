# 4.3 为什么 Attention 需要“看上下文”

## 你为什么要学这个

讲完 token 变成向量后，读者还不知道模型怎样处理“同一个词在不同句子里含义不同”的问题。本篇只解决一个问题：为什么每个 token 不能只看自己的 embedding，而需要读取周围 token 的信息。

## 学前检查

- 你知道 token ID 和 embedding 的区别；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- 你知道一个 token 可以表示成一个向量；不需要先懂 Q/K/V。

## 一个真实问题

在句子 `Apple released a new model` 和 `I ate an apple` 里，`Apple/apple` 的含义不同。只看单个 token 的向量，很难判断它是公司还是水果。模型必须让 token 读取上下文。

## 核心概念

### 只看自己为什么不够

Embedding 给每个 token 一个初始向量，但这个向量还没有吸收当前句子的上下文。

### 上下文读取是什么

上下文读取就是：当前 token 根据当前句子里的其他 token，更新自己的表示。

### Attention 的目标

Attention 要回答三个问题：

1. 当前 token 想找什么信息。
2. 其他 token 能提供什么信息。
3. 当前 token 应该从每个 token 读取多少信息。

这三个问题会在下一篇变成 Q、K、V。

## 最小心智模型

输入：一串 token embedding。

中间：每个 token 观察同一句子里的其他 token，决定哪些信息更相关。

输出：每个 token 得到一个带上下文的新向量。

## 和 LLM 应用的连接

- RAG 中，模型回答问题时要判断检索片段里的哪些 token 和问题相关。
- Agent 中，模型要在工具说明、用户目标、历史步骤之间建立关系。
- 长上下文成本高，是因为 token 之间的关系读取会随上下文长度变重。

## 常见误区

- Attention 不是让模型“理解一切”，它只是提供一种读取上下文的机制。
- Embedding 不是最终语义，经过 Attention 后的 hidden state 才吸收了当前上下文。
- 不是所有 token 都同等重要，Attention 权重表达的是相对读取比例。

## 自测

1. 为什么只看 embedding 不足以处理上下文含义？
2. Attention 想解决哪三个问题？
3. 为什么 RAG 回答需要上下文读取能力？

## 下一步

下一篇读 [04-self-attention-qkv.md](./04-self-attention-qkv.md)，把“想找什么、谁能提供、读取什么”具体变成 Q/K/V。
