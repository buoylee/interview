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

这就是自回归语言模型。

### Causal Mask

生成第 `t` 个 token 时，模型不能偷看未来 token。Causal Mask 会遮住当前位置之后的信息。

```text
token 1 can see: token 1
token 2 can see: token 1, token 2
token 3 can see: token 1, token 2, token 3
```

### Logits 到下一个 token

最后一层输出会变成词表上每个 token 的分数，也就是 logits。解码策略再从这些分数中选择下一个 token。

### KV Cache

生成新 token 时，历史 token 的 K/V 不变，可以缓存。这样每一步只需要为新 token 计算新的 K/V，并读取历史缓存。

## 和 LLM 应用的连接

| 应用现象 | Decoder-only 视角 |
|----------|-------------------|
| 流式输出 | 自回归逐 token 生成 |
| Function Calling 是生成结构化 token | 工具名和参数也是 token 序列 |
| KV Cache 占显存 | 每层缓存历史 token 的 K/V |
| 长对话越来越贵 | 上下文 token 越多，缓存和注意力读取越重 |
| 低温度更稳定 | 解码策略减少随机性 |

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

用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 做复习。如果 Residual、Norm 或 FFN 仍不清楚，回到 [deep-learning foundations](../foundations/deep-learning/) 补课。
