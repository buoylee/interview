# Agent 专题扩展设计

## 背景

当前 `ai/ml-to-llm-roadmap/02-agent-tool-use/` 已经系统化了 Agent 的基础层：

- `01-agent-boundary-and-loop.md`：Agent、Function Calling、workflow、普通 LLM 调用的边界。
- `02-tool-use-and-recovery.md`：工具 schema、权限、参数校验、失败恢复、幂等和人工升级。
- `03-state-memory-and-planning.md`：working state、conversation history、memory、planning 和 multi-agent 的基础概念。
- `04-agent-evaluation-safety-production.md`：trajectory eval、安全控制、日志和生产排查。
- `05-agent-patterns-and-architectures.md`：ReAct 以外的 plan-and-execute、router/supervisor、graph-constrained、reflection、multi-agent、memory-augmented、durable agent 等模式选型。

这些内容已经能覆盖 AI Engineer 面试里的 Agent 基础问题，但对真实 Agent 平台或复杂项目落地还不够。后续专题需要从“能讲清概念”扩展到“能设计、实现、评估和上线 Agent 系统”。

## 目标

Agent 专题采用“工程系统主线 + 每章面试收口”的双用途结构：

- 面试用途：每章都能回答高频问题、深入追问、项目表达和常见误区。
- 工程用途：章节顺序能指导真实 Agent 系统设计，包括 runtime、workflow、memory、security、eval、multi-agent、coding agent 和平台案例。
- 项目叙事：用一个持续案例串联各章，帮助把抽象概念落到可讲的系统架构。

## 非目标

- 不把专题做成某个框架的 API 教程。
- 不展开模型训练、RLHF、DPO 等模型对齐细节。
- 不把所有框架横向对比塞进主线；框架只用于解释架构取舍。
- 不一次性重写已有 01-05 文档，除非为了接入新章节需要轻量调整 README 或交叉链接。

## 总体结构

专题保留现有 01-05 作为基础层，新增工程层和高级层。

```text
基础层：
01 agent boundary and loop
02 tool use and recovery
03 state, memory and planning
04 evaluation, safety and production overview
05 agent patterns and architectures

工程层：
06 agent runtime engineering
07 agent workflow and durable state
08 agent memory deep dive
10 agent security deep dive
11 agent eval practice

高级层：
09 multi-agent coordination
12 coding agent architecture
13 agent platform case study
```

文件顺序保留编号递增；README 中按“基础层 / 工程层 / 高级层”解释学习路径，避免读者被 09、10、11 的顺序困惑。

## 持续案例

主持续案例采用“客服退款/工单 Agent”。

选择理由：

- 覆盖身份校验、订单查询、退款状态查询、创建工单、人工升级等典型工具调用。
- 同时包含只读工具和写操作，能讲清权限、幂等、审批和审计。
- 天然需要状态持久化、暂停/恢复、等待人工、失败恢复和生产日志。
- 容易构造 eval 样本：正常完成、缺信息、权限失败、工具超时、重复写入、prompt injection、需要人工升级。
- 面试中容易转化成项目叙事，不依赖特定框架。

Coding Agent 不作为全专题持续案例，而是在 `12-coding-agent-architecture.md` 独立展开。

## 新增章节设计

### 06-agent-runtime-engineering.md

定位：解释 Agent runtime 到底怎么跑。

核心内容：

- Agent step 生命周期：input、state load、context assembly、model call、tool call、observation、state update、stop。
- Tool call lifecycle：生成、校验、权限检查、执行、结果校验、错误分类、回写。
- Loop controller：max steps、retry budget、latency budget、cost budget、stop reason。
- Context assembly：system prompt、developer instruction、user message、state snapshot、trajectory summary、retrieved memory、tool definitions。
- Trace / trajectory schema：step id、tool call id、arguments summary、observation summary、policy result、state diff。
- 同步、异步和并发 tool call 的边界。
- Runtime 和 framework 的边界：runtime 是控制循环，framework 是一种实现选择。

面试收口：

- 如果让你设计一个 Agent runtime，你会有哪些模块？
- 为什么 Agent runtime 不能只是 while loop + tool call？
- Agent 什么时候应该停止？

### 07-agent-workflow-and-durable-state.md

定位：解释 Agent 和 workflow / durable execution 怎么结合。

核心内容：

