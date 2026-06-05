# Agentic RAG MVP — Plan 3:API + 流式 + 可观测 + 韧性 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Plan 2 的 Agent 图包成生产形态的 FastAPI 服务:同步/SSE 流式问答、会话状态查询与 HITL 恢复、健康检查、Prometheus 指标、可观测(默认 Langfuse,可换)、韧性(retry/fallback/降级),`docker compose up` 即起。

**Architecture:** FastAPI 用 `create_app(deps)` 工厂 + 依赖注入(AppDeps 持有 compiled graph、db、可观测回调),测试注入 stub 即可用 TestClient 端到端测端点而不碰真实 LLM/Langfuse。可观测后端由 `get_observability_callbacks(settings)` 按 `OBS_BACKEND` 选择(langfuse/langsmith/none + 始终带一个 Prometheus MonitoringCallback)。request_id 串联 trace 与结构化日志。

**Tech Stack:** 在 Plan 1+2 基础上新增 `fastapi` + `uvicorn[standard]` + `prometheus-client` + `langfuse` + `httpx`(TestClient)。

---

## 上位文档
- 设计 spec:`docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`(§5.4 可观测、§5.6 韧性、§5.8 API)
- 前置:Plan 1+2 已合入 main(检索通路 + Agent 图 `build_production_agent_graph(db, checkpointer, settings)`、`get_chat_model`、`Database`、`PostgresSaver` 用法)。
- 本计划只覆盖 API/流式/可观测/韧性;eval + 面试文档层在 Plan 4。

## 前置条件
- Plan 1+2 环境(uv 项目、Docker)。
- 真实 LLM 端到端(/chat 真答案、Langfuse 真 trace)需 `.env` 的 `LLM_*` + `LANGFUSE_*`,**本计划不依赖它**(测试用 stub graph + OBS_BACKEND=none / 假 key)。

## 文件结构(本计划产出 / 修改)
```
ai/langchain/mvp-agentic-rag/
├─ pyproject.toml                       (改:加 fastapi/uvicorn/prometheus-client/langfuse/httpx)
├─ .env.example                         (改:加 OBS_BACKEND / LANGFUSE_* / APP_API_KEY)
├─ Dockerfile                           (新:应用镜像)
├─ docker-compose.yml                   (改:加 app 服务 + 可选 langfuse profile 说明)
├─ Makefile                             (改:加 run / serve 目标)
├─ langgraph.json                       (新:LangGraph Server 入口)
├─ src/mvp_agentic_rag/
│  ├─ core/
│  │  ├─ config.py                      (改:obs/auth 字段)
│  │  └─ resilience.py                  (新:get_chat_model_with_fallback)
│  ├─ obs/
│  │  ├─ __init__.py                    (新)
│  │  ├─ metrics.py                     (新:Prometheus 指标对象)
│  │  ├─ callbacks.py                   (新:MonitoringCallback)
│  │  └─ backends.py                    (新:get_observability_callbacks)
│  ├─ api/
│  │  ├─ __init__.py                    (新)
│  │  ├─ schemas.py                     (新:请求/响应模型)
│  │  ├─ deps.py                        (新:AppDeps + api_key 依赖)
│  │  └─ app.py                         (新:create_app + 端点)
│  └─ main.py                           (新:生产入口装配)
└─ tests/
   ├─ test_metrics_callback.py          (新)
   ├─ test_obs_backends.py              (新)
   ├─ test_api_schemas.py               (新)
   ├─ test_api_health.py                (新)
   ├─ test_api_chat.py                  (新)
   ├─ test_api_stream.py                (新)
   ├─ test_api_threads.py               (新)
   └─ test_resilience.py                (新)
```

> 约定:命令都在 `ai/langchain/mvp-agentic-rag/` 下执行。

---

### Task 1: 依赖 + 可观测/鉴权配置 + Prometheus 指标与 MonitoringCallback

**Files:**
- Modify: `pyproject.toml`, `.env.example`, `src/mvp_agentic_rag/core/config.py`
- Create: `src/mvp_agentic_rag/obs/__init__.py`, `src/mvp_agentic_rag/obs/metrics.py`, `src/mvp_agentic_rag/obs/callbacks.py`
- Test: `tests/test_metrics_callback.py`

- [ ] **Step 1: 加依赖**

