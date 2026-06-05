import logging
import os

from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.obs.callbacks import MonitoringCallback

logger = logging.getLogger(__name__)


def _make_langfuse_handler(settings: Settings):
    """构造 Langfuse CallbackHandler。失败时记 warning 并返回 None(优雅降级)。"""
    # 把 key 透传到 langfuse 读取的环境变量
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
    try:  # langfuse v3/v4
        from langfuse.langchain import CallbackHandler
    except ImportError:  # langfuse v2 回退
        try:
            from langfuse.callback import CallbackHandler  # type: ignore[no-redef]
        except ImportError as exc:
            logger.warning("langfuse import failed, skipping handler: %s", exc)
            return None
    try:
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001 — 无连接时优雅降级
        logger.warning("langfuse CallbackHandler() init failed, skipping: %s", exc)
        return None


def get_observability_callbacks(settings: Settings | None = None) -> list:
    s = settings or get_settings()
    callbacks: list = [MonitoringCallback()]
    backend = (s.obs_backend or "none").lower()
    if backend == "langfuse":
        handler = _make_langfuse_handler(s)
        if handler is not None:
            callbacks.append(handler)
    elif backend == "langsmith":
        os.environ["LANGSMITH_TRACING"] = "true"  # 其余 LANGSMITH_API_KEY/PROJECT 由 .env 提供
    return callbacks
