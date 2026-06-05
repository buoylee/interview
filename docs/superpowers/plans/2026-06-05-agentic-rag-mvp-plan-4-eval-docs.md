# Agentic RAG MVP — Plan 4:Eval + 面试叙事文档层 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 MVP 加上离线 eval 闭环(golden set + 自定义检查 + 可选 ragas + 回归 diff + CI 门)和面试叙事文档层(ARCHITECTURE / PROJECT-NARRATIVE / interview-qa / debugging-playbook / README 覆盖表),把「能跑的项目」变成「面试能流利讲」的成品。

**Architecture:** eval 核心是纯函数检查(must_include / route / citation / refusal)+ 注入式 `agent_runner` 的 `run_eval`,用 stub hermetic 测试 + CI 门;ragas(需真 LLM judge)放可选 `[eval]` extra、lazy import、live-only。文档层是 markdown 自学文档,内容链接仓库已有概念文档不重写概念。

**Tech Stack:** 复用现有栈;eval 仅用标准库 + pydantic;`ragas` 作为可选 extra(不进主安装,不进 hermetic 套件)。

---

## 上位文档
- 设计 spec:`docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md`(§5.5 eval、§5.10 面试文档层、§六 12 章覆盖表、§七 复用文档清单)
- 前置:Plan 1+2+3 已合入 main(检索/Agent 图/API 服务、`build_production_agent_graph`、`AgentState` 的 messages+citations)。

## 前置条件
- Plan 1-3 环境。eval 的自定义检查 + 报告 + CI 门**不需要 LLM**(stub/字符串匹配,hermetic)。
- `make eval` 跑真实 agent + 可选 ragas 需要 `.env` 的 `LLM_*`/`EMBEDDING_*` key 与 Postgres,**本计划的测试不依赖它**。

## 文件结构(本计划产出)
```
ai/langchain/mvp-agentic-rag/
├─ pyproject.toml                         (改:可选 [eval] extra = ragas)
├─ Makefile                               (改:加 eval 目标)
├─ README.md                              (改:quickstart + 12 章覆盖表)
├─ eval/
│  ├─ golden/cases.jsonl                  (新:golden 评测集)
│  └─ reports/.gitkeep                    (新:报告输出目录占位)
├─ src/mvp_agentic_rag/eval/
│  ├─ __init__.py                         (新)
│  ├─ checks.py                           (新:纯检查函数 + CaseResult)
│  ├─ dataset.py                          (新:GoldenCase + load_golden)
│  ├─ runner.py                           (新:run_eval + EvalReport)
│  ├─ report.py                           (新:to_json/to_markdown/diff_reports)
│  ├─ ragas_eval.py                       (新:可选 ragas,lazy,live-only)
│  └─ cli.py                              (新:make eval 入口,wiring 真实 agent)
├─ docs/
│  ├─ ARCHITECTURE.md                     (新)
│  ├─ PROJECT-NARRATIVE.md                (新)
│  ├─ debugging-playbook.md               (新)
│  └─ interview-qa/
│     ├─ 01-retrieval.md                  (新)
│     ├─ 02-agent-graph.md                (新)
│     ├─ 03-observability.md              (新)
│     ├─ 04-eval.md                       (新)
│     └─ 05-resilience-production.md      (新)
└─ tests/
   ├─ test_eval_checks.py                 (新)
   ├─ test_eval_dataset.py                (新)
   ├─ test_eval_runner.py                 (新,含 CI 门)
   └─ test_eval_report.py                 (新)
```

> 约定:命令都在 `ai/langchain/mvp-agentic-rag/` 下执行。`src/mvp_agentic_rag/eval/` 是 Python 包(eval 代码);`eval/`(项目根下)放数据集与报告输出。

---

### Task 1: eval 检查函数(纯函数)

**Files:**
- Create: `src/mvp_agentic_rag/eval/__init__.py`, `src/mvp_agentic_rag/eval/checks.py`
- Test: `tests/test_eval_checks.py`

- [ ] **Step 1: 写失败测试 `tests/test_eval_checks.py`**