Run: `cd ai/langchain/mvp-agentic-rag && uv add fastapi "uvicorn[standard]" prometheus-client langfuse httpx`
Expected: 写入 pyproject + uv.lock,安装成功。

- [ ] **Step 2: 扩展 `core/config.py`(在 llm_model_fallback 后追加)**

```python
    # 可观测
    obs_backend: str = "none"          # none | langfuse | langsmith
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"
    # 鉴权(留空=开发模式不校验)
    app_api_key: str = ""
```

- [ ] **Step 3: 更新 `.env.example`(末尾追加)**

```bash
# ---- 可观测 ----
OBS_BACKEND=none            # none | langfuse | langsmith
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=http://localhost:3000
# ---- 鉴权(留空=开发模式)----
APP_API_KEY=
```

- [ ] **Step 4: 写 `src/mvp_agentic_rag/obs/__init__.py`(空)**

```python
```

- [ ] **Step 5: 写 `src/mvp_agentic_rag/obs/metrics.py`(模块级单例指标,避免重复注册)**

```python
from prometheus_client import Counter, Histogram

LLM_TOKENS = Counter("rag_llm_tokens_total", "LLM total tokens consumed")
LLM_CALLS = Counter("rag_llm_calls_total", "Number of LLM calls")
TOOL_ERRORS = Counter("rag_tool_errors_total", "Number of tool errors")
LLM_LATENCY = Histogram("rag_llm_latency_seconds", "LLM call latency seconds")
```

- [ ] **Step 6: 写失败测试 `tests/test_metrics_callback.py`**

```python
from langchain_core.outputs import LLMResult, ChatGeneration
from langchain_core.messages import AIMessage


def _llm_result_with_tokens(total):
    msg = AIMessage(content="hi", usage_metadata={
        "input_tokens": total // 2, "output_tokens": total - total // 2, "total_tokens": total})
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def test_monitoring_callback_counts_tokens_and_calls():
    from mvp_agentic_rag.obs.callbacks import MonitoringCallback
    from mvp_agentic_rag.obs import metrics

    before_calls = metrics.LLM_CALLS._value.get()
    before_tokens = metrics.LLM_TOKENS._value.get()

    cb = MonitoringCallback()
    cb.on_llm_start({}, ["prompt"], run_id="r1")
    cb.on_llm_end(_llm_result_with_tokens(10), run_id="r1")

    assert metrics.LLM_CALLS._value.get() == before_calls + 1
    assert metrics.LLM_TOKENS._value.get() == before_tokens + 10


def test_monitoring_callback_counts_tool_errors():
    from mvp_agentic_rag.obs.callbacks import MonitoringCallback
    from mvp_agentic_rag.obs import metrics

    before = metrics.TOOL_ERRORS._value.get()
    cb = MonitoringCallback()
    cb.on_tool_error(ValueError("boom"), run_id="r2")
    assert metrics.TOOL_ERRORS._value.get() == before + 1
```

- [ ] **Step 7: 运行测试,确认失败**

Run: `uv run pytest tests/test_metrics_callback.py -v`
Expected: FAIL（无 `obs.callbacks`）。

- [ ] **Step 8: 写实现 `src/mvp_agentic_rag/obs/callbacks.py`**

```python
import time

from langchain_core.callbacks import BaseCallbackHandler

from mvp_agentic_rag.obs import metrics


class MonitoringCallback(BaseCallbackHandler):
    """把 LLM/工具的关键指标打到 Prometheus(与 trace 互补:metrics 看聚合)。"""

    def __init__(self) -> None:
        self._starts: dict = {}

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs) -> None:
        self._starts[run_id] = time.monotonic()

    def on_llm_end(self, response, *, run_id=None, **kwargs) -> None:
        metrics.LLM_CALLS.inc()
        start = self._starts.pop(run_id, None)
        if start is not None:
            metrics.LLM_LATENCY.observe(time.monotonic() - start)
        total = 0
        for gens in getattr(response, "generations", []) or []:
            for gen in gens:
                msg = getattr(gen, "message", None)
                usage = getattr(msg, "usage_metadata", None) if msg else None
                if usage:
                    total += usage.get("total_tokens", 0)
        if total:
            metrics.LLM_TOKENS.inc(total)

    def on_tool_error(self, error, *, run_id=None, **kwargs) -> None:
        metrics.TOOL_ERRORS.inc()
```

