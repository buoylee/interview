# AI Engineer 面试路径：生成控制

## 适用场景

- 已能调用 LLM API，但对采样参数、结构化输出和 Function Calling 的边界不够清楚。
- 面试中需要解释“为什么输出不稳定”和“如何让输出可被系统消费”。
- RAG 和 Agent 先延后；本路径只解决单次模型生成的可控性。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [Decoding Parameters](../03-generation-control/01-decoding-parameters.md) | 说清 temperature、top-k、top-p 和重复惩罚 |
| 2 | [Structured Output and Constrained Decoding](../03-generation-control/02-structured-output-constrained-decoding.md) | 区分 prompt 约束、JSON Mode、schema constrained decoding |
| 3 | [Function Calling Output Shape](../03-generation-control/03-function-calling-output-shape.md) | 理解工具调用只是输出结构，不是模型执行工具 |
| 4 | [Generation Control Cheatsheet](../09-review-notes/04-generation-control-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先读系统学习页，按“采样控制 -> 结构约束 -> 工具调用形状”串起来。
2. 给每个概念准备一个反例：参数调低仍可能错、JSON 能解析但不一定符合业务 schema、Function Calling 仍需外部执行。
3. 用一个实际 API 输出链路复述 fallback：校验、重试、降级、人工或规则兜底。
4. 最后读 [Generation Control Cheatsheet](../09-review-notes/04-generation-control-cheatsheet.md)，只补口径，不替代系统学习。

## 必答问题

- Temperature、Top-k、Top-p 分别控制什么？
- JSON Mode 和 schema constrained decoding 的区别？
- Function Calling 是模型执行工具吗？
- Prompt 约束为什么不等于结构化输出保证？
- 结构化输出失败时怎么设计 fallback？
- 为什么低 temperature 不等于确定性和正确性？
- 什么时候应该重试，什么时候应该降级到规则或人工处理？

## 可跳过内容

- 不展开 RAG 检索链路、Agent 多步规划和工具生态。
- 不背具体厂商 SDK 参数名，重点掌握参数含义和失败模式。
- 不深入实现 tokenizer 级 constrained decoding，只需能解释它为什么比 prompt 更强。

## 复习笔记

从系统学习页开始，最后用 [Generation Control Cheatsheet](../09-review-notes/04-generation-control-cheatsheet.md) 收口。