- 固定 workflow vs dynamic agent vs graph-constrained agent。
- 状态图：节点、边、前置条件、失败边、人工升级边。
- Durable state：task id、state version、resume point、stop reason。
- Pause / resume：等待用户、等待人工、等待 webhook、等待定时任务。
- 幂等与重放安全：idempotency key、write barrier、replay-safe tool。
- Saga / compensation：写操作失败后的补偿、撤销和人工复核。
- Temporal、LangGraph 这类思想作为架构参照，不做 API 教程。

面试收口：

- 为什么高风险业务不能让 Agent 自由循环？
- Durable agent 的核心为什么不是长上下文？
- Workflow 和 Agent 如何组合？

### 08-agent-memory-deep-dive.md

定位：系统化 Agent 记忆设计。

核心内容：

- Working memory：当前任务变量、约束、完成项、失败原因、停止条件。
- Episodic memory：历史任务过程和结果。
- Semantic memory：长期事实、用户偏好、案例知识。
- User profile memory：跨会话偏好、身份属性和权限边界。
- Memory write policy：什么时候写、写什么、谁批准、如何去重。
- Memory retrieval policy：什么时候检索、召回多少、如何过滤、如何引用来源。
- Memory expiration / deletion：过期、撤回、隐私删除、用户控制。
- Memory permission：不同用户、租户、角色的可见范围。
- Memory vs RAG vs long context。

面试收口：

- Agent memory 怎么设计？
- 怎么防止旧记忆污染当前任务？
- 为什么 memory 不能替代实时权限校验？

### 09-multi-agent-coordination.md

定位：把 multi-agent 从“多个角色聊天”落到协作协议。

核心内容：

- Handoff：什么时候交接、交接 payload、责任归属。
- Manager-worker：任务拆分、worker 权限、汇总和裁决。
- Blackboard：共享状态、状态所有权、写入冲突。
- Debate / competition：独立方案、judge、明确评判标准。
- Communication protocol：消息类型、结构化输出、状态引用、错误报告。
- Conflict resolution：多个 Agent 结论冲突时如何裁决。
- Multi-agent eval：单 Agent 成功不等于整体成功。
- 什么时候不要 multi-agent：职责不独立、评估标准不清、共享状态无法治理。

面试收口：

- Multi-agent 什么时候有必要？
- 怎么避免 multi-agent 变成混乱聊天？
- Supervisor 和 multi-agent 的区别是什么？

### 10-agent-security-deep-dive.md

定位：深入 Agent 特有安全风险。

核心内容：

- Tool output prompt injection：搜索结果、网页、工单备注、用户文本中的恶意指令。
- Data exfiltration：通过工具把敏感数据带出系统。
- Confused deputy：模型被诱导用自己的权限替用户完成越权动作。
- Tool permission escalation：万能工具、粗粒度工具、动态工具注册带来的风险。
- Unsafe side effects：删除、退款、外发邮件、执行 SQL、部署代码。
- Sandbox：代码执行、浏览器、文件系统、网络访问隔离。
- Approval gates：用户确认、人工审批、策略审批。
- Secret handling：密钥不进 prompt、不进通用日志、不暴露给工具输出。
- Audit trail：谁请求、谁批准、调用了什么工具、产生了什么副作用。
- Red-team cases：构造攻击样本并进入回归集。

面试收口：

- Agent 比普通 RAG 多哪些安全风险？
- 怎么防 tool output prompt injection？
- 写工具为什么需要审批、幂等和审计？

### 11-agent-eval-practice.md

定位：把 Agent eval 从概念变成可执行评估方案。

核心内容：

- Task success eval：目标是否完成。
- Trajectory eval：步骤是否必要、顺序是否合理、是否正确停止。
- Tool-call eval：工具名、参数、依赖、schema version 是否正确。
- Permission eval：是否越权读写、是否触发正确审批。
- Simulated user：缺信息、反复改需求、恶意输入、等待用户回复。
- Golden traces：标准轨迹和可接受变体。
- Adversarial traces：权限失败、工具注入、超时、重复写入。
- Regression set：线上失败回灌、版本升级回归。
- LLM-as-judge rubric：何时可用、如何约束、如何抽样人工复核。
- Online metrics：loop count、tool failure rate、escalation rate、cost、latency、user correction。

面试收口：

- Agent eval 为什么不能只看最终答案？
- 如何设计一个 Agent 的离线评估集？
- 线上怎么发现 Agent 失控？

### 12-coding-agent-architecture.md

定位：独立解释 coding agent 的架构，不把它混入客服案例。

