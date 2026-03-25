# LangChain & LangGraph 完全学习路线

> 目标：从零到完全掌握 LangChain + LangGraph，能独立构建生产级 AI Agent 应用。

---

## 总览：LangChain 生态全景

```
┌─────────────────────────────────────────────────────────────────┐
│                      LangChain 生态系统                          │
│                                                                 │
│  langchain-core        核心抽象 (LCEL、Messages、Runnables)       │
│  langchain             高层框架 (Chains、Agents、预构建模板)        │
│  langchain-community   第三方集成 (向量数据库、检索器、工具)          │
│  langgraph             底层编排引擎 (状态图、持久化、流式)            │
│  langsmith             可观测性平台 (追踪、评估、调试)               │
│                                                                 │
│  关系: LangChain Agent 底层用 LangGraph 实现                      │
│        LangGraph 可独立使用，也可搭配 LangChain 组件               │
└─────────────────────────────────────────────────────────────────┘
```

### LangChain vs LangGraph

| 维度 | LangChain | LangGraph |
|------|-----------|-----------|
| **定位** | 高层应用框架 | 底层编排引擎 |
| **类比** | Django (全家桶) | Flask (灵活组装) |
| **核心能力** | Models、Prompts、Tools、Retrievers、LCEL 管道 | State、Nodes、Edges、条件分支、循环 |
| **适合场景** | 快速原型、简单链式调用、80% 常见场景 | 复杂工作流、多 Agent、Human-in-the-loop |
| **学习顺序** | ✅ 先学 | ⏩ 后学 |

---

## 学习路线总图

```
第1章: LangChain 基础          ← 所有人必学 (3-5天)
  ↓
第2章: LCEL 深入               ← 核心范式 (2-3天)
  ↓
第3章: Tool Calling & Agent    ← 重点章节 (3-5天)
  ↓
第4章: RAG with LangChain      ← 结合已有知识 (2-3天)
  ↓
第5章: LangGraph 基础          ← 进入编排层 (3-5天)
  ↓
第6章: LangGraph 进阶          ← 复杂 Agent (5-7天)
  ↓
第7章: 生产化                  ← 部署上线 (3-5天)
  ↓
第8章: 多 Agent 系统           ← 高级话题 (5-7天)

总时长: 约 4-6 周 (每天 2-3 小时)
```

---

## 第1章: LangChain 基础 (3-5天)

> 目标：理解核心组件，能用 LangChain 调 LLM、管理 Prompt、解析输出。

### 1.1 环境搭建

```bash
pip install langchain langchain-openai langchain-community
# 如果用 Anthropic
pip install langchain-anthropic
```

### 1.2 Chat Models — 统一的 LLM 接口

**学什么**：
- `ChatOpenAI`, `ChatAnthropic`, 本地模型调用
- `.invoke()`, `.stream()`, `.batch()` 三种调用方式
- Message 类型：`SystemMessage`, `HumanMessage`, `AIMessage`
- 与 Token 计费相关的 `max_tokens`, `temperature` 等参数

**练习**：
- [ ] 用 ChatOpenAI 发一条消息并获取回复
- [ ] 用 `.stream()` 实现流式输出
- [ ] 切换不同模型 (GPT-4o → Claude → 本地 Ollama)

### 1.3 Prompt Templates — Prompt 工程

**学什么**：
- `ChatPromptTemplate` — 结构化 Prompt 模板
- `MessagesPlaceholder` — 动态插入消息历史
- `FewShotChatMessagePromptTemplate` — Few-shot 学习模板

**练习**：
- [ ] 创建一个带 system message 和 user input 的模板
- [ ] 创建带 few-shot 示例的 Prompt
- [ ] 用 `MessagesPlaceholder` 实现带历史的对话

### 1.4 Output Parsers — 结构化输出

**学什么**：
- `StrOutputParser` — 纯文本输出
- `JsonOutputParser` — JSON 输出
- `PydanticOutputParser` — Pydantic 模型输出
- `with_structured_output()` — 推荐方式，基于 Function Calling

**练习**：
- [ ] 让 LLM 输出符合 Pydantic 模型的结构化数据
- [ ] 用 `with_structured_output()` 提取实体信息

### 1.5 关键概念

