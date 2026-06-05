from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


class StubGraph:
    def __init__(self):
        self.last_config = None

    def invoke(self, state, config=None):
        self.last_config = config
        return {"messages": [HumanMessage(content=state["messages"][-1].content),
                             AIMessage(content="stub answer")],
                "citations": [{"doc_id": "k8s.md", "chunk_idx": 0}]}


def _client(graph):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app
    import mvp_agentic_rag.core.config as cfg

    cfg.get_settings.cache_clear()  # 让 require_api_key 重新读取 APP_API_KEY
    return TestClient(create_app(AppDeps(graph=graph, db=object(), callbacks=[])))


def test_chat_returns_answer_and_citations():
    graph = StubGraph()
    client = _client(graph)
    r = client.post("/chat", json={"message": "autoscaling?", "thread_id": "t1"})
    assert r.status_code == 200
    body = r.json()
    assert body["response"] == "stub answer"
    assert body["citations"][0]["doc_id"] == "k8s.md"
    assert body["request_id"]
    # thread_id 进了 config
    assert graph.last_config["configurable"]["thread_id"] == "t1"


def test_chat_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    import mvp_agentic_rag.core.config as cfg
    cfg.get_settings.cache_clear()

    client = _client(StubGraph())
    # 缺 key → 401
    assert client.post("/chat", json={"message": "x"}).status_code == 401
    # 带正确 key → 200
    ok = client.post("/chat", json={"message": "x"}, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    cfg.get_settings.cache_clear()
