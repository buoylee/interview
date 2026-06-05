# LangGraph Agentic RAG 生产级 MVP 设计

> 目标读者:本人(Java/Go 后端转 LLM,准备 AI Engineer 面试)。
> 这份 spec 描述一个**可运行、生产形态**的企业知识库 Agentic RAG 助手,作为 `ai/langchain/` 12 章学习笔记的落地实现。

---

## 一、背景(Context)

`ai/langchain/` 已有 12 篇高质量学习笔记(约 5000 行),覆盖 Chat Models → Prompts → Parsers → LCEL → Tool Calling → Agents → RAG → LangGraph 核心/进阶 → 生产化 → 多 Agent。周边还有 `ml-to-llm-roadmap/02-agent-tool-use/`(厂商中立的 Agent 概念)、`rag-lab/`、`agent-memory/` 等概念资料。

**缺口:全部是 markdown + 零散代码片段,没有一个能跑起来的工程。** 没有 `pyproject`、没有 `.py`、没有把 FastAPI + LangGraph + Checkpointer + RAG + 可观测 + eval + 测试 + Docker 串起来的骨架。第 11 章「生产化」只是列了概念(LangSmith、retry/fallback、FastAPI、Docker),没有端到端把它们接通的参考实现。

要补的不是再写几篇概念,而是**一个真实可构建、可部署、可测试、可观测的参考项目**——把那 12 章落成一个能跑、能讲、能上线的东西。

---

## 二、目标 / 非目标

### 目标
- 产出一个**生产形态**的 Agentic RAG 参考项目:真实代码 + 真实接线 + 真实失败处理,`docker compose up` 可一键跑通。
- **必须真用 LangGraph**(不是只用 LangChain Chain);实现方式主流、合理。
- **生产级可观测**:执行过程可跟踪(trace)、可监控(metrics),坏答案能凭 `request_id` 定位到具体哪一步出错。
- 自然覆盖高频面试考点:LCEL、tool calling、ReAct、RAG(hybrid+rerank)、CRAG 自我纠正、checkpoint 持久化、HITL、streaming、多 Agent supervisor、可观测、eval、部署。
- 配套**面试 Q&A / 项目叙事文档层**,把代码转成可讲的面试火力;概念部分**复用**仓库已有文档,不重写。

### 非目标
- 不重写仓库里已有的可观测/eval/runtime **概念**文档;通过链接复用。
- 不做多服务/平台级架构(消息队列、多向量库、独立 ingestion/retrieval/agent 服务)——那超出 MVP,稀释 focus。
- 不实现完整企业级鉴权(OIDC/JWT/RBAC),MVP 用 API key 头占位并注明超纲。
- 不绑定任何付费 SaaS 才能跑;默认全本地/离线可用。
- 不做模型训练/微调/对齐。

---

## 三、已确定的决策

| 维度 | 结论 | 关键理由 |
|---|---|---|
| 首要目的 | 面试轻松应对 langchain/langgraph,底气来自生产级真实项目 | 项目要真能跑、能讲取舍 |
| 领域 | 企业知识库 Agentic RAG 助手 | AI Engineer 面试最经典、考点覆盖最广 |
| 形式 | 真实可跑参考项目 + 面试 Q&A 注解 | 纯概念已有,缺的是落地代码 |
| 模型栈 | **OpenAI 兼容 API**(默认 OpenAI,可换 `base_url`) | 一套代码切 OpenAI/Azure/本地 vLLM/Ollama;本身是面试加分点 |
| 架构路线 | 自建 FastAPI + Postgres 垂直切片 + 多 Agent supervisor 进核心 + 附 `langgraph.json` | 亲手接持久化/流式/trace 是面试火力点;supervisor 是高频考点 |
| 可观测 | **默认 Langfuse 自托管**(离线/免费/数据不出内网),放 callback 边界后可换 LangSmith;Phoenix 当超轻备选 | LangSmith 默认上云需联网、自托管仅 Enterprise;Langfuse MIT 开源、docker 本地全跑 |
| 落地位置 | `ai/langchain/mvp-agentic-rag/` | 紧挨 12 章笔记,「学习→落地」最连贯 |

