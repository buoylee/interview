# 月 2:MVP 可观测 OTel 化(OBS_BACKEND=otel)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **执行状态(2026-06-11):** 全部 6 个任务已完成并通过 review(含 review 后修复:chain 运行跟踪、取消泄漏清扫、线程锁);仅「Langfuse UI 真实 span 树验证」待用户环境,见 07/03 锚点的〔待实测〕。

**Goal:** 给 MVP 的可观测层新增 `otel` 后端:LangChain callback 三边界(LLM 调用/工具/检索)翻译成 OTel GenAI 语义约定 span,OTLP 导出到 Langfuse(或任意 OTLP 后端),保留 `OBS_BACKEND` 一键切换;并把「OTel 三边界」实战锚点回填进 roadmap 07/03 监控篇。

**Architecture:** 不引入 OpenInference/OpenLLMetry 自动 instrument(那是文档里提的现成替代),手写 `OTelTraceCallback(BaseCallbackHandler)`——用 LangChain 回调的 `run_id/parent_run_id` 映射 span 父子树,与 lab 手动埋点形成「同一套语义约定,两种接入方式」的对照。exporter 注入式设计(同 lab):tests 用 InMemorySpanExporter 全 hermetic;真实运行时 Langfuse OTLP 或控制台回退。现有 langfuse/langsmith 后端不动。

**Tech Stack:** MVP 现有栈 + `opentelemetry-sdk` + `opentelemetry-exporter-otlp-proto-http`(与 lab 同款)。

---

## 上位文档

- 设计 spec:`docs/superpowers/specs/2026-06-11-ml-to-llm-roadmap-practical-content-design.md` 决策 1 + 第九节排期(月 2)
- 对照实现:`ai/agent-loop-lab/src/agent_loop/{config,otel}.py`(OTLP 端点拼装、注入式 tracer 已验证)
- 回填目标:`ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`

## 前置条件

- 全程 hermetic,不需要 key/Docker。改动在 `ai/langchain/mvp-agentic-rag/`,现有测试(`make test` = `uv run pytest`)必须保持全绿。
- 真实 trace 验证(Langfuse UI 看 span 树)依赖用户环境,标〔待实测〕顺延。

## 文件结构(本计划产出 / 修改)

```
ai/langchain/mvp-agentic-rag/
├─ pyproject.toml                          (修改:加 opentelemetry 两个依赖)
├─ .env.example                            (修改:OBS_BACKEND 注释加 otel 选项)
├─ README.md                               (修改:可观测切换节加 otel 行)
├─ src/mvp_agentic_rag/
│  ├─ core/config.py                       (修改:obs_backend 注释加 otel)
│  └─ obs/
│     ├─ otel.py                           (新:langfuse_otlp_config + build_tracer + OTelTraceCallback)
│     └─ backends.py                       (修改:backend == "otel" 分支)
└─ tests/
   └─ test_obs_otel.py                     (新:callback 行为 + 工厂接线测试)

ai/ml-to-llm-roadmap/07-evaluation-safety-production/
└─ 03-production-debugging-monitoring.md   (修改:文末追加实战锚点)
```

---

### Task 1: 依赖 + 配置注释

**Files:**
- Modify: `ai/langchain/mvp-agentic-rag/pyproject.toml`
- Modify: `ai/langchain/mvp-agentic-rag/src/mvp_agentic_rag/core/config.py`(第 22 行注释)
- Modify: `ai/langchain/mvp-agentic-rag/.env.example`(OBS_BACKEND 注释)

- [ ] **Step 1:** pyproject `dependencies` 列表加两行(保持现有排序风格):

```toml
    "opentelemetry-sdk>=1.27",
    "opentelemetry-exporter-otlp-proto-http>=1.27",
```

- [ ] **Step 2:** config.py 第 22 行注释 `# none | langfuse | langsmith` 改为 `# none | langfuse | langsmith | otel`。`.env.example` 里 OBS_BACKEND 相关注释同步加 `otel`(找到现有注释行照格式补)。

