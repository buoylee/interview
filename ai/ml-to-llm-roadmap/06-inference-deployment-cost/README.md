# 06 推理优化、部署与成本

> **定位**：这个模块解释为什么 LLM 推理慢、贵、吃显存，以及工程上如何通过 KV Cache、batching、量化、长上下文策略和端侧部署降低成本。

## 默认学习顺序

1. [Prefill、Decode 与 KV Cache](./01-prefill-decode-kv-cache.md)
2. [Batching、vLLM/PagedAttention 与量化](./02-batching-vllm-quantization.md)
3. [长上下文、端侧部署与成本估算](./03-long-context-edge-cost.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 的逐 token 生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| KV Cache 的基本直觉 | [KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md) |
| Attention 为什么随序列变贵 | [Self-Attention QKV](../04-transformer-foundations/04-self-attention-qkv.md) |

## 这个模块的主线

LLM 推理不是一次函数调用就结束，而是先读完输入，再一个 token 一个 token 地写输出。成本和延迟来自几类问题：

```text
输入越长: prefill 越贵，KV Cache 越占显存
输出越长: decode 步数越多，用户等待越久
并发越高: batching 和显存管理决定吞吐
部署越受限: 量化、小模型和端侧推理决定能不能跑
```

学完这个模块，你应该能把一个慢或贵的 LLM 服务拆成可分析的指标：TTFT、tokens/sec、上下文长度、batch size、显存占用、重试率和输入/输出 token 成本。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版推理优化](../06-llm-core/05-inference-optimization.md)
- [旧版长上下文技术](../06-llm-core/13-long-context.md)
- [旧版端侧/小模型部署](../06-llm-core/15-edge-deployment.md)
