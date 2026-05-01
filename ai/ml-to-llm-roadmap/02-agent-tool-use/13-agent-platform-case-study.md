# Agent 平台案例：客服退款/工单系统

## 这篇解决什么问题

前面已经分别讲过 Agent runtime、workflow、memory、security 和 eval。真实面试或系统设计题里，通常不会只问其中一块，而会问：如果要做一个可上线的客服退款/工单 Agent 平台，整体架构怎么讲？

这篇解决的问题是：怎样把路由、工具注册、权限模型、workflow graph、记忆、评估、可观测性、人工升级和成本控制串成一条完整平台叙事。目标不是展示一个 prompt demo，而是能说明这个平台如何理解用户意图、选择受控流程、执行工具、恢复失败、转人工、评估质量，并持续运营。

## 学前检查

读这篇前，建议先理解：

- Agent runtime 如何控制状态、工具、预算和 trace：[Agent Runtime 工程](./06-agent-runtime-engineering.md)
- 长流程如何用 workflow 和 durable state 管恢复：[Agent、Workflow 与持久化状态](./07-agent-workflow-and-durable-state.md)
- Agent 安全如何处理权限、审批、prompt injection 和审计：[Agent 安全深水区](./10-agent-security-deep-dive.md)
- Agent eval 如何检查 trajectory、tool-call、permission 和 recovery：[Agent Eval 实战](./11-agent-eval-practice.md)

如果还不熟，可以先记住一句话：Agent 平台不是“聊天 UI + 工具”，而是把模型决策放进受控的业务执行系统。

## 概念为什么出现

单个 Agent demo 通常只展示“用户说一句话，模型调用几个工具，最后回复”。但客服退款/工单系统有更多生产要求：

- 用户意图不同：退款查询、催进度、改银行卡、投诉、取消订单和普通闲聊不能进入同一条路径。
- 工具风险不同：查退款状态是只读，创建工单是写操作，高价值退款需要审批或人工 handoff。
- 权限边界不同：用户只能查自己的订单，客服角色、租户、地区和订单状态都会影响可执行动作。
- 流程会跨时间：工单创建、支付渠道回调、审批和人工处理都需要 durable state 和 resume point。
- 记忆有治理要求：历史偏好、旧工单和重复失败模式有用，但不能替代实时权限和退款状态。
- 质量不能只看最终回复：平台要评估 trajectory、tool call、permission check、recovery 和人工升级是否正确。
- 线上要可运营：需要 observability、成本控制、模型路由、context trimming、tool caching 和 step limits。

所以平台设计要把 routing、tool registry、permission model、workflow graph、memory、eval、observability、human handoff 和 cost control 一起设计。少了任意一块，系统都会退回到不可控的 prompt demo：能演示，但难上线、难排查、难合规。

## 最小心智模型

客服退款/工单 Agent 平台可以按这条链路理解：

```text
user -> gateway/router -> agent runtime -> workflow graph -> tool registry/policy -> memory/eval/observability -> response or human handoff
```

每层只做自己的事：

| platform component | responsibility | key design decision |
|--------------------|----------------|---------------------|
| gateway/router | 接入用户请求，做身份上下文、租户、渠道和 intent routing | 哪些意图进入 Agent，哪些走固定 FAQ、表单、人工或拒绝路径 |
| agent runtime | 加载状态、组装上下文、调用模型、校验动作、控制 loop 和 stop reason | 每一步如何记录 step id、budget、state diff、tool call 和恢复点 |
| workflow graph | 固定高风险业务路径和允许转移边 | 哪些节点必须按顺序执行，哪些局部判断交给 LLM |
| tool registry | 注册只读/写工具、schema、owner、风险等级、幂等和缓存策略 | 工具暴露到什么粒度，是否区分 read/write、sync/async 和审批阈值 |
| permission model | 执行前检查用户、租户、角色、订单归属、金额和状态机 | 授权按当前用户主体判断，还是按后台服务账号误放大权限 |
| memory system | 管 profile、episodic、semantic 和 tool-observation memory | 什么能写、何时检索、是否过期、如何按 user/order/case 过滤 |
| eval system | 离线和线上检查 task success、trajectory、tool-call、permission、recovery | 哪些场景进入 regression，哪些断言用规则，哪些用 judge |
| observability | 记录 trace、metrics、audit、cost、latency、policy result 和 handoff outcome | 线上问题能否回放到具体 step、工具、状态和策略结果 |
| human handoff | 把不可自动处理或高风险任务交给人工，并保留 resume point | 交接包包含哪些事实、证据、已执行动作、权限边界和下一步 |
| cost control | 控制模型档位、上下文、工具调用、缓存、重试和 step limits | 哪些请求用小模型，哪些升级强模型，什么时候停止或转人工 |

