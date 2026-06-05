# Agentic RAG MVP — Plan 2:Agent 图(LangGraph 核心) 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Plan 1 的检索通路之上,用 LangGraph 搭出「supervisor 路由 + kb_rag(CRAG 自纠正)子图 + web 子图 + PostgresSaver 持久化 + HITL 中断/恢复」的可运行 Agent 图,进程内 invoke 即可得到带引用的接地答案。

**Architecture:** 所有 LLM 决策(路由/文档评分/查询改写/答案生成/接地检查)抽象成可注入的小组件(Protocol + LLM 实现),图只负责编排。这样图的接线/路由/CRAG 循环/checkpoint/HITL 用确定性 stub + `InMemorySaver` 即可 hermetic 测试;只有 PostgresSaver 跨实例持久化用一个容器测试。LLM 提示质量不在本计划断言(留 Plan 4 eval)。

**Tech Stack:** 在 Plan 1 基础上新增 `langgraph` + `langgraph-checkpoint-postgres`;复用 langchain-openai(ChatOpenAI)、psycopg/pgvector、pytest + testcontainers。

---

## 上位文档
- 设计 spec:`docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`(§5.1 Agent 状态图、§5.3 持久化)
- 前置:Plan 1 已完成并合入 main(检索层 `HybridRetriever`、`retrieve_kb` 工具、`core/config.py`、`core/llm.py` 的 `get_embeddings`、`core/db.py` 的 `Database`、`tests/conftest.py` 的 `clean_db`/`fake_embeddings` 夹具)。
- 本计划只覆盖 Agent 图;API/流式/可观测/eval 在 Plan 3-4。

## 前置条件
- Plan 1 的环境(uv 项目、Docker)。`pgvector/pgvector:pg16` 镜像已在本地。
- LLM 提示质量的端到端验证需要真实 OpenAI 兼容 chat 端点 + key,**本计划不依赖它**(测试全用 stub/fake)。

## 文件结构(本计划产出 / 修改)
```
ai/langchain/mvp-agentic-rag/
├─ pyproject.toml                         (修改:加 langgraph 依赖)
├─ .env.example                           (修改:加 LLM_* chat 配置)
├─ src/mvp_agentic_rag/
│  ├─ core/
│  │  ├─ config.py                        (修改:加 llm_base_url/api_key/model)
│  │  └─ llm.py                           (修改:加 get_chat_model)
│  ├─ agent/
│  │  ├─ state.py                         (新:AgentState + KBRagState)
│  │  ├─ components.py                    (新:决策 Protocol + Pydantic schema + LLM 实现)
│  │  ├─ supervisor.py                    (新:make_supervisor_node)
│  │  ├─ human_review.py                  (新:HITL interrupt 节点)
│  │  ├─ graph.py                         (新:build_agent_graph 顶层装配)
│  │  ├─ factory.py                       (新:build_production_agent_graph from config)
│  │  ├─ tools.py                         (修改:加 web_search stub 工具)
│  │  └─ subgraphs/
│  │     ├─ __init__.py                   (新)
│  │     ├─ kb_rag.py                     (新:CRAG 子图)
│  │     └─ web.py                        (新:create_react_agent 工厂)
└─ tests/
   ├─ fakes.py                            (新:FakeLLM / 各决策 stub)
   ├─ test_chat_model.py                  (新)
   ├─ test_agent_state.py                 (新)
   ├─ test_components.py                  (新)
   ├─ test_kb_rag.py                      (新)
   ├─ test_supervisor.py                  (新)
   ├─ test_graph.py                       (新)
   ├─ test_hitl.py                        (新)
   └─ test_postgres_checkpoint.py         (新)
```

> 约定:命令都在 `ai/langchain/mvp-agentic-rag/` 下执行。

---

### Task 1: 新增 LangGraph 依赖 + Chat 模型配置与工厂

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `src/mvp_agentic_rag/core/config.py`
- Modify: `src/mvp_agentic_rag/core/llm.py`
- Test: `tests/test_chat_model.py`

- [ ] **Step 1: 加依赖**

Run: `cd ai/langchain/mvp-agentic-rag && uv add langgraph langgraph-checkpoint-postgres`
Expected: 解析并写入 `pyproject.toml` + `uv.lock`,安装成功。

- [ ] **Step 2: 写失败测试 `tests/test_chat_model.py`**

```python
def test_settings_has_llm_fields(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "my-chat")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings

    s = Settings()
    assert s.llm_base_url == "http://x/v1"
    assert s.llm_model == "my-chat"


def test_get_chat_model_uses_config(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "my-chat")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings
    from mvp_agentic_rag.core.llm import get_chat_model

    chat = get_chat_model(Settings())
    assert chat.model_name == "my-chat"
    assert str(chat.openai_api_base) == "http://x/v1"
```

- [ ] **Step 3: 运行测试,确认失败**

Run: `uv run pytest tests/test_chat_model.py -v`
Expected: FAIL（`Settings` 无 `llm_base_url` / 无 `get_chat_model`）。

- [ ] **Step 4: 扩展 `src/mvp_agentic_rag/core/config.py`（在 Embedding 字段后加入 LLM 字段）**

