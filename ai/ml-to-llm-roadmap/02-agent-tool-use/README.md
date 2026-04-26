# 02 Agent 与工具调用

> **定位**：这个模块解释什么时候需要 Agent，以及如何把 LLM 的结构化输出、工具执行、状态、记忆、恢复和安全控制组成可上线的多步执行系统。

## 默认学习顺序

1. [Agent 边界与执行循环](./01-agent-boundary-and-loop.md)
2. [工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)
3. [状态、记忆与任务规划](./03-state-memory-and-planning.md)
4. [Agent 评估、安全与生产排查](./04-agent-evaluation-safety-production.md)

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

学完本模块，你应该能区分普通 LLM 调用、Function Calling、workflow 和 Agent，并能设计工具权限、失败恢复、状态管理、评估、安全和生产排查。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版 Agent 架构理论](../07-theory-practice-bridge/02-agent-architecture.md)
- [旧版 Compound AI Systems](../07-theory-practice-bridge/05-compound-ai-systems.md)
