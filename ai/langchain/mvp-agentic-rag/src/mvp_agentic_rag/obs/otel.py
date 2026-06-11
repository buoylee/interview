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


from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry.trace import Status, StatusCode, set_span_in_context


def _extract_usage(response) -> tuple[int, int]:
    """与 MonitoringCallback 同源的 usage 提取:遍历 generations 的 usage_metadata。"""
    input_tokens = output_tokens = 0
    for gens in getattr(response, "generations", []) or []:
        for gen in gens:
            msg = getattr(gen, "message", None)
            usage = getattr(msg, "usage_metadata", None) if msg else None
            if usage:
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
    return input_tokens, output_tokens


class OTelTraceCallback(BaseCallbackHandler):
    """LangChain 回调三边界 → OTel GenAI 语义约定 span。

    run_id → span 表;parent_run_id 在表里就挂为父 span,否则做根。
    回调缺 start(框架异常路径)时 end 是 no-op,不影响主流程。
    """

    raise_error = False

    def __init__(self, tracer) -> None:
        self._tracer = tracer
        self._spans: dict = {}

    # ---- 内部 ----
    def _start(self, run_id, parent_run_id, name: str, attributes: dict) -> None:
        parent = self._spans.get(parent_run_id)
        ctx = set_span_in_context(parent) if parent is not None else None
        self._spans[run_id] = self._tracer.start_span(name, context=ctx, attributes=attributes)

    def _end(self, run_id, error=None) -> None:
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        if error is not None:
            span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()

    # ---- LLM 边界 ----
    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        params = kwargs.get("invocation_params") or {}
        model = str(params.get("model_name") or params.get("model") or "unknown")
        self._start(run_id, parent_run_id, f"chat {model}",
                    {"gen_ai.operation.name": "chat", "gen_ai.request.model": model})

    def on_llm_start(self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs):
        # 非 chat 模型走这里;同样处理
        self.on_chat_model_start(serialized, [], run_id=run_id, parent_run_id=parent_run_id, **kwargs)

    def on_llm_end(self, response, *, run_id, **kwargs):
        span = self._spans.get(run_id)
        if span is not None:
            input_tokens, output_tokens = _extract_usage(response)
            if input_tokens:
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
            if output_tokens:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        self._end(run_id)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    # ---- 工具边界 ----
    def on_tool_start(self, serialized, input_str, *, run_id, parent_run_id=None, **kwargs):
        name = (serialized or {}).get("name", "unknown")
        self._start(run_id, parent_run_id, f"execute_tool {name}",
                    {"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name})

    def on_tool_end(self, output, *, run_id, **kwargs):
        self._end(run_id)

    def on_tool_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)

    # ---- 检索边界 ----
    def on_retriever_start(self, serialized, query, *, run_id, parent_run_id=None, **kwargs):
        self._start(run_id, parent_run_id, "retrieve kb", {"gen_ai.operation.name": "retrieve"})

    def on_retriever_end(self, documents, *, run_id, **kwargs):
        span = self._spans.get(run_id)
        if span is not None:
            span.set_attribute("retrieval.documents.count", len(documents))
        self._end(run_id)

    def on_retriever_error(self, error, *, run_id, **kwargs):
        self._end(run_id, error)
