# 第3章：Agents — 核心架构与实战

> Agent = LLM + Tools + 循环。它是 LangChain 最强大的能力，也是面试高频考点。

---

## 一、Agent 是什么

### 1.1 Chain vs Agent

```
Chain (链):   固定流程  A → B → C → 结果
              开发者预先设定好每一步

Agent (智能体): 动态流程  用户输入 → LLM 决策循环 → 结果
                LLM 自己决定下一步做什么
```

| 维度 | Chain | Agent |
|------|-------|-------|
| **流程** | 固定的、预定义的 | 动态的、LLM 决策的 |
| **决策者** | 开发者 | LLM |
| **能力** | 完成预设流程 | 根据情况选择工具、多步推理 |
| **可控性** | 高 | 相对低 |
| **适用场景** | 流程明确的任务 | 需要推理和工具选择的任务 |

### 1.2 Agent 的核心循环 (ReAct)

```
用户输入
  ↓
┌──────────────────────────────────────────┐
│            Agent 循环                     │
│                                          │
│  LLM 思考 ──→ 需要工具? ──→ 是 ──→ 调用工具 │
│     ↑                          ↓         │
│     └────── 将结果加入历史 ←──── 得到结果   │
│                                          │
│              不需要 ──→ 输出最终回答        │
└──────────────────────────────────────────┘
```

**ReAct 模式**: **Re**asoning + **Act**ing

1. **Reason**: LLM 分析当前情况，决定是否需要工具
2. **Act**: 如果需要，调用工具获取信息
3. **Observe**: 观察工具返回的结果
4. **Repeat**: 根据结果继续推理，直到能给出最终答案

---

## 二、LangChain 预置 Agent

### 2.1 create_react_agent() — 最常用

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# 定义工具
@tool
def get_weather(city: str) -> str:
    """查询指定城市的实时天气"""
    return f"{city}: 晴天,25°C"

@tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

# 创建 Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
agent = create_react_agent(llm, tools=[get_weather, calculator])

# 运行
result = agent.invoke(
    {"messages": [("human", "北京今天多少度？如果温度乘以2是多少？")]}
)

# 查看所有消息
for msg in result["messages"]:
    print(f"{msg.type}: {msg.content}")
```

### 2.2 输出解析

```python
result = agent.invoke({"messages": [("human", "北京天气")]})

# result["messages"] 包含完整的对话历史:
# [0] HumanMessage:  "北京天气"
# [1] AIMessage:     tool_calls=[{name: "get_weather", args: {city: "北京"}}]
# [2] ToolMessage:   "北京: 晴天,25°C"
# [3] AIMessage:     "北京今天是晴天,气温25°C..."  ← 最终回答

# 获取最终回答
final_answer = result["messages"][-1].content
```

### 2.3 添加 System Prompt

```python
agent = create_react_agent(
    llm,
    tools=[get_weather, calculator],
    prompt="你是一个天气助手，用中文回答，回答要简洁友好。",
)
```

### 2.4 面试深度问题

> **Q: `create_react_agent()` 底层是怎么实现的？**
>
> A: 它是一个 **LangGraph 预构建图**。内部创建了一个 `StateGraph`，包含两个核心节点：(1) `agent` 节点——调用绑定了工具的 LLM；(2) `tools` 节点——执行 LLM 请求的工具调用。中间通过条件边连接：如果 LLM 输出了 `tool_calls`，就走 tools 节点；否则走 END。这形成了一个 **循环图**，Agent 可以多次调用工具直到给出最终回答。

```python
# create_react_agent 的等价 LangGraph 实现:
from langgraph.graph import StateGraph, START, END, MessagesState

def agent_node(state):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}

def tool_node(state):
    tool_msgs = []
    for tc in state["messages"][-1].tool_calls:
        result = tool_map[tc["name"]].invoke(tc["args"])
        tool_msgs.append(ToolMessage(content=result, tool_call_id=tc["id"]))
    return {"messages": tool_msgs}

def should_continue(state):
    return "tools" if state["messages"][-1].tool_calls else END

