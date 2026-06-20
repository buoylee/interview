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

> **⚠️ v1.x**：`create_react_agent` 已弃用，迁移到 `from langchain.agents import create_agent`（详见第 7 章 §2.1）。下方代码仍用旧 API 讲解多 Agent 编排逻辑。

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

### 2.3 为什么 Supervisor 用 `Command` 而不是条件边

注意上面 Supervisor 没有用 `add_conditional_edges`,而是直接 `return Command(...)`。这是 LangGraph 里**两种不同的路由机制**,差别在一道硬墙:

> **条件边的路由函数 `route(state) -> str` 只能「返回一个去向」,不能写 state。** 而 `Command` 由节点自己返回,能把「去哪」(`goto`)和「写什么」(`update`)在一次返回里一起给出。

Supervisor 恰好踩在 `Command` 的甜区——它一次 LLM 调用同时产出两条**耦合**的信息:

```python
class Decision(BaseModel):
    next: Literal["research", "writer", "FINISH"]  # 去哪        → goto
    instructions: str                               # 给下游的任务 → update
```

`next` 和 `instructions` 是同一次推理一起产出的,用 `Command` 就能原地交付,两者都留下:

```python
return Command(
    goto=decision.next,
    update={"messages": [HumanMessage(decision.instructions)]},  # 顺手写进 state
)
```

如果硬用条件边,你会被迫把一次逻辑拆成「节点 + 路由函数」两段,还要**额外开一个 state 字段当传话筒**(因为节点和路由函数之间只有 state 一根线):

```python
class TeamState(MessagesState):
    next: str          # 纯粹为了把决策从节点递给路由函数而存在

def supervisor(state):
    decision = supervisor_llm.invoke([...])
    return {"messages": [HumanMessage(decision.instructions)], "next": decision.next}

def route(state) -> str:            # 只能读 state、只能返回去向
    return END if state["next"] == "FINISH" else state["next"]

graph.add_conditional_edges("supervisor", route, ["research", "writer", END])
```

对比之下 `Command` 版省掉了 `next` 字段、省掉了 `route` 函数,**决策和写入 co-located 在一处**。

注意这份代码里两种机制各得其所:`agent → supervisor` 用的是**静态边**(`add_edge`),因为「干完回 supervisor」是无条件的,根本没有「条件」要判断;只有 `supervisor → 谁` 是动态的、还要带指令,才用 `Command`。

> **⚠️ 可视化提醒**:用 `Command` 后图里没有显式声明 supervisor 的出边,要把返回类型标成 `Command[Literal["research", "writer", "__end__"]]`,LangGraph 才能据此画图 / 静态校验它可能跳去哪。这是 `Command` 唯一比条件边「不直观」的地方——出边藏在代码里,得靠类型注解补回可视化信息。

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

### 3.3 handoff 传的是「控制权」,不是数据

很容易误以为 handoff 是把数据「传」给下一个 agent。其实多 Agent 系统有**两条互相独立的轴**:

| 轴 | 回答 | 谁负责 |
|---|---|---|
| **数据流(data)** | 「现在能看到什么信息」 | 共享 state(见第五节) |
| **控制流(control)** | 「接下来轮到谁干活」 | 边 / 路由 / **handoff** |

共享 state 让「轮到谁,谁就读得到全部数据」,但它**永远不决定「轮到谁」**。`handoff` 干的就是这件事——**把执行权(控制权)交给另一个 agent**。用 Java/Go 的直觉:共享 state 像所有线程都能看的堆内存;handoff 像「接力棒传给下一个 goroutine」——堆里有数据,不等于知道该谁跑。

上面 §3.2 的写法里,信息其实是靠**共享 message 历史**隐式传过去的:`support_node` 拿到的是同一个 `state["messages"]`,sales 说过的、用户说过的它全看得到;`transfer_to_support` 工具本身只返回一个字符串信号,**不携带任何业务数据,只表达「该转给谁」**。

把 handoff 抽掉,一个 Swarm 就瘫了——没有 supervisor、没有静态边,agent 之间没有任何切换方式,全卡在第一个 agent。所以它不是冗余,而是 Swarm **唯一**的状态转移机制。

### 3.4 用 `Command` 携带交接信息(现代写法)

