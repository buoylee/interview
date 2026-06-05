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