**可观测选型说明(资深取舍):** 生产不会同时跑两个 trace 后端(双倍 callback 开销、split-brain、双倍维护)。正确做法是**选一个 + 放在可换边界后**。LangChain 的 callback 机制本身就是这层抽象:agent 从 config 收 `callbacks`,一个 env flag(`OBS_BACKEND`)决定注入哪个后端。
- 默认 **Langfuse 自托管**:MIT 开源、`docker compose up` 本地/离线全跑、trace 数据(含真实 query + 检索文档)不出内网、自托管免费。贴合企业知识库场景。
- **LangSmith** 作为「面试要会讲 + 1 个 flag 可切」:默认模式把 trace 上传 GCP us-central(需联网),自托管仅 Enterprise(付费、k8s)。建议注册免费账号看一眼 UI 即可。
- **何时翻向 LangSmith/云**:小团队要零运维、要最深 LangChain 集成和内建 dataset/eval、且无硬性数据驻留要求时。

---

## 四、整体架构

```
                ┌────────────────────── observability(单一后端,可换)──────────────────────┐
                │  默认 Langfuse(自托管/离线)  ┊  LangSmith(env flag 可切)  ┊  Phoenix(超轻)│
                │  + 自定义 MonitoringCallback: token / cost / latency / tool_err → /metrics  │
                └───────────────────────────────────────────────────────────────────────────┘
                                          ▲ trace 每一步(request_id 串联 trace+日志)
   ingest CLI                FastAPI                      LangGraph(顶层 supervisor 图)
 ┌───────────┐   upsert   ┌──────────┐  /chat,/stream  ┌───────────────────────────────────┐
 │ load→split│──────────▶ │  API 层  │ ───────────────▶│  supervisor → {kb_rag | web | END}│
 │ →embed    │            │ SSE 流式  │                 │   kb_rag 子图(CRAG):             │
 └───────────┘            └────┬─────┘                 │     retrieve→grade→generate→ground│
       │                       │ checkpoint(thread)    │   web 子图:create_react_agent     │
       ▼                       │                       │   human_review:interrupt()(可选)  │
 ┌──────────────────────┐     │                        └────────────────┬──────────────────┘
 │ Postgres(单库双用)   │◀────┴────────────────────────────────────────┘
 │  • pgvector(向量库)  │   retrieve(hybrid: 向量 + 全文 → RRF → rerank)
 │  • PostgresSaver(状态)│
 └──────────────────────┘
```

一个 Postgres 同时当向量库(pgvector)+ checkpointer,`docker compose up` 起 app + postgres(+ 可选 langfuse profile)。

### 模块布局

```
ai/langchain/mvp-agentic-rag/
├─ ingest/         文档加载→分块→嵌入→pgvector(content_hash 幂等去重)        ← 第4章
├─ retrieval/      hybrid(向量+全文)→ RRF 融合 → 可插拔 rerank → 可选压缩      ← 第4章
├─ agent/
│   ├─ graph.py        顶层 supervisor StateGraph 装配 + PostgresSaver
│   ├─ supervisor.py   supervisor 节点:结构化输出路由(Command(goto=...))
│   ├─ subgraphs/
│   │   ├─ kb_rag.py   ★知识库 Agentic RAG 子图(CRAG 风味)
│   │   └─ web.py      库外/兜底 create_react_agent(web_search stub)
│   ├─ human_review.py HITL:敏感动作前 interrupt() → Command(resume=...)
│   ├─ tools.py        retrieve_kb / 计算 / web_search(stub)
│   └─ state.py        State(TypedDict) + add_messages reducer
├─ api/            FastAPI:/chat /chat/stream /threads /ingest /healthz /readyz /metrics ← 第7章
├─ obs/            可观测后端工厂(langfuse|langsmith|phoenix|none)+ MonitoringCallback ← 第7章★
├─ eval/           golden set(JSONL)+ ragas + 轨迹自检 + 回归对比 + 报告              ← 第7章
├─ core/           config(pydantic-settings)、LLM/embedding 工厂、resilience
├─ tests/          单元 + 集成(假 LLM 跑整图)+ eval smoke
├─ docs/           ARCHITECTURE / PROJECT-NARRATIVE / interview-qa/ / debugging-playbook
├─ langgraph.json  让它也能在 LangGraph Server/Studio 跑(借路线 C)
├─ docker-compose.yml / Dockerfile / pyproject.toml / Makefile / .env.example
└─ README.md       quickstart + 「12 章 → MVP 落点」覆盖表
```

