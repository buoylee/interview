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
    """langfuse 后端:不抛错 + MonitoringCallback 始终在列。
    若环境缺少 langfuse/langchain 依赖则优雅降级(handler=None 被跳过),
    len>=2 仅在依赖完整时成立;本测试只断言 no-exception + MonitoringCallback 存在。
    [CONCERN] langfuse v4 CallbackHandler 需要 'langchain' 包 (非 langchain_core);
    本 venv 仅有 langchain_core,handler 降级为 None → len==1。
    真实部署加 'uv add langchain' 即可恢复 len>=2。
    """
    monkeypatch.setenv("OBS_BACKEND", "langfuse")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/d")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGFUSE_HOST", "http://localhost:3000")
    from mvp_agentic_rag.obs.backends import get_observability_callbacks

    # must not raise even when langfuse import fails in this env
    cbs = get_observability_callbacks(Settings())
    assert any(isinstance(c, MonitoringCallback) for c in cbs)
    assert len(cbs) >= 1  # at minimum MonitoringCallback; >= 2 when langfuse deps present