§3.2 是「工具发信号 + 条件边执行路由」两段式。现代写法把它合并:**handoff 工具直接返回 `Command`**,自带 `goto` + 携带的 payload,就不再需要 `route_after_agent` 那条条件边了。

```python
from langgraph.types import Command
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langchain_core.messages import ToolMessage
from typing import Annotated

def create_handoff_tool(*, agent_name: str, description: str):
    name = f"transfer_to_{agent_name}"

    @tool(name, description=description)
    def handoff(
        task: str,                                        # ① LLM 填:精准的交接摘要
        state: Annotated[dict, InjectedState],            # ② 框架注入:当前完整 state
        tool_call_id: Annotated[str, InjectedToolCallId], # ③ 框架注入:本次工具调用 id
    ) -> Command:
        tool_msg = ToolMessage(content=f"转交给 {agent_name}",
                               name=name, tool_call_id=tool_call_id)
        return Command(
            goto=agent_name,
            graph=Command.PARENT,         # 跳到父图里的兄弟 agent(见 §5.3)
            update={"messages": [tool_msg], "task": task},
        )
    return handoff
```

三个底层要点:

1. **`task` 是 payload 入口**:它是工具参数,等于让移交方的 LLM 把「用户要退款、订单 123、已核实身份」总结成一句干净的上下文,而不是把整段对话甩过去。
2. **`InjectedState` / `InjectedToolCallId` 对 LLM 不可见**,是框架注入的——LLM 只看到 `task`;前者让你读当前 state 决定转发多少,后者用来回一条 `ToolMessage`(每个 tool_call 必须有对应响应,否则下次调模型 API 会报「tool_call 悬空」)。
3. **`graph=Command.PARENT`**:工具是在某个 agent 的子图内部执行的,要够到父图里的兄弟 agent 必须跳出当前图——这是条件边做不到的(条件边绑死在单图内)。

> 即便用 `Command` 携带了 `task`,在「全共享 messages」的 Swarm 里 payload 也主要是**给接班人的聚焦指令**,而非「让数据可达」(数据本就可达)。只有当你**故意隔离 state**(见 §5.5)时,payload 才回到「数据桥」的角色。

---

## 四、控制流:三种路由机制与选择

前面出现了三种「决定下一个谁干活」的方式:**条件边**、**Supervisor 的 `Command` 节点**、**Swarm 的 handoff 工具**。它们都在「控制流」这条轴上(数据流见第五节),区别在**谁来决策、决策能不能留痕**。

### 4.1 三种路由机制对照

| 能力 | 条件边 | Command 节点(Supervisor) | handoff 工具(Swarm) |
|---|---|---|---|
| 谁决定下一个 | 独立路由函数(代码) | 中心 supervisor 节点(LLM) | 当前正在干活的 agent(LLM) |
| 可不可以**顺便写 state** | ❌ 只能返回节点名 | ✅ goto + update | ✅ goto + update |
| 是不是**图节点**(可观测/中断/重试) | ❌ 是「转移」,不是节点 | ✅ | ✅ |
| 额外 LLM 调用 | 0(纯代码) | +1 / 每次路由 | 0(搭在 agent 本轮推理上) |
| 中心化 | 集中(一处逻辑) | 集中(单一协调者) | 去中心(各 agent 自治) |
| 跨子图 | 否 | 看实现 | 是(`Command.PARENT`) |
| 典型场景 | 校验过没过 / 重试 / 读 tool_call | 多专家流程、可重新分配 | 客服式动态转接 |

### 4.2 「条件边里塞 LLM 不也行吗?」

会。条件边的路由函数里完全可以 `llm.invoke()` 来决定去向。所以区别**不是**「能不能用 LLM」,而是一道结构性硬墙:

> **条件边只能返回一个去向,不能写 state,也不是一个图节点。**

后果是:你在条件边里调 LLM,它想了一大堆,**最后只有「去哪」这一个字活下来,其余全丢**。比如路由 LLM 决定「交给 writer,并让 writer 专注第 3 节」——`writer` 能返回,「专注第 3 节」却无处安放,蒸发了。要留住它,只能把这次 LLM 调用搬进一个 node,而「一个 node 决定去向 + 写 state」——**那就是 Command / Supervisor 模式本身**。