在 `embed_dim: int = 1536` 这一行后面追加:
```python
    # Chat LLM(OpenAI 兼容)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_model_fallback: str = "gpt-4o-mini"
```

- [ ] **Step 5: 扩展 `src/mvp_agentic_rag/core/llm.py`（追加 chat 工厂）**

在文件末尾追加:
```python
from langchain_openai import ChatOpenAI


def get_chat_model(settings: Settings | None = None, *, model: str | None = None) -> ChatOpenAI:
    s = settings or get_settings()
    return ChatOpenAI(
        model=model or s.llm_model,
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        temperature=0,
        timeout=30,
        max_retries=2,
    )
```
（`from langchain_openai import OpenAIEmbeddings` 已在文件顶部;新增的 `ChatOpenAI` import 放文件末尾追加块或并入顶部 import 均可。）

- [ ] **Step 6: 更新 `.env.example`（在 EMBED_DIM 行后追加）**

```bash
# ---- Chat LLM(OpenAI 兼容)----
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-replace-me
LLM_MODEL=gpt-4o-mini
LLM_MODEL_FALLBACK=gpt-4o-mini
```

- [ ] **Step 7: 运行测试,确认通过**

Run: `uv run pytest tests/test_chat_model.py -v`
Expected: PASS（2 passed）。若 `ChatOpenAI` 的属性名在该版本不同（如 `model_name` vs `model`、`openai_api_base`），按红灯调整**断言**读取正确属性,保持工厂实现不变,并记为 concern。

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock .env.example src/mvp_agentic_rag/core/config.py src/mvp_agentic_rag/core/llm.py tests/test_chat_model.py
git commit -m "mvp-agentic-rag: Plan2 Task1 LangGraph 依赖 + chat 模型配置与工厂"
```

---

### Task 2: Agent 状态(AgentState + KBRagState)

**Files:**
- Create: `src/mvp_agentic_rag/agent/state.py`
- Test: `tests/test_agent_state.py`

> `agent/__init__.py` 在 Plan 1 已存在。

- [ ] **Step 1: 写失败测试 `tests/test_agent_state.py`**

```python
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import START, END, StateGraph


def test_agent_state_messages_accumulate():
    from mvp_agentic_rag.agent.state import AgentState

    def add_ai(state):
        return {"messages": [AIMessage(content="hi")]}

    g = StateGraph(AgentState)
    g.add_node("add_ai", add_ai)
    g.add_edge(START, "add_ai")
    g.add_edge("add_ai", END)
    app = g.compile()

    out = app.invoke({"messages": [HumanMessage(content="hello")], "next": "", "citations": [], "step_budget": 3})
    # add_messages reducer 追加,而不是替换
    assert [m.content for m in out["messages"]] == ["hello", "hi"]


def test_kb_rag_state_importable():
    from mvp_agentic_rag.agent.state import KBRagState
    # TypedDict:实例化为普通 dict 即可
    s: KBRagState = {"query": "q", "chunks": [], "rewrites": 0,
                     "relevant": False, "answer": "", "citations": [], "grounded": False}
    assert s["query"] == "q"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_agent_state.py -v`
Expected: FAIL（无 `agent.state`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/agent/state.py`**

```python
from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    citations: list[dict]
    step_budget: int


class KBRagState(TypedDict):
    query: str
    chunks: list          # list[RetrievedChunk]
    rewrites: int
    relevant: bool
    answer: str
    citations: list[dict]
    grounded: bool
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_agent_state.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/agent/state.py tests/test_agent_state.py
git commit -m "mvp-agentic-rag: Plan2 Task2 Agent 状态(AgentState + KBRagState)"
```

---

### Task 3: 决策组件(Protocol + Pydantic schema + LLM 实现)

**Files:**
- Create: `src/mvp_agentic_rag/agent/components.py`
- Create: `tests/fakes.py`
- Test: `tests/test_components.py`

- [ ] **Step 1: 写测试替身 `tests/fakes.py`**

```python
from langchain_core.messages import AIMessage


class _FakeStructured:
    """模拟 llm.with_structured_output(Schema) 返回的 runnable。"""

    def __init__(self, value):
        self._value = value

    def invoke(self, messages):
        return self._value


class FakeLLM:
    """Chat 模型测试替身。
    - with_structured_output(Schema).invoke(...) 返回预置 structured_value
    - invoke(...) 返回 AIMessage(content=text)
    """

    def __init__(self, *, structured_value=None, text=""):
        self._structured_value = structured_value
        self._text = text

    def with_structured_output(self, schema):
        return _FakeStructured(self._structured_value)

    def invoke(self, messages):
        return AIMessage(content=self._text)
```

- [ ] **Step 2: 写失败测试 `tests/test_components.py`**

