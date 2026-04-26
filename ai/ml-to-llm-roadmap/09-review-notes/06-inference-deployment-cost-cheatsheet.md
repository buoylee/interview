# 推理部署成本面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [推理优化、部署与成本](../06-inference-deployment-cost/)。

## 30 秒答案

LLM 推理分 prefill 和 decode：prefill 读完整输入并建立 KV Cache，decode 逐 token 生成并复用历史 K/V。长输入推高 TTFT 和缓存显存，长输出推高 decode 步数。vLLM/PagedAttention 主要优化变长请求下的 KV Cache 管理和吞吐；量化降低显存和带宽成本，但要评估质量；长上下文要当稀缺资源治理。

## 2 分钟展开

Prefill 是“读题”：prompt、历史消息和上下文 token 已知，可以并行处理，但输入越长越贵。Decode 是“逐字作答”：每一步依赖上一步输出，不能一次性并行生成完整答案。KV Cache 缓存每层历史 token 的 K/V，不是缓存最终问答；它减少 decode 重算，但不能消除长 prompt 的 prefill 成本。

线上 serving 还要处理多用户并发和变长请求。Static batching 适合离线批处理，但在线可能让短请求被长请求拖住。Continuous batching 在 decode step 动态加入和移除请求，提高 GPU 利用率。PagedAttention 把 KV Cache 像分页内存一样按块管理，减少碎片和预留浪费。

部署成本来自输入 token、输出 token、重试、fallback、缓存未命中、监控和人工处理。量化用更低精度存权重或计算，能降低显存和带宽压力，但 INT4/INT8 可能在长上下文、代码、数学或格式严格任务上退化。端侧部署通常依赖小模型、量化和本地推理引擎。

## 高频追问

| 追问 | 回答 |
|------|------|
| Prefill 和 decode 的区别是什么？ | Prefill 处理已知输入并建立缓存；decode 逐 token 生成并追加新 token 的 K/V。 |
| KV Cache 缓存什么？ | 缓存历史 token 在各层 attention 里的 Key/Value 表示，不是答案或 attention 权重。 |
| 为什么长上下文贵？ | 输入 token 增加 prefill 时间，KV Cache 占用和读取成本也随上下文增长。 |
| vLLM/PagedAttention 解决什么？ | 主要解决高并发变长请求下的 KV Cache 显存管理、碎片和吞吐问题。 |
| 量化为什么能省钱？ | 降低权重和部分中间表示的存储精度，减少显存占用和内存带宽压力。 |
| 量化的风险是什么？ | 数值误差可能造成质量下降，尤其在长上下文、代码、数学和严格格式任务上要实测。 |
| TTFT 高优先查什么？ | 输入 token、prefill、排队、batching、长上下文拼接和 KV Cache 显存压力。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| TTFT vs tokens/sec | 都叫延迟 | TTFT 偏第一个 token，tokens/sec 偏 decode 吞吐 |
| KV Cache vs response cache | 以为都是缓存答案 | KV Cache 是模型内部 K/V；response cache 是应用层结果复用 |
| PagedAttention vs attention 算法 | 以为改变模型能力 | 它主要优化 KV Cache 显存布局，不改变模型知识 |
| Batch size | 以为越大越好 | 大 batch 提高吞吐，也可能增加排队和单请求延迟 |
| Long context | 以为窗口越长越好 | 更长窗口提高容量，也增加成本、延迟和注意力分散风险 |

## 项目连接

- 用户说“第一个字很慢”：先用 TTFT 拆 prefill、输入长度、排队和模型路由。
- 用户说“输出很慢”：看 decode tokens/sec、输出长度、batching、量化和硬件。
- 账单上涨：拆输入、输出、重试、fallback、缓存未命中和人工复核，不只看模型单价。
- 长文档场景：优先压缩、摘要或选择相关上下文；需要外部知识接入时进入 [RAG 与检索系统](../01-rag-retrieval-systems/)。

## 反向链接

- [Prefill、Decode 与 KV Cache](../06-inference-deployment-cost/01-prefill-decode-kv-cache.md)
- [Batching、vLLM/PagedAttention 与量化](../06-inference-deployment-cost/02-batching-vllm-quantization.md)
- [长上下文、端侧部署与成本估算](../06-inference-deployment-cost/03-long-context-edge-cost.md)
- [KV Cache、上下文长度与推理成本](../04-transformer-foundations/09-kv-cache-context-cost.md)
