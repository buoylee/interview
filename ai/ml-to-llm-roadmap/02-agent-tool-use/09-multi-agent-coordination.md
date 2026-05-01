# Multi-Agent 协作机制

## 这篇解决什么问题

前面已经讲过单 Agent 的工具循环、状态、workflow、durable execution 和 eval。Multi-agent 继续往前一步：当一个 Agent 的职责、工具、权限、上下文和评估标准都变得太宽时，系统可能需要多个 Agent 或 specialist 协作。

这一篇解决的问题是：怎样把 multi-agent 设计成显式协调协议，而不是几段自由角色聊天。真正的 multi-agent 架构要定义谁分派、谁执行、谁写状态、谁裁决冲突、谁停止，以及如何评估整个协作过程。

## 学前检查

读这篇前，建议先理解：

- Agent 如何使用状态、记忆和计划：[State、Memory 与 Planning](./03-state-memory-and-planning.md)
- 常见 Agent 模式，尤其是 router / supervisor 和 multi-agent：[Agent 模式与架构选型](./05-agent-patterns-and-architectures.md)
- Agent eval 为什么要看 trajectory、tool-call、permission 和 recovery：[Agent Eval 实战](./11-agent-eval-practice.md)

如果还不熟，可以先记住一句话：multi-agent 的重点不是“多个角色说话”，而是“多个受控执行者按协议共享任务、状态和责任”。

## 概念为什么出现

一个 Agent 变得太宽，通常不是因为 prompt 不够长，而是因为它同时承担了太多边界不同的事情：

- 工具不同：查退款状态、解释政策、创建工单、审批退款和通知用户可能调用完全不同的系统。
- 权限不同：只读查询、内部备注读取、写工单、发起退款和人工接管不应该暴露给同一个自由 Agent。
- 上下文不同：政策解释需要规则和案例，工单处理需要历史记录，退款状态需要支付系统和订单状态。
- 评估标准不同：状态查询看事实一致性，政策解释看合规性，工单创建看 schema、幂等和恢复能力。
- 子任务可独立验证：每个子任务都有明确输入、输出、证据和通过条件，可以单独运行 eval 或人工复核。

这些差异足够明显时，拆成多个 specialist 才有工程价值。否则，把一个短任务拆成多个角色，只会增加 token 成本、延迟、状态同步和排查难度。

## 最小心智模型

Multi-agent 的最小模型不是“大家讨论一下”，而是：

```text
supervisor -> assign task -> worker acts with scoped tools -> report structured result -> merge/check conflicts -> decide next handoff or stop
```

这个模型里有三个关键约束：

- supervisor 负责路由、权限边界、结果合并、conflict resolution 和 stop reason。
- worker 只拿本任务需要的 scoped tools、上下文和输出 schema，不直接改全局状态。
- 协作结果通过结构化消息传递，例如 `task_id`、`role`、`input`、`evidence`、`confidence`、`proposed_state_update`、`risk` 和 `next_action`。

常见协调方式可以这样比较：

| 协作方式 | 核心做法 | 适合场景 | 主要风险 |
|----------|----------|----------|----------|
| handoff | 一个 Agent 完成局部工作后，把结构化上下文交给下一个 Agent 或人工 | 分阶段处理、权限边界清晰、需要转人工 | handoff payload 缺字段，导致下游重复查、误判或丢失责任 |
| manager-worker | manager / supervisor 拆任务、分派 worker、汇总结果 | 多工具平台、复杂工单、可并行调查 | manager 路由错、worker 输出不可比、汇总时忽略冲突 |
| blackboard | 多个 Agent 读写共享的结构化工作区 | 信息收集、事件处置、研究归纳 | shared state 所有权不清，写入互相覆盖，旧结论被当成事实 |
| debate/competition | 多个 Agent 独立给方案，再由 judge 选择或综合 | 有明确 rubric 的设计、推理、诊断候选 | 没有 judge 或证据要求时退化成主观争论 |
| sequential pipeline | A 的输出固定交给 B，再交给 C | research -> draft -> review、抽取 -> 校验 -> 入库 | 上游错误级联，下游无法追问或回退 |

面试里要强调：这些方式不是互斥的。生产系统可以用 supervisor 做外层路由，用 handoff 交接人工，用 blackboard 收集证据，再用 judge 对 competition 结果做裁决。

## 客服退款/工单 Agent 案例

运行案例仍然是客服退款/工单 Agent。用户可能说：

```text
我订单 A123 的退款一直没到账，帮我看看。
```

最简单、最高频的退款状态查询不应该直接变成 multi-agent。更稳的做法通常是单个 graph-constrained Agent：身份校验、订单归属校验、读取退款状态、生成回复。如果只是查状态或解释预计到账时间，拆成多个 Agent 只会让流程变慢。

只有当任务出现明显职责边界时，supervisor 才有必要路由给 specialist：

- refund-status specialist：只读查询订单、退款、支付通道状态，输出事实、时间戳、证据和不确定性。
- policy specialist：读取退款政策、到账时效、特殊品类规则和可披露话术，输出可解释的政策结论。
- ticket specialist：在满足前置条件后创建或更新工单，带上 idempotency key、失败原因、证据和 resume point。
- human handoff：当权限不足、高价值退款、用户投诉升级、工具冲突或政策例外时，把结构化状态交给人工。

