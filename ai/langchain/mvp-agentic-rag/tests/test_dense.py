import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    import tempfile, pathlib

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("the quick brown fox", encoding="utf-8")
    (d / "y.md").write_text("a totally different sentence", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db, fake_embeddings


def test_dense_exact_text_ranks_first(seeded):
    from mvp_agentic_rag.retrieval.dense import DenseRetriever

    db, emb = seeded
    retriever = DenseRetriever(db=db, embeddings=emb)

    results = retriever.search("the quick brown fox", top_k=2)

    assert len(results) >= 1
    assert results[0].content == "the quick brown fox"
    assert results[0].score >= results[-1].score  # 分数降序