- [ ] **Step 9: 运行测试,确认通过**

Run: `uv run pytest tests/test_metrics_callback.py -v`
Expected: PASS（2 passed）。若 `Counter._value.get()` 内部 API 在该 prometheus-client 版本不可用,改用 `from prometheus_client import REGISTRY; REGISTRY.get_sample_value("rag_llm_calls_total")` 读取,并相应调整断言;记为 concern。

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml uv.lock .env.example src/mvp_agentic_rag/core/config.py src/mvp_agentic_rag/obs/ tests/test_metrics_callback.py
git commit -m "mvp-agentic-rag: Plan3 Task1 依赖 + 可观测配置 + Prometheus MonitoringCallback"
```

---

### Task 2: 可观测后端选择(get_observability_callbacks)

**Files:**
- Create: `src/mvp_agentic_rag/obs/backends.py`
- Test: `tests/test_obs_backends.py`

> 单一后端 + 可换:始终带 MonitoringCallback;`OBS_BACKEND=langfuse` 追加 Langfuse handler(版本容错:v3 `langfuse.langchain` 优先,回退 v2 `langfuse.callback`);`langsmith` 仅靠环境变量自动追踪(不需 handler);`none`/未知 不加额外 handler。

- [ ] **Step 1: 写失败测试 `tests/test_obs_backends.py`**

```python
from mvp_agentic_rag.core.config import Settings
from mvp_agentic_rag.obs.callbacks import MonitoringCallback


def test_none_backend_only_monitoring(monkeypatch):
    monkeypatch.setenv("OBS_BACKEND", "none")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    assert any(isinstance(c, MonitoringCallback) for c in cbs)
    assert len(cbs) == 1


def test_langsmith_backend_sets_env_no_extra_handler(monkeypatch):
    monkeypatch.setenv("OBS_BACKEND", "langsmith")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    # langsmith 靠环境变量自动追踪,不额外加 handler
    assert len(cbs) == 1
    import os
    assert os.environ.get("LANGSMITH_TRACING") == "true"


def test_langfuse_backend_adds_handler(monkeypatch):
    monkeypatch.setenv("OBS_BACKEND", "langfuse")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    # 至少包含 MonitoringCallback + 一个 langfuse handler
    assert any(isinstance(c, MonitoringCallback) for c in cbs)
    assert len(cbs) >= 2
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_obs_backends.py -v`
Expected: FAIL（无 `obs.backends`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/obs/backends.py`**

```python
import os

from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.obs.callbacks import MonitoringCallback


def _make_langfuse_handler(settings: Settings):
    # 把 key 透传到 langfuse 读取的环境变量
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    try:  # langfuse v3
        from langfuse.langchain import CallbackHandler
    except ImportError:  # langfuse v2 回退
        from langfuse.callback import CallbackHandler
    return CallbackHandler()


def get_observability_callbacks(settings: Settings | None = None) -> list:
    s = settings or get_settings()
    callbacks: list = [MonitoringCallback()]
    backend = (s.obs_backend or "none").lower()
    if backend == "langfuse":
        callbacks.append(_make_langfuse_handler(s))
    elif backend == "langsmith":
        os.environ["LANGSMITH_TRACING"] = "true"  # 其余 LANGSMITH_API_KEY/PROJECT 由 .env 提供
    return callbacks
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_obs_backends.py -v`
Expected: PASS（3 passed）。若 langfuse v3 `CallbackHandler()` 在无连接时构造抛错,改为捕获并降级(记 warning、不追加 handler),并相应放宽该测试为「不抛错」;记为 concern。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/obs/backends.py tests/test_obs_backends.py
git commit -m "mvp-agentic-rag: Plan3 Task2 可观测后端选择(默认 Langfuse 可换)"
```

---

### Task 3: API 请求/响应模型

**Files:**
- Create: `src/mvp_agentic_rag/api/__init__.py`, `src/mvp_agentic_rag/api/schemas.py`
- Test: `tests/test_api_schemas.py`

- [ ] **Step 1: 写失败测试 `tests/test_api_schemas.py`**

```python
def test_chat_request_defaults():
    from mvp_agentic_rag.api.schemas import ChatRequest

    r = ChatRequest(message="hi")
    assert r.message == "hi"
    assert r.thread_id == "default"


