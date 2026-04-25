# 4.8 Decoder-only 与逐 Token 生成

前一篇已经解释了 Encoder-only、Encoder-Decoder 和 Decoder-only 的差异。本篇只回答一个问题：当架构选择 Decoder-only 后，模型如何基于已有上下文逐 token 生成。

## 你为什么要学这个

GPT、LLaMA、Claude 这类主流 LLM 都以 Decoder-only 自回归生成为核心。理解逐 token 生成，可以解释流式输出、next-token prediction、低温度为什么更稳定，以及 Function Calling 为什么仍然可以看成生成结构化 token。

KV Cache、prefill、decode 和长上下文成本会在下一篇单独讲。本篇先把“模型如何从上下文得到下一个 token”讲清楚。

## 学前检查

- 你知道三种 Transformer 架构范式；不熟先看 [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md)。
- 你知道 Transformer Block 的组成；不熟先看 [05-transformer-block.md](./05-transformer-block.md)。
- 你知道 Self-Attention 会让 token 读取上下文；不熟先看 [04-self-attention-qkv.md](./04-self-attention-qkv.md)。

## 一个真实问题

为什么模型回答问题时不是一次性吐出整段文本，而是一个 token 一个 token 地输出？因为 Decoder-only 模型的基本任务不是“生成完整答案”，而是在当前上下文后面预测下一个 token，再把这个 token 接回上下文，继续预测下一个。

## 核心概念

### Decoder-only 的训练目标

Decoder-only 语言模型训练的是自回归目标：

```text
P(token_t | token_1, token_2, ..., token_{t-1})
```

训练时通常把输入和标签错开一位。输入位置 `t` 可以看见 `token_1` 到 `token_t`，这个位置的 hidden state/logits 用来预测 `token_{t+1}`。等价地说，预测某个答案 token 时，模型只能依赖它之前的 token，不能提前看见答案。

这就是 next-token prediction。它看起来只是预测一个 token，但不断重复后，就能形成句子、代码、JSON 参数或工具调用内容。

### Causal Mask

生成第 `t` 个 token 时，模型不能偷看未来 token。Causal Mask 会遮住当前位置之后的信息，让每个位置只能读取自己和自己之前的上下文。

下面描述的是输入位置的可见范围，不是该位置要预测的答案。比如输入位置 3 可以看见 `token 3`，但它的输出用于预测后面的 `token 4`。

```text
input position 1 can see: token 1
input position 2 can see: token 1, token 2
input position 3 can see: token 1, token 2, token 3
```

Causal Mask 是 Decoder-only 能做自回归生成的关键约束：训练时不能泄漏未来答案，推理时也只能基于已有上下文继续写。

### Logits 到下一个 token

最后一层 Transformer 输出 hidden state 后，会通过输出层映射到整个词表，得到每个候选 token 的分数，也就是 logits。

```text
context tokens -> Transformer -> last hidden state -> vocab logits -> next token
```

logits 越高，表示模型越倾向选择对应 token。实际生成时，系统会用解码策略把 logits 转成下一个 token，然后把新 token 追加到上下文末尾，进入下一轮预测。

### 解码策略最小解释

- Greedy：每一步都选 logits/probability 最高的 token，结果稳定但可能单调。
- Temperature：调节概率分布的尖锐程度，温度越低越保守，温度越高越随机。
- Top-p：只在累计概率达到 `p` 的高概率候选集合里采样，减少低概率 token 乱入。

这些策略只决定“从候选 token 中怎么选”，不改变 Decoder-only 的基本链路：已有上下文预测下一个 token。

## 最小心智模型

```text
prompt -> predict next token
prompt + token 1 -> predict next token
prompt + token 1 + token 2 -> predict next token
...
```

如果输出是文本，token 会逐步拼成句子；如果输出是工具调用，工具名、参数字段和值也可以被看成同一条 token 序列里的后续内容。

## 和 LLM 应用的连接

| 应用现象 | Decoder-only 生成视角 |
|----------|------------------------|
| 流式输出 | 模型每生成一个 token 就可以先返回一个 token |
| Function Calling 是生成结构化内容 | 工具名和参数也是 token 序列 |
| 低温度更稳定 | 解码策略减少随机性 |
| JSON 可能格式错误 | 模型仍在逐 token 生成，除非外层系统施加约束 |
| 长答案需要更久 | 输出 token 越多，decode 步数越多 |

Function Calling 底层仍可理解为生成结构化 token，但 API/runtime 层可能额外施加 schema 约束、参数校验和外部工具执行。模型生成工具名和参数只是完整工具调用流程的一部分。

## 常见误区

- Decoder-only 不是“一次生成整段答案”，而是重复预测下一个 token。
- Causal Mask 不是让模型看不到上下文，而是让它看不到未来 token。
- Greedy、temperature、top-p 是解码策略，不是新的模型架构。
- Function Calling 不是脱离语言模型生成，它通常仍从 token 生成开始，再由系统接管执行。

## 自测

1. Decoder-only 的训练目标是什么？
2. Causal Mask 为什么能防止模型偷看未来 token？
3. logits 如何变成下一个 token？
4. greedy、temperature、top-p 分别影响生成的哪一部分？
5. Function Calling 为什么仍然可以理解成逐 token 生成？

## 下一步

下一篇读 [09-kv-cache-context-cost.md](./09-kv-cache-context-cost.md)，理解为什么 Decoder-only 生成可以缓存历史 K/V，以及长上下文为什么仍然贵。
