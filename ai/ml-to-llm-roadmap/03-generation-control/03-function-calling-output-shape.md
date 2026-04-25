# Function Calling 的输出形态

## 这篇解决什么问题

当用户问“上海明天天气怎么样”时，模型自己通常不知道实时天气。系统需要让模型表达“我想调用天气工具，并给出城市参数”。Function Calling 解决的就是这种输出形态问题：让模型输出一个结构化 call，而不是一段自由文本。

这一篇只讨论 Function Calling 的输出协议和边界，不讨论 Agent 的计划、循环、记忆、多步反思或工具编排架构。这些会放到未来 Agent 模块单独系统化。

## 学前检查

读这篇前，最好先理解：

- [结构化输出与约束解码](./02-structured-output-constrained-decoding.md)
- 解码参数为什么影响稳定性：[解码参数：Temperature、Top-k、Top-p](./01-decoding-parameters.md)

如果你已经理解 Schema 约束，就可以把 Function Calling 看成一种特殊 schema：输出对象里包含函数名和参数。

## 概念为什么出现

自由文本回答适合给人看，但程序不能稳定地从自由文本里判断：

- 该调用哪个工具？
- 参数是什么？
- 参数是否符合类型和枚举要求？
- 模型是要调用工具，还是已经能直接回答？
- 多个工具调用是否可以并行？

Function Calling 出现，是为了把这些决定变成明确的结构化输出，让应用层可以解析、验证和执行。

## 最小心智模型

Function Calling 不是“模型自动执行工具”。更准确的流程是：

```text
开发者提供工具 schema
模型生成 tool call 形状
应用层解析并执行真实工具
应用层把工具结果交回模型或直接返回
模型生成最终自然语言答案
```

边界要清楚：模型负责生成“想调用什么”和“参数是什么”；你的程序负责真正执行工具、处理错误、注入结果和决定是否继续。

## 最小例子

工具 schema 描述了一个天气函数，例如 `get_weather(city)`。当用户问：

```text
上海天气怎么样？
```

模型可能输出：

```json
{
  "name": "get_weather",
  "arguments": {"city": "Shanghai"}
}
```

这个 JSON 不是天气结果，也不是工具已经执行。它只是一个结构化意图：调用名为 `get_weather` 的工具，并传入 `city = Shanghai`。

应用层拿到后，才会真正请求天气服务。拿到天气服务返回后，系统可以再让模型生成最终自然语言答案，例如“上海今天多云，气温 18 到 23 度”。

## 原理层

Function Calling 通常包含几类控制：

- arguments：函数参数，通常按 JSON object 表示。
- schema：参数名、类型、必填字段、枚举值和描述。
- tool choice：允许模型自动选择工具、强制某个工具，或禁止工具。
- parallel call shape：模型一次输出多个独立 tool call，应用层需要并发执行并合并结果。
- final natural-language answer：工具结果返回后，模型再组织成人类可读答案。

它和普通结构化输出一样，可以借助 Schema 约束减少格式错误。但 Schema 只能约束形状，不能保证语义完全正确。比如 `city` 字段一定是字符串，不代表模型一定选了正确城市；`unit` 字段是枚举，不代表选择的单位符合用户隐含偏好。

常见失败模式包括：

| 失败模式 | 例子 | 处理方式 |
|----------|------|----------|
| wrong tool | 查天气却选择了日历工具 | 工具选择验证、重试或回退 |
| missing argument | 少了必填 `city` | 参数校验后追问或重试 |
| invalid enum | `unit` 输出 `kelvins` 但枚举不支持 | schema 约束或校验修复 |
| hallucinated tool name | 输出不存在的 `search_weather_now` | 只接受注册工具名 |

并行 tool call 还需要额外处理顺序、部分失败、超时和结果合并。即使模型一次给出多个调用，应用层仍要决定哪些可以并发、哪些有依赖。

## 和应用/面试的连接

在 AI Engineer 面试里，Function Calling 最容易和 Agent 混在一起。可以这样区分：

- Function Calling 是输出协议：模型输出可解析的调用形状。
- Agent 是控制架构：系统如何规划、循环、观察工具结果、决定下一步。

这一篇只覆盖前者。Agent 的多轮 tool loop、planner、executor、memory 和 reflection 都不在本模块范围内，会在未来 Agent 模块处理。

工程上你要能说清：工具 schema 怎么设计，参数如何验证，工具结果如何回传，什么时候强制工具，什么时候允许模型直接回答，以及失败时如何追问、重试或降级。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| Function Calling 会自动执行工具 | 模型只输出 call shape，应用层负责执行 |
| 有 Schema 就不会错 | Schema 限制形状，不保证语义正确 |
| Function Calling 就是 Agent | 它只是 Agent 可能使用的一种输出协议 |
| 工具越多越好 | 工具过多会增加选择错误和 schema 理解成本 |
| 并行调用只是多个 JSON | 还要处理并发、失败、超时和结果合并 |

## 自测

1. Function Calling 和 Agent 有什么边界？
2. 模型输出 tool call 后，谁负责真正执行工具？
3. Schema 为什么不能保证语义正确？
4. 并行 tool call 的输出形态需要额外处理什么？

## 回到主线

生成控制模块到这里形成三层：

```text
解码参数: 控制从概率分布中如何采样
结构化输出: 控制输出是否符合机器可解析格式
Function Calling: 把结构化输出用于工具调用意图表达
```

继续往后学习时，先把 Function Calling 当作输出形态理解。至于 Agent 如何决定是否调用工具、调用几轮、如何处理观察结果，那是后续 Agent 模块的主题。
