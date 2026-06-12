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

接上一篇的心智模型：`prompt -> predict next token`。要预测第一个输出 token，模型必须先把整个 prompt 完整跑一遍 Transformer——这一遍就叫 prefill（预填充）。

具体发生了什么：假设 prompt 有 100 个 token。prefill 阶段这 100 个 token 一起进入模型，每一层里每个 token 都算出自己的 Q/K/V、做 attention、过 FFN。跑完这一遍，得到两样东西：

- **最后一个位置的 hidden state**：它已经"读过"全部 prompt，过输出层就能预测第一个输出 token。
- **每一层、每个 prompt token 的 K 和 V**：这些被存进缓存，就是 KV Cache 的初始内容。

"预填充"填的就是 KV Cache：在逐 token 生成开始之前，先把 prompt 部分的 K/V 一次性填进去。这 100 个 token 互相之间没有先后依赖（每个 token 的 Q/K/V 各自独立计算，attention 是一次矩阵乘法），所以 prefill 可以一次前向并行完成，不需要像生成阶段那样一个一个来。

```text
prompt (100 tokens) --一次前向--> 100 个 token 的 K/V 存入 KV Cache
                              \-> 最后位置 hidden state -> 第一个输出 token
```

### Decode

Decode 是逐步生成新 token 的阶段，对应上一篇"把新 token 接回上下文，继续预测下一个"的循环。每一步只有一个新 token 进入模型：它算出自己的 Q/K/V，用 Q 去读 KV Cache 里全部历史 K/V 做 attention，再把自己的 K/V 追加进缓存。历史 token 的 K/V 不重算——这就是缓存的意义。

### KV Cache 缓存什么

KV Cache 缓存每一层历史 token 的 Key 和 Value。Query 来自当前新 token，历史 K/V 可以复用。

注意 K 和 V 是"每个 token 各自一份"的向量，不是"token 对 token"的关系数据：100 个 token 在某一层就是 100 个 K 向量加 100 个 V 向量，结构上类似一个只追加的 `List<Vector>`，而不是 100×100 的矩阵。"谁该关注谁"的注意力分数（Q·K）是 decode 每一步用新 token 的 Q 现算的，不在缓存里。

位置信息也已经在缓存里了。位置在 K/V 被算出来**之前**就已经进入计算：要么在 embedding 阶段就加进了输入向量（绝对位置编码，见 [02-token-to-vector.md](./02-token-to-vector.md)），要么在算注意力前直接对 Q 和 K 做随位置变化的旋转（RoPE，LLaMA/Qwen 等主流模型的做法）。所以缓存里第 7 个 token 的 K 天然带着"我在第 7 位"的信息，复用时不需要再补位置。

### "每一层"指什么：两个方向不要混

"每一层历史 token 的 K/V"里的"层"，指模型**深度**方向的 Transformer 层（比如 32 层），不是 decode 的步数。两个方向分开看：

- **深度方向（层与层之间）**：每层有自己的 `W_K`/`W_V`，且每层的输入 `x` 也不同（深层的 `x` 已混入更多上下文），所以**同一个 token 在每层的 k/v 都不一样**，必须按层各存一份，层之间不能共用。
- **时间方向（步与步之间）**：每生成一个 token，它依次穿过 32 层，在每层算出该层的 k/v、追加进**该层**的缓存。"只差一个 token、不断累加"说的是这个方向。

```text
KV Cache 结构（32 层模型，当前历史 101 个 token）：
layer 1:  K[101 个], V[101 个]
layer 2:  K[101 个], V[101 个]
...
layer 32: K[101 个], V[101 个]

生成下一个 token：新 token 穿过 32 层，每层各追加一条
-> 所有层都变成 K[102 个], V[102 个]
```

所以缓存总量 ≈ `2(K和V) × 层数 × 历史 token 数 × 向量维度`——层数和 token 数相乘，这就是长上下文显存压力的来源。

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
- 流式输出能更早看到结果，是因为 token 边生成边返回；KV Cache 则让每步 decode 少重复计算历史 K/V。
- API 的 prompt caching / vLLM 的 prefix caching 就是跨请求共享 KV Cache：causal mask 保证前缀的 K/V 不受后文影响，且 K/V 由权重和 token 序列确定性算出，所以**逐 token 完全相同的前缀**（如共享 system prompt）只需 prefill 一次，后续请求直接复用。中间差一个 token，从那一点起全部失效。
- "逐 token 相同"听起来命中率很低，其实命中靠的是**结构性重复**，不是两个人恰好问同一句话：多轮对话每轮重发完整历史（前缀=上一轮全部内容，自己命中自己）；Agent 每步工具调用 context 只增不减；所有用户共享同一段 system prompt + 工具定义。对应的工程实践：稳定内容排前、易变内容排后，prompt 开头别放时间戳。
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

系统学习到这里先完成 Transformer 主线。面试前再读 [Transformer 面试阅读路径](../interview-paths/ai-engineer-transformer.md) 和 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。
