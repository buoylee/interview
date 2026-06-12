"""校验 `ai/langchain/07-agents.md` 的关键声称。

本章是「Agent = LLM + Tools + 循环」。绝大部分机制都能离线确定性证明:
不用真实 LLM,而是用一个「按脚本返回 tool_calls 的假模型」来驱动整个 ReAct 循环,
从而把笔记里关于「调工具 → 得结果 → 给最终答案」的声称变成可重复的断言。

每个测试上方注释指向它所证明的笔记章节(`# §X.Y — <claim>`)。

笔记的 import 路径核对(实测 langgraph 1.2.4 / langchain 1.3.7):
- 笔记 §2.1 用 `from langgraph.prebuilt import create_react_agent` —— **该路径仍可用,但已 DEPRECATED**。
  调用时会发 `LangGraphDeprecatedSinceV10`,提示迁移到 `from langchain.agents import create_agent`。
  本文件沿用笔记教的旧路径(它仍工作),并把 deprecation 漂移记录在此。
  关键差异:旧 `create_react_agent` 的图节点叫 **agent / tools**(正是 §2.4 所述);
  新 `create_agent` 的节点叫 **model / tools**(节点名变了)。
- `from langgraph.prebuilt import ToolNode` —— 有效。注意 ToolNode 单独 invoke 在 1.x 需要注入
  Runtime(内部细节),所以本文件把它放进一张编译图里跑——这也更贴近真实用法。
- 笔记 §六 6.1 的 `recursion_limit` —— 实测命中上限会抛 `langgraph.errors.GraphRecursionError`。

跑法:
    uv run pytest tests/test_07_agents.py            # 仅离线
    uv run pytest tests/test_07_agents.py -m live    # 真实 OpenAI(需 key)
"""

from typing import ClassVar

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import tool

# 笔记 §2.1 教的路径:仍可用(但 deprecated,见模块 docstring 漂移记录)
from langgraph.prebuilt import ToolNode, create_react_agent

# 让 deprecation 警告不污染测试输出(漂移已在 docstring 记录,这里只验证行为)
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# --------------------------------------------------------------------------- #
# 复用的离线工具:确定性,无副作用
# --------------------------------------------------------------------------- #


