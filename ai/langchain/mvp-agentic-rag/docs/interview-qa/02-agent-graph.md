# 面试 Q&A — Agent 图与 LangGraph

> 本篇聚焦 supervisor 图设计、CRAG 子图、state schema 桥接、checkpointer 选型、HITL 机制。不重写概念,指向仓库已有文档。

---

## Q1: supervisor vs swarm 怎么选?本项目为什么用 supervisor?

**答案要点**

- **supervisor 模式**:有一个中央协调节点,所有 worker 节点执行完后回到 supervisor;supervisor 决定下一步走 kb_rag、web、HITL 还是 FINISH。控制流集中,可解释性强,调试和测试容易——每次路由决策都能在 trace 里看到 `RouteDecision`。
- **swarm 模式**:每个 agent 自己决定把控制权 `handoff` 给谁;无中央路由,适合任务分布式、没有单一协调点的场景。
- **本项目选 supervisor 的理由**:知识库 RAG 是结构化两步(先判断 query 属于哪类,再交给专家执行),路由逻辑简单、有限;中央路由方便加 `step_budget` 守卫防死循环,也方便 HITL 统一注入。
- 代码:`agent/supervisor.py`(LLMRouter) + `agent/graph.py`(顶层 StateGraph)。

**深挖追问**

- "如果要加第三个专家节点(例如 SQL 查数据库),怎么扩展?" — 在 `supervisor.py` 的 RouteDecision 枚举加一个值,在 `graph.py` 加节点 + 条件边,supervisor 无需改逻辑。
- "supervisor 的 LLMRouter 用了 with_structured_output,为什么用结构化输出而不是 parsing?" — 避免手写正则/提示工程,`RouteDecision` 是 Pydantic model,LangChain 直接调 function calling 返回强类型。

**常见误区**

- 误认为 supervisor 就是"只有一个 agent"。supervisor 本身不做业务,只做路由;业务全在 worker 子图里。
- 误认为 swarm 更高级。swarm 适合 agent 数量多、任务不可预测的场景;明确有限路由时 supervisor 反而更好维护。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/05-agent-patterns-and-architectures.md` → supervisor/swarm/反应式架构对比
- `ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md` → 多 agent 协调模式

---

## Q2: CRAG 子图是怎么防死循环的?grade/grounding 双轴是什么意思?

**答案要点**

- **双轴**指两个独立的质量检查门:
  - **grade(相关性轴)**:检索到 chunks 后,grader 判断这些 chunks 是否和 query 相关。不相关 → 进 rewrite。
  - **grounding(接地性轴)**:generate 生成答案后,grounder 判断答案是否有 chunks 支撑,即是否"接地"。不接地 → 说明 generate 幻觉了,再走 rewrite。
- **rewrite 预算防死循环**:`max_rewrites=1`(默认)。`state["rewrites"] < max_rewrites` 才允许 rewrite,超出直接走 `hedge`(返回"依据不足"兜底答案)。
- 代码:`agent/subgraphs/kb_rag.py` — `after_grade` 和 `after_grounding` 两个条件边函数,均检查 `state["rewrites"] < max_rewrites`。
- `KBRagState.rewrites` 从 0 开始,每次 rewrite 节点 +1。

**深挖追问**

- "max_rewrites=1 会不会太保守?" — 生产中默认 1 是合理的:每次 rewrite 多一次 LLM 调用,延迟和 cost 都上升;若知识库质量差,增大 max_rewrites 也救不了。可通过 golden set eval 数据驱动地调整。
- "grounding check 是怎么判断答案接地的?" — 本 MVP 中 grounder 是个可注入的组件;生产实现可用 NLI 模型或 LLM-as-judge,判断答案中的每个主张是否能在 chunks 中找到依据。

**常见误区**

- 误认为 CRAG 是"先验证 chunks、不行就上网搜"。原版 CRAG 论文确实有 web fallback;本项目把 web 搜索独立成 `web_agent` 节点,由 supervisor 决定要不要走,不是 CRAG 内部的 fallback。
- 误认为只有一个检查轴。grade 是检索前向检查(有没有找到相关内容),grounding 是生成后向检查(生成内容是否有依据),两者方向相反、互补。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md` → CRAG 实现细节、条件边

---

## Q3: 子图(KBRagState)和顶层图(AgentState)schema 不同,怎么桥接?

**答案要点**

- `AgentState`:messages(add_messages)、next、citations、step_budget — 面向对话历史和全局路由。
- `KBRagState`:query、chunks、rewrites、relevant、answer、citations、grounded — 面向单次 RAG 执行。
- **桥接方式**:在顶层图的 `kb_rag_node` 函数里手动做 schema 转换:
  - 入:从 `AgentState.messages` 提取 last human message → 作为 `KBRagState.query` 调用子图。
  - 出:从子图返回的 `KBRagState` 取出 `answer` 和 `citations` → 包装成 `AIMessage` 写回 `AgentState`。
