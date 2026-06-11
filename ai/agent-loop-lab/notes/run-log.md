# run-log — 真实运行记录

> 状态:待填。API key 就绪后执行 Task 8,用下面的命令采集数字后回填各表格。

---

## 运行记录表

| 问题 | turns | 工具序列 | input tokens | output tokens | 裸 loop 延迟 | 对照 MVP 延迟 |
|------|:---:|---------|:---:|:---:|:---:|:---:|
| pgvector 的索引类型有哪些? | 〔待实测〕 | 〔待实测,如 search_docs → read_doc〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 |
| k8s liveness/readiness 探针有什么区别? | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 |
| 深圳明天天气怎么样?(域外) | 〔待实测〕 | 〔待实测,预期无工具调用〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 | 〔待实测〕 |

---

## 如何采集

### 1. 配置环境

```bash
cp .env.example .env
# 填写:
# LLM_BASE_URL=https://api.openai.com/v1
# LLM_API_KEY=sk-...
# LLM_MODEL=gpt-4o-mini
# LANGFUSE_HOST=http://localhost:3000  (可选,有自托管 Langfuse 时填)
# LANGFUSE_PUBLIC_KEY=pk-...
# LANGFUSE_SECRET_KEY=sk-...
```

### 2. 运行三个问题

```bash
uv run python -m agent_loop.main "pgvector 的索引类型有哪些?"

uv run python -m agent_loop.main "k8s liveness/readiness 探针有什么区别?"

uv run python -m agent_loop.main "深圳明天天气怎么样?"
```

### 3. 从哪里读数字

每次运行结尾输出格式:

```
--- turns=X tools=['search_docs', 'read_doc'] tokens=XXX+YYY latency=Z.ZZs
```

- **turns**: `turns=X` 字段
- **工具序列**: `tools=[...]` 字段(按调用顺序)
- **input tokens**: `tokens=X+Y` 中的 X
- **output tokens**: `tokens=X+Y` 中的 Y
- **裸 loop 延迟**: `latency=Z.ZZs` 字段

### 4. MVP 对照延迟

运行 MVP 的相同问题(见 `../langchain/mvp-agentic-rag/README.md`):

```bash
cd ../langchain/mvp-agentic-rag
# 启动服务后:
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-secret" \
  -d '{"message": "pgvector 的索引类型有哪些?", "thread_id": "t-bench-1"}' | jq
```

MVP 延迟从 Langfuse UI 的 trace total duration 读取(或 curl 响应时间)。

---

## 备注

- 域外问题(深圳天气)裸 loop 应直接回答「不知道」(system prompt 约束),不调工具,turns=1
- MVP 遇到域外问题会路由到 `web_agent`(ReAct 环),如无 web 搜索 key 则 hedge
- Langfuse trace 里每个 span 的 duration 可拆解各节点延迟(路由/grade/grounding 各约 500ms)
