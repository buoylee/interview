# 第6章：LangGraph 进阶 — 复杂 Agent 模式

> 掌握了 LangGraph 基础后，本章深入 Human-in-the-loop、Streaming、SubGraph 等生产级特性。

---

## 一、Human-in-the-Loop — 人工介入

### 1.1 为什么需要

Agent 执行敏感操作（发邮件、删数据、转账）前，需要人工确认。

### 1.2 interrupt() — 暂停等待审批

```python
from langgraph.types import interrupt, Command
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.checkpoint.memory import MemorySaver

def human_approval(state: MessagesState):
    """在执行敏感操作前，暂停等待人工审批"""
    last_msg = state["messages"][-1]
    
    # 暂停执行，把信息传给人类审查
    approval = interrupt({
        "question": "是否批准以下操作？",
        "action": last_msg.content,
    })
    
    if approval == "approve":
        return {"messages": [AIMessage(content="操作已执行")]}
    else:
        return {"messages": [AIMessage(content="操作已取消")]}

# 构建图
graph = StateGraph(MessagesState)
graph.add_node("agent", agent_node)
graph.add_node("approval", human_approval)
graph.add_node("execute", execute_node)

graph.add_edge(START, "agent")
graph.add_conditional_edges("agent", route, ["approval", END])
graph.add_edge("approval", "execute")
graph.add_edge("execute", END)

agent = graph.compile(checkpointer=MemorySaver())
```

### 1.3 恢复执行

```python
config = {"configurable": {"thread_id": "session_1"}}

# 第一次调用 — 触发 interrupt
result = agent.invoke(
    {"messages": [("human", "删除用户的所有数据")]},
    config=config,
)
# 到达 interrupt 时暂停

# 检查暂停信息
state = agent.get_state(config)
print(state.next)  # ["approval"]  ← 等待在 approval 节点

# 人工批准后恢复
result = agent.invoke(
    Command(resume="approve"),  # 传入审批结果
    config=config,
)
```

### 1.4 面试要点

> **Q: interrupt() 和 Checkpointing 有什么关系？**
>
> A: interrupt() **依赖** Checkpointing。当调用 interrupt() 时，LangGraph 将当前 State 保存到 Checkpointer，然后停止执行。恢复时，从 Checkpointer 恢复 State，继续执行。**没有 Checkpointer 就不能用 interrupt()**。

---

## 二、Streaming — 高级流式

### 2.1 三种流式模式

```python
# 模式1: values — 每个节点完成后，返回完整 state
for event in agent.stream(input, stream_mode="values"):
    last_msg = event["messages"][-1]
    print(f"[{last_msg.type}] {last_msg.content}")

# 模式2: updates — 只返回每个节点的增量
for event in agent.stream(input, stream_mode="updates"):
    for node_name, update in event.items():
        print(f"节点 {node_name} 更新: {update}")

# 模式3: messages — 逐 token 返回 (最适合 UI)
for msg, metadata in agent.stream(input, stream_mode="messages"):
    if msg.content:
        print(msg.content, end="", flush=True)
```

### 2.2 astream_events — 异步事件流

```python
async for event in agent.astream_events(input, version="v2"):
    kind = event["event"]
    
    if kind == "on_chat_model_stream":
        # LLM 逐 token 输出
        token = event["data"]["chunk"].content
        print(token, end="", flush=True)
    
    elif kind == "on_tool_start":
        # 工具开始执行
        print(f"\n🔧 调用工具: {event['name']}")
    
    elif kind == "on_tool_end":
        # 工具执行完成
        print(f"✅ 工具结果: {event['data']['output']}")
```

### 2.3 传到前端 (FastAPI + SSE)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/chat")
async def chat(request: ChatRequest):
    async def stream():
        async for msg, meta in agent.astream(
            {"messages": [("human", request.message)]},
            stream_mode="messages",
        ):
            if msg.content:
                yield f"data: {msg.content}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(stream(), media_type="text/event-stream")
```

---

## 三、SubGraph — 子图

### 3.1 为什么用子图

```
复杂系统拆分:
  主图: 路由 → 子图A (研究) → 子图B (写作) → 审核

好处:
- 模块化: 每个子图独立开发、测试
- 复用: 多个主图可以复用同一个子图
- 状态隔离: 子图有自己的 State
```

### 3.2 定义子图

```python
# 子图: 研究模块
class ResearchState(TypedDict):
    topic: str
    findings: list[str]

def search_step(state: ResearchState):
    results = web_search(state["topic"])
    return {"findings": [results]}

def analyze_step(state: ResearchState):
    analysis = llm.invoke(f"分析: {state['findings']}")
    return {"findings": state["findings"] + [analysis.content]}

research_graph = StateGraph(ResearchState)
research_graph.add_node("search", search_step)
research_graph.add_node("analyze", analyze_step)
research_graph.add_edge(START, "search")
research_graph.add_edge("search", "analyze")
research_graph.add_edge("analyze", END)