```python
from mvp_agentic_rag.retrieval.types import RetrievedChunk
from tests.fakes import FakeLLM


def _chunk(i, content):
    return RetrievedChunk(id=i, doc_id="d", chunk_idx=i, content=content, metadata={})


def test_llm_router_returns_decision():
    from mvp_agentic_rag.agent.components import LLMRouter, RouteDecision

    router = LLMRouter(FakeLLM(structured_value=RouteDecision(next="kb_rag")))
    assert router.route([]) == "kb_rag"


def test_llm_doc_grader_returns_bool():
    from mvp_agentic_rag.agent.components import LLMDocGrader, GradeDecision

    grader = LLMDocGrader(FakeLLM(structured_value=GradeDecision(relevant=True)))
    assert grader.grade("q", [_chunk(1, "c")]) is True


def test_llm_query_rewriter_returns_text():
    from mvp_agentic_rag.agent.components import LLMQueryRewriter

    rw = LLMQueryRewriter(FakeLLM(text="rephrased query"))
    assert rw.rewrite("orig") == "rephrased query"


def test_llm_answer_generator_returns_text():
    from mvp_agentic_rag.agent.components import LLMAnswerGenerator

    gen = LLMAnswerGenerator(FakeLLM(text="answer [1]"))
    assert gen.generate("q", [_chunk(1, "c")]) == "answer [1]"


def test_llm_grounding_checker_returns_bool():
    from mvp_agentic_rag.agent.components import LLMGroundingChecker, GroundingDecision

    g = LLMGroundingChecker(FakeLLM(structured_value=GroundingDecision(grounded=False)))
    assert g.check("ans", [_chunk(1, "c")]) is False
```

- [ ] **Step 3: 运行测试,确认失败**

Run: `uv run pytest tests/test_components.py -v`
Expected: FAIL（无 `agent.components`）。

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/agent/components.py`**

```python
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from mvp_agentic_rag.retrieval.types import RetrievedChunk


# ---- 结构化输出 schema ----
class RouteDecision(BaseModel):
    next: str = Field(description="下一步交给谁,取值之一:kb_rag / web / FINISH")


class GradeDecision(BaseModel):
    relevant: bool = Field(description="检索片段是否与问题相关")


class GroundingDecision(BaseModel):
    grounded: bool = Field(description="答案是否被检索片段支持(无幻觉)")


# ---- 决策接口(便于测试注入)----
class Router(Protocol):
    def route(self, messages: list) -> str: ...


class DocGrader(Protocol):
    def grade(self, query: str, chunks: list[RetrievedChunk]) -> bool: ...


class QueryRewriter(Protocol):
    def rewrite(self, query: str) -> str: ...


class AnswerGenerator(Protocol):
    def generate(self, query: str, chunks: list[RetrievedChunk]) -> str: ...


class GroundingChecker(Protocol):
    def check(self, answer: str, chunks: list[RetrievedChunk]) -> bool: ...


def _format(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))


# ---- LLM 实现 ----
_ROUTER_SYS = (
    "你是一个多 Agent 调度器。根据对话,决定下一步:\n"
    "- kb_rag:问题需要查企业知识库\n"
    "- web:问题超出知识库范围,需要外部信息\n"
    "- FINISH:已经有了足够的最终答案\n"
    "只输出路由决策。"
)


class LLMRouter:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(RouteDecision)

    def route(self, messages: list) -> str:
        out = self._llm.invoke([SystemMessage(content=_ROUTER_SYS), *messages])
        return out.next


_GRADER_SYS = "你判断检索到的片段是否与用户问题相关。只输出布尔判断。"


class LLMDocGrader:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(GradeDecision)

    def grade(self, query: str, chunks: list[RetrievedChunk]) -> bool:
        prompt = f"问题:{query}\n\n检索片段:\n{_format(chunks)}\n\n这些片段相关吗?"
        return self._llm.invoke([SystemMessage(content=_GRADER_SYS), HumanMessage(content=prompt)]).relevant


_REWRITER_SYS = "你把用户问题改写得更利于检索(澄清意图、补全关键词)。只输出改写后的问题。"


class LLMQueryRewriter:
    def __init__(self, llm):
        self._llm = llm

    def rewrite(self, query: str) -> str:
        out = self._llm.invoke([SystemMessage(content=_REWRITER_SYS), HumanMessage(content=query)])
        return out.content


_GEN_SYS = (
    "你是企业知识库助手。只依据给定片段回答,并用 [n] 标注引用的片段编号。"
    "若片段不足以回答,明确说明依据不足。"
)


class LLMAnswerGenerator:
    def __init__(self, llm):
        self._llm = llm

    def generate(self, query: str, chunks: list[RetrievedChunk]) -> str:
        prompt = f"问题:{query}\n\n可用片段:\n{_format(chunks)}\n\n请作答并标注引用。"
        return self._llm.invoke([SystemMessage(content=_GEN_SYS), HumanMessage(content=prompt)]).content


_GROUND_SYS = "你判断答案是否完全被给定片段支持(无编造)。只输出布尔判断。"


class LLMGroundingChecker:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(GroundingDecision)

    def check(self, answer: str, chunks: list[RetrievedChunk]) -> bool:
        prompt = f"答案:{answer}\n\n片段:\n{_format(chunks)}\n\n答案是否被片段支持?"
        return self._llm.invoke([SystemMessage(content=_GROUND_SYS), HumanMessage(content=prompt)]).grounded
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_components.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/agent/components.py tests/fakes.py tests/test_components.py
git commit -m "mvp-agentic-rag: Plan2 Task3 决策组件(Protocol + schema + LLM 实现)"
```

---

### Task 4: kb_rag CRAG 子图

**Files:**
- Create: `src/mvp_agentic_rag/agent/subgraphs/__init__.py`
- Create: `src/mvp_agentic_rag/agent/subgraphs/kb_rag.py`
- Test: `tests/test_kb_rag.py`

> 流程:retrieve → grade →(相关:generate / 不相关且有改写预算:rewrite→retrieve / 不相关且无预算:hedge)→ generate → grounding_check →(接地:END / 不接地且有预算:rewrite / 不接地且无预算:hedge)。用脚本化 stub 组件断言三条路径。

- [ ] **Step 1: 写失败测试 `tests/test_kb_rag.py`**

```python
from mvp_agentic_rag.retrieval.types import RetrievedChunk


