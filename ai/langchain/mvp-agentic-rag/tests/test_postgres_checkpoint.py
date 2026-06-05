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
