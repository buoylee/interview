# Agent 模式与架构选型

## 这篇解决什么问题

前几篇把 Agent 的核心循环、工具、状态和评估讲清楚了，但面试里还会追问：除了最常见的 ReAct / observe-act loop，还有哪些 Agent 模式？它们解决什么问题？什么时候应该用，什么时候只是过度设计？

这一篇解决的问题是：把常见 Agent 模式放到一个选型框架里，而不是只会说“用 ReAct 调工具”。

## 先澄清：ReAct 不是 Agent 的全部

ReAct 可以看成最典型的单 Agent 工具循环：

```text
observe state -> decide action -> call tool -> observe result -> continue or stop
```

它适合路径会随工具结果变化的短到中等长度任务。但真实系统里，Agent 经常还要面对更长任务、更强约束、多个角色、人工审批、异步执行和可恢复状态。此时会出现其他架构模式。

不要把这些模式理解成互斥分类。生产系统常常组合使用：例如一个 graph-constrained agent 里，某个节点用 ReAct 调工具，另一个节点用 evaluator-optimizer 做质量检查，外层再由 supervisor 控制路由和升级。

## 常见模式总览

| 模式 | 核心做法 | 适合场景 | 主要风险 |
|------|----------|----------|----------|
| ReAct / observe-act | 单个控制器根据观察结果逐步行动 | 客服查询、排查、轻量数据分析 | 循环失控、工具误用、状态漂移 |
| Plan-and-execute | 先规划，再逐步执行和修正 | 长任务、研究报告、复杂操作流程 | 计划幻觉、计划过期、执行反馈没回写 |
| Router / supervisor | 先判断任务类型，再分派给工具、工作流或子 Agent | 多意图助手、企业 AI 平台、客服分流 | 路由错误、职责边界不清、fallback 缺失 |
| Graph-constrained agent | 用状态图限制可走节点，LLM 只在局部做选择 | 高风险业务流程、审批、生产工单 | 图过硬导致不灵活，图过松又退化成自由 Agent |
| Reflection / critic | 生成后由评审器检查，再修正或停止 | 代码、写作、数据分析、合规检查 | 自我确认偏差、成本升高、评审标准空泛 |
| Evaluator-optimizer | 用明确 rubric 或测试结果驱动迭代优化 | 有可测指标的生成任务、代码修复、SQL 生成 | 指标覆盖不足，优化到局部指标 |
| Multi-agent | 多个角色按协议协作或竞争 | 研究-实现-评审、复杂系统设计、并行调查 | 通信成本高、状态不一致、责任难追踪 |
| Memory-augmented agent | 把用户偏好、历史任务和案例作为可检索记忆 | 长期助手、客户支持、个人化工作流 | 记忆过期、权限混乱、检索结果注入 |
| Durable / long-running agent | 状态持久化，可暂停、恢复、等待事件或人工 | 工单、运维处置、采购审批、长周期任务 | 幂等、重放、超时和人工交接复杂 |

## 模式 1：ReAct / Observe-Act

ReAct 的价值是让模型不要一次性猜完整流程，而是在每一步根据工具观察修正下一步。它的工程重点不是“让模型思考”，而是让应用层掌控工具、状态、停止条件和日志。

适合：

- 路径不完全固定，但每一步都可以通过工具观察推进。
- 工具数量有限，单轮任务步数可控。
- 失败时可以追问、重试、fallback 或转人工。

不适合：

- 流程强合规，必须按固定审批节点走。
- 需要长时间等待外部事件。
- 工具很多且职责重叠，模型很容易选错。

面试表达：ReAct 是动态工具循环的基础形态，但生产里要把它包在权限、状态机、loop limit 和审计日志里。

## 模式 2：Plan-and-Execute

Plan-and-execute 把“做什么顺序”与“每一步怎么执行”拆开：

```text
goal -> planner produces plan -> executor runs step -> observe result -> update plan/state -> continue
```

它解决的是长任务里的局部最优问题。直接 ReAct 可能每轮只看眼前动作，容易忘记总体目标；先规划可以让系统有阶段、依赖和完成条件。

关键控制点：

- 计划要是高层步骤，不要让 planner 编造工具结果。
- 每步执行后要把观察结果回写到 state，并允许修正计划。
- 计划和执行可以用同一个模型，也可以用不同模型或策略。
- 达到失败条件时应停止或升级，而不是继续执行旧计划。

