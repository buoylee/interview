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
> A: interrupt() **依赖** Checkpointing 才能完成「暂停 → 恢复」闭环。调用 interrupt() 时，LangGraph 将当前 State 保存到 Checkpointer 并停止；恢复时从 Checkpointer 取回 State，用 `Command(resume=...)` 继续执行。
>
> **精确地说**（实测 langgraph 1.x）：没有 Checkpointer，interrupt() **仍会暂停**（节点后续代码不执行、结果带 `__interrupt__`），但你**无法** `Command(resume=...)` 恢复、也**无法** `get_state()` 查看——HITL 闭环走不通。所以生产环境里 interrupt 必须配 Checkpointer。

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

> 概念、家族对比、「Plan-and-Execute 到底有没有 replan」三层坑，见 [07 章 §5.3 / §5.7](07-agents.md)。本节只补一件事：在 LangGraph 里 **planner / executor / 条件边到底怎么连成一个循环**。

**思路(一句话)**：planner 一次性列出完整步骤清单 → executor 用代码从清单里取**一步**、交给一个 ReAct 子 agent 跑 → 条件边检查「清单跑完没」→ 没跑完就**回到 executor** 跑下一步，跑完就去 summarize 收尾。

和 4.3 Reflection 一样是个循环，区别在于：这里的循环由**代码里的 `current_step` 计数器**驱动(执行顺序在 planner 那一步就定死了)，而不是每步让 LLM 重新决定。

#### Step 1：Schema、State 和节点函数

```python
from typing import Literal
from pydantic import BaseModel, Field

class PlanSchema(BaseModel):                      # ← planner 的结构化输出
    steps: list[str] = Field(description="完成任务的有序步骤清单")

class PlanState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: list[str]            # planner 写入的步骤清单
    current_step: int          # 代码用它当游标，逐步推进
    results: list[str]         # 每步的执行结果

def planner(state: PlanState):
    """① 一次性把任务拆成有序步骤清单"""
    plan = llm.with_structured_output(PlanSchema).invoke(
        "为以下任务制定执行计划: " + state["messages"][-1].content
    )
    return {"plan": plan.steps, "current_step": 0, "results": []}

def executor(state: PlanState):
    """② 取出第 current_step 步，交给 ReAct 子 agent 执行，游标 +1"""
    step = state["plan"][state["current_step"]]
    result = agent_executor.invoke({"messages": [("human", step)]})
    return {
        "results": state["results"] + [result["messages"][-1].content],
        "current_step": state["current_step"] + 1,
    }

def summarize(state: PlanState):
    """④ 所有步骤跑完，汇总结果给用户"""
    summary = llm.invoke("根据以下执行结果回答用户:\n" + "\n".join(state["results"]))
    return {"messages": [summary]}

def is_done(state: PlanState) -> Literal["executor", "summarize"]:
    """③ 条件路由：清单跑完没？跑完去 summarize，没跑完回 executor"""
    if state["current_step"] >= len(state["plan"]):
        return "summarize"
    return "executor"
```

先交代三个之前凭空出现的依赖：
- **`PlanSchema`** —— planner 的结构化输出 schema(上面已补)。`with_structured_output` 强制 LLM 返回 `{steps: [...]}`，这样 `plan.steps` 才是干净的 `list[str]`。
- **`agent_executor`** —— 上一章的 ReAct 子 agent(`create_react_agent(llm, tools)`)。executor 节点把**单个步骤**当成一句话喂给它，它自己带工具把这一步跑完。**Plan-and-Execute = 外层代码循环 + 内层 ReAct 干活**，这层嵌套是关键。
- **`summarize`** —— 收尾节点(上面已补)。原代码里 `is_done` 返回了 `"summarize"` 却没有这个节点，图会编译失败。

#### Step 2：把节点串成图(你问的「如何串起来」)

```python
graph = StateGraph(PlanState)
graph.add_node("planner", planner)
graph.add_node("executor", executor)
graph.add_node("summarize", summarize)

graph.add_edge(START, "planner")                 # 入口 → 规划
graph.add_edge("planner", "executor")            # 规划完 → 执行第一步
graph.add_conditional_edges(                      # ← 循环的关键：executor 之后岔路
    "executor", is_done, ["executor", "summarize"]
)
graph.add_edge("summarize", END)                 # 收尾 → 结束

app = graph.compile()
```

关键就是那条 **`add_conditional_edges("executor", is_done, ...)`**：每次 executor 跑完一步，都由 `is_done` 决定是**回到自己**(跑下一步)还是**去 summarize**(收尾)。这条「指回自己」的条件边，就是循环的本体。

```
START → planner → executor ──is_done──▶ summarize → END
                     ▲          │
                     └──────────┘
                  还有步骤没跑完，回到 executor
```

#### 进阶：从「盲跑」升级成真正的 Plan-and-Execute

> ⚠️ 上面这版是**盲跑**：planner 一锤定音，执行过程中不回头改计划。按 [07 章 §5.3](07-agents.md) 的说法，**作为 agent 架构，Plan-and-Execute 的灵魂正是 replan loop —— 没有 replan，它跟 ReAct 比没优势**。

升级方法：把 `is_done` 这个纯计数判断，换成一个 **replan 节点** —— 每跑完一步，让 LLM 看着结果重写**剩余**计划(可能加步骤、删步骤，或判定任务已完成)：

```python
class Response(BaseModel):                         # replan 的两种结果之一：已完成
    answer: str
class Act(BaseModel):
    action: Response | PlanSchema                  # 要么收尾，要么给新计划

def replan(state: PlanState):
    out = llm.with_structured_output(Act).invoke(
        f"原计划:{state['plan']}\n已完成:{state['results']}\n"
        "若任务已完成给出最终答案，否则给出更新后的剩余步骤。"
    )
    if isinstance(out.action, Response):
        return {"messages": [AIMessage(out.action.answer)]}   # 完成
    return {"plan": out.action.steps, "current_step": 0}      # 改写剩余计划

# 接线改两行：executor 之后不再直接判 is_done，而是先经过 replan
graph.add_edge("executor", "replan")
graph.add_conditional_edges(
    "replan",
    lambda s: END if s["messages"][-1].type == "ai" else "executor",
    ["executor", END],
)
```

对比记忆：**盲跑版** = `executor →(计数判断)→ executor / summarize`；**replan 版** = `executor → replan →(LLM 判断)→ executor / END`。差别就在那个 replan 节点是不是真让 LLM 回头改计划。07 章有完整参考实现和 ReWOO / 产品版 plan 的对照。

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
