from mvp_agentic_rag.ingest.loader import load_documents


def test_load_documents_reads_md_and_txt(tmp_path):
    (tmp_path / "a.md").write_text("alpha content", encoding="utf-8")
    (tmp_path / "b.txt").write_text("bravo content", encoding="utf-8")
    (tmp_path / "ignore.png").write_bytes(b"\x89PNG")

    docs = load_documents(str(tmp_path))

    by_id = {d["doc_id"]: d["text"] for d in docs}
    assert by_id == {"a.md": "alpha content", "b.txt": "bravo content"}
