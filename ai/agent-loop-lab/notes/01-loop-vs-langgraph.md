# 同一个功能:裸 loop vs LangGraph(MVP)

> 左边 ~112 行 `loop.py`,右边 MVP 的 supervisor+CRAG 图(graph.py 46 行 + supervisor.py 15 行 + state.py 21 行 + components.py 114 行 + kb_rag.py 62 行 = 258 行)。两边跑同一批问题、同一份语料(sample_docs)、同一个 Langfuse。

---

## 1. 各维度对照

| 维度 | 裸 loop(本 lab) | LangGraph(MVP) |
|------|------------------|------------------|
| 循环本体 | 显式 `while` + `messages` list(`loop.py:run_agent`) | 图边定义,引擎驱动(`agent/graph.py:build_agent_graph`) |
| 状态 | 函数内局部变量,进程死=状态丢 | `AgentState` + `PostgresSaver` checkpoint,可跨进程恢复 |
| 防死循环 | `max_turns` 手写(`loop.py` 第 50 行 `for turn in range`) | `step_budget` 计数(`supervisor.py`) |
| 工具错误恢复 | 手写 `try/except` 回喂 `ERROR` 前缀字符串(`loop.py` 第 105–107 行) | 同思路,框架不替你做(`components.py` 各 LLM 组件自行处理异常) |
| HITL | 没有,要自己造 | `interrupt()` + `Command(resume=...)` 一等公民(`agent/human_review.py`) |
| 流式 | 要自己改 `create(stream=True)` 再透传 | `graph.astream(stream_mode="messages")` 现成(API 层 `/chat/stream` SSE) |
| 可观测 | OTel 手动埋 3 类 span(GenAI 语义约定:`invoke_agent` / `chat` / `execute_tool`) | Langfuse `CallbackHandler` 自动全埋,`MonitoringCallback` 推 Prometheus |
| 代码量(本功能切片) | 112 行(`loop.py`) | 258 行(graph.py 46 + supervisor.py 15 + state.py 21 + components.py 114 + kb_rag.py 62) |
| 自纠正(CRAG) | 无——单次检索,不做相关性评分或接地性检验 | `kb_rag.py` 双轴:grade(相关性)→ 可选 rewrite → generate → grounding_check → 可选 hedge |
| 查询改写 | 无 | `LLMQueryRewriter`(`components.py`)——相关性不足时改写后再检索 |
| Fallback 降级 | 无 | `core/resilience.py:get_chat_model_with_fallback` — 主模型超时自动切备用 |
| 多路由专家 | 无(只有 kb 问答) | supervisor LLM 路由:kb_rag / web / human_review / FINISH |

---

## 2. 真实数字对照(同问题)

### 2a. 工具调用开销(离线实测)

| 指标 | 实测值 | 备注 |
|------|--------|------|
| MCP `call_mcp_tool` 冷启动 | 约 0.2–0.3 s(波动明显) | 每次调用都 `spawn` 新子进程 + `initialize` 握手;生产应长连接复用 session。一次采样示例:0.202 s / 0.209 s / 0.225 s |
| `search_docs` 进程内(3 次) | 0.0002 s / 0.0001 s / 0.0001 s | 纯 Python 关键词打分,无 I/O;< 0.5 ms |

裸 loop 的代价:每次 `read_doc` 多付 约 0.2–0.3 s 的子进程冷启动(波动明显)。如果一轮对话触发 2 次 `read_doc`,仅 MCP 启动就消耗 ~0.4–0.6 s,与 LLM 调用延迟同量级。

### 2b. 同问题端到端对照(待 LLM key)

| 问题 | 裸 loop turns | 裸 loop tokens | 裸 loop 延迟 | MVP 延迟 |
|------|:---:|:---:|:---:|:---:|
| pgvector 的索引类型有哪些? | 〔待实测:跑 Task 8 后填〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测:跑 Task 1 后填〕 |
| k8s liveness/readiness 探针有什么区别? | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 |
| 深圳明天天气怎么样?(域外问题) | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 |

### 2c. MVP 比裸 loop 多哪些 LLM 调用

每次成功的 kb 问答,MVP 在裸 loop 的「一次 LLM 生成」之上额外发起:

