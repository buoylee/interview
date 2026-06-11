# src/mvp_agentic_rag/obs/otel.py
"""OTel 可观测后端:LangChain callback 边界 → GenAI 语义约定 span → OTLP。

与 ai/agent-loop-lab 的手动埋点是同一套语义约定的两种接入方式:
lab 在自己的循环里手动开 span;这里把框架回调翻译成 span。
"""
import atexit
import base64
import logging

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from mvp_agentic_rag.core.config import Settings

logger = logging.getLogger(__name__)


def langfuse_otlp_config(settings: Settings) -> tuple[str, dict[str, str]] | None:
    """Langfuse 收 OTLP:{host}/api/public/otel,traces 信号全路径 + /v1/traces。"""
    if not (settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    auth = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    endpoint = settings.langfuse_host.rstrip("/") + "/api/public/otel/v1/traces"
    return endpoint, {"Authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"}


def build_tracer(settings: Settings, exporter=None):
    """返回 tracer。exporter 可注入(测试);provider 注册 atexit 刷缓冲。"""
    if exporter is None:
        otlp = langfuse_otlp_config(settings)
        if otlp is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint, headers = otlp
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        else:
            logger.warning("OBS_BACKEND=otel 但未配置 LANGFUSE_*,trace 落到控制台")
            exporter = ConsoleSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "mvp-agentic-rag"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    atexit.register(provider.shutdown)
    return provider.get_tracer("mvp_agentic_rag.obs")
