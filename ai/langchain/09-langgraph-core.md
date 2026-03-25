# 第5章：LangGraph 核心概念 — 状态图编排引擎

> LangGraph 是 LangChain 生态的底层编排引擎，用「图」来建模复杂的 AI 工作流。掌握它，就掌握了构建高级 Agent 的能力。

---

## 一、为什么需要 LangGraph

### 1.1 LCEL 的局限

```
LCEL:  A → B → C (线性管道)
问题:  无法表达循环、复杂分支、有状态的工作流

Agent 需要: LLM → 工具 → LLM → 工具 → ... → 最终回答 (循环!)
            这种循环结构 LCEL 表达不了
```

### 1.2 LangGraph 解决什么问题

| 需求 | LCEL | LangGraph |
|------|------|-----------|
| 循环 (Agent 循环) | ❌ | ✅ |
| 条件分支 (多路由) | ⚠️ 有限 | ✅ 完整 |
| 共享状态 | ❌ | ✅ State |
| 持久化 (暂停/恢复) | ❌ | ✅ Checkpointer |
| Human-in-the-loop | ❌ | ✅ interrupt() |
| 流式事件 | ⚠️ 部分 | ✅ 完整 |

---

## 二、核心三要素

### 2.1 State — 共享状态

State 是贯穿整个图的共享数据结构，**每个节点都可以读取和更新它**。

```python
from typing import TypedDict, Annotated
from langgraph.graph import add_messages

# 方式1: 自定义 State
class MyState(TypedDict):
    messages: Annotated[list, add_messages]  # 消息列表 (用 Reducer 累加)
    current_step: str                         # 当前步骤
    results: dict                             # 中间结果

# 方式2: 使用内置 MessagesState (最常用)
from langgraph.graph import MessagesState
# 等价于: class MessagesState(TypedDict):
#             messages: Annotated[list, add_messages]
```

### 2.2 Reducer — 状态如何更新

```python
# 关键概念: Annotated[type, reducer_function]
# Reducer 决定新值如何与旧值合并

# add_messages: 不覆盖, 而是追加到列表
messages: Annotated[list, add_messages]
# 如果node返回 {"messages": [new_msg]}, 结果是 state.messages + [new_msg]

# 没有 Reducer: 直接覆盖
current_step: str
# 如果node返回 {"current_step": "think"}, 结果是 state.current_step = "think"

# 自定义 Reducer
from operator import add
count: Annotated[int, add]  # 用加法累加
# 如果node返回 {"count": 1}, 结果是 state.count + 1
```

### 2.3 面试深度问题

> **Q: 为什么 messages 需要用 `Annotated[list, add_messages]`，而不是普通的 `list`？**
>
> A: 如果用普通 `list`，每个节点返回的 `{"messages": [...]}` 会**覆盖**之前的所有消息，导致历史丢失。`add_messages` 是一个 Reducer 函数，它的作用是将新消息**追加**到现有列表中，而非覆盖。并且它还能正确处理 ToolMessage 的 ID 匹配。这是 LangGraph 状态管理的核心设计——**用 Reducer 控制状态如何更新**。

### 2.4 Node — 节点 (处理函数)

Node 就是普通的 Python 函数，接收 State，返回 State 的部分更新。

```python
from langchain_openai import ChatOpenAI
from langchain.messages import SystemMessage

llm = ChatOpenAI(model="gpt-4o")

def chatbot(state: MessagesState):
    """聊天节点 — 调用 LLM"""
    response = llm.invoke(
        [SystemMessage(content="你是一个有帮助的助手")]
        + state["messages"]
    )
    return {"messages": [response]}  # 返回要更新的字段

def search(state: MessagesState):
    """搜索节点 — 执行搜索"""
    query = state["messages"][-1].content
    results = web_search(query)
    return {"messages": [AIMessage(content=results)]}
```

**关键理解**: 节点只返回需要更新的字段，不需要返回完整 State。

### 2.5 Edge — 边 (流转逻辑)

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(MessagesState)

# 添加节点
graph.add_node("chatbot", chatbot)
graph.add_node("search", search)

