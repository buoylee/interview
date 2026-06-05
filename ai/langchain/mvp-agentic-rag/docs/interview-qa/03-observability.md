# 面试 Q&A — 可观测性

> 本篇聚焦 LangSmith vs Langfuse 取舍、trace vs metrics 分工、request_id 的排查用法。不重写概念,指向仓库已有文档。

---

## Q1: LangSmith 和 Langfuse 怎么选?本项目为什么默认 Langfuse 自托管?

**答案要点**

本项目 `OBS_BACKEND=langfuse` 是默认值,原因如下(每个维度都有具体取舍):

| 维度 | Langfuse(默认) | LangSmith |
|---|---|---|
| **数据驻留** | 自托管:trace 数据留在自己的 Postgres,不出内网 | 默认上云(api.smith.langchain.com),数据进 Anthropic/LangChain 的 SaaS — 企业合规风险 |
| **成本** | 开源免费(MIT),基础设施成本自付 | SaaS 有免费额度,超额付费;自托管版仅 Enterprise 方案提供 |
| **开源/可审计** | MIT License,代码可审计、可 fork、可定制 | 自托管仅企业版;SaaS 黑盒 |
| **运维** | 需要自己跑 Langfuse Docker Compose / K8s | SaaS 零运维,但企业自托管 = Enterprise 合同 |
| **LangChain 集成** | `langfuse.langchain.CallbackHandler` — 与 LangSmith 完全对等的集成体验 | 原生 LangSmith 集成,略微更深(Annotated runs、feedback API) |
| **多模型支持** | 任意 LLM provider,只要走 LangChain callback | 同上 |

- **一句话理由**:企业知识库场景,query 内容可能含内部文档敏感信息,不能送上 SaaS 云;Langfuse 自托管给数据驻留 + 零额外成本。
- 代码:`obs/backends.py` — `OBS_BACKEND` 环境变量决定注入哪个 callback handler;切换不改业务代码。

**深挖追问**

- "什么时候应该用 LangSmith?" — 个人项目/快速原型、团队没有运维 Langfuse 的能力、Anthropic/LangChain 的 feedback loop 功能有需求时。
- "Langfuse 自托管要跑什么服务?" — Docker Compose:Langfuse web + worker + Postgres + Redis。4 个容器,生产可上 K8s Helm chart。
- "两者能同时用吗?" — 本项目设计是单一 backend(OBS_BACKEND);要双写需自己在 `get_observability_callbacks` 里追加第二个 handler。

**常见误区**

- 误认为"LangSmith = 官方 = 更好"。选型核心是数据驻留和成本,不是官方背书。
- 误认为 Langfuse 只能记 trace,不能做 eval。Langfuse 自带评分 API 和 human annotation 工作流,可以对 trace 打分做 online eval。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md` → observability backend 选型
- `ai/langchain/11-production.md` → LangChain callback 体系与 tracing

---

## Q2: trace 和 metrics 有什么区别?各自用来做什么?

**答案要点**

- **Trace(分布式追踪)**:记录一次请求完整的执行轨迹——supervisor 走了哪条路、retrieve 耗时多少、LLM 输入输出是什么、哪步报错。单条可查,适合排查**具体一次坏答案**的根因。
  - 本项目:每次请求生成 `request_id`,作为 trace 的 root span tag,串联从 API 层到每个 LangGraph 节点的所有子 span。
  - 工具:Langfuse / LangSmith dashboard 可按 request_id 搜索定位。

- **Metrics(聚合指标)**:统计维度的数值——每分钟 LLM 调用次数、token 消耗总量、P95 延迟、工具报错率。适合看**系统整体健康状况**、做容量规划、触发告警。
  - 本项目:`obs/metrics.py` 用 Prometheus client:
    - `rag_llm_tokens_total` — token 消耗 counter
    - `rag_llm_calls_total` — LLM 调用次数
    - `rag_tool_errors_total` — 工具报错次数
    - `rag_llm_latency_seconds` — LLM 延迟 histogram
  - 通过 `MonitoringCallback` 在每次 LLM 调用时写入,API 层 `/metrics` 暴露给 Prometheus 抓取。

- **一句话区分**:trace 看单条(why this request is bad),metrics 看聚合(is the system healthy)。

**深挖追问**

- "如果没有 trace,只有 metrics,能排查坏答案吗?" — 不能。metrics 告诉你"P95 延迟升高了",但无法告诉你"第 42 个请求为什么答错了"——需要 trace 的单条上下文。
- "如果只有 trace,没有 metrics,能做告警吗?" — 不实用。trace 是流式数据,聚合计算成本高;metrics 是预聚合指标,告警规则直接在 Prometheus 上写,亚秒级反应。

**常见误区**

- 误认为 Langfuse dashboard 上的 trace 就是 metrics。Langfuse 也有 aggregate 统计页,但那是事后分析;实时告警要走 Prometheus + Alertmanager。
- 误认为打了 trace 就不需要结构化日志。trace 记 LangGraph 节点级别的输入输出;日志记系统级事件(启动失败、DB 连接中断)。两者互补。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md` → trace vs metrics vs logs 三者分工
- `ai/langchain/11-production.md` → Prometheus callback 集成

