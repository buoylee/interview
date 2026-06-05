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
