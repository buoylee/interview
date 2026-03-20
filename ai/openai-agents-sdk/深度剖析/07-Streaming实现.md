# 07 - Streaming 实现：事件驱动的主循环

> 流式模式（`Runner.run_streamed()`）让用户在 LLM 生成过程中实时接收事件。
> 本文剖析流式主循环的架构、事件类型、去重机制、以及流式与非流式的差异。

---

## 流式 vs 非流式的架构差异

```
非流式 Runner.run()                    流式 Runner.run_streamed()
─────────────────                    ──────────────────────────
同步等待 LLM 完成                     LLM 边生成边推送事件
→ 返回 RunResult                     → 返回 RunResultStreaming
                                      → 通过 async for event 消费
```

### 入口差异

```python
# 非流式
result = await Runner.run(agent, "你好")
print(result.final_output)

# 流式
result = Runner.run_streamed(agent, "你好")
async for event in result.stream_events():
    if event.type == "raw_response_event":
        print(event.data)  # LLM token 级事件
    elif event.type == "run_item_stream_event":
        print(event.item)  # 语义级事件（消息、工具调用等）
```

---

## 事件类型

源码：`stream_events.py:1-64`

### 1. RawResponsesStreamEvent

```python
@dataclass
class RawResponsesStreamEvent:
    data: TResponseStreamEvent   # OpenAI API 的原始流式事件
    type: Literal["raw_response_event"] = "raw_response_event"
```

**最低级的事件**：直接透传 LLM 的流式事件（token 级别）。包括：
- `response.created` — 响应创建
- `response.output_item.added` — 开始新的输出项
- `response.content_part.added` — 新内容块
- `response.output_text.delta` — **文本增量**（最常用）
- `response.output_item.done` — 输出项完成
- `response.completed` — 响应完成

### 2. RunItemStreamEvent

```python
@dataclass
class RunItemStreamEvent:
    name: Literal[
        "message_output_created",
        "handoff_requested",
        "handoff_occured",        # ← 拼写错误，但不能改（breaking change）
        "tool_called",
        "tool_search_called",
        "tool_search_output_created",
        "tool_output",
        "reasoning_item_created",
        "mcp_approval_requested",
        "mcp_approval_response",
        "mcp_list_tools",
    ]
    item: RunItem
    type: Literal["run_item_stream_event"] = "run_item_stream_event"
```

**语义级事件**：SDK 解析 LLM 输出后生成的高级事件。对应 `RunItem` 的各种子类型。

### 3. AgentUpdatedStreamEvent

```python
@dataclass
class AgentUpdatedStreamEvent:
    new_agent: Agent[Any]
    type: Literal["agent_updated_stream_event"] = "agent_updated_stream_event"
```

当 handoff 发生，`current_agent` 切换时触发。

---

## 流式主循环架构

源码：`run_internal/run_loop.py:400+`

```
start_streaming()
│
├── 初始化 RunState, ConversationTracker
│
└── 主循环 while True:
    │
    ├── [恢复态] resolve_interrupted_turn()
    │   └── 推送事件到 event_queue
    │
    ├── 准备工具、输入
    │
    ├── Input Guardrail（串行 + 并行）
    │
    ├── run_single_turn_streamed()
    │   │
    │   ├── stream_response_with_retry()
    │   │   └── 逐个推送 RawResponsesStreamEvent → event_queue
    │   │
    │   ├── 响应完成后：process_model_response()
    │   │
    │   ├── 推送 RunItemStreamEvent → event_queue
    │   │   └── stream_step_items_to_queue()
    │   │
    │   └── execute_tools_and_side_effects()
    │       └── 工具输出也推送为 RunItemStreamEvent
    │
    ├── 根据 NextStep 决定下一步
    │
    └── 推送 QueueCompleteSentinel → event_queue（结束信号）
```

### 事件队列

流式模式的核心是一个 `asyncio.Queue`：

```python
event_queue: asyncio.Queue[StreamEvent | QueueCompleteSentinel]
```

- 生产者：run loop 内部的各个阶段
- 消费者：用户的 `async for event in result.stream_events()` 循环

`QueueCompleteSentinel` 是结束信号，消费者收到后停止迭代。

