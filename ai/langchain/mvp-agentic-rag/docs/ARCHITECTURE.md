# 架构文档 — Agentic RAG MVP

> 面向 AI Engineer 面试的参考项目。完整设计 spec 见
> [`../../../../docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`](../../../../docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md)；
> Agent 运行时工程概念见
> [`../../../../ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md`](../../../../ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md)。

---

## 一、系统总览图

```
         ┌──────────────── observability(单一后端,OBS_BACKEND 决定)──────────────────┐
         │  默认 Langfuse(自托管/离线/MIT)                                           │
         │  ┊ LangSmith(env flag 可切,数据上云)   ┊  none(开发/测试)               │
         │  + MonitoringCallback → Prometheus /metrics                                │
         │    token / cost / latency / tool_err counter + latency histogram           │
         └────────────────────────────────────────────────────────────────────────────┘
                                    ▲ trace 每一步(request_id 串联 trace + 日志)

  ingest CLI                  FastAPI                    LangGraph 顶层 supervisor 图
┌──────────────┐  upsert   ┌──────────────┐  /chat      ┌─────────────────────────────────────┐
│ load → split │──────────▶│   API 层      │ /chat/stream│  supervisor                          │
│ → embed      │           │   SSE 流式    │────────────▶│    ↓ supervisor 写 next,经 add_conditional_edges 路由(等价于 Command(goto=...))│
│ content_hash │           │   request_id  │             │  ┌──────────┐   ┌──────────────────┐ │
│  幂等去重     │           │   API key 鉴权│             │  │  kb_rag  │   │   web_agent      │ │
└──────────────┘           └──────┬───────┘             │  │  子图    │   │ create_react_    │ │
        │                         │ checkpoint(thread)  │  │  (CRAG)  │   │ agent(ReAct 环)  │ │
        ▼                         │                     │  └──────────┘   └──────────────────┘ │
┌─────────────────────────────┐   │                     │  human_review: interrupt()(HITL)      │
│  Postgres(单库双用)          │◀──┴─────────────────────┤                                      │
│  pgvector → dense ANN       │                         └─────────────────────────────────────┘
│  tsvector  → sparse FTS     │   retrieve(hybrid):
│  PostgresSaver → checkpoint │     向量 + 全文 → RRF → rerank
└─────────────────────────────┘

  eval/
    golden/cases.jsonl     ← golden set,版本化进 git
    reports/report.json    ← make eval 产出,CI 灰度门
```

---

## 二、组件职责表

| 组件 | 模块 | 一句话职责 |
|---|---|---|
| **ingest** | `ingest/` | 文档 load → 分块 → embed → pgvector upsert,content_hash 幂等去重 |
| **retrieval** | `retrieval/` | 向量(dense)+全文(sparse)双路检索 → RRF 融合 → cross-encoder rerank,返回 top-N chunks + metadata |
| **agent graph** | `agent/graph.py` | 顶层 StateGraph:supervisor 路由 → kb_rag 子图 / web_agent / human_review,PostgresSaver 持久化每个 super-step |
| **supervisor** | `agent/supervisor.py` + `components.py:LLMRouter` | 结构化输出路由决策(RouteDecision),决定下一个节点:kb_rag / web / human_review / FINISH |
| **kb_rag 子图** | `agent/subgraphs/kb_rag.py` | CRAG 风味子图:retrieve → grade → [rewrite] → generate → grounding_check → [hedge];双轴自纠正(相关性 + 接地性) |
| **web agent** | `agent/subgraphs/web.py` | 库外/兜底:prebuilt `create_react_agent`,ReAct 工具调用环 |
| **human_review** | `agent/human_review.py` | 敏感动作前 `interrupt()`,等 `/threads/{id}/resume` 传入 `Command(resume=...)` 后继续 |
| **API** | `api/app.py` | FastAPI:/chat(同步)、/chat/stream(SSE)、/threads(状态读取)、/threads/resume(HITL)、/healthz、/readyz、/metrics |
| **obs** | `obs/backends.py` + `obs/callbacks.py` + `obs/metrics.py` | 可观测工厂:OBS_BACKEND 决定注入 Langfuse/LangSmith/none;MonitoringCallback 推 Prometheus 指标 |
| **eval** | `eval/` | golden set(JSONL)→ run_eval(纯函数检查)→ EvalReport → 回归 diff;可选 ragas live 指标 |
| **core** | `core/config.py` + `core/llm.py` + `core/resilience.py` | pydantic-settings 配置、OpenAI 兼容 LLM/embedding 工厂、主模型 + fallback 降级链 |

