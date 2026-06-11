"""裸 agent 循环。没有框架:一个 while、一个消息列表、一张工具表。

OTel span 遵循 GenAI 语义约定(gen_ai.*):
- invoke_agent(根)→ 每轮一个 chat span + 每次工具执行一个 execute_tool span。
"""
import json
from dataclasses import dataclass, field

from opentelemetry.trace import Status, StatusCode

from agent_loop.tools import ToolSpec

SYSTEM_PROMPT = (
    "你是知识库问答助手。优先用 search_docs 检索;需要某文件完整内容时用 read_doc。"
    "回答必须基于工具返回的内容,并注明来源文件名;检索不到就明说不知道,禁止编造。"
)


class MaxTurnsExceeded(RuntimeError):
    pass


@dataclass
class AgentResult:
    final_text: str = ""
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[str] = field(default_factory=list)


def run_agent(client, model: str, tools: list[ToolSpec], user_input: str, tracer,
              max_turns: int = 8) -> AgentResult:
    tool_map = {t.name: t for t in tools}
    tool_defs = [t.to_openai() for t in tools]
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    result = AgentResult()

    with tracer.start_as_current_span(
        "invoke_agent doc-qa",
        attributes={
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "doc-qa",
            "gen_ai.request.model": model,
        },
    ) as agent_span:
        for turn in range(1, max_turns + 1):
            result.turns = turn

            with tracer.start_as_current_span(
                f"chat {model}",
                attributes={"gen_ai.operation.name": "chat", "gen_ai.request.model": model},
            ) as llm_span:
                response = client.chat.completions.create(
                    model=model, messages=messages, tools=tool_defs
                )
                usage = getattr(response, "usage", None)
                if usage is not None:
                    llm_span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
                    llm_span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)
                    result.input_tokens += usage.prompt_tokens
                    result.output_tokens += usage.completion_tokens

            msg = response.choices[0].message
            if not msg.tool_calls:  # 模型不再要工具 → 这就是最终答案,循环结束
                result.final_text = msg.content or ""
                agent_span.set_attribute("agent.turns", turn)
                return result

            # assistant 的 tool_calls 消息必须原样回填,后面的 role=tool 消息才合法
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                result.tool_calls.append(name)
                with tracer.start_as_current_span(
                    f"execute_tool {name}",
                    attributes={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name},
                ) as tool_span:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                        if name in tool_map:
                            output = tool_map[name].handler(**args)
                        else:
                            output = f"ERROR: 未知工具 {name}"
                    except Exception as exc:  # 工具失败不终止循环:错误回喂给模型自行恢复
                        output = f"ERROR: {exc}"
                        tool_span.set_status(Status(StatusCode.ERROR, str(exc)))
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": output})

        agent_span.set_status(Status(StatusCode.ERROR, "max turns exceeded"))
        raise MaxTurnsExceeded(f"agent 在 {max_turns} 轮内未产出最终答案")