| 概念 | 说明 |
|------|------|
| **Runnable** | 所有组件的基础接口，支持 `.invoke()`, `.stream()`, `.batch()` |
| **RunnableConfig** | 运行时配置 (callbacks、metadata、tags) |
| **Message** | LLM 对话的基本单元 (System/Human/AI/Tool) |

---

## 第2章: LCEL 深入 (2-3天)

> 目标：掌握 LangChain Expression Language，能用管道符组合任意组件。

### 2.1 LCEL 基础 — 管道符 `|`

**学什么**：
- `|` 管道符原理：前一个 Runnable 的输出 = 下一个的输入
- `RunnablePassthrough` — 透传输入
- `RunnableParallel` — 并行执行多个分支
- `RunnableLambda` — 包装普通函数为 Runnable

```python
# 经典 LCEL 链
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

### 2.2 进阶组合

**学什么**：
- `RunnableBranch` — 条件分支
- `.assign()` — 给 state 增加字段
- `.with_config()` — 运行时注入配置
- `.with_retry()` — 自动重试
- `.with_fallbacks()` — 降级策略

**练习**：
- [ ] 构建一个 "输入 → Prompt → LLM → 解析" 的完整 LCEL 链
- [ ] 用 RunnableParallel 并行执行两个 LLM 调用并合并结果
- [ ] 用 RunnableBranch 实现条件路由 (不同问题走不同链)
- [ ] 给链加上 retry 和 fallback

### 2.3 LCEL vs LangGraph 的关系

```
LCEL:      A → B → C        线性管道，适合简单流水线
LangGraph: 图 (有循环、分支)   适合需要决策+循环的场景

LCEL 是 LangChain 的 "管道胶水"
LangGraph 是 "工作流引擎"
二者互补，不是替代
```

---

## 第3章: Tool Calling & Agent (3-5天)

> 目标：让 LLM 能调用外部工具，理解 Agent 的本质。

### 3.1 Tool — 让 LLM 使用工具

**学什么**：
- `@tool` 装饰器 — 最简单的工具定义方式
- `BaseTool` 类 — 更灵活的工具定义
- `StructuredTool.from_function()` — 从函数创建
- Tool 的 `name`, `description`, `args_schema` 如何影响 LLM 选择
- `.bind_tools()` — 把工具绑定到 LLM

```python
from langchain_core.tools import tool

@tool
def search_weather(city: str) -> str:
    """查询指定城市的天气"""
    return f"{city}: 晴天, 25°C"

# 绑定工具到 LLM
llm_with_tools = llm.bind_tools([search_weather])
```

**练习**：
- [ ] 用 `@tool` 创建一个搜索工具和一个计算工具
- [ ] 观察 LLM 何时选择调用工具、何时直接回答

### 3.2 Agent 的本质 — ReAct 循环

```
用户输入 → LLM 思考 → 需要工具吗？
                        ├── 是 → 调用工具 → 拿到结果 → 再次思考 (循环)
                        └── 否 → 直接输出最终回答
```

**学什么**：
- `create_react_agent()` — LangChain 预置的 ReAct Agent
- Agent 的停止条件
- 如何传入 `system_message` 定制 Agent 行为
- Message History 管理

**练习**：
- [ ] 用 `create_react_agent()` 创建一个能搜索+计算的 Agent
- [ ] 观察 Agent 的中间步骤 (intermediate_steps)
- [ ] 给 Agent 添加对话历史

### 3.3 内置工具集成

**学什么**：
- Wikipedia、Tavily Search、Python REPL、DuckDuckGo 等
- 如何包装任意 API 为 LangChain Tool
- Toolkit 概念 (一组相关工具的集合)

---

## 第4章: RAG with LangChain (2-3天)

> 目标：用 LangChain 组件实现 RAG，衔接你已掌握的 RAG 知识。

### 4.1 文档加载与处理

**学什么**：
- `DocumentLoader` 系列 (PDF、Web、Markdown 等)
- `TextSplitter` 系列 (递归字符、语义分块)
- `Document` 对象 (page_content + metadata)

### 4.2 向量存储与检索

**学什么**：
- `VectorStore` 接口 (Chroma、FAISS、Qdrant)
- `Retriever` 接口 及 `.as_retriever()`
- 混合检索 `EnsembleRetriever`
- `MultiQueryRetriever` — LLM 改写查询
- `ContextualCompressionRetriever` — 上下文压缩

### 4.3 完整 RAG Chain

```python
# 用 LCEL 组合 RAG
rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