---

## 流式 LLM 调用

源码：`run_internal/run_loop.py` 中 `run_single_turn_streamed`

### 与非流式的关键差异

非流式：

```python
response = await model.get_response(...)  # 等待完整响应
```

流式：

```python
async for event in model.stream_response(...):
    # 每个 event 立即推送到 queue
    event_queue.put_nowait(RawResponsesStreamEvent(data=event))

    if isinstance(event, ResponseCompletedEvent):
        # 响应完成，提取完整的 ModelResponse
        model_response = extract_response(event)
```

**原始事件透传**：每个 LLM 流式事件都直接包装成 `RawResponsesStreamEvent` 推入队列，用户可以实时看到 token。

### 响应完成后的处理

流式响应完成后，处理与非流式**完全相同**：

```python
# 1. 分类
processed_response = process_model_response(...)

# 2. 推送分类结果为 RunItemStreamEvent
stream_step_items_to_queue(processed_response.new_items, event_queue)

# 3. 执行工具
step_result = await execute_tools_and_side_effects(...)

# 4. 推送工具结果为 RunItemStreamEvent
stream_step_items_to_queue(step_result.new_step_items, event_queue)
```

---

## 事件推送与去重

### stream_step_items_to_queue

```python
def stream_step_items_to_queue(items: list[RunItem], queue: asyncio.Queue):
    for item in items:
        event = _item_to_stream_event(item)
        if event is not None:
            queue.put_nowait(event)
```

### RunItem → RunItemStreamEvent 映射

| RunItem 类型 | event.name |
|-------------|------------|
| MessageOutputItem | `"message_output_created"` |
| HandoffCallItem | `"handoff_requested"` |
| HandoffOutputItem | `"handoff_occured"` |
| ToolCallItem | `"tool_called"` |
| ToolCallOutputItem | `"tool_output"` |
| ToolSearchCallItem | `"tool_search_called"` |
| ToolSearchOutputItem | `"tool_search_output_created"` |
| ReasoningItem | `"reasoning_item_created"` |
| MCPApprovalRequestItem | `"mcp_approval_requested"` |
| MCPApprovalResponseItem | `"mcp_approval_response"` |
| MCPListToolsItem | `"mcp_list_tools"` |

### 去重机制

在流式多轮循环中，同一个 RunItem 可能在不同阶段被推送。SDK 通过以下方式去重：

1. **ToolCallItem 去重**：`_dedupe_tool_call_items` 使用 `(call_id, name, arguments)` 三元组作为身份标识
2. **unique item appender**：`_make_unique_item_appender` 使用 Python 对象的 `id()` 做去重

---

## 流式中的增量 Session 持久化

流式模式的特殊之处在于，工具输出需要**增量**保存到 session，而不是等整个 turn 完成。

```python
# save_result_to_session 中：
already_persisted = run_state._current_turn_persisted_item_count
if already_persisted >= len(new_items):
    new_run_items = []
else:
    new_run_items = new_items[already_persisted:]  # 只保存新增的
```

`_current_turn_persisted_item_count` 追踪当前 turn 已经保存了多少 items，确保：
- 流式过程中可以中间保存（partial save）
- 不会重复保存已经持久化的 items

---

## 流式中的 Guardrail

### Input Guardrail

```python
# 串行 guardrail：先执行，再开始流式
if sequential_guardrails:
    await run_input_guardrails_with_queue(event_queue, sequential_guardrails, ...)

# 并行 guardrail：作为后台任务与 LLM 并行
if parallel_guardrails:
    streamed_result._input_guardrails_task = asyncio.create_task(
        run_input_guardrails_with_queue(event_queue, parallel_guardrails, ...)
    )
```

`run_input_guardrails_with_queue` 的区别是它会将 guardrail 结果也推送到事件队列。

### Output Guardrail

```python
streamed_result._output_guardrails_task = asyncio.create_task(
    run_output_guardrails(agent.output_guardrails + run_config.output_guardrails, ...)
)
```

Output guardrail 也是后台任务。如果 tripwire 触发：
- 流式事件已经发出，无法撤回
- 异常在流结束时（`stream_events()` 迭代完成后）才被检查和抛出

