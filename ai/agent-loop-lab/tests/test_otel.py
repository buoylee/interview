from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agent_loop.config import Settings
from agent_loop.otel import init_tracing


def test_init_tracing_with_injected_exporter_records_spans():
    exporter = InMemorySpanExporter()
    settings = Settings("u", "k", "m", "", "", "")
    tracer, provider = init_tracing(settings, exporter=exporter)
    with tracer.start_as_current_span("wiring-check"):
        pass
    provider.shutdown()  # 刷 BatchSpanProcessor
    spans = exporter.get_finished_spans()
    assert [s.name for s in spans] == ["wiring-check"]
    assert spans[0].resource.attributes["service.name"] == "agent-loop-lab"
