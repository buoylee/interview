# agent-loop-lab:不用框架手写 agent

一个周末实验:裸 OpenAI SDK 手写 agent loop + 自写 MCP server/client 两端 + OTel 手动埋点(GenAI 语义约定),trace 进自托管 Langfuse。复刻 MVP(`../langchain/mvp-agentic-rag`)kb 问答的薄切片,用于「裸写 vs 框架」对照。

---

## 跑起来

```bash
# 1. 安装依赖(含 dev)
uv sync --extra dev

# 2. 运行测试(不需要 LLM key,全 hermetic)
uv run pytest

# 3. 真实运行(需要 LLM key)
cp .env.example .env
# 填写 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
# 可选:填写 LANGFUSE_HOST / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY

uv run python -m agent_loop.main "pgvector 的索引类型有哪些?"
```

输出示例:

```
pgvector 支持 ivfflat 和 hnsw 两种索引……(来源:postgres.md)

--- turns=2 tools=['search_docs', 'read_doc'] tokens=312+87 latency=2.41s
```

---

## 看什么

| 文件 | 内容 |
|------|------|
| `src/agent_loop/loop.py` | agent 循环本体(112 行,面试可背骨架):显式 while + messages list + OTel 三层 span |
| `src/agent_loop/mcp_server.py` | MCP server 端:FastMCP 注册 `read_doc` 工具,读 `sample_docs/` |
| `src/agent_loop/mcp_client.py` | MCP client 端:每次 `call_mcp_tool` spawn 子进程 + `initialize` 握手(实测冷启动约 0.2–0.3 s,波动明显) |
| `src/agent_loop/tools.py` | `ToolSpec` 结构体 + `search_docs`(关键词打分,< 0.5 ms 进程内) |
| `src/agent_loop/otel.py` | OTel 初始化:控制台 / OTLP 两端;GenAI 语义约定 span 属性 |
| `src/agent_loop/config.py` | pydantic-settings 配置 + Langfuse OTLP endpoint 拼装 |
| `notes/01-loop-vs-langgraph.md` | 与 LangGraph 版逐维度对照 + 实测数字 + 面试一句话答案 |
| `notes/run-log.md` | 真实运行记录(待 Task 8 填写) |

---

## 测试

```bash
uv run pytest
```

18 条,全 hermetic:假 LLM 客户端(`FakeOpenAI`) + `InMemorySpanExporter` + 真 stdio MCP 子进程(测 MCP 两端握手)。不需要任何 API key。

---

## 与 MVP 的关系

本 lab 只复刻 MVP 的「知识库问答」薄切片,刻意省去:

- CRAG 自纠正(grade + rewrite + grounding_check)
- supervisor 多路由(web agent / HITL)
- PostgresSaver checkpoint(进程死=状态丢)
- Fallback 降级链(`core/resilience.py`)

详细对照见 `notes/01-loop-vs-langgraph.md`。
