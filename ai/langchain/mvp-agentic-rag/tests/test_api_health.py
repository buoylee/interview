from fastapi.testclient import TestClient


class StubDB:
    def __init__(self, ok=True):
        self.ok = ok

    def connect(self):
        db = self

        class _Ctx:
            def __enter__(self):
                if not db.ok:
                    raise RuntimeError("db down")
                return _Conn()

            def __exit__(self, *a):
                return False

        class _Conn:
            def execute(self, *a, **k):
                return self

            def fetchone(self):
                return (1,)

        return _Ctx()


def _client(db_ok=True):
    from mvp_agentic_rag.api.deps import AppDeps
    from mvp_agentic_rag.api.app import create_app

    deps = AppDeps(graph=object(), db=StubDB(db_ok), callbacks=[])
    return TestClient(create_app(deps))


def test_healthz():
    r = _client().get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_request_id_header():
    r = _client().get("/healthz")
    assert r.headers.get("X-Request-ID")


def test_readyz_ok():
    r = _client(db_ok=True).get("/readyz")
    assert r.status_code == 200


def test_readyz_db_down_returns_503():
    r = _client(db_ok=False).get("/readyz")
    assert r.status_code == 503


def test_metrics_endpoint():
    r = _client().get("/metrics")
    assert r.status_code == 200
    assert "rag_llm_calls_total" in r.text
