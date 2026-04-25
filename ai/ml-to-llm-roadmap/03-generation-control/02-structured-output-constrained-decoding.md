# 结构化输出与约束解码

## 这篇解决什么问题

很多 LLM 应用不是把回答直接展示给人，而是要把结果交给程序继续处理。程序需要稳定的结构，例如 JSON、枚举值、数组或嵌套对象。

这一篇解决的问题是：为什么“请你输出 JSON”在生产里经常不够，以及 JSON mode、Schema 约束、grammar-constrained decoding 和 validation-retry 分别解决哪一层问题。

## 学前检查

读这篇前，最好先理解：

- [解码参数：Temperature、Top-k、Top-p](./01-decoding-parameters.md)
- Decoder-only 模型逐 token 生成的过程：[Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)

如果你已经知道模型每一步是在选下一个 token，就能理解约束解码的核心：在选择前先屏蔽不合法 token。

## 概念为什么出现

Prompt-only JSON 指令在 demo 里常常够用，但生产中会遇到这些问题：

- 模型可能在 JSON 前后加解释文字。
- 字符串、逗号、括号可能不完整。
- 字段名可能拼错，类型可能错。
- 枚举值可能输出一个看起来合理但系统不接受的新值。
- 长输出或复杂嵌套时，错误概率会累积。

这些问题的根源是：prompt 只是自然语言约束，模型仍然在自由文本空间里生成。结构化输出需要把“格式要求”从建议变成解码过程的一部分，或至少在输出后有明确的验证和失败处理。

## 最小心智模型

结构化输出可以分成四层：

```text
Prompt 约束: 告诉模型输出 JSON
JSON mode: 让输出保持 JSON 语法形态
Schema/Grammar 约束: 限制字段、类型、枚举和语法路径
Validation-retry: 输出后检查，失败时重试或降级
```

约束越靠近解码过程，格式保证越强；越靠后处理，越像补救。

## 最小例子

你希望模型判断一个问题是否能回答，并给出置信度：

```json
{"answer": "yes", "confidence": 0.82}
```

一个 prompt-only 写法可能是：

```text
请只输出 JSON，字段包括 answer 和 confidence。
```

它可能返回：

```text
Sure, here is the JSON:
{"answer": "yes", "confidence": "high"}
```

这个结果对人可读，但对程序不稳定：前面有多余文字，`confidence` 也不是数字。Schema 约束会把期望说得更具体：`answer` 只能是 `yes` 或 `no`，`confidence` 必须是 0 到 1 之间的数字。

## 原理层

约束解码的核心直觉是“mask invalid next tokens”。模型每一步都会给出所有候选 token 的概率。如果当前已经生成：

```json
{"answer":
```

那么下一步合法 token 可能只能是字符串开头、空格或符合语法的片段，而不能是 `}`、任意解释句或无关字段。约束解码会把不合法 token 的概率屏蔽掉，只允许合法路径继续。

几种常见机制的边界不同：

| 机制 | 解决的问题 | 边界 |
|------|------------|------|
| JSON mode | 输出必须像 JSON | 不一定符合你的字段和类型要求 |
| Schema-constrained decoding | 字段、类型、枚举更稳定 | 语义仍可能错 |
| Grammar-constrained decoding | 能表达更一般的语法规则 | 需要设计 grammar，复杂时影响延迟 |
| Validation-retry | 发现错误后补救 | 不是保证，重试仍可能失败 |

Validation-retry 很有用，但它是 fallback，不是 guarantee。它依赖模型下一次能修好，也会增加延迟、成本和状态处理复杂度。

## 和应用/面试的连接

结构化输出常见在这些场景：

- 信息抽取：从用户输入里抽字段。
- 分类路由：输出固定枚举值，决定后续流程。
- 审核与风控：输出原因、风险等级和证据。
- UI 生成：输出列表、表单、操作建议。
- 工具调用前的参数准备：输出符合 schema 的 arguments。

面试中可以这样组织回答：prompt 约束是自然语言层面的要求，constrained decoding 是生成过程层面的限制；Schema 能减少格式错误，但不能保证模型理解业务语义；生产系统还需要验证、重试、降级和监控。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| “只输出 JSON”就足够稳定 | prompt-only 不能阻止非法 token 被采样 |
| JSON mode 等于 Schema 约束 | JSON mode 主要保证语法形态，不等于字段语义正确 |
| Schema 能保证答案正确 | Schema 只能限制形状，不能保证事实和业务判断 |
| validation-retry 可以替代约束解码 | 它是失败后的补救，会增加延迟且仍可能失败 |
| 结构化输出没有成本 | 约束、验证和重试都会影响延迟与失败处理 |

## 自测

1. Prompt 约束和 constrained decoding 的根本区别是什么？
2. Schema 约束为什么能减少格式错误？
3. 为什么 validation-retry 不能替代真正的约束解码？
4. 结构化输出为什么会影响延迟和失败处理？

## 回到主线

这一篇解释了如何让模型输出可被程序消费的结构。下一篇看 Function Calling：它本质上也是一种结构化输出形态，只是这个结构表示“想调用哪个函数，以及参数是什么”。

下一篇：[Function Calling 的输出形态](./03-function-calling-output-shape.md)
