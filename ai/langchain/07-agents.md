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

> **⚠️ 版本说明（v1.x）**：`from langgraph.prebuilt import create_react_agent` 仍可用但**已弃用**（`LangGraphDeprecatedSinceV10`）。官方现在推荐 `from langchain.agents import create_agent`——签名有变：`prompt=` → `system_prompt=`，内部 LLM 节点名从 `agent` 改为 `model`。本章为对照旧代码仍用 `create_react_agent` 讲解，迁移时换成 `create_agent` 即可。

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

### 3.4 记忆机制演进史(高频面试题）

> 面试官常问：「LangChain 的记忆机制是怎么演进的？为什么要改？」考的不是 API 名字，而是你**懂不懂这次重新设计的动机**。

**先记住一句话**：新版**不是**旧版套一层壳，而是**推倒重做**。LangGraph 的 Checkpointer 跟旧版 `BaseMemory` 没有继承关系、机制完全不同——旧版只存「消息」，新版存的是**整个 graph State 的快照**。但背后「把对话状态存下来、下次再注入回去」的核心思想一脉相承。

> 类比 Java：`java.util.Date` / `Calendar` → `java.time`(JSR-310）。后者是另起炉灶的重新设计，不是前者的子类；但你仍该知道 `Calendar` 存在——老项目到处是它，面试官也爱问「为什么要有 java.time」。

#### 三代演进

| | Gen1 旧 Memory | Gen2 过渡桥 | Gen3 现在(本章讲的） |
|---|---|---|---|
| 代表 API | `ConversationBufferMemory` `ConversationChain` | `RunnableWithMessageHistory` + `ChatMessageHistory` | LangGraph **Checkpointer** + **Store** |
| 绑定对象 | 死绑 `Chain` | 绑任意 LCEL Runnable | 绑 graph State |
| 存什么 | 只存 messages | 只存 messages | 整个 State 快照 |
| 会话 key | `memory_key`(隐式） | `session_id` | `thread_id`(短期）/ namespace(长期） |
| 当前状态 | **已 deprecated** | 还能用、但官方推 Gen3 | 官方主推 |

**为什么要改(这是得分点）**：旧版 Memory 有四个痛点——
1. **死绑 Chain**，组合性差，没法塞进 LCEL 管道；
2. **多用户并发**时 per-session 记忆难管理；
3. 状态是**隐式 in-place 修改**，难 debug / 难观测；
4. **只能存消息**，存不了复杂工作流的中间状态。

LangGraph 用「**显式 State + Reducer + 持久化(Checkpointer）**」一次性解决了这四点。

#### 旧版「档位」→ 新版「原语」

理解这点最关键：旧版给你几个**固定档位的自动挡**(预制 Memory class）；新版给你**离合+油门(原语）**，让你自己组合任意策略。所以新版是旧版的**超集**——旧版会的它全做得到，还更灵活。

| 旧版固定 class | 新版怎么做(本章已涉及） |
|---|---|
| `ConversationBufferWindowMemory(k=N)` | 在 node 里 `trim_messages` / 切片 |
| `ConversationSummaryMemory` | 一个摘要 node，把旧消息压成 SystemMessage |
| `ConversationTokenBufferMemory` | token 预算检查(见 §3.3、第11章) |
| `VectorStoreRetrieverMemory` | RAG 检索 node + Store |

> **Q: 还有必要学旧版 Memory 吗？**
>
> A: **学「故事」，不学「API」**。
> (1) ❌ 不要背 class 名 / 参数，更不要用它写新代码——已 deprecated，写了反而扣分；
> (2) ✅ 要能讲清楚「旧版长怎样 → 4 个痛点 → 为什么换成 LangGraph → 旧策略如何映射成新原语」；
> (3) ✅ `RunnableWithMessageHistory` 知道它是**过渡桥**就好(老 Chain 迁到 LCEL 时的记忆方案），不用深学。

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

**三者的「颗粒度」不一样**(最容易混的点):

| mode | 多久来一个 event | 给你什么 | event 形状 | 用途 |
|---|---|---|---|---|
| `values` | 每个**节点**完成 | 当前**完整 state**(全量快照,列表越来越长) | dict → `event["messages"]` | 调试看全貌 / 拿最终结果 |
| `updates` | 每个**节点**完成 | 这一步的**增量**,按节点名 key | dict → `event.items()` → `(节点名, {"messages":[...]})` | 看「哪个节点改了啥」 |
| `messages` | LLM 每个 **token** | 一个 **token 片段** + 元数据 | **tuple** → `(msg_chunk, metadata)` | 前端打字机 |

- **颗粒度主线**:`values` / `updates` 单位是**「节点」**(图跑完一步给一个 event);`messages` 单位是**「token」**(LLM 每吐一段就给一个 event)。前两者要等整个节点(整次 LLM 调用)跑完才给,看不到「逐字蹦」;只有 `messages` 能做打字机。
- **`values` 是 `updates` 的累加和**:`values[N].messages == values[N-1].messages + updates[N] 的增量`。想看全貌用 `values`,想看 diff(省带宽、知道谁改的)用 `updates`。
- 注意 `messages` 返回的是 **tuple** `(msg, metadata)`,前两种是 dict —— 形状不同,循环写法别套错。

> **Q:`stream_mode="messages"` 的「逐 token」,是 LLM 接口实际返回的颗粒,还是 LangChain 硬拆的?**
>
> A:**是上游接口实际返回的颗粒,LangChain 只透传,不重切也不重并。**
> 如果 OpenAI 流式接口把 `"北京今天"` 当**一个 chunk** 发来,你就拿到**一个** `AIMessageChunk(content="北京今天")`,LangChain 不会硬拆成 `"北京"`/`"今天"`。整条管线是 1:1:
>
> ```
> 模型内部 BPE token(字节级,不可见)
>    │  ← 提供方把若干 token 攒成一个「合法 UTF-8 文本」的 delta,自己决定攒多少
>    ▼
> OpenAI SSE: delta.content = "北京"      ← chunk 边界由「提供方」定,不是 LangChain
>    │  ← LangChain 一对一包一层(ChatModel._stream),不重切不重并
>    ▼
> AIMessageChunk(content="北京")
>    │  ← LangGraph messages 模式原样转发
>    ▼
> 你 for 循环里的 msg
> ```
>
> 所以「逐 token」是**教学简化**,准确说是**「逐 API 流式 chunk」**,那个 chunk 通常 ≈ 1 token 但不保证:
> - 提供方可能一个 delta 给 1 个 token,也可能给几个(它自己攒);
> - 第一个 chunk 常只有 role、`content` 为空(所以代码里 `if msg.content` 过滤);
> - 中文一个汉字在 BPE 里可能是 1~3 个字节级 token,提供方会**攒到完整汉字再发**,你不会收到半个汉字的乱码;
> - 反例:若某模型集成是「假流式」(底层一次性返回再整块 yield),你只会收到一个大 chunk —— 再次说明颗粒度完全由**上游**决定,LangChain 只是搬运工。

---

## 五、Agent 架构模式

> 前面用 ReAct 讲了基础盘。但 Agent 的实现模式是一整个家族,面试常被追问「ReAct 之外还有哪些、为什么会演化出它们」。本节按**家族**梳理 —— 记家族比记名字重要,面试官真正想听的是「为什么会演化出这个模式、它解决了前一个的什么痛点」。

### 5.1 四大家族全景

```
家族1：推理-行动 (Reasoning-Acting)   ← 单 agent 基础盘
  ├─ ReAct              想一步→做一步→看结果→再想（边走边看）
  ├─ Function Calling   现代原生：模型直接吐 tool_calls（§2 的 create_react_agent 底层就是它）
  └─ Self-Ask           把大问题拆成"追问子问题"再逐个查

家族2：先规划后执行 (Plan-then-Execute)  ← 解决 ReAct"走一步算一步、易迷路"
  ├─ Plan-and-Execute   先列完整计划 → 逐步执行 → 重规划
  ├─ ReWOO              规划时一次写好所有步骤(占位符)，执行不调 LLM，最后统一收尾（省 token）
  └─ LLMCompiler        把计划编译成 DAG，能并行的工具并行调（省延迟）

家族3：反思-自我改进 (Reflect / Refine)  ← 解决"第一次答得不够好"
  ├─ Reflection / Self-Refine   生成→自我批评→改写
  ├─ Reflexion                  反思 + 把教训写进记忆，下次别再犯
  └─ LATS                       树搜索(MCTS) + 反思，探索多条路径选最优

家族4：多 Agent (Multi-Agent)           ← 单 agent 工具太多/职责太杂时拆分
  ├─ Supervisor   一个主管 agent 派活给多个专家 agent
  ├─ Hierarchical 主管下面还有子主管，层级树
  └─ Swarm / Network  agent 之间平等"交接(handoff)"，去中心化
```

**三条演化主线(帮你串起来记)**：

1. **ReAct → Function Calling**：不是替代,而是**实现方式升级**。早期 ReAct 靠 LLM 输出 `Thought/Action/Observation` 文本再正则解析,脆弱;现在模型原生支持 tool calling,§2 的 `create_react_agent` 底层走的就是 function calling,逻辑结构仍是 ReAct 循环。
2. **ReAct → Plan-and-Execute → ReWOO / LLMCompiler**：一条「**减少 LLM 调用 / 提速**」的优化线。
3. **Reflection → Reflexion → LATS**：一条「**用更多算力换更高质量**」的线,越往后越贵,生产很少全套上。

> **一句话总结(面试版)**：主流生产环境 90% 还是 **ReAct(function-calling 实现)** + 必要时拆成**多 Agent(supervisor)**;Plan-and-Execute / ReWOO 适合步骤明确的长任务,Reflection 系列适合对质量极敏感、能容忍延迟的场景。

### 5.2 家族1：推理-行动

**ReAct(默认)**
```
Think → Act → Observe → Think → ... → Answer
```
- **优势**: 简单、通用、内置支持、能根据中间结果灵活调整
- **劣势**: 可能陷入无限循环、每步都要 LLM 推理、历史越滚越长(token 膨胀)、长任务易迷路

**Function Calling Agent**：ReAct 的现代实现。早期靠解析文本里的 action 不稳定;现在模型**原生**输出结构化 `tool_calls`,稳得多。你用的 `create_react_agent` 就是这一类。

**Self-Ask**：把一个复杂问题拆成一串"追问子问题",逐个查再合并。适合多跳问答。

### 5.3 家族2：先规划后执行

**Plan-and-Execute** —— 解决 ReAct「走一步算一步、长任务跑偏」：
```
用户输入 → Planner(列出完整计划) → 逐步执行 → Re-plan(改剩余计划) → ... → 收尾
```
跟 ReAct 比,两个关键差别:(1) **有显式的待办清单**(写出来、能审查);(2) **有 Re-plan 环节**(执行完一步回头改计划,不是盲跑)。
- **优势**: 复杂任务拆解更好、计划可审查、减少"决策"类 LLM 调用
- **劣势**: 计划可能一开始就错、增加延迟

> ⚠️ **Plan-and-Execute 到底有没有 re-plan？** —— 这是面试坑。「Plan-and-Execute」这个名字压了**三层不同的东西**,re-plan 有无正好不同:
>
> | 你指的是哪个 | 有没有 re-plan | 说明 |
> |---|---|---|
> | **Plan-and-Solve(那篇 prompting 论文)** | ❌ 没有 | 纯提示词技巧,一个 prompt 走完,名字来源 |
> | **Plan-and-Execute(agent 架构,即本节)** | ✅ **有** | BabyAGI / LangChain 参考实现,**有显式 replan 节点** |
> | **ReWOO** | ❌ **没有(设计如此)** | 计划一锤定音,这是它的卖点也是软肋 |
>
> 记忆:**作为 agent 架构的 Plan-and-Execute,灵魂就是那个 replan loop** —— 没有 replan 就退化成盲跑,跟 ReAct 比没优势。「计划一锤定音、不能改」那是 ReWOO 的性质,别安到 Plan-and-Execute 头上。

**ReWOO**(Reasoning WithOut Observation)—— 解决 ReAct 的 token 爆炸:规划时一次写好所有步骤(用 `#E1`、`#E2` 占位符代替还不知道的结果)→ Worker 执行工具时**完全不调 LLM**,纯代入 → Solver 一次性收尾。
- **优势**: 全程约 2 次 LLM 调用,观测结果不塞回推理循环,token 省一个量级
- **劣势**: 计划一锤定音,**不能根据中间结果调整**,易脆

**LLMCompiler** —— 解决串行太慢:把计划编译成 **DAG**,无依赖的工具**并行**调。

### 5.4 家族3：反思-自我改进

**Reflection / Self-Refine**:
```
用户输入 → 初始生成 → 自我审查 → 改进 → 再审查 → ... → 输出
```
- **优势**: 输出质量高　**劣势**: 延迟高(多次 LLM 调用)

**Reflexion**：Reflection 反思完就忘;Reflexion 把**反思结论写进记忆**,跨轮复用,下次别再犯同样的错。

**LATS**(Language Agent Tree Search)：树搜索(MCTS)+ 反思,探索多条路径选最优。最贵,调用次数指数级,知道存在 + 适用场景即可。

### 5.5 家族4：多 Agent

单 agent 工具一多就容易选错;把它拆成多个专精 agent:
- **Supervisor**:一个主管 agent 路由派活给多个专家 agent(最常用)
- **Hierarchical**:主管下面还有子主管,层级树
- **Swarm / Network**:agent 之间平等"交接(handoff)",去中心化

### 5.6 三者跑一趟：ReAct vs Plan-Execute vs ReWOO 的 token 账

拿同一任务:**「2023 票房最高的电影,它导演的家乡人口是多少?」**(需 4 次查询)

```
ReAct —— 走一步看一步，没有计划：
  LLM调用1: 想"先查2023票房冠军" → search → "芭比"
  LLM调用2: 【prompt塞进上面全部】想"查芭比导演" → search → "Greta Gerwig"
  LLM调用3: 【prompt又塞进全部】想"查她家乡" → search → "萨克拉门托"
  LLM调用4: 【prompt再塞进全部】想"查人口" → search → "52万"
  LLM调用5: 【prompt含全部历史】→ 最终答案
  → 5 次调用，每次 prompt 比上次大（token 爆炸源头）

Plan-and-Execute —— 先规划，再逐步执行 + 重规划：
  LLM调用1 (Planner): [1.查冠军 2.查导演 3.查家乡 4.查人口]
  执行步骤1 → "芭比"
  LLM调用 (Re-plan): 看结果，更新剩余计划   ← 关键：有重规划
  执行步骤2 → ... 逐步 + 必要时重规划

ReWOO —— 一次规划好(占位符)，执行不调 LLM：
  LLM调用1 (Planner): #E1=search[2023冠军]; #E2=search[#E1导演]; #E3=search[#E2家乡]; #E4=search[#E3人口]
  Worker: 真跑 #E1~#E4，纯代入，不调 LLM
  LLM调用2 (Solver): 拿全部证据 → 最终答案
  → 全程仅 2 次 LLM 调用
```

| | 有显式计划? | 观测结果怎么处理 | LLM 调用次数 | 能否中途调整 |
|---|---|---|---|---|
| **ReAct** | ❌ 脑内隐式 | 每步塞回不断增长的 prompt(**token 爆炸源头**) | 多(每步 1 次) | 能(每步都重想) |
| **Plan-and-Execute** | ✅ 显式清单 | 重规划时塞回 | 中(规划+重规划+执行) | 能(重规划) |
| **ReWOO** | ✅ 显式 + 占位符 | **不塞回**,Worker 直接代入 | 少(≈2 次) | ❌ 不能(计划一锤定音) |

### 5.7 学术 plan vs 产品 plan 模式：实现方案差异

> 高频困惑:Claude Code / Cursor / Manus 里都有「plan / todos」,这跟学术 Plan-and-Execute 是一回事吗?**不是。**

一句话定调:**学术版 = 一张「多节点状态图」(planner / execute / replan 是三个独立节点 + 条件边);产品版 = 「一个 ReAct loop + 通用原语」,plan 根本不是一个节点。**

**学术 Plan-and-Execute(LangGraph 参考实现)**：plan 是 State 里的结构化 `list[str]`,由**代码**迭代驱动,replan 是**独立节点**:
```python
class PlanExecute(TypedDict):
    plan: list[str]                       # ← 结构化步骤列表
    past_steps: Annotated[list, operator.add]
    response: str

planner   = prompt | llm.with_structured_output(Plan)   # Plan(steps: list[str])
replanner = prompt | llm.with_structured_output(Act)    # Act(action: Union[Response, Plan])
executor  = create_react_agent(llm, tools)              # 子 agent 跑单步

def exec_step(s):
    task = s["plan"][0]                   # ← 代码从列表取步骤驱动
    return {"past_steps": [(task, executor.invoke({"messages": [("user", task)]}))]}

def replan_step(s):                       # ← 专用 replan 节点
    out = replanner.invoke(s)
    return ({"response": out.action.response} if isinstance(out.action, Response)
            else {"plan": out.action.steps})

g.add_edge("planner", "executor"); g.add_edge("executor", "replan")
g.add_conditional_edges("replan", lambda s: END if s.get("response") else "executor", ["executor", END])
```

**产品口味A —— Claude Code 式(审批 gate)**：没有 planner/replan 节点,就是普通 ReAct,只加两个原语:① plan 阶段**限制工具集**(只读)② 用 **interrupt 卡人类审批**:
```python
def agent_node(s):
    tools = READONLY_TOOLS if s["mode"] == "plan" else ALL_TOOLS   # ① 工具门禁
    return {"messages": [llm.bind_tools(tools).invoke(s["messages"])]}

def gate(s):
    if called_exit_plan_mode(s):
        ok = interrupt({"plan": extract_plan(s)})                  # ② 人类 gate
        return {"mode": "execute"} if ok else {"mode": "plan"}
# plan 是一条自然语言 message + 一个 interrupt，不是 list[str]，没有代码迭代它
```

**产品口味B —— Manus 式(todo.md 便利贴)**：还是一个 ReAct loop,plan 是工作区一个**文件**,用通用 file 工具 + prompt 纪律维护:
```python
SYSTEM = "开工先写 todo.md 列步骤；每完成一步就重写 todo.md 勾掉它、按需加新步骤。"
agent = create_react_agent(llm, tools=[read_file, write_file, run, ...])
# 没有 plan 专用节点：读/写 todo.md 走通用 file 工具。
# "反复重写 todo.md" 的副作用 = 把目标重新顶进最近上下文 → 防漂移。
```

| 实现维度 | 学术 Plan-and-Execute | 产品口味A(Claude Code) | 产品口味B(Manus) |
|---|---|---|---|
| **整体结构** | 多节点状态图 | 一个 ReAct loop | 一个 ReAct loop |
| **plan 是独立节点吗** | ✅ planner 节点 | ❌ 一条 message + 一个工具 | ❌ 一次 write_file |
| **plan 数据形态** | State 里 `list[str]` | 自然语言文本 | 工作区 `todo.md` 文件 |
| **谁驱动执行** | **代码**:`plan[0]` 迭代 | **LLM**:plan 只是 context | **LLM**:plan 只是 context |
| **replan 怎么实现** | 专用节点 + `structured_output(Union)` | 无;靠 **human interrupt** | LLM 用 **write_file** 改文件 |
| **关键原语** | structured output、条件边、嵌套子 agent | **工具门禁 + interrupt** | **file 工具 + prompt 纪律** |

### 5.8 Claude Code 的两个 plan：Plan Mode vs TodoWrite

> 你天天看到 Claude Code / Codex 里的 todos,会以为「这就是 plan」。对,但要分清 —— **Claude Code 里有两个 plan 性质的东西**:

| 你看到的 | 是什么 | 对应 §5.7 | 何时出现 |
|---|---|---|---|
| **Plan Mode**(Shift+Tab 进入,列计划**等你批准**) | 审批 gate | 口味A | 动手**前**,给你看 |
| **执行时那串 ☐/☑ todos**(`TodoWrite`) | 自管理便利贴 | 口味B(=Manus todo.md) | 动手**中**,给自己追踪 |
| (学术 Plan-and-Execute) | 代码驱动的图架构 | —— | 产品没用 |

所以「todos = plan」对,只是它是**口味B**:Claude Code 用 `TodoWrite` 工具、Manus 用 `todo.md` 文件、Codex 用 `update_plan` 工具 —— 同一套路:一份自己读、自己改、防长任务跑偏的清单。两者还会接力:Plan Mode 批准的计划,落地常被转成 todos 执行。

**为什么 todos 还是 ≠ 学术 Plan-and-Execute(实现层)**:
```
学术 P&E：   代码  for step in plan: execute(step); replan()       ← plan 驱动代码
Claude Code：LLM 在 ReAct loop 里自己 TodoWrite / 自己读回 / 自己决定 ← plan 只是它的便利贴
```
核心:Claude Code 的 todos 是「挂在 ReAct loop 上、由 LLM 自管理的清单」,**没有任何代码 `for todo in todos: run(todo)` 在驱动它**;replan 就是 LLM 再调一次 `TodoWrite`,不是代码迭代 plan 列表 + 专用 replanner 节点。

### 5.9 面试必知

> **Q: ReAct Agent 在实际项目中有什么缺陷？如何解决？**
>
> A: 主要缺陷：(1) **无限循环** — LLM 反复调同一个工具。解决：设 `max_iterations` 限制最大步数；(2) **工具选择错误** — LLM 选错工具或传错参数。解决：优化工具描述、用 few-shot 示例、限制可用工具集；(3) **上下文膨胀** — 多步执行积累大量消息。解决：中间结果压缩、只保留关键信息；(4) **不可预测性** — 同一输入可能走不同路径。解决：temperature=0 + 更具体的 system prompt + 评估测试集。

> **Q: 现在产品里的「plan 模式 / todos」是学术 Plan-and-Execute 吗？**
>
> A: 不是。学术 Plan-and-Execute 是**以 plan 为核心驱动、全自动**的多节点图架构(planner/execute/replan + 代码迭代 plan 列表);产品的 plan 模式是**在 ReAct 引擎上外挂一层 plan**,plan 是给人审查(Claude Code 的 Plan Mode)或防长任务漂移(Manus todo.md / Claude Code 的 TodoWrite)的护栏,由 **LLM 而非代码**驱动。纯 Plan-and-Execute / ReWOO 多是学术/框架教程概念,生产很少纯用。

> **Q: 比较 ReAct、Plan-and-Execute、ReWOO 的优劣？**
>
> A: ReAct 灵活但贵(走一步问一次,历史越滚越大);Plan-Execute 加「计划骨架 + 重规划」,长任务不易跑偏;ReWOO 为省 token/提速,牺牲「中途调整」灵活性,适合步骤能一次想清的任务。ReWOO 的并行思想后来被现代 LLM 的 **parallel tool calling** 继承。

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

核心诉求:**工具执行前暂停 → 人类审批 → 再继续**。要能"停下来还恢复得了",图的状态就必须存得下来 —— 所以 `checkpointer` 是前置条件,真正的开关是 `interrupt_before`。

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    llm, tools,
    checkpointer=MemorySaver(),   # ① 持久化状态,断点才能恢复
    interrupt_before=["tools"],   # ② 在 tools 节点执行前暂停
)

config = {"configurable": {"thread_id": "1"}}   # 同一 thread 才能续上

# 跑到工具调用前停住,不会真的执行工具
agent.invoke({"messages": [("human", "删除 /tmp 下所有文件")]}, config)

# 此时可以查看 agent 打算调用哪个工具、参数是什么
state = agent.get_state(config)
print(state.next)                                # ('tools',) —— 卡在工具前
print(state.values["messages"][-1].tool_calls)  # 待审批的工具调用

# 人工确认后,传 None = 从断点继续(也可先改状态再继续)
agent.invoke(None, config)
```

> `interrupt_before=["tools"]` 是**静态断点**(每次到 tools 都停)。若想由 Agent **自己决定**哪一步要找人(只在危险操作时 gate),用动态的 `interrupt()` 函数 —— 见本章 §6 产品口味对比里的 `ok = interrupt({"plan": ...})`,LangGraph 章节细讲。

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

## 九、框架选型与生态位:LangChain / LangGraph / provider Agents SDK(高频面试题)

> 面试常问「为什么大家不爱用 LangChain?」「有了 OpenAI/Anthropic 的 Agents SDK,LangGraph 还有位置吗?」—— 考的不是立场,是你**分不分得清这几层、知不知道各自的生态位**。

### 9.1 先分清:被骂的「老 LangChain」≠ 你这章学的「LangGraph」

LangChain 是口碑两极的**两层**东西,别混为一谈:

| | 挨骂的(老) | 你这章学的(新) |
|---|---|---|
| 代表 | `LLMChain` / `AgentExecutor` / `ConversationBufferMemory` | **LangGraph** 原语 + LCEL |
| 风格 | 黑箱魔法,一行搞定一切 | 显式 graph、自己连节点、`MessagesState` |
| 现状 | 已 deprecated / 劝退 | 业界主推 |

整章其实是 LangGraph 视角(`create_react_agent` 来自 `langgraph.prebuilt`)。**你觉得 API「好」,正是因为这章教的是被筛剩下的现代好部分,挨骂的那套你压根没碰。**

> 关键:想表达「中立编排层」时,嘴上要说 **LangGraph**,不是 LangChain —— 说混了面试官会觉得你没分清。

### 9.2 老 LangChain 为什么挨骂

| 罪状 | 说明 |
|---|---|
| **藏住了 prompt** | LLM 应用里 **prompt 就是源代码**,它却把 prompt 拼装/解析包进抽象,debug 要扒五层 ≈ ORM 把你最该看的**生成 SQL** 糊上(Hibernate 挨骂的翻版) |
| **负价值抽象** | 很多组件就是对一次 API 调用包一层,文档还比底层 SDK 烂;一旦不合用,拆它比自己写还费劲 |
| **API 动荡** | monolith → core/community/partner → LCEL → LangGraph,deprecation 满天飞(**本章 §2.1 那条弃用警告就是活证据**) |
| **依赖膨胀** | 一个 loader 背一棵传递依赖树 |
| **模型进化抽走了它的理由** | 它 2022 年补的洞(output parser、ReAct 文本解析)→ 模型把 **tool calling / structured output** 做成原生后,胶水一夜变多余 |

### 9.3 看懂生态位:SDK 管「一次调用」,编排管「调用周围那一圈」

这不是「SDK vs 框架」,是**上下两层、共存**(LangGraph 底层照样调 SDK):

```
   ┌─ 循环/分支/重试、状态持久化、HITL、
   │  多 agent、断点恢复、跨步 streaming/trace      ← 编排层
   │        [ 中间才是那一次 SDK call ]            ← 调用层
   └────────────────────────────────────────────
```

- **调用层**:裸 provider SDK(tool calling / structured output / streaming),负责正中间那一格。
- **编排层**:外面那一圈,三选一 —— 自己 `while` 循环 / **LangGraph** / **provider Agents SDK**。
- 简单 agent(一个 LLM + 几个工具 + 循环):Anthropic 自己《Building Effective Agents》都说**别急着上框架,while 循环够了**。

### 9.4 真正的擂台:provider Agents SDK vs LangGraph

现在是**框架打框架**(都做编排),比的是 **绑定 / 抽象高度 / durability / 生态**:

| 维度 | provider Agents SDK | LangGraph |
|---|---|---|
| 模型绑定 | 绑自家(OpenAI / Anthropic) | **厂商中立**,可多模型混用 / 按成本路由 |
| 抽象 | **钦定一种 agent 形态**,合则极省、不合则搏斗 | 低层图原语,**任意控制流**自己搭 |
| 新能力 | 模型新特性**当天支持** | 要等它包一层 |
| durable execution | 较轻 | **强**(checkpointer 断点恢复 / HITL 等几天) |
| RAG 生态 | 自带有限 | **广**(retriever/vectorstore + LangSmith 中立 trace) |

> **Java 桥**:provider Agents SDK vs LangGraph ≈ **AWS Step Functions vs Temporal** —— 前者跟自家平台深咬合但被锁定,后者跑哪都行、谁都不绑。企业最怕 vendor lock-in,这条常一票定生死。

⚠️ 一个易混点:**Claude Agent SDK** 偏「Claude Code 那种**自主用工具 / 操作电脑**」的 autonomous 形态;真正跟 LangGraph 抢「**显式编排 workflow 图**」这块的是 **OpenAI Agents SDK**。

### 9.5 决策矩阵

| 你的情况 | 选 |
|---|---|
| 单厂商 all-in + 流程合钦定形态 | **provider Agents SDK**(更瘦更快) |
| 要 coding / autonomous「会自己干活」的 agent | **Claude Agent SDK** |
| **多模型 / 怕 lock-in**,或自定义控制流、深 durability、RAG 生态 | **LangGraph** |
| 老 Chain / AgentExecutor | 都别碰 |

### 9.6 面试答法

> **Q: 为什么大家不爱用 LangChain?**
>
> A: 挨骂的是**老高层抽象**(Chain/AgentExecutor/魔法 Memory):把 prompt 和 API 调用藏太深、debug 难、API 动荡,且随着模型原生支持 tool calling / structured output 而失去价值。社区因此转向**更底层显式的 LangGraph + 直接贴 SDK**。我的取舍:编排用 LangGraph、调用尽量贴 SDK、原型期借它的集成,但避开重抽象链。

> **Q: 有了 provider Agents SDK,LangGraph 还有位置吗?**
>
> A: 有,但比一年前**窄、也更硬**。provider SDK 正从「通用 agent 循环」这端往上吃;LangGraph 退守到 **厂商中立 + durable execution + 任意控制流图 + RAG 生态** 这块更难替代的地。注意两点:① 想要「中立」≠ **非 LangGraph 不可**,薄 wrapper(litellm)/ 自己循环也能中立,LangGraph 是「**中立 + 复杂编排都要**」时的优选;② LangGraph 的优势不止中立,单厂商下 durable / 自定义图 / RAG 生态照样是选它的理由。

**一句话记忆**:**provider SDK = 厂商钦定形态;LangGraph = 中立 + durable + 任意图 —— 中立是它最硬的牌,但不是唯一的牌。**

---

## 十、练习任务

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
- [ ] 讲清「老 LangChain 为什么挨骂」+「有了 provider Agents SDK,LangGraph 还有位置吗」

---

> **本章掌握后，你应该能**：用 LangChain 创建和运行 Agent，理解 Agent 的核心循环，知道不同 Agent 架构的适用场景，能评估 Agent 的性能，并能在 LangGraph / provider Agents SDK 之间做选型并说清理由。
