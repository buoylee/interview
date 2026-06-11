# tests/test_loop.py
import pytest

from agent_loop.loop import MaxTurnsExceeded, run_agent
from agent_loop.tools import ToolSpec
from tests.fakes import FakeChatClient, final_response, tool_call_response

ECHO = ToolSpec(
    name="echo",
    description="原样返回 text",
    parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    handler=lambda text: f"echo:{text}",
)

BOOM = ToolSpec(
    name="boom",
    description="总是抛异常",
    parameters={"type": "object", "properties": {}},
    handler=lambda: (_ for _ in ()).throw(RuntimeError("炸了")),
)


def test_tool_call_then_final_answer(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "hi"}), final_response("done")])
    result = run_agent(client, "m", [ECHO], "问题", tracer)
    assert result.final_text == "done"
    assert result.turns == 2
    assert result.tool_calls == ["echo"]
    # 工具结果以 role=tool 回填进了第二次请求
    second_messages = client.calls[1]["messages"]
    assert {"role": "tool", "tool_call_id": "call_1", "content": "echo:hi"} in second_messages


def test_tool_exception_fed_back_as_error_message(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("boom", {}), final_response("recovered")])
    result = run_agent(client, "m", [BOOM], "问题", tracer)
    assert result.final_text == "recovered"
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert tool_msg["content"].startswith("ERROR")


def test_unknown_tool_fed_back_as_error(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("ghost", {}), final_response("ok")])
    result = run_agent(client, "m", [ECHO], "问题", tracer)
    tool_msg = [m for m in client.calls[1]["messages"] if m["role"] == "tool"][0]
    assert "未知工具" in tool_msg["content"]
    assert result.final_text == "ok"


def test_max_turns_raises(tracing):
    tracer, _ = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "x"}, call_id=f"c{i}") for i in range(3)])
    with pytest.raises(MaxTurnsExceeded):
        run_agent(client, "m", [ECHO], "问题", tracer, max_turns=3)


def test_spans_follow_genai_conventions(tracing):
    tracer, exporter = tracing
    client = FakeChatClient([tool_call_response("echo", {"text": "hi"}), final_response("done")])
    run_agent(client, "gpt-test", [ECHO], "问题", tracer)
    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert set(spans) == {"invoke_agent doc-qa", "chat gpt-test", "execute_tool echo"}
    agent = spans["invoke_agent doc-qa"].attributes
    assert agent["gen_ai.operation.name"] == "invoke_agent"
    llm = spans["chat gpt-test"].attributes
    assert llm["gen_ai.operation.name"] == "chat"
    assert llm["gen_ai.request.model"] == "gpt-test"
    assert llm["gen_ai.usage.input_tokens"] == 10
    tool = spans["execute_tool echo"].attributes
    assert tool["gen_ai.operation.name"] == "execute_tool"
    assert tool["gen_ai.tool.name"] == "echo"
    # 父子关系:chat / execute_tool 都挂在 invoke_agent 下
    root_id = spans["invoke_agent doc-qa"].context.span_id
    assert spans["chat gpt-test"].parent.span_id == root_id
    assert spans["execute_tool echo"].parent.span_id == root_id