---

## 三、请求数据流

以 `POST /chat` 为例,完整的一次请求路径:

```
1. 客户端发送请求
   POST /chat  {message: "...", thread_id: "t-123"}
   (可带 X-Request-ID 头;中间件若无则生成 UUID 并写回响应头)

2. API 层
   add_request_id 中间件 → request_id = "abc123"
   require_api_key 校验常数时间比较(防 timing attack)
   → deps.graph.invoke({"messages": [HumanMessage], "next":"", "citations":[], "step_budget":6},
                       config={thread_id, callbacks=[MonitoringCallback, LangfuseHandler]})

3. LangGraph 顶层图执行
   START → supervisor
   supervisor:
     LLMRouter.route(messages) → with_structured_output(RouteDecision)
     → next = "kb_rag"
   Command(goto="kb_rag") → kb_rag 节点

4. kb_rag 节点(调 CRAG 子图)
   subgraph START → retrieve
     HybridRetriever.retrieve(query):
       dense: pgvector ANN cosine (top_k_dense=20)
       sparse: tsvector ts_rank (top_k_sparse=20)
       reciprocal_rank_fusion(k=60) → 候选排名
       Reranker.rerank → top_n=5 最终 chunks
   → grade(LLMDocGrader.grade): relevant?
     relevant=True → generate
     relevant=False, rewrites<1 → rewrite → retrieve(再来一次)
     relevant=False, 超预算 → hedge("未找到足够依据…")
   → generate(LLMAnswerGenerator.generate):
       构建 citations = [{doc_id, chunk_idx, content}…]
       LLM 带引用作答
   → grounding_check(LLMGroundingChecker.check):
       grounded=True → subgraph END
       grounded=False → rewrite 或 hedge
   → 返回 {answer, citations}

5. kb_rag 节点 → supervisor(边 kb_rag→supervisor)
   supervisor 看 messages 里已有 AI 答案 → route = "FINISH"
   → END

6. 结果回到 API
   取 messages[-1](AIMessage) 作 response
   返回 ChatResponse{response, citations, request_id}

7. 可观测侧(每步并行)
   LangfuseHandler: 每个 LLM call → span,带 tokens/latency/model
   MonitoringCallback: on_llm_end → rag_requests_total++,token counter++
   structlog JSON: request_id + thread_id + node + latency
   → Langfuse UI: 完整 trace 树(可查 chunks 命中情况)
   → /metrics: Prometheus counter/histogram(Grafana 可接)
```

---

## 四、关键决策表

### 决策 ①：一个 Postgres 同时充当向量库(pgvector)和 checkpointer(PostgresSaver)

| 项 | 内容 |
|---|---|
| **决策** | 同一个 Postgres 实例:pgvector 存 chunks+embedding+tsvector;PostgresSaver 存 LangGraph checkpoint |
| **为什么** | MVP 阶段最小基建依赖:一个 `docker compose up` 起 app+postgres,无需额外 Qdrant/Redis/Weaviate;两类数据都是强事务性场景(upsert 幂等、checkpoint 原子快照),Postgres 的 ACID 正好;运维面只有一个库要备份和监控 |
| **替代方案** | 向量库单独跑 Qdrant/Weaviate;checkpoint 用 Redis。两库都有更优的向量性能上限 |
| **取舍** | 向量规模 <1M chunks 时 pgvector HNSW 性能完全够用;超出后需迁移到专用向量库。checkpoint 表和向量表共享连接池,写入高峰可能互相干扰(可拆 pool 缓解)。MVP 接受这个取舍换最小复杂度 |

---

### 决策 ②：hybrid 检索(向量 + 全文) + RRF + rerank,而非纯向量

| 项 | 内容 |
|---|---|
| **决策** | dense(pgvector cosine ANN)+ sparse(Postgres tsvector ts_rank)→ RRF 融合 → cross-encoder rerank |
| **为什么** | 纯向量对精确术语/缩写召回差(embedding 往往语义平滑掉关键词);纯 BM25 对语义近义词/同义改写盲目。两路互补:dense 补语义,sparse 补精确词;RRF 融合不需调权重(两路 recall 差距不大时 RRF 稳健);rerank 在 RRF 候选上做精排,把 recall 问题和 precision 问题分开解决 |
| **替代方案** | 纯向量;纯 BM25;加权线性融合(需调权重α);Elasticsearch/OpenSearch 原生 hybrid;ParadeDB/pg_search 真 BM25 |
| **取舍** | 三阶段(dense+sparse+rerank)比单路多两次 I/O + 一次 cross-encoder 推理,延迟增加约 200-400ms。换来 recall+precision 同步提升,对企业知识库场景是值得的取舍。中文全文需 pg_jieba 分词,当前用 `fts_config=simple`(ASCII 友好),中文效果有限 |

