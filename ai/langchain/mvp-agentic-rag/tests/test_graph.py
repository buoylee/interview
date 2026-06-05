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
    router = SeqRouter(["kb_rag", "kb_rag", "kb_rag"])
    app = _build(router, InMemorySaver())
    out = app.invoke({"messages": [HumanMessage(content="q")],
                      "next": "", "citations": [], "step_budget": 1}, _config("t3"))
    # 不应无限循环;能正常结束
    assert any("HPA scales pods" in m.content for m in out["messages"])
    # 终止是预算护栏触发的:预算归零后 supervisor 直接 FINISH,不再问 router
    assert router.calls == 1