research_subgraph = research_graph.compile()
```

### 3.3 在主图中使用子图

```python
class MainState(TypedDict):
    messages: Annotated[list, add_messages]
    research_results: str

def call_research(state: MainState):
    topic = state["messages"][-1].content
    result = research_subgraph.invoke({"topic": topic})
    return {"research_results": "\n".join(result["findings"])}

main_graph = StateGraph(MainState)
main_graph.add_node("research", call_research)
main_graph.add_node("respond", respond_node)
main_graph.add_edge(START, "research")
main_graph.add_edge("research", "respond")
main_graph.add_edge("respond", END)
```

---

## 四、Agent 架构模式实现

### 4.1 ReAct (已在上一章实现)

### 4.2 Router — 意图路由

```python
from pydantic import BaseModel, Field
from typing import Literal

class RouteDecision(BaseModel):
    route: Literal["technical", "billing", "general"] = Field(
        description="用户问题类别"
    )

def classify(state: MessagesState):
    """用 LLM 分类用户意图"""
    classifier = llm.with_structured_output(RouteDecision)
    decision = classifier.invoke(state["messages"])
    return {"route": decision.route}

def route_to_expert(state):
    return state["route"]

graph = StateGraph(MessagesState)
graph.add_node("classify", classify)
graph.add_node("technical", tech_expert)
graph.add_node("billing", billing_expert)
graph.add_node("general", general_expert)

graph.add_edge(START, "classify")
graph.add_conditional_edges("classify", route_to_expert, 
    ["technical", "billing", "general"])
graph.add_edge("technical", END)
graph.add_edge("billing", END)
graph.add_edge("general", END)
```

### 4.3 Reflection — 自我反思

```python
def generate(state):
    """初始生成"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

def reflect(state):
    """自我反思"""
    reflection_prompt = f"""审查以下回答，指出问题并改进：
    {state["messages"][-1].content}"""
    reflection = llm.invoke(reflection_prompt)
    return {"messages": [HumanMessage(content=reflection.content)]}

def should_continue(state):
    """是否需要继续反思（最多 3 轮）"""
    if len(state["messages"]) > 6:  # 3轮 × 2条消息
        return END
    return "reflect"

graph = StateGraph(MessagesState)
graph.add_node("generate", generate)
graph.add_node("reflect", reflect)
graph.add_edge(START, "generate")
graph.add_conditional_edges("generate", should_continue, ["reflect", END])
graph.add_edge("reflect", "generate")
```

### 4.4 Plan-and-Execute

```python
class PlanState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: list[str]
    current_step: int
    results: list[str]

def planner(state: PlanState):
    plan = llm.with_structured_output(PlanSchema).invoke(
        "为以下任务制定执行计划: " + state["messages"][-1].content
    )
    return {"plan": plan.steps, "current_step": 0}

def executor(state: PlanState):
    step = state["plan"][state["current_step"]]
    result = agent_executor.invoke(step)
    return {
        "results": state["results"] + [result],
        "current_step": state["current_step"] + 1,
    }

def is_done(state: PlanState):
    if state["current_step"] >= len(state["plan"]):
        return "summarize"
    return "executor"
```

---

## 五、动态 Node 数量

```python
# 使用 Send 实现动态并行节点
from langgraph.types import Send

def route_to_workers(state):
    """根据任务数量动态创建并行节点"""
    return [
        Send("worker", {"task": task})
        for task in state["tasks"]
    ]

graph.add_conditional_edges("planner", route_to_workers)
```

---

## 六、错误处理与重试

```python
def robust_tool_node(state: MessagesState):
    """带错误处理的工具节点"""
    results = []
    for tc in state["messages"][-1].tool_calls:
        try:
            result = tool_map[tc["name"]].invoke(tc["args"])
            results.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        except Exception as e:
            results.append(ToolMessage(
                content=f"工具执行失败: {str(e)}，请尝试其他方法",
                tool_call_id=tc["id"],
            ))
    return {"messages": results}
```

---

## 七、练习任务

### 基础练习
- [ ] 实现一个带 interrupt() 的 Human-in-the-loop Agent
- [ ] 用 stream_mode="messages" 实现逐 token 流式输出

### 进阶练习
- [ ] 实现 Router 模式 (分类 → 路由到不同处理器)
- [ ] 实现 Reflection 模式 (生成 → 反思 → 改进)
- [ ] 创建一个子图并在主图中调用

### 面试模拟
- [ ] 比较 ReAct、Router、Reflection、Plan-and-Execute 四种模式
- [ ] 解释 interrupt() 的工作原理及其与 Checkpointing 的关系
- [ ] 描述如何将 LangGraph Agent 的流式输出传到前端

---

> **本章掌握后，你应该能**：实现各种复杂 Agent 模式，使用 Human-in-the-loop，处理流式输出，构建模块化子图。