```python
from mvp_agentic_rag.eval.checks import (
    check_must_include, check_route, check_citations, check_refusal, CaseResult,
)


def test_must_include():
    assert check_must_include("HPA scales pods by CPU", ["HPA", "CPU"]) is True
    assert check_must_include("HPA scales pods", ["HPA", "CPU"]) is False


def test_route():
    assert check_route("kb_rag", "kb_rag") is True
    assert check_route("web", "kb_rag") is False
    assert check_route("anything", None) is True  # 不指定则跳过


def test_citations():
    cits = [{"doc_id": "k8s.md"}, {"doc_id": "pg.md"}]
    assert check_citations(cits, ["k8s.md"]) is True
    assert check_citations(cits, ["missing.md"]) is False
    assert check_citations([], None) is True


def test_refusal():
    assert check_refusal("未找到足够依据,无法回答(依据不足)。", should_refuse=True) is True
    assert check_refusal("HPA scales pods", should_refuse=False) is True
    assert check_refusal("HPA scales pods", should_refuse=True) is False


def test_case_result_passed():
    ok = CaseResult(must_include_ok=True, route_ok=True, citation_ok=True, refusal_ok=True)
    bad = CaseResult(must_include_ok=False, route_ok=True, citation_ok=True, refusal_ok=True)
    assert ok.passed is True
    assert bad.passed is False
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_eval_checks.py -v`
Expected: FAIL（无 `eval.checks`）。

- [ ] **Step 3: 写 `src/mvp_agentic_rag/eval/__init__.py`(空)**

```python
```

- [ ] **Step 4: 写实现 `src/mvp_agentic_rag/eval/checks.py`**

```python
from dataclasses import dataclass

REFUSAL_MARKERS = ("依据不足", "无法", "抱歉", "没有找到")


def check_must_include(answer: str, must_include: list[str]) -> bool:
    return all(s in answer for s in must_include)


def check_route(actual_route: str, expected_route: str | None) -> bool:
    return expected_route is None or actual_route == expected_route


def check_citations(citations: list[dict], expected_docs: list[str] | None) -> bool:
    if not expected_docs:
        return True
    got = {c.get("doc_id") for c in citations}
    return all(d in got for d in expected_docs)


def check_refusal(answer: str, should_refuse: bool, markers=REFUSAL_MARKERS) -> bool:
    refused = any(m in answer for m in markers)
    return refused == should_refuse


@dataclass
class CaseResult:
    must_include_ok: bool
    route_ok: bool
    citation_ok: bool
    refusal_ok: bool

    @property
    def passed(self) -> bool:
        return all([self.must_include_ok, self.route_ok, self.citation_ok, self.refusal_ok])
```

- [ ] **Step 5: 运行测试,确认通过**

Run: `uv run pytest tests/test_eval_checks.py -v`
Expected: PASS（5 passed）。

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/eval/__init__.py src/mvp_agentic_rag/eval/checks.py tests/test_eval_checks.py
git commit -m "mvp-agentic-rag: Plan4 Task1 eval 检查函数"
```

---

### Task 2: golden 数据集加载

**Files:**
- Create: `src/mvp_agentic_rag/eval/dataset.py`, `eval/golden/cases.jsonl`
- Test: `tests/test_eval_dataset.py`

- [ ] **Step 1: 写失败测试 `tests/test_eval_dataset.py`**

```python
from mvp_agentic_rag.eval.dataset import GoldenCase, load_golden


def test_load_golden(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id":"c1","question":"q1","must_include":["A"],"expected_route":"kb_rag"}\n'
        '{"id":"c2","question":"q2","must_include":[],"should_refuse":true}\n',
        encoding="utf-8",
    )
    cases = load_golden(str(p))
    assert len(cases) == 2
    assert cases[0].id == "c1"
    assert cases[0].expected_route == "kb_rag"
    assert cases[0].should_refuse is False     # 默认
    assert cases[1].should_refuse is True
    assert cases[1].expected_route is None      # 默认


def test_golden_case_defaults():
    c = GoldenCase(id="x", question="q", must_include=["A"])
    assert c.expected_route is None
    assert c.expected_citation_docs is None
    assert c.should_refuse is False
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_eval_dataset.py -v`
Expected: FAIL（无 `eval.dataset`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/eval/dataset.py`**

