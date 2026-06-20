from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    # 不传 → server 端为本次请求生成一个全新 thread_id(见 app.py),
    # 每次都是独立会话、零历史累积;传了才会续上同一会话的多轮记忆。
    thread_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    citations: list[dict] = Field(default_factory=list)
    request_id: str
    # 回传本次实际使用的 thread_id:不传时由 server 生成,client 想续聊就带它回来。
    thread_id: str


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str
