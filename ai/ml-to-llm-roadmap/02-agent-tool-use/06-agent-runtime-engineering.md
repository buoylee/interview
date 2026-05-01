# Agent Runtime 工程

## 这篇解决什么问题

前面几篇已经把 Agent 的边界、工具权限和生产评估讲清楚了。但在真实应用里，还缺一层东西：谁负责把这些控制串起来。

Agent runtime 就是应用侧的控制系统。它负责加载状态、组装上下文、调用模型、校验 tool call、执行工具、写入 observation、执行限制策略，并记录可排查的 trace。模型只决定“下一步想做什么”，runtime 决定“这一步能不能做、怎么做、做完如何进入下一步”。

这一篇解决的问题是：怎样把 Agent loop 从一句抽象的“让模型循环调用工具”，落到可恢复、可审计、可限流、可上线的工程结构里。

## 学前检查

读这篇前，建议先理解：

- Agent loop 的边界：[Agent 边界与执行循环](./01-agent-boundary-and-loop.md)
- 工具执行前后的治理：[工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)
- 生产环境为什么要看完整轨迹：[Agent 评估、安全与生产排查](./04-agent-evaluation-safety-production.md)

如果还不熟，可以先记住一句话：runtime 不是让模型更聪明，而是让模型的每一步都被应用层接住、校验、记录和约束。

## 概念为什么出现

很多 demo 会把 Agent 写成：

```text
while model wants tool calls:
  execute tool
  append result
```

这个写法能解释 Agent 的形状，但不足以支撑生产系统。它缺少状态版本、policy checks、timeout/cost budgets、stop reasons、traceability 和 recoverability。

具体问题包括：

- 状态版本缺失：工具返回后不知道当前 state 是否已经被别的请求更新，可能覆盖新数据。
- 策略检查缺失：tool schema 合法，不代表当前用户、当前金额、当前场景允许执行。
- 预算缺失：模型调用、工具调用和重试都可能拖垮 latency budget 或 cost budget。
- 停止原因缺失：系统不知道是成功完成、缺信息、触发 loop limit、工具失败，还是转人工。
- 可追踪性缺失：线上回答错了，只看最终文本无法定位是哪一步选错工具或写错状态。
- 可恢复性缺失：工具超时、进程重启或异步任务未完成时，系统无法从中间步骤继续。

Agent runtime 出现，是为了把“循环”变成一个受控执行器，而不是把业务可靠性交给 prompt。

## 最小心智模型

最小 runtime 生命周期是：

```text
request -> load state -> assemble context -> model step -> validate action -> execute tool -> observe -> update state -> decide stop/continue -> log trace
```

可以把它拆成几层：

| runtime layer | responsibility | failure if missing |
|---------------|----------------|--------------------|
| state store | 保存会话、任务状态、工具观察、版本号和恢复点 | 重启后丢步骤，或多个请求互相覆盖状态 |
| context assembler | 做 context assembly，把目标、状态、相关历史、工具说明和策略摘要组装给模型 | 模型看不到关键约束，或被无关历史污染 |
| model caller | 管理模型、prompt/schema 版本、token 限制、超时和返回解析 | 无法复现一次决策，也无法治理模型成本 |
| tool dispatcher | 根据工具名路由执行器，区分读写工具、同步/异步和重试策略 | 工具调用散落在业务代码里，权限和幂等难统一 |
| policy engine | 在执行前后检查权限、风险、审批阈值和安全策略 | schema 通过后直接做危险动作 |
| loop controller | 决定继续、停止、追问、重试、降级或转人工 | 无限循环、过早停止或重复写操作 |
| trace writer | 记录 step、tool call、observation、state diff、budget 和 stop reason | 线上问题只能猜，不能回放和评估 |

这里的重点不是使用某个框架，而是把每一轮决策的输入、输出、限制和结果都变成明确的工程对象。

## 客服退款/工单 Agent 案例

用户请求：

```text
我的订单 A123 退款到哪了？一直没收到。
```

一次受控 runtime 执行可以是：