适合研究报告、代码迁移、数据分析、复杂客服处理。不适合非常短的一次查询，也不适合高度固定、已经能用普通 workflow 表达的业务。

## 模式 3：Router / Supervisor

Router 或 supervisor 模式先判断任务属于哪类，再交给对应能力：

```text
input -> route intent -> select specialist/tool/workflow -> monitor result -> fallback/escalate
```

它不是让多个 Agent 自由聊天，而是让一个上层控制器管理职责边界。企业平台里很常见：用户一句话可能是查知识库、查订单、改账号、生成 SQL、创建工单或转人工，不能把所有工具都暴露给一个自由 Agent。

设计要点：

- 路由输出要结构化：intent、confidence、selected handler、fallback reason。
- 低置信度时走追问或人工，不要硬路由。
- 每个 specialist 只拿自己的工具和权限。
- supervisor 负责 stop reason、错误归因和最终用户回复。

面试里可以把它和 multi-agent 区分开：supervisor 强调调度和权限边界，multi-agent 强调多个角色之间的协作协议。

## 模式 4：Graph-Constrained Agent

Graph-constrained agent 用状态图约束 Agent 可走路径：

```text
collect info -> validate identity -> choose read/write branch -> execute -> verify -> respond/escalate
```

LLM 不是任意决定下一步，而是在某个节点里做局部判断，例如选择工具参数、判断是否需要补充信息，或在允许的边里选择下一状态。

适合：

- 金融、客服、审批、运维等需要强控制的流程。
- 节点间有明确前置条件、权限和审计要求。
- 既需要固定框架，又需要局部自然语言理解和工具选择。

风险是两边都可能失败：图太死，无法处理真实业务分支；图太松，系统又变成不可控自由循环。工程上要把状态 schema、节点输入输出、失败边、人工升级边定义清楚。

## 模式 5：Reflection / Critic

Reflection / critic 模式让一个生成器产出结果，再由评审器检查问题：

```text
actor output -> critic checks evidence/rubric/policy -> revise or stop
```

它适合质量敏感但能定义评审标准的任务，例如代码改动、文档总结、SQL 查询、合规文案、答案是否引用证据。

关键点：

- critic 不应该只说“好/不好”，要输出结构化发现：issue、severity、evidence、fix suggestion。
- critic 最好能访问外部证据或测试结果，否则容易只是另一个模型的主观意见。
- 修正循环要有限次，并记录每次修改理由。

这类模式常被滥用。没有明确 rubric、测试或证据时，多一轮 critic 只是在增加成本，不一定提高质量。

## 模式 6：Evaluator-Optimizer

Evaluator-optimizer 和 reflection 类似，但更强调可测反馈。系统先生成候选，再用 evaluator 打分或运行测试，optimizer 根据反馈改进：

```text
generate candidate -> evaluate with tests/rubric -> optimize -> re-evaluate -> stop
```

典型例子：

- 代码 Agent：运行测试、lint、类型检查，再修复。
- SQL Agent：执行 dry run、检查 schema 和结果行数。
- 信息抽取：用 schema 校验、字段覆盖率和人工样本评估。
- 文案生成：按品牌规范、事实一致性和风险项打分。

它适合有可验证目标的任务。不适合目标模糊、评估标准只靠“看起来更好”的任务。面试里要强调：evaluator 要尽量外部化、可复现，而不是只靠同一个模型自评。

## 模式 7：Multi-Agent

Multi-agent 不是“Agent 越多越强”，而是当职责、工具、权限或评估标准确实不同，才把任务拆给多个角色。

常见协作方式：

| 协作方式 | 做法 | 适合 |
|----------|------|------|
| Sequential | A 的输出交给 B，再交给 C | research -> draft -> review |
| Hierarchical | manager 分解任务，worker 执行，manager 汇总 | 复杂项目、多工具平台 |
| Blackboard | 多个 Agent 读写共享结构化状态 | 信息收集、事件处置 |
| Debate / competition | 多个 Agent 独立给方案，再由 judge 选择 | 有明确评判标准的设计或推理任务 |

必须补上的工程控制：

- 共享状态的 schema 和所有权。
- 每个 Agent 的工具权限和停止条件。
- 冲突解决：两个 Agent 结论不一致时谁裁决。
- 成本和延迟预算。
- 可追踪日志：哪个 Agent 做了什么、依据是什么。

如果只是一个任务拆成很多角色互相聊天，但没有状态、权限、裁决和评估，通常是演示效果强，生产排查弱。