这张表的核心是：平台组件不是堆功能，而是把“模型建议动作”和“系统允许执行”分开。模型负责理解和局部决策，平台负责边界、状态、证据和运营。

## 客服退款/工单 Agent 案例

用户请求：

```text
我的订单 A123 退款一直没到账，帮我看看。
```

一次可上线的平台流程可以这样设计：

```text
1. gateway/router
   - 识别 intent routing: refund_query
   - 绑定 user_id、tenant_id、channel、request_id
   - 如果缺登录态，先走身份补全或人工路径

2. agent runtime
   - 加载 durable state 和历史 open ticket
   - 做 context trimming，只放当前目标、必要状态、工具说明和安全策略
   - 设置 step limits、latency budget 和 cost budget

3. workflow graph
   - Start -> VerifyIdentity -> CheckOrderOwnership -> ReadRefundStatus -> DecideNext
   - DecideNext 只能转向 FinalResponse、CreateTicket、Approval 或 HumanHandoff

4. tool registry/policy
   - check_order_ownership(order_id=A123, user_id=user_42) 是只读工具
   - get_refund_status(order_id=A123) 是只读工具，但只能在 CheckOrderOwnership 通过后由 policy wrapper 调用，可短期 tool caching
   - create_ticket(order_id=A123, reason, idempotency_key) 是写工具
   - request_approval(order_id=A123, amount, evidence) 是高风险流程节点

5. memory/eval/observability
   - memory 检索同用户、同订单、同工单范围内的历史摘要，例如曾经因 bank_reject 失败
   - eval 记录 expected trajectory 是否满足身份、归属、退款状态读取和正确升级
   - observability 写入 trace、policy result、tool latency、token cost 和 stop reason

6. response or human handoff
   - 如果退款状态可解释且无需人工，直接回复用户
   - 如果状态异常、金额高、审批缺失或工具失败，创建交接包进入 human handoff
```

主链路展开后是：

```text
refund query -> verify identity -> order ownership -> refund status read -> decide
  -> final response
  -> ticket creation
  -> approval/human handoff
```

几个关键分支：

- refund query：router 把请求识别为退款查询，而不是普通闲聊或投诉工单。低置信度时不要直接进写流程，可以追问订单号或转人工。
- order ownership：必须调用业务系统确认 A123 属于当前用户。历史记忆里出现过 A123，也不能替代实时归属校验。
- refund status read：读取当前退款状态、更新时间、失败原因和支付渠道状态。只读结果可以短时间缓存，但要带数据版本和过期时间。
- ticket creation：如果退款失败且符合自动建单条件，调用 `create_ticket`，必须带稳定 idempotency key，避免超时重试生成重复工单。
- approval/human handoff：高价值退款、策略不确定、工具超时、用户身份异常或状态机冲突时，进入审批或人工队列。
- final response：只使用可披露字段回复，例如当前状态、已创建工单号、预计处理时间或人工接管说明；不泄露内部风控、原始银行错误或其他用户信息。

人工交接包不应该只是一段聊天摘要，而应包含：

```text
request_id=R1
user_id=user_42
order_id=A123
identity_verified=true
order_owned=true
refund_status=failed
failure_reason=bank_reject
ticket_id=T88 or null
policy_result=approval_required or tool_timeout or state_conflict
completed_steps=VerifyIdentity, CheckOrderOwnership, ReadRefundStatus
resume_point=DecideNext
sanitized_trace_link=trace:R1
```

这样人工接手后能知道系统为什么停、哪些事实已确认、哪些动作已执行、下一步从哪里恢复，而不是重新问用户一遍。

## 工程控制点

- intent routing：把退款查询、退款写入、投诉、订单取消、FAQ 和闲聊分开。低置信度路由应追问或转人工，不要进入高风险 workflow。
- tool registry：每个工具要有 owner、schema version、read/write 类型、风险等级、幂等要求、超时、重试、缓存和审计字段。工具越多越要靠 registry 控制暴露面。
- permission model：执行前用当前用户、租户、角色、订单归属、金额阈值和状态机做硬检查。prompt 不能替代权限系统，Agent 服务账号也不能替用户越权。
- workflow graph：把身份校验、订单归属、退款状态读取、工单创建、审批、人工升级和最终回复建成显式节点和边。LLM 只能在节点内做局部判断或选择允许边。
- memory：profile、历史工单和重复失败模式只能作为线索；身份、订单归属、退款状态和审批权限必须实时检查。记忆写入要有来源、时间、过期和删除更正流程。
- eval：离线样本覆盖正常查询、缺订单号、非本人订单、退款失败建单、工具超时、恶意工具输出、高价值审批和人工升级。上线后把事故和人工改判加入 regression。
- observability：trace 至少记录 request_id、step_id、intent、model、tool call、sanitized observation、policy result、permission result、state diff、latency、cost、stop reason 和 handoff outcome。
- human handoff：升级条件要显式，包括权限失败、风险高、工具不可用、状态冲突、用户投诉升级、低置信度和预算耗尽。交接包要带证据、已执行动作和 resume point。
- cost control：控制 token、模型档位、工具调用次数、重试次数、并发读工具和写工具数量。成本控制是系统设计问题，不只是把模型换便宜。
- model routing：低风险分类、摘要和 FAQ 可用小模型；复杂退款判断、异常解释和高风险分支可升级强模型；安全策略和权限检查仍由确定性系统执行。
- context trimming：上下文只放当前目标、必要 durable state、相关记忆摘要、工具说明和策略摘要。原始长聊天、过期工具观察和敏感字段不应全部塞给模型。
- tool caching：只读工具可按 user/order/status version 做短 TTL 缓存；写工具不能靠缓存掩盖失败，必须用 idempotency key 和状态查询确认结果。
- step limits：限制最大模型步数、连续同类工具调用、重试次数和总耗时。达到上限时写清 stop reason，并转人工或给用户明确下一步。

