from typing import Protocol

from mvp_agentic_rag.retrieval.types import RetrievedChunk


class Reranker(Protocol):
    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]: ...


class IdentityReranker:
    """不改变顺序,只截断到 top_n。默认实现。"""

    def rerank(
        self, query: str, chunks: list[RetrievedChunk], top_n: int
    ) -> list[RetrievedChunk]:
        return chunks[:top_n]