每个模块单一职责、可独立测试。

---

## 五、模块设计

### 5.1 Agent 状态图(核心)

**顶层 = supervisor 路由图,知识库 RAG 是它的子图。** 用 Graph API(主流、可 `draw_mermaid_png` 可视化、LangGraph Studio 友好)。

```
              START ──▶ supervisor ──Command(goto)──▶ {kb_rag_agent | web_agent}
                           ▲                                   │
                           └───────────────────────────────────┘ (专家做完回到 supervisor,可多轮)
              supervisor ──route=FINISH──▶ END
              supervisor ──敏感动作──▶ human_review (interrupt → resume)
```

**顶层 State(TypedDict):**
- `messages: Annotated[list, add_messages]` — 对话累加(Reducer)
- `next: str` — supervisor 决定的下一个 agent(`kb_rag` / `web` / `FINISH`)
- `citations: list` — 跨节点累积的引用来源
- `step_budget: int` — 步数/成本预算护栏,超了强制 FINISH

**kb_rag_agent 子图(CRAG/Self-RAG 风味,强考点):**

```
START → retrieve(hybrid → rerank)
          → grade_docs(相关性打分) ──不相关──▶ rewrite_query →(回 retrieve,有上限)
          → generate(带引用作答)
          → grounding_check(LLM-as-judge 忠实度) ──不忠实──▶ 重检索 / 降级声明「依据不足」
          → END(回 supervisor)
```

**实现方式(主流 + 能讲原理 的混搭):**
- `supervisor`:手写节点 + `Command(goto=..., update=...)` 路由;README 注明生产可换 `langgraph-supervisor` 预构建。
- `kb_rag` 子图:**手写**节点/条件边——能在白板上画出来、逐节点讲取舍。
- `web_agent`:用预构建 `create_react_agent`——展示也会用现成轮子、知道何时不重造。
- 持久化:`PostgresSaver` 在顶层 checkpoint;子图状态随顶层一起存。
- HITL:`interrupt()` 在 `human_review`,`Command(resume=...)` 恢复,绑定敏感工具。

### 5.2 检索层

原则:主流、无额外基建(复用同一个 Postgres)、可调可讲。

```
query
  ├──▶ dense:  pgvector ANN(向量 cosine, top_k_dense)
  ├──▶ sparse: Postgres 全文检索 tsvector + ts_rank(top_k_sparse)
  ▼ RRF(Reciprocal Rank Fusion)合并两路排名
  ▼ rerank: 可插拔 cross-encoder(默认本地 bge-reranker, 取 top_n)
  ▼ (可选)ContextualCompression 裁掉无关句,省 token
  ▼ 返回 chunks + metadata(doc_id/来源/页码)→ 供 generate 做引用
```

**关键取舍:**

| 决策 | 选什么 | 为什么 / 替代 |
|---|---|---|
| 稀疏路 | Postgres 全文检索(tsvector) | 不引入 ES;要真 BM25 可换 ParadeDB/`pg_search`,README 注明 |
| 融合 | RRF | 参数少、不需调权重;框架等价物是 LangChain `EnsembleRetriever` |
| rerank | 本地 cross-encoder,做成可插拔接口 | LLM 栈锁 OpenAI 兼容,rerank 是独立关注点;云端 rerank API 可一键换 |
| 压缩 | 可选 `ContextualCompressionRetriever` | 省 token/降成本,延迟换成本,默认关 |

