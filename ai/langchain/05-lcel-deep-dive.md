# 第2章：LCEL 深入 — LangChain Expression Language

> LCEL 是 LangChain 的核心范式——用管道符 `|` 把组件像乐高一样拼在一起。理解 LCEL 才算真正理解 LangChain。

---

## 一、LCEL 是什么

### 1.1 一句话定义

**LCEL = 用 `|` (管道符) 将 Runnable 组件串联成链**，前一个组件的输出自动作为下一个组件的输入。

```python
chain = prompt | llm | output_parser
#       ↑         ↑       ↑
#    Runnable  Runnable  Runnable
#       └── output ──→ input ──→ output ──→ result
```

### 1.2 与传统方式对比

```python
# ❌ 传统方式 — 手动传递数据
prompt_value = prompt.invoke({"question": "什么是 RAG?"})
llm_output = llm.invoke(prompt_value)
result = parser.invoke(llm_output)

# ✅ LCEL 方式 — 自动串联
chain = prompt | llm | parser
result = chain.invoke({"question": "什么是 RAG?"})
```

### 1.3 LCEL 的核心优势

| 优势 | 说明 |
|------|------|
| **统一接口** | 所有链自动获得 invoke/stream/batch/ainvoke/astream/abatch |
| **流式传输** | 自动支持逐 token 流式输出，无需额外编码 |
| **并行执行** | RunnableParallel 自动并行化，提升效率 |
| **重试/降级** | .with_retry(), .with_fallbacks() 开箱即用 |
| **可观测性** | 与 LangSmith 自动集成，每一步都可追踪 |
| **可组合** | 链可以嵌套在链中，链可以作为更大链的一部分 |

---

## 二、Runnable 接口 — LCEL 的基础

### 2.1 所有组件都是 Runnable

```
LangChain 中，几乎所有组件都实现了 Runnable 接口：

- ChatPromptTemplate  → Runnable
- ChatOpenAI          → Runnable
- StrOutputParser     → Runnable
- Retriever           → Runnable
- Tool                → Runnable
- 用 | 组合的 Chain    → 也是 Runnable!
```

### 2.2 Runnable 的标准方法

```python
# 任何 Runnable 都有这 6 个方法
runnable.invoke(input)      # 同步单次
runnable.stream(input)      # 同步流式
runnable.batch(inputs)      # 同步批量
runnable.ainvoke(input)     # 异步单次
runnable.astream(input)     # 异步流式
runnable.abatch(inputs)     # 异步批量

# 还有这些实用方法
runnable.with_config(...)     # 注入配置
runnable.with_retry(...)      # 添加重试
runnable.with_fallbacks(...)  # 添加降级
runnable.bind(...)            # 绑定固定参数
```

### 2.3 Runnable 的输入输出类型

```python
# 查看任何 Runnable 的输入输出 Schema
chain = prompt | llm | parser

print(chain.input_schema.model_json_schema())
# {"properties": {"question": {"type": "string"}}, "required": ["question"]}

print(chain.output_schema.model_json_schema())
# {"type": "string"}
```

### 2.4 面试深度问题

> **Q: 为什么说 LCEL 中 "一切都是 Runnable"？这有什么好处？**
>
> A: Runnable 是 LangChain 的统一抽象层，所有组件实现同一个接口。好处：(1) **可组合性** — 任意两个 Runnable 都能用 `|` 连接；(2) **统一执行** — 一条链自动获得 invoke/stream/batch 六个方法，不用分别为每个组件写流式逻辑；(3) **可观测** — LangSmith 自动追踪每个 Runnable 的输入输出；(4) **可互换** — 替换链中的某个组件不影响其他部分。这是典型的**接口隔离**设计模式。

---

## 三、核心 Runnable 类型

### 3.1 RunnablePassthrough — 透传

将输入原封不动地传到下一步。

```python
from langchain_core.runnables import RunnablePassthrough

# 常见用法: 在并行分支中传递原始输入
chain = {
    "context": retriever,                    # 检索上下文
    "question": RunnablePassthrough(),       # 原封不动传递用户问题
} | prompt | llm | StrOutputParser()

result = chain.invoke("什么是 RAG?")
# retriever 拿到 "什么是 RAG?" 去检索
# question 直接传递 "什么是 RAG?" 到 prompt
```

### 3.2 RunnablePassthrough.assign() — 增加字段

在现有输入中**追加**新字段，不覆盖原有字段。

```python
from langchain_core.runnables import RunnablePassthrough

chain = RunnablePassthrough.assign(
    context=lambda x: retriever.invoke(x["question"]),
    word_count=lambda x: len(x["question"]),
)

result = chain.invoke({"question": "什么是 RAG?"})
# result = {
#   "question": "什么是 RAG?",     ← 原有字段保留
#   "context": [...],              ← 新增字段
#   "word_count": 7,               ← 新增字段
# }
```