核心内容：

- Repo context indexing：文件发现、符号、依赖、最近变更。
- File selection：如何决定读哪些文件。
- Planning：任务拆分、变更范围、风险判断。
- Patch generation：生成补丁而不是大段覆盖。
- Apply patch：冲突处理、保持用户改动、最小编辑。
- Test loop：选择测试、运行测试、定位失败、修复。
- Code review loop：发现 bug、提出风险、修正。
- Context compaction：保留任务状态、文件路径、决策和未完成事项。
- Subagent delegation：并行探索、分工实现、结果整合。
- Sandbox / permission：文件系统、网络、命令执行、破坏性操作审批。

面试收口：

- Cursor / Codex / Claude Code 这类 coding agent 大概怎么工作？
- Coding agent 为什么要读代码而不是直接改？
- 如何防止 coding agent 覆盖用户改动？

### 13-agent-platform-case-study.md

定位：把前面章节整合成一个完整平台案例。

核心内容：

- 场景：企业客服退款/工单 Agent 平台。
- Intent routing：退款查询、订单查询、账号问题、知识库回答、人工转接。
- Tool registry：只读工具、写工具、审批工具、人工工具。
- Permission model：用户身份、订单归属、租户边界、agent role。
- Workflow graph：身份校验、读取状态、创建工单、人工升级、最终回复。
- Memory：用户偏好、历史工单摘要、当前任务 state。
- Eval：golden traces、adversarial traces、线上指标。
- Observability：trace、state diff、tool call、policy result、cost。
- Human handoff：交接摘要、失败原因、已执行动作、待处理项。
- Cost control：模型路由、上下文裁剪、工具缓存、step limit。

面试收口：

- 讲一个你设计过的 Agent 平台，架构怎么讲？
- 这个平台如何处理安全、成本、失败恢复和人工升级？

## README 调整

`02-agent-tool-use/README.md` 后续应增加三层学习路径：

```text
基础层：
01 -> 02 -> 03 -> 04 -> 05

工程层：
06 -> 07 -> 08 -> 10 -> 11

高级层：
09 -> 12 -> 13
```

同时保留“面试冲刺路径”：

```text
01 -> 02 -> 03 -> 05 -> 04 -> cheatsheet
```

新增“系统落地路径”：

```text
01 -> 02 -> 03 -> 05 -> 06 -> 07 -> 08 -> 10 -> 11 -> 13
```

## 与现有文档的关系

- `03-state-memory-and-planning.md` 保留基础解释，`08-agent-memory-deep-dive.md` 展开长期记忆和策略。
- `04-agent-evaluation-safety-production.md` 保留生产总览，`10-agent-security-deep-dive.md` 和 `11-agent-eval-practice.md` 分别深入安全和评估。
- `05-agent-patterns-and-architectures.md` 保留模式选型总览，`07-agent-workflow-and-durable-state.md` 和 `09-multi-agent-coordination.md` 展开具体模式。
- `12-coding-agent-architecture.md` 可以引用 `ai/coding-agent/` 和各 SDK 深度剖析材料，但主线仍以架构能力为目标。
- `13-agent-platform-case-study.md` 负责把所有章节连接成项目叙事。

## 实施策略

分两阶段实施，避免一次性膨胀。

第一阶段补核心工程能力：

1. `06-agent-runtime-engineering.md`
2. `07-agent-workflow-and-durable-state.md`
3. `08-agent-memory-deep-dive.md`
4. `10-agent-security-deep-dive.md`
5. `11-agent-eval-practice.md`
6. 更新 README、interview path、cheatsheet 的链接和学习路径

第二阶段补高级专题和项目叙事：

1. `09-multi-agent-coordination.md`
2. `12-coding-agent-architecture.md`
3. `13-agent-platform-case-study.md`
4. 将案例在相关章节里串联起来
5. 补充 review notes 中的高级追问

## 验收标准

- Agent 专题能同时支持面试复习和真实系统设计。
- 每个新增章节都包含：问题定位、最小心智模型、工程控制点、持续案例、面试收口、常见误区、自测。
- README 能清楚区分基础层、工程层、高级层、面试冲刺路径和系统落地路径。
- Cheatsheet 至少补充 runtime、workflow/durable state、memory、安全、eval 的高频追问。
- 新内容不重复覆盖现有 01-05，而是明确分层和交叉链接。
- 持续案例保持一致，默认使用客服退款/工单 Agent。