- [ ] **Step 3:** `cd ai/langchain/mvp-agentic-rag && uv sync --extra dev && uv run python -c "import opentelemetry.sdk; print('ok')"` → ok;`uv run pytest -q` 现有测试全绿。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/mvp_agentic_rag/core/config.py .env.example
git commit -m "mvp-agentic-rag: OTel 依赖 + OBS_BACKEND otel 选项注释"
```

---

### Task 2: obs/otel.py — OTLP 配置 + tracer 工厂(TDD)

**Files:**
- Create: `ai/langchain/mvp-agentic-rag/src/mvp_agentic_rag/obs/otel.py`(本任务只写这两个函数)
- Test: `ai/langchain/mvp-agentic-rag/tests/test_obs_otel.py`(本任务只写前两个测试)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_obs_otel.py
import base64

from mvp_agentic_rag.core.config import Settings
from mvp_agentic_rag.obs.otel import langfuse_otlp_config


def _settings(**overrides):
    base = dict(
        obs_backend="otel",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-2",
        langfuse_host="http://localhost:3000",
    )
    base.update(overrides)
    return Settings(**base)


def test_otlp_config_builds_langfuse_endpoint_and_basic_auth():
    endpoint, headers = langfuse_otlp_config(_settings())
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected = base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["x-langfuse-ingestion-version"] == "4"


def test_otlp_config_none_when_keys_missing():
    assert langfuse_otlp_config(_settings(langfuse_public_key="")) is None
```

注:MVP 的 `Settings` 是 pydantic-settings/dataclass(以 core/config.py 实际为准),字段都有默认值,按关键字构造即可;若构造方式不同,调整 `_settings` helper,不改断言。

- [ ] **Step 2:** `uv run pytest tests/test_obs_otel.py -v` → ImportError/ModuleNotFoundError。

- [ ] **Step 3: 实现(otel.py 第一部分)**

```python
# src/mvp_agentic_rag/obs/otel.py
"""OTel 可观测后端:LangChain callback 边界 → GenAI 语义约定 span → OTLP。

与 ai/agent-loop-lab 的手动埋点是同一套语义约定的两种接入方式:
lab 在自己的循环里手动开 span;这里把框架回调翻译成 span。
"""
import atexit
import base64
import logging

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from mvp_agentic_rag.core.config import Settings

logger = logging.getLogger(__name__)


def langfuse_otlp_config(settings: Settings) -> tuple[str, dict[str, str]] | None:
    """Langfuse 收 OTLP:{host}/api/public/otel,traces 信号全路径 + /v1/traces。"""
    if not (settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    endpoint = settings.langfuse_host.rstrip("/") + "/api/public/otel/v1/traces"
    return endpoint, {"Authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"}


def build_tracer(settings: Settings, exporter=None):
    """返回 tracer。exporter 可注入(测试);provider 注册 atexit 刷缓冲。"""
    if exporter is None:
        otlp = langfuse_otlp_config(settings)
        if otlp is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint, headers = otlp
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        else:
            logger.warning("OBS_BACKEND=otel 但未配置 LANGFUSE_*,trace 落到控制台")
            exporter = ConsoleSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "mvp-agentic-rag"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    atexit.register(provider.shutdown)
    return provider.get_tracer("mvp_agentic_rag.obs")
```