**pgvector 表 schema 要点:** `embedding(vector)` + `content` + `metadata(jsonb)` + `tsvector`(全文)+ `content_hash`(幂等去重)+ `doc_id/chunk_idx`(引用定位)。一张表同时支撑 dense + sparse。

**可调旋钮:** `top_k_dense / top_k_sparse / rrf_k / rerank_top_n / chunk_size / overlap`,调参经验复用 `rag-lab/03,08`。

### 5.3 持久化

- 顶层图挂 `PostgresSaver`(`langgraph-checkpoint-postgres`),`thread_id` = 一个会话。
- 每个 super-step 存完整 state 快照 → 支持中断恢复、时间旅行、HITL。
- 同一个 Postgres、配连接池;首次 `.setup()` 自动建 checkpoint 表。
- 考点:`MemorySaver`(开发)/ `SqliteSaver`(单机)/ `PostgresSaver`(生产多实例)怎么选;checkpoint vs thread vs checkpoint_id。

### 5.4 可观测

```
请求 request_id + thread_id 注入 trace metadata & 结构化日志(structlog JSON)
   ├─▶ 可观测后端(单一,OBS_BACKEND 决定):
   │     Langfuse(默认/自托管):CallbackHandler 注入,docker 本地跑,数据不出内网
   │     LangSmith(可切):3 个 env 变量,自动嵌套 span,数据上云
   │     Phoenix(超轻备选):pip 起本地 UI,OTel,无需账号
   │   → 看到:supervisor 路由 → kb_rag 子图 → retrieve(命中 chunks!)→ rerank
   │         → generate → grounding_check,每步 token/cost/latency
   └─▶ 自定义 MonitoringCallback → Prometheus /metrics
         counter: requests / tokens / cost / tool_errors;histogram: latency / ttft / retrieved_docs
```

- **trace 与 metrics 是可观测的两根支柱,不重复**:trace 查单条请求,metrics 看聚合 + 告警。MVP 保留精简 metrics callback(证明懂区分、会抽指标),Grafana 整套留扩展。
- **OpenTelemetry** 留扩展:`openinference-instrumentation-langchain` 发 OTel span → Grafana/Datadog。
- **让排查 playbook 真能跑**:`request_id` 串起 trace + 结构化日志,坏答案 → 拿 request_id → 开 trace → 一眼看出哪一步错。这把 `06-agent-runtime-engineering`(trace+recoverability 层)和 `03-production-debugging-monitoring`(监控维度 + 症状→组件排查)**变成可执行实现**。
- 日志字段照 `03` 的可复现清单:`request_id / model+version / prompt_version / context chunk ids / decoding params / output / parser result / latency / cost`(隐私敏感则脱敏)。

### 5.5 Eval

Agent eval 分两层:

```
golden set(JSONL 进 git):问题 + 期望(must_include / 期望路由 / 期望工具 / 该不该拒答 / 期望引用)
   ▼ make eval(离线、可 CI)
① RAG 质量(ragas, LLM-as-judge)         ② Agent 轨迹(轻量自检)
   faithfulness / answer_relevancy            路由对不对 / 调没调该调的工具 / 步数·成本是否超预算
   context_precision / context_recall
   + 自定义:must_include、引用存在性、该拒答时拒答
   ▼ 报告 report.md/json(分维度 + 失败样本)
   ▼ 回归对比(diff 上次 run),新回归就 fail(CI 灰度门)
   ▼ 可选:scores 推到 Langfuse,和 trace 并排看(在线 eval 雏形)
```

