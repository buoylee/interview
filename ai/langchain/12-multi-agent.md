# 第8章：多 Agent 系统 — 协作与编排

> 单个 Agent 有能力上限。多 Agent 系统让多个专家 Agent 协作，解决复杂任务。这是 2025-2026 年 AI 工程的核心方向。

---

## 一、为什么需要多 Agent

### 1.1 单 Agent 的问题

```
问题: "帮我研究一下竞品，写一份分析报告，并创建 PPT"

单 Agent:
  一个 Agent 要做研究 + 分析 + 写报告 + 做PPT
  → 上下文过长、任务混杂、质量下降

多 Agent:
  Research Agent → 收集竞品信息
  Analyst Agent  → 分析数据and发现
  Writer Agent   → 撰写报告
  Designer Agent → 制作 PPT
  Supervisor     → 协调和审核
  → 各司其职, 质量更高
```

### 1.2 多 Agent 的优势

| 维度 | 单 Agent | 多 Agent |
|------|----------|----------|
| **复杂度** | 一个巨大 prompt | 多个专注的小 prompt |
| **质量** | 任务多时下降 | 各自专注保持高质量 |
| **可维护性** | 难以调试 | 各 Agent 独立测试 |
| **并行性** | 串行 | 可并行 |
| **复用性** | 无 | Agent 可跨系统复用 |

---

## 二、Supervisor 模式

### 2.1 架构

```
                    ┌───────────┐
    用户输入 ──────→ │ Supervisor │ ──────→ 最终输出
                    └─────┬─────┘
                          │ 分配任务
              ┌───────────┼───────────┐
              ↓           ↓           ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Research  │ │ Writer   │ │ Review   │
        │  Agent   │ │  Agent   │ │  Agent   │
        └──────────┘ └──────────┘ └──────────┘
```

### 2.2 实现

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from typing import Literal

# 1. 创建专家 Agent
research_agent = create_react_agent(
    ChatOpenAI(model="gpt-4o"),
    tools=[web_search],
    prompt="你是一个研究专家，擅长信息收集和整理。"
)

writer_agent = create_react_agent(
    ChatOpenAI(model="gpt-4o"),
    tools=[],
    prompt="你是一个写作专家，擅长撰写结构清晰的报告。"
)

# 2. 定义 Supervisor
def supervisor(state: MessagesState) -> Command:
    """Supervisor 决定下一步该谁工作"""
    
    class Decision(BaseModel):
        next: Literal["research", "writer", "FINISH"]
        instructions: str
    
    supervisor_llm = ChatOpenAI(model="gpt-4o").with_structured_output(Decision)
    
    decision = supervisor_llm.invoke([
        SystemMessage(content="""你是一个团队协调者。
团队成员: research (研究), writer (写作)
根据当前进度决定下一步:
- 需要信息收集 → research
- 需要写报告 → writer  
- 任务完成 → FINISH"""),
        *state["messages"],
    ])
    
    if decision.next == "FINISH":
        return Command(goto=END)
    
    return Command(
        goto=decision.next,
        update={"messages": [HumanMessage(content=decision.instructions)]},
    )

# 3. 包装 Agent 为节点
def research_node(state: MessagesState):
    result = research_agent.invoke(state)
    return {"messages": [AIMessage(
        content=result["messages"][-1].content,
        name="research"  # 标记来源
    )]}

def writer_node(state: MessagesState):
    result = writer_agent.invoke(state)
    return {"messages": [AIMessage(
        content=result["messages"][-1].content,
        name="writer"
    )]}

# 4. 构建图
graph = StateGraph(MessagesState)
graph.add_node("supervisor", supervisor)
graph.add_node("research", research_node)
graph.add_node("writer", writer_node)

graph.add_edge(START, "supervisor")
graph.add_edge("research", "supervisor")  # 完成后回 supervisor
graph.add_edge("writer", "supervisor")

multi_agent = graph.compile()