---

## RunResultStreaming

```python
@dataclass
class RunResultStreaming:
    _event_queue: asyncio.Queue    # 事件队列
    _state: RunState | None        # 可用于中断恢复

    async def stream_events(self) -> AsyncIterator[StreamEvent]:
        """消费事件流"""
        while True:
            event = await self._event_queue.get()
            if isinstance(event, QueueCompleteSentinel):
                break
            yield event

    # 最终结果（流完成后可用）
    final_output: Any
    new_items: list[RunItem]
    raw_responses: list[ModelResponse]
    input_guardrail_results: list[InputGuardrailResult]
    output_guardrail_results: list[OutputGuardrailResult]
```

用户可以：
1. `async for event in result.stream_events()` — 实时消费事件
2. 流结束后访问 `result.final_output` — 获取最终输出

---

## 场景走读：流式天气查询

```python
result = Runner.run_streamed(agent, "北京天气怎么样？")
async for event in result.stream_events():
    print(event)
```

### 事件序列

```
1. AgentUpdatedStreamEvent(new_agent=天气助手)

--- 第一轮：LLM 返回 tool_call ---

2. RawResponsesStreamEvent(data=response.created)
3. RawResponsesStreamEvent(data=response.output_item.added)     # function_call 项
4. RawResponsesStreamEvent(data=response.content_part.added)    # arguments 开始
5. RawResponsesStreamEvent(data=response.output_text.delta)     # '{"city'
6. RawResponsesStreamEvent(data=response.output_text.delta)     # '": "北京'
7. RawResponsesStreamEvent(data=response.output_text.delta)     # '"}'
8. RawResponsesStreamEvent(data=response.output_item.done)      # function_call 完成
9. RawResponsesStreamEvent(data=response.completed)             # 响应完成

10. RunItemStreamEvent(name="tool_called", item=ToolCallItem)

--- 工具执行 ---

11. RunItemStreamEvent(name="tool_output", item=ToolCallOutputItem)

--- 第二轮：LLM 返回最终文本 ---

12. RawResponsesStreamEvent(data=response.created)
13. RawResponsesStreamEvent(data=response.output_item.added)     # message 项
14. RawResponsesStreamEvent(data=response.output_text.delta)     # '北京'
15. RawResponsesStreamEvent(data=response.output_text.delta)     # '今天'
16. RawResponsesStreamEvent(data=response.output_text.delta)     # '晴，25°C'
17. RawResponsesStreamEvent(data=response.output_item.done)
18. RawResponsesStreamEvent(data=response.completed)

19. RunItemStreamEvent(name="message_output_created", item=MessageOutputItem)
```

---

## 设计洞察

### 1. 事件的两个粒度

- **RawResponsesStreamEvent**：token 级，用于实时显示文字
- **RunItemStreamEvent**：语义级，用于 UI 状态更新（显示"正在调用工具..."等）

应用层通常关注 raw events 做文字流式展示，关注 item events 做状态更新。

### 2. 队列作为解耦层

run loop 和用户消费之间通过 `asyncio.Queue` 解耦。run loop 不需要等待消费者处理，消费者也不需要知道 run loop 的内部状态。

### 3. 流式不改变核心逻辑

`process_model_response` 和 `execute_tools_and_side_effects` 在流式和非流式中是**完全相同**的代码。流式只是在它们的前后加了事件推送。

### 4. 流式的 Guardrail 限制

因为流式事件一旦发出就无法撤回，所以：
- Input guardrail 的 tripwire 如果在 LLM 已经开始输出后触发，已输出的内容无法回收
- Output guardrail 的检查结果在流结束后才能获取

---

## 小结

流式实现的核心是在非流式架构上叠加事件推送层：

1. **事件队列**（`asyncio.Queue`）作为 run loop 和消费者之间的桥梁
2. **RawResponsesStreamEvent** 透传 LLM token 级事件
3. **RunItemStreamEvent** 在 `process_model_response` 和工具执行后推送语义级事件
4. **增量 Session 保存** 通过 `_current_turn_persisted_item_count` 追踪已保存进度
5. **核心逻辑复用** — 分类器和执行引擎在流式/非流式间完全共享
