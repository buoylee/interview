def test_chat_model_with_fallback_builds_runnable(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "primary")
    monkeypatch.setenv("LLM_MODEL_FALLBACK", "backup")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings
    from mvp_agentic_rag.core.resilience import get_chat_model_with_fallback

    model = get_chat_model_with_fallback(Settings())
    # with_fallbacks 返回一个带 fallbacks 的 RunnableWithFallbacks
    assert hasattr(model, "fallbacks")
    assert len(model.fallbacks) == 1
