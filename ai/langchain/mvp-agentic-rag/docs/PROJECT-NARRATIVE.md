# 项目叙事 — Agentic RAG MVP

> 这份文档是面试口述的剧本骨架。三个版本对应不同场景:开场自我介绍(30 秒)、项目详述(2 分钟)、技术深挖(按需展开)。具体子系统的 Q&A 见 `docs/interview-qa/`。

---

## 一、30 秒版(开场一句话定位)

> "我做了一个**企业知识库 Agentic RAG 助手**的生产级参考项目。核心是 LangGraph supervisor 图 + CRAG 自纠正子图,检索层做了 hybrid(向量+全文) + RRF + rerank,答案强制带引用,全程可观测(Langfuse trace + Prometheus metrics),配套离线 eval 闭环和面试 Q&A 文档。目标是把 LangChain 12 章学习笔记落成一个能跑、能讲、能上线的东西。"

---

## 二、2 分钟版(STAR 结构)

### Situation — 问题背景

企业内部有大量 markdown/PDF 文档(技术手册、运营规范、产品 FAQ),员工用自然语言提问,直接问 GPT 的问题是:**答案没有依据、无法验证来源、出了幻觉也无从排查**。另一个痛点是可观测性缺失:一次坏答案发生了,不知道是检索没命中、还是模型编造、还是哪一步超时。

### Task — 要解决什么

需要一个**生产形态**的参考实现,覆盖从文档入库到答案生成的完整链路,且每一步可 trace、可 debug、可回归测试。同时这也是我备战 AI Engineer 面试的落地项目——不能只会讲概念,要能讲清楚每个取舍。

### Action — 做了什么

**检索层**:hybrid 双路(pgvector ANN + Postgres tsvector 全文) → RRF 融合 → cross-encoder rerank。两路互补,RRF 无需调权重,rerank 把 recall 和 precision 分离解决。全部复用同一个 Postgres,零额外基建。

**Agent 图**:LangGraph supervisor 顶层图,路由到 kb_rag CRAG 子图(retrieve→grade→[rewrite]→generate→grounding_check→[hedge])或 web_agent(create_react_agent ReAct 环)。CRAG 双轴自纠正:相关性 grade 过滤不相关召回,grounding_check LLM-as-judge 验证答案无幻觉,不接地则降级返回"依据不足"。PostgresSaver 持久化 checkpoint,支持 HITL interrupt/resume。

**API 层**:FastAPI /chat(同步)、/chat/stream(SSE token 级)、/threads(状态读取/时间旅行)、/threads/{id}/resume(HITL 恢复)。request_id 中间件串联 trace+日志,常数时间 API key 校验。

**可观测**:默认 Langfuse 自托管(MIT 开源,trace 数据不出内网);一个 env flag(`OBS_BACKEND=langsmith`)切 LangSmith;MonitoringCallback 推 Prometheus /metrics。坏答案拿 X-Request-ID → 开 Langfuse trace → 一眼定位到哪一步出错。

**Eval 闭环**:golden set(JSONL 进 git)+ 纯函数检查(must_include/route/citation/refusal)+ 回归 diff;CI 门用确定性 stub agent 断言 pass_rate≥90%。可选 ragas live 接入(faithfulness/answer_relevancy/context_precision/context_recall)。

### Result — 结果

75 个测试全绿(hermetic,无需真实 LLM/DB)。完整可观测链路接通。面试能流利讲清每个子系统的取舍。`docker compose up` 一键跑通。

---

## 三、深挖版(按子系统展开)

面试官问到哪个子系统,直接打开对应的 Q&A 文档:

| 子系统 | 文档 | 核心取舍 |
|---|---|---|
| 检索(hybrid+RRF+rerank) | [`interview-qa/01-retrieval.md`](interview-qa/01-retrieval.md) | 为什么不纯向量?RRF 怎么工作?rerank 解决什么?chunk 怎么调? |
| Agent 图(CRAG+supervisor+HITL) | [`interview-qa/02-agent-graph.md`](interview-qa/02-agent-graph.md) | supervisor vs swarm?CRAG 怎么防死循环?子图 state schema 桥接? |
| 可观测(Langfuse vs LangSmith) | [`interview-qa/03-observability.md`](interview-qa/03-observability.md) | 为什么选 Langfuse?trace vs metrics 各解决什么?request_id 怎么用? |
| Eval 闭环 | [`interview-qa/04-eval.md`](interview-qa/04-eval.md) | RAG eval vs agent 轨迹 eval?ragas 四指标?非确定性怎么测? |
| 韧性与生产 | [`interview-qa/05-resilience-production.md`](interview-qa/05-resilience-production.md) | fallback 为什么不接结构化组件?step_budget 防什么?部署怎么搞? |

更完整的排查流程见 [`debugging-playbook.md`](debugging-playbook.md)。

---

## 四、下一步会做什么(诚实的 follow-up)

这是 MVP,有明确的已知边界。如果继续做,优先级从高到低:

### 1. ragas live 接入

当前 ragas 是可选 extra(`uv sync --extra eval`),需要真实 LLM judge 才能跑,不进 hermetic 套件。下一步:在 CI 加 nightly/weekly 任务,用采样 golden 子集 + 真实 LLM 跑 ragas 四指标(faithfulness/answer_relevancy/context_precision/context_recall),结果推到 Langfuse 和 trace 并排看。

### 2. SSE 只推 generate 节点的 token

当前 `/chat/stream` 用 `graph.astream(stream_mode="messages")` 把所有节点的消息都推出去,包括 supervisor 路由结果、grade/grounding 的 token。面向用户的 SSE 流应该只推 generate 节点产出的 token,其他节点 token 在内部消化。需要用 `astream_events` 过滤 `on_chat_model_stream` 事件且 `metadata.langgraph_node == "generate"` 的 chunk。

### 3. 结构化组件 fallback 补全

当前 `LLMRouter`/`LLMDocGrader`/`LLMGroundingChecker` 这三个结构化输出组件没有 fallback 保护(见 ARCHITECTURE.md 决策⑧)。正确做法是 `chat.with_structured_output(Schema).with_fallbacks([chat_fb.with_structured_output(Schema)])`,两侧都做结构化。这样主模型宕机时路由/评分/接地也能优雅降级到备用模型。

### 4. OIDC/JWT 鉴权

当前 MVP 用 `app_api_key`(常数时间比对),是占位方案。生产场景需要 OIDC(与企业 IdP 集成)或 JWT(带 scope + 过期时间)。FastAPI 的 `OAuth2PasswordBearer` 或 `fastapi-security` 是自然的扩展点。

### 5. HA/多副本部署

当前单副本。水平扩展依赖 PostgresSaver(checkpoint 跨实例共享)和 stateless API 层,架构上已就绪。需要在 docker-compose 或 k8s Deployment 上配置 replica + load balancer,并给 Postgres 加连接池上限(pgbouncer 或 asyncpg pool_size)。

### 6. Grafana 面板

当前 `/metrics` 暴露 Prometheus counter+histogram 但没有面板。下一步用 `docker compose --profile grafana up` 起 Grafana,导入预建 dashboard:RAG 请求量/成功率、token 用量/成本、检索延迟分布、工具错误率、HITL 积压量。

### 7. 中文全文检索(pg_jieba)

当前 `fts_config=simple`(空格分词,适合英文)。中文文档需要分词插件 pg_jieba(jieba 中文分词的 Postgres extension)或 zhparser。安装后把 `fts_config` 改为 `zhparser` 或 `jieba_cfg`。不装插件时中文全文召回几乎为零,退化成纯向量检索。