```text
request_id=R1
step_id=1
load state: identity=user_42, account_verified=true, open_ticket=false
assemble context: 用户目标、订单号 A123、可用工具、退款查询策略、不能泄露内部字段
model step: call get_refund_status(order_id=A123)
validate action: A123 属于 user_42，get_refund_status 是只读工具
execute tool: get_refund_status
observation: status=failed, reason=bank_reject, updated_at=2026-05-01
update state: refund_status=failed, failure_reason=bank_reject
decide continue: 可自动创建工单，进入下一步

step_id=2
model step: call create_refund_ticket(order_id=A123, reason=bank_reject)
validate action: 写工具，需要幂等键 ticket:R1:A123:bank_reject，金额未超过人工审批阈值
execute tool: create_refund_ticket
observation: ticket_id=T88, eta=1 business day
update state: open_ticket=true, ticket_id=T88
decide stop: stop_reason=task_completed
final answer: 告知退款失败原因、工单号和预计处理时间
```

如果 `create_refund_ticket` 超时，loop controller 不应该无限重试。它可以在 retry budget 用完后写入失败 observation，设置 `stop_reason=tool_unavailable_escalated`，并把已有查询结果和失败原因转给人工队列。

## 工程控制点

Agent runtime 至少要把这些控制做成显式字段或模块：

- Agent step id 和 tool call id：每一次模型决策、每一次工具调用都要有稳定 ID，方便幂等、追踪和回放。
- loop limit：限制最大步数，防止重复调用同一工具或一直追问。
- retry budget：按失败类型设置重试上限，超时和 502 可以重试，权限失败不能重试绕过。
- latency budget：给整次请求和单个工具设置超时，超过后停止、降级或转异步。
- cost budget：限制 token、模型档位、工具费用和重试次数，避免单个任务成本失控。
- sync vs async tool calls：快读工具适合同步返回，慢工单、审批、外部系统写入更适合异步任务和后续通知。
- 并发读工具与串行写工具：parallel read-only tool calls 可以降低等待时间，但写工具要 serialized，避免重复创建、顺序错乱和事务冲突。
- tool result normalization：把不同工具的状态码、错误类型、时间戳和数据版本统一成 observation 格式。
- state diff after each step：每轮只记录状态变化，便于审计“哪一步改变了什么”。
- redaction before trace logging：trace 落库前先脱敏订单号、邮箱、手机号、原始用户文本、密钥和内部 ID。

这些控制点最好不散落在 prompt 里，而是由 runtime 在每一步执行前后强制检查。

## 和应用/面试的连接

如果让你设计一个 Agent runtime，你会有哪些模块？

可以按模块回答：state store、context assembler、model caller、tool dispatcher、policy engine、loop controller、trace writer。再补充预算治理、幂等、异步任务、人工升级和评估回放。这样能说明你设计的是应用执行系统，而不是只会调用模型 API。

为什么 Agent runtime 不能只是 while loop + tool call？

因为 while loop 只描述“模型还想调用工具时继续”，没有回答状态版本、权限策略、预算、停止原因、trace、幂等和恢复。生产 Agent 的风险主要在这些应用侧问题上，而不是循环语句本身。

Agent 什么时候应该停止？

常见停止条件包括：任务完成、用户信息不足需要追问、权限或安全策略不允许继续、达到 loop limit、retry budget 用完、latency budget 或 cost budget 用完、工具不可用、需要人工审批或人工接管。停止时必须写清 stop reason，而不是只返回一段自然语言。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| runtime 等于框架 | 框架可以帮你组织代码，但 runtime 的核心是状态、策略、工具、循环和 trace 的控制责任 |
| tool schema 通过就可以执行 | schema 只说明参数形状，还要检查用户权限、业务策略、风险和幂等 |
| trace 只需要最终答案 | Agent 排查需要 step、tool call、observation、state diff、budget 和 stop reason |
| 并发 tool call 总是更快 | 并发读可能更快，但写工具并发会带来重复副作用和一致性问题 |
| stop condition 只是省钱 | 停止条件还防无限循环、越权尝试、错误恢复失控和用户等待过久 |

## 自测

1. Agent runtime 的完整生命周期包括哪些步骤？
2. loop controller 需要根据哪些信号决定继续、停止、重试或转人工？
3. context assembly 为什么不能只是把全部历史消息塞给模型？
4. 哪些 tool call 可以并发，哪些必须串行执行？为什么？
5. 一个可排查的 trace schema 至少应该记录哪些字段？

## 回到主线

到这里，你已经知道 Agent runtime 是应用侧控制系统：它把状态、上下文、模型、工具、策略、预算和 trace 串成可上线的执行器。下一步要看：当任务跨请求、跨系统或跨人工审批时，如何用 workflow 和 durable state 管理长流程。

下一篇：[Agent Workflow 与 Durable State](./07-agent-workflow-and-durable-state.md)
