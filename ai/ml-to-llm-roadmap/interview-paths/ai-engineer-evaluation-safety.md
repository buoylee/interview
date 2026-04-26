# AI Engineer 面试路径：评估、安全与生产稳定性

## 适用场景

- 需要把“感觉模型不错”变成可度量、可回归、可监控的工程体系。
- 面试中会被追问 eval、LLM-as-Judge、幻觉、Prompt Injection、guardrails 和线上回退定位。
- RAG 与 Agent 有独立面试路径；本路径先处理通用 LLM 应用的质量与安全闭环。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [LLM Evaluation and Judge](../07-evaluation-safety-production/01-llm-evaluation-judge.md) | 设计离线 eval、在线指标和 judge 口径 |
| 2 | [Hallucination, Safety and Guardrails](../07-evaluation-safety-production/02-hallucination-safety-guardrails.md) | 分类风险并设计缓解层 |
| 3 | [Production Debugging and Monitoring](../07-evaluation-safety-production/03-production-debugging-monitoring.md) | 建立线上定位和回归监控方法 |
| 4 | [Evaluation Safety Cheatsheet](../09-review-notes/07-evaluation-safety-production-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先按 eval 闭环复述：任务定义、样本集、指标、人工标注、LLM-as-Judge、回归门禁。
2. 再按风险复述：事实幻觉、指令冲突、越权工具调用、敏感输出和 Prompt Injection。
3. 用线上事故方式复述定位：输入分布、模型版本、prompt 版本、检索结果、解析失败、下游依赖。
4. 最后读 [Evaluation Safety Cheatsheet](../09-review-notes/07-evaluation-safety-production-cheatsheet.md)，补齐面试表达。

## 必答问题

- 怎么设计 LLM eval？
- LLM-as-Judge 有什么风险？
- 幻觉有哪些类型，怎么缓解？
- Prompt Injection 怎么分类和防御？
- 线上质量回退怎么定位？
- Guardrails 应该放在输入、生成中还是输出后？
- 如何区分模型问题、prompt 问题、数据问题和系统问题？

## 可跳过内容

- 不展开 RAG 专属评估如检索召回率和 chunk 命中率。
- 不展开 Agent 工具权限系统和多步轨迹评估。
- 不把 LLM-as-Judge 当唯一真值；要保留人工标注和业务指标。

## 复习笔记

从系统学习页开始，最后用 [Evaluation Safety Cheatsheet](../09-review-notes/07-evaluation-safety-production-cheatsheet.md) 收口。
