# 月 1:MVP 首次真实跑通 + 裸循环 Agent 实验(agent-loop-lab)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 第一次用真实 key 跑通 MVP 拿到第一批真实数字(runlog),并手写一个不依赖任何框架的 agent loop(裸 OpenAI SDK + MCP 工具 + OTel 手动 span,trace 进自托管 Langfuse),最后把「裸 loop vs LangGraph」对比和真实数字回填到 02 模块文档。

**Architecture:** lab 是独立 uv 小项目 `ai/agent-loop-lab/`,复用 MVP 的 `LLM_*`/`LANGFUSE_*` env 约定和 `sample_docs` 语料。agent loop 是一个纯函数 `run_agent(client, model, tools, user_input, tracer)`——LLM 客户端、工具表、tracer 全部注入,测试用 FakeChatClient + InMemorySpanExporter 全 hermetic。两个工具复刻 MVP kb 路由的薄切片:`search_docs`(进程内关键词检索)+ `read_doc`(走 MCP stdio,自己写 server 和 client 两端)。OTel span 遵循 GenAI 语义约定(`gen_ai.*`),OTLP HTTP 导出到 Langfuse。

**Tech Stack:** Python 3.11+ / uv;`openai`(裸 SDK)、`mcp`(FastMCP server + stdio client)、`opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`、`python-dotenv`、`pytest`。

---

## 上位文档

- 设计 spec:`docs/superpowers/specs/2026-06-11-ml-to-llm-roadmap-practical-content-design.md`(决策 2 裸循环实验、决策 4 回填规则、第九节排期重排)
- 对照对象:MVP `ai/langchain/mvp-agentic-rag/`(Plan 1-4 代码已全部合入 main,但从未真实运行)
- 回填目标:`ai/ml-to-llm-roadmap/02-agent-tool-use/01-agent-boundary-and-loop.md`

## 前置条件(Task 1 开始前用户需准备)

- `ai/langchain/mvp-agentic-rag/.env`:`LLM_*` 与 `EMBEDDING_*` 填真实 OpenAI 兼容 key(参考 `.env.example`)。
- Docker 可用;自托管 Langfuse 见 Task 1 Step 1(首次需注册并建项目拿 pk/sk)。
- 无 key 时:Task 2-7 照常可做(全 hermetic);Task 1、8 阻塞(Task 9 的数字部分、Task 10 依赖 8),顺延即可。

## 文件结构(本计划产出 / 修改)

```
ai/agent-loop-lab/                        (全新)
├─ pyproject.toml
├─ .env.example
├─ README.md                              (Task 9)
├─ src/agent_loop/
│  ├─ __init__.py
│  ├─ config.py                           (env 加载 + Langfuse OTLP 拼装)
│  ├─ otel.py                             (tracer 初始化,exporter 可注入)
│  ├─ tools.py                            (ToolSpec + search_docs 本地工具)
│  ├─ mcp_server.py                       (FastMCP:read_doc 工具)
│  ├─ mcp_client.py                       (stdio 客户端同步封装 + READ_DOC ToolSpec)
│  ├─ loop.py                             (核心:run_agent 裸循环)
│  └─ main.py                             (CLI 入口)
├─ notes/
│  ├─ run-log.md                          (Task 8:真实运行数字)
│  └─ 01-loop-vs-langgraph.md             (Task 9:对比笔记)
└─ tests/
   ├─ conftest.py                         (tracing fixture)
   ├─ fakes.py                            (FakeChatClient)
   ├─ test_config.py
   ├─ test_tools.py
   ├─ test_mcp.py
   └─ test_loop.py

ai/langchain/mvp-agentic-rag/docs/
└─ runlog-2026-06-first-real-run.md       (Task 1:MVP 首跑记录)

ai/ml-to-llm-roadmap/02-agent-tool-use/
└─ 01-agent-boundary-and-loop.md          (Task 10:追加「实战锚点」节)
```

---

### Task 1: MVP 首次真实跑通 + runlog

**Files:**
- Create: `ai/langchain/mvp-agentic-rag/docs/runlog-2026-06-first-real-run.md`

这是运行性任务,不写新代码。目的:验证 Plan 1-4 的代码真的端到端能跑,并拿到第一批可背的真实数字。

- [ ] **Step 1: 起自托管 Langfuse(一次性)**

```bash
git clone https://github.com/langfuse/langfuse.git ~/langfuse-selfhost
cd ~/langfuse-selfhost && docker compose up -d
```

浏览器开 `http://localhost:3000` → 注册账号 → 新建 Organization/Project → Settings 里拿 `pk-lf-...` / `sk-lf-...`,填进 MVP 的 `.env`(`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST=http://localhost:3000`)。
Expected: `docker compose ps` 全部服务 healthy;UI 能登录。

- [ ] **Step 2: 起 MVP 全链路**