def _chunk(i, content="c"):
    return RetrievedChunk(id=i, doc_id=f"doc{i}.md", chunk_idx=i, content=content, metadata={})


class StubRetriever:
    def __init__(self):
        self.calls = 0

    def retrieve(self, query):
        self.calls += 1
        return [_chunk(1, "kubernetes autoscaling uses HPA")]


class ScriptedGrader:
    """按调用顺序返回脚本化的 relevant 值。"""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def grade(self, query, chunks):
        v = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return v


class StubRewriter:
    def __init__(self):
        self.calls = 0

    def rewrite(self, query):
        self.calls += 1
        return query + " (rewritten)"


class StubGenerator:
    def generate(self, query, chunks):
        return "HPA scales pods [1]"


class ScriptedGrounder:
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def check(self, answer, chunks):
        v = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        return v


def _build(grader, grounder, rewriter=None, retriever=None, max_rewrites=1):
    from mvp_agentic_rag.agent.subgraphs.kb_rag import build_kb_rag_subgraph

    return build_kb_rag_subgraph(
        retriever=retriever or StubRetriever(),
        grader=grader,
        rewriter=rewriter or StubRewriter(),
        generator=StubGenerator(),
        grounder=grounder,
        max_rewrites=max_rewrites,
    )


def test_happy_path_relevant_and_grounded():
    app = _build(ScriptedGrader([True]), ScriptedGrounder([True]))
    out = app.invoke({"query": "how does autoscaling work", "rewrites": 0})
    assert out["answer"] == "HPA scales pods [1]"
    assert out["grounded"] is True
    assert out["citations"][0]["doc_id"] == "doc1.md"


def test_not_relevant_triggers_rewrite_then_succeeds():
    retriever = StubRetriever()
    rewriter = StubRewriter()
    app = _build(ScriptedGrader([False, True]), ScriptedGrounder([True]),
                 rewriter=rewriter, retriever=retriever, max_rewrites=1)
    out = app.invoke({"query": "q", "rewrites": 0})
    assert rewriter.calls == 1          # 改写过一次
    assert retriever.calls == 2          # 重新检索过
    assert out["answer"] == "HPA scales pods [1]"


def test_not_grounded_then_rewrite_succeeds():
    # 接地失败 → 改写重试 → 第二轮接地成功(覆盖 grounding 重试成功子路径)
    retriever = StubRetriever()
    rewriter = StubRewriter()
    app = _build(ScriptedGrader([True, True]), ScriptedGrounder([False, True]),
                 rewriter=rewriter, retriever=retriever, max_rewrites=1)
    out = app.invoke({"query": "q", "rewrites": 0})
    assert rewriter.calls == 1
    assert retriever.calls == 2
    assert out["answer"] == "HPA scales pods [1]"
    assert out["grounded"] is True


def test_not_grounded_no_budget_hedges():
    app = _build(ScriptedGrader([True]), ScriptedGrounder([False]), max_rewrites=0)
    out = app.invoke({"query": "q", "rewrites": 0})
    assert "依据不足" in out["answer"]
    assert out["citations"] == []
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_kb_rag.py -v`
Expected: FAIL（无 `agent.subgraphs.kb_rag`）。

- [ ] **Step 3: 创建 `src/mvp_agentic_rag/agent/subgraphs/__init__.py`(空文件)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/agent/subgraphs/kb_rag.py`**

```python
from langgraph.graph import END, START, StateGraph

from mvp_agentic_rag.agent.state import KBRagState

HEDGE_ANSWER = "未找到足够依据,无法可靠回答(依据不足)。"


def build_kb_rag_subgraph(retriever, grader, rewriter, generator, grounder, max_rewrites: int = 1):
    def retrieve(state: KBRagState) -> dict:
        return {"chunks": retriever.retrieve(state["query"])}

    def grade(state: KBRagState) -> dict:
        return {"relevant": grader.grade(state["query"], state["chunks"])}

    def rewrite(state: KBRagState) -> dict:
        return {"query": rewriter.rewrite(state["query"]), "rewrites": state["rewrites"] + 1}

    def generate(state: KBRagState) -> dict:
        chunks = state["chunks"]
        citations = [
            {"doc_id": c.doc_id, "chunk_idx": c.chunk_idx, "content": c.content} for c in chunks
        ]
        return {"answer": generator.generate(state["query"], chunks), "citations": citations}

    def grounding_check(state: KBRagState) -> dict:
        return {"grounded": grounder.check(state["answer"], state["chunks"])}

    def hedge(state: KBRagState) -> dict:
        return {"answer": HEDGE_ANSWER, "citations": [], "grounded": False}

    def after_grade(state: KBRagState) -> str:
        if state["relevant"]:
            return "generate"
        if state["rewrites"] < max_rewrites:
            return "rewrite"
        return "hedge"

    def after_grounding(state: KBRagState) -> str:
        if state["grounded"]:
            return "done"
        if state["rewrites"] < max_rewrites:
            return "rewrite"
        return "hedge"

    g = StateGraph(KBRagState)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("rewrite", rewrite)
    g.add_node("generate", generate)
    g.add_node("grounding_check", grounding_check)
    g.add_node("hedge", hedge)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", after_grade,
                            {"generate": "generate", "rewrite": "rewrite", "hedge": "hedge"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("generate", "grounding_check")
    g.add_conditional_edges("grounding_check", after_grounding,
                            {"done": END, "rewrite": "rewrite", "hedge": "hedge"})
    g.add_edge("hedge", END)
    return g.compile()
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_kb_rag.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/agent/subgraphs/__init__.py src/mvp_agentic_rag/agent/subgraphs/kb_rag.py tests/test_kb_rag.py
git commit -m "mvp-agentic-rag: Plan2 Task4 kb_rag CRAG 子图"
```

