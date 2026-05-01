# Agent 与工具调用 面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [Agent 与工具调用](../02-agent-tool-use/)。

## 30 秒答案

Agent 不是 Function Calling，而是“观察结果后继续决策”的受控执行循环：goal、state、decide next action、tool call、observation、update state、stop or continue。Function Calling 只生成工具名和参数形状，应用层负责权限、参数校验、执行、结果校验和恢复。生产 Agent 还要显式管理状态、记忆、计划、停止条件、loop limit、审计日志，并按完整轨迹评估 task success、tool validity、permission safety、cost/latency 和 human escalation，而不是只看最终回答。

## 2 分钟展开

Agent 适合目标明确但路径会随观察结果变化的多步任务，例如退款追踪、运维排查、数据分析助手和多系统客服协作。一次结构化输出能解决的分类任务不需要 Agent；固定审批或查询流程能稳定完成时，workflow 也可能比 Agent 更可控。Agent 的关键边界是下一步是否根据状态和工具观察动态决定。

工具层是风险入口。Tool schema 告诉模型工具名、参数和用途，但不能证明用户有权访问数据，也不能保证写操作安全。可上线链路要有 tool allowlist、least privilege、permission check、argument validation、timeout、result validation、retry/fallback/escalate；写工具还要考虑幂等、二次确认、审批阈值和审计日志。工具结果也可能包含用户文本、网页或第三方内容，不能当作系统指令信任。

状态让 Agent 知道目标、约束、已完成步骤、工具观察、失败原因和停止条件。Working state 服务当前任务，长期记忆服务跨会话偏好或历史材料；不能把所有历史都塞进上下文，因为成本高、噪声大，也会放大安全风险。评估时要看完整 trajectory：工具是否选对、参数是否合法、权限是否通过、失败是否分类、循环是否正确停止、是否该转人工，以及最终答案是否如实反映执行结果。

ReAct 只是最常见的单 Agent 工具循环，不是 Agent 的全部。长任务可以用 plan-and-execute；多意图平台可以用 router/supervisor；高风险流程适合 graph-constrained agent；质量敏感产出可加 reflection、critic 或 evaluator-optimizer；职责、工具和权限明显不同才考虑 multi-agent；跨会话偏好用 memory-augmented agent；需要等待事件、人工或恢复时用 durable / long-running agent。

## 高频追问

| 追问 | 回答 |
|------|------|
| Agent 和 Function Calling 的区别？ | Function Calling 是输出协议，模型生成工具名和参数；Agent 是控制架构，围绕状态、观察和停止条件循环决定下一步。 |
| Tool schema 为什么不能替代权限控制？ | Schema 只约束参数形状，不能证明订单属于当前用户、工具可被调用、写操作安全或动作符合策略。 |
| Agent 为什么需要状态？ | 多步任务要记录目标、用户约束、工具观察、失败原因、已完成步骤和停止条件，否则容易重复调用、忘记约束或用旧观察决策。 |
| 除了 ReAct，还有哪些 Agent 模式？ | Plan-and-execute 管长任务，router/supervisor 管分流和权限，graph-constrained 管高风险流程，reflection/evaluator 管质量迭代，multi-agent 管多角色协作，memory-augmented 管长期记忆，durable agent 管异步恢复。 |
| Router/supervisor 和 multi-agent 的区别？ | Router/supervisor 强调上层控制器把任务分派给专门 handler，并管理 fallback；multi-agent 强调多个角色按协议协作、竞争或共享状态。 |
| Graph-constrained agent 解决什么？ | 用状态图限制可走流程，LLM 只在节点内做局部判断，适合身份校验、审批、工单等高风险业务。 |
| Agent eval 为什么不能只看最终答案？ | 最终答案可能看起来对，但中间越权访问、选错工具、重复写入、循环失控或没有真正创建工单。 |
| 什么时候不该用 Agent？ | 一次 LLM 调用、结构化输出或固定 workflow 已经能稳定完成时，不该为了“智能”增加 Agent 循环和排查复杂度。 |
| 哪些工具失败适合重试？ | 502、超时、限流等 transient failure 可有上限重试；权限失败、高风险动作和信息不一致应停止、追问或转人工。 |
| Loop limit 防什么？ | 防无限循环、重复工具调用和成本失控；但可能导致复杂任务过早停止，所以要记录 stop_reason 并设计 fallback。 |
| Multi-agent 什么时候有必要？ | 只有子任务确实需要不同工具、权限或评估标准时才考虑；否则会增加同步、状态和评估复杂度。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Agent vs Function Calling | 以为有 tool call 就是 Agent | Function Calling 是调用形状，Agent 是观察后继续决策的循环 |
| Agent vs Workflow | 以为工具编排都叫 Agent | 固定流程是 workflow；根据观察动态决定下一步才接近 Agent |
| ReAct vs Agent patterns | 以为 ReAct 覆盖所有 Agent | ReAct 是基础动态循环，复杂系统还会组合 planning、routing、graph、reflection、multi-agent、memory 和 durable state |
| Tool schema vs 权限 | 以为 schema 校验通过就能执行 | 权限、业务规则和副作用安全必须由应用层判断 |
| Tool result vs 可信事实 | 以为工具输出一定可信 | 工具可能返回过期数据、错误状态或带 prompt injection 的文本 |
| State vs History | 以为状态就是聊天记录 | 状态是当前任务关键变量、约束、工具观察和停止条件 |
| Memory vs RAG | 以为记忆检索就是 Agent | 记忆可复用 RAG-like retrieval，但 Agent 核心是行动循环 |
| Final answer vs Task success | 以为自然语言回答好就成功 | 还要检查轨迹、工具执行、权限安全和实际副作用 |

## 项目连接

- 客服退款 Agent：状态记录 user_id、order_id、已查工具、退款状态、失败原因、是否创建工单和是否转人工。
- 工具设计：把只读查询和写操作拆开，给 Agent 最小工具集合，不暴露万能后台动作。
- 失败恢复：parse/schema failure 可修复或追问，transient tool failure 可限次重试，permission failure 和 unsafe action 应停止或升级。
- 生产日志：记录 request_id、goal、state snapshot、model/prompt/schema 版本、tool calls、脱敏参数、observations 摘要、policy result、retry count、latency、cost、stop_reason 和 final answer。
- 模式选型：退款查询可用 graph-constrained agent 固定身份校验和高风险写操作，节点内用 ReAct 调只读工具；复杂研究任务可用 plan-and-execute；多意图平台用 router/supervisor 控制 specialist 权限。
- 面试表达：先判断是否需要 Agent，再讲 loop、模式选型、工具权限、状态管理、轨迹评估、安全控制和生产排查。

## 反向链接

- [Agent 边界与执行循环](../02-agent-tool-use/01-agent-boundary-and-loop.md)
- [工具调用、权限与失败恢复](../02-agent-tool-use/02-tool-use-and-recovery.md)
- [状态、记忆与任务规划](../02-agent-tool-use/03-state-memory-and-planning.md)
- [Agent 评估、安全与生产排查](../02-agent-tool-use/04-agent-evaluation-safety-production.md)
- [Agent 模式与架构选型](../02-agent-tool-use/05-agent-patterns-and-architectures.md)
- [Function Calling 的输出形态](../03-generation-control/03-function-calling-output-shape.md)
