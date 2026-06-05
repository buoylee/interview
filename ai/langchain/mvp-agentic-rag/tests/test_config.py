from mvp_agentic_rag.core.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://x/v1")
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("EMBEDDING_MODEL", "m")
    monkeypatch.setenv("EMBED_DIM", "8")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    s = Settings()

    assert s.embedding_base_url == "http://x/v1"
    assert s.embed_dim == 8
    assert s.top_k_dense == 20  # 默认值
    assert s.rrf_k == 60


def test_settings_overrides_knobs(monkeypatch):
    monkeypatch.setenv("EMBEDDING_API_KEY", "k")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("TOP_K_DENSE", "3")

    s = Settings()

    assert s.top_k_dense == 3
