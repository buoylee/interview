from mvp_agentic_rag.core.config import Settings
from mvp_agentic_rag.obs.callbacks import MonitoringCallback


def test_none_backend_only_monitoring(monkeypatch):
    monkeypatch.setenv("OBS_BACKEND", "none")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    assert any(isinstance(c, MonitoringCallback) for c in cbs)
    assert len(cbs) == 1


def test_langsmith_backend_sets_env_no_extra_handler(monkeypatch):
    monkeypatch.setenv("OBS_BACKEND", "langsmith")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    # langsmith 靠环境变量自动追踪,不额外加 handler
    assert len(cbs) == 1
    import os
    assert os.environ.get("LANGSMITH_TRACING") == "true"


def test_langfuse_backend_adds_handler(monkeypatch):
    """langfuse 后端:不抛错 + MonitoringCallback 始终在列 + langfuse handler 已附加。
    依赖 langchain(已安装),CallbackHandler 构造成功,列表长度 >= 2。
    """
    monkeypatch.setenv("OBS_BACKEND", "langfuse")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    cbs = get_observability_callbacks(Settings())
    assert any(isinstance(c, MonitoringCallback) for c in cbs)
    assert len(cbs) >= 2  # MonitoringCallback + LangchainCallbackHandler
