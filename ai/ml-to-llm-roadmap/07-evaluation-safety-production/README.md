# 07 评估、安全与生产排查

> **定位**：这个模块解释 LLM 应用上线后如何判断“好不好、安不安全、哪里坏了”。它把评估、安全和生产排查放在一起，因为真实系统里这三件事经常互相影响。

## 默认学习顺序

1. [LLM 评估与 LLM-as-Judge](./01-llm-evaluation-judge.md)
2. [幻觉、安全与 Guardrails](./02-hallucination-safety-guardrails.md)
3. [生产排查、监控与回归定位](./03-production-debugging-monitoring.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| LLM 为什么会逐 token 生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| 解码参数为什么影响输出稳定性 | [解码参数](../03-generation-control/01-decoding-parameters.md) |
| 延迟和成本为什么要拆成指标 | [推理优化、部署与成本](../06-inference-deployment-cost/) |

## 这个模块的主线

LLM 应用不能只靠“我试了几个问题感觉不错”上线。真实系统要回答三类问题：

```text
评估: 输出是否满足任务目标？
安全: 输出是否越界、编造或被攻击诱导？
生产排查: 当指标变差时，坏在输入、模型、提示词、解码、解析、评估还是基础设施？
```

学完这个模块，你应该能设计一个最小可用的 eval set，解释 LLM-as-Judge 为什么需要 rubric 和校准，区分幻觉、grounding、instruction following 与 policy safety，并把线上问题拆成可定位、可监控、可回归验证的组件。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版数据与评估](../06-llm-core/09-data-evaluation.md)
- [旧版安全与幻觉](../06-llm-core/10-safety-hallucination.md)
- [旧版 LLM-as-Judge](../06-llm-core/14-llm-as-judge.md)
- [旧版生产排查](../07-theory-practice-bridge/04-production-debugging.md)