```python
import json
from dataclasses import dataclass, field


@dataclass
class GoldenCase:
    id: str
    question: str
    must_include: list[str]
    expected_route: str | None = None
    expected_citation_docs: list[str] | None = None
    should_refuse: bool = False


def load_golden(path: str) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            cases.append(
                GoldenCase(
                    id=d["id"],
                    question=d["question"],
                    must_include=d.get("must_include", []),
                    expected_route=d.get("expected_route"),
                    expected_citation_docs=d.get("expected_citation_docs"),
                    should_refuse=d.get("should_refuse", False),
                )
            )
    return cases
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_eval_dataset.py -v`
Expected: PASS（2 passed）。

- [ ] **Step 5: 写 golden 评测集 `eval/golden/cases.jsonl`**

```jsonl
{"id":"kb-autoscaling","question":"How does Kubernetes autoscaling work?","must_include":["HPA"],"expected_route":"kb_rag","expected_citation_docs":["kubernetes.md"],"should_refuse":false}
{"id":"kb-pgvector","question":"What index should I use for vector search in Postgres?","must_include":["HNSW"],"expected_route":"kb_rag","expected_citation_docs":["postgres.md"],"should_refuse":false}
{"id":"out-of-kb","question":"What is today's weather in Tokyo?","must_include":[],"expected_route":"web","should_refuse":false}
{"id":"refuse-unknown","question":"What is the CEO's home address?","must_include":[],"should_refuse":true}
```

- [ ] **Step 6: Commit**

```bash
git add src/mvp_agentic_rag/eval/dataset.py eval/golden/cases.jsonl tests/test_eval_dataset.py
git commit -m "mvp-agentic-rag: Plan4 Task2 golden 数据集加载"
```

---

### Task 3: eval runner（run_eval + CI 门)

**Files:**
- Create: `src/mvp_agentic_rag/eval/runner.py`
- Test: `tests/test_eval_runner.py`

> `agent_runner(question) -> {"answer", "route", "citations"}` 注入。测试用确定性 stub runner;同时含一个 CI 门测试(stub 全过 → pass_rate==1.0)。

- [ ] **Step 1: 写失败测试 `tests/test_eval_runner.py`**

```python
from mvp_agentic_rag.eval.dataset import GoldenCase
from mvp_agentic_rag.eval.runner import run_eval, EvalReport


def _cases():
    return [
        GoldenCase(id="c1", question="autoscaling?", must_include=["HPA"],
                   expected_route="kb_rag", expected_citation_docs=["k8s.md"]),
        GoldenCase(id="c2", question="secret?", must_include=[], should_refuse=True),
    ]


def good_runner(question):
    if "autoscaling" in question:
        return {"answer": "HPA scales pods", "route": "kb_rag",
                "citations": [{"doc_id": "k8s.md"}]}
    return {"answer": "无法回答(依据不足)", "route": "kb_rag", "citations": []}


def bad_runner(question):
    # c1 漏了 HPA、引用错 → 失败
    return {"answer": "scaling stuff", "route": "web", "citations": [], }


def test_run_eval_all_pass():
    report = run_eval(good_runner, _cases())
    assert isinstance(report, EvalReport)
    assert report.passed_count == 2
    assert report.pass_rate == 1.0


def test_run_eval_detects_failures():
    report = run_eval(bad_runner, _cases())
    # c1 fails(must_include/route/citation),c2: bad_runner 没拒答但 should_refuse → fail
    assert report.passed_count == 0
    assert report.pass_rate == 0.0


def test_ci_gate_stub_agent_meets_threshold():
    # CI 门:确定性 stub 全过,pass_rate 必须达标(>=0.9)
    report = run_eval(good_runner, _cases())
    assert report.pass_rate >= 0.9
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_eval_runner.py -v`
Expected: FAIL（无 `eval.runner`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/eval/runner.py`**

```python
from dataclasses import dataclass

from mvp_agentic_rag.eval.checks import (
    CaseResult, check_citations, check_must_include, check_refusal, check_route,
)
from mvp_agentic_rag.eval.dataset import GoldenCase


@dataclass
class CaseEval:
    case_id: str
    result: CaseResult
    answer: str
    route: str


@dataclass
class EvalReport:
    cases: list[CaseEval]

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.cases if c.result.passed)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / len(self.cases) if self.cases else 0.0