- [ ] **Step 4:** `uv run pytest tests/test_obs_otel.py -v` → 2 passed。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/obs/otel.py tests/test_obs_otel.py
git commit -m "mvp-agentic-rag: obs/otel OTLP 配置 + tracer 工厂"
```

---

### Task 3: OTelTraceCallback(核心,TDD)

**Files:**
- Modify: `ai/langchain/mvp-agentic-rag/src/mvp_agentic_rag/obs/otel.py`(追加 callback 类)
- Modify: `ai/langchain/mvp-agentic-rag/tests/test_obs_otel.py`(追加测试)

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_obs_otel.py 追加
from types import SimpleNamespace
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mvp_agentic_rag.obs.otel import OTelTraceCallback


@pytest.fixture()
def otel_cb():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    cb = OTelTraceCallback(provider.get_tracer("test"))
    yield cb, exporter
    provider.shutdown()


def _llm_result(input_tokens=10, output_tokens=5):
    msg = SimpleNamespace(usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens,
                                          "total_tokens": input_tokens + output_tokens})
    return SimpleNamespace(generations=[[SimpleNamespace(message=msg)]])


def test_chat_span_with_usage(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_chat_model_start({}, [], run_id=run_id, parent_run_id=None,
                           invocation_params={"model_name": "gpt-test"})
    cb.on_llm_end(_llm_result(), run_id=run_id)
    (span,) = exporter.get_finished_spans()
    assert span.name == "chat gpt-test"
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.request.model"] == "gpt-test"
    assert span.attributes["gen_ai.usage.input_tokens"] == 10
    assert span.attributes["gen_ai.usage.output_tokens"] == 5


def test_tool_span_nested_under_parent(otel_cb):
    cb, exporter = otel_cb
    parent_id, child_id = uuid4(), uuid4()
    cb.on_chat_model_start({}, [], run_id=parent_id, parent_run_id=None,
                           invocation_params={"model_name": "m"})
    cb.on_tool_start({"name": "retrieve_kb"}, "查询", run_id=child_id, parent_run_id=parent_id)
    cb.on_tool_end("结果", run_id=child_id)
    cb.on_llm_end(_llm_result(), run_id=parent_id)
    spans = {s.name: s for s in exporter.get_finished_spans()}
    tool = spans["execute_tool retrieve_kb"]
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == "retrieve_kb"
    assert tool.parent.span_id == spans["chat m"].context.span_id


def test_tool_error_sets_status(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_tool_start({"name": "boom"}, "x", run_id=run_id, parent_run_id=None)
    cb.on_tool_error(RuntimeError("炸了"), run_id=run_id)
    (span,) = exporter.get_finished_spans()
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR


def test_retriever_span_records_doc_count(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_retriever_start({}, "查询", run_id=run_id, parent_run_id=None)
    cb.on_retriever_end([SimpleNamespace(), SimpleNamespace(), SimpleNamespace()], run_id=run_id)
    (span,) = exporter.get_finished_spans()
    assert span.name == "retrieve kb"
    assert span.attributes["gen_ai.operation.name"] == "retrieve"
    assert span.attributes["retrieval.documents.count"] == 3


def test_orphan_end_is_noop(otel_cb):
    cb, exporter = otel_cb
    cb.on_llm_end(_llm_result(), run_id=uuid4())  # 没有对应 start,不得抛异常
    assert exporter.get_finished_spans() == ()
```

- [ ] **Step 2:** `uv run pytest tests/test_obs_otel.py -v` → 新测试 ImportError(OTelTraceCallback 不存在)。

- [ ] **Step 3: 实现(otel.py 追加)**

```python
# src/mvp_agentic_rag/obs/otel.py 追加
from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry.trace import Status, StatusCode, set_span_in_context


def _extract_usage(response) -> tuple[int, int]:
    """与 MonitoringCallback 同源的 usage 提取:遍历 generations 的 usage_metadata。"""
    input_tokens = output_tokens = 0
    for gens in getattr(response, "generations", []) or []:
        for gen in gens:
            msg = getattr(gen, "message", None)
            usage = getattr(msg, "usage_metadata", None) if msg else None
            if usage:
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
    return input_tokens, output_tokens


class OTelTraceCallback(BaseCallbackHandler):
    """LangChain 回调三边界 → OTel GenAI 语义约定 span。

    run_id → span 表;parent_run_id 在表里就挂为父 span,否则做根。
    回调缺 start(框架异常路径)时 end 是 no-op,不影响主流程。
    """

    raise_error = False

    def __init__(self, tracer) -> None:
        self._tracer = tracer
        self._spans: dict = {}

    # ---- 内部 ----
    def _start(self, run_id, parent_run_id, name: str, attributes: dict) -> None:
        parent = self._spans.get(parent_run_id)
        ctx = set_span_in_context(parent) if parent is not None else None
        self._spans[run_id] = self._tracer.start_span(name, context=ctx, attributes=attributes)

    def _end(self, run_id, error=None) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        if error is not None:
            span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()

    # ---- LLM 边界 ----
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        params = kwargs.get("invocation_params") or {}
        model = str(params.get("model_name") or params.get("model") or "unknown")
        self._start(run_id, parent_run_id, f"chat {model}",
                    {"gen_ai.operation.name": "chat", "gen_ai.request.model": model})

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        # 非 chat 模型走这里;同样处理
        self.on_chat_model_start(serialized, [], run_id=run_id, parent_run_id=parent_run_id, **kwargs)

    def on_llm_end(self, response, *, run_id, **kwargs):
        span = self._spans.get(run_id)
        if span is not None:
            input_tokens, output_tokens = _extract_usage(response)
            if input_tokens:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            if output_tokens:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        self._end(run_id)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    # ---- 工具边界 ----
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        name = (serialized or {}).get("name", "unknown")
        self._start(run_id, parent_run_id, f"execute_tool {name}",
                    {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name})

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._end(run_id)

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    # ---- 检索边界 ----
    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, **kwargs):
        self._start(run_id, parent_run_id, "retrieve kb", {"gen_ai.operation.name": "retrieve"})

    def on_retriever_end(self, documents, *, run_id, **kwargs):
        span = self._spans.get(run_id)
        if span is not None:
            span.set_attribute("retrieval.documents.count", len(documents))
        self._end(run_id)

    def on_retriever_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)
```