这些控制点的共同目标是让每一步都可解释：为什么进这个流程，为什么能调用这个工具，为什么停在这里，为什么转人工，以及成本为什么可控。

## 和应用/面试的连接

讲一个你设计过的 Agent 平台，架构怎么讲？

可以从主链路讲：`user -> gateway/router -> agent runtime -> workflow graph -> tool registry/policy -> memory/eval/observability -> response or human handoff`。再把客服退款例子落到具体节点：intent routing 识别退款查询，runtime 加载状态和预算，workflow graph 固定身份校验、订单归属、退款状态读取、工单创建和审批，tool registry 管只读/写工具，permission model 执行前拦截越权，memory 提供历史线索，observability 和 eval 证明流程可排查、可回归，human handoff 处理高风险或失败恢复。

这个平台如何处理安全、成本、失败恢复和人工升级？

安全靠 least privilege tool registry、read/write 分离、permission model、approval gate、tool output sanitize 和 audit trail；成本靠 model routing、context trimming、tool caching、step limits、retry budget 和 cost budget；失败恢复靠 durable state、resume point、idempotency key、write barrier、tool timeout 分类和 recovery edges；人工升级靠明确 handoff policy、交接包、证据链和可恢复入口。

怎么把 Agent 项目讲成系统设计而不是 prompt demo？

不要从“我写了一个 prompt”开始，而要从平台对象讲：请求路由、状态模型、workflow graph、工具注册、权限策略、记忆治理、eval plan、observability、人工流程和成本预算。再用一个端到端案例说明每个组件在真实业务里承担什么责任，并强调模型输出只是候选动作，最终执行由应用侧 policy、permission 和 workflow 控制。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| Agent 平台就是聊天 UI 加工具 | 聊天 UI 只是入口，平台核心是 routing、runtime、workflow、tool registry、permission、memory、eval、observability、handoff 和 cost control |
| 工具越多平台越强 | 工具越多暴露面越大；强平台靠工具分层、权限、schema、审计、幂等和风险控制，而不是工具数量 |
| 只要接了人工就安全 | 人工 handoff 也需要触发条件、交接包、权限边界、证据和 resume point；否则只是把混乱转给人工 |
| eval 可以上线后再补 | 没有 eval 就无法证明 trajectory、permission、recovery 和 escalation 正确，上线后只会把事故变成第一批测试样本 |
| 成本控制只是换便宜模型 | 成本还来自上下文长度、工具调用、重试、缓存、模型路由、step limits、人工升级率和失败恢复策略 |

## 自测

1. intent routing 在客服退款平台里应该区分哪些请求？低置信度时为什么不能直接进入写流程？
2. tool registry 至少要记录哪些字段，才能支撑权限、缓存、幂等、审计和成本控制？
3. permission model 为什么必须检查当前用户、租户、订单归属和金额阈值，而不能只依赖 prompt？
4. workflow graph 在退款查询、工单创建、approval 和 human handoff 之间应该约束哪些边？
5. observability 和 human handoff 分别要记录哪些证据，才能定位失败并让人工从正确 resume point 接手？

## 回到主线

到这里，Agent topic 在这个阶段已经形成闭环：runtime 负责执行控制，workflow 和 durable state 负责长流程恢复，memory 负责受治理的历史线索，security 负责边界和审批，eval 负责证明行为正确，platform case study 负责把它们组织成可讲、可落地、可运营的系统设计。

回到主线可以看：[Agent 与工具调用 README](./README.md)。

Agent topic 在当前阶段已经完成：高级专题已经覆盖 multi-agent 协作、coding agent 和客服平台案例。后续如果继续扩展，可以把同一套平台视角迁移到企业级权限治理和跨团队 Agent marketplace。
