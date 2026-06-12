"""校验 `ai/langchain/06-tool-calling.md` 的关键声称。

每个测试上方注释指向它所证明的笔记章节。
- 离线测试:纯机制,用 langchain_core 内置工具,确定性、无需 key、始终绿。
- live 测试(`@pytest.mark.live`):调真实 OpenAI(gpt-4o-mini),无 key 时自动 skip。

跑法:
    uv run pytest tests/test_06_tool_calling.py            # 仅离线
    uv run pytest tests/test_06_tool_calling.py -m live    # 真实 OpenAI(需 key)
"""

from typing import ClassVar

import pytest

# 笔记 §四 用的就是 `from langchain.messages import ...`,这条 import 路径在 v1.x 仍有效
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool, tool

# 笔记 §2.1 用 `args_schema.model_json_schema()` 看 schema;查 OpenAI tool schema 的稳定路径是这条
from langchain_core.utils.function_calling import convert_to_openai_tool


# --------------------------------------------------------------------------- #
# 复用的离线工具:确定性,无副作用
# --------------------------------------------------------------------------- #


@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。

    Args:
        city: 城市名称，如 "北京", "上海"
    """
    weather_db = {"北京": "晴天 25°C", "上海": "多云 22°C"}
    return weather_db.get(city, f"未找到 {city} 的天气数据")


# --------------------------------------------------------------------------- #
# 离线:纯机制,确定性,无需 API key
# --------------------------------------------------------------------------- #


# §2.1 —— @tool 把普通函数变成 BaseTool,带 name / description / args
def test_tool_decorator_produces_basetool():
    assert isinstance(get_weather, BaseTool)
    assert get_weather.name == "get_weather"
    # name 默认取函数名,description 取自 docstring(默认整段,含 Args)
    assert "查询指定城市的实时天气" in get_weather.description
    # args 由函数签名 + 类型注解推导:city 是 string
    assert get_weather.args == {"city": {"title": "City", "type": "string"}}


# §2.1 / §四 —— tool.invoke({...}) 真正执行函数体并返回其结果
def test_tool_invoke_runs_the_function():
    assert get_weather.invoke({"city": "北京"}) == "晴天 25°C"
    # 函数内的兜底分支也真的跑到了
    assert get_weather.invoke({"city": "广州"}) == "未找到 广州 的天气数据"


# §2.1 —— 生成的 OpenAI tool schema 参数名/类型/required 正确
def test_openai_tool_schema_shape():
    schema = convert_to_openai_tool(get_weather)
    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "get_weather"
    params = fn["parameters"]
    assert params["properties"]["city"]["type"] == "string"
    assert params["required"] == ["city"]


# §2.2 —— @tool(args_schema=...) 用 Pydantic 显式定义参数:默认值/多参数都进 schema
def test_tool_with_pydantic_args_schema():
    from pydantic import BaseModel, Field

    class SearchInput(BaseModel):
        query: str = Field(description="搜索关键词")
        max_results: int = Field(default=5, description="返回结果数量")
        language: str = Field(default="zh", description="结果语言 zh/en")

    @tool(args_schema=SearchInput)
    def web_search(query: str, max_results: int = 5, language: str = "zh") -> str:
        """在互联网上搜索信息。"""
        return f"搜索 '{query}' 的结果 ({max_results} 条, {language})"

    assert set(web_search.args.keys()) == {"query", "max_results", "language"}
    assert web_search.args["query"]["type"] == "string"
    assert web_search.args["max_results"]["type"] == "integer"
    # 默认值随 schema 一起带出
    assert web_search.args["max_results"]["default"] == 5


# §2.4 —— StructuredTool.from_function 可自定义 name/description,仍是 BaseTool 且能执行
def test_structuredtool_from_function():
    def multiply(a: int, b: int) -> int:
        """将两个整数相乘"""
        return a * b

    t = StructuredTool.from_function(
        func=multiply, name="multiply", description="计算两个数的乘积"
    )
    assert isinstance(t, BaseTool)
    assert t.name == "multiply"
    assert t.description == "计算两个数的乘积"  # 显式 description 覆盖 docstring
    assert t.invoke({"a": 6, "b": 7}) == 42


# §3.2 / §4.1 —— AIMessage.tool_calls 条目形状 {id, name, args},并自动补 type="tool_call"
def test_aimessage_tool_calls_entry_shape():
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "call_abc123", "name": "get_weather", "args": {"city": "北京"}}],
    )
    entry = ai.tool_calls[0]
    assert entry["id"] == "call_abc123"
    assert entry["name"] == "get_weather"
    assert entry["args"] == {"city": "北京"}
    # 即使构造时没传 type,LangChain 也会归一化补上 "tool_call"
    assert entry["type"] == "tool_call"


# §四 4.1 —— 手动循环:用 AIMessage 的请求 id 配出 ToolMessage,二者 id 必须匹配
def test_toolmessage_pairs_with_request_id():
    ai = AIMessage(
        content="",
        tool_calls=[{"id": "call_abc123", "name": "get_weather", "args": {"city": "北京"}}],
    )
    tc = ai.tool_calls[0]
    # 手动循环:按 name 找工具 -> 执行 -> 用同一个 id 回包
    tool_map = {get_weather.name: get_weather}
    result = tool_map[tc["name"]].invoke(tc["args"])
    tool_msg = ToolMessage(content=str(result), tool_call_id=tc["id"])
    assert tool_msg.tool_call_id == ai.tool_calls[0]["id"]  # 请求-响应配对
    assert tool_msg.content == "晴天 25°C"
    # tool_call_id 是必填:缺了直接构造失败
    with pytest.raises(Exception):
        ToolMessage(content="缺 id")


# §四 4.1 —— 用完整 ToolCall dict 调 tool,直接得到一个配好 id 的 ToolMessage
def test_tool_invoke_with_toolcall_returns_toolmessage():
    msg = get_weather.invoke(
        {"type": "tool_call", "id": "call_z", "name": "get_weather", "args": {"city": "上海"}}
    )
    assert isinstance(msg, ToolMessage)
    assert msg.tool_call_id == "call_z"
    assert msg.content == "多云 22°C"


# §3.1 / §3.3 / §七 —— bind_tools 返回携带 tools 的 runnable;tool_choice / parallel 进 kwargs(全程离线)
def test_bind_tools_carries_tools_offline():
    from langchain_openai import ChatOpenAI

    # dummy key:构造 + bind 都不发网络,只有 invoke 才会真正调用
    llm = ChatOpenAI(model="gpt-4o", api_key="sk-test-dummy", temperature=0)

    @tool
    def calculator(expression: str) -> str:
        """计算数学表达式。"""
        return "42"

    bound = llm.bind_tools([get_weather, calculator])
    tools_kw = bound.kwargs["tools"]
    assert [t["function"]["name"] for t in tools_kw] == ["get_weather", "calculator"]

    # §3.3 tool_choice="get_weather" 会被规整成 OpenAI 的 {type:function, function:{name}} 结构
    forced = llm.bind_tools([get_weather], tool_choice="get_weather")
    assert forced.kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "get_weather"},
    }

    # §七 parallel_tool_calls=False 原样进 kwargs
    no_parallel = llm.bind_tools([get_weather], parallel_tool_calls=False)
    assert no_parallel.kwargs["parallel_tool_calls"] is False


# §6.1 —— response_format="content_and_artifact":工具返回 (content, artifact),
#         artifact 落在 ToolMessage.artifact,不混进对话文本
def test_tool_content_and_artifact():
    counter = {"n": 0}

    @tool(response_format="content_and_artifact")
    def generate_chart(data: str) -> tuple[str, dict]:
        """生成图表数据"""
        counter["n"] += 1
        return "图表已生成", {"type": "bar", "values": [1, 2, 3]}

    msg = generate_chart.invoke(
        {"type": "tool_call", "id": "c1", "name": "generate_chart", "args": {"data": "x"}}
    )
    assert isinstance(msg, ToolMessage)
    assert msg.content == "图表已生成"  # 进对话的只有 content
    assert msg.artifact == {"type": "bar", "values": [1, 2, 3]}  # 结构化数据单独留存
    assert counter["n"] == 1  # 函数体确实跑了一次


# §2.1 (隐含) —— pydantic-safe 计数器:确认 tool.invoke 每次都真正执行函数体
def test_tool_invoke_actually_calls_each_time():
    class _Counter:
        calls: ClassVar[int] = 0

    @tool
    def ping(x: str) -> str:
        """回声工具"""
        _Counter.calls += 1
        return x

    try:
        ping.invoke({"x": "a"})
        ping.invoke({"x": "b"})
        assert _Counter.calls == 2  # 没有缓存,两次调用 = 两次执行
    finally:
        _Counter.calls = 0  # 复位全局状态


# --------------------------------------------------------------------------- #
# live:真实 OpenAI(gpt-4o-mini),无 OPENAI_API_KEY 时自动 skip
# --------------------------------------------------------------------------- #


# §3.1 / §3.2 —— 给了工具,真实模型会 EMIT 一个命名该工具的 tool_calls 条目(只有真模型能证明)
@pytest.mark.live
def test_live_model_emits_tool_call():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    bound = llm.bind_tools([get_weather])
    resp = bound.invoke([HumanMessage(content="北京今天天气怎么样?")])
    assert isinstance(resp, AIMessage)
    assert resp.tool_calls, "期望模型决定调用工具,却没有 tool_calls"
    tc = resp.tool_calls[0]
    assert tc["name"] == "get_weather"
    assert "city" in tc["args"]
    assert tc["id"]  # 有 id 才能配 ToolMessage


# §3.3 —— tool_choice 强制使用某工具:真实模型必定 EMIT 该工具(即便问题与工具无关)
@pytest.mark.live
def test_live_tool_choice_forces_tool():
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    forced = llm.bind_tools([get_weather], tool_choice="get_weather")
    resp = forced.invoke([HumanMessage(content="随便聊聊")])
    assert resp.tool_calls
    assert resp.tool_calls[0]["name"] == "get_weather"