- 代码:`agent/graph.py` 的 `kb_rag_node` 函数:
  ```python
  query = _last_human_text(state["messages"])
  result = kb_rag_runnable.invoke({"query": query, "rewrites": 0})
  return {"messages": [AIMessage(content=result["answer"])], "citations": result.get("citations", [])}
  ```
- 好处:子图是纯函数,可独立测试,不关心顶层 messages 格式。

**深挖追问**

- "为什么不让子图直接操作 messages?" — 子图的 CRAG 逻辑只关心 query 字符串和 chunks;混入 messages 会让子图复杂且难以复用。单一职责原则。
- "如果子图要回写多轮 citations 怎么做?" — 可在 `AgentState` 加 `Annotated[list, operator.add]` reducer,让每次子图调用追加而不是覆盖。

**常见误区**

- 误认为子图必须和父图共享同一个 State class。LangGraph 允许子图有独立 StateGraph 类型,只要包装节点做好入/出转换即可。
- 误认为 `.invoke()` 调子图会自动继承 parent state。不会,需要显式传入子图期望的初始 dict。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md` → 子图与 state schema 设计

---

## Q4: checkpointer 怎么选?为什么用 PostgresSaver 而非 InMemorySaver 或 SqliteSaver?

**答案要点**

- `InMemorySaver`:进程重启数据丢失,不适合生产;适合单元测试(本项目 tests 全用它)。
- `SqliteSaver`:单文件,进程重启不丢,适合开发/单机;但不支持并发写(SQLite 写锁),无法水平扩展。
- `PostgresSaver`(langgraph-checkpoint-postgres):
  - 持久化到 Postgres,与 pgvector 同一个库——本项目"单库"策略。
  - 支持并发,可多实例横向扩展。
  - thread_id 对应一条对话历史,API 层 `/threads/{id}` 直接从 checkpoint 读状态。
  - HITL 的 `interrupt()` 状态也持久化在这里,进程崩溃后 resume 依然有效。
- 代码:`agent/factory.py` 用注入式 `checkpointer` 参数,测试时传 `InMemorySaver()`,生产时传 `PostgresSaver(conn)`。

**深挖追问**

- "多实例部署时 PostgresSaver 够用吗?" — 水平扩展可以,但注意同一 thread_id 的并发写要业务层保证串行(通常用户单线程发请求)。checkpoint 的锁粒度是 thread_id 级别。
- "Redis 做 checkpoint 可以吗?" — LangGraph 生态没有官方 RedisSaver,需自己实现 `BaseCheckpointSaver`。生产可考虑,但维护成本高。

**常见误区**

- 误认为 InMemorySaver 在生产只是"有点慢"。InMemorySaver 进程级内存,单实例就会泄漏,多实例完全无法共享 thread 状态。
- 误认为换 checkpointer 需要改业务逻辑。不需要,checkpointer 是注入参数,编译期注入,业务节点无感。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md` → durable state 与 checkpointer

---

## Q5: HITL interrupt/resume 机制是怎么工作的?

**答案要点**

- `interrupt()` 是 LangGraph 的暂停原语:在 `human_review` 节点调用 `interrupt({"payload": ...})` 后,当前 super-step 暂停,状态持久化到 checkpointer,API 层立即返回 `status: "pending_review"` 给客户端。
- 此后 graph 不再推进,直到客户端 POST `/threads/{id}/resume` 带上 `Command(resume=approved/rejected)` 触发 `graph.invoke(Command(resume=...), config)` 恢复执行。
- 代码:`agent/human_review.py` 的 `human_review_node`;API 层 `/threads/{id}/resume` 端点。
- 实际场景:supervisor 判定 query 涉及敏感操作(如删文档)→ `next="human_review"` → 暂停等人工确认 → resume 后再继续。

**深挖追问**

- "interrupt 的 payload 是什么格式?" — 任意可序列化的 dict,本项目传 `{"question": ...}` 给前端展示。
- "如果用户一直不 resume 怎么办?" — checkpoint 里的 pending 状态会一直存在;可加 TTL 策略在业务层清理(本 MVP 未实现)。
- "interrupt 能中断在任意节点吗?" — 是,任何节点内调用 `interrupt()` 即可;本项目封装在专用 `human_review` 节点里,清晰分离。

**常见误区**

- 误认为 interrupt 是异常/报错。`interrupt()` 是正常控制流暂停,不抛异常,状态完整持久化。
- 误认为 resume 需要重跑整个 graph。resume 从中断点继续,不重跑已完成的节点(checkpointer 保障)。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md` → HITL、interrupt/resume 实现
- `ai/ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md` → durable execution 与断点续跑