**练习**：
- [ ] 用 LangChain 实现你在 01-rag-learning-path 中学到的 Level 1 RAG
- [ ] 加入 MultiQueryRetriever 优化检索
- [ ] 加入 Reranker
- [ ] 对比效果

---

## 第5章: LangGraph 基础 (3-5天)

> 目标：掌握图状态机的核心概念，能构建简单的 Agent 图。

### 5.1 核心三要素

| 概念 | 说明 | 类比 |
|------|------|------|
| **State** | 贯穿整个工作流的共享数据 | 全局变量 |
| **Node** | 处理逻辑的函数 | 流程图中的矩形框 |
| **Edge** | 决定下一步走哪 | 流程图中的箭头 |

```python
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    messages: list
    next_step: str

graph = StateGraph(State)
graph.add_node("think", think_fn)      # 节点
graph.add_node("act", act_fn)
graph.add_edge(START, "think")          # 固定边
graph.add_conditional_edges(            # 条件边
    "think", decide, ["act", END]
)
graph.add_edge("act", "think")          # 循环!
agent = graph.compile()
```

### 5.2 MessagesState — 消息状态

**学什么**：
- `MessagesState` — 内置的消息管理状态
- `add_messages` — 消息累加器 (Reducer)
- 自定义 State 与 Reducer

### 5.3 Graph API vs Functional API

```
Graph API:      声明式，定义 Node + Edge     ← 可视化友好，推荐入门
Functional API: @entrypoint + @task          ← 代码更自然，适合简单场景
```

**练习**：
- [ ] 用 Graph API 构建一个简单的 ReAct Agent
- [ ] 用 Functional API 实现同样的 Agent
- [ ] 用 `graph.get_graph().draw_mermaid_png()` 可视化你的图

### 5.4 Checkpointing — 状态持久化

**学什么**：
- `MemorySaver` — 内存中的 checkpoint (开发用)
- `SqliteSaver`, `PostgresSaver` — 持久化 checkpoint
- Thread 概念 — 每个对话一个持久化线程
- 时间旅行 — 回溯到任意历史状态

---

## 第6章: LangGraph 进阶 (5-7天)

> 目标：掌握复杂 Agent 模式，能构建生产级工作流。

### 6.1 Human-in-the-Loop (人工介入)

**学什么**：
- `interrupt()` — 在关键节点暂停，等待人工审批
- `Command(resume=...)` — 人工审批后恢复执行
- 应用场景：敏感操作确认、Agent 输出审核

**练习**：
- [ ] 构建一个在执行敏感工具前暂停等待确认的 Agent

### 6.2 Streaming — 流式输出

**学什么**：
- `.stream()` — 流式获取节点更新
- `.astream_events()` — 异步事件流 (token 级)
- 流式传输到前端的最佳实践

### 6.3 子图 (SubGraph)

**学什么**：
- 将复杂图拆分为多个子图
- 子图间的状态传递
- 子图复用

### 6.4 常用 Agent 架构模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **ReAct** | 思考→行动→观察 循环 | 通用 Agent |
| **Plan-and-Execute** | 先制定计划，再逐步执行 | 复杂多步任务 |
| **Reflection** | Agent 自我反思改进输出 | 代码生成、写作 |
| **Router** | LLM 决定走哪个分支 | 请求分发、意图识别 |

**练习**：
- [ ] 实现 ReAct Agent (用 LangGraph 全手搓)
- [ ] 实现一个 Router 工作流
- [ ] 实现 Plan-and-Execute Agent

---

## 第7章: 生产化 (3-5天)

> 目标：将 Agent 部署到生产环境。

### 7.1 LangSmith — 可观测性

**学什么**：
- Trace 追踪 — 看到每一步的输入输出
- 评估 (Evaluation) — 批量测试 Agent 质量
- 在线监控 — 延迟、成本、错误率

### 7.2 LangGraph Platform — 部署

**学什么**：
- LangGraph Server — 将 Agent 部署为 API
- LangGraph Studio — 可视化调试工具
- Docker 部署方案

### 7.3 错误处理与韧性

**学什么**：
- 重试策略 (Retry)
- 降级策略 (Fallback)
- Token 限制管理
- 超时处理

