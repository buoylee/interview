import pathlib
import tempfile

import pytest


@pytest.fixture
def seeded(clean_db, fake_embeddings):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    d = pathlib.Path(tempfile.mkdtemp())
    (d / "x.md").write_text("kubernetes autoscaling guide", encoding="utf-8")
    (d / "y.md").write_text("postgres replication tuning", encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=200, chunk_overlap=0
    )
    pipe.ingest_directory(str(d))
    return clean_db


def test_sparse_keyword_match(seeded):
    from mvp_agentic_rag.retrieval.sparse import SparseRetriever

    retriever = SparseRetriever(db=seeded, fts_config="simple")
    results = retriever.search("kubernetes", top_k=5)

    assert len(results) == 1
    assert "kubernetes" in results[0].content