### 3.3 RunnableParallel — 并行执行

同时执行多个 Runnable，结果合并为 dict。

```python
from langchain_core.runnables import RunnableParallel

# 方式1: 显式 RunnableParallel
parallel = RunnableParallel(
    summary=summary_chain,
    translation=translation_chain,
    keywords=keyword_chain,
)
result = parallel.invoke("LangChain is a framework for building LLM apps")
# result = {
#   "summary": "...",
#   "translation": "...",
#   "keywords": [...]
# }

# 方式2: dict 简写（最常用）
chain = {"summary": summary_chain, "translation": translation_chain} | merge_prompt | llm
```

**面试要点**：dict 形式自动创建 RunnableParallel，这是 LCEL 最常用的模式之一。

### 3.4 RunnableLambda — 包装普通函数

将任意 Python 函数变成 Runnable。

```python
from langchain_core.runnables import RunnableLambda

def format_docs(docs):
    """将 Document 列表格式化为字符串"""
    return "\n\n".join(doc.page_content for doc in docs)

# 包装为 Runnable
format_docs_runnable = RunnableLambda(format_docs)

# 在链中使用
chain = retriever | format_docs_runnable | prompt | llm
# 等价于
chain = retriever | RunnableLambda(format_docs) | prompt | llm
# 也等价于 (LCEL 自动包装)
chain = retriever | format_docs | prompt | llm  # ← 直接用函数！
```

> **注意**: 在 `|` 管道中，普通函数会被自动包装为 `RunnableLambda`，所以一般不需要显式创建。

### 3.5 RunnableBranch — 条件分支

根据条件走不同的链。

```python
from langchain_core.runnables import RunnableBranch

branch = RunnableBranch(
    # (条件函数, 对应的链)
    (lambda x: "代码" in x["question"], code_chain),
    (lambda x: "翻译" in x["question"], translation_chain),
    # 默认分支 (最后一个，不带条件)
    general_chain,
)

result = branch.invoke({"question": "帮我写一段 Python 代码"})
# → 走 code_chain
```

**面试加分**：`RunnableBranch` 适合简单条件路由。复杂路由建议用 LangGraph 的 `add_conditional_edges()`。

---

## 四、LCEL 链的典型模式

### 4.1 最简链

```python
chain = prompt | llm | StrOutputParser()
```

### 4.2 RAG 链 (面试经典)

```python
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
```

**数据流解析**:
```
用户输入: "什么是 RAG?"
    ↓
RunnableParallel(dict):
  ├── context: retriever.invoke("什么是 RAG?") → [doc1, doc2] → format_docs → "doc1\n\ndoc2"
  └── question: RunnablePassthrough() → "什么是 RAG?"
    ↓
→ {"context": "doc1\n\ndoc2", "question": "什么是 RAG?"}
    ↓
prompt.invoke({...}) → [SystemMessage, HumanMessage(含context+question)]
    ↓
llm.invoke(messages) → AIMessage(content="RAG 是...")
    ↓
StrOutputParser().invoke(ai_msg) → "RAG 是..."
```

### 4.3 多步骤处理链

```python
chain = (
    RunnablePassthrough.assign(
        language=lambda x: detect_language(x["text"]),
    )
    | RunnablePassthrough.assign(
        translated=lambda x: translate(x["text"], x["language"]),
    )
    | RunnablePassthrough.assign(
        summary=lambda x: summarize_chain.invoke(x["translated"]),
    )
)
```

### 4.4 动态路由链

```python
from langchain_core.runnables import RunnableLambda

def route(info):
    if info["topic"] == "tech":
        return tech_chain
    elif info["topic"] == "business":
        return business_chain
    return general_chain

chain = (
    classify_prompt | llm.with_structured_output(TopicClassification)
    | RunnableLambda(route)
)
```

---

## 五、.bind() — 绑定固定参数

给 Runnable 绑定额外参数，之后调用时不需要再传。

```python
# 最常用: 给 LLM 绑定 tools
llm_with_tools = llm.bind(tools=[search_tool, calc_tool])

# 绑定 stop sequences
llm_with_stop = llm.bind(stop=["\n\nHuman:"])

# 绑定 response_format
llm_json = llm.bind(response_format={"type": "json_object"})
```

---

## 六、.with_config() — 运行时配置

```python
# 注入运行时配置
chain = prompt | llm | parser

result = chain.invoke(
    {"question": "hello"},
    config={
        "callbacks": [my_callback],      # 回调
        "tags": ["production", "v2"],    # 标签 (LangSmith 中筛选用)
        "metadata": {"user_id": "123"}, # 元数据
        "max_concurrency": 5,           # batch 时的并发数
        "run_name": "my_chain",         # 运行名称
    }
)
```

