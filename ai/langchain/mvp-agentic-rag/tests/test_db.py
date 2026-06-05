def test_init_schema_creates_table(clean_db):
    with clean_db.connect() as conn:
        row = conn.execute(
            "SELECT to_regclass('public.kb_chunks')"
        ).fetchone()
    assert row[0] == "kb_chunks"


def test_vector_extension_enabled(clean_db):
    with clean_db.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
    assert row is not None
