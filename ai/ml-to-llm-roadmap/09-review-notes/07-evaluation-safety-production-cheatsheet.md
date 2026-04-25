# 评估安全生产面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [评估、安全与生产排查](../07-evaluation-safety-production/)。

## 30 秒答案

LLM 上线不能只看几个 demo，要用 golden set、regression set、offline/online eval 和清晰 rubric 评估质量。LLM-as-Judge 能扩展评估吞吐，但必须用人类样本校准。幻觉要区分 factuality 和 grounding；prompt injection 要把外部内容当数据而不是高优先级指令；生产回归要从 input、prompt、model、decoding、parser、guardrail、infra 逐段定位。

## 2 分钟展开

LLM 输出开放，exact match 往往不够。评估要先定义任务目标和失败类型，再构造 golden set 覆盖核心样本，regression set 覆盖历史 bug 和边界场景。Offline eval 用来发布前比较模型、prompt 和参数；online eval 用真实流量、用户反馈、抽样标注或 A/B 看上线表现。

LLM-as-Judge 是可扩展评估器，不是自动真相。它需要 rubric，把 correctness、helpfulness、grounding、safety 等维度拆开评分。Judge 可能偏爱长答案、受顺序影响、忽略事实细节或过度保守，所以要用 human eval 抽样校准，把分数当趋势信号。

安全上，幻觉是看似合理但无依据或不符合事实的内容。Factuality 看是否符合外部事实，grounding 看是否被当前上下文支持。Guardrails 是输入检测、prompt/解码约束、输出验证、拒答、red teaming、监控和回归集的组合。Prompt injection 分直接注入和间接注入；外部文档、网页或工具结果只能当数据，不能覆盖系统指令。

## 高频追问

| 追问 | 回答 |
|------|------|
| 如何设计 LLM eval？ | 先定任务和失败类型，再建 golden/regression set，用 rubric 多维评分，并接入发布前后流程。 |
| Offline eval 和 online eval 区别是什么？ | Offline 可重复、适合发布前比较；online 更真实、适合观察流量和用户反馈。 |
| LLM-as-Judge 为什么要校准？ | Judge 有偏差和漂移，必须用人类样本、已知好坏样本和一致率检查。 |
| 幻觉、factuality、grounding 怎么区分？ | 幻觉是无依据或错误生成；factuality 看外部事实；grounding 看是否被给定证据支持。 |
| Prompt injection 怎么解释？ | 用户或外部内容试图覆盖高优先级指令；外部内容应作为数据处理并做验证。 |
| 生产质量回归怎么定位？ | 固定失败样本，按 input、context、prompt、model、decoding、parser、guardrail、infra 对比版本。 |
| Schema failure 突增查什么？ | 查 prompt/schema 版本、结构化输出能力、解码参数、parser、validation-retry 和模型版本。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Golden set vs regression set | 都是评估集 | Golden 覆盖核心任务，regression 防历史问题复发 |
| Judge score vs truth | 以为分数就是事实 | Judge 是评估器，需要 rubric 和人类校准 |
| Factuality vs grounding | 以为事实正确就 grounded | Grounding 要求答案被当前证据支持 |
| Guardrails | 以为是一个安全开关 | 它是输入、生成、输出、评估和监控组合 |
| HTTP 200 vs success | 以为接口成功就是质量成功 | LLM 可能返回流畅但错误、越权或不可解析的答案 |

## 项目连接

- 讲质量提升项目：说明 eval set、rubric、上线前对比、上线后监控和失败样本闭环。
- 讲幻觉治理：先区分缺事实、缺证据、指令冲突和验证缺失，不要只说“加 RAG”。
- 讲安全策略：列出违规输出、敏感信息、危险建议、过度拒答和 prompt injection 的控制点。
- 讲线上排查：用 request id、模型/prompt/schema 版本、参数、输出、评估结果、延迟和成本复现问题。

## 反向链接

- [LLM 评估与 LLM-as-Judge](../07-evaluation-safety-production/01-llm-evaluation-judge.md)
- [幻觉、安全与 Guardrails](../07-evaluation-safety-production/02-hallucination-safety-guardrails.md)
- [生产排查、监控与回归定位](../07-evaluation-safety-production/03-production-debugging-monitoring.md)
- [结构化输出与约束解码](../03-generation-control/02-structured-output-constrained-decoding.md)
- [推理优化、部署与成本](../06-inference-deployment-cost/)