---

### Task 5: supervisor 节点

**Files:**
- Create: `src/mvp_agentic_rag/agent/supervisor.py`
- Test: `tests/test_supervisor.py`

- [ ] **Step 1: 写失败测试 `tests/test_supervisor.py`**

```python
class StubRouter:
    def __init__(self, decision):
        self.decision = decision

    def route(self, messages):
        return self.decision


def test_supervisor_routes_and_decrements_budget():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("kb_rag"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 3})
    assert out["next"] == "kb_rag"
    assert out["step_budget"] == 2


def test_supervisor_finishes_when_budget_exhausted():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("kb_rag"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 0})
    assert out["next"] == "FINISH"


def test_supervisor_coerces_invalid_route_to_finish():
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node

    node = make_supervisor_node(StubRouter("nonsense"))
    out = node({"messages": [], "next": "", "citations": [], "step_budget": 3})
    assert out["next"] == "FINISH"
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_supervisor.py -v`
Expected: FAIL（无 `agent.supervisor`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/agent/supervisor.py`**

```python
DEFAULT_MEMBERS = ("kb_rag", "web", "human_review")


def make_supervisor_node(router, *, members: tuple[str, ...] = DEFAULT_MEMBERS):
    valid = set(members) | {"FINISH"}

    def supervisor(state) -> dict:
        if state.get("step_budget", 0) <= 0:
            return {"next": "FINISH"}
        decision = router.route(list(state["messages"]))
        if decision not in valid:
            decision = "FINISH"
        return {"next": decision, "step_budget": state["step_budget"] - 1}

    return supervisor
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_supervisor.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/agent/supervisor.py tests/test_supervisor.py
git commit -m "mvp-agentic-rag: Plan2 Task5 supervisor 节点"
```

---

### Task 6: web 专家(create_react_agent 工厂)+ web_search stub 工具

**Files:**
- Modify: `src/mvp_agentic_rag/agent/tools.py`
- Create: `src/mvp_agentic_rag/agent/subgraphs/web.py`
- Test: `tests/test_web_agent.py`

> create_react_agent 的真实工具调用循环需要支持 tool-calling 的真模型,难以 hermetic 伪造。本任务只做**构造冒烟**(工厂可调用、web_search 工具形态正确);真实 react 行为留待 live/eval(Plan 4)。顶层图测试(Task 7)用 stub web runnable,不依赖本工厂。

- [ ] **Step 1: 写失败测试 `tests/test_web_agent.py`**

```python
def test_web_search_tool_shape():
    from mvp_agentic_rag.agent.tools import web_search

    assert web_search.name == "web_search"
    assert web_search.description
    out = web_search.invoke({"query": "weather"})
    assert isinstance(out, str)


def test_build_web_agent_is_callable():
    # 仅验证工厂存在且可导入(构造需要真模型,不在此断言行为)
    from mvp_agentic_rag.agent.subgraphs.web import build_web_agent

    assert callable(build_web_agent)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_web_agent.py -v`
Expected: FAIL（无 `web_search` / 无 `agent.subgraphs.web`）。

- [ ] **Step 3: 在 `src/mvp_agentic_rag/agent/tools.py` 末尾追加 web_search stub 工具**

```python
@tool
def web_search(query: str) -> str:
    """当问题超出企业知识库范围、需要外部/实时信息时,搜索网络。"""
    # MVP 占位实现:接入真实搜索 API(Tavily/DuckDuckGo)时替换这里。
    return f"[web_search 占位结果] 关于「{query}」的外部信息暂未接入真实搜索。"
```
（`from langchain_core.tools import tool` 需在文件顶部 import;若 Plan 1 的 tools.py 只 import 了 `StructuredTool`,则补充 `tool`。)

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/agent/subgraphs/web.py`**

```python
from langgraph.prebuilt import create_react_agent


def build_web_agent(chat_model, tools):
    """库外/兜底专家:预构建 ReAct agent。
    生产用真实 chat 模型 + web_search 等工具;返回一个可 invoke({"messages": [...]}) 的图。"""
    return create_react_agent(chat_model, tools)
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_web_agent.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/agent/tools.py src/mvp_agentic_rag/agent/subgraphs/web.py tests/test_web_agent.py
git commit -m "mvp-agentic-rag: Plan2 Task6 web 专家工厂 + web_search stub"
```

