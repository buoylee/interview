from mvp_agentic_rag.retrieval.rerank import IdentityReranker
from mvp_agentic_rag.retrieval.types import RetrievedChunk


def _chunk(i, content):
    return RetrievedChunk(id=i, doc_id="d", chunk_idx=i, content=content, metadata={})


def test_identity_reranker_keeps_order_and_truncates():
    chunks = [_chunk(i, f"c{i}") for i in range(5)]
    reranker = IdentityReranker()

    out = reranker.rerank("q", chunks, top_n=3)

    assert [c.content for c in out] == ["c0", "c1", "c2"]
