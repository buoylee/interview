# Agent、Workflow 与持久化状态

## 这篇解决什么问题

前一篇讲 runtime：每一轮 Agent 决策如何被加载状态、校验工具、写 trace 和控制停止。但有一类任务不能只靠一次请求里的 loop 解决：退款、审批、工单、风控、运维处置、采购流程。

这些任务有三个共同点：风险高、步骤长、会等待。身份检查、退款写入、主管审批、外部系统回调、人工交接和失败恢复，都不能交给自由 Agent loop 临场发挥。

这一篇解决的问题是：怎样把固定 workflow、graph-constrained Agent 行为和 durable execution 组合起来，让 Agent 在高风险或长周期任务里既能动态判断局部情况，又不会越过业务边界、丢失恢复点或重复执行副作用。

## 学前检查

读这篇前，建议先理解：

- Agent 为什么需要应用侧 loop 控制：[Agent 边界与执行循环](./01-agent-boundary-and-loop.md)
- 常见 Agent 架构模式，尤其是 graph-constrained agent 和 durable agent：[Agent 模式与架构选型](./05-agent-patterns-and-architectures.md)
- runtime 如何管理状态、工具、预算和 trace：[Agent Runtime 工程](./06-agent-runtime-engineering.md)

如果还不熟，可以先记住一句话：workflow 管业务路径，Agent 管局部判断，持久化状态管跨时间恢复。

## 概念为什么出现

自由 Agent loop 适合短任务和低风险探索，但不适合身份检查、退款、审批、长等待、崩溃后重试和人工升级。

原因很直接：

- 身份检查不能跳步。用户说“我是本人”不等于可以读取订单或退款。
- 退款和审批是写操作。模型不能自由决定金额、次数、权限和审批阈值。
- 长等待会跨请求。外部支付系统、人工主管或用户补材料可能几个小时后才返回。
- 崩溃后重试可能重复副作用。重新跑一次 `create_ticket` 或 `issue_refund` 可能生成重复工单或重复退款。
- 人工 handoff 不是发一条消息。它要带上状态、证据、失败原因、责任边界和可恢复入口。

所以生产系统通常不会让 Agent 自由循环到结束，而是把外层做成 workflow 或状态图：哪些节点能走、每个节点前置条件是什么、失败后去哪、什么时候等待、什么时候恢复、什么时候升级。

## 最小心智模型

最小组合方式是：

```text
workflow node -> precondition check -> local LLM/tool decision -> persist state -> transition edge -> wait/resume/finish
```

四种形态可以这样区分：

| 形态 | 核心控制 | 适合场景 | 主要风险 |
|------|----------|----------|----------|
| Fixed workflow | 路径、节点和转移都由代码固定 | 强合规、步骤稳定、动态性低的审批或表单流程 | 异常分支多时流程变僵，用户表达理解弱 |
| Free Agent loop | 模型根据观察自由选择下一步工具 | 低风险探索、研究、短链路排查 | 越权、无限循环、重复写入、无法保证前置条件 |
| Graph-constrained Agent | 图限制可走节点，LLM 在节点内做局部判断 | 客服、金融、运维等既要控制又要适应自然语言的流程 | 图太松会退化成自由 Agent，图太硬会处理不了真实异常 |
| Durable workflow | 状态、事件、等待点和恢复点持久化 | 长周期工单、审批、外部回调、崩溃恢复 | 幂等、replay safety、版本兼容和补偿复杂 |

这里的 durable 不是“上下文更长”，而是任务状态可落库、可恢复、可审计、可重放，并且每个副作用都能判断是否已经发生过。

## 客服退款/工单 Agent 案例

用户请求：

```text
我订单 A123 的退款一直没到，帮我处理一下。
```

不要让 Agent 在所有工具里自由循环。更稳的做法是把外层做成图：

```text
Start
  -> VerifyIdentity
  -> CheckOrderOwnership
  -> ReadRefundStatus
  -> DecideNext
       -> CreateTicket
       -> HumanEscalation
       -> FinalResponse
```

每个节点有明确责任：

- `VerifyIdentity`：确认登录态、二次验证或必要身份信息，不通过则进入追问或人工升级。
- `CheckOrderOwnership`：校验订单属于当前用户，不允许模型只凭用户文本读取任意订单。
- `ReadRefundStatus`：只读查询退款状态、更新时间、失败原因和外部支付状态。
- `DecideNext`：LLM 可以根据只读观察判断是直接回复、创建工单还是升级人工，但只能选择图允许的边。
- `CreateTicket`：写工具节点，必须带 idempotency key，并在 write barrier 之后执行。
- `HumanEscalation`：把已验证身份、订单归属、退款状态、失败证据、已执行工具和 resume point 交给人工队列。
- `FinalResponse`：只使用状态里的可披露字段回复用户，不能泄露内部风控、银行原始错误或其他用户信息。

一次 durable execution 的状态可以像这样：

