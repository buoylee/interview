# Batching、vLLM/PagedAttention 与量化

## 这篇解决什么问题

单个请求已经可以用 prefill、decode 和 KV Cache 来理解。但真实服务面对的是很多用户：有的 prompt 很长，有的只问一句；有的输出 20 个 token，有的输出 1000 个 token；有的刚进入 prefill，有的正在 decode。

这一篇解决的问题是：LLM serving 为什么需要 batching，vLLM/PagedAttention 解决了什么显存管理问题，量化为什么能降低部署成本，以及这些技术的代价是什么。

## 学前检查

读这篇前，最好已经理解：

- Prefill、decode 和 KV Cache：[Prefill、Decode 与 KV Cache](./01-prefill-decode-kv-cache.md)
- Attention 为什么需要历史 K/V：[Self-Attention QKV](../04-transformer-foundations/04-self-attention-qkv.md)
- 模型权重为什么占内存：[神经网络基础](../02-deep-learning/01-neural-network-basics.md)

如果你已经做过 RAG 或 Agent 服务，可以把这里理解成“为什么线上推理不是简单 for 循环调用模型”。

## 概念为什么出现

GPU 擅长并行计算。如果每次只处理一个用户请求，硬件利用率通常很差；但如果把多个请求拼成一个 batch，又会遇到长度不一致、请求不断进出、KV Cache 显存碎片和排队延迟的问题。

Serving 系统要同时解决三件事：

```text
吞吐: 单位时间服务更多 token
延迟: 单个用户不要等太久
显存: 权重、激活和 KV Cache 都要放得下
```

Batching、PagedAttention 和量化就是围绕这三件事出现的。

## 最小心智模型

Static batching 是“等一批人坐满车再发车”。它实现简单，但短请求可能等长请求，实时服务体验容易变差。

Dynamic 或 continuous batching 是“车一直开，路上有人上车下车”。系统在每个 decode step 动态合并仍在生成的请求，让 GPU 尽量保持忙碌。

PagedAttention 是“把 KV Cache 像分页内存一样管理”。请求的上下文长度不同，不再要求每个请求占用一大块连续显存，而是按块分配和复用，减少碎片和浪费。

量化是“用更低精度存权重或计算”。它减少显存和内存带宽压力，但可能带来质量下降、数值误差或某些任务上的退化。

## 最小例子

假设同一时刻有 3 个请求：

```text
A: prompt 200 token，预计输出 20 token
B: prompt 4000 token，预计输出 200 token
C: prompt 80 token，预计输出 800 token
```

Static batching 可能把 A、B、C 塞进同一个固定 batch。B 的长 prompt 拉高 prefill 成本，C 的长输出让 batch 很久才完全结束，A 即使很短也被拖住。

Continuous batching 会在每个 decode step 重新组织活跃请求。A 结束后释放位置，新来的 D 可以加入；B 和 C 继续生成。PagedAttention 让这些请求的 KV Cache 按块管理，A 结束后释放的块可以给 D 使用。

一个最小精度对比：

| 精度 | 常见用途 | 主要收益 | 主要风险 |
|------|----------|----------|----------|
| FP16 | GPU 推理常见基线 | 质量稳定，硬件支持成熟 | 显存占用较高 |
| INT8 | 权重量化或部分计算量化 | 降低显存和带宽压力 | 少数任务可能有精度损失 |
| INT4 | 小模型、本地部署、低成本服务 | 显存占用更低，端侧更可行 | 质量更敏感，需评估具体模型和任务 |

## 原理层

LLM serving 的核心难点不是只把矩阵乘法跑快，而是让不同长度、不同阶段的请求共享 GPU。Prefill 阶段计算量大，decode 阶段每步计算小但频繁，二者混在一起会让调度更复杂。

Static batching 在离线任务中很常见，例如批量跑评测或批量生成数据。它可以把相似长度的输入放一起，减少 padding 浪费。但在线服务中，请求持续到达，固定等一批请求会增加排队时间。

Dynamic batching 会在短时间窗口内聚合请求；continuous batching 更进一步，在 decode 的每一步都允许请求进入和退出。这样可以提升 GPU 利用率，但调度器要管理不同请求的状态、停止条件、KV Cache 和优先级。

PagedAttention 关注的是 KV Cache 的显存布局。传统连续分配容易因为请求长度变化产生碎片，也可能为最大长度预留过多空间。分页式管理把 KV Cache 拆成块，按需分配，降低浪费。它不改变 Transformer 的数学定义，而是改变服务系统如何管理缓存。

量化降低的是权重和有时激活/KV 的存储精度。收益来自更少显存占用和更低带宽需求，尤其在模型权重读取或 KV Cache 访问成为瓶颈时明显。代价是数值表示更粗，某些长上下文、代码、数学或格式严格任务可能更敏感，所以量化方案必须用真实任务评估。

## 和应用/面试的连接

工程上，如果服务 GPU 利用率低但用户延迟高，可能是 batching 窗口、请求长度分布或调度策略不合适。如果显存不够，除了换更小模型，还可以看量化、减少上下文、限制输出长度、优化 KV Cache 管理。

面试里不要只说“vLLM 更快”。更准确的表达是：vLLM 这类 serving 系统通过 continuous batching 和 PagedAttention 等机制，提高高并发、变长请求下的吞吐和显存利用率。

常见问法包括：

- Static batching 和 continuous batching 的差异是什么？
- PagedAttention 解决的是 attention 算法问题还是 KV Cache 管理问题？
- 量化为什么能省显存？为什么可能掉质量？
- 为什么吞吐优化可能伤害单请求延迟？

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| Batching 只会让服务更快 | Batching 提高吞吐，但可能增加排队和 TTFT |
| PagedAttention 改写了模型能力 | 它主要优化 KV Cache 显存管理，不改变模型训练出的能力 |
| INT4 一定比 INT8 划算 | INT4 更省资源，但质量风险更高，需要按任务评估 |
| 显存只被模型权重占用 | KV Cache、激活、batch 和运行时开销也会占显存 |

## 自测

1. Static batching 为什么适合离线批处理，却可能不适合在线聊天？
2. Continuous batching 如何处理请求不断进入和结束的问题？
3. PagedAttention 主要减少哪类显存浪费？
4. FP16、INT8、INT4 的核心取舍是什么？
5. 为什么“GPU 利用率更高”不等于“每个用户都更快”？

## 回到主线

到这里，你已经能理解并发 serving、KV Cache 管理和量化的基本取舍。下一篇继续看：当上下文拉长、部署位置从云端变到端侧、账单需要拆解时，如何系统分析质量、延迟和总成本：[长上下文、端侧部署与成本估算](./03-long-context-edge-cost.md)。
