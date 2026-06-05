from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


class Snapshot:
    def __init__(self, values):
        self.values = values


class ThreadStubGraph:
    def __init__(self):
        self.resumed_with = None

    def get_state(self, config):
        return Snapshot({"messages": [HumanMessage(content="q"), AIMessage(content="a")]})

    def invoke(self, command, config=None):
        self.resumed_with = command
        return {"messages": [AIMessage(content="resumed")], "citations": []}


def _client(graph):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app
    import mvp_agentic_rag.core.config as cfg

    cfg.get_settings.cache_clear()
    return TestClient(create_app(AppDeps(graph=graph, db=object(), callbacks=[])))


def test_get_thread_state_returns_messages():
    r = _client(ThreadStubGraph()).get("/threads/t1")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert msgs[-1]["content"] == "a"


def test_resume_continues_run():
    graph = ThreadStubGraph()
    r = _client(graph).post("/threads/t1/resume", json={"thread_id": "t1", "decision": "approved"})
    assert r.status_code == 200
    assert r.json()["response"] == "resumed"
    # 传入的是 Command(resume="approved")
    assert getattr(graph.resumed_with, "resume", None) == "approved"


def test_get_thread_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    import mvp_agentic_rag.core.config as cfg
    cfg.get_settings.cache_clear()

    client = _client(ThreadStubGraph())
    # 缺 key → 401
    assert client.get("/threads/t1").status_code == 401
    # 带正确 key → 200
    ok = client.get("/threads/t1", headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    cfg.get_settings.cache_clear()
