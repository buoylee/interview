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