另外,**checkpoint / HITL 中断 / 重试策略都挂在 node 上**:路由跑在两个 super-step 之间的转移里,不是 super-step,所以**不被 checkpoint、不能中断等审批、不能单独重试**。想「做路由决策前停下来让人审批」或「路由调用失败自动重试」,就必须让它是 node。这也是官方建议「别在条件边里干重活」的原因。

而 handoff 比「edge 里塞 LLM」还更省:edge 里的 LLM 是一次**额外的、只看得到 state 的新调用**;handoff 的决策**搭在 agent 本来就要做的那一轮推理上**——它此刻已满载上下文,顺手挑个 `transfer_to_x` 工具,**0 次额外调用**,决策者还是最懂当前情况的那个 agent。

### 4.3 怎么选

```
路由决策能用代码从 state 直接算出来吗?
├─ 能(确定性)              → 条件边(最轻、免费、可单测)
└─ 不能,要 LLM 判断        → 还需要什么?
        ├─ 要顺便写 state / 要可中断·可重试 → Command 节点
        ├─ 有个"专职调度员"统筹           → Supervisor(= Command 节点)
        └─ 由"正在干活、已有上下文"的 agent 顺手决定 → handoff 工具(0 额外调用)
```

口诀:**能写成 `if`** → 条件边;**要个"项目经理"统筹** → Supervisor;**让"当事人"自己转交** → handoff。

> 注意「决策」和「执行路由」是两层:条件边既能自己做确定性决策、也能只当别人决策的执行器(§3.2 就是 handoff 工具出决策、条件边做执行);`Command` 则把两层并成一步。你真正在选的是**「决策由谁、怎么做」**,用边还是 Command 只是接线细节。

### 4.4 Supervisor vs Swarm 对比

| 维度 | Supervisor | Swarm |
|------|-----------|-------|
| **控制** | 中心控制, 可预测 | 去中心化, 更灵活 |
| **延迟** | 每步都经过 Supervisor (多一次 LLM 调用) | Agent 直接交接, 延迟更低 |
| **复杂度** | 简单, 容易理解 | 复杂, 需要每个 Agent 知道何时交接 |
| **适合** | 明确的流程 (研究→写作→审核) | 动态的交互 (客服系统) |
| **容错** | Supervisor 可以重试/重新分配 | 需要每个 Agent 自己处理错误 |

---

## 五、数据流:状态怎么存、怎么跨图(Agent 间通信)

### 5.1 共享黑板模型:channel 与 reducer

LangGraph 的 state **不是函数传参,而是一块「共享黑板」**:有若干**命名格子**(channel),节点不互相调用,而是「往某个格子写、从某个格子读」。这套你其实很熟——它就像 Redux store 按 key 取 slice、Spring 按 name 拿 bean、中间件链里传的 `Map<String,Object>`。

channel 名 = state schema 里的**字段名**;字段上的 `Annotated[类型, reducer]` 给它绑定**合并策略**:

```python
from langgraph.graph.message import add_messages

# 所有 Agent 共享同一个 State;每个字段 = 一个 channel
class TeamState(TypedDict):
    messages: Annotated[list, add_messages]  # channel "messages",reducer = 追加(按 id 去重)
    research_data: str      # channel "research_data",默认 = 覆盖(last-write-wins);research 写
    report_draft: str       # writer 写,reviewer 读
    review_notes: str       # reviewer 写
```

规则只有两条:**① 节点不直接改 state,只 `return` 一个「增量」dict;② 每个 channel 用它的 reducer 把「旧值」和「节点返回的新值」合并。** 所以 `return {"messages": [msg]}` 不是「把 messages 设成 [msg]」,而是「把 msg 交给 reducer 去 append」。想让 agent 传**结构化数据**而非塞进 messages,就像上面给 state 加 `research_data` / `report_draft` 这类专用 channel,数据就有明确落点,不用从一长串 message 里捞。

并行写同一个 channel(如 §六 Map-Reduce 的多个 worker 写 `results`)**必须配累加 reducer**——LangGraph 按 super-step(BSP)执行,同一步并行节点的返回先收集、step 结束统一交给 reducer 合并;没有 reducer 会互相覆盖/冲突。

> **为什么用「按名寻址的共享黑板」而不是显式传参**:节点彻底解耦——writer 不需要知道谁产出了 `research_data`、谁会读它的 `report_draft`,只认格子名。于是你重连图(加节点、改顺序、并行)时节点函数签名一行都不用动。代价是 channel 名是 stringly-typed,改名要改多处——缓解办法是把共享 channel 抽到一个 base schema 复用(见 §5.4)。

