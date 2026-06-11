# 企业知识库 Agentic RAG 助手（MVP）

> **一句话定位**：把 `ai/langchain/` 12 章教程落成一个**生产形态**的可运行工程——带引用、带自纠正（CRAG）、可观测、可 eval，`docker compose up` 一键跑通。

- 架构决策与组件职责 → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 面试叙事（30 秒 / STAR / 深挖）→ [docs/PROJECT-NARRATIVE.md](docs/PROJECT-NARRATIVE.md)
- 各子系统面试 Q&A → [docs/interview-qa/](docs/interview-qa/)

---

## Quickstart

```bash
make install          # uv sync --extra dev 安装依赖
make up               # docker compose 起 postgres（pgvector + checkpoint）
cp .env.example .env  # 填 EMBEDDING_* / LLM_*（+ LANGFUSE_* 看 trace）
make db-init          # 建表（pgvector + PostgresSaver 表）
make ingest           # 把 sample_docs 入库（幂等，可重跑）
make serve            # 起 API：http://localhost:8000  (/docs 看 OpenAPI)
make eval             # 离线 eval（需 key，产出 eval/reports/report.{json,md}）
make test             # hermetic 全量测试（不联网、不需 key）
```

> **说明：** `make test` hermetic，完全离线；`make serve / make eval` 需要 `.env` 的 `LLM_*` / `EMBEDDING_*` key 与运行中的 Postgres。

---

## API 一览

| 端点 | 方法 | 说明 |
|---|---|---|
| `/chat` | POST | 同步问答，返回 `{response, citations, request_id}` |
| `/chat/stream` | POST | SSE token 级流式（`astream_events`） |
| `/threads/{id}` | GET | 取会话历史 / 时间旅行（从 checkpointer 读） |
| `/threads/{id}/resume` | POST | HITL 恢复（`Command(resume=...)`） |
| `/healthz` | GET | 存活探针 |
| `/readyz` | GET | 就绪探针（DB ping） |
| `/metrics` | GET | Prometheus 指标（请求数 / token / 延迟 / 工具错误） |

---

## 可观测切换

```bash
OBS_BACKEND=none        # 关闭 trace（测试 / 离线）
OBS_BACKEND=langfuse    # 默认：Langfuse 自托管（docker 本地，数据不出内网）
OBS_BACKEND=langsmith   # 切 LangSmith（需 LANGSMITH_API_KEY，trace 上云）
OBS_BACKEND=otel        # OTel GenAI 语义约定 span,OTLP 导出(默认打到 Langfuse 的 /api/public/otel)
```

切换只改一个 env 变量，无需修改代码（callback 工厂在 `obs/` 注入）。

`otel` 后端是手写的 `OTelTraceCallback`(`obs/otel.py`):把 LangChain 回调的边界翻译成 OTel span——chain(图节点,负责把树接起来)、LLM 调用(GenAI 语义约定 `gen_ai.*`,挂 token 数)、工具、检索;`run_id/parent_run_id` 映射成 span 父子树,带取消泄漏清扫。OTLP 出口指向哪个后端只由 env 决定——Langfuse、Phoenix、Jaeger、Datadog 都收 OTLP,换后端零代码改动。与 [agent-loop-lab](../../agent-loop-lab/) 的手动埋点是同一套语义约定的两种接入方式;现成替代品是 OpenInference/OpenLLMetry 的 LangChain instrumentor。

---

## 12 章 → MVP 落点

> 这张表证明这一个项目把 `ai/langchain/` 整套 12 章教程落成了可运行实现。

| 教程章节 | 在 MVP 的落点 |
|---|---|
| 02 Chat Models | `core/llm.py` 工厂（OpenAI 兼容，invoke / stream / batch） |
| 03 Prompt Templates | 各节点 prompt（supervisor / generate / grade / grounding） |
| 04 Output Parsers | supervisor 路由 + grade / grounding 用 `with_structured_output` |
| 05 LCEL | retrieve → prompt → llm → parse 链；`.with_retry` / `.with_fallbacks` |
| 06 Tool Calling | `agent/tools.py`（retrieve_kb / 计算 / web_search）+ `bind_tools` |
| 07 Agents | `web_agent` = `create_react_agent`；ReAct 循环 |
| 08 RAG | `ingest/` + `retrieval/`（hybrid + RRF + rerank）+ kb_rag 子图 |
| 09 LangGraph 核心 | `agent/graph.py`（State / Node / Edge / 条件边 / 循环）+ PostgresSaver |
| 10 LangGraph 进阶 | HITL `interrupt`、streaming、子图、CRAG / router 模式 |
| 11 生产化 | `obs/` 可观测、resilience、FastAPI、Docker、`langgraph.json` |
| 12 多 Agent | supervisor 顶层图 + 专家子图（kb_rag / web）+ handoff |

---

## 已知边界

- **live 端到端需 key**：`make serve` / `make eval` 需要 `LLM_*` / `EMBEDDING_*` 环境变量（任何 OpenAI 兼容端点均可，包括本地 vLLM / Ollama）。
- **ragas 需额外安装**：`uv sync --extra eval`（ragas 依赖较重，不进主安装；hermetic 测试不依赖它）。
- **中文全文检索需 pg_jieba**：当前用 Postgres 内置 `tsvector`（英文/默认分词），中文 FTS 需装 `pg_jieba`（MVP 范围外，README 注明扩展点）。
- **非 HA / 无 OIDC**：MVP 单实例、API key 头鉴权占位；真实企业部署需加 OIDC/JWT/RBAC + 多副本 + Grafana 面板。
