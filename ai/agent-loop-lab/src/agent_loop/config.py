"""env 配置。与 MVP(ai/langchain/mvp-agentic-rag)共用 LLM_*/LANGFUSE_* 命名约定。"""
import base64
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    langfuse_host: str
    langfuse_public_key: str
    langfuse_secret_key: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        llm_base_url=os.environ["LLM_BASE_URL"],
        llm_api_key=os.environ["LLM_API_KEY"],
        llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        langfuse_host=os.environ.get("LANGFUSE_HOST", ""),
        langfuse_public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        langfuse_secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    )


def langfuse_otlp_config(settings: Settings) -> tuple[str, dict[str, str]] | None:
    """Langfuse 收 OTLP 的端点是 {host}/api/public/otel,traces 信号全路径再加 /v1/traces。

    返回 None 表示未配置 Langfuse(调用方应回退到控制台 exporter)。
    """
    if not (settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    endpoint = settings.langfuse_host.rstrip("/") + "/api/public/otel/v1/traces"
    headers = {
        "Authorization": f"Basic {auth}",
        "x-langfuse-ingestion-version": "4",
    }
    return endpoint, headers