### 5.2 运行期 vs 持久化:state 真正「保存」在哪

上面的 channel 全活在**内存**里,一次 `invoke` 结束就没了。要让 state 跨多次调用活下来(多轮对话记忆、HITL 暂停恢复),compile 时挂 **checkpointer**,调用时给 `thread_id`:

```python
from langgraph.checkpoint.memory import MemorySaver

multi_agent = graph.compile(checkpointer=MemorySaver())
cfg = {"configurable": {"thread_id": "user-42"}}
multi_agent.invoke({"messages": [("human", "...")]}, cfg)  # 第二次同 thread_id 调用会自动续上
```

机制:**每个 super-step 跑完,checkpointer 把整份 state 快照写一次**,按 `(thread_id, checkpoint_id)` 存;下次同 `thread_id` 进来先加载最后一个快照再继续。后端可选:`MemorySaver`(内存,重启即丢)/ `SqliteSaver`(本地文件,`langgraph.checkpoint.sqlite`)/ `PostgresSaver`(生产、多实例共享)。多 Agent 的额外好处:checkpointer 也保存**子图的嵌套 state**,所以能在某个 agent 内部(如等审批)暂停、之后精确恢复。

> 跨**不同 thread**的长期记忆(如「记住这个用户偏好」)是另一个东西——`BaseStore`(KV、namespaced),和 checkpointer(单 thread 短期 state)是两条线,别混。

### 5.3 父图与子图:`return` 到底写哪张图的 state

当一个 agent 本身是子图(`create_react_agent` 编出来的就是),就有了「父图 state」和「子图 state」两层。一条铁律:

> **节点的 `return` 永远 append 到「定义这个节点的那张图」的 state,不可选。** 子图里的节点写子图,父图里的节点写父图;`return` 本身不能挑图。

那父子怎么通信?**靠同名 channel 在边界自动桥接**(当你 `add_node("sub", compiled_subgraph)` 直接挂子图时):

- **进入**:父 state 里和子图**同名**的 channel 喂进子图;父图独有的 channel 子图看不到。
- **退出**:子图最终 state 里和父图**同名**的 channel 自动并回父图(走父图 reducer);子图独有的私有、丢弃。

```python
class ParentState(TypedDict):
    messages: Annotated[list, add_messages]   # 与子图同名 → 互通
    parent_only: str                          # 子图碰不到

class SubState(TypedDict):
    messages: Annotated[list, add_messages]   # 与父图同名 → 互通
    sub_only: str                             # 私有,不上浮
```

所以**「数据上不上浮」= channel 命名:同名互通、异名隔离**。要在子图节点里**直接写父图**(而非子图自己),用 `Command(graph=Command.PARENT, update=...)`——这是唯一能让一次返回跨图、点名写父图的开关(§3.4 的 handoff 就靠它跨到兄弟 agent)。

> **一个真实坑**:退出时同名 `messages` 并回父图,子图返回的是「旧+新」整串。`add_messages` 按 message id 去重,不会翻倍;但若用裸 `operator.add`,旧消息会被**重复累加**。共享列表型 channel 一律用 `add_messages`。

### 5.4 别把三个「名」搞混

```python
graph.add_node("writer", writer_node)          # ← node 名
def writer_node(state):
    return {"messages": [AIMessage(content=..., name="writer")]}
    #        ↑ channel 名                        ↑ message 的 name
```

| 名 | 在哪定义 | 作用 |
|---|---|---|
| **channel 名** | state schema 的**字段名** | state 存储 + **父子图桥接靠它** |
| **node 名** | `add_node("writer", fn)` 的第一个参数 | 图拓扑标签,用于连边 / `goto` |
| **message 的 name** | `AIMessage(name="writer")` 的 name | 消息作者标签,纯元数据,**与 channel/state 无关** |

决定 append 落哪、父子通不通的,**只有 channel 名**。把共享 channel 抽进一个 base schema 复用,可避免「靠碰巧同名」的脆弱:

```python
class SharedChannels(TypedDict):
    messages: Annotated[list, add_messages]   # 只定义一次
class ParentState(SharedChannels): parent_only: str
class SubState(SharedChannels): sub_only: str
```