**练习**：
- [ ] 用 LangSmith 追踪一个完整的 Agent 运行
- [ ] 给 Agent 加上完善的错误处理
- [ ] 用 LangGraph Server 部署一个 Agent API

---

## 第8章: 多 Agent 系统 (5-7天)

> 目标：掌握多个 Agent 协作的模式，能构建复杂的 AI 系统。

### 8.1 Supervisor 模式

```
                   ┌─────────┐
            ┌───── │Supervisor│ ─────┐
            ↓      └─────────┘      ↓
      ┌──────────┐           ┌──────────┐
      │ Research  │           │  Writer  │
      │  Agent   │           │  Agent   │
      └──────────┘           └──────────┘
```

- 一个主 Agent (Supervisor) 分配任务给多个子 Agent
- Supervisor 决定下一步该谁工作

### 8.2 Swarm 模式

- Agent 之间直接交接控制权 (Handoff)
- 无中心调度，更灵活
- `create_handoff_tool()` 实现 Agent 切换

### 8.3 Multi-Agent 通信

**学什么**：
- Agent 间的消息传递
- 共享 State vs 独立 State
- Agent 的 Tool 互调

**练习**：
- [ ] 构建 Supervisor + 2个子 Agent 的多 Agent 系统
- [ ] 实现一个 Research Agent + Writing Agent 的协作写作系统
- [ ] 用 Swarm 模式实现客服系统 (路由 → 专家 Agent)

---

## 推荐学习资源

### 官方教程 (最权威)
| 资源 | 链接 | 说明 |
|------|------|------|
| LangChain 官方文档 | https://python.langchain.com/docs/ | 入门+API 参考 |
| LangGraph 官方文档 | https://langchain-ai.github.io/langgraph/ | Agent 编排 |
| LangChain Academy | https://academy.langchain.com/ | **免费** 官方视频课程 |
| LangSmith 文档 | https://docs.smith.langchain.com/ | 可观测性 |

### 视频课程
| 资源 | 说明 |
|------|------|
| LangChain Academy (官方) | 免费，覆盖 LangChain + LangGraph，强烈推荐 |
| DeepLearning.AI 短课 | 吴恩达合作课程，适合快速入门 |

### 实战项目建议

| 阶段 | 项目 | 涉及章节 |
|------|------|----------|
| 入门 | 带工具的聊天机器人 (搜索+计算) | 第1-3章 |
| 进阶 | 基于私有文档的 QA 系统 (RAG) | 第4章 |
| 高级 | 自动代码审查 Agent | 第5-6章 |
| 专家 | 多 Agent 客服系统 | 第7-8章 |

---

## 关键依赖版本 (2025/2026)

```bash
pip install langchain>=0.3          # 核心框架
pip install langchain-core>=0.3     # 核心抽象
pip install langchain-openai>=0.3   # OpenAI 集成
pip install langgraph>=0.4          # 图编排引擎
pip install langsmith>=0.2          # 可观测性
```

> ⚠️ LangChain 在 0.2→0.3 有较大 breaking change，确保用最新版本学习。

---

## 学习检查清单

### ✅ LangChain 基础
- [ ] 能用 ChatModel 调用不同 LLM
- [ ] 能创建和使用 PromptTemplate
- [ ] 能用 `with_structured_output()` 获取结构化输出
- [ ] 能用 LCEL `|` 管道串联组件
- [ ] 理解 Runnable 接口

### ✅ Tool & Agent
- [ ] 能用 `@tool` 定义自定义工具
- [ ] 能用 `create_react_agent()` 创建 Agent
- [ ] 理解 ReAct 循环原理

### ✅ RAG
- [ ] 能用 LangChain 实现完整 RAG Pipeline
- [ ] 能使用不同 Retriever 策略

### ✅ LangGraph
- [ ] 能定义 State、Node、Edge
- [ ] 能构建有循环的 Agent 图
- [ ] 能实现 Human-in-the-loop
- [ ] 能使用 Checkpointing 持久化状态

### ✅ 生产化
- [ ] 能用 LangSmith 追踪和评估
- [ ] 能部署 Agent 为 API
- [ ] 能实现多 Agent 协作

---

> **按这个路线学完后，你将能独立构建从简单 Chain 到复杂多 Agent 系统的全栈 AI 应用。**
