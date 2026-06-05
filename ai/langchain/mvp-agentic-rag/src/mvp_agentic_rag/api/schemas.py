from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    citations: list[dict] = Field(default_factory=list)
    request_id: str


class ResumeRequest(BaseModel):
    thread_id: str
    decision: str
