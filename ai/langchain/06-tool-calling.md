# 第3章：Tool Calling — 让 LLM 使用工具

> Tool Calling 是 Agent 的前置能力——LLM 本身只能生成文本，通过 Tool Calling，它可以搜索、计算、调 API、操作数据库。

---

## 一、Tool Calling 是什么

### 1.1 核心概念

```
传统 LLM: 用户问 → LLM 凭记忆回答 (可能过时或错误)

Tool Calling:
  用户问 → LLM 判断需要工具 → 输出工具名+参数 → 你执行工具 → 结果返回 LLM → LLM 生成最终回答
```

**关键理解**: LLM **不执行**工具，它只**决定**调哪个工具、传什么参数。真正的执行在你的代码中。

### 1.2 工作流程

```
用户: "北京今天天气怎么样?"
  ↓
LLM 思考: "用户问天气，我需要调用 get_weather 工具"
  ↓
LLM 输出 (不是文本, 是结构化调用):
  tool_calls: [{name: "get_weather", args: {city: "北京"}}]
  ↓
你的代码执行: get_weather("北京") → "晴天, 25°C"
  ↓
把结果作为 ToolMessage 发回给 LLM
  ↓
LLM 生成最终回答: "北京今天是晴天, 气温25°C, 适合出门~"
```

### 1.3 面试核心理解

> **Q: Tool Calling 和 Function Calling 有什么区别？**
>
> A: **Tool Calling 是 Function Calling 的进化版**。Function Calling 是 OpenAI 2023 年首推的概念，每次只能调一个函数。Tool Calling 是 2024 年的标准术语，支持**一次调多个工具** (parallel tool calls)。在 LangChain 中统一使用 Tool Calling 的概念。

---

## 二、定义 Tool

