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


def test_not_grounded_no_budget_hedges():
    app = _build(ScriptedGrader([True]), ScriptedGrounder([False]), max_rewrites=0)
    out = app.invoke({"query": "q", "rewrites": 0})
    assert "依据不足" in out["answer"]
    assert out["citations"] == []