| 决策 | 选什么 | 为什么 |
|---|---|---|
| RAG 指标 | ragas | RAG eval 事实标准、开源本地跑;judge LLM 指向同一个 OpenAI 兼容端点(可用便宜模型省成本) |
| 轨迹 eval | 轻量自写 | MVP 不上重型 trajectory 框架;能讲清「agent eval ≠ RAG eval」 |
| 数据集 | JSONL 进 git | 版本化、可 diff、零外部依赖;即 `03` 文档的 regression set |
| 回归门 | CI 跑子集,新回归 fail | 落地「先过 golden+regression 再灰度」 |
| 在线 eval | 推 scores 到 Langfuse(可选) | 采样线上 trace 做 LLM-as-judge,雏形即可 |

### 5.6 韧性

| 层 | 手段 |
|---|---|
| LLM 客户端 | `max_retries` + `timeout` |
| 节点/链 | `.with_retry(stop_after_attempt, wait_exponential_jitter)` |
| 降级 | `.with_fallbacks([便宜模型链])`:主模型→小模型→「依据不足」兜底 |
| Agent 环护栏 | LangGraph `recursion_limit` + state `step_budget` 超了强制 FINISH |
| 成本护栏 | 累加 `usage_metadata`,超 token/成本预算即停 |
| 优雅降级 | 检索挂→hedge 作答不崩;rerank 挂→退回 RRF 顺序;可观测后端挂→trace 静默降级、服务照跑 |

### 5.7 配置

- `core/config.py`:`pydantic-settings` BaseSettings + `.env.example`(提交)。
- 关键项:`LLM_BASE_URL/API_KEY/MODEL/MODEL_FALLBACK`、`EMBEDDING_BASE_URL/MODEL`、`RERANK_*`、`DATABASE_URL`、`OBS_BACKEND`(langfuse|langsmith|phoenix|none)、`LANGFUSE_*`/`LANGSMITH_*`、检索旋钮、`STEP_BUDGET`、超时。
- `core/llm.py`:LLM/embedding **工厂**,从 config 返回 provider 中立客户端(OpenAI 兼容 `base_url`)——切供应商只动一处。

### 5.8 API 面

```
POST /chat                  同步 → {response, citations, request_id}
POST /chat/stream           SSE token 级(astream_events / stream_mode="messages")
GET  /threads/{id}          取会话状态(checkpointer,历史/时间旅行)
POST /threads/{id}/resume   HITL 恢复(Command(resume=...))
POST /ingest                触发入库(CLI 为主,端点可选 + 鉴权)
GET  /healthz /readyz       探活 / 就绪(DB ping)
GET  /metrics               Prometheus
```

request_id 中间件 + 结构化日志 + 统一错误封套;MVP 用 API key 头鉴权(真实 OIDC/JWT 注明超纲)。

### 5.9 测试

- **单元**:retrieve 形状、RRF 融合、rerank 接口、citation 格式化、budget 护栏、结构化输出。
- **集成**:用假 LLM(`GenericFakeChatModel` 确定性)跑整图——断言路由正确、调对工具、ReAct 环会终止、checkpoint 存取/恢复、HITL interrupt+resume。pgvector 用测试 Postgres(testcontainers)。
- **eval smoke**:CI 跑 golden 子集,指标低于阈值就 fail。
- 考点:非确定性怎么测——逻辑用假 LLM 断言,质量用 eval 不用断言。

### 5.10 面试敘事文档层

项目内 `docs/`,**全部链接已有概念文档、不重写概念**:
- `ARCHITECTURE.md`:系统图 + 组件职责 + 数据流 + 每个关键决策的 why/替代/取舍。
- `PROJECT-NARRATIVE.md`:STAR 故事(30 秒 / 2 分钟 / 深挖三版)+ 真实指标(eval 分、延迟、成本)。
- `interview-qa/*.md`:按子系统的 Q&A + 深挖追问,链接 `rag-lab/03,08`、`02-agent-tool-use/05,06,09`、`07/01,03`、`11-production` 等。
- `debugging-playbook.md`:把 `03` 的「症状→组件」在本系统上可执行化。
- 顶层 `README.md`:`docker compose up` → `make ingest` → `make run` → `make eval` 快速跑通 + 「12 章 → MVP 落点」覆盖表。

---

## 六、12 章 → MVP 覆盖映射