graph = StateGraph(MessagesState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", should_continue, ["tools", END])
graph.add_edge("tools", "agent")
agent = graph.compile()
```

---

## 三、Agent 的状态管理

### 3.1 消息历史 = Agent 的"记忆"

```python
# Agent 通过消息列表保持上下文
result1 = agent.invoke({
    "messages": [("human", "北京天气怎么样?")]
})

# 继续对话 (传入之前的所有消息)
result2 = agent.invoke({
    "messages": result1["messages"] + [
        ("human", "那上海呢?")
    ]
})
```

### 3.2 使用 Checkpointer 持久化

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
agent = create_react_agent(llm, tools, checkpointer=checkpointer)

# 第一次对话
config = {"configurable": {"thread_id": "user_123"}}
result1 = agent.invoke(
    {"messages": [("human", "北京天气怎么样?")]},
    config=config,
)

# 第二次对话 — 自动恢复历史！
result2 = agent.invoke(
    {"messages": [("human", "比昨天高了多少?")]},
    config=config,  # 同一个 thread_id
)
```

### 3.3 面试加分

> **Q: Agent 的消息列表会越来越长，怎么处理？**
>
> A: 这是**上下文窗口管理**问题。实践中常用策略：
> (1) **滑动窗口** — 只保留最近 N 条消息
> (2) **摘要压缩** — 用 LLM 将旧消息总结为一条 SystemMessage
> (3) **Token 预算** — 当消息总 token 超过阈值时触发压缩
> (4) **RAG 检索** — 将旧对话存入向量数据库，需要时检索

---

## 四、Agent 的流式输出

### 4.1 stream() — 逐事件流式

```python
for event in agent.stream(
    {"messages": [("human", "北京天气怎么样?")]},
    stream_mode="values",
):
    # 每个 event 是一个完整的 state
    last_msg = event["messages"][-1]
    last_msg.pretty_print()
```

### 4.2 stream_mode 选项

```python
# "values" — 每个节点输出后，返回完整 state
for event in agent.stream(input, stream_mode="values"):
    print(event["messages"][-1])

# "updates" — 只返回每个节点的增量更新
for event in agent.stream(input, stream_mode="updates"):
    for node_name, update in event.items():
        print(f"节点 {node_name}: {update}")

# "messages" — 逐 token 返回 LLM 输出
for msg, metadata in agent.stream(input, stream_mode="messages"):
    if isinstance(msg, AIMessageChunk) and msg.content:
        print(msg.content, end="", flush=True)
```

---

## 五、Agent 架构模式

### 5.1 ReAct (默认)

```
Think → Act → Observe → Think → ... → Answer
```
- **优势**: 简单、通用、内置支持
- **劣势**: 可能陷入无限循环、每步都需要 LLM 推理

### 5.2 Plan-and-Execute

```
用户输入 → 制定计划 (列出步骤) → 逐步执行 → 验证结果
```
- **优势**: 复杂任务拆解更好、计划可审查
- **劣势**: 计划可能不准确、增加延迟

### 5.3 Reflection

```
用户输入 → 初始生成 → 自我审查 → 改进 → 再审查 → ... → 输出
```
- **优势**: 输出质量高
- **劣势**: 延迟高 (多次 LLM 调用)

### 5.4 面试必知

> **Q: ReAct Agent 在实际项目中有什么缺陷？如何解决？**
>
> A: 主要缺陷：(1) **无限循环** — LLM 反复调同一个工具。解决：设 `max_iterations` 限制最大步数；(2) **工具选择错误** — LLM 选错工具或传错参数。解决：优化工具描述、用 few-shot 示例、限制可用工具集；(3) **上下文膨胀** — 多步执行积累大量消息。解决：中间结果压缩、只保留关键信息；(4) **不可预测性** — 同一输入可能走不同路径。解决：temperature=0 + 更具体的 system prompt + 评估测试集。

---

## 六、限制与安全

### 6.1 最大迭代次数

```python
# 防止无限循环
agent = create_react_agent(
    llm, tools,
    # LangGraph 中通过 recursion_limit 控制
)

result = agent.invoke(
    {"messages": [("human", "...")]},
    config={"recursion_limit": 10},  # 最多 10 步
)
```

### 6.2 工具安全

```python
# ❌ 危险: 允许执行任意代码
@tool
def run_code(code: str) -> str:
    """执行 Python 代码"""
    return str(eval(code))  # 安全隐患!

# ✅ 安全: 限制工具能力
@tool
def safe_calculator(expression: str) -> str:
    """计算数学表达式 (只支持基本运算)"""
    # 白名单方式验证
    import re
    if not re.match(r'^[\d\s\+\-\*/\(\)\.]+$', expression):
        return "错误: 只支持数字和基本运算符"
    return str(eval(expression))
```

### 6.3 Human-in-the-Loop

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    llm, tools,
    checkpointer=MemorySaver(),
)