# 固定边 — 无条件跳转
graph.add_edge(START, "chatbot")  # 入口 → chatbot
graph.add_edge("search", "chatbot")  # search → chatbot (回到循环)

# 条件边 — 根据状态决定走哪
def should_search(state: MessagesState):
    """决定是否需要搜索"""
    last_msg = state["messages"][-1]
    if last_msg.tool_calls:
        return "search"
    return END

graph.add_conditional_edges(
    "chatbot",          # 从哪个节点出发
    should_search,      # 决策函数
    ["search", END],    # 可能的目标节点
)

# 编译
app = graph.compile()
```

---

## 三、构建第一个 LangGraph Agent

### 3.1 完整示例

```python
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.messages import SystemMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END

# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """查询城市天气"""
    return f"{city}: 晴天 25°C"

@tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

tools = [get_weather, calculator]
tool_map = {t.name: t for t in tools}

# 2. 定义 LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# 3. 定义节点
def llm_call(state: MessagesState):
    """LLM 节点 — 思考并决定是否使用工具"""
    response = llm_with_tools.invoke(
        [SystemMessage(content="你是一个有帮助的助手")] + state["messages"]
    )
    return {"messages": [response]}

def tool_node(state: MessagesState):
    """工具节点 — 执行 LLM 请求的工具调用"""
    results = []
    for tc in state["messages"][-1].tool_calls:
        result = tool_map[tc["name"]].invoke(tc["args"])
        results.append(ToolMessage(
            content=str(result),
            tool_call_id=tc["id"],
        ))
    return {"messages": results}

# 4. 定义路由
def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END

# 5. 构建图
graph = StateGraph(MessagesState)
graph.add_node("llm_call", llm_call)
graph.add_node("tool_node", tool_node)
graph.add_edge(START, "llm_call")
graph.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
graph.add_edge("tool_node", "llm_call")  # 工具结果 → 回到 LLM

# 6. 编译
agent = graph.compile()

# 7. 可视化
from IPython.display import Image, display
display(Image(agent.get_graph().draw_mermaid_png()))

# 8. 运行
result = agent.invoke({
    "messages": [("human", "北京天气怎么样？温度乘以3是多少？")]
})
for msg in result["messages"]:
    print(f"{msg.type}: {msg.content or msg.tool_calls}")
```

### 3.2 执行流程图

```
START
  ↓
llm_call: LLM 思考 → "需要查天气" → tool_calls: [get_weather(北京)]
  ↓ (条件边: 有 tool_calls → tool_node)
tool_node: 执行 get_weather → "晴天 25°C"
  ↓ (固定边: → llm_call)
llm_call: LLM 思考 → "25°C × 3" → tool_calls: [calculator("25*3")]
  ↓ (条件边: 有 tool_calls → tool_node)
tool_node: 执行 calculator → "75"
  ↓ (固定边: → llm_call)
llm_call: LLM 思考 → "我有所有信息了" → content: "北京晴天25°C, ×3=75"
  ↓ (条件边: 无 tool_calls → END)
END
```

---

## 四、Checkpointing — 持久化

### 4.1 为什么需要 Checkpointing

```
没有 Checkpointing:
  对话1: "北京天气?" → 回答
  对话2: "那上海呢?" → "你在说什么?" (没有上下文)

有 Checkpointing:
  对话1: "北京天气?" → 回答 (保存 state)
  对话2: "那上海呢?" → "上海也是..." (恢复上下文)
```

### 4.2 基本使用

```python
from langgraph.checkpoint.memory import MemorySaver

# 内存 Checkpointer (开发用)
checkpointer = MemorySaver()
agent = graph.compile(checkpointer=checkpointer)

# 用 thread_id 标识不同对话
config = {"configurable": {"thread_id": "user_123_session_1"}}

# 第一次对话
result1 = agent.invoke(
    {"messages": [("human", "北京天气怎么样?")]},
    config=config,
)

