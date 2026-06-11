"""OTel tracing 初始化。配置了 Langfuse 就 OTLP 导出,否则打到控制台。"""
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from agent_loop.config import Settings, langfuse_otlp_config


def init_tracing(settings: Settings, exporter=None):
    """返回 (tracer, provider)。调用方退出前必须 provider.shutdown() 刷掉 batch 缓冲。"""
    if exporter is None:
        otlp = langfuse_otlp_config(settings)
        if otlp is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            endpoint, headers = otlp
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        else:
            exporter = ConsoleSpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "agent-loop-lab"}))
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider.get_tracer("agent_loop"), provider