# 使用 interrupt_before 在工具执行前暂停
# (这是 LangGraph 的特性，将在 LangGraph 章节详细讲解)
```

---

## 七、完整实战示例

### 7.1 研究助手 Agent

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def web_search(query: str) -> str:
    """搜索互联网获取最新信息"""
    # 实际接入 Tavily 或其他搜索 API
    return f"搜索 '{query}' 的结果: ..."

@tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    return str(eval(expression))

@tool
def save_note(title: str, content: str) -> str:
    """保存研究笔记"""
    with open(f"notes/{title}.md", "w") as f:
        f.write(content)
    return f"笔记 '{title}' 已保存"

llm = ChatOpenAI(model="gpt-4o", temperature=0)

agent = create_react_agent(
    llm,
    tools=[web_search, calculator, save_note],
    prompt="""你是一个专业的研究助手。
你的工作流程:
1. 理解用户的研究问题
2. 用搜索工具收集信息
3. 如果需要计算，用计算器
4. 整理研究结果
5. 如果用户要求，将结果保存为笔记

回答要有条理、引用来源。""",
)

result = agent.invoke({
    "messages": [("human", "帮我研究一下 2025 年全球 AI 市场规模")]
})
```

---

## 八、Agent 评估

### 8.1 评估维度

| 维度 | 说明 | 如何评估 |
|------|------|----------|
| **任务完成率** | 是否正确回答了问题 | 对比预期答案 |
| **工具使用准确率** | 是否选对了工具 | 检查 tool_calls 序列 |
| **效率** | 用了多少步完成 | 统计迭代次数 |
| **鲁棒性** | 面对异常输入是否稳定 | 模糊测试 |
| **成本** | Token 消耗和延迟 | 监控 usage_metadata |

### 8.2 简单评估框架

```python
test_cases = [
    {"input": "北京天气", "expected_tools": ["get_weather"], "expected_contains": "北京"},
    {"input": "3 + 5 * 2", "expected_tools": ["calculator"], "expected_contains": "13"},
]

for case in test_cases:
    result = agent.invoke({"messages": [("human", case["input"])]})
    final_answer = result["messages"][-1].content
    used_tools = [
        m.tool_calls[0]["name"]
        for m in result["messages"]
        if hasattr(m, "tool_calls") and m.tool_calls
    ]

    # 检查
    assert case["expected_contains"] in final_answer, f"回答中没有 {case['expected_contains']}"
    for t in case["expected_tools"]:
        assert t in used_tools, f"没有使用 {t} 工具"
```

---

## 九、练习任务

### 基础练习
- [ ] 用 `create_react_agent()` 创建一个带 3 个工具的 Agent
- [ ] 观察 Agent 的完整消息流 (每一步的 type 和 content)
- [ ] 实现 Agent 的流式输出

### 进阶练习
- [ ] 给 Agent 添加 Checkpointer 实现多轮对话
- [ ] 手动用 LangGraph 实现 `create_react_agent()` 的等价逻辑
- [ ] 实现一个 Plan-and-Execute 风格的 Agent

### 面试模拟
- [ ] 画出 ReAct Agent 的执行流程图
- [ ] 解释 `create_react_agent()` 的底层 LangGraph 实现
- [ ] 描述 Agent 在生产环境中的常见问题和解决方案
- [ ] 比较 ReAct、Plan-and-Execute、Reflection 架构的优劣

---

> **本章掌握后，你应该能**：用 LangChain 创建和运行 Agent，理解 Agent 的核心循环，知道不同 Agent 架构的适用场景，并能评估 Agent 的性能。
