from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from mvp_agentic_rag.agent.human_review import human_review_node
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
    g.add_node("human_review", human_review_node)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route,
                            {"kb_rag": "kb_rag", "web": "web",
                             "human_review": "human_review", "FINISH": END})
    g.add_edge("kb_rag", "supervisor")
    g.add_edge("web", "supervisor")
    g.add_edge("human_review", "supervisor")
    return g.compile(checkpointer=checkpointer)
