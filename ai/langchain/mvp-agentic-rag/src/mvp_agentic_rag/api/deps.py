from dataclasses import dataclass, field

from fastapi import Header, HTTPException

from mvp_agentic_rag.core.config import get_settings


@dataclass
class AppDeps:
    graph: object              # 编译后的 LangGraph(或测试 stub)
    db: object                 # Database(或测试 stub),供 readyz
    callbacks: list = field(default_factory=list)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """APP_API_KEY 留空=开发模式不校验;设置后要求请求头 X-API-Key 匹配。"""
    expected = get_settings().app_api_key
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