```bash
cd /Users/buoy/Development/gitrepo/interview/ai/langchain/mvp-agentic-rag
make install && make up && make db-init && make ingest
make serve
```

Expected: `make ingest` 输出入库 chunk 数(记下来);`curl -s http://localhost:8000/readyz` 返回 200。

- [ ] **Step 3: 真实问答 + 计时**

```bash
time curl -s http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "pgvector 的索引类型有哪些?各自什么取舍?", "thread_id": "runlog-1"}' | python3 -m json.tool
```

(若 `.env` 设了 `APP_API_KEY`,加 `-H "X-API-Key: $APP_API_KEY"`。)
Expected: 返回 `{response, citations, request_id}`,`citations` 非空且指向 `postgres.md`。再问一个知识库外的问题(如「今天深圳天气」)验证 supervisor 路由到 web 分支或明确拒答。各记录 `time` 的总耗时。

- [ ] **Step 4: Langfuse 看 trace 树**

UI 里找到刚才两条请求的 trace,确认能看到:supervisor 路由 → 检索命中 chunks → (rerank) → 生成 → grounding 检查,每步有 token/latency。截图存 `ai/langchain/mvp-agentic-rag/docs/img/`(目录不存在就创建)。

- [ ] **Step 5: 写 runlog 并提交**

创建 `docs/runlog-2026-06-first-real-run.md`,如实填(数字全部来自上面真实运行,不许估):

```markdown
# MVP 首次真实运行记录(2026-06)

| 项 | 值 |
|----|----|
| 日期 / 模型 | <date> / <LLM_MODEL> |
| ingest 入库 chunk 数 | <n> |
| kb 问题端到端延迟 | <x.x s> |
| kb 问题 token(prompt/completion,从 Langfuse trace 读) | <n / n> |
| 单次 kb 问答成本估算(按模型牌价) | <$x.xxxx> |
| citations 数量与命中文件 | <n, postgres.md> |
| 非 kb 问题的路由行为 | <web / 拒答,延迟> |
| trace 树截图 | docs/img/<file>.png |

## 跑通过程中遇到的问题(原样记录,这就是排查素材)
- <症状 → 定位 → 修复;没有就写"无">
```

```bash
git add docs/runlog-2026-06-first-real-run.md docs/img/
git commit -m "mvp-agentic-rag: 首次真实运行 runlog(端到端延迟/token/成本基线)"
```

---

### Task 2: agent-loop-lab 骨架

**Files:**
- Create: `ai/agent-loop-lab/pyproject.toml`
- Create: `ai/agent-loop-lab/.env.example`
- Create: `ai/agent-loop-lab/src/agent_loop/__init__.py`(空文件)
- Create: `ai/agent-loop-lab/tests/__init__.py`(空文件)

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "agent-loop-lab"
version = "0.1.0"
description = "裸循环 agent 实验:不用框架手写 agent loop + MCP 工具 + OTel 手动埋点"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.40",
    "mcp>=1.0",
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp-proto-http>=1.27",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_loop"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: 写 .env.example(与 MVP 同名约定,可直接复制 MVP 的值)**

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-replace-me
LLM_MODEL=gpt-4o-mini

# 留空 = trace 打到控制台;填了 = OTLP 导出到 Langfuse
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

- [ ] **Step 3: 安装依赖,验证可导入**

```bash
cd /Users/buoy/Development/gitrepo/interview/ai/agent-loop-lab
uv sync --extra dev
uv run python -c "import agent_loop; import mcp; import opentelemetry; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example src/ tests/ uv.lock
git commit -m "agent-loop-lab: 项目骨架(uv + openai/mcp/otel 依赖)"
```

---

### Task 3: config.py(env 加载 + Langfuse OTLP 拼装)

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/config.py`
- Test: `ai/agent-loop-lab/tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
import base64

from agent_loop.config import Settings, langfuse_otlp_config


def _settings(**overrides):
    base = dict(
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="sk-x",
        llm_model="gpt-4o-mini",
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-2",
    )
    base.update(overrides)
    return Settings(**base)


def test_otlp_config_builds_langfuse_endpoint_and_basic_auth():
    endpoint, headers = langfuse_otlp_config(_settings())
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected_auth = base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    assert headers["Authorization"] == f"Basic {expected_auth}"
    assert headers["x-langfuse-ingestion-version"] == "4"


def test_otlp_config_none_when_keys_missing():
    assert langfuse_otlp_config(_settings(langfuse_public_key="")) is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/test_config.py -v
```

Expected: FAIL(`ModuleNotFoundError: agent_loop.config`)

- [ ] **Step 3: 实现 config.py**

```python
# src/agent_loop/config.py
"""env 配置。与 MVP(ai/langchain/mvp-agentic-rag)共用 LLM_*/LANGFUSE_* 命名约定。"""
import base64
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    langfuse_host: str
    langfuse_public_key: str
    langfuse_secret_key: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        langfuse_host=os.environ.get("LANGFUSE_HOST", ""),
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    )