def test_chat_response_shape():
    from mvp_agentic_rag.api.schemas import ChatResponse

    r = ChatResponse(response="ans", citations=[{"doc_id": "a.md"}], request_id="x")
    assert r.response == "ans"
    assert r.citations[0]["doc_id"] == "a.md"


def test_resume_request():
    from mvp_agentic_rag.api.schemas import ResumeRequest

    r = ResumeRequest(thread_id="t1", decision="approved")
    assert r.decision == "approved"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_api_schemas.py -v`
Expected: FAIL（无 `api.schemas`）。

- [ ] **Step 3: 写 `src/mvp_agentic_rag/api/__init__.py`(空)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/api/schemas.py`**

```python
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    citations: list[dict] = Field(default_factory=list)
    request_id: str


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_api_schemas.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/api/__init__.py src/mvp_agentic_rag/api/schemas.py tests/test_api_schemas.py
git commit -m "mvp-agentic-rag: Plan3 Task3 API 请求/响应模型"
```

---

### Task 4: AppDeps + create_app + 健康检查 / 指标 / request_id

**Files:**
- Create: `src/mvp_agentic_rag/api/deps.py`, `src/mvp_agentic_rag/api/app.py`
- Test: `tests/test_api_health.py`

> `create_app(deps)` 工厂 + DI:测试注入 stub graph/db。中间件给每个响应加 `X-Request-ID`。`/healthz` 存活、`/readyz` ping DB、`/metrics` 暴露 Prometheus。

- [ ] **Step 1: 写失败测试 `tests/test_api_health.py`**

```python
from fastapi.testclient import TestClient


class StubDB:
    def __init__(self, ok=True):
        self.ok = ok

    def connect(self):
        db = self

        class _Ctx:
            def __enter__(self):
                if not db.ok:
                    raise RuntimeError("db down")
                return _Conn()

            def __exit__(self, *a):
                return False

        class _Conn:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return (1,)

        return _Ctx()


def _client(db_ok=True):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app

    deps = AppDeps(graph=object(), db=StubDB(db_ok), callbacks=[])
    return TestClient(create_app(deps))


def test_healthz():
    r = _client().get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_request_id_header():
    r = _client().get("/healthz")
    assert r.headers.get("X-Request-ID")


def test_readyz_ok():
    r = _client(db_ok=True).get("/readyz")
    assert r.status_code == 200


def test_readyz_db_down_returns_503():
    r = _client(db_ok=False).get("/readyz")
    assert r.status_code == 503


def test_metrics_endpoint():
    r = _client().get("/metrics")
    assert r.status_code == 200
    assert "rag_llm_calls_total" in r.text
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: FAIL（无 `api.deps` / `api.app`）。

- [ ] **Step 3: 写 `src/mvp_agentic_rag/api/deps.py`**

```python
from dataclasses import dataclass, field

from fastapi import Header, HTTPException

from mvp_agentic_rag.core.config import get_settings


@dataclass
class AppDeps:
    graph: object              # 编译后的 LangGraph(或测试 stub)
    db: object                 # Database(或测试 stub),供 readyz
    callbacks: list = field(default_factory=list)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """APP_API_KEY 留空=开发模式不校验;设置后要求请求头 X-API-Key 匹配。"""
    expected = get_settings().app_api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
```

- [ ] **Step 4: 写 `src/mvp_agentic_rag/api/app.py`**

```python
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from mvp_agentic_rag.api.deps import AppDeps


def create_app(deps: AppDeps) -> FastAPI:
    app = FastAPI(title="Agentic RAG MVP")
    app.state.deps = deps

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        try:
            with deps.db.connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ready"}
        except Exception as exc:  # noqa: BLE001 — readiness 探针要吞异常转 503
            return JSONResponse(status_code=503, content={"status": "not ready", "error": str(exc)})

    @app.get("/metrics")
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_api_health.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/api/deps.py src/mvp_agentic_rag/api/app.py tests/test_api_health.py
git commit -m "mvp-agentic-rag: Plan3 Task4 create_app + 健康检查/指标/request_id"
```

---

### Task 5: /chat 同步端点(+ API key 鉴权)

**Files:**
- Modify: `src/mvp_agentic_rag/api/app.py`
- Test: `tests/test_api_chat.py`

> `/chat` 用 `deps.graph.invoke(...)`(注入 callbacks + thread_id),取最后一条 AI 消息为 response、state 的 citations。鉴权用 `require_api_key` 依赖。

- [ ] **Step 1: 写失败测试 `tests/test_api_chat.py`**

```python
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