```text
task_id=refund:A123:user_42
state_version=3
resume point=ReadRefundStatus.completed
identity_verified=true
order_owned=true
refund_status=bank_rejected
ticket_id=null
last_edge=ReadRefundStatus -> DecideNext
next_allowed_edges=CreateTicket, HumanEscalation, FinalResponse
```

如果进程在 `ReadRefundStatus` 后崩溃，恢复时不能从头自由重跑。系统应读取 `task_id` 和 `resume point`，确认只读观察是否 replay-safe，再从 `DecideNext` 或下一个安全节点继续。

## 工程控制点

高风险 durable Agent 的控制点要显式建模：

- State schema 和 state version：状态字段、节点输出、工具观察和可披露内容要有版本，避免模型、prompt 或 tool schema 升级后读错旧状态。
- Task id 和 resume point：每个长任务有稳定 `task_id`，每次持久化写清当前节点、已完成动作、下一条允许边和恢复入口。
- Node preconditions：节点执行前检查身份、订单归属、权限、金额阈值、状态版本和是否已取消。
- Failure edges 和 escalation edges：不要只靠异常抛出；图里要有工具失败、权限失败、用户信息不足、超时、人工升级等边。
- Idempotency key for write tools：`create_ticket`、`issue_refund`、`send_notification` 等写工具必须有 idempotency key，恢复或重试时先查是否已执行。
- Write barrier before side effects：写副作用前先持久化“即将执行的动作、参数、幂等键和状态版本”，再调用外部系统，避免崩溃后不知道是否该重试。
- Replay-safe read and write tools：读工具要可重复读取并标注数据版本；写工具要通过幂等键、去重表或外部请求 ID 支持 replay。
- Timeout, cancel, and compensation：长等待必须有超时边；用户撤销或人工接管时要能 cancel；部分写成功后要有 compensation 路径。
- Saga-style compensation for partial writes：跨系统没有单个数据库事务时，用 Saga 记录每个已完成步骤和对应补偿动作，例如撤销工单、取消退款请求、发送更正通知。

可以把写操作前后的顺序固定成：

```text
validate preconditions -> persist pending_action -> execute write tool with idempotency key -> persist observation -> choose success/failure/compensation edge
```

这比把“失败了就重跑”写进 prompt 可靠得多。重跑是否安全，取决于工具是否 replay-safe、幂等键是否稳定、write barrier 是否已经落库，以及补偿动作是否定义清楚。

## 和应用/面试的连接

为什么高风险业务不能让 Agent 自由循环？

因为高风险业务的核心不是“能不能想到下一步”，而是“能不能保证不能做错事”。身份校验、订单归属、退款写入、审批阈值、人工升级和审计证据都有明确边界。自由 loop 可能跳过前置条件、重复写工具、在错误状态下继续执行，或者在失败后给出看似合理但不可追责的答案。

Durable agent 的核心为什么不是长上下文？

长上下文只是让模型看到更多历史，不保证状态一致、恢复安全或副作用幂等。Durable agent 的核心是持久化 state schema、state version、task id、resume point、事件、等待点、工具观察和 stop reason。系统恢复时依赖这些结构化状态，而不是依赖模型“记得之前发生了什么”。

Workflow 和 Agent 如何组合？

外层用 workflow 或图约束业务路径：哪些节点能执行、哪些边能转移、哪些前置条件必须满足。节点内部再让 Agent 做局部动态判断：理解用户表达、选择只读工具参数、总结证据、判断是否需要人工升级。这样 workflow 提供安全边界，Agent 提供自然语言和异常处理能力。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| workflow 比 Agent 低级 | workflow 负责确定性业务控制，Agent 负责局部动态决策；两者是组合关系，不是高低关系 |
| durable agent 等于长上下文 | durable 的核心是持久化状态、resume point、事件恢复、幂等和审计，不是把更多消息塞给模型 |
| 失败后重跑一定安全 | 只有 replay-safe 工具、稳定 idempotency key、write barrier 和补偿策略都具备时，重跑才可能安全 |
| 人工升级只是发消息 | 人工升级要交接身份状态、证据、失败原因、已执行动作、权限边界和恢复入口 |
| 图约束会消灭所有动态能力 | 图约束限制危险路径，节点内部仍可用 LLM 做理解、参数选择、分支判断和回复生成 |

## 自测

1. graph constraints 应该约束哪些东西？哪些判断可以留给节点内的 LLM？
2. durable state 至少要保存哪些字段，才能支持崩溃后的恢复？
3. 什么叫 replay safety？为什么只读工具和写工具的要求不同？
4. idempotency key 应该绑定哪些业务字段？为什么不能每次重试都生成新 key？
5. Saga-style compensation 适合解决什么问题？它和数据库事务有什么不同？

## 回到主线

到这里，你应该能把 Agent 从“自由循环调工具”升级成“workflow 约束路径、Agent 局部决策、durable state 支持等待和恢复”的工程系统。下一步复习 Agent memory 时，要继续区分：哪些信息是当前任务状态，哪些才是长期记忆。

下一篇：[Agent Memory 深入](./08-agent-memory-deep-dive.md)