@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。"""
    return f"{city}: 晴天 25°C"


# --------------------------------------------------------------------------- #
# 离线驱动 Agent 用的「脚本化假模型」
#
# fake_chat_models 里的 GenericFakeChatModel / FakeMessagesListChatModel 都 **不支持**
# bind_tools(会抛 NotImplementedError),没法驱动 create_react_agent。所以这里写一个
# 最小的 BaseChatModel 子类:bind_tools 返回 self(假装绑定),_generate 按对话状态出牌——
# 第一轮请求工具,看到 ToolMessage 后给最终答案。这样就能离线、确定性地跑完整个 ReAct 循环。
# --------------------------------------------------------------------------- #


class ScriptedToolModel(BaseChatModel):
    """看到非工具消息就请求 get_weather;看到 ToolMessage 就给最终答案。"""

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        last = messages[-1]
        if isinstance(last, ToolMessage):
            msg = AIMessage(content=f"最终回答: {last.content}")
        else:
            msg = AIMessage(
                content="",
                tool_calls=[{"id": "c1", "name": "get_weather", "args": {"city": "北京"}}],
            )
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):
        return self  # 假装绑定,实际忽略——离线测试不需要真的把工具塞进请求


class AlwaysCallsModel(BaseChatModel):
    """永远请求工具、永不收尾——用来制造无限循环,验证 recursion_limit。"""

    @property
    def _llm_type(self) -> str:
        return "always-calls-model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[{"id": "c1", "name": "get_weather", "args": {"city": "北京"}}],
                    )
                )
            ]
        )

    def bind_tools(self, tools, **kwargs):
        return self


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §2.1 / §2.4 —— create_react_agent 返回一个「已编译的 LangGraph」,是 Runnable,
#                内部就是 agent / tools 两个核心节点(正是 §2.4 面试题的答案)
def test_create_react_agent_returns_compiled_graph():
    from langchain_openai import ChatOpenAI

    # dummy key:构造不发网络,只有 invoke 才会真正调用
    llm = ChatOpenAI(model="gpt-4o", api_key="sk-test-dummy", temperature=0)
    agent = create_react_agent(llm, [get_weather])

    assert isinstance(agent, Runnable)  # 可 invoke / stream / batch
    assert hasattr(agent, "invoke") and hasattr(agent, "stream")
    node_names = set(agent.get_graph().nodes.keys())
    # §2.4:核心是 agent 节点(调 LLM)+ tools 节点(执行工具),外加 START/END
    assert {"agent", "tools"}.issubset(node_names)


# §2.1 / §2.2 / 一、1.2 —— 完整 ReAct 循环:Human → AI(发 tool_call) → Tool(执行) → AI(最终答案)
#                          这是本章最核心的声称,用脚本化假模型离线、确定性地证明
def test_react_loop_calls_tool_then_answers():
    agent = create_react_agent(ScriptedToolModel(), [get_weather])
    result = agent.invoke({"messages": [HumanMessage(content="北京天气怎么样?")]})

    msgs = result["messages"]
    # §2.2 笔记画的消息流:human → ai(tool_calls) → tool → ai(final)
    assert [m.type for m in msgs] == ["human", "ai", "tool", "ai"]

    # 中间那条 AIMessage 携带了对 get_weather 的工具调用
    ai_call = msgs[1]
    assert ai_call.tool_calls[0]["name"] == "get_weather"
    assert ai_call.tool_calls[0]["args"] == {"city": "北京"}

    # 工具真的被执行,ToolMessage 带回结果且 id 与请求配对
    tool_msg = msgs[2]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.content == "北京: 晴天 25°C"
    assert tool_msg.tool_call_id == ai_call.tool_calls[0]["id"]

    # §2.2 —— 最终回答 = messages[-1].content,且包含工具结果
    final = msgs[-1].content
    assert "北京: 晴天 25°C" in final


# §2.4 —— ToolNode 执行 AIMessage 里的 tool_calls,产出一个 id 配对的 ToolMessage。
#         (ToolNode 单独 invoke 在 1.x 需注入 Runtime;放进编译图里跑更稳、更贴近真实用法)
def test_toolnode_executes_tool_calls_into_toolmessage():
    from langgraph.graph import END, START, MessagesState, StateGraph

    g = StateGraph(MessagesState)
    g.add_node("tools", ToolNode([get_weather]))
    g.add_edge(START, "tools")
    g.add_edge("tools", END)
    app = g.compile()

    ai = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "get_weather", "args": {"city": "北京"}}],
    )
    out = app.invoke({"messages": [ai]})

    # 输入的 AIMessage 之后追加了一条 ToolMessage(MessagesState 走 add_messages 追加语义)
    tool_msg = out["messages"][-1]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.content == "北京: 晴天 25°C"
    assert tool_msg.tool_call_id == "call_1"  # 与请求 id 配对
    assert tool_msg.name == "get_weather"


# §2.3 —— prompt="..." 字符串会作为一条 SystemMessage 注入到模型每次看到的消息最前面
def test_prompt_string_becomes_leading_system_message():
    class CapturingModel(BaseChatModel):
        seen: ClassVar[list] = []

        @property
        def _llm_type(self) -> str:
            return "capturing-model"

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            CapturingModel.seen = list(messages)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

        def bind_tools(self, tools, **kwargs):
            return self

    try:
        agent = create_react_agent(
            CapturingModel(), [get_weather], prompt="你是一个天气助手,用中文回答。"
        )
        agent.invoke({"messages": [HumanMessage(content="hi")]})

        seen = CapturingModel.seen
        assert isinstance(seen[0], SystemMessage)  # prompt 落在最前面
        assert seen[0].content == "你是一个天气助手,用中文回答。"
        assert isinstance(seen[1], HumanMessage)  # 用户消息紧随其后
    finally:
        CapturingModel.seen = []  # 复位全局状态


# §四 4.2 —— stream_mode="updates" 逐节点吐出增量,key 是节点名;
#            一次「调一次工具」的循环正好走 agent → tools → agent
def test_stream_updates_emits_node_names_in_react_order():
    agent = create_react_agent(ScriptedToolModel(), [get_weather])

    nodes_seen = []
    for event in agent.stream(
        {"messages": [HumanMessage(content="北京天气")]}, stream_mode="updates"
    ):
        nodes_seen.extend(event.keys())  # updates 模式下 key 即节点名

    assert nodes_seen == ["agent", "tools", "agent"]  # 思考→调工具→再思考收尾


# §四 4.1 —— stream_mode="values" 每个 superstep 后吐出「完整 state」,
#            最后一个 state 的消息列表 = 完整对话历史(等价于 invoke 的结果)
def test_stream_values_yields_full_state_snapshots():
    agent = create_react_agent(ScriptedToolModel(), [get_weather])

    events = list(
        agent.stream(
            {"messages": [HumanMessage(content="北京天气")]}, stream_mode="values"
        )
    )
    # 每个 event 都是完整 state(含 messages),且消息只增不减
    lengths = [len(e["messages"]) for e in events]
    assert lengths == sorted(lengths)  # 单调不减:state 一路累积
    # 末个快照 = 完整历史,最后一条是最终答案
    final_state = events[-1]
    assert final_state["messages"][-1].type == "ai"
    assert "北京: 晴天 25°C" in final_state["messages"][-1].content


# §六 6.1 / §五 5.4 —— recursion_limit 防无限循环:模型若永不收尾,命中上限抛 GraphRecursionError
def test_recursion_limit_raises_on_infinite_loop():
    from langgraph.errors import GraphRecursionError

    agent = create_react_agent(AlwaysCallsModel(), [get_weather])
    with pytest.raises(GraphRecursionError):
        agent.invoke(
            {"messages": [HumanMessage(content="x")]},
            config={"recursion_limit": 5},  # 最多 5 步,之后强制中止
        )


# §三 3.1 —— 消息历史 = Agent 的"记忆":把上一轮的 messages 续上再 invoke,新一轮带着旧上下文
def test_message_history_threads_across_invocations():
    agent = create_react_agent(ScriptedToolModel(), [get_weather])

    first = agent.invoke({"messages": [HumanMessage(content="北京天气?")]})
    # §3.1 笔记写法:把上一轮所有消息 + 新问题一起传入
    second = agent.invoke(
        {"messages": first["messages"] + [HumanMessage(content="那上海呢?")]}
    )

    # 第二轮的历史严格包含第一轮的全部消息(上下文被带过去了)
    assert len(second["messages"]) > len(first["messages"])
    first_contents = [(m.type, m.content) for m in first["messages"]]
    second_contents = [(m.type, m.content) for m in second["messages"]]
    assert second_contents[: len(first_contents)] == first_contents


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §一 1.2 / §2.1 / §八 8.2 —— 真实 Agent 拿到工具会自己决定调用它,并产出含工具结果的最终答案
#                            (只有真模型能证明「LLM 自主决策调工具」这一核心声称)
@pytest.mark.live
def test_live_agent_invokes_tool_and_answers():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, [get_weather])
    result = agent.invoke({"messages": [HumanMessage(content="北京今天天气怎么样?")]})

    msgs = result["messages"]
    # §八 8.2:从消息流里抽出真实用过的工具名
    used_tools = [
        m.tool_calls[0]["name"]
        for m in msgs
        if isinstance(m, AIMessage) and m.tool_calls
    ]
    assert "get_weather" in used_tools  # 模型自主选择了 get_weather

    # 工具确实被执行,且最终答案里反映了工具结果
    assert any(isinstance(m, ToolMessage) for m in msgs)
    final = msgs[-1].content
    assert isinstance(msgs[-1], AIMessage) and not msgs[-1].tool_calls  # 收尾的是纯文本回答
    assert "北京" in final