# 第二次对话 — 自动恢复历史!
result2 = agent.invoke(
    {"messages": [("human", "比昨天高了几度?")]},
    config=config,  # 同一个 thread_id
)
```

### 4.3 生产级 Checkpointer

```python
# SQLite (适合单机)
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# PostgreSQL (适合分布式)
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://user:pass@localhost:5432/mydb"
)
```

### 4.4 时间旅行

```python
# 获取某个 thread 的所有历史状态
states = agent.get_state_history(config)
for state in states:
    print(f"Step: {state.metadata.get('step')}")
    print(f"Messages: {len(state.values.get('messages', []))}")

# 回溯到特定状态
past_config = states[3].config  # 回到第3步
agent.update_state(past_config, {"messages": [...]})
```

---

## 五、Graph API vs Functional API

### 5.1 Graph API (前面学的)

```python
# 声明式: 定义 Node → Edge → 编译
graph = StateGraph(State)
graph.add_node("a", fn_a)
graph.add_node("b", fn_b)
graph.add_edge(START, "a")
graph.add_conditional_edges("a", decide, ["b", END])
agent = graph.compile()
```

### 5.2 Functional API (更 Pythonic)

```python
from langgraph.func import entrypoint, task
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

@task
def call_llm(messages: list[BaseMessage]):
    return llm_with_tools.invoke(messages)

@task
def call_tool(tool_call):
    return tool_map[tool_call["name"]].invoke(tool_call["args"])

@entrypoint()
def agent(messages: list[BaseMessage]):
    llm_response = call_llm(messages).result()
    while True:
        if not llm_response.tool_calls:
            break
        tool_results = [
            call_tool(tc).result() for tc in llm_response.tool_calls
        ]
        messages = add_messages(messages, [llm_response, *tool_results])
        llm_response = call_llm(messages).result()
    return add_messages(messages, llm_response)
```

### 5.3 对比

| 维度 | Graph API | Functional API |
|------|-----------|----------------|
| **风格** | 声明式 (定义节点和边) | 命令式 (写 Python 代码) |
| **可视化** | ✅ `draw_mermaid_png()` | ⚠️ 有限 |
| **调试** | 通过节点名追踪 | 通过函数追踪 |
| **灵活性** | 结构化 | 更自由 |
| **适合** | 复杂图、需要可视化 | 简单流程、快速原型 |
| **推荐** | ⭐⭐⭐ 复杂 Agent | ⭐⭐ 简单场景 |

---

## 六、常见图模式

### 6.1 顺序执行

```python
graph.add_edge(START, "step1")
graph.add_edge("step1", "step2")
graph.add_edge("step2", "step3")
graph.add_edge("step3", END)
```

### 6.2 条件路由

```python
def router(state):
    if state["type"] == "question":
        return "qa_node"
    elif state["type"] == "task":
        return "task_node"
    return "default_node"

graph.add_conditional_edges("classify", router, ["qa_node", "task_node", "default_node"])
```

### 6.3 Agent 循环

```python
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_use_tool, ["tool", END])
graph.add_edge("tool", "agent")  # 循环回 agent
```

### 6.4 并行扇出→汇聚

```python
# 一个节点触发多个并行节点
graph.add_edge("start", "research")
graph.add_edge("start", "analyze")
graph.add_edge("start", "summarize")
# 汇聚
graph.add_edge("research", "merge")
graph.add_edge("analyze", "merge")
graph.add_edge("summarize", "merge")
graph.add_edge("merge", END)
```

---

## 七、练习任务

### 基础练习
- [ ] 定义一个自定义 State (含 messages + 自定义字段)
- [ ] 构建一个 3 节点 + 条件边的简单图
- [ ] 用 `draw_mermaid_png()` 可视化你的图

### 进阶练习
- [ ] 手动实现一个完整的 ReAct Agent (不用 `create_react_agent`)
- [ ] 添加 Checkpointer 实现多轮对话持久化
- [ ] 用 Functional API 重写同样的 Agent

### 面试模拟
- [ ] 画出 LangGraph Agent 的图结构 (节点和边)
- [ ] 解释 State、Node、Edge 三者的关系
- [ ] 说明 Reducer (如 add_messages) 的作用和必要性
- [ ] 比较 Graph API 和 Functional API

---

> **本章掌握后，你应该能**：用 LangGraph 从零构建 Agent，理解状态管理和持久化，能可视化和调试图结构。