一个受控流程可以是：

```text
supervisor classifies request
  -> refund-status specialist reads refund evidence
  -> policy specialist explains allowed next step if needed
  -> ticket specialist creates ticket only after preconditions pass
  -> supervisor checks conflict and decides final answer or human handoff
```

这里 supervisor 不只是“主持聊天”。它要检查 refund-status specialist 的状态证据和 policy specialist 的规则结论是否一致。例如退款状态显示银行拒绝，但政策结论说仍在正常到账周期，supervisor 不能随便挑一个回答用户，而要触发 conflict resolution：重新查询、要求更多证据、转人工或给出不确定性说明。

## 工程控制点

- handoff payload：交接必须包含 `task_id`、用户/租户、已验证身份、资源 ID、已执行工具、关键 observation、证据、风险、失败原因、resume point 和下游允许动作。
- role/tool permissions：每个 worker 只拿自己的工具和权限；refund-status specialist 不该创建工单，policy specialist 不该读内部支付详情，ticket specialist 不该绕过审批。
- shared state ownership：shared state 要区分事实、假设、建议和最终决策；每个字段要有 owner、来源、时间戳和可覆盖规则。
- blackboard write rules：blackboard 不能随便写。写入要符合 schema，标注 evidence 和 confidence；高风险字段只能由授权 role 写入，旧字段更新要保留版本或历史。
- conflict resolution：当 Agent 结论冲突时，必须定义裁决顺序，例如优先实时工具事实、再看政策规则、再看人工判断；不能让模型用“听起来合理”合并矛盾结论。
- judge/supervisor responsibility：judge 或 supervisor 要负责选择、合并、拒绝、升级和停止，并输出裁决理由；debate/competition 没有明确 judge 就没有生产价值。
- communication schema：Agent 间通信要结构化，至少包括 `status`、`result`、`evidence`、`confidence`、`state_delta`、`risk`、`needs_handoff` 和 `stop_reason`。
- cost/latency budget：multi-agent 会增加模型调用、工具调用和等待时间。低风险高频任务要设置最大 worker 数、最大 round 数、p95 延迟和 token 成本预算。
- multi-agent eval：评估不只看最终答案，还要看路由是否正确、handoff 是否完整、worker 工具权限是否受控、shared state 是否一致、conflict 是否正确处理、judge 是否引用证据。
- when not to split：如果任务短、工具少、权限一致、上下文一致、单一路径可评估，就不要拆。很多客服退款查询用一个 graph-constrained Agent 加只读工具就够了。

## 和应用/面试的连接

Multi-agent 什么时候有必要？

当一个任务自然拆成多个可独立验证的子任务，并且这些子任务在工具、权限、上下文、风险或评估标准上明显不同，multi-agent 才有必要。典型例子是复杂工单、研究-实现-评审、平台型助手中的多域路由。短查询、固定 workflow 或单一工具链通常不需要。

怎么避免 multi-agent 变成混乱聊天？

把它设计成协议：明确 supervisor、worker、handoff payload、通信 schema、shared state owner、blackboard 写规则、conflict resolution、权限边界、停止条件和 eval。Agent 之间不要传自由散文作为唯一状态，必须传结构化结果和 evidence。

Supervisor 和 multi-agent 的区别是什么？

Supervisor 是一种控制角色或架构模式，重点是路由、权限、监控、合并、升级和停止。Multi-agent 是多个 Agent 或 specialist 按协议协作的系统形态。一个系统可以只有 supervisor 路由到工具或 workflow，而不一定是 multi-agent；也可以用 supervisor 管理多个 worker，形成 manager-worker 式 multi-agent。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| agent 越多越强 | Agent 越多，通信、状态一致性、成本和责任追踪越难；只有边界真的不同才拆 |
| 多角色对话等于 multi-agent 架构 | 多角色 prompt 只是表现形式；架构要有权限、状态、协议、裁决和 eval |
| shared state 可以随便写 | shared state 必须有 schema、owner、来源、版本和写入规则 |
| supervisor 可以不做权限控制 | supervisor 的核心职责之一就是隔离工具、上下文和可执行动作 |
| debate 没有明确 judge 也有价值 | 没有 judge、rubric 和 evidence requirement 的 debate 只是增加主观噪声 |

## 自测

1. handoff payload 至少应该包含哪些字段？为什么只传一段自然语言总结不够？
2. manager-worker 模式里，manager / supervisor 要承担哪些责任，worker 又应该被限制在哪些边界内？
3. blackboard 模式中，shared state 的 owner、写入规则和版本记录分别解决什么问题？
4. 两个 specialist 对退款原因给出冲突结论时，系统应该如何做 conflict resolution？
5. 设计 multi-agent eval 时，除了最终答案，还要评估哪些协作过程指标？

## 回到主线

到这里，你应该能把 multi-agent 从“多角色聊天”理解成“受权限、状态、协议和评估约束的协作系统”。下一步可以看安全边界如何进一步落地：[Agent 安全深水区](./10-agent-security-deep-dive.md)。

后续的 [Coding Agent 架构](./12-coding-agent-architecture.md) 会把这些 coordination ideas 应用到 coding agents：例如 planner、patch writer、test runner、reviewer 和 subagent 如何在同一个 repo 状态上协作而不覆盖用户改动。
