# Transformer 核心面试速记

## 30 秒答案

Transformer 的核心是 Self-Attention：每个 token 通过 Q/K/V 判断该关注哪些上下文 token，并把相关 token 的 V 加权汇总。现代 LLM 还依赖 FFN、Residual、LayerNorm/RMSNorm 和 Decoder-only 自回归生成；这些概念能帮助应用工程师解释 RAG 上下文组织、长上下文成本、KV Cache、工具调用和生成稳定性问题。

## 2 分钟展开

Self-Attention 的公式是：

```text
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

Q 表示当前 token 想找什么，K 表示每个 token 能被如何匹配，V 是实际内容。`QK^T` 得到 token 两两相关性，除以 `sqrt(d_k)` 防止 softmax 饱和，softmax 产生权重，再加权求和 V。Multi-Head 让不同头在不同子空间捕捉不同关系。

完整 Transformer Block 不是只有 Attention。Attention 负责 token 间通信，FFN 负责 token 内加工，Residual 保留原信息并改善梯度流，LayerNorm/RMSNorm 稳定数值。Decoder-only 模型通过 causal mask 让当前位置只能关注自己和之前的 token，不能关注未来 token；它用 next-token prediction 训练，并在推理时用 KV Cache 复用历史 K/V。

## 面试官追问

| 追问 | 回答 |
|------|------|
| 为什么除以 `sqrt(d_k)`？ | QK 点积的方差随维度增大，数值过大会让 softmax 接近 one-hot，梯度变小；缩放后分布更平滑。 |
| Multi-Head 有什么用？ | 单个头只有一组投影和一个注意力子空间，Multi-Head 可以并行捕捉不同模式。 |
| FFN 的作用是什么？ | Attention 做跨 token 信息聚合，FFN 对每个 token 独立做非线性加工。 |
| 为什么要 Residual？ | 保留原始信息，提供更短的梯度路径，让深层网络更容易训练。 |
| 为什么现代 LLM 多是 Decoder-only？ | 自回归目标简单统一，适合通用生成、对话、工具调用和规模化训练。 |
| KV Cache 缓存什么？ | 缓存历史 token 在各层 Attention 中的 K/V，避免生成每个新 token 时重复计算历史上下文。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Token ID vs Embedding | 以为 ID 本身有语义 | ID 是词表编号，embedding 向量才参与计算 |
| Attention vs FFN | 以为 Transformer 只有 Attention | Attention 负责交流，FFN 负责加工 |
| LayerNorm vs BatchNorm | 以为归一化都一样 | LN/RMSNorm 不依赖 batch，更适合序列和生成 |
| Encoder-only vs Decoder-only | 以为 BERT 和 GPT 只是训练数据不同 | 架构和注意力 mask 不同，任务定位也不同 |
| KV Cache vs Attention weights | 以为缓存的是注意力分数 | 缓存的是 K/V，不是 softmax 后的权重 |

## 记忆钩子

```text
Embedding 让文本变数字。
Attention 让 token 互相读。
FFN 让 token 自己想。
Residual 让信息别丢。
Norm 让数值别炸。
Decoder-only 让模型一步步写。
KV Cache 让历史别重算。
```

## 项目连接

讲 RAG 项目时可以这样连接：

- 检索命中文档但回答错：从上下文组织、注意力竞争和位置影响分析，不只怪向量库。
- 长文档问答成本高：区分 prefill 和 decode；KV Cache 能加速增量生成，但不能消除初始长上下文 Attention 成本，而且缓存内存和读取成本会随上下文增长。
- 工具调用不稳定：说明工具调用本质上也是 Decoder-only 模型生成结构化 token，需要约束解码或 schema 校验。
- 多轮 Agent 变慢：历史对话进入上下文，导致 token 增长和 KV Cache 增长。

## 深入阅读

- [为什么 AI Engineer 需要懂 Transformer](../04-transformer-foundations/01-why-ai-engineers-need-transformer.md)
- [从 Token 到向量](../04-transformer-foundations/02-token-to-vector.md)
- [Self-Attention 与 Q/K/V](../04-transformer-foundations/04-self-attention-qkv.md)
- [Transformer Block](../04-transformer-foundations/05-transformer-block.md)
- [Decoder-only 与逐 Token 生成](../04-transformer-foundations/08-decoder-only-generation.md)
- [KV Cache、上下文长度与推理成本](../04-transformer-foundations/09-kv-cache-context-cost.md)