def langfuse_otlp_config(settings: Settings) -> tuple[str, dict[str, str]] | None:
    """Langfuse 收 OTLP 的端点是 {host}/api/public/otel,traces 信号全路径再加 /v1/traces。

    返回 None 表示未配置 Langfuse(调用方应回退到控制台 exporter)。
    """
    if not (settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    endpoint = settings.langfuse_host.rstrip("/") + "/api/public/otel/v1/traces"
    headers = {
        "Authorization": f"Basic {auth}",
        "x-langfuse-ingestion-version": "4",
    }
    return endpoint, headers
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_loop/config.py tests/test_config.py
git commit -m "agent-loop-lab: env 配置 + Langfuse OTLP 端点拼装"
```

---

### Task 4: tools.py(ToolSpec + 本地工具 search_docs)

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/tools.py`
- Test: `ai/agent-loop-lab/tests/test_tools.py`

`search_docs` 是 MVP「kb 检索路由」的薄切片复刻:不用向量库,纯关键词给段落打分。语料直接指向 MVP 的 `sample_docs/`(kubernetes.md、postgres.md),保证两边回答同样的问题、可对比。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools.py
from pathlib import Path

import agent_loop.tools as tools
from agent_loop.tools import SEARCH_DOCS, ToolSpec, search_docs


def test_toolspec_to_openai_format():
    spec = ToolSpec(name="t", description="d", parameters={"type": "object"}, handler=lambda: "x")
    assert spec.to_openai() == {
        "type": "function",
        "function": {"name": "t", "description": "d", "parameters": {"type": "object"}},
    }


def test_search_docs_returns_matching_paragraph(tmp_path: Path, monkeypatch):
    (tmp_path / "a.md").write_text("第一段讲 docker。\n\n这一段讲 pgvector 索引,有 hnsw 和 ivfflat。", encoding="utf-8")
    (tmp_path / "b.md").write_text("无关内容。", encoding="utf-8")
    monkeypatch.setattr(tools, "DOCS_DIR", tmp_path)
    out = search_docs("pgvector hnsw")
    assert "[a.md]" in out and "ivfflat" in out
    assert "无关内容" not in out


def test_search_docs_no_match(tmp_path: Path, monkeypatch):
    (tmp_path / "a.md").write_text("完全无关。", encoding="utf-8")
    monkeypatch.setattr(tools, "DOCS_DIR", tmp_path)
    assert search_docs("量子纠缠").startswith("NO_MATCH")


def test_search_docs_default_dir_points_at_mvp_sample_docs():
    assert (tools.DOCS_DIR / "postgres.md").exists()
    assert SEARCH_DOCS.name == "search_docs"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: FAIL(`ModuleNotFoundError: agent_loop.tools`)

- [ ] **Step 3: 实现 tools.py**

```python
# src/agent_loop/tools.py
"""工具定义。ToolSpec 是「工具 = JSON Schema + 本地函数」的最小表达——
框架里的 @tool 装饰器底下就是这点东西。"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# 复用 MVP 的语料,保证 lab 和 LangGraph 版回答同样的问题可对比
DOCS_DIR = Path(
    os.environ.get(
        "LAB_DOCS_DIR",
        Path(__file__).resolve().parents[3] / "langchain" / "mvp-agentic-rag" / "sample_docs",
    )
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., str]

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def search_docs(query: str, top_k: int = 3) -> str:
    """按关键词给段落打分,返回得分最高的 top_k 段。MVP hybrid 检索的极简对照物。"""
    keywords = [w.lower() for w in query.split() if len(w) > 1]
    scored: list[tuple[int, str]] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        for para in path.read_text(encoding="utf-8").split("\n\n"):
            text = para.lower()
            score = sum(text.count(k) for k in keywords)
            if score > 0:
                scored.append((score, f"[{path.name}] {para.strip()}"))
    if not scored:
        return "NO_MATCH: 知识库中没有相关内容"
    scored.sort(key=lambda item: -item[0])
    return "\n\n".join(snippet for _, snippet in scored[:top_k])


SEARCH_DOCS = ToolSpec(
    name="search_docs",
    description="在本地知识库(markdown)中按关键词检索,返回最相关段落(带 [文件名] 前缀)。查不到返回 NO_MATCH。",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "检索关键词,空格分隔"}},
        "required": ["query"],
    },
    handler=search_docs,
)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
uv run pytest tests/test_tools.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_loop/tools.py tests/test_tools.py
git commit -m "agent-loop-lab: ToolSpec + search_docs 本地检索工具"
```

---

### Task 5: MCP server + 客户端工具(read_doc)

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/mcp_server.py`
- Create: `ai/agent-loop-lab/src/agent_loop/mcp_client.py`
- Test: `ai/agent-loop-lab/tests/test_mcp.py`

自己写 MCP 的两端(server 用 FastMCP,client 用 stdio),比接现成 server 学得透:能亲口讲「MCP = 工具的 JSON-RPC 进程间协议,initialize → list_tools → call_tool」。

- [ ] **Step 1: 写失败测试(真 stdio 子进程,本地 hermetic)**

```python
# tests/test_mcp.py
from agent_loop.mcp_client import READ_DOC, call_mcp_tool


def test_read_doc_via_mcp_returns_file_content():
    out = call_mcp_tool("read_doc", {"filename": "postgres.md"})
    assert "postgres" in out.lower()


def test_read_doc_rejects_path_traversal():
    out = call_mcp_tool("read_doc", {"filename": "../pyproject.toml"})
    assert out.startswith("ERROR")


def test_read_doc_missing_file_lists_available():
    out = call_mcp_tool("read_doc", {"filename": "nope.md"})
    assert out.startswith("ERROR") and "postgres.md" in out


def test_read_doc_toolspec():
    assert READ_DOC.name == "read_doc"
    assert READ_DOC.parameters["required"] == ["filename"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
uv run pytest tests/test_mcp.py -v
```

Expected: FAIL(`ModuleNotFoundError: agent_loop.mcp_client`)

- [ ] **Step 3: 实现 mcp_server.py**

```python
# src/agent_loop/mcp_server.py
"""最小 MCP server:暴露一个 read_doc 工具。`python -m agent_loop.mcp_server` 以 stdio 运行。"""
from mcp.server.fastmcp import FastMCP

from agent_loop.tools import DOCS_DIR

mcp = FastMCP("doc-reader")


@mcp.tool()
def read_doc(filename: str) -> str:
    """读取知识库中指定 markdown 文件的完整内容。"""
    base = DOCS_DIR.resolve()
    path = (base / filename).resolve()
    if path.parent != base or path.suffix != ".md":
        return "ERROR: 只允许读取知识库目录下的 .md 文件"
    if not path.exists():
        available = ", ".join(sorted(p.name for p in base.glob("*.md")))
        return f"ERROR: 文件不存在。可用文件: {available}"
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()  # 默认 stdio transport
```

- [ ] **Step 4: 实现 mcp_client.py**

```python
# src/agent_loop/mcp_client.py
"""MCP stdio 客户端的同步封装。

为简单起见每次调用都重新拉起 server 子进程并走 initialize 握手——
生产实现会保持长连接复用 session(这是 lab 的刻意取舍,对比笔记里要提)。
"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_loop.tools import ToolSpec

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable, args=["-m", "agent_loop.mcp_server"]
)


def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    async def _call() -> str:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return "\n".join(
                    block.text for block in result.content if getattr(block, "text", None)
                )

    return asyncio.run(_call())


READ_DOC = ToolSpec(
    name="read_doc",
    description="通过 MCP 读取知识库指定 .md 文件全文。先用 search_docs 定位文件名,需要完整上下文时再用本工具。",
    parameters={
        "type": "object",
        "properties": {"filename": {"type": "string", "description": "如 postgres.md"}},
        "required": ["filename"],
    },
    handler=lambda filename: call_mcp_tool("read_doc", {"filename": filename}),
)
```

- [ ] **Step 5: 跑测试确认通过**

```bash
uv run pytest tests/test_mcp.py -v
```

Expected: 4 passed(每条测试拉起一次 stdio 子进程,稍慢属正常)

- [ ] **Step 6: Commit**

```bash
git add src/agent_loop/mcp_server.py src/agent_loop/mcp_client.py tests/test_mcp.py
git commit -m "agent-loop-lab: 手写 MCP server(FastMCP)+ stdio 客户端工具 read_doc"
```

---

### Task 6: otel.py(tracer 初始化,exporter 可注入)

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/otel.py`
- Create: `ai/agent-loop-lab/tests/conftest.py`

不设全局 TracerProvider(`trace.set_tracer_provider` 一个进程只能设一次,妨碍测试),tracer 显式传给 `run_agent`。

- [ ] **Step 1: 写 conftest.py 的 tracing fixture(loop 测试也要用)**

```python
# tests/conftest.py
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture()
def tracing():
    """返回 (tracer, exporter):span 进内存,测试里直接断言。"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("test"), exporter
```

- [ ] **Step 2: 实现 otel.py**

```python
# src/agent_loop/otel.py
"""OTel tracing 初始化。配置了 Langfuse 就 OTLP 导出,否则打到控制台。"""
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from agent_loop.config import Settings, langfuse_otlp_config


def init_tracing(settings: Settings, exporter=None):
    """返回 (tracer, provider)。调用方退出前必须 provider.shutdown() 刷掉 batch 缓冲。"""
    if exporter is None:
        otlp = langfuse_otlp_config(settings)
        if otlp is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint, headers = otlp
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        else:
            exporter = ConsoleSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "agent-loop-lab"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider.get_tracer("agent_loop"), provider
```

- [ ] **Step 3: 快速验证(无独立测试文件,Task 7 的 span 断言会覆盖它)**

```bash
uv run python -c "
from agent_loop.config import Settings
from agent_loop.otel import init_tracing
s = Settings('u','k','m','','','')
tracer, provider = init_tracing(s)
with tracer.start_as_current_span('smoke'):
    pass
provider.shutdown()
print('otel ok')
"
```

Expected: 控制台打出一段 span JSON + `otel ok`

- [ ] **Step 4: Commit**

```bash
git add src/agent_loop/otel.py tests/conftest.py
git commit -m "agent-loop-lab: OTel tracer 初始化(OTLP→Langfuse / 控制台回退)"
```

---

### Task 7: loop.py(核心:裸 agent 循环 + GenAI 语义约定 span)

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/loop.py`
- Create: `ai/agent-loop-lab/tests/fakes.py`
- Test: `ai/agent-loop-lab/tests/test_loop.py`

这就是「agent = while 循环」的本体。面试可背的循环骨架:**发消息+工具表 → 模型要么给 tool_calls 要么给最终答案 → 执行工具、结果以 role=tool 回填 → 再调模型,直到没有 tool_calls 或到 max_turns**。

- [ ] **Step 1: 写 fakes.py(脚本化假 LLM 客户端,镜像 openai SDK 的响应结构)**

```python
# tests/fakes.py
import json
from types import SimpleNamespace


def _usage(prompt=10, completion=5):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def tool_call_response(name: str, arguments: dict, call_id: str = "call_1"):
    tc = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )
    msg = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage())


def final_response(text: str):
    msg = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage())


class FakeChatClient:
    """按脚本依次吐响应;记录每次收到的 kwargs 供断言。鸭子类型兼容 openai.OpenAI。"""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._scripted.pop(0)
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_loop.py
import pytest

from agent_loop.loop import MaxTurnsExceeded, run_agent
from agent_loop.tools import ToolSpec
from tests.fakes import FakeChatClient, final_response, tool_call_response

ECHO = ToolSpec(
    name="echo",
    description="原样返回 text",
    parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    handler=lambda text: f"echo:{text}",
)

BOOM = ToolSpec(
    name="boom",
    description="总是抛异常",
    parameters={"type": "object", "properties": {}},
    handler=lambda: (_ for _ in ()).throw(RuntimeError("炸了")),
)


def test_tool_call_then_final_answer(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "hi"}), final_response("done")])
    result = run_agent(client, "m", [ECHO], "问题", tracer)
    assert result.final_text == "done"
    assert result.turns == 2
    assert result.tool_calls == ["echo"]
    # 工具结果以 role=tool 回填进了第二次请求
    second_messages = client.calls[1]["messages"]
    assert {"role": "tool", "tool_call_id": "call_1", "content": "echo:hi"} in second_messages


def test_tool_exception_fed_back_as_error_message(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("boom", {}), final_response("recovered")])
    result = run_agent(client, "m", [BOOM], "问题", tracer)
    assert result.final_text == "recovered"
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert tool_msg["content"].startswith("ERROR")


def test_unknown_tool_fed_back_as_error(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("ghost", {}), final_response("ok")])
    result = run_agent(client, "m", [ECHO], "问题", tracer)
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "未知工具" in tool_msg["content"]
    assert result.final_text == "ok"


def test_max_turns_raises(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "x"}, call_id=f"c{i}") for i in range(3)])
    with pytest.raises(MaxTurnsExceeded):
        run_agent(client, "m", [ECHO], "问题", tracer, max_turns=3)


def test_spans_follow_genai_conventions(tracing):
    tracer, exporter = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "hi"}), final_response("done")])
    run_agent(client, "gpt-test", [ECHO], "问题", tracer)
    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert set(spans) == {"invoke_agent doc-qa", "chat gpt-test", "execute_tool echo"}
    agent = spans["invoke_agent doc-qa"].attributes
    assert agent["gen_ai.operation.name"] == "invoke_agent"
    llm = spans["chat gpt-test"].attributes
    assert llm["gen_ai.operation.name"] == "chat"
    assert llm["gen_ai.request.model"] == "gpt-test"
    assert llm["gen_ai.usage.input_tokens"] == 10
    tool = spans["execute_tool echo"].attributes
    assert tool["gen_ai.operation.name"] == "execute_tool"
    assert tool["gen_ai.tool.name"] == "echo"
    # 父子关系:chat / execute_tool 都挂在 invoke_agent 下
    root_id = spans["invoke_agent doc-qa"].context.span_id
    assert spans["chat gpt-test"].parent.span_id == root_id
    assert spans["execute_tool echo"].parent.span_id == root_id
```

注:同名 `chat gpt-test` span 出现两次,dict 去重后剩一个,断言集合相等仍成立。

- [ ] **Step 3: 跑测试确认失败**

```bash
uv run pytest tests/test_loop.py -v
```

Expected: FAIL(`ModuleNotFoundError: agent_loop.loop`)

- [ ] **Step 4: 实现 loop.py**

```python
# src/agent_loop/loop.py
"""裸 agent 循环。没有框架:一个 while、一个消息列表、一张工具表。

OTel span 遵循 GenAI 语义约定(gen_ai.*):
- invoke_agent(根)→ 每轮一个 chat span + 每次工具执行一个 execute_tool span。
"""
import json
from dataclasses import dataclass, field

from opentelemetry.trace import Status, StatusCode

from agent_loop.tools import ToolSpec

SYSTEM_PROMPT = (
    "你是知识库问答助手。优先用 search_docs 检索;需要某文件完整内容时用 read_doc。"
    "回答必须基于工具返回的内容,并注明来源文件名;检索不到就明说不知道,禁止编造。"
)


class MaxTurnsExceeded(RuntimeError):
    pass


@dataclass
class AgentResult:
    final_text: str = ""
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[str] = field(default_factory=list)


def run_agent(client, model: str, tools: list[ToolSpec], user_input: str, tracer,
              max_turns: int = 8) -> AgentResult:
    tool_map = {t.name: t for t in tools}
    tool_defs = [t.to_openai() for t in tools]
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    result = AgentResult()

    with tracer.start_as_current_span(
        "invoke_agent doc-qa",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "doc-qa",
            "gen_ai.request.model": model,
        },
    ) as agent_span:
        for turn in range(1, max_turns + 1):
            result.turns = turn

            with tracer.start_as_current_span(
                f"chat {model}",
                attributes={"gen_ai.operation.name": "chat", "gen_ai.request.model": model},
            ) as llm_span:
                response = client.chat.completions.create(
                    model=model, messages=messages, tools=tool_defs
                )
                usage = getattr(response, "usage", None)
                if usage is not None:
                    llm_span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
                    llm_span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)
                    result.input_tokens += usage.prompt_tokens
                    result.output_tokens += usage.completion_tokens

            msg = response.choices[0].message
            if not msg.tool_calls:  # 模型不再要工具 → 这就是最终答案,循环结束
                result.final_text = msg.content or ""
                agent_span.set_attribute("agent.turns", turn)
                return result

            # assistant 的 tool_calls 消息必须原样回填,后面的 role=tool 消息才合法
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                result.tool_calls.append(name)
                with tracer.start_as_current_span(
                    f"execute_tool {name}",
                    attributes={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name},
                ) as tool_span:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        if name in tool_map:
                            output = tool_map[name].handler(**args)
                        else:
                            output = f"ERROR: 未知工具 {name}"
                    except Exception as exc:  # 工具失败不终止循环:错误回喂给模型自行恢复
                        output = f"ERROR: {exc}"
                        tool_span.set_status(Status(StatusCode.ERROR, str(exc)))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

        agent_span.set_status(Status(StatusCode.ERROR, "max turns exceeded"))
        raise MaxTurnsExceeded(f"agent 在 {max_turns} 轮内未产出最终答案")
```

- [ ] **Step 5: 跑全量测试确认通过**

```bash
uv run pytest -v
```

Expected: 全部 passed(config 2 + tools 4 + mcp 4 + loop 5)

- [ ] **Step 6: Commit**

```bash
git add src/agent_loop/loop.py tests/fakes.py tests/test_loop.py
git commit -m "agent-loop-lab: 裸 agent 循环(tool-call 回填/错误恢复/max_turns)+ GenAI 约定 span"
```

---

### Task 8: main.py CLI + 真实运行采集数字

**Files:**
- Create: `ai/agent-loop-lab/src/agent_loop/main.py`
- Create: `ai/agent-loop-lab/notes/run-log.md`

- [ ] **Step 1: 实现 main.py**

```python
# src/agent_loop/main.py
"""CLI:uv run python -m agent_loop.main "你的问题" """
import argparse
import time

from openai import OpenAI

from agent_loop.config import load_settings
from agent_loop.loop import run_agent
from agent_loop.mcp_client import READ_DOC
from agent_loop.otel import init_tracing
from agent_loop.tools import SEARCH_DOCS


def main() -> None:
    parser = argparse.ArgumentParser(description="裸循环 agent:本地知识库问答")
    parser.add_argument("question")
    parser.add_argument("--max-turns", type=int, default=8)
    args = parser.parse_args()

    settings = load_settings()
    tracer, provider = init_tracing(settings)
    client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

    start = time.perf_counter()
    result = run_agent(
        client, settings.llm_model, [SEARCH_DOCS, READ_DOC], args.question, tracer,
        max_turns=args.max_turns,
    )
    elapsed = time.perf_counter() - start

    print(result.final_text)
    print(
        f"\n--- turns={result.turns} tools={result.tool_calls} "
        f"tokens={result.input_tokens}+{result.output_tokens} latency={elapsed:.2f}s"
    )
    provider.shutdown()  # 刷 BatchSpanProcessor,不调用会丢 trace


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 真实运行(需 .env:LLM key + Langfuse pk/sk,Langfuse 已在 Task 1 起好)**

```bash
cp .env.example .env   # 填入与 MVP 相同的 key
uv run python -m agent_loop.main "pgvector 的索引类型有哪些?各自什么取舍?"
uv run python -m agent_loop.main "k8s 的 liveness 和 readiness 探针有什么区别?"
uv run python -m agent_loop.main "今天深圳天气怎么样?"   # 知识库外:应明说不知道
```

Expected: 前两问给出带 `[postgres.md]` / `[kubernetes.md]` 来源的回答;第三问明确说知识库没有。每次打印 turns/tools/tokens/latency。

- [ ] **Step 3: Langfuse 验证 trace**

UI 里应看到 service `agent-loop-lab` 的 trace:`invoke_agent doc-qa` 根 span 下挂 `chat ...` 和 `execute_tool search_docs`(可能还有 `read_doc`),chat span 上有 `gen_ai.usage.*`。截图存 `notes/img/`。

- [ ] **Step 4: 写 notes/run-log.md(数字全部来自真实输出)**

```markdown
# agent-loop-lab 真实运行记录(2026-06)

| 问题 | turns | 工具序列 | tokens(in+out) | 延迟 | 对照 MVP /chat 延迟(runlog) |
|------|-------|---------|----------------|------|------------------------------|
| pgvector 索引 | <n> | <[...]> | <n+n> | <x.xs> | <x.xs> |
| k8s 探针 | <n> | <[...]> | <n+n> | <x.xs> | — |
| 深圳天气(域外) | <n> | <[...]> | <n+n> | <x.xs> | <MVP 的路由行为> |

- Langfuse trace 截图:notes/img/<file>.png
- 观察:<例如 read_doc 每次冷启动 MCP 子进程带来的额外延迟;模型是否会先 search 再 read;域外问题是否老实拒答>
```

- [ ] **Step 5: Commit**

```bash
git add src/agent_loop/main.py notes/
git commit -m "agent-loop-lab: CLI 入口 + 真实运行数字(turns/tokens/latency + Langfuse trace)"
```

---

### Task 9: 对比笔记 + README

**Files:**
- Create: `ai/agent-loop-lab/notes/01-loop-vs-langgraph.md`
- Create: `ai/agent-loop-lab/README.md`

- [ ] **Step 1: 写对比笔记**

逐节写满,引用两边真实代码与 run-log/runlog 数字,禁止空话。固定结构:

```markdown
# 同一个功能:裸 loop vs LangGraph(MVP)

> 左边 ~120 行 `loop.py`,右边 MVP 的 supervisor+CRAG 图。两边跑同一批问题、同一份语料、同一个 Langfuse。

## 1. 各维度对照

| 维度 | 裸 loop(本 lab) | LangGraph(MVP) |
|------|------------------|------------------|
| 循环本体 | 显式 while + messages list(loop.py:run_agent) | 图边定义,引擎驱动(agent/graph.py) |
| 状态 | 函数内局部变量,进程死=状态丢 | AgentState + PostgresSaver checkpoint,可跨进程恢复 |
| 防死循环 | max_turns 手写 | recursion_limit + 路由条件边 |
| 工具错误恢复 | 手写 try/except 回喂 ERROR | 同思路,框架不替你做 |
| HITL | 没有,要自己造(信号量/队列) | interrupt() + Command(resume) 一等公民 |
| 流式 | 要自己改 create(stream=True) 再透传 | astream_events 现成 |
| 可观测 | OTel 手动埋 3 类 span | Langfuse callback 自动全埋 |
| 代码量(本功能切片) | <真实行数> | <真实行数,wc -l 相关文件> |

## 2. 真实数字对照(同问题)
<从 run-log.md 和 MVP runlog 摘:延迟、token;分析差异来源——MVP 多了路由/CRAG 评分/grounding 检查这几次额外 LLM 调用>

## 3. 结论:什么时候选哪个(面试答案)
执行时按真实证据校订下面的草稿,与数字矛盾处必须改:
- 选裸 loop:单轮/短会话、无人工审批、状态可丢的场景(loop.py 全部逻辑一屏读完,调试 = 打印 messages);需要极致控制 context 组装与 token 预算时;依赖面要求最小时(零框架依赖,升级无 breaking change 风险)。
- 选框架:会话要跨进程/跨天恢复(PostgresSaver checkpoint 不值得手搓);要 HITL 审批中断(interrupt/resume 自己造要写信号量+持久化+恢复语义);要 token 级流式且多节点(astream_events 现成);图本身复杂到画出来才说得清(supervisor + CRAG 循环)。
- 一句话版:「agent 本质是循环+工具+context 管理,我两种都写过;框架买的是 checkpoint、HITL、流式这些生产能力,不是循环本身。」

## 4. 本 lab 的刻意简化(被追问时主动交代)
- MCP 每次调用冷启动子进程(生产应长连接复用 session)
- search_docs 是关键词打分不是向量检索
- 无重试/退避、无 budget 控制(MVP 的 core/resilience.py 有)
```

- [ ] **Step 2: 写 README.md**

```markdown
# agent-loop-lab:不用框架手写 agent

一个周末实验:裸 OpenAI SDK 手写 agent loop + 自写 MCP server/client + OTel 手动埋点(GenAI 语义约定),trace 进自托管 Langfuse。复刻 MVP(../langchain/mvp-agentic-rag)kb 问答的薄切片,用于「裸写 vs 框架」对照。

## 跑起来
```bash
uv sync --extra dev
uv run pytest                 # hermetic,不需要 key
cp .env.example .env          # 填 LLM_*;LANGFUSE_* 可选
uv run python -m agent_loop.main "pgvector 的索引类型有哪些?"
```

## 看什么
- `src/agent_loop/loop.py` — agent 循环本体(~120 行,面试可背骨架)
- `src/agent_loop/mcp_server.py` / `mcp_client.py` — MCP 两端
- `notes/01-loop-vs-langgraph.md` — 与 LangGraph 版的逐维度对照 + 真实数字
- `notes/run-log.md` — 真实运行记录
```

- [ ] **Step 3: Commit**

```bash
git add notes/01-loop-vs-langgraph.md README.md
git commit -m "agent-loop-lab: 裸 loop vs LangGraph 对比笔记 + README"
```

---

### Task 10: 02 模块文档锚点回填

**Files:**
- Modify: `ai/ml-to-llm-roadmap/02-agent-tool-use/01-agent-boundary-and-loop.md`(文末追加,不改原文)

- [ ] **Step 1: 在文末追加「实战锚点」节**

按 spec 决策 4 的格式,数字从 `notes/run-log.md` 取真实值:

```markdown
## 实战锚点(2026-06,亲手跑出)

这一篇讲的 agent loop,我在两个地方各实现过一遍:

- **裸写版**:[ai/agent-loop-lab](../../agent-loop-lab/) —— 不用框架,~120 行 while 循环 + MCP 工具 + OTel 手动埋点。真实一问:turns=<n>、工具序列 <[...]>、tokens <n+n>、延迟 <x.x>s(notes/run-log.md)。
- **框架版**:[mvp-agentic-rag](../../langchain/mvp-agentic-rag/) —— LangGraph supervisor + CRAG 子图 + PostgresSaver。同样的问题端到端 <x.x>s,差异来自路由/文档评分/grounding 检查的额外 LLM 调用(docs/runlog-2026-06-first-real-run.md)。
- **对照结论**:[裸 loop vs LangGraph](../../agent-loop-lab/notes/01-loop-vs-langgraph.md) —— 框架买的是 checkpoint/HITL/流式,不是循环本身。
- **面试 30 秒**:agent 本质 = while 循环里「模型要工具 → 执行 → 结果回填 → 再问」,终止条件是模型不再要工具或 max_turns 兜底;我手写过这个循环,也用 LangGraph 实现过带持久化和人工审批的版本,什么时候选哪个见对照笔记。
```

- [ ] **Step 2: 校验链接可达**

```bash
ls ai/agent-loop-lab/notes/01-loop-vs-langgraph.md ai/agent-loop-lab/notes/run-log.md \
   ai/langchain/mvp-agentic-rag/docs/runlog-2026-06-first-real-run.md
```

Expected: 三个文件都存在

- [ ] **Step 3: Commit**

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use/01-agent-boundary-and-loop.md
git commit -m "ml-to-llm-roadmap: 02/01 agent loop 实战锚点(裸写 vs LangGraph 真实数字)"
```

---

## 验收(对照 spec 第六节)

- [ ] 能背着说:MVP 一次 kb 问答的真实延迟、token、成本量级,citations 命中文件(spec 验收 7 的参数底料)
- [ ] 能白板写出 agent loop 骨架并解释每步(spec 验收 4 前半)
- [ ] 能讲:MCP initialize → list_tools → call_tool 的握手过程,自己写过两端
- [ ] 能讲:OTel 三边界 span + GenAI 语义约定 + OTLP 换后端(spec 验收 5 的 lab 版,MVP OTel 化在月 2)
- [ ] `uv run pytest` 全绿且 hermetic(不需要 key)
- [ ] 02/01 文档的实战锚点里没有占位符,全是真实数字

## 不在本计划内(顺延)

- MVP obs 层 OTel 化(spec 决策 1)→ 月 2
- golden set 扩充 + `make eval` 真报告 + 07 回填 → 月 3