# 5. 运行
result = multi_agent.invoke({
    "messages": [("human", "研究 LangChain 的市场定位并写一份分析报告")]
})
```

---

## 三、Swarm 模式 (Handoff)

### 3.1 架构

```
没有中心调度, Agent 之间直接交接:

用户 → Agent A ──handoff──→ Agent B ──handoff──→ Agent C → 最终回答
              (发现不是自己的领域)   (发现需要另一个专家)
```

### 3.2 实现

```python
from langgraph.prebuilt import create_react_agent

# 1. 定义 handoff 工具
def create_handoff_tool(target_agent: str, description: str):
    @tool(name=f"transfer_to_{target_agent}")
    def handoff() -> str:
        f"""将对话转交给 {target_agent}。{description}"""
        return f"转交给 {target_agent}"
    return handoff

# 2. 各 Agent 有 handoff 工具
sales_agent = create_react_agent(
    llm,
    tools=[
        product_search,
        create_handoff_tool("support", "当用户有技术问题时"),
        create_handoff_tool("billing", "当用户有账单问题时"),
    ],
    prompt="你是销售顾问，帮助用户选择产品。"
)

support_agent = create_react_agent(
    llm,
    tools=[
        troubleshoot,
        create_handoff_tool("sales", "当用户想购买产品时"),
        create_handoff_tool("billing", "当用户有账单问题时"),
    ],
    prompt="你是技术支持专家。"
)

billing_agent = create_react_agent(
    llm,
    tools=[
        check_billing,
        create_handoff_tool("sales", "当用户想购买产品时"),
        create_handoff_tool("support", "当用户有技术问题时"),
    ],
    prompt="你是账单专员。"
)

# 3. 构建图
def route_after_agent(state, agent_name):
    last_msg = state["messages"][-1]
    for tc in (last_msg.tool_calls or []):
        if tc["name"].startswith("transfer_to_"):
            return tc["name"].replace("transfer_to_", "")
    return END

graph = StateGraph(MessagesState)
graph.add_node("sales", sales_node)
graph.add_node("support", support_node)
graph.add_node("billing", billing_node)

graph.add_edge(START, "sales")  # 默认从销售开始
# 每个 Agent 完成后检查是否需要 handoff
graph.add_conditional_edges("sales", 
    lambda s: route_after_agent(s, "sales"),
    ["support", "billing", END])
graph.add_conditional_edges("support",
    lambda s: route_after_agent(s, "support"),
    ["sales", "billing", END])
graph.add_conditional_edges("billing",
    lambda s: route_after_agent(s, "billing"),
    ["sales", "support", END])
```

---

## 四、Supervisor vs Swarm 对比

| 维度 | Supervisor | Swarm |
|------|-----------|-------|
| **控制** | 中心控制, 可预测 | 去中心化, 更灵活 |
| **延迟** | 每步都经过 Supervisor (多一次 LLM 调用) | Agent 直接交接, 延迟更低 |
| **复杂度** | 简单, 容易理解 | 复杂, 需要每个 Agent 知道何时交接 |
| **适合** | 明确的流程 (研究→写作→审核) | 动态的交互 (客服系统) |
| **容错** | Supervisor 可以重试/重新分配 | 需要每个 Agent 自己处理错误 |

---

## 五、Agent 间通信

### 5.1 共享 State

```python
# 所有 Agent 共享同一个 State
class TeamState(TypedDict):
    messages: Annotated[list, add_messages]
    research_data: str      # research agent 写入
    report_draft: str       # writer agent 写入
    review_notes: str       # reviewer agent 写入
```

### 5.2 独立 State + 消息传递

```python
# 每个 Agent 有独立 State, 通过消息传递数据
def research_node(state):
    # 用自己的独立 agent
    result = research_agent.invoke({"messages": state["messages"]})
    research_output = result["messages"][-1].content
    
    # 通过消息传递给下一个 Agent
    return {"messages": [AIMessage(
        content=f"[研究结果]\n{research_output}",
        name="researcher"
    )]}
