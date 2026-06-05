from langgraph.checkpoint.memory import InMemorySaver

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database


def _build():
    s = get_settings()
    db = get_database()
    db.init_schema()
    # LangGraph Server 会注入自己的持久化;此处占位用内存 saver。
    return build_production_agent_graph(db, InMemorySaver(), s)


graph = _build