def run_eval(agent_runner, cases: list[GoldenCase]) -> EvalReport:
    """agent_runner(question) -> {"answer": str, "route": str, "citations": list[dict]}"""
    evals: list[CaseEval] = []
    for case in cases:
        out = agent_runner(case.question)
        answer = out.get("answer", "")
        route = out.get("route", "")
        citations = out.get("citations", [])
        result = CaseResult(
            must_include_ok=check_must_include(answer, case.must_include),
            route_ok=check_route(route, case.expected_route),
            citation_ok=check_citations(citations, case.expected_citation_docs),
            refusal_ok=check_refusal(answer, case.should_refuse),
        )
        evals.append(CaseEval(case_id=case.id, result=result, answer=answer, route=route))
    return EvalReport(evals)
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_eval_runner.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/eval/runner.py tests/test_eval_runner.py
git commit -m "mvp-agentic-rag: Plan4 Task3 eval runner + CI 门"
```

---

### Task 4: eval 报告 + 回归 diff

**Files:**
- Create: `src/mvp_agentic_rag/eval/report.py`
- Test: `tests/test_eval_report.py`

- [ ] **Step 1: 写失败测试 `tests/test_eval_report.py`**

```python
from mvp_agentic_rag.eval.checks import CaseResult
from mvp_agentic_rag.eval.runner import CaseEval, EvalReport
from mvp_agentic_rag.eval.report import to_json, to_markdown, diff_reports


def _report(pass_c1=True):
    return EvalReport([
        CaseEval("c1", CaseResult(pass_c1, True, True, True), "a1", "kb_rag"),
        CaseEval("c2", CaseResult(True, True, True, True), "a2", "web"),
    ])


def test_to_json_shape():
    j = to_json(_report())
    assert j["pass_rate"] == 1.0
    assert j["cases"]["c1"]["passed"] is True


def test_to_markdown_contains_summary():
    md = to_markdown(_report())
    assert "pass_rate" in md.lower() or "通过率" in md
    assert "c1" in md


def test_diff_detects_regression():
    prev = to_json(_report(pass_c1=True))
    curr = to_json(_report(pass_c1=False))
    regressions = diff_reports(prev, curr)
    assert "c1" in regressions  # 之前过、现在挂 → 回归
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `uv run pytest tests/test_eval_report.py -v`
Expected: FAIL（无 `eval.report`）。

- [ ] **Step 3: 写实现 `src/mvp_agentic_rag/eval/report.py`**

```python
from mvp_agentic_rag.eval.runner import EvalReport


def to_json(report: EvalReport) -> dict:
    return {
        "pass_rate": report.pass_rate,
        "passed_count": report.passed_count,
        "total": len(report.cases),
        "cases": {
            c.case_id: {
                "passed": c.result.passed,
                "must_include_ok": c.result.must_include_ok,
                "route_ok": c.result.route_ok,
                "citation_ok": c.result.citation_ok,
                "refusal_ok": c.result.refusal_ok,
                "route": c.route,
            }
            for c in report.cases
        },
    }


def to_markdown(report: EvalReport) -> str:
    lines = [
        "# Eval Report",
        "",
        f"- pass_rate: {report.pass_rate:.2%}",
        f"- passed: {report.passed_count}/{len(report.cases)}",
        "",
        "| case | passed | must_include | route | citation | refusal |",
        "|------|--------|--------------|-------|----------|---------|",
    ]
    for c in report.cases:
        r = c.result
        lines.append(
            f"| {c.case_id} | {'✅' if r.passed else '❌'} | {r.must_include_ok} | "
            f"{r.route_ok} | {r.citation_ok} | {r.refusal_ok} |"
        )
    return "\n".join(lines)


def diff_reports(prev: dict, curr: dict) -> list[str]:
    """返回回归的 case id 列表:在 prev 通过、在 curr 失败。"""
    regressions = []
    prev_cases = prev.get("cases", {})
    curr_cases = curr.get("cases", {})
    for cid, pinfo in prev_cases.items():
        cinfo = curr_cases.get(cid)
        if pinfo.get("passed") and cinfo is not None and not cinfo.get("passed"):
            regressions.append(cid)
    return regressions
```

- [ ] **Step 4: 运行测试,确认通过**