```

---

## 六、Map-Reduce 模式

```python
from langgraph.types import Send

class ResearchState(TypedDict):
    topics: list[str]
    results: Annotated[list[str], add]  # 用 add reducer 收集结果

def fan_out(state: ResearchState):
    """将多个主题并行分发给 worker"""
    return [Send("worker", {"topic": t}) for t in state["topics"]]

def worker(state):
    """每个 worker 处理一个主题"""
    result = llm.invoke(f"研究: {state['topic']}")
    return {"results": [result.content]}

def summarize(state: ResearchState):
    """汇总所有 worker 的结果"""
    combined = "\n\n".join(state["results"])
    summary = llm.invoke(f"汇总以下研究结果:\n{combined}")
    return {"messages": [AIMessage(content=summary.content)]}

graph = StateGraph(ResearchState)
graph.add_node("worker", worker)
graph.add_node("summarize", summarize)
graph.add_conditional_edges(START, fan_out)
graph.add_edge("worker", "summarize")
graph.add_edge("summarize", END)
```

---

## 七、面试高频问题

> **Q: 多 Agent 系统的最大挑战是什么？**
>
> A: (1) **协调开销** — 每次 Agent 通信都需要 LLM 调用，延迟和成本线性增长；(2) **状态一致性** — 多个 Agent 共享/传递状态时容易信息丢失或冲突；(3) **错误传播** — 一个 Agent 的错误输出会影响下游所有 Agent；(4) **调试困难** — 多 Agent 的 Trace 链路复杂。解决方案：用 LangSmith 追踪全链路、每个 Agent 独立评估、设置合理的超时和重试。

> **Q: 什么时候应该用多 Agent，什么时候单 Agent 就够了？**
>
> A: **单 Agent 够用**：任务单一 (搜索+回答)、工具少 (<5个)、不需要深度推理。**需要多 Agent**：(1) 任务涉及多个专业领域 (研究+写作+审核)；(2) 需要并行处理 (同时研究多个主题)；(3) 需要 Agent 间的审查和反馈循环；(4) 单 Agent 的 prompt 太长导致质量下降。**经验法则**: 先用单 Agent，效果不好再拆分为多 Agent。

---

## 八、练习任务

### 基础练习
- [ ] 实现一个 Supervisor + 2 个子 Agent 的系统
- [ ] 观察多 Agent 系统的完整 Trace

### 进阶练习
- [ ] 实现 Swarm 模式的客服系统 (销售→技术→账单)
- [ ] 用 Map-Reduce 并行研究 3 个主题并汇总
- [ ] 给多 Agent 系统添加 Human-in-the-loop 审批步骤

### 面试模拟
- [ ] 比较 Supervisor 和 Swarm 模式
- [ ] 设计一个多 Agent 系统解决特定业务问题
- [ ] 说明多 Agent 系统的调试和评估方法

---

> **本章掌握后，你应该能**：构建多 Agent 协作系统，选择合适的协作模式，处理 Agent 间通信，并在生产环境中部署和监控。

---

## 学习路线完成总结

```
✅ 第1章: LangChain 基础 (Models, Prompts, Parsers)
✅ 第2章: LCEL 深入 (管道组合)
✅ 第3章: Tool Calling & Agent (工具+循环)
✅ 第4章: RAG with LangChain (检索增强)
✅ 第5章: LangGraph 核心 (State, Node, Edge)
✅ 第6章: LangGraph 进阶 (HITL, Streaming, 架构模式)
✅ 第7章: 生产化 (可观测性, 部署, 安全)
✅ 第8章: 多 Agent 系统 (Supervisor, Swarm, Map-Reduce)
```

> **恭喜！完成所有章节后，你将具备大厂 AI 工程师所需的 LangChain + LangGraph 全栈能力。**
