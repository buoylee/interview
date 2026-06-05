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