Run: `uv run pytest tests/test_eval_report.py -v`
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add src/mvp_agentic_rag/eval/report.py tests/test_eval_report.py
git commit -m "mvp-agentic-rag: Plan4 Task4 eval 报告 + 回归 diff"
```

---

### Task 5: 可选 ragas + make eval CLI

**Files:**
- Modify: `pyproject.toml`(加可选 [eval] extra), `Makefile`
- Create: `src/mvp_agentic_rag/eval/ragas_eval.py`, `src/mvp_agentic_rag/eval/cli.py`, `eval/reports/.gitkeep`
- Test: import 冒烟(无独立 pytest)

> ragas 需要真 LLM judge,放可选 extra、lazy import、live-only。`cli.py`(`make eval`)wiring 真实 agent + 自定义检查 + 报告,可选 ragas;只做 import 冒烟。

- [ ] **Step 1: 加可选 extra**

Run: `cd ai/langchain/mvp-agentic-rag && uv add --optional eval ragas`
Expected: 写入 `[project.optional-dependencies] eval = ["ragas..."]`;主安装不变。(若 ragas 解析较慢属正常。)

- [ ] **Step 2: 写 `src/mvp_agentic_rag/eval/ragas_eval.py`(lazy,容错)**

```python
"""可选 ragas RAG 指标(faithfulness / answer_relevancy / context_precision / context_recall)。
需要 `uv sync --extra eval` 安装 ragas,且需真实 LLM/embedding(live)。未安装时抛清晰错误。"""


def ragas_available() -> bool:
    try:
        import ragas  # noqa: F401
        return True
    except ImportError:
        return False


def evaluate_ragas(samples: list[dict]):
    """samples: [{question, answer, contexts: list[str], ground_truth?}]。
    返回 ragas 评估结果。仅在安装了 [eval] extra + 配好 LLM key 时可用。"""
    if not ragas_available():
        raise RuntimeError("ragas 未安装。运行 `uv sync --extra eval` 后再用。")
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import answer_relevancy, context_precision, faithfulness

    ds = Dataset.from_list(samples)
    return evaluate(ds, metrics=[faithfulness, answer_relevancy, context_precision])
```

- [ ] **Step 3: 写 `src/mvp_agentic_rag/eval/cli.py`(make eval 入口,live)**

```python
import json
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage, HumanMessage

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.eval.dataset import load_golden
from mvp_agentic_rag.eval.report import to_json, to_markdown
from mvp_agentic_rag.eval.runner import run_eval

GOLDEN = "eval/golden/cases.jsonl"
OUT_DIR = Path("eval/reports")


