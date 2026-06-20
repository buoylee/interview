import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from langgraph.types import Command

import mvp_agentic_rag.obs.metrics  # noqa: F401 — registers Prometheus metrics on import
from mvp_agentic_rag.api.deps import AppDeps, require_api_key
from mvp_agentic_rag.api.schemas import ChatRequest, ChatResponse, ResumeRequest


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

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest, request: Request, _: None = Depends(require_api_key)):
        thread_id = req.thread_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}, "callbacks": deps.callbacks}
        result = deps.graph.invoke(
            {"messages": [HumanMessage(content=req.message)],
             "next": "", "citations": [], "step_budget": 6},
            config,
        )
        answer = ""
        for m in reversed(result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        if not answer:
            raise HTTPException(status_code=500, detail="no AI response generated")
        return ChatResponse(response=answer, citations=result.get("citations", []),
                            request_id=request.state.request_id, thread_id=thread_id)

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request, _: None = Depends(require_api_key)):
        thread_id = req.thread_id or uuid.uuid4().hex
        config = {"configurable": {"thread_id": thread_id}, "callbacks": deps.callbacks}
        inp = {"messages": [HumanMessage(content=req.message)],
               "next": "", "citations": [], "step_budget": 6}

        async def event_stream():
            async for chunk, _meta in deps.graph.astream(inp, config, stream_mode="messages"):
                content = getattr(chunk, "content", "")
                if content:
                    yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"

        # SSE body 不便放结构化字段,thread_id 走响应头交给 client(想续聊就带回来)。
        return StreamingResponse(event_stream(), media_type="text/event-stream",
                                 headers={"X-Thread-ID": thread_id})

    @app.get("/threads/{thread_id}")
    async def get_thread(thread_id: str, _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = deps.graph.get_state(config)
        messages = [
            {"type": m.__class__.__name__, "content": str(getattr(m, "content", ""))}
            for m in snapshot.values.get("messages", [])
        ]
        return {"thread_id": thread_id, "messages": messages}

    @app.post("/threads/{thread_id}/resume", response_model=ChatResponse)
    async def resume_thread(thread_id: str, req: ResumeRequest, request: Request,
                            _: None = Depends(require_api_key)):
        config = {"configurable": {"thread_id": thread_id}, "callbacks": deps.callbacks}
        result = deps.graph.invoke(Command(resume=req.decision), config)
        answer = ""
        for m in reversed(result.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        if not answer:
            raise HTTPException(status_code=500, detail="no AI response generated")
        return ChatResponse(response=answer, citations=result.get("citations", []),
                            request_id=request.state.request_id, thread_id=thread_id)

    return app