### 2.1 @tool 装饰器 — 最简单

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气。

    Args:
        city: 城市名称，如 "北京", "上海"
    """
    # 实际应该调天气 API
    weather_db = {"北京": "晴天 25°C", "上海": "多云 22°C"}
    return weather_db.get(city, f"未找到 {city} 的天气数据")

# 查看生成的工具信息
print(get_weather.name)          # "get_weather"
print(get_weather.description)   # "查询指定城市的实时天气。"
print(get_weather.args_schema.model_json_schema())
# {"properties": {"city": {"type": "string"}}, "required": ["city"]}
```

**⚠️ 面试关键**: **docstring 非常重要！** LLM 根据 `name` + `description` + `args_schema` 决定是否调用这个工具、传什么参数。

### 2.2 使用 Pydantic 定义参数 Schema

```python
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class SearchInput(BaseModel):
    query: str = Field(description="搜索关键词")
    max_results: int = Field(default=5, description="返回结果数量")
    language: str = Field(default="zh", description="结果语言 zh/en")

@tool(args_schema=SearchInput)
def web_search(query: str, max_results: int = 5, language: str = "zh") -> str:
    """在互联网上搜索信息。适用于需要最新信息或事实性问题。"""
    return f"搜索 '{query}' 的结果 ({max_results} 条, {language})"
```

### 2.3 BaseTool 类 — 完全自定义

```python
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Optional, Type

class CalculatorInput(BaseModel):
    expression: str = Field(description="数学表达式，如 '2 + 3 * 4'")

class Calculator(BaseTool):
    name: str = "calculator"
    description: str = "计算数学表达式。当需要精确计算时使用。"
    args_schema: Type[BaseModel] = CalculatorInput

    def _run(self, expression: str) -> str:
        """同步执行"""
        try:
            result = eval(expression)  # 注意: 生产环境不要用 eval
            return str(result)
        except Exception as e:
            return f"计算错误: {e}"

    async def _arun(self, expression: str) -> str:
        """异步执行"""
        return self._run(expression)

calc = Calculator()
print(calc.invoke({"expression": "2 + 3 * 4"}))  # "14"
```

### 2.4 StructuredTool.from_function() — 中间方案

```python
from langchain_core.tools import StructuredTool

def multiply(a: int, b: int) -> int:
    """将两个整数相乘"""
    return a * b

tool = StructuredTool.from_function(
    func=multiply,
    name="multiply",
    description="计算两个数的乘积",
)
```

### 2.5 三种方式对比

| 方式 | 复杂度 | 适用场景 | 推荐度 |
|------|--------|----------|--------|
| `@tool` 装饰器 | ⭐ 最简单 | 90% 的场景 | ⭐⭐⭐ |
| `StructuredTool.from_function()` | ⭐⭐ | 需要自定义 name/description | ⭐⭐ |
| `BaseTool` 类 | ⭐⭐⭐ 最灵活 | 需要异步、缓存、复杂逻辑 | ⭐ |

---

## 三、将 Tool 绑定到 LLM

### 3.1 bind_tools()

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# 绑定工具
tools = [get_weather, web_search, Calculator()]
llm_with_tools = llm.bind_tools(tools)

# 调用 — LLM 会决定是否使用工具
response = llm_with_tools.invoke("北京今天天气怎么样？")

# 检查是否有 tool calls
if response.tool_calls:
    for tc in response.tool_calls:
        print(f"工具: {tc['name']}")
        print(f"参数: {tc['args']}")
        print(f"ID:   {tc['id']}")
else:
    print(f"直接回答: {response.content}")
```

### 3.2 response.tool_calls 结构

```python
response = llm_with_tools.invoke("北京天气怎么样？")

# response.tool_calls 是一个列表
# [
#   {
#     "name": "get_weather",
#     "args": {"city": "北京"},
#     "id": "call_abc123",
#     "type": "tool_call"
#   }
# ]

# 如果 LLM 决定同时调多个工具 (Parallel Tool Calls):
response = llm_with_tools.invoke("北京和上海的天气")
# response.tool_calls 可能有 2 个元素
```

### 3.3 tool_choice 参数 — 强制使用工具

```python
# 强制 LLM 必须使用某个工具
llm_must_use_tool = llm.bind_tools(
    tools,
    tool_choice="get_weather"  # 强制使用 get_weather
)

# 强制使用任意一个工具 (不能直接回答)
llm_must_use_tool = llm.bind_tools(
    tools,
    tool_choice="any"  # 必须调一个工具，不能不调
)

# 不限制 (默认)
llm_auto = llm.bind_tools(
    tools,
    tool_choice="auto"  # LLM 自行决定
)
```

---

## 四、手动执行 Tool Call 循环

理解这个循环是理解 Agent 的前提。

```python
from langchain.messages import HumanMessage, ToolMessage

# 1. 用户输入
messages = [HumanMessage(content="北京今天天气怎么样？")]

# 2. LLM 决定调工具
response = llm_with_tools.invoke(messages)
messages.append(response)  # 把 AIMessage 加入历史

# 3. 执行工具
if response.tool_calls:
    for tool_call in response.tool_calls:
        # 找到对应的工具
        tool_map = {t.name: t for t in tools}
        tool = tool_map[tool_call["name"]]

        # 执行工具
        result = tool.invoke(tool_call["args"])

        # 构造 ToolMessage
        tool_msg = ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"],  # 必须匹配!
        )
        messages.append(tool_msg)

# 4. LLM 根据工具结果生成最终回答
final_response = llm_with_tools.invoke(messages)
print(final_response.content)
# "北京今天是晴天，气温25°C，是个适合出门的好天气！"
```

### 4.1 面试必知的完整消息流

```python
# 完整的消息列表最终是这样的:
messages = [
    HumanMessage(content="北京今天天气怎么样？"),           # 1. 用户
    AIMessage(content="", tool_calls=[{                    # 2. LLM 决定调工具
        "name": "get_weather",
        "args": {"city": "北京"},
        "id": "call_abc123"
    }]),
    ToolMessage(content="晴天 25°C",                       # 3. 工具结果
                tool_call_id="call_abc123"),
    AIMessage(content="北京今天是晴天，气温25°C..."),         # 4. LLM 最终回答
]
```

---

## 五、内置工具与 Toolkit

### 5.1 常用内置工具

```python
# Tavily 搜索 (推荐)
from langchain_community.tools.tavily_search import TavilySearchResults
search = TavilySearchResults(max_results=3)

# Wikipedia
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
wiki = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

# Python REPL (执行 Python 代码)
from langchain_community.tools import PythonREPLTool
python_repl = PythonREPLTool()

# DuckDuckGo 搜索 (无需 API key)
from langchain_community.tools import DuckDuckGoSearchRun
ddg_search = DuckDuckGoSearchRun()
```

### 5.2 包装任意 API 为 Tool

```python
import httpx
from langchain_core.tools import tool

@tool
def get_stock_price(symbol: str) -> str:
    """查询股票实时价格。

    Args:
        symbol: 股票代码，如 AAPL, GOOGL, TSLA
    """
    # 实际应调用股票 API
    response = httpx.get(f"https://api.example.com/stock/{symbol}")
    data = response.json()
    return f"{symbol}: ${data['price']}"
```

---

## 六、高级工具特性

### 6.1 工具返回 Artifacts

工具可以返回结构化数据 (artifact)，不混入对话消息中。

```python
from langchain_core.tools import tool

@tool(response_format="content_and_artifact")
def generate_chart(data: str) -> tuple[str, dict]:
    """生成图表数据"""
    chart_data = {"type": "bar", "values": [1, 2, 3]}
    return "图表已生成", chart_data  # (content, artifact)
```

### 6.2 错误处理

```python
@tool(handle_tool_error=True)
def risky_tool(input: str) -> str:
    """可能失败的工具"""
    if not input:
        raise ValueError("输入不能为空")
    return f"处理: {input}"

# handle_tool_error=True 时，异常会被捕获并作为错误消息返回给 LLM
# LLM 可以看到错误并决定是否重试或换个方式
```

### 6.3 工具的 Description 设计原则

```python
# ❌ 差的描述
@tool
def search(q: str) -> str:
    """搜索"""  # 太简短，LLM 不知道什么时候该用
    ...

# ✅ 好的描述
@tool
def web_search(query: str) -> str:
    """在互联网上搜索最新信息。

    当需要回答以下类型的问题时使用此工具：
    - 最新新闻、事件
    - 实时数据（天气、股价、体育比分）
    - 你不确定或知识可能过时的事实性问题

    不要用于：
    - 常识性问题
    - 数学计算（请用 calculator 工具）

    Args:
        query: 搜索关键词，尽量具体明确
    """
    ...
```

---

## 七、Parallel Tool Calls — 并行工具调用

```python
# LLM 可以一次请求多个工具调用
response = llm_with_tools.invoke("北京和上海的天气分别怎么样？")

# response.tool_calls 可能返回:
# [
#   {"name": "get_weather", "args": {"city": "北京"}, "id": "call_1"},
#   {"name": "get_weather", "args": {"city": "上海"}, "id": "call_2"},
# ]

# 你可以并行执行这些工具调用
import asyncio

async def execute_tools_parallel(tool_calls, tool_map):
    tasks = [
        asyncio.to_thread(tool_map[tc["name"]].invoke, tc["args"])
        for tc in tool_calls
    ]
    return await asyncio.gather(*tasks)

# 如果不想并行调用，可以关闭
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)
```

---

## 八、练习任务

### 基础练习
- [ ] 用 `@tool` 创建 3 个工具：天气查询、计算器、搜索
- [ ] 用 `bind_tools()` 绑定到 LLM
- [ ] 手动实现一次完整的 Tool Call 循环 (发送→执行→回传)

### 进阶练习
- [ ] 包装一个真实 API 为 LangChain Tool
- [ ] 实现并行工具调用的处理逻辑
- [ ] 用 `tool_choice` 强制 LLM 使用特定工具

### 面试模拟
- [ ] 解释 Tool Calling 的完整工作流程
- [ ] 画出消息列表在 Tool Call 过程中的变化
- [ ] 说明 tool description 对 LLM 决策的影响
- [ ] 比较 @tool、StructuredTool、BaseTool 的适用场景

---

> **本章掌握后，你应该能**：定义自定义工具，将工具绑定到 LLM，理解并手动实现 Tool Calling 循环。这是理解 Agent 的必要前提。