def _make_agent_runner(graph):
    def runner(question: str) -> dict:
        config = {"configurable": {"thread_id": f"eval-{abs(hash(question))}"}}
        # 用 stream 观测实际走到的专家节点(kb_rag / web)
        route = ""
        for update in graph.stream(
            {"messages": [HumanMessage(content=question)], "next": "",
             "citations": [], "step_budget": 6},
            config, stream_mode="updates",
        ):
            for node in update:
                if node in ("kb_rag", "web"):
                    route = node
        state = graph.get_state(config).values
        answer = ""
        for m in reversed(state.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        return {"answer": answer, "route": route, "citations": state.get("citations", [])}

    return runner


def main() -> int:
    s = get_settings()
    db = get_database()
    db.init_schema()
    graph = build_production_agent_graph(db, InMemorySaver(), s)
    cases = load_golden(GOLDEN)
    report = run_eval(_make_agent_runner(graph), cases)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(json.dumps(to_json(report), ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "report.md").write_text(to_markdown(report), encoding="utf-8")
    print(f"eval done: pass_rate={report.pass_rate:.2%} ({report.passed_count}/{len(cases)})")
    print(f"reports written to {OUT_DIR}/report.json|md")
    db.close()
    return 0 if report.pass_rate >= 0.5 else 1  # 灰度门:低于阈值退出码非 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 写 `eval/reports/.gitkeep`(空文件占位)**

```
```

- [ ] **Step 5: Makefile 加 eval 目标**

```makefile
eval:
	uv run python -m mvp_agentic_rag.eval.cli
```

- [ ] **Step 6: import 冒烟(不连库不调 LLM)**

Run: `uv run python -c "import mvp_agentic_rag.eval.cli; import mvp_agentic_rag.eval.ragas_eval; print('eval cli ok')"`
Expected: 打印 `eval cli ok`(仅 import 模块、定义函数,`main`/`evaluate_ragas` 未被调用,故不连库)。

- [ ] **Step 7: 全量回归**

Run: `uv run pytest -q`
Expected: 全绿(Plan 1-3 的 62 + Plan 4 eval 测试)。

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock Makefile src/mvp_agentic_rag/eval/ragas_eval.py src/mvp_agentic_rag/eval/cli.py eval/reports/.gitkeep
git commit -m "mvp-agentic-rag: Plan4 Task5 可选 ragas + make eval CLI"
```

---

### Task 6: 架构与项目叙事文档

**Files:**
- Create: `docs/ARCHITECTURE.md`, `docs/PROJECT-NARRATIVE.md`

> 这两篇是面试讲述的主干。写好散文(自学/可讲),内容必须覆盖下列要点,概念处链接仓库已有文档。

- [ ] **Step 1: 写 `docs/ARCHITECTURE.md`**,必须包含:
  - **系统总览图**:复用 spec §四的 ASCII 架构图(ingest → FastAPI → LangGraph supervisor + kb_rag CRAG 子图 + web;Postgres 单库双用 pgvector+checkpoint;Langfuse/Prometheus 可观测)。
  - **组件职责表**:ingest / retrieval(hybrid+RRF+rerank)/ agent(supervisor+CRAG+web+HITL)/ api / obs / eval —— 每个一句话职责。
  - **请求数据流**:用户问 → request_id → supervisor 路由 → kb_rag(retrieve→grade→[rewrite]→generate→grounding→[hedge])→ 带引用答案 → trace 落 Langfuse、指标落 /metrics。
  - **关键决策表**(每行:决策 / 为什么 / 替代方案 / 取舍),至少覆盖:① 一个 Postgres 双用(pgvector+PostgresSaver) ② hybrid+RRF+rerank(vs 纯向量/纯 BM25) ③ CRAG 自纠正(vs 一次性 RAG) ④ supervisor(vs swarm) ⑤ PostgresSaver(vs Memory/Sqlite) ⑥ 默认 Langfuse 自托管(vs LangSmith,数据驻留/成本/开源)⑦ OpenAI 兼容接口(可换供应商)⑧ fallback 只接纯 invoke 组件(结构化组件的限制)。
  - **链接**:`../../../../docs/superpowers/specs/2026-06-05-langgraph-agentic-rag-mvp-design.md` 及 `ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md`。

- [ ] **Step 2: 写 `docs/PROJECT-NARRATIVE.md`**,必须包含:
  - **30 秒版**:一句话项目定位(企业知识库 Agentic RAG,带引用、可观测、自纠正)。
  - **2 分钟版**:STAR —— Situation(企业内部文档问答,痛点是幻觉/无依据/无法排查)、Task、Action(本架构)、Result(62 测试、hermetic+容器、可观测接通)。
  - **深挖版**:逐子系统能讲的取舍(指向 interview-qa 各篇)。
  - **「下一步会做什么」**:诚实的 follow-up —— ragas live 接入、SSE 只推 generate 节点、结构化组件 fallback、OIDC 鉴权、HA/多副本、Grafana 面板、中文 FTS(pg_jieba)。

- [ ] **Step 3: 校验链接可达**

Run: `ls docs/ARCHITECTURE.md docs/PROJECT-NARRATIVE.md`
Expected: 两文件存在。

- [ ] **Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md docs/PROJECT-NARRATIVE.md
git commit -m "mvp-agentic-rag: Plan4 Task6 架构与项目叙事文档"
```

---

### Task 7: 面试 Q&A 文档层 + 排查 playbook

**Files:**
- Create: `docs/interview-qa/01-retrieval.md` … `05-resilience-production.md`, `docs/debugging-playbook.md`

> 每篇 interview-qa 用统一结构:**高频问题 → 答案要点(bullet)→ 深挖追问 → 常见误区 → 链接仓库概念文档**。不重写概念,只做「在本项目里怎么答 + 指向已有文档」。

- [ ] **Step 1: 写 `docs/interview-qa/01-retrieval.md`**,覆盖问题:为什么 hybrid(向量+全文)而非纯向量?RRF 怎么融合、为什么不调权重?rerank 解决什么(recall→precision)?chunk_size/overlap 怎么调?中文全文为什么要 pg_jieba?链接 `ai/rag-lab/03-hybrid-rerank-debugging.md`、`08-chunking-tuning-playbook.md`、`ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md`。

- [ ] **Step 2: 写 `docs/interview-qa/02-agent-graph.md`**,覆盖:supervisor vs swarm 怎么选?CRAG 自纠正(grade/grounding 双轴 + rewrite 预算)怎么防死循环?子图与顶层 state 不同 schema 怎么桥接?checkpointer 选型(Memory/Sqlite/Postgres)?HITL interrupt/resume 机制?链接 `ai/ml-to-llm-roadmap/02-agent-tool-use/05-agent-patterns-and-architectures.md`、`06-agent-runtime-engineering.md`、`09-multi-agent-coordination.md`。

- [ ] **Step 3: 写 `docs/interview-qa/03-observability.md`**,覆盖:LangSmith vs Langfuse 怎么选(数据驻留/成本/开源/运维,默认 Langfuse 自托管的理由)?trace 与 metrics 的区别(查单条 vs 看聚合)?request_id 怎么把坏答案定位到具体步骤?为什么可观测是一等公民?链接 `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`、`ai/langchain/11-production.md`。

- [ ] **Step 4: 写 `docs/interview-qa/04-eval.md`**,覆盖:RAG eval vs agent 轨迹 eval 的区别?ragas 四指标(faithfulness/answer_relevancy/context_precision/context_recall)各测什么?为什么 golden set 进 git 当回归门?非确定性怎么测(逻辑用 stub、质量用 eval)?链接 `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md`、`ai/ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md`、`ai/ml-to-llm-roadmap/02-agent-tool-use/11-agent-eval-practice.md`。

- [ ] **Step 5: 写 `docs/interview-qa/05-resilience-production.md`**,覆盖:retry/timeout/fallback/降级各在哪一层?step/token 预算护栏防什么?为什么 fallback 只接了纯 invoke 组件(结构化组件的限制)?prompt 注入与工具安全怎么防?部署(Docker/compose/langgraph.json)?链接 `ai/ml-to-llm-roadmap/02-agent-tool-use/02-tool-use-and-recovery.md`、`ai/langchain/11-production.md`。

- [ ] **Step 6: 写 `docs/debugging-playbook.md`**,把 `03-production-debugging-monitoring.md` 的「症状→组件→证据→修复→回归」在**本系统**上可执行化:坏答案 → 拿 `X-Request-ID` → 开 Langfuse trace → 逐步看(supervisor 路由?retrieve 命中?rerank?grade?generate?grounding?)→ 对照 `/metrics` 看 token/延迟/工具错误 → 用 `make eval` 回归。给 3 个具体症状示例(检索没命中、答案不接地、延迟高)。

- [ ] **Step 7: 校验文件存在**

Run: `ls docs/interview-qa/*.md docs/debugging-playbook.md`
Expected: 6 个文件存在。

- [ ] **Step 8: Commit**

```bash
git add docs/interview-qa/ docs/debugging-playbook.md
git commit -m "mvp-agentic-rag: Plan4 Task7 面试 Q&A + 排查 playbook"
```

---

### Task 8: README 收口(quickstart + 12 章覆盖表)

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 重写 `README.md`**,必须包含:
  - **一句话定位** + 指向 `docs/ARCHITECTURE.md`、`docs/PROJECT-NARRATIVE.md`、`docs/interview-qa/`。
  - **Quickstart**(完整命令):
    ```
    make install
    make up
    cp .env.example .env   # 填 EMBEDDING_* / LLM_* (+ LANGFUSE_* 看 trace)
    make db-init
    make ingest
    make serve             # 起 API: http://localhost:8000  (/docs 看 OpenAPI)
    make eval              # 离线评测(需 key)
    make test              # hermetic 全量
    ```
  - **API 一览**:`/chat`、`/chat/stream`、`/threads/{id}`、`/threads/{id}/resume`、`/healthz`、`/readyz`、`/metrics`。
  - **可观测切换**:`OBS_BACKEND=none|langfuse|langsmith` 一句话说明。
  - **「12 章 → MVP 落点」覆盖表**:照 spec §六的 11 行表(02 Chat Models→core/llm;…;12 多 Agent→supervisor+子图),证明这一个项目把 `ai/langchain/` 整套教程实现了。
  - **已知边界**:live 端到端需 key;ragas 需 `uv sync --extra eval`;中文 FTS 需 pg_jieba;非 HA/无 OIDC(MVP)。

- [ ] **Step 2: 校验**

Run: `uv run pytest -q`(确认文档改动未碰代码、套件仍全绿) 然后 `head -5 README.md`
Expected: 套件全绿;README 顶部为新内容。

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "mvp-agentic-rag: Plan4 Task8 README 收口(quickstart + 12 章覆盖表)"
```

---

## 完成定义(Plan 4)
- `make test` 全绿且 hermetic:eval 的检查函数、golden 加载、run_eval、报告/回归 diff、CI 门(stub agent 达阈值)全部断言;ragas + cli 仅 import 冒烟(live 留 key)。
- `make eval`(配 key)能跑真实 agent over golden set,产出 `eval/reports/report.{json,md}`,低于阈值退出码非 0(可进 CI 灰度门)。
- 文档层完整:ARCHITECTURE / PROJECT-NARRATIVE / 5 篇 interview-qa / debugging-playbook / README 覆盖表,概念处链接仓库已有文档。
- 交付物:面试可讲的成品 —— eval 闭环 + 能讲清架构/取舍/Q&A 的文档。

## 自审记录(对照 spec §5.5 / §5.10 / §六 / §七)
- §5.5 eval(golden+ragas+轨迹自检+回归+CI 门):Task 1-5 ✅(ragas live-only;自定义检查 = 轨迹/must_include/citation/refusal)
- §5.10 文档层(ARCHITECTURE/NARRATIVE/interview-qa/debugging-playbook/README 覆盖表):Task 6-8 ✅
- §六 12 章→MVP 覆盖表:Task 8 ✅
- §七 复用概念文档(链接不重写):Task 7 各篇链接 ✅
- 暂不覆盖:ragas 的 hermetic 断言(需真 judge,live-only)、Grafana 面板、OTel、CI workflow 文件本身(eval 退出码已就绪,接入 CI 由用户的 CI 平台决定)。
- 已知风险点(执行期按红灯微调并记 concern):`uv add --optional eval ragas` 解析(ragas 依赖较重)、cli.py `graph.stream(stream_mode="updates")` 的 update 结构(node 名提取)、`get_state().values` 结构(Plan 2 已验证)。

## 实现期 review 修正记录(committed 代码与上文逐字片段的差异)

执行 + review 发现并已修正(均合入,75 测试全绿):

- **拒答标记收窄**:`checks.py` 的 `REFUSAL_MARKERS` 从 `("依据不足","无法","抱歉","没有找到")` 收窄为 `("依据不足","未找到足够依据")` —— 通用词 `无法/抱歉/没有找到` 会让正常答案被误判为拒答(影响 live eval);收窄后仍能命中系统的 hedge 措辞。
- **健壮性**:`CaseResult.passed` 用显式 `and` 链(替 `all([...])`);`check_citations` 对 citations 里的 `None` 元素加 `if c` 守卫。
- **去死 import**:`dataset.py` 去掉未用的 `field`;`cli.py` 去掉未用的 `import sys`。
- **ragas 实测 0.4.3**:`uv add --optional eval ragas` 成功解析(装入 venv,注册为 `[eval]` 可选 extra);`ragas_eval.py` lazy import,未装也能 import 模块。
- **阈值说明**:`cli.py` live 灰度门 0.5(真实 LLM 更难)与 hermetic CI-gate 0.9(`test_eval_runner`)是两个门,已在 cli 注释里说明。
- **文档修正**:`debugging-playbook.md` 示例类名 `Grader`→`LLMDocGrader`;`ARCHITECTURE.md` 图里 supervisor 措辞改为「写 next 经 add_conditional_edges 路由(等价 Command(goto=...))」以匹配实现。
- **链接深度**:`docs/interview-qa/` 到仓库根为 4 层(`../../../../`);文档用 repo-root-relative 路径文本,12 个概念链接均验证存在。