注:若 langchain-core 的回调签名与上面不容(运行测试见真章),按已安装版本的 `BaseCallbackHandler` 实际签名微调形参,但保持 span 行为与测试断言不变。

- [ ] **Step 4:** `uv run pytest tests/test_obs_otel.py -v` → 7 passed;全套 `uv run pytest -q` 仍全绿。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/obs/otel.py tests/test_obs_otel.py
git commit -m "mvp-agentic-rag: OTelTraceCallback——LangChain 回调三边界翻译成 GenAI span"
```

---

### Task 4: backends.py 接线(TDD)

**Files:**
- Modify: `ai/langchain/mvp-agentic-rag/src/mvp_agentic_rag/obs/backends.py`
- Modify: `ai/langchain/mvp-agentic-rag/tests/test_obs_otel.py`(追加工厂测试)

- [ ] **Step 1: 追加失败测试**

```python
# tests/test_obs_otel.py 追加
from mvp_agentic_rag.obs.backends import get_observability_callbacks


def test_backend_otel_appends_otel_callback():
    s = _settings(langfuse_public_key="", langfuse_secret_key="")  # 无 key→控制台 exporter,无网络
    callbacks = get_observability_callbacks(s)
    assert any(type(c).__name__ == "OTelTraceCallback" for c in callbacks)


def test_backend_none_has_no_otel_callback():
    s = _settings(obs_backend="none")
    callbacks = get_observability_callbacks(s)
    assert not any(type(c).__name__ == "OTelTraceCallback" for c in callbacks)
```

注:`_settings(langfuse_public_key="")` 走 ConsoleSpanExporter 分支,测试静默(span 在 BatchSpanProcessor 缓冲里,进程内不打印就不污染输出;可接受)。

- [ ] **Step 2:** 跑测试确认失败(otel 分支不存在,第一条 fail)。

- [ ] **Step 3: backends.py 的 get_observability_callbacks 加分支**(在 langsmith 分支后):

```python
    elif backend == "otel":
        from mvp_agentic_rag.obs.otel import OTelTraceCallback, build_tracer

        callbacks.append(OTelTraceCallback(build_tracer(s)))
```

- [ ] **Step 4:** `uv run pytest -q` 全绿(新 9 条 + 既有)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/obs/backends.py tests/test_obs_otel.py
git commit -m "mvp-agentic-rag: OBS_BACKEND=otel 接线"
```

---

### Task 5: README 可观测节 + 文档说明

**Files:**
- Modify: `ai/langchain/mvp-agentic-rag/README.md`(「可观测切换」节)

- [ ] **Step 1:** README 可观测切换代码块加一行,并补一段说明:

```bash
OBS_BACKEND=otel        # OTel GenAI 语义约定 span,OTLP 导出(默认打到 Langfuse 的 /api/public/otel)
```

说明段(加在该节末尾):

