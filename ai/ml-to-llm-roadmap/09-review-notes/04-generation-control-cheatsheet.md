# 生成控制面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [生成控制与结构化输出](../03-generation-control/)。

## 30 秒答案

生成控制是在模型给出下一个 token 概率分布后，控制“怎么选”和“输出长什么样”。Temperature 调分布尖锐度，Top-k/Top-p 截断候选；JSON mode 主要管 JSON 语法，Schema/约束解码管字段、类型和枚举；Function Calling 是一种 tool call 形状，执行工具仍由应用层负责；生产里还要做 validation、retry、fallback 和监控。

## 2 分钟展开

LLM 不是一次性写完整答案，而是逐 token 生成。Temperature 作用在 logits 到概率的过程：低温度更稳定，高温度更多样。Top-k 保留概率最高的固定 k 个候选，Top-p 保留累计概率达到 p 的最小候选集合。它们影响稳定性和多样性，但不改变模型知识，也不能保证结构合法。

结构化输出要分层看：prompt 只是自然语言要求，JSON mode 让输出更像合法 JSON，Schema/grammar-constrained decoding 把字段、类型、枚举和语法路径放进生成约束，validation-retry 是生成后的补救。约束越靠近解码过程，格式保证越强；越靠后处理，越像失败恢复。

Function Calling 本质上是结构化输出：模型输出函数名和 arguments，应用层解析、校验、执行真实工具，再决定是否把结果交回模型。它不是 Agent，也不是模型自动执行工具。RAG 和 Agent 可以在对应系统里使用这类输出协议，但不是本模块默认内容。

## 高频追问

| 追问 | 回答 |
|------|------|
| Temperature、Top-k、Top-p 分别控制什么？ | Temperature 调概率分布尖锐度，Top-k 按固定数量截断候选，Top-p 按累计概率截断候选。 |
| 低 Temperature 能保证 JSON 正确吗？ | 不能。它只降低随机性，格式合法还需要 JSON mode、Schema 约束或校验重试。 |
| JSON mode 和 Schema 有什么区别？ | JSON mode 主要保证 JSON 语法形态；Schema 进一步限制字段、类型、必填项和枚举。 |
| Constrained decoding 的核心直觉是什么？ | 每一步生成前屏蔽不合法 next token，只允许符合当前语法或 schema 的 token 路径继续。 |
| Function Calling 的边界是什么？ | 模型只生成 tool call 形状；应用层负责参数校验、工具执行、错误处理和结果回传。 |
| 结构化输出失败怎么兜底？ | 先解析和 schema validation，失败时重试、修复、降级、追问或转人工，并记录失败类型。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Temperature vs Top-p | 都叫“随机性参数” | Temperature 改分布形状，Top-p 改候选集合 |
| Top-k vs Top-p | 都是截断 | Top-k 固定数量，Top-p 随概率分布变化 |
| JSON mode vs Schema | 以为 JSON 合法就等于业务可用 | JSON 合法不代表字段、类型、枚举或语义正确 |
| Schema vs correctness | 以为 schema 能保证答案正确 | Schema 管形状，事实和业务判断还要评估或校验 |
| Function Calling vs Agent | 以为有工具调用就是 Agent | Function Calling 是输出协议，Agent 是控制架构 |

## 项目连接

- 做字段抽取或分类路由：低温度加 Schema 约束，枚举字段不要只靠 prompt 描述。
- 做下游系统集成：把输出契约、parser、validation 和 retry 设计在一开始，而不是上线后补。
- 做工具调用：说明 tool schema、参数校验、错误处理和结果回传，避免说“模型自动调用工具”。
- 做质量排查：schema failure、invalid enum、missing field、hallucinated tool name 都要进入日志和回归集。

## 反向链接

- [解码参数：Temperature、Top-k、Top-p](../03-generation-control/01-decoding-parameters.md)
- [结构化输出与约束解码](../03-generation-control/02-structured-output-constrained-decoding.md)
- [Function Calling 的输出形态](../03-generation-control/03-function-calling-output-shape.md)
- [Decoder-only 与逐 Token 生成](../04-transformer-foundations/08-decoder-only-generation.md)