class StubGraph:
    def __init__(self):
        self.last_config = None

    def invoke(self, state, config=None):
        self.last_config = config
        return {"messages": [HumanMessage(content=state["messages"][-1].content),
                             AIMessage(content="stub answer")],
                "citations": [{"doc_id": "k8s.md", "chunk_idx": 0}]}


def _client(graph):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app
    import mvp_agentic_rag.core.config as cfg

    cfg.get_settings.cache_clear()  # 让 require_api_key 重新读取 APP_API_KEY
    return TestClient(create_app(AppDeps(graph=graph, db=object(), callbacks=[])))


def test_chat_returns_answer_and_citations():
    graph = StubGraph()
    client = _client(graph)
    r = client.post("/chat", json={"message": "autoscaling?", "thread_id": "t1"})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "stub answer"
    assert body["citations"][0]["doc_id"] == "k8s.md"
    assert body["request_id"]
    # thread_id 进了 config
    assert graph.last_config["configurable"]["thread_id"] == "t1"


def test_chat_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    import mvp_agentic_rag.core.config as cfg
    cfg.get_settings.cache_clear()

    client = _client(StubGraph())
    # 缺 key → 401
    assert client.post("/chat", json={"message": "x"}).status_code == 401
    # 带正确 key → 200
    ok = client.post("/chat", json={"message": "x"}, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    cfg.get_settings.cache_clear()
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_api_chat.py -v`
Expected: FAIL（无 `/chat` 路由）。

- [ ] **Step 3: 在 `src/mvp_agentic_rag/api/app.py` 增加 /chat（在 `/metrics` 之后、`return app` 之前)**

先在文件顶部 import 区补充:
```python
from fastapi import Depends
from langchain_core.messages import AIMessage, HumanMessage

from mvp_agentic_rag.api.deps import require_api_key
from mvp_agentic_rag.api.schemas import ChatRequest, ChatResponse
```
然后加入端点:
```python
    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request, _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": req.thread_id}, "callbacks": deps.callbacks}
        result = deps.graph.invoke(
            {"messages": [HumanMessage(content=req.message)],
             "next": "", "citations": [], "step_budget": 6},
            config,
        )
        answer = ""
        for m in reversed(result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        return ChatResponse(response=answer, citations=result.get("citations", []),
                            request_id=request.state.request_id)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_api_chat.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/api/app.py tests/test_api_chat.py
git commit -m "mvp-agentic-rag: Plan3 Task5 /chat 同步端点 + API key 鉴权"
```

---

### Task 6: /chat/stream SSE 流式端点

**Files:**
- Modify: `src/mvp_agentic_rag/api/app.py`
- Test: `tests/test_api_stream.py`

> 用 `deps.graph.astream(input, config, stream_mode="messages")` 取消息块,逐块 `data: <content>\n\n` 推送,末尾 `data: [DONE]`。stub graph 提供异步 astream。

- [ ] **Step 1: 写失败测试 `tests/test_api_stream.py`**

```python
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk


class StreamStubGraph:
    async def astream(self, state, config=None, stream_mode=None):
        yield (AIMessageChunk(content="Hello"), {})
        yield (AIMessageChunk(content=" world"), {})


def _client():
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app

    return TestClient(create_app(AppDeps(graph=StreamStubGraph(), db=object(), callbacks=[])))


def test_chat_stream_yields_sse_tokens():
    r = _client().post("/chat/stream", json={"message": "hi", "thread_id": "t1"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "data: Hello" in body
    assert "data:  world" in body
    assert "data: [DONE]" in body
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_api_stream.py -v`
Expected: FAIL（无 `/chat/stream`）。

- [ ] **Step 3: 在 `src/mvp_agentic_rag/api/app.py` 增加 /chat/stream**

先在 import 区补充:
```python
from fastapi.responses import StreamingResponse
```
然后加入端点(放在 /chat 之后):
```python
    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request, _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": req.thread_id}, "callbacks": deps.callbacks}
        inp = {"messages": [HumanMessage(content=req.message)],
               "next": "", "citations": [], "step_budget": 6}

        async def event_stream():
            async for chunk, _meta in deps.graph.astream(inp, config, stream_mode="messages"):
                content = getattr(chunk, "content", "")
                if content:
                    yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_api_stream.py -v`
Expected: PASS（1 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/api/app.py tests/test_api_stream.py
git commit -m "mvp-agentic-rag: Plan3 Task6 /chat/stream SSE 流式端点"
```

---

### Task 7: /threads/{id} 状态查询 + HITL 恢复

**Files:**
- Modify: `src/mvp_agentic_rag/api/app.py`
- Test: `tests/test_api_threads.py`

> `/threads/{id}` 用 `deps.graph.get_state(config)` 返回消息历史;`/threads/{id}/resume` 用 `deps.graph.invoke(Command(resume=...), config)` 恢复 HITL。

- [ ] **Step 1: 写失败测试 `tests/test_api_threads.py`**

```python
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


class Snapshot:
    def __init__(self, values):
        self.values = values


class ThreadStubGraph:
    def __init__(self):
        self.resumed_with = None

    def get_state(self, config):
        return Snapshot({"messages": [HumanMessage(content="q"), AIMessage(content="a")]})

    def invoke(self, command, config=None):
        self.resumed_with = command
        return {"messages": [AIMessage(content="resumed")], "citations": []}


def _client(graph):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app

    return TestClient(create_app(AppDeps(graph=graph, db=object(), callbacks=[])))


def test_get_thread_state_returns_messages():
    r = _client(ThreadStubGraph()).get("/threads/t1")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs[-1]["content"] == "a"


def test_resume_continues_run():
    graph = ThreadStubGraph()
    r = _client(graph).post("/threads/t1/resume", json={"thread_id": "t1", "decision": "approved"})
    assert r.status_code == 200
    assert r.json()["response"] == "resumed"
    # 传入的是 Command(resume="approved")
    assert getattr(graph.resumed_with, "resume", None) == "approved"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_api_threads.py -v`
Expected: FAIL（无 /threads 路由）。

- [ ] **Step 3: 在 `src/mvp_agentic_rag/api/app.py` 增加 /threads 端点**

先在 import 区补充:
```python
from langgraph.types import Command

from mvp_agentic_rag.api.schemas import ResumeRequest
```
加入端点(放在 /chat/stream 之后):
```python
    @app.get("/threads/{thread_id}")
    async def get_thread(thread_id: str, _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = deps.graph.get_state(config)
        messages = [
            {"type": m.__class__.__name__, "content": str(getattr(m, "content", ""))}
            for m in snapshot.values.get("messages", [])
        ]
        return {"thread_id": thread_id, "messages": messages}

    @app.post("/threads/{thread_id}/resume", response_model=ChatResponse)
    async def resume_thread(thread_id: str, req: ResumeRequest, request: Request,
                            _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": thread_id}, "callbacks": deps.callbacks}
        result = deps.graph.invoke(Command(resume=req.decision), config)
        answer = ""
        for m in reversed(result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        return ChatResponse(response=answer, citations=result.get("citations", []),
                            request_id=request.state.request_id)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_api_threads.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/api/app.py tests/test_api_threads.py
git commit -m "mvp-agentic-rag: Plan3 Task7 /threads 状态查询 + HITL 恢复"
```

---

### Task 8: 韧性 — chat 模型降级(fallback)

**Files:**
- Create: `src/mvp_agentic_rag/core/resilience.py`
- Test: `tests/test_resilience.py`

> 主模型失败时降级到更便宜/小的模型。基于 langchain 的 `.with_fallbacks([...])`。retry/timeout 已在 `get_chat_model`(max_retries/timeout)中。

- [ ] **Step 1: 写失败测试 `tests/test_resilience.py`**

```python
def test_chat_model_with_fallback_builds_runnable(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "primary")
    monkeypatch.setenv("LLM_MODEL_FALLBACK", "backup")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings
    from mvp_agentic_rag.core.resilience import get_chat_model_with_fallback

    model = get_chat_model_with_fallback(Settings())
    # with_fallbacks 返回一个带 fallbacks 的 RunnableWithFallbacks
    assert hasattr(model, "fallbacks")
    assert len(model.fallbacks) == 1
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_resilience.py -v`
Expected: FAIL（无 `core.resilience`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/core/resilience.py`**

```python
from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.core.llm import get_chat_model


def get_chat_model_with_fallback(settings: Settings | None = None):
    """主模型 + 降级模型。主模型失败(超时/报错)时自动切到更便宜的备用模型。"""
    s = settings or get_settings()
    primary = get_chat_model(s, model=s.llm_model)
    fallback = get_chat_model(s, model=s.llm_model_fallback)
    return primary.with_fallbacks([fallback])
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_resilience.py -v`
Expected: PASS（1 passed）。若该 langchain 版本 `RunnableWithFallbacks` 的属性名不是 `fallbacks`,inspect 实际属性并调整断言;记为 concern。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/core/resilience.py tests/test_resilience.py
git commit -m "mvp-agentic-rag: Plan3 Task8 韧性 chat 模型降级(fallback)"
```

---

### Task 9: 生产入口 main.py + langgraph.json + Dockerfile + compose + Makefile

**Files:**
- Create: `src/mvp_agentic_rag/main.py`, `langgraph.json`, `Dockerfile`
- Modify: `docker-compose.yml`, `Makefile`
- Test: 入口 import 冒烟(无独立 pytest)

> `main.py` 把真实 deps(生产 Agent 图 + PostgresSaver + 可观测回调)装进 `create_app`,供 uvicorn 运行。只做 import 冒烟(真实运行需 `.env` 的 key + Postgres)。

- [ ] **Step 1: 写 `src/mvp_agentic_rag/main.py`**

```python
from langgraph.checkpoint.postgres import PostgresSaver

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.api.app import create_app
from mvp_agentic_rag.api.deps import AppDeps
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.obs.backends import get_observability_callbacks


def build_app():
    s = get_settings()
    db = get_database()
    db.init_schema()
    checkpointer = PostgresSaver.from_conn_string(s.database_url).__enter__()
    checkpointer.setup()
    graph = build_production_agent_graph(db, checkpointer, s)
    callbacks = get_observability_callbacks(s)
    return create_app(AppDeps(graph=graph, db=db, callbacks=callbacks))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mvp_agentic_rag.main:build_app", factory=True, host="0.0.0.0", port=8000)
```

> 说明:`build_app()` 真实连库 + 起 checkpointer,所以**不要在模块顶层调用它**(import 冒烟不应连库)。模块顶层只有 import + `build_app` 函数定义 + `__main__` 块;uvicorn / Docker CMD 用 `--factory` 形式调用 `build_app`。

- [ ] **Step 2: 写 `langgraph.json`**

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./src/mvp_agentic_rag/lg_entry.py:graph"
  },
  "env": ".env"
}
```

- [ ] **Step 3: 写 `src/mvp_agentic_rag/lg_entry.py`(LangGraph Server 入口:它自带持久化,这里用内存 checkpointer 占位由平台接管)**

```python
from langgraph.checkpoint.memory import InMemorySaver

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database


def _build():
    s = get_settings()
    db = get_database()
    db.init_schema()
    # LangGraph Server 会注入自己的持久化;此处占位用内存 saver。
    return build_production_agent_graph(db, InMemorySaver(), s)


graph = _build
```

> 注:`graph` 暴露为可调用工厂(LangGraph Server 接受 callable 或已编译图)。若该平台版本要求已编译图实例而非工厂,改为 `graph = _build()`(会在导入时连库,仅在真正 `langgraph up` 时发生)。记为 concern。

- [ ] **Step 4: 写 `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "mvp_agentic_rag.main:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: 在 `docker-compose.yml` 增加 app 服务(postgres 服务已存在)**

在 `services:` 下、`postgres:` 同级追加:
```yaml
  app:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql://rag:rag@postgres:5432/rag
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
```

- [ ] **Step 6: 在 `Makefile` 增加 serve 目标**

```makefile
serve:
	uv run uvicorn mvp_agentic_rag.main:build_app --factory --reload --port 8000
```

- [ ] **Step 7: import 冒烟(不连库)**

Run: `uv run python -c "import mvp_agentic_rag.main; import mvp_agentic_rag.lg_entry; print('entry ok')"`
Expected: 打印 `entry ok`(仅 import 模块、定义函数,不调用 build_app/_build,故不连库不调 LLM)。

- [ ] **Step 8: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿(Plan 1+2 的 41 + Plan 3 各任务测试)。

- [ ] **Step 9: Commit**

```bash
git add src/mvp_agentic_rag/main.py src/mvp_agentic_rag/lg_entry.py langgraph.json Dockerfile docker-compose.yml Makefile
git commit -m "mvp-agentic-rag: Plan3 Task9 生产入口 main + langgraph.json + Dockerfile + compose"
```

---

## 完成定义(Plan 3)
- `make test` 全绿且 hermetic:`/healthz`、`/readyz`、`/metrics`、`/chat`(含鉴权)、`/chat/stream`(SSE)、`/threads/{id}`、`/threads/{id}/resume` 都用 stub graph + TestClient 断言;可观测后端选择与 MonitoringCallback 指标断言;fallback 构造断言。
- 可观测一等公民:`OBS_BACKEND` 一个 env 切 none/langfuse/langsmith;每请求 `X-Request-ID` 串联;`/metrics` 暴露 token/调用/工具错误/延迟。
- `main.py` + `Dockerfile` + `docker-compose.yml`(app + postgres)可 `docker compose up` 起服务(真实运行需 `.env` 的 LLM/Langfuse key)。
- 交付物:可被 Plan 4(eval + 文档)对接的运行服务 + 可观测面。

## 自审记录(对照 spec §5.4 / §5.6 / §5.8)
- §5.8 API 面(/chat /chat/stream /threads /threads/resume /healthz /readyz /metrics):Task 4-7 ✅
- §5.4 可观测(Langfuse 默认可换、MonitoringCallback、request_id 串联):Task 1-2 + Task 4 中间件 ✅
- §5.6 韧性(retry/timeout 已在 get_chat_model;fallback 降级):Task 8 ✅(token/step budget 护栏在 Plan 2)
- 部署(Dockerfile/compose/langgraph.json):Task 9 ✅
- 鉴权(API key,真实 OIDC 超纲):Task 5 ✅
- 暂不覆盖(留 Plan 4):ragas eval、面试文档层、Grafana 面板、OTel、真实 Langfuse/LLM 端到端断言、SSE 仅推 generate 节点的过滤(当前推所有消息块,留作细化)。
- 已知风险点(执行期按红灯微调并记 concern):`prometheus_client` 读取计数 API、langfuse v3 `CallbackHandler()` 无连接时构造、`RunnableWithFallbacks.fallbacks` 属性名、langgraph.json `graph` 期望工厂还是已编译图、SSE TestClient 缓冲读取。

## 实现期 review 修正记录(committed 代码与上文逐字片段的差异)

执行时实测 + review 发现并已修正(均已合入,测试全绿):

- **langfuse 是 v4.7.1**(非 v3):`from langfuse.langchain import CallbackHandler` 仍可用(v4 类名 `LangchainCallbackHandler`),但 **v4 的 langchain 集成需要顶层 `langchain` 包**(项目原本只有 langchain-core)→ 追加 `uv add langchain`;`obs/backends.py` 的 `_make_langfuse_handler` 用 try/except 优雅降级(装不上/构造失败→返回 None 跳过);`OBS_BACKEND=langfuse` 实测返回 2 个回调。
- **`app.py` 顶部 `import mvp_agentic_rag.obs.metrics`**(noqa F401):模块级指标单例需在 `/metrics` 服务前注册。
- **常量时间鉴权**:`require_api_key` 用 `hmac.compare_digest`(而非 `!=`),防计时侧信道。
- **空答案守卫**:`/chat` 与 `/threads/{id}/resume` 在无 AIMessage 时 `raise HTTPException(500)`,不返回静默空 200。
- **补充鉴权测试**:`/chat/stream`、`/threads/{id}` 各加一条「设了 APP_API_KEY 时缺 key→401」测试。
- **韧性 fallback 接线**:`agent/factory.py` 把 `get_chat_model_with_fallback` 接到**纯 .invoke 的组件(生成/改写)**;结构化输出组件(路由/评分/接地)保持普通 chat —— 因为 `with_fallbacks` 返回的 `RunnableWithFallbacks` 没有 `.with_structured_output`,naive 接会崩。给结构化调用加 fallback 需在 `with_structured_output` 之后包,留作后续。
- **lg_entry.py** 暴露 `graph = _build`(可调用工厂);若 LangGraph Server 版本要求已编译图实例,改 `graph = _build()`(`langgraph up` 时才连库)。
