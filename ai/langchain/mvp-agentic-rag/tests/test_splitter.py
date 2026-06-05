from mvp_agentic_rag.ingest.splitter import split_text


def test_split_produces_overlapping_chunks():
    text = "abcdefghij" * 30  # 300 字符
    chunks = split_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) >= 3
    assert all(len(c) <= 100 for c in chunks)


def test_split_short_text_single_chunk():
    chunks = split_text("hello", chunk_size=100, chunk_overlap=20)
    assert chunks == ["hello"]
