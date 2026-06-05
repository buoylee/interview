from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.core.db import Database
from mvp_agentic_rag.core.llm import get_embeddings
from mvp_agentic_rag.retrieval.dense import DenseRetriever
from mvp_agentic_rag.retrieval.hybrid import HybridRetriever
from mvp_agentic_rag.retrieval.rerank import IdentityReranker
from mvp_agentic_rag.retrieval.sparse import SparseRetriever


def build_hybrid_retriever(
    db: Database, settings: Settings | None = None
) -> HybridRetriever:
    s = settings or get_settings()
    embeddings = get_embeddings(s)
    return HybridRetriever(
        dense=DenseRetriever(db=db, embeddings=embeddings),
        sparse=SparseRetriever(db=db, fts_config=s.fts_config),
        reranker=IdentityReranker(),
        top_k_dense=s.top_k_dense,
        top_k_sparse=s.top_k_sparse,
        rrf_k=s.rrf_k,
        rerank_top_n=s.rerank_top_n,
    )
