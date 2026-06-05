import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

import mvp_agentic_rag.obs.metrics  # noqa: F401 — registers Prometheus metrics on import
from mvp_agentic_rag.api.deps import AppDeps


def create_app(deps: AppDeps) -> FastAPI:
    app = FastAPI(title="Agentic RAG MVP")
    app.state.deps = deps

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        try:
            with deps.db.connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ready"}
        except Exception as exc:  # noqa: BLE001 — readiness 探针要吞异常转 503
            return JSONResponse(status_code=503, content={"status": "not ready", "error": str(exc)})

    @app.get("/metrics")
    async def metrics():
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app
