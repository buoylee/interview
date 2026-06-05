from langgraph.checkpoint.postgres import PostgresSaver

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.api.app import create_app
from mvp_agentic_rag.api.deps import AppDeps
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.obs.backends import get_observability_callbacks


def build_app():
    s = get_settings()
    db = get_database()
    db.init_schema()
    checkpointer = PostgresSaver.from_conn_string(s.database_url).__enter__()
    checkpointer.setup()
    graph = build_production_agent_graph(db, checkpointer, s)
    callbacks = get_observability_callbacks(s)
    return create_app(AppDeps(graph=graph, db=db, callbacks=callbacks))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mvp_agentic_rag.main:build_app", factory=True, host="0.0.0.0", port=8000)
