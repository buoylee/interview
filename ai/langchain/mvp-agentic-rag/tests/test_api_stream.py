from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk


class StreamStubGraph:
    async def astream(self, state, config=None, stream_mode=None):
        yield (AIMessageChunk(content="Hello"), {})
        yield (AIMessageChunk(content=" world"), {})


def _client():
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app
    import mvp_agentic_rag.core.config as cfg

    cfg.get_settings.cache_clear()
    return TestClient(create_app(AppDeps(graph=StreamStubGraph(), db=object(), callbacks=[])))


def test_chat_stream_yields_sse_tokens():
    r = _client().post("/chat/stream", json={"message": "hi", "thread_id": "t1"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    assert "data: Hello" in body
    assert "data:  world" in body
    assert "data: [DONE]" in body


def test_chat_stream_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    import mvp_agentic_rag.core.config as cfg
    cfg.get_settings.cache_clear()

    client = _client()
    # 缺 key → 401
    assert client.post("/chat/stream", json={"message": "x"}).status_code == 401
    # 带正确 key → 200
    ok = client.post("/chat/stream", json={"message": "x"}, headers={"X-API-Key": "secret"})
    assert ok.status_code == 200
    cfg.get_settings.cache_clear()
