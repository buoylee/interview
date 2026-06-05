from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str
    citations: list[dict]
    step_budget: int


class KBRagState(TypedDict):
    query: str
    chunks: list          # list[RetrievedChunk]
    rewrites: int
    relevant: bool
    answer: str
    citations: list[dict]
    grounded: bool