---

## 七、错误处理

### 7.1 .with_retry() — 自动重试

```python
chain = prompt | llm.with_retry(
    stop_after_attempt=3,          # 最多重试 3 次
    wait_exponential_jitter=True,  # 指数退避 + 随机抖动
) | parser
```

### 7.2 .with_fallbacks() — 降级策略

```python
# 主链失败时，尝试备用链
primary_chain = prompt | ChatOpenAI(model="gpt-4o") | parser
fallback_chain = prompt | ChatAnthropic(model="claude-sonnet-4-20250514") | parser

robust_chain = primary_chain.with_fallbacks([fallback_chain])
```

### 7.3 异常捕获

```python
from langchain_core.runnables import RunnableLambda

def safe_invoke(input):
    try:
        return risky_chain.invoke(input)
    except Exception as e:
        return f"处理失败: {str(e)}"

safe_chain = RunnableLambda(safe_invoke)
```

---

## 八、流式传输详解

### 8.1 链的流式输出

```python
# LCEL 链自动支持流式！
chain = prompt | llm | StrOutputParser()

for chunk in chain.stream({"question": "解释量子计算"}):
    print(chunk, end="", flush=True)
# 逐 token 输出
```

### 8.2 哪些组件支持流式？

| 组件 | 流式行为 |
|------|----------|
| ChatModel | ✅ 逐 token 流式 |
| StrOutputParser | ✅ 透传流式 |
| Prompt | ❌ 一次性输出 (Prompt 生成很快) |
| Retriever | ❌ 一次性输出 (检索结果) |
| RunnableLambda | ❌ 默认不流式 (可实现 `transform` 方法) |

### 8.3 astream_events — 高级流式

```python
# 获取链中每一步的事件流
async for event in chain.astream_events(
    {"question": "hello"},
    version="v2",
):
    if event["event"] == "on_chat_model_stream":
        print(event["data"]["chunk"].content, end="")
    elif event["event"] == "on_chain_start":
        print(f"\n--- {event['name']} 开始 ---")
```

---

## 九、调试技巧

### 9.1 查看链的结构

```python
chain = prompt | llm | parser

# 打印链的图结构
chain.get_graph().print_ascii()

# 查看输入输出 schema
print(chain.input_schema.model_json_schema())
print(chain.output_schema.model_json_schema())
```

### 9.2 中间步骤检查

```python
from langchain_core.runnables import RunnableLambda

def debug_print(x):
    print(f"🔍 中间值: {type(x)} = {x}")
    return x

chain = prompt | RunnableLambda(debug_print) | llm | RunnableLambda(debug_print) | parser
```

### 9.3 LangSmith 追踪

```bash
# 设置环境变量即可自动追踪
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=lsv2_pt_...
export LANGSMITH_PROJECT=my-project
```

---

## 十、LCEL vs LangGraph 何时用哪个

| 场景 | 用 LCEL | 用 LangGraph |
|------|---------|-------------|
| 简单链 (Prompt → LLM → Parse) | ✅ | 过度设计 |
| RAG (检索 → 生成) | ✅ | 过度设计 |
| 条件分支 (1-2 个) | ✅ RunnableBranch | 均可 |
| 需要循环的 Agent | ❌ | ✅ |
| 多步骤有状态工作流 | ❌ | ✅ |
| Human-in-the-loop | ❌ | ✅ |
| 多 Agent 协作 | ❌ | ✅ |

**经验法则**: 如果你的流程是 **线性的**（A→B→C），用 LCEL；如果有**循环、分支、状态管理**，用 LangGraph。

---

## 十一、练习任务

### 基础练习
- [ ] 构建一个 prompt | llm | StrOutputParser() 基础链
- [ ] 用 RunnableParallel (dict) 实现同时生成摘要+翻译
- [ ] 用 RunnablePassthrough.assign() 在数据流中追加字段

### 进阶练习
- [ ] 实现一个完整的 RAG LCEL 链
- [ ] 用 RunnableBranch 实现根据问题类型走不同链
- [ ] 给链加上 .with_retry() 和 .with_fallbacks()
- [ ] 用 chain.stream() 实现流式输出

### 面试模拟
- [ ] 画出一个 RAG LCEL 链的完整数据流
- [ ] 解释 Runnable 接口的设计理念和好处
- [ ] 比较 LCEL 和 LangGraph 的适用场景
- [ ] 说明 LCEL 链如何自动支持流式传输

---

> **本章掌握后，你应该能**：用 LCEL 构建任意复杂度的链式流水线，理解数据流的每一步，并知道何时应该切换到 LangGraph。