### 5.5 控制子 agent 状态「上浮」到外层的 4 个杠杆

子 agent 的消息**一定**会进它自己的 state(那是它推理的草稿本,拦不掉也不该拦);你能控制的只有**有多少冒泡到外层(父图)**。四个杠杆:

| 想要的效果 | 用哪个杠杆 |
|---|---|
| 只让最终结论上浮 | **A. wrapper `return`**:`return {"messages": [result["messages"][-1]]}` |
| 整段过程都上浮(调试) | A:回本轮新增的全部 `result["messages"][before:]` |
| 完全不进父 messages | A 写私有字段 / **B. channel 异名** / **C. 子图 `output` schema** |
| 直接挂子图、自动合并 | B:父子用**同名** channel |
| 不想自己写 wrapper | **D. 现成库 `output_mode`** |

杠杆 A 是「独立 State + 消息传递」的核心——子 agent 跑完,`result` 在你手里只是个普通 dict,你 `return` 什么父图才拿到什么:

```python
# 每个 Agent 有独立 State, 通过 wrapper 的 return 控制上浮
def research_node(state):
    result = research_agent.invoke({"messages": state["messages"]})
    research_output = result["messages"][-1].content
    # 只回最后一条结论 → 子 agent 内部一堆工具调用不会污染父 messages
    return {"messages": [AIMessage(
        content=f"[研究结果]\n{research_output}",
        name="researcher",
    )]}
```

杠杆 C 在定义层锁死出口:`StateGraph(InnerState, output=OutputState)`,只有 `OutputState` 里的 channel 会回父图。杠杆 D 是 `langgraph-supervisor` 把杠杆 A 封成的参数:

```python
from langgraph_supervisor import create_supervisor

app = create_supervisor(
    agents=[research_agent, writer_agent], model=llm,
    output_mode="last_message",   # 只把子 agent 最后一条结论进父 state(干净)
    # output_mode="full_history", # 子 agent 全部消息进父 state(调试友好但 context 膨胀)
)
```

> **要点**:「进不进本 state」不由你控(子 agent 推理必然全量写自己的 state);你控的只有「进不进外层 state」——靠 wrapper `return` / channel 异名 / `output` schema / 库的 `output_mode`。

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

> **Q: Supervisor 为什么直接 `return Command` 而不用条件边?**
>
> A: 因为它一次 LLM 调用同时产出「去哪」(`next`)和「给下游的指令」(`instructions`),而**条件边的路由函数只能返回去向、不能写 state**。用 `Command` 能把 `goto` + `update` 一次给齐;用条件边则要多开一个 state 字段当传话筒、再拆出一个路由函数。(详见 §2.3)

> **Q: 条件边里也能 `llm.invoke()` 决定路由,它和 Command 节点 / handoff 有何不同?**
>
> A: 区别不是「能不能用 LLM」,而是条件边有道硬墙——**只能返回一个去向、不能写 state、不是图节点**。所以 LLM 在条件边里的产出除了「去哪」全部丢失,且**不被 checkpoint、不能 HITL 中断、不能重试**。要保留决策产出或要可中断/可重试,就得让路由成为 node(即 Command/Supervisor);handoff 则更进一步,0 额外调用、决策者自带上下文。(详见 §4.2)

> **Q: handoff 到底在交接什么?数据已经共享了,它不多余吗?**
>
> A: 不多余——它交的是**控制权(下一个谁干活),不是数据**。共享 state 解决「数据谁都能看」,但永远不决定「轮到谁」。在全共享 messages 的 Swarm 里,数据靠共享历史隐式可达,handoff 的 payload 主要是给接班人的**聚焦指令**。(详见 §3.3)

> **Q: 父图和子图之间的状态靠什么传递?子 agent 的内部消息怎么不污染父 state?**
>
> A: 父子靠**同名 channel** 在子图进出边界自动桥接(同名互通、异名隔离);要在子图节点里直接写父图,用 `Command(graph=Command.PARENT, update=...)`。子 agent 内部消息必进它自己的 state,控制「上浮多少」有 4 个杠杆:wrapper 只 `return` 最后一条 / 子图 channel 异名 / 子图 `output` schema / `langgraph-supervisor` 的 `output_mode="last_message"`。(详见 §5.3、§5.5)

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
