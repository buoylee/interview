# Prefill、Decode 与 KV Cache

## 这篇解决什么问题

你在 RAG 或 Agent 应用里可能已经见过这些现象：用户刚提交问题时要等一会儿才看到第一个字；一旦开始输出，后面的 token 又像流式打印一样逐步出现；上下文变长后，费用和延迟都明显上升。

这一篇解决的问题是：LLM 推理为什么天然分成 prefill 和 decode 两个阶段，KV Cache 到底缓存了什么，以及为什么这些概念会影响 TTFT、tokens/sec、context length 和 batch size。

## 学前检查

读这篇前，最好已经理解：

- Decoder-only 如何逐 token 生成：[Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)
- Attention 为什么需要 Q/K/V：[Self-Attention QKV](../04-transformer-foundations/04-self-attention-qkv.md)
- KV Cache 的基础直觉：[KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md)

如果你已经有 RAG 或 Agent 使用经验，可以先把这里理解成“为什么塞进 prompt 的每个 token 都会改变延迟和成本”。

## 概念为什么出现

LLM 的服务端要解决两个不同问题：

```text
先读输入: 用户给了 prompt、历史消息、检索片段或工具结果，模型要一次性处理这些上下文。
再写输出: 模型每一步只能生成一个或少量新 token，新 token 又会成为下一步的上下文。
```

这两个问题的计算形态不同，所以工程上把它们拆成 prefill 和 decode。KV Cache 出现，是为了解决 decode 时的重复计算：如果每生成一个新 token 都重新计算所有历史 token 的 K/V，成本会被不断放大。

## 最小心智模型

Prefill 是“读题”。模型把输入 prompt 中的所有 token 过一遍 Transformer，得到每一层 attention 需要的历史 K/V。

Decode 是“逐字作答”。模型把上一步刚生成的 token 作为这一步输入，计算并追加这个 token 的 K/V，再用当前位置 logits 预测下一个 token。

KV Cache 缓存的是过去 token 在每一层 attention 中的 Key 和 Value 表示，不是缓存最终答案，也不是缓存 prompt 到 answer 的映射。

几个服务指标可以这样放：

- TTFT：time to first token，从请求进入到第一个输出 token 出现，通常强烈受 prefill 和排队影响。
- tokens/sec：decode 阶段每秒能生成多少 token。它可以指单个请求的流式输出速度，也可以指整个服务在 batching 后的总吞吐，需要看上下文。
- context length：输入和已生成输出的上下文长度，影响 attention 和 KV Cache 占用。
- batch size：同一时间一起送入 GPU 的请求数量，影响吞吐、排队和显存压力。

## 最小例子

假设用户输入：

```text
Question: Name one capital city in Europe.
Answer:
```

推理可以简化成：

```text
1. Prefill:
   处理 Question: Name one capital city in Europe. Answer:
   为这些历史 token 计算并保存每层 K/V。

2. Prefill 结束时:
   用最后位置的 logits 采样第一个输出 token，得到 "Paris"。
   注意：这一步还没有计算 "Paris" 自己的 K/V。

3. Decode 第 1 步:
   把 "Paris" 作为新输入 token。
   计算并追加 "Paris" 的 K/V。
   用当前位置 logits 预测下一个 token，可能得到 "."。

4. Decode 第 2 步:
   把 "." 作为新输入 token。
   计算并追加 "." 的 K/V。
   再预测下一个 token。
```

如果没有 KV Cache，每次预测下一个 token 前，都要重新计算 prompt 加上此前已生成 token 的历史 K/V。KV Cache 的价值就是复用 prompt 和已生成 token 的 K/V，让 decode 主要为本步新增 token 做增量计算。

## 原理层

在 Transformer attention 里，每个新 token 的 Query 需要和历史 token 的 Key 做匹配，再从对应的 Value 聚合信息。历史 token 的 K/V 在生成过程中不会因为未来 token 出现而改变，所以可以复用。

Prefill 通常更像“大块输入并行计算”：输入 token 都已知，GPU 可以并行处理整个 prompt。长 prompt、RAG 拼接的大量片段、多轮对话历史，都会推高 prefill 时间和 KV Cache 初始占用。

Decode 更像“小步循环计算”：下一步输入依赖上一步输出，不能像 prefill 那样一次性并行生成完整回答。输出越长，循环步数越多。很多线上延迟优化，实际是在平衡 prefill 排队、decode 吞吐、batching 和 KV Cache 显存。

Batch size 不是越大越好。更大的 batch 可以提高 GPU 利用率，但也可能让单个请求排队更久，或者因为 KV Cache 太大导致显存不足。服务系统通常要在用户可感知延迟和整体吞吐之间取舍。

## 和应用/面试的连接

工程上，TTFT 高不一定是模型“生成慢”。它可能来自 prompt 太长、检索片段太多、请求排队、prefill batch 被大请求拖住，或者 KV Cache 显存压力导致调度效率下降。

如果用户抱怨“开始很慢但开始后还行”，优先看 TTFT、输入 token、排队和 prefill。如果用户抱怨“输出像挤牙膏”，再看 decode tokens/sec、输出长度、batching、量化和硬件。

面试里常见问法是：

- Prefill 和 decode 的瓶颈为什么不同？
- KV Cache 缓存的是答案吗？
- 为什么长上下文会增加显存和延迟？
- 为什么同一个模型在低并发和高并发下体验不同？

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| KV Cache 是缓存问答结果 | KV Cache 缓存历史 token 的 K/V 表示，用于后续 attention |
| Prefill 和 decode 只是名字不同 | Prefill 处理已知输入，decode 逐 token 依赖前一步输出 |
| 上下文越长只影响输入价格 | 上下文还会影响 prefill 时间、KV Cache 显存和调度 |
| batch size 越大体验一定越好 | batch 变大可能提高吞吐，也可能增加排队和单请求延迟 |

## 自测

1. Prefill 和 decode 分别解决推理过程中的哪一段问题？
2. KV Cache 复用的是哪些中间结果？为什么不是缓存最终答案？
3. TTFT 高时，你会先检查哪些因素？
4. 为什么输出 token 越多，decode 成本越高？
5. Batch size 增大可能同时带来哪些好处和坏处？

## 回到主线

到这里，你已经能把单个请求拆成 prefill、decode 和 KV Cache。下一篇继续看：当很多用户同时请求、长度又不一样时，服务系统如何用 batching、PagedAttention 和量化提高吞吐并控制显存：[Batching、vLLM/PagedAttention 与量化](./02-batching-vllm-quantization.md)。