---

### Task 7: 顶层图装配(supervisor + 子图 + InMemorySaver)

**Files:**
- Create: `src/mvp_agentic_rag/agent/graph.py`
- Test: `tests/test_graph.py`

> kb_rag 子图与顶层 state 不同 schema,用包装节点把 messages→query、answer→messages 转换。web 分支注入一个 stub runnable(返回 `{"messages": [...]}`)。human_review 节点在 Task 8 接入;本任务先不路由到它。

- [ ] **Step 1: 写失败测试 `tests/test_graph.py`**

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver


class SeqRouter:
    """按调用顺序返回路由,最后停在 FINISH。"""

    def __init__(self, seq):
        self._seq = list(seq)
        self.calls = 0

    def route(self, messages):
        v = self._seq[min(self.calls, len(self._seq) - 1)]
        self.calls += 1
        return v


class StubKBRag:
    """模拟编译后的 kb_rag 子图:invoke 返回带 answer + citations 的 dict。"""

    def invoke(self, state, *args, **kwargs):
        return {"answer": "HPA scales pods [1]",
                "citations": [{"doc_id": "k8s.md", "chunk_idx": 0, "content": "HPA"}]}


class StubWeb:
    def invoke(self, state, *args, **kwargs):
        return {"messages": [AIMessage(content="external answer")]}


def _build(router, checkpointer):
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node
    from mvp_agentic_rag.agent.graph import build_agent_graph

    return build_agent_graph(
        supervisor_node=make_supervisor_node(router),
        kb_rag_runnable=StubKBRag(),
        web_runnable=StubWeb(),
        checkpointer=checkpointer,
    )


def _config(tid="t1"):
    return {"configurable": {"thread_id": tid}}


def test_route_to_kb_rag_returns_grounded_answer():
    app = _build(SeqRouter(["kb_rag", "FINISH"]), InMemorySaver())
    out = app.invoke({"messages": [HumanMessage(content="autoscaling?")],
                      "next": "", "citations": [], "step_budget": 5}, _config("t1"))
    contents = [m.content for m in out["messages"]]
    assert "HPA scales pods [1]" in contents
    assert out["citations"][0]["doc_id"] == "k8s.md"


def test_route_to_web():
    app = _build(SeqRouter(["web", "FINISH"]), InMemorySaver())
    out = app.invoke({"messages": [HumanMessage(content="today's news?")],
                      "next": "", "citations": [], "step_budget": 5}, _config("t2"))
    contents = [m.content for m in out["messages"]]
    assert "external answer" in contents


def test_budget_forces_finish():
    # step_budget=1:supervisor 第一次路由后预算归零,kb_rag 跑一次后第二次进 supervisor 即 FINISH
    app = _build(SeqRouter(["kb_rag", "kb_rag", "kb_rag"]), InMemorySaver())
    out = app.invoke({"messages": [HumanMessage(content="q")],
                      "next": "", "citations": [], "step_budget": 1}, _config("t3"))
    # 不应无限循环;能正常结束
    assert any("HPA scales pods" in m.content for m in out["messages"])
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL（无 `agent.graph`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/agent/graph.py`**

```python
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from mvp_agentic_rag.agent.state import AgentState


def _last_human_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return messages[-1].content if messages else ""


def build_agent_graph(supervisor_node, kb_rag_runnable, web_runnable, checkpointer):
    def kb_rag_node(state: AgentState) -> dict:
        query = _last_human_text(state["messages"])
        result = kb_rag_runnable.invoke({"query": query, "rewrites": 0})
        return {
            "messages": [AIMessage(content=result["answer"])],
            "citations": result.get("citations", []),
        }

    def web_node(state: AgentState) -> dict:
        result = web_runnable.invoke({"messages": list(state["messages"])})
        last = result["messages"][-1]
        content = last.content if hasattr(last, "content") else str(last)
        return {"messages": [AIMessage(content=content)]}

    def route(state: AgentState) -> str:
        return state["next"]

    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor_node)
    g.add_node("kb_rag", kb_rag_node)
    g.add_node("web", web_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route,
                            {"kb_rag": "kb_rag", "web": "web", "FINISH": END})
    g.add_edge("kb_rag", "supervisor")
    g.add_edge("web", "supervisor")
    return g.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_graph.py -v`
Expected: PASS（3 passed）。若遇到递归上限错误,确认 `step_budget` 与 SeqRouter 的 FINISH 能终止;必要时在 invoke 的 config 里加 `"recursion_limit": 25`(默认应足够)。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/agent/graph.py tests/test_graph.py
git commit -m "mvp-agentic-rag: Plan2 Task7 顶层图装配(supervisor + 子图)"
```

---

### Task 8: HITL 人工审核(interrupt / resume)

**Files:**
- Create: `src/mvp_agentic_rag/agent/human_review.py`
- Modify: `src/mvp_agentic_rag/agent/graph.py`
- Test: `tests/test_hitl.py`