```markdown
`otel` 后端是手写的 `OTelTraceCallback`(`obs/otel.py`):把 LangChain 回调的三边界(LLM 调用/工具/检索)翻译成 OTel GenAI 语义约定 span(`gen_ai.*`),`run_id/parent_run_id` 映射成 span 父子树。OTLP 出口指向哪个后端只由 env 决定——Langfuse、Phoenix、Jaeger、Datadog 都收 OTLP,换后端零代码改动。与 [agent-loop-lab](../../agent-loop-lab/) 的手动埋点是同一套语义约定的两种接入方式;现成替代品是 OpenInference/OpenLLMetry 的 LangChain instrumentor。
```

- [ ] **Step 2:** 校验链接 `ls ai/agent-loop-lab/README.md` 存在;通读改动处上下文无矛盾。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "mvp-agentic-rag: README 可观测节补 otel 后端说明"
```

---

### Task 6: 07/03 监控篇实战锚点回填

**Files:**
- Modify: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`(文末追加,不动原文)

- [ ] **Step 1:** 先读原文(确认追加位置在最后一节之后),文末追加:

```markdown

## 实战锚点(2026-06,亲手实现)

这一篇讲的 trace/监控,我在两套实现里各落地过一遍,同一套 OTel GenAI 语义约定(`gen_ai.*`):

- **手动埋点版**:[agent-loop-lab](../../agent-loop-lab/) —— 在自己写的 agent 循环里手动开三类 span:`invoke_agent`(根)→ `chat {model}`(挂 `gen_ai.usage.*` token 数)→ `execute_tool {name}`(挂 `gen_ai.tool.call.id`,失败置 ERROR status)。OTLP 导出到自托管 Langfuse(`{host}/api/public/otel`,Basic auth)。
- **框架翻译版**:[mvp-agentic-rag 的 `obs/otel.py`](../../langchain/mvp-agentic-rag/src/mvp_agentic_rag/obs/otel.py) —— 不碰业务代码,把 LangChain 回调三边界(LLM/工具/检索)翻译成同样的 span,`run_id/parent_run_id` 映射父子树;`OBS_BACKEND=otel` 一键启用,与 langfuse callback / LangSmith 后端并存可切。
- **三边界**指:模型调用(token/延迟/模型名)、工具调用(名字/错误)、检索(命中文档数)。无论用不用框架,trace 都打在这三个边界上——这是排查「质量/延迟/成本突变」时从症状定位到组件的最小坐标系。
- **换后端零代码**:OTLP 是中立协议,Langfuse/Phoenix/Jaeger/Datadog 都收;我项目里默认自托管 Langfuse,数据不出内网。
- **面试 30 秒**:「可观测我不绑定框架。三边界打 span、遵循 OTel GenAI 语义约定、OTLP 出口后端可换。我手写过 span 埋点,也写过把 LangChain 回调翻译成 OTel span 的 callback——两边在 Langfuse 里长一个样。」
- 〔待实测:真实 trace 树截图与单请求 span 数/延迟分布,跑通月 1 Task 1/8 后回填〕
```

- [ ] **Step 2:** 校验两个相对链接从该文件位置可达(`../../agent-loop-lab/`、`../../langchain/mvp-agentic-rag/src/mvp_agentic_rag/obs/otel.py`)。该文件若有未提交的用户改动,STOP 报 BLOCKED。

- [ ] **Step 3: Commit**

```bash
git add ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md
git commit -m "ml-to-llm-roadmap: 07/03 监控篇实战锚点(OTel 三边界两种接入)"
```

---

## 验收

- [ ] MVP `uv run pytest -q` 全绿(新增 9 条 OTel 测试 + 既有全部)
- [ ] `OBS_BACKEND=otel` 无 LANGFUSE_* key 时控制台回退,不抛错
- [ ] 现有 langfuse/langsmith 后端行为零变化(回归:既有 obs 相关测试不动且通过)
- [ ] 07/03 锚点链接全部可达,无编造数字(LLM 相关全部〔待实测〕)

## 不在本计划内

- 真实 Langfuse UI 验证 span 树(待用户环境,月 1 Task 1/8 一并)
- golden set 扩充、eval 真报告、judge 校准(月 3)
