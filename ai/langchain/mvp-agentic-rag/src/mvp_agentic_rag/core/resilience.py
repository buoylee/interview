from mvp_agentic_rag.core.config import Settings, get_settings
from mvp_agentic_rag.core.llm import get_chat_model


def get_chat_model_with_fallback(settings: Settings | None = None):
    """主模型 + 降级模型。主模型失败(超时/报错)时自动切到更便宜的备用模型。"""
    s = settings or get_settings()
    primary = get_chat_model(s, model=s.llm_model)
    fallback = get_chat_model(s, model=s.llm_model_fallback)
    return primary.with_fallbacks([fallback])
