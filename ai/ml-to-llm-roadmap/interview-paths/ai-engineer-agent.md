# AI Engineer 面试路径：Agent 工具使用

## 适用场景

- 已能设计普通 LLM 调用和 Function Calling，需要在面试中解释多步任务、工具调用和恢复机制。
- 需要说清 Agent、workflow、单次工具调用和普通聊天补全的边界。
- 这不是零基础学习入口；先掌握生成控制和基础系统设计，再用本路径冲刺 Agent 面试。
- RAG 或生成控制只作为前置边界理解，不作为本路径默认复习步骤。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [Agent Boundary and Loop](../02-agent-tool-use/01-agent-boundary-and-loop.md) | 区分 Agent、workflow、Function Calling 和普通 LLM 调用 |
| 2 | [Tool Use and Recovery](../02-agent-tool-use/02-tool-use-and-recovery.md) | 说明工具 schema、权限、校验、失败恢复和重试 |
| 3 | [State, Memory and Planning](../02-agent-tool-use/03-state-memory-and-planning.md) | 区分 state、memory、planning 的作用和风险 |
| 4 | [Agent Evaluation, Safety and Production](../02-agent-tool-use/04-agent-evaluation-safety-production.md) | 建立评估、限流、审计、安全和上线口径 |
| 5 | [Agent Tool Use Cheatsheet](../09-review-notes/02-agent-tool-use-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先读系统学习页，按“边界和循环 -> 工具执行 -> 状态规划 -> 生产安全”串起来。
2. 用一个真实任务复述 observe-act loop：观察输入、选择动作、调用工具、处理结果、决定是否继续。
3. 准备失败定位表：模型选错工具、schema 不清、参数非法、权限不足、状态污染、工具超时。
4. 最后读 [Agent Tool Use Cheatsheet](../09-review-notes/02-agent-tool-use-cheatsheet.md)，检查答案能否压到 3 到 5 分钟。

## 必答问题

- Agent 和普通 LLM 调用、Function Calling、workflow 的区别？
- ReAct 或 observe-act loop 的核心是什么？
- Tool schema、权限、参数校验和错误恢复怎么设计？
- State、memory、planning 分别解决什么问题？
- Agent 系统怎么评估、限流、审计和防止失控？
- 什么时候不该用 Agent？
- Agent 失败时怎么定位是模型、工具、状态还是权限问题？

## 可跳过内容

- 不做 Agent 框架横向对比，重点是工程边界、工具协议、状态管理和生产风险。
- 不默认引入 RAG；只有当问题需要外部知识检索时，才把 RAG 当作工具或子系统。
- 不展开模型训练和对齐细节，重点放在运行时控制、恢复和审计。

## 复习笔记

从系统学习页开始，最后用 [Agent Tool Use Cheatsheet](../09-review-notes/02-agent-tool-use-cheatsheet.md) 收口。