## 模式 8：Memory-Augmented Agent

Memory-augmented agent 把长期偏好、历史任务、客户资料或案例库作为可检索材料。它和 RAG 类似，但目标不是只回答问题，而是影响下一步行动。

设计重点：

- 区分 working state、conversation history、long-term memory 和 retrieved memory。
- 记忆要有来源、时间戳、权限、过期策略和删除机制。
- 注入前要做相关性和安全过滤，不能把历史工具输出当系统指令。
- 高风险动作不能只凭记忆执行，仍要实时校验权限和事实。

例子：客服 Agent 记得用户偏好中文沟通，但不能因为历史里有某个订单号，就跳过当前身份验证。

## 模式 9：Durable / Long-Running Agent

Long-running agent 处理的是“这件事不会在一次模型调用里完成”的问题。它可能要等审批、等外部 webhook、等用户补充材料，或者在失败后恢复。

它更像一个持久化状态机：

```text
start task -> persist state -> wait event/human/tool -> resume -> verify -> continue/close
```

关键工程问题：

- task_id、state version、resume point 和 stop reason。
- 工具写操作的幂等键，防止恢复后重复执行。
- 超时、取消、人工接管和通知。
- 模型、prompt、tool schema 版本变化后的兼容性。

面试里可以说：long-running agent 的难点不在提示词，而在持久化、幂等、事件驱动、审计和人工交接。

## 如何选型

| 问题 | 倾向选择 |
|------|----------|
| 路径动态但步数不长？ | ReAct / observe-act |
| 目标长、步骤多、需要阶段管理？ | Plan-and-execute |
| 输入意图多、工具域差异大？ | Router / supervisor |
| 流程高风险、必须满足前置条件？ | Graph-constrained agent |
| 产出质量需要检查和修正？ | Reflection / critic |
| 有测试、rubric 或外部指标？ | Evaluator-optimizer |
| 子任务职责、工具或权限明显不同？ | Multi-agent |
| 需要跨会话偏好或历史经验？ | Memory-augmented agent |
| 任务会等待事件或人工，并需要恢复？ | Durable / long-running agent |

## 和应用/面试的连接

面试里不要只背模式名。更好的回答顺序是：

1. 先判断任务是否真的需要 Agent，还是一次调用、结构化输出或固定 workflow 足够。
2. 如果需要 Agent，说明路径动态性、工具风险、状态生命周期和停止条件。
3. 再选模式：ReAct、plan-and-execute、router、graph、reflection、multi-agent、memory 或 durable。
4. 最后补生产控制：权限、schema、幂等、loop limit、日志、评估、fallback 和人工升级。

示例回答：

```text
如果是退款查询，我不会直接上 multi-agent。先用 graph-constrained agent 固定身份校验、订单读取、退款状态查询和回复节点；每个节点内部可以用 ReAct 选择只读工具。若退款失败需要创建工单，写操作走单独节点，有幂等键、权限校验和人工升级。这样既保留动态处理异常的能力，又不会让模型自由决定高风险动作。
```

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| ReAct 就等于 Agent | ReAct 是单 Agent 动态工具循环的一种常见模式 |
| Plan-and-execute 一定比 ReAct 高级 | 长任务有价值，短任务会增加计划幻觉和成本 |
| Multi-agent 越多越好 | 只有职责、工具、权限或评估标准不同才值得拆 |
| Reflection 一定提升质量 | 没有 rubric、证据或测试时，critic 可能只是增加主观噪声 |
| Graph agent 就不是 Agent | 图约束外层流程，节点内仍可有动态决策 |
| Memory 能替代实时校验 | 记忆可能过期或越权，高风险事实必须实时验证 |
| Long-running agent 主要靠更长上下文 | 核心是持久化状态、幂等、事件恢复和人工交接 |

## 自测

1. ReAct、plan-and-execute 和 graph-constrained agent 的边界分别是什么？
2. Router / supervisor 和 multi-agent 的区别是什么？
3. Reflection 和 evaluator-optimizer 有什么不同？
4. 为什么 durable agent 的核心不是长上下文？
5. 设计一个客服退款 Agent 时，你会选哪些模式组合？为什么？

## 回到主线

到这里，你应该能把 Agent 从“一个 ReAct loop”扩展成一组可选架构模式。下一步复习时，把这些模式放回工具权限、状态、评估和生产日志里一起讲，面试答案才会像工程系统，而不是框架名清单。
