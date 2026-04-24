# 4.1 为什么 AI Engineer 需要懂 Transformer

## 你为什么要学这个

你不一定要训练一个大模型，但你需要解释大模型为什么会这样工作。RAG 召回了正确文档但回答仍然错、Agent 工具调用参数不稳定、长上下文成本暴涨、结构化输出偶尔坏掉，这些问题都和 Transformer 的输入表示、注意力、解码和上下文机制有关。

## 学前检查

你需要知道：

- Token 是模型处理文本的最小单位之一；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- 神经网络是一组线性变换和非线性函数的组合；不熟先看 [神经元、MLP 与激活函数](../foundations/deep-learning/01-neuron-mlp-activation.md)。

## 一个真实问题

你的 RAG 系统检索到了包含答案的文档，但模型仍然回答错。可能原因不只在检索层，也可能是：

- 文档片段太长，关键信息在上下文中被稀释。
- Prompt 中多个信息互相竞争，模型注意力分配不理想。
- 模型按生成概率续写，而不是做数据库式精确查询。
- 解码过程在格式、事实和流畅性之间做了取舍。

理解 Transformer 能帮助你把问题拆到更具体的层：输入表示、注意力分配、上下文位置、解码行为和推理缓存。

## 核心概念

### Transformer 解决的核心问题

传统序列模型按顺序读文本，长距离信息要一步步传递。Transformer 让每个 token 可以直接查看其他 token，并根据相关性聚合信息。

```text
RNN/LSTM: token 1 -> token 2 -> token 3 -> token 4
Transformer: 每个 token 同时查看所有 token
```

### AI Engineer 需要掌握的最小模型

```text
文本 -> token IDs -> embedding 向量 -> Transformer Blocks -> logits -> 下一个 token
```

其中：

- `embedding` 决定文本如何进入模型。
- `attention` 决定 token 之间如何读取信息。
- `FFN` 决定每个 token 如何独立加工信息。
- `residual + normalization` 决定深层模型能否稳定运行。
- `decoder-only + causal mask` 决定 GPT 类模型如何逐 token 生成。

## 和 LLM 应用的连接

| 应用问题 | Transformer 相关机制 |
|----------|----------------------|
| RAG 命中文档但回答错 | 上下文组织、注意力竞争、位置影响 |
| Agent 工具调用参数不稳 | 解码、结构化输出、上下文约束 |
| 长上下文慢且贵 | Attention 复杂度、KV Cache |
| 模型幻觉 | 训练目标、生成概率、上下文证据不足 |
| 小模型和大模型能力差异 | 层数、宽度、上下文建模和训练规模 |

## 面试怎么问

- 你做应用为什么还需要懂 Transformer？
- RAG 系统里，Transformer 知识能帮你排查什么问题？
- 为什么长上下文会带来成本和效果问题？
- Agent 的工具调用为什么不是简单 JSON 拼接问题？

完整答法见 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。

## 自测

1. Transformer 相比 RNN/LSTM，最关键的结构差异是什么？
2. 为什么 RAG 答错不一定是向量检索的问题？
3. 为什么结构化输出失败可能和解码有关？
4. 长上下文为什么既影响成本，也影响质量？

## 下一步

下一篇读 [02-token-to-vector.md](./02-token-to-vector.md)，先搞清楚文本如何变成模型能处理的向量。