| 额外调用 | 来源 | 大约延迟 |
|---------|------|---------|
| 路由决策(`LLMRouter.route`) | `components.py:LLMRouter` + `supervisor.py` | 〔待实测,约 500 ms〕 |
| 文档相关性评分(`LLMDocGrader.grade`) | `components.py:LLMDocGrader` → `kb_rag.py:grade` 节点 | 〔待实测,约 500 ms〕 |
| 接地性检验(`LLMGroundingChecker.check`) | `components.py:LLMGroundingChecker` → `kb_rag.py:grounding_check` 节点 | 〔待实测,约 500 ms〕 |
| 查询改写(`LLMQueryRewriter.rewrite`,触发时) | `components.py:LLMQueryRewriter` → `kb_rag.py:rewrite` 节点,`relevant=False` 且 `rewrites<1` 时触发 | 〔待实测〕 |
| 二次路由(kb_rag 结束后再判 FINISH) | `supervisor` 节点被 `kb_rag → supervisor` 边触发一次 | 〔待实测〕 |

结论:MVP 最少多 3 次 LLM 调用(路由 + grade + grounding),触发改写时多 4–5 次。延迟代价是框架换来可靠性的直接成本。

---

## 3. 结论:什么时候选哪个(面试答案)

**选裸 loop:**
- 单轮/短会话、无人工审批、状态可丢(`loop.py` 一屏读完,调试 = 打印 `messages`)
- 要极致控制 context 组装与 token 预算(每个 `messages.append` 都是显式的)
- 依赖面要求最小——只需 `openai` SDK,无框架 lock-in
- 学习目的:彻底看懂 agent 的本质机制再选框架

**选框架:**
- 会话要跨进程恢复(`PostgresSaver` checkpoint 不值得手搓)
- 要 HITL 审批中断(`interrupt()` + `Command(resume=...)` 是 LangGraph 一等公民,裸写需大量脚手架)
- 要 token 级流式且多节点(`graph.astream(stream_mode="messages")` 现成)
- 图复杂到画出来才说得清(supervisor + CRAG 循环 + web fallback)
- 需要 CRAG 双轴自纠正:grade 过滤幻觉、grounding_check 验接地性

**一句话版:**
> 「agent 本质是循环 + 工具 + context 管理,我两种都写过;框架买的是 checkpoint、HITL、流式这些生产能力,不是循环本身。」

---

## 4. 本 lab 的刻意简化(被追问时主动交代)

| 简化点 | 详情 |
|--------|------|
| MCP 冷启动 | 每次调用 `call_mcp_tool` 都 spawn 新子进程 + `initialize` 握手,实测约 0.2–0.3 s(波动明显,一次采样示例:202 ms / 209 ms / 225 ms);生产应长连接复用 session(`async with ClientSession` 持久化) |
| 关键词检索 | `search_docs` 是 TF-IDF 风格关键词打分(< 0.5 ms),不是向量检索;MVP 用 pgvector HNSW dense + tsvector sparse + RRF 融合 + cross-encoder rerank |
| 无重试/退避 | 工具失败直接回喂 `ERROR` 前缀;MVP 的 `core/resilience.py` 提供主模型+fallback 降级链(`primary.with_fallbacks([fallback])`) |
| 无 budget 控制 | 只有 `max_turns` 上限;MVP 有 `step_budget` 字段计数(`supervisor.py`) |
| `isError` 拍平 | MCP 的 `isError=True` 标志被统一拍平为 `"ERROR"` 前缀字符串约定(`mcp_client.py` 注释有说明) |
| 无 CRAG | 单次检索,不评分相关性,不检验接地性,不改写查询;遇到语料外问题靠 system prompt 约束模型说「不知道」 |
| 无流式 | `client.chat.completions.create` 同步阻塞;改流式需换 `stream=True` + `for chunk in response` |

---

## 5. 待实测清单(跑通 Task 1/8 后回填)

| 条目 | 获取方法 |
|------|---------|
| 裸 loop turns(3 个问题) | `uv run python -m agent_loop.main "..."` 输出的 `--- turns=X` |
| 裸 loop tokens(input+output) | 同上 `tokens=X+Y` |
| 裸 loop 端到端延迟 | 同上 `latency=Z.ZZs` |
| 路由 LLM 调用延迟 | Langfuse UI → 该 trace → supervisor 节点 span duration |
| grade LLM 调用延迟 | Langfuse UI → kb_rag 子图 → grade 节点 span duration |
| grounding_check LLM 调用延迟 | Langfuse UI → kb_rag 子图 → grounding_check 节点 span duration |
| MVP 端到端延迟 | `POST /chat` 响应时间 / Langfuse trace total duration |
| MVP tokens(各节点) | Langfuse UI → token usage per span |
