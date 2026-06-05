from mvp_agentic_rag.ingest.loader import load_documents


def test_load_documents_reads_md_and_txt(tmp_path):
    (tmp_path / "a.md").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bravo content", encoding="utf-8")
    (tmp_path / "ignore.png").write_bytes(b"\x89PNG")

    docs = load_documents(str(tmp_path))

    by_id = {d["doc_id"]: d["text"] for d in docs}
    assert by_id == {"a.md": "alpha content", "b.txt": "bravo content"}


def test_ingest_inserts_chunks(clean_db, fake_embeddings, tmp_path):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    (tmp_path / "doc.md").write_text("hello world. " * 50, encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=100, chunk_overlap=20
    )

    n = pipe.ingest_directory(str(tmp_path))

    assert n > 0
    with clean_db.connect() as conn:
        count = conn.execute("SELECT count(*) FROM kb_chunks").fetchone()[0]
    assert count == n


def test_ingest_is_idempotent(clean_db, fake_embeddings, tmp_path):
    from mvp_agentic_rag.ingest.pipeline import IngestionPipeline

    (tmp_path / "doc.md").write_text("hello world. " * 50, encoding="utf-8")
    pipe = IngestionPipeline(
        db=clean_db, embeddings=fake_embeddings, chunk_size=100, chunk_overlap=20
    )

    first = pipe.ingest_directory(str(tmp_path))
    second = pipe.ingest_directory(str(tmp_path))  # 再来一次
    assert second == 0

    with clean_db.connect() as conn:
        count = conn.execute("SELECT count(*) FROM kb_chunks").fetchone()[0]
    assert count == first  # 没有重复插入
