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
from mvp_agentic_rag.core.resilience import get_chat_model_with_fallback
from mvp_agentic_rag.retrieval.factory import build_hybrid_retriever


def build_production_agent_graph(db: Database, checkpointer, settings: Settings | None = None):
    s = settings or get_settings()
    chat = get_chat_model(s)
    # 纯 .invoke 的组件(生成/改写)接降级:主模型失败时自动切便宜模型。
    # 结构化输出组件(路由/评分/接地)用普通 chat —— with_fallbacks 返回的
    # RunnableWithFallbacks 没有 .with_structured_output,naive 接会崩;
    # 给结构化调用加 fallback 需在 with_structured_output 之后包,留作后续。
    chat_fb = get_chat_model_with_fallback(s)
    retriever = build_hybrid_retriever(db, s)

    kb_rag = build_kb_rag_subgraph(
        retriever=retriever,
        grader=LLMDocGrader(chat),
        rewriter=LLMQueryRewriter(chat_fb),
        generator=LLMAnswerGenerator(chat_fb),
        grounder=LLMGroundingChecker(chat),
    )
    web = build_web_agent(chat, [make_retrieve_kb_tool(retriever), web_search])
    supervisor = make_supervisor_node(LLMRouter(chat))
    return build_agent_graph(supervisor, kb_rag, web, checkpointer)