---

## Q3: request_id 怎么把一个坏答案定位到具体步骤?

**答案要点**

完整排查路径如下:

1. **拿到 request_id**:API 响应头 `X-Request-ID: abc123`;或从用户反馈中提取(前端应存储并上报)。
2. **打开 Langfuse**:在 dashboard 搜索 `request_id=abc123`,找到对应 trace。
3. **逐步检查 span**:
   - `supervisor` span:RouteDecision 是什么?路由对不对?
   - `retrieve` span:hybrid 检索返回了哪些 chunks?top 几个的 doc_id 和 score 是多少?
   - `grade` span:grader 判断 relevant=True 还是 False?
   - `generate` span:LLM 输入 prompt 和输出答案各是什么?token 数多少?
   - `grounding_check` span:grounder 判断 grounded=True 还是 False?
4. **对照 /metrics**:若该时段 `rag_llm_latency_seconds` 的 P99 偏高,对照看是 LLM 端慢还是 DB 检索慢。
5. **定位根因类别**:
   - 检索 chunks 不相关 → retrieval 问题,调 hybrid/rerank 参数。
   - chunks 相关但答案不接地 → LLM 幻觉或 grounding 阈值问题。
   - 延迟高但答案正确 → LLM 慢或 rerank 候选集过大。

**深挖追问**

- "如果客户端没有存 X-Request-ID 怎么查?" — 可以用 Langfuse 的 session_id(= thread_id)搜对话历史,再缩小到时间窗口。
- "request_id 是怎么生成并传播的?" — API 层 `add_request_id` 中间件:若请求头有 `X-Request-ID` 则复用,否则生成 UUID4;写入 response header 并注入 `config["metadata"]["request_id"]` 传给 LangGraph callbacks。

**常见误区**

- 误认为 thread_id 就是 request_id。thread_id 标识一条对话(多轮),request_id 标识一次 HTTP 请求(单次);一个 thread 可以有多个 request_id。
- 误认为只要有 trace 就能不用结构化日志。DB 连接失败、中间件异常等不经过 LangGraph callback 的问题,只能在应用日志里找。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md` → request_id 串联 trace 模式
- 详细可执行排查流程见 `docs/debugging-playbook.md`

---

## Q4: 为什么可观测性是一等公民?不加可观测性会怎样?

**答案要点**

- LLM 系统的两个特性决定了可观测性必须是一等公民:① 输入/输出是自然语言,**不可能**用 assert 覆盖所有 case;② 每次调用 LLM 都是外部 I/O,失败模式多样(超时、截断、幻觉、context 不足)。
- 没有 trace:用户反馈"答案不对",工程师无从还原那次请求的检索结果、LLM 输入输出,只能靠猜。
- 没有 metrics:无法区分"偶发用户投诉"还是"全局降级";无法做 SLO/SLA;告警完全靠人工巡检。
- 本项目在**设计阶段**就将 obs 作为注入组件(callbacks list),而非事后插桩——代价是多 2 个环境变量,收益是完整 trace 覆盖。

**常见误区**

- 误认为 print/logging 就够了。print 没有 span 层级、没有 latency 采样、没有 dashboard,对于分布式 agent 执行完全不够。
- 误认为可观测性是"上线前再加"。LangGraph 节点的 callback hook 是编译期注入,加 trace 需要在 `graph.compile(checkpointer=..., callbacks=...)` 时传入;事后改成本高。

**仓库概念文档**

- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md` → production observability 设计原则
