# tests/test_obs_otel.py
import base64

from mvp_agentic_rag.core.config import Settings
from mvp_agentic_rag.obs.otel import langfuse_otlp_config


def _settings(**overrides):
    base = dict(
        obs_backend="otel",
        langfuse_public_key="pk-lf-1",
        langfuse_secret_key="sk-lf-2",
        langfuse_host="http://localhost:3000",
    )
    base.update(overrides)
    return Settings(**base)


def test_otlp_config_builds_langfuse_endpoint_and_basic_auth():
    endpoint, headers = langfuse_otlp_config(_settings())
    assert endpoint == "http://localhost:3000/api/public/otel/v1/traces"
    expected = base64.b64encode(b"pk-lf-1:sk-lf-2").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["x-langfuse-ingestion-version"] == "4"


def test_otlp_config_none_when_keys_missing():
    assert langfuse_otlp_config(_settings(langfuse_public_key="")) is None


from types import SimpleNamespace
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mvp_agentic_rag.obs.otel import OTelTraceCallback


@pytest.fixture()
def otel_cb():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    cb = OTelTraceCallback(provider.get_tracer("test"))
    yield cb, exporter
    provider.shutdown()


def _llm_result(input_tokens=10, output_tokens=5):
    msg = SimpleNamespace(usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens,
                                          "total_tokens": input_tokens + output_tokens})
    return SimpleNamespace(generations=[[SimpleNamespace(message=msg)]])


def test_chat_span_with_usage(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_chat_model_start({}, [], run_id=run_id, parent_run_id=None,
                           invocation_params={"model_name": "gpt-test"})
    cb.on_llm_end(_llm_result(), run_id=run_id)
    (span,) = exporter.get_finished_spans()
    assert span.name == "chat gpt-test"
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.request.model"] == "gpt-test"
    assert span.attributes["gen_ai.usage.input_tokens"] == 10
    assert span.attributes["gen_ai.usage.output_tokens"] == 5


def test_tool_span_nested_under_parent(otel_cb):
    cb, exporter = otel_cb
    parent_id, child_id = uuid4(), uuid4()
    cb.on_chat_model_start({}, [], run_id=parent_id, parent_run_id=None,
                           invocation_params={"model_name": "m"})
    cb.on_tool_start({"name": "retrieve_kb"}, "查询", run_id=child_id, parent_run_id=parent_id)
    cb.on_tool_end("结果", run_id=child_id)
    cb.on_llm_end(_llm_result(), run_id=parent_id)
    spans = {s.name: s for s in exporter.get_finished_spans()}
    tool = spans["execute_tool retrieve_kb"]
    assert tool.attributes["gen_ai.operation.name"] == "execute_tool"
    assert tool.attributes["gen_ai.tool.name"] == "retrieve_kb"
    assert tool.parent.span_id == spans["chat m"].context.span_id


def test_tool_error_sets_status(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_tool_start({"name": "boom"}, "x", run_id=run_id, parent_run_id=None)
    cb.on_tool_error(RuntimeError("炸了"), run_id=run_id)
    (span,) = exporter.get_finished_spans()
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR


def test_retriever_span_records_doc_count(otel_cb):
    cb, exporter = otel_cb
    run_id = uuid4()
    cb.on_retriever_start({}, "查询", run_id=run_id, parent_run_id=None)
    cb.on_retriever_end([SimpleNamespace(), SimpleNamespace(), SimpleNamespace()], run_id=run_id)
    (span,) = exporter.get_finished_spans()
    assert span.name == "retrieve kb"
    assert span.attributes["gen_ai.operation.name"] == "retrieve"
    assert span.attributes["retrieval.documents.count"] == 3


def test_orphan_end_is_noop(otel_cb):
    cb, exporter = otel_cb
    cb.on_llm_end(_llm_result(), run_id=uuid4())  # 没有对应 start,不得抛异常
    assert exporter.get_finished_spans() == ()


from mvp_agentic_rag.obs.backends import get_observability_callbacks


def test_backend_otel_appends_otel_callback():
    s = _settings(langfuse_public_key="", langfuse_secret_key="")  # 无 key→控制台 exporter,无网络
    callbacks = get_observability_callbacks(s)
    assert any(type(c).__name__ == "OTelTraceCallback" for c in callbacks)


def test_backend_none_has_no_otel_callback():
    s = _settings(obs_backend="none")
    callbacks = get_observability_callbacks(s)
    assert not any(type(c).__name__ == "OTelTraceCallback" for c in callbacks)
