import pathlib
import tempfile

import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("kubernetes autoscaling best practices", encoding="utf-8")
    (d / "y.md").write_text("postgres index tuning notes", encoding="utf-8")
    (d / "z.md").write_text("redis caching strategies", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db, fake_embeddings


def test_hybrid_returns_relevant_chunk(seeded):
    from mvp_agentic_rag.retrieval.dense import DenseRetriever
    from mvp_agentic_rag.retrieval.sparse import SparseRetriever
    from mvp_agentic_rag.retrieval.rerank import IdentityReranker
    from mvp_agentic_rag.retrieval.hybrid import HybridRetriever

    db, emb = seeded
    retriever = HybridRetriever(
        dense=DenseRetriever(db=db, embeddings=emb),
        sparse=SparseRetriever(db=db, fts_config="simple"),
        reranker=IdentityReranker(),
        top_k_dense=10,
        top_k_sparse=10,
        rrf_k=60,
        rerank_top_n=3,
    )

    results = retriever.retrieve("kubernetes autoscaling")

    assert len(results) >= 1
    assert any("kubernetes" in c.content for c in results)
    assert len(results) <= 3