---

### 决策 ③：CRAG 自纠正子图,而非一次性 RAG

| 项 | 内容 |
|---|---|
| **决策** | kb_rag 子图实现 CRAG(Corrective RAG)风味:retrieve → grade(相关性) → [rewrite+重检索] → generate → grounding_check(接地性) → [降级 hedge] |
| **为什么** | 一次性 RAG 的问题:检索到不相关文档时 LLM 仍会编造,grounding 无保障。CRAG 双轴自纠正:① grade 节点过滤不相关召回,触发 query rewrite 再检索;② grounding_check(LLM-as-judge)验证生成答案是否被 chunks 支持,不支持则 hedge 返回「依据不足」。两个自检环把幻觉概率显著压低 |
| **替代方案** | 一次性 RAG(无 grade/grounding);Self-RAG(更复杂,每 token 生成时打分);CoVE(思维链验证) |
| **取舍** | 每次请求多 2-3 次 LLM 调用(grade + grounding,各约 500ms+);rewrite+再检索最多触发 `max_rewrites=1` 次(可配置),防死循环。`step_budget` 护栏兜底。延迟换可靠性,企业知识库场景无法接受无依据答案,这个取舍合理 |

---

### 决策 ④：supervisor 模式,而非 swarm 对等多 Agent

| 项 | 内容 |
|---|---|
| **决策** | 顶层图用 supervisor(单一调度节点 + `Command(goto=...)`)统一路由到 kb_rag/web/human_review |
| **为什么** | 企业 RAG 场景的路由逻辑明确且有优先级(优先知识库→退库外→人工审核),不需要 peer-to-peer 动态协商。supervisor 的路由决策集中、可解释、可在 trace 里一眼看到;swarm 的去中心化路由更难 debug。LangGraph 的 `Command` API 天然支持 supervisor:一个节点发 `Command(goto=X, update={...})` 就能切换专家 |
| **替代方案** | swarm(平权多 Agent 相互 handoff);hierarchical multi-supervisor;pipeline(固定顺序) |
| **取舍** | supervisor 是单点,路由逻辑集中在 LLMRouter;supervisor 节点本身的 LLM call 增加每轮延迟约 500ms。swarm 适合专家域对等、路由逻辑去中心化的场景(如复杂工作流 orchestration) |

---

### 决策 ⑤：PostgresSaver,而非 MemorySaver 或 SqliteSaver

| 项 | 内容 |
|---|---|
| **决策** | 生产用 `PostgresSaver`(`langgraph-checkpoint-postgres`)持久化 LangGraph checkpoint |
| **为什么** | `MemorySaver` 进程内存,进程重启/崩溃后对话历史全丢,无法支持多副本水平扩展。`SqliteSaver` 单机文件,多副本写同一文件会锁冲突,且无连接池。`PostgresSaver` 跨进程/副本共享状态,HITL interrupt+resume 在不同实例上可恢复,时间旅行(get_state by checkpoint_id)也靠它 |
| **替代方案** | MemorySaver(开发/测试用);SqliteSaver(单机无 HA 场景);自实现 Redis checkpointer |
| **取舍** | 需要一个 Postgres 实例(本项目复用同一库,无额外成本);`.setup()` 首次运行自动建 checkpoint 表;连接池配置不当可能成瓶颈(用 `pool_size` 参数控制) |

---

### 决策 ⑥：默认 Langfuse 自托管,而非 LangSmith

| 项 | 内容 |
|---|---|
| **决策** | `OBS_BACKEND=langfuse`(默认),`docker compose --profile langfuse up` 本地跑;`OBS_BACKEND=langsmith` 一个 flag 可切 |
| **为什么** | **数据驻留**:企业知识库的 trace 包含真实查询 + 检索到的内部文档内容,数据不应出内网。Langfuse 自托管时 trace 数据完全在本地 Postgres,不出任何第三方。**成本**:Langfuse MIT 开源,`docker compose up` 零费用;LangSmith 默认把 trace 上传 GCP us-central1,自托管仅 Enterprise 版(付费 + k8s 运维)。**离线**:Langfuse 自托管可在完全断网环境跑;LangSmith 云版需联网。**开源**:Langfuse 社区活跃,可 fork/定制,无供应商锁定 |
| **替代方案** | LangSmith 云版(最深 LangChain 集成、内建 dataset/eval UI、零运维);Phoenix(超轻,OTel,pip 起本地 UI);none(开发/测试) |
| **取舍** | Langfuse 自托管多一个运维对象(langfuse + clickhouse 或 postgres),升级需手动。LangSmith 在需要 built-in dataset/eval 工作流、小团队要零运维、且无硬性数据驻留要求时更合适。本项目的 callback 边界(`get_observability_callbacks()` 工厂)让切换只需改一个 env var,不改代码 |

