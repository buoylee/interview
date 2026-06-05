def test_settings_has_llm_fields(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "my-chat")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings

    s = Settings()
    assert s.llm_base_url == "http://x/v1"
    assert s.llm_model == "my-chat"


def test_get_chat_model_uses_config(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "my-chat")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")

    from mvp_agentic_rag.core.config import Settings
    from mvp_agentic_rag.core.llm import get_chat_model

    chat = get_chat_model(Settings())
    assert chat.model_name == "my-chat"
    assert str(chat.openai_api_base) == "http://x/v1"
