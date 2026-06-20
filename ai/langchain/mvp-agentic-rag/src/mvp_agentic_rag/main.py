from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row

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
    # checkpointer 的连接由 app 进程长期持有(server 活多久它活多久)。
    # 不能用 from_conn_string(...).__enter__():那个上下文管理器临时对象会被 GC,
    # 触发内部 `with Connection.connect()` 退出、把连接关掉,下一行 setup() 就拿到
    # 一条已关闭的连接。这里直接建一条自有连接,参数复刻 from_conn_string 内部所需。
    conn = Connection.connect(
        s.database_url, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    graph = build_production_agent_graph(db, checkpointer, s)
    callbacks = get_observability_callbacks(s)
    return create_app(AppDeps(graph=graph, db=db, callbacks=callbacks))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("mvp_agentic_rag.main:build_app", factory=True, host="0.0.0.0", port=8000)