> 在顶层图加入 `human_review` 节点与路由。supervisor 路由到它时,节点调用 `interrupt(...)` 暂停;用 `Command(resume=...)` 恢复。用 `InMemorySaver` + thread_id 测试。

- [ ] **Step 1: 写失败测试 `tests/test_hitl.py`**

```python
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


class SeqRouter:
    def __init__(self, seq):
        self._seq = list(seq)
        self.calls = 0

    def route(self, messages):
        v = self._seq[min(self.calls, len(self._seq) - 1)]
        self.calls += 1
        return v


class StubKBRag:
    def invoke(self, state, *a, **k):
        return {"answer": "ans [1]", "citations": []}


class StubWeb:
    def invoke(self, state, *a, **k):
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="web")]}


def _app(router):
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node
    from mvp_agentic_rag.agent.graph import build_agent_graph
    return build_agent_graph(make_supervisor_node(router), StubKBRag(), StubWeb(), InMemorySaver())


def test_hitl_interrupts_then_resumes():
    app = _app(SeqRouter(["human_review", "FINISH"]))
    config = {"configurable": {"thread_id": "h1"}}

    result = app.invoke(
        {"messages": [HumanMessage(content="delete prod db")], "next": "", "citations": [], "step_budget": 5},
        config,
    )
    # 第一次 invoke 应在 human_review 处中断
    assert "__interrupt__" in result

    # 人工批准后恢复
    final = app.invoke(Command(resume="approved"), config)
    contents = [m.content for m in final["messages"]]
    assert any("approved" in c for c in contents)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_hitl.py -v`
Expected: FAIL（无 `agent.human_review` / 图未路由 human_review）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/agent/human_review.py`**

```python
from langchain_core.messages import AIMessage
from langgraph.types import interrupt


def human_review_node(state) -> dict:
    """敏感动作前暂停,等待人工决定。interrupt 的返回值即 Command(resume=...) 传入的值。"""
    decision = interrupt(
        {"reason": "需要人工审核的敏感动作", "pending": _last_text(state["messages"])}
    )
    return {"messages": [AIMessage(content=f"[人工审核:{decision}] 已按审核结果处理。")], "next": "FINISH"}


def _last_text(messages) -> str:
    return messages[-1].content if messages else ""
```

- [ ] **Step 4: 修改 `src/mvp_agentic_rag/agent/graph.py` 接入 human_review**

在 `build_agent_graph` 内,`g.add_node("web", web_node)` 之后加入 human_review 节点;并把它加入路由映射与回边。具体改动:

在 import 区加:
```python
from mvp_agentic_rag.agent.human_review import human_review_node
```
在 `g.add_node("web", web_node)` 下一行加:
```python
    g.add_node("human_review", human_review_node)
```
把路由映射那行改为(增加 human_review):
```python
    g.add_conditional_edges("supervisor", route,
                            {"kb_rag": "kb_rag", "web": "web",
                             "human_review": "human_review", "FINISH": END})
```
在 `g.add_edge("web", "supervisor")` 下一行加:
```python
    g.add_edge("human_review", "supervisor")
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_hitl.py -v`
Expected: PASS（1 passed）。若 `"__interrupt__" in result` 的检测方式在该 langgraph 版本不同,改用 `state = app.get_state(config); assert state.next` 非空 来判定中断,再 resume;记为 concern。

- [ ] **Step 6: 回归确认 Task 7 的图测试仍通过**

Run: `uv run pytest tests/test_graph.py -v`
Expected: PASS（3 passed;新增 human_review 路由不影响既有路径）。

- [ ] **Step 7: Commit**

```bash
git add src/mvp_agentic_rag/agent/human_review.py src/mvp_agentic_rag/agent/graph.py tests/test_hitl.py
git commit -m "mvp-agentic-rag: Plan2 Task8 HITL 人工审核(interrupt/resume)"
```

---

### Task 9: PostgresSaver 持久化 + 生产工厂

**Files:**
- Create: `src/mvp_agentic_rag/agent/factory.py`
- Test: `tests/test_postgres_checkpoint.py`

> 持久化测试用真实 pgvector 容器(复用 conftest 的 `conninfo` 夹具)验证「checkpoint 跨图实例存活」。生产工厂把真实组件从 config 装配,只做 import 冒烟(真实 chat 调用需 key)。

- [ ] **Step 1: 写失败测试 `tests/test_postgres_checkpoint.py`**

```python
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver


class SeqRouter:
    def __init__(self, seq):
        self._seq = list(seq)
        self.calls = 0

    def route(self, messages):
        v = self._seq[min(self.calls, len(self._seq) - 1)]
        self.calls += 1
        return v


class StubKBRag:
    def invoke(self, state, *a, **k):
        return {"answer": "persisted answer [1]", "citations": []}


class StubWeb:
    def invoke(self, state, *a, **k):
        from langchain_core.messages import AIMessage
        return {"messages": [AIMessage(content="web")]}


def _build(checkpointer):
    from mvp_agentic_rag.agent.supervisor import make_supervisor_node
    from mvp_agentic_rag.agent.graph import build_agent_graph
    return build_agent_graph(make_supervisor_node(SeqRouter(["kb_rag", "FINISH"])),
                             StubKBRag(), StubWeb(), checkpointer)


