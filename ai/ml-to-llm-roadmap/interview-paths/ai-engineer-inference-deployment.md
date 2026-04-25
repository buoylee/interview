# AI Engineer 面试路径：推理、部署与成本

## 适用场景

- 已会调用模型，但需要解释延迟、吞吐、显存和成本为什么变化。
- 面试中会被问到 prefill、decode、KV Cache、batching、vLLM、量化和长上下文优化。
- RAG 和 Agent 先延后；本路径先建立模型服务本身的性能和成本模型。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [Prefill, Decode and KV Cache](../06-inference-deployment-cost/01-prefill-decode-kv-cache.md) | 区分 prompt 处理和逐 token 生成 |
| 2 | [Batching, vLLM and Quantization](../06-inference-deployment-cost/02-batching-vllm-quantization.md) | 理解吞吐、显存管理和压缩 |
| 3 | [Long Context, Edge and Cost](../06-inference-deployment-cost/03-long-context-edge-cost.md) | 解释长上下文、端侧和成本优化 |
| 4 | [Inference Deployment Cheatsheet](../09-review-notes/06-inference-deployment-cost-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先画出一次请求：prefill 读 prompt，decode 逐 token 生成，KV Cache 复用历史注意力信息。
2. 再解释服务端优化：continuous batching、PagedAttention、量化、并发限制和缓存策略。
3. 用一个长上下文场景复述成本来源：输入 token、输出 token、显存占用、延迟和质量风险。
4. 最后读 [Inference Deployment Cheatsheet](../09-review-notes/06-inference-deployment-cost-cheatsheet.md)，把概念压成面试短答。

## 必答问题

- Prefill 和 Decode 的瓶颈分别是什么？
- KV Cache 缓存的是什么？
- vLLM/PagedAttention 解决什么问题？
- 量化如何影响速度、显存和质量？
- 长上下文为什么贵，怎么优化？
- 为什么首 token 延迟和总生成时长要分开看？
- 如何在吞吐、延迟和成本之间做部署取舍？

## 可跳过内容

- 不深入 CUDA kernel、张量并行和分布式训练细节。
- 不展开 RAG chunking 或 Agent 多轮调用成本。
- 不背具体云厂商价格，重点掌握成本由哪些变量驱动。

## 复习笔记

从系统学习页开始，最后用 [Inference Deployment Cheatsheet](../09-review-notes/06-inference-deployment-cost-cheatsheet.md) 收口。
