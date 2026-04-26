# AI Engineer 面试路径：系统设计与项目叙事

## 适用场景

- 需要把 LLM 能力落到可上线、可观测、可控成本的系统方案。
- 面试中需要讲清模型路由、fallback、eval、监控、成本延迟质量取舍和项目故事。
- RAG 与 Agent 有独立面试路径；本路径先建立通用 AI 系统设计框架，再按题目决定是否引入它们。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [AI System Design Method](../08-system-design-project-narrative/01-ai-system-design-method.md) | 建立需求、风险、数据、模型、评估的回答框架 |
| 2 | [LLM Platform Routing and Cost](../08-system-design-project-narrative/02-llm-platform-routing-cost.md) | 设计模型路由、fallback 和成本控制 |
| 3 | [Project Narrative](../08-system-design-project-narrative/03-project-narrative.md) | 把项目讲成可追问的工程故事 |
| 4 | [System Design Cheatsheet](../09-review-notes/08-system-design-project-narrative-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先用一个题目走完整框架：用户目标、输入输出、质量标准、失败模式、模型选择、系统边界。
2. 再补平台层：路由、缓存、fallback、限流、成本预算、审计和人工兜底。
3. 最后练项目叙事：背景、约束、方案、指标、事故、迭代和可深挖点。
4. 读 [System Design Cheatsheet](../09-review-notes/08-system-design-project-narrative-cheatsheet.md)，检查是否能把答案压到 3 到 5 分钟。

## 必答问题

- AI 系统设计和普通后端系统设计有什么不同？
- 如何设计模型路由和 fallback？
- 如何把成本、延迟、质量一起权衡？
- 如何设计 eval 和监控？
- 怎么讲一个项目让面试官能继续深挖？
- 什么时候引入 RAG、Agent、微调，什么时候不用？
- 如何定义上线前门禁和上线后回滚条件？

## 可跳过内容

- 不默认把所有题目设计成 RAG 或 Agent。
- 不展开具体向量数据库、Agent 框架和云厂商部署细节。
- 不把项目讲成技术清单；重点是约束、决策和结果。

## 复习笔记

从系统学习页开始，最后用 [System Design Cheatsheet](../09-review-notes/08-system-design-project-narrative-cheatsheet.md) 收口。