def test_checkpoint_persists_across_graph_instances(conninfo):
    config = {"configurable": {"thread_id": "persist-1"}}

    # 实例 1:跑一轮,状态写入 Postgres
    with PostgresSaver.from_conn_string(conninfo) as cp:
        cp.setup()
        app1 = _build(cp)
        app1.invoke({"messages": [HumanMessage(content="q")], "next": "",
                     "citations": [], "step_budget": 5}, config)

    # 实例 2:全新图 + 全新 PostgresSaver,同一 thread_id 应能读回历史
    with PostgresSaver.from_conn_string(conninfo) as cp2:
        app2 = _build(cp2)
        state = app2.get_state(config)
        contents = [m.content for m in state.values["messages"]]
        assert any("persisted answer" in c for c in contents)
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_postgres_checkpoint.py -v`
Expected: FAIL（首次因生产工厂 import 链或 PostgresSaver 用法报错;若仅 factory 缺失不影响本测试,则本测试可能直接因断言/表未建而失败 → 进入实现修正)。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/agent/factory.py`**

```python
from mvp_agentic_rag.agent.components import (
    LLMAnswerGenerator,
    LLMDocGrader,
    LLMGroundingChecker,
    LLMQueryRewriter,
    LLMRouter,
)
from mvp_agentic_rag.agent.graph import build_agent_graph
from mvp_agentic_rag.agent.subgraphs.kb_rag import build_kb_rag_subgraph
from mvp_agentic_rag.agent.subgraphs.web import build_web_agent
from mvp_agentic_rag.agent.supervisor import make_supervisor_node
from mvp_agentic_rag.agent.tools import make_retrieve_kb_tool, web_search
from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.core.llm import get_chat_model
from mvp_agentic_rag.retrieval.factory import build_hybrid_retriever


def build_production_agent_graph(db: Database, checkpointer, settings: Settings | None = None):
    s = settings or get_settings()
    chat = get_chat_model(s)
    retriever = build_hybrid_retriever(db, s)

    kb_rag = build_kb_rag_subgraph(
        retriever=retriever,
        grader=LLMDocGrader(chat),
        rewriter=LLMQueryRewriter(chat),
        generator=LLMAnswerGenerator(chat),
        grounder=LLMGroundingChecker(chat),
    )
    web = build_web_agent(chat, [make_retrieve_kb_tool(retriever), web_search])
    supervisor = make_supervisor_node(LLMRouter(chat))
    return build_agent_graph(supervisor, kb_rag, web, checkpointer)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_postgres_checkpoint.py -v`
Expected: PASS（1 passed;容器启动 + checkpoint 持久化验证）。若 `PostgresSaver.from_conn_string` 对 conninfo 的格式有要求(如需 `?sslmode=disable`),按错误调整测试里的连接串;若该版本 `get_state(...).values` 结构不同,按实际读取 messages,记为 concern。

- [ ] **Step 5: 生产工厂 import 冒烟**

Run: `uv run python -c "import mvp_agentic_rag.agent.factory; print('factory ok')"`
Expected: 打印 `factory ok`(仅 import,不连 DB / 不调 LLM)。

- [ ] **Step 6: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿（Plan 1 的 18 + Plan 2 各任务测试）。

- [ ] **Step 7: Commit**

```bash
git add src/mvp_agentic_rag/agent/factory.py tests/test_postgres_checkpoint.py
git commit -m "mvp-agentic-rag: Plan2 Task9 PostgresSaver 持久化 + 生产工厂"
```

---

## 完成定义(Plan 2)
- `make test` 全绿且 hermetic:图的路由、CRAG 自纠正循环(相关/改写重试/接地兜底)、supervisor 预算护栏、HITL 中断+恢复 都用 stub + InMemorySaver 断言;PostgresSaver 跨实例持久化用容器断言。
- 进程内可装配生产 Agent 图:`build_production_agent_graph(db, checkpointer)` 从 config 接真实 LLM 组件(import 冒烟通过)。
- 交付物:可被 Plan 3(FastAPI/流式/可观测)直接挂载的编译图 + checkpointer。
- 真实 LLM 端到端(路由/作答质量)留待 Plan 4 eval 与 live 冒烟(需 `.env` 的 `LLM_*` key)。

## 自审记录(对照 spec §5.1 / §5.3)
- supervisor 顶层路由(kb_rag/web/human_review/FINISH)+ 预算护栏:Task 5/7 ✅
- kb_rag CRAG 子图(retrieve→grade→[rewrite 循环]→generate→grounding→[hedge]):Task 4 ✅
- web 专家 = create_react_agent:Task 6 ✅(深度行为留 eval)
- 结构化输出决策(路由/评分/接地)+ 生成/改写:Task 3 ✅
- PostgresSaver 持久化 + thread_id:Task 9 ✅
- HITL interrupt/resume:Task 8 ✅
- 暂不覆盖(留 Plan 3-4):FastAPI/SSE 流式、可观测接线、eval、真实 LLM 质量断言、Command(goto) 形态(本计划用等价且版本稳定的 add_conditional_edges)。
- 已知风险点(执行期按红灯微调并记 concern):`ChatOpenAI` 属性名、`__interrupt__` 检测方式、`PostgresSaver.from_conn_string` 连接串格式、`get_state().values` 结构。