| 教程章节 | 在 MVP 的落点 |
|---|---|
| 02 Chat Models | `core/llm.py` 工厂(OpenAI 兼容,invoke/stream/batch) |
| 03 Prompt Templates | 各节点 prompt(supervisor/generate/grade/grounding) |
| 04 Output Parsers | supervisor 路由 + grade/grounding 用 `with_structured_output` |
| 05 LCEL | retrieve→prompt→llm→parse 链;`.with_retry/.with_fallbacks` |
| 06 Tool Calling | `agent/tools.py`(retrieve_kb / 计算 / web_search)+ `bind_tools` |
| 07 Agents | `web_agent` = `create_react_agent`;ReAct 循环 |
| 08 RAG | `ingest/` + `retrieval/`(hybrid+RRF+rerank)+ kb_rag 子图 |
| 09 LangGraph 核心 | `agent/graph.py`(State/Node/Edge/条件边/循环)+ PostgresSaver |
| 10 LangGraph 进阶 | HITL `interrupt`、streaming、子图、CRAG/router 模式 |
| 11 生产化 | `obs/` 可观测、resilience、FastAPI、Docker、`langgraph.json` |
| 12 多 Agent | supervisor 顶层图 + 专家子图 + handoff |

---

## 七、复用的已有概念文档(链接,不重写)

- `ai/rag-lab/03-hybrid-rerank-debugging.md`、`08-chunking-tuning-playbook.md`(检索/调参)
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md`、`04-rag-evaluation-debugging.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/02-tool-use-and-recovery.md`、`05-agent-patterns-and-architectures.md`、`06-agent-runtime-engineering.md`、`09-multi-agent-coordination.md`、`11-agent-eval-practice.md`
- `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md`、`03-production-debugging-monitoring.md`
- `ai/langchain/11-production.md`(LangSmith/Langfuse/MonitoringCallback 片段)

---

## 八、实现阶段(粗粒度,留待 writing-plans 细化)

1. **骨架**:仓库结构、`pyproject`、config、LLM 工厂、docker-compose(app+postgres)、`healthz`。
2. **RAG 数据通路**:ingest CLI → pgvector;retrieval(hybrid+RRF+rerank);`retrieve_kb` 工具。
3. **Agent 图**:kb_rag 子图(CRAG)→ supervisor → web_agent → PostgresSaver;`draw_mermaid_png` 可视化。
4. **API + streaming**:`/chat`、`/chat/stream`、`/threads`、HITL resume。
5. **可观测**:Langfuse 默认接线 + MonitoringCallback + `/metrics` + request_id 串联;LangSmith/Phoenix 可切。
6. **韧性**:retry/fallback/budget/降级。
7. **Eval**:golden set + ragas + 轨迹自检 + 回归报告 + CI smoke。
8. **测试**:单元 + 假 LLM 集成。
9. **文档层**:ARCHITECTURE / PROJECT-NARRATIVE / interview-qa / debugging-playbook / README 覆盖表。
10. **(扩展)**:`langgraph-supervisor` 预构建对照、OTel、Grafana、第 3 个专家 agent、在线 eval。

---

## 九、验收标准

- `docker compose up` 后,`make ingest`(示例语料)→ `make run` → `/chat` 能就一个知识库问题给出**带引用**的答案;`/chat/stream` token 级流式。
- 在默认 Langfuse UI 里能看到一次请求的**完整 trace 树**(supervisor 路由 → 检索命中的 chunks → rerank → 生成 → grounding),每步有 token/latency。
- 切 `OBS_BACKEND=langsmith` 后无需改代码即可改用 LangSmith。
- HITL:敏感动作触发 `interrupt`,`/threads/{id}/resume` 能恢复。
- `make eval` 产出分维度报告;CI 上质量回归会 fail。
- `make test` 全绿(含假 LLM 跑整图的集成测试)。
- `docs/` 的 interview-qa 覆盖各子系统,且链接到对应概念文档。
- README 的「12 章 → MVP 落点」覆盖表完整。
