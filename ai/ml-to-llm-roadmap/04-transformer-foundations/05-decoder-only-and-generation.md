# 4.5 Decoder-only 与逐 Token 生成

## 你为什么要学这个

GPT、LLaMA、Claude 这类主流 LLM 都以 Decoder-only 自回归生成为核心。理解 Decoder-only 可以解释 next-token prediction、causal mask、KV Cache、上下文窗口、流式输出和 Function Calling 的底层行为。

## 学前检查

你需要知道：

- Transformer Block 的组成；不熟先看 [04-transformer-block.md](./04-transformer-block.md)。
- Self-Attention 会让 token 读取上下文；不熟先看 [03-self-attention-qkv.md](./03-self-attention-qkv.md)。

## 一个真实问题

为什么模型生成 JSON 时会一个 token 一个 token 地输出？为什么已经生成过的上下文不需要每步完全重算？这些问题都来自自回归生成和 KV Cache。

## 核心概念

### 三种 Transformer 范式

| 范式 | 代表 | 典型用途 |
|------|------|----------|
| Encoder-only | BERT | 理解、分类、向量表示 |
| Encoder-Decoder | T5 | 输入到输出转换 |
| Decoder-only | GPT、LLaMA | 通用生成、对话、工具调用 |

### Decoder-only 的训练目标

```text
给定前面的 token，预测下一个 token
P(token_t | token_1, token_2, ..., token_{t-1})
```

这就是自回归语言模型。训练时通常把输入和标签错开一位：输入位置 `t` 可以看见 `token_1` 到 `token_t`，这个位置的 hidden state/logits 用来预测 `token_{t+1}`。等价地说，预测 `token_t` 时，模型只依赖 `token_1` 到 `token_{t-1}`，不会看见答案 token。

### Causal Mask

生成第 `t` 个 token 时，模型不能偷看未来 token。Causal Mask 会遮住当前位置之后的信息。

下面表格描述的是输入位置的可见范围，不是该位置要预测的答案。比如输入位置 3 可以看见 `token 3`，但它的输出用于预测后面的 `token 4`。

```text
input position 1 can see: token 1
input position 2 can see: token 1, token 2
input position 3 can see: token 1, token 2, token 3
```

### Logits 到下一个 token

最后一层输出会变成词表上每个 token 的分数，也就是 logits。解码策略再从这些分数中选择下一个 token。

### KV Cache

生成新 token 时，历史 token 的 K/V 不变，可以缓存。新 token 仍然要经过每一层并计算自己的 Q/K/V；加速来自复用历史 token 的 K/V，而不是每一步重新计算所有过去 token 的 K/V。

## 和 LLM 应用的连接

| 应用现象 | Decoder-only 视角 |
|----------|-------------------|
| 流式输出 | 自回归逐 token 生成 |
| Function Calling 是生成结构化 token | 工具名和参数也是 token 序列 |
| KV Cache 占显存 | 每层缓存历史 token 的 K/V |
| 长对话越来越贵 | 上下文 token 越多，缓存和注意力读取越重 |
| 低温度更稳定 | 解码策略减少随机性 |

Function Calling 底层仍可理解为生成结构化 token，但 API/runtime 层可能额外施加 schema 约束、参数校验和外部工具执行。模型生成工具名和参数只是完整工具调用流程的一部分。

## 面试怎么问

- BERT、T5、GPT 架构有什么区别？
- 为什么现代 LLM 多数是 Decoder-only？
- 什么是 causal mask？
- KV Cache 为什么能加速推理？
- Function Calling 和普通文本生成在底层有什么共同点？

## 自测

1. Decoder-only 为什么不能看未来 token？
2. 自回归生成和流式输出是什么关系？
3. KV Cache 缓存的是什么？
4. Function Calling 为什么仍然可以理解成生成任务？

## 下一步

用 [Transformer 核心面试速记（后续任务创建）](../09-review-notes/03-transformer-core-cheatsheet.md) 做复习。迁移完成后，如果 Residual、Norm 或 FFN 仍不清楚，回到 [deep-learning foundations（后续任务创建）](../foundations/deep-learning/) 补课。
