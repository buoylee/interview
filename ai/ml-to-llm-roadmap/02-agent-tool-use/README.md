# 02 Agent 与工具调用

> **定位**：这个模块解释什么时候需要 Agent，以及如何把 LLM 的结构化输出、工具执行、状态、记忆、恢复和安全控制组成可上线的多步执行系统。

## 默认学习顺序

1. [Agent 边界与执行循环](./01-agent-boundary-and-loop.md)
2. [工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)
3. [状态、记忆与任务规划](./03-state-memory-and-planning.md)
4. [Agent 评估、安全与生产排查](./04-agent-evaluation-safety-production.md)
5. [Agent 模式与架构选型](./05-agent-patterns-and-architectures.md)
6. [Agent Runtime 工程](./06-agent-runtime-engineering.md)
7. [Agent、Workflow 与持久化状态](./07-agent-workflow-and-durable-state.md)
8. [Agent 记忆系统深水区](./08-agent-memory-deep-dive.md)
9. [Agent 安全深水区](./10-agent-security-deep-dive.md)
10. [Agent Eval 实战](./11-agent-eval-practice.md)

## 分层学习路径

| 层级 | 阅读顺序 | 目标 |
|------|----------|------|
| 基础层 | 01 -> 02 -> 03 -> 04 -> 05 | 建立 Agent 边界、工具、状态、评估和模式选型 |
| 工程层 | 06 -> 07 -> 08 -> 10 -> 11 | 掌握 runtime、durable workflow、memory、安全和 eval 实战 |
| 高级层 | 09 -> 12 -> 13 | 后续扩展 multi-agent、coding agent 和平台案例 |

## 推荐路径

| 目标 | 路径 |
|------|------|
| 面试冲刺 | 01 -> 02 -> 03 -> 05 -> 04 -> 速记 |
| 系统落地 | 01 -> 02 -> 03 -> 05 -> 06 -> 07 -> 08 -> 10 -> 11 |

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Function Calling 只是输出形态 | [Function Calling 的输出形态](../03-generation-control/03-function-calling-output-shape.md) |
| 结构化输出为什么需要校验 | [结构化输出与约束解码](../03-generation-control/02-structured-output-constrained-decoding.md) |
| RAG 和记忆检索的关系 | [RAG 与检索系统](../01-rag-retrieval-systems/) |
| 生产排查和监控为什么重要 | [生产排查、监控与回归定位](../07-evaluation-safety-production/03-production-debugging-monitoring.md) |

## 这个模块的主线

Agent 不是“模型会自动执行工具”，而是一个受控循环：

```text
目标 -> 状态 -> 选择下一步 -> 生成 tool call -> 应用执行工具 -> 观察结果 -> 更新状态 -> 停止或继续
```

学完本模块，你应该能区分普通 LLM 调用、Function Calling、workflow 和 Agent，并能设计工具权限、失败恢复、状态管理、评估、安全和生产排查；同时能说明 ReAct 以外的 plan-and-execute、router/supervisor、graph-constrained、reflection、multi-agent、memory-augmented 和 durable agent 等模式该如何选型。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版 Agent 架构理论](../07-theory-practice-bridge/02-agent-architecture.md)
- [旧版 Compound AI Systems](../07-theory-practice-bridge/05-compound-ai-systems.md)