---

### 决策 ⑦：OpenAI 兼容接口,统一 LLM/embedding 工厂

| 项 | 内容 |
|---|---|
| **决策** | `core/llm.py` 工厂统一用 `langchain_openai.ChatOpenAI(base_url=..., api_key=...)`;embedding 同理。`LLM_BASE_URL` 可指向 OpenAI/Azure OpenAI/本地 vLLM/Ollama |
| **为什么** | OpenAI API 已成行业 de-facto 标准,主流供应商(Azure、Fireworks、Together、Groq、本地 vLLM/Ollama)均提供兼容接口。一套代码切供应商只需改 `.env` 的 `LLM_BASE_URL + LLM_API_KEY + LLM_MODEL`,不改任何业务逻辑。面试角度:能讲清「接口隔离」+ 「供应商无关」是加分项 |
| **替代方案** | 各供应商原生 SDK;LiteLLM proxy 统一转发;LangChain provider-specific 类(ChatAnthropic 等) |
| **取舍** | 依赖供应商遵循 OpenAI 兼容规范;少数高级功能(如 Anthropic Computer Use)需专用 SDK。本项目使用的功能(chat completion + structured output + embedding)所有主流供应商都支持 |

---

### 决策 ⑧：fallback 只接纯 `.invoke` 组件,不接结构化输出组件

| 项 | 内容 |
|---|---|
| **决策** | `get_chat_model_with_fallback()` 返回 `primary.with_fallbacks([fallback])`(RunnableWithFallbacks);只给 `LLMQueryRewriter`(plain `.invoke`)和 `LLMAnswerGenerator`(plain `.invoke`)挂 fallback。`LLMRouter`/`LLMDocGrader`/`LLMGroundingChecker` 用普通 `chat`(无 fallback) |
| **为什么** | `primary.with_fallbacks([fallback])` 返回的是 `RunnableWithFallbacks` 对象,**没有 `.with_structured_output()` 方法**。如果对 `RunnableWithFallbacks` 调用 `.with_structured_output(RouteDecision)`,运行时报 `AttributeError`,整个 agent 崩溃。因此,凡是需要结构化输出(`with_structured_output`)的组件,必须先拿到原始 `ChatOpenAI` 对象再调 `.with_structured_output()`,不能先 wrap fallback |
| **替代方案** | 在 `with_structured_output()` 之后再用 `.with_fallbacks()` 包:即 `chat.with_structured_output(Schema).with_fallbacks([chat_fb.with_structured_output(Schema)])`,两边都做结构化 |
| **取舍** | 当前路由/评分/接地组件无 fallback 保护;主模型宕机时这三个节点会抛异常而非优雅降级。`factory.py` 注释已明确标注此限制,正确做法(在 structured_output 之后包 fallback)留作后续 |

---

## 五、模块目录

```
src/mvp_agentic_rag/
├── core/          config(pydantic-settings) / llm 工厂 / db / resilience
├── ingest/        loader / splitter / pipeline / cli
├── retrieval/     dense / sparse / fusion(RRF) / rerank / hybrid / factory / types
├── agent/
│   ├── state.py           AgentState(顶层) + KBRagState(子图)
│   ├── graph.py           顶层 StateGraph 装配
│   ├── factory.py         build_production_agent_graph(DB, checkpointer, settings)
│   ├── supervisor.py      make_supervisor_node
│   ├── components.py      LLMRouter / LLMDocGrader / LLMQueryRewriter / LLMAnswerGenerator / LLMGroundingChecker
│   ├── human_review.py    HITL interrupt 节点
│   ├── tools.py           retrieve_kb_tool / web_search stub
│   └── subgraphs/
│       ├── kb_rag.py      build_kb_rag_subgraph(CRAG)
│       └── web.py         build_web_agent(create_react_agent)
├── api/           FastAPI app / deps / schemas
├── obs/           backends(工厂) / callbacks(MonitoringCallback) / metrics(Prometheus)
└── eval/          checks / dataset / runner / report / ragas_eval / cli
```
