# 08 - Session 与状态持久化：RunState 序列化与 Session 保存时机

> Session 和 RunState 是 SDK 中两个不同的持久化机制。
> Session 用于跨对话的历史存储，RunState 用于中断/恢复的状态快照。
> 本文剖析它们的保存时机、序列化格式、以及服务端会话追踪。

---

## 两种持久化的区别

| | Session | RunState |
|---|---|---|
| **用途** | 跨对话的历史记忆 | 单次运行的中断恢复 |
| **生命周期** | 长期（多次 Runner.run） | 短期（一次中断到恢复） |
| **内容** | 输入/输出历史（input items） | 完整运行快照（agent、responses、items、approvals、context） |
| **触发保存** | 每个 turn 自动保存 | 中断时自动构建 |
| **存储形式** | Session 接口实现（内存/数据库/API） | JSON 字符串 |

---

## Session 系统

### Session 接口

```python
class Session(Protocol):
    async def get_items(self, *, limit: int | None = None) -> list[TResponseInputItem]:
        """获取历史 items"""
        ...

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """添加新 items"""
        ...
```

SDK 提供了内置实现，也允许用户自定义。

### Session 保存的 5 个时机

源码追踪 `save_result_to_session` 的调用点：

#### 时机 1：初始输入保存

```python
# run.py 主循环启动后
if session and not is_resumed_state:
    await save_result_to_session(session, input_items, [], run_state)
```

在第一轮循环开始前，将用户的原始输入保存到 session。

#### 时机 2：每轮正常完成后

```python
# 每个 turn 完成后
turn_items = session_items_for_turn(turn_result)
await save_result_to_session(session, [], turn_items, run_state)
```

每轮循环完成后，将该轮生成的 items 增量保存。

#### 时机 3：Guardrail tripwire 触发时

```python
# guardrail 异常捕获中
except InputGuardrailTripwireTriggered:
    await persist_session_items_for_guardrail_trip(session, ...)
    raise
```

即使运行被 guardrail 中止，已有的 items 也要保存。

#### 时机 4：流式中间保存

```python
# 流式模式中，工具执行后
await save_result_to_session(session, [], new_items, run_state)
```

流式模式下，工具执行结果不等 turn 完成就保存（增量保存）。

#### 时机 5：中断恢复后

```python
# resolve_interrupted_turn 完成后
await save_resumed_turn_items(session, turn_result, run_state)
```

---

## save_result_to_session 的增量保存机制

源码：`session_persistence.py:227-300+`

```python
async def save_result_to_session(session, original_input, new_items, run_state, ...):
    # 1. 计算已保存的数量
    already_persisted = run_state._current_turn_persisted_item_count

    # 2. 只保存新增的 items
    if already_persisted >= len(new_items):
        new_run_items = []
    else:
        new_run_items = new_items[already_persisted:]

    # 3. 转换 RunItem → TResponseInputItem（API 格式）
    new_items_as_input = []
    for run_item in new_run_items:
        converted = run_item_to_input_item(run_item, reasoning_item_id_policy)
        if converted is not None:
            new_items_as_input.append(converted)

    # 4. 去重
    items_to_save = deduplicate_input_items_preferring_latest(input_list + new_items_as_input)

    # 5. 指纹比对，避免重复保存
    # ... fingerprinting logic ...

    # 6. 保存
    await session.add_items(items_to_save)

    # 7. 更新计数器
    if run_state:
        run_state._current_turn_persisted_item_count = len(new_items)
```

**关键设计**：

1. **增量保存**：通过 `_current_turn_persisted_item_count` 追踪已保存进度，避免重复保存
2. **指纹去重**：通过 `fingerprint_input_item` 计算每个 item 的指纹，跳过已存在的
3. **格式转换**：`RunItem` → `TResponseInputItem`，因为 session 存储的是 API 格式

---

## prepare_input_with_session：从 Session 加载历史

源码：`session_persistence.py:53-167`

```python
async def prepare_input_with_session(input, session, session_input_callback, ...):
    # 1. 从 session 获取历史
    history = await session.get_items(limit=resolved_settings.limit)

    # 2. 标准化格式
    converted_history = [ensure_input_item_format(item) for item in history]
    new_input_list = [ensure_input_item_format(item) for item in input_to_new_input_list(input)]

    # 3. 如果有 callback，让用户自定义合并策略
    if session_input_callback:
        combined = session_input_callback(history_copy, new_items_copy)
        # ... 复杂的 identity/frequency 分析，确定哪些是新的 ...
    else:
        prepared_items = converted_history + new_input_list

    # 4. 清理：移除孤立的 function_call（没有对应输出的）
    filtered = drop_orphan_function_calls(prepared_items, ...)

    # 5. 标准化 + 去重
    normalized = normalize_input_items_for_api(filtered)
    deduplicated = deduplicate_input_items_preferring_latest(normalized)

    return deduplicated, appended_items
```

**session_input_callback 的用途**：

```python
def my_callback(history, new_items):
    # 可以：
    # - 截断历史（只保留最近 N 条）
    # - 过滤某些类型的历史
    # - 重新排序
    # - 注入系统消息
    return filtered_history + new_items

result = await Runner.run(
    agent, "新问题",
    session=my_session,
    session_input_callback=my_callback,
)
```

---

## 服务端会话追踪（Server-managed Conversation）

### 两种模式

SDK 支持两种互斥的会话管理模式：

#### 模式 A：本地 Session

```python
session = InMemorySession()
result = await Runner.run(agent, "你好", session=session)
```

所有历史在本地管理，每次调用 LLM 时发送完整历史。

#### 模式 B：服务端会话

```python
result = await Runner.run(agent, "你好", conversation_id="conv_123")
# 或
result = await Runner.run(agent, "你好", previous_response_id="resp_456")
```

OpenAI API 服务端维护会话状态，本地只发送新消息 + 会话 ID。

### OpenAIServerConversationTracker

```python
# run.py / run_loop.py 中
if conversation_id or previous_response_id or auto_previous_response_id:
    server_conversation_tracker = OpenAIServerConversationTracker(
        conversation_id=conversation_id,
        previous_response_id=previous_response_id,
        auto_previous_response_id=auto_previous_response_id,
    )
```

**auto_previous_response_id**：自动将每次 LLM 响应的 ID 记录为下一次的 `previous_response_id`，实现自动链接。

### 互斥性

使用 server-managed conversation 时，**输入准备逻辑不同**：

```python
# 非服务端管理：发送完整历史
model_input = original_input + all_generated_items

# 服务端管理：只发送新内容 + conversation_id
model_input = new_items_only  # API 会自动接续之前的上下文
```

---

## RunState 的序列化格式

### to_json_dict() 输出结构

```python
{
    "schema_version": "1.6",
    "current_turn": 1,
    "max_turns": 10,
    "current_agent_name": "天气助手",
    "original_input": "北京天气怎么样？",
    "model_responses": [
        {
            "usage": {"input_tokens": 50, "output_tokens": 20, ...},
            "output": [
                {"type": "function_call", "name": "get_weather", "call_id": "...", ...}
            ],
            "response_id": "resp_xxx",
        }
    ],
    "generated_items": [
        {
            "type": "tool_call_item",
            "raw_item": {"type": "function_call", ...},
            "agent_name": "天气助手",
        }
    ],
    "approvals": {
        "delete_all": {
            "approved": ["call_abc"],  # 或 true（全局批准）
            "rejected": false,
        }
    },
    "conversation_id": null,
    "previous_response_id": null,
    "tool_use_tracker_snapshot": {
        "天气助手": ["get_weather"]
    },
    "context": {"user_id": "123"},  # 如果 context 是 mapping
    "context_meta": {
        "serialized_via": "mapping",
        "requires_deserializer": false,
    },
}
```

### RunItem 的序列化

每种 RunItem 子类都有对应的序列化/反序列化逻辑：

| RunItem 类型 | 序列化的 type 字段 |
|-------------|-------------------|
| MessageOutputItem | `"message_output_item"` |
| ToolCallItem | `"tool_call_item"` |
| ToolCallOutputItem | `"tool_call_output_item"` |
| HandoffCallItem | `"handoff_call_item"` |
| HandoffOutputItem | `"handoff_output_item"` |
| ReasoningItem | `"reasoning_item"` |
| ToolApprovalItem | `"tool_approval_item"` |
| CompactionItem | `"compaction_item"` |
| MCPApprovalRequestItem | `"mcp_approval_request_item"` |
| MCPApprovalResponseItem | `"mcp_approval_response_item"` |

### from_json() 的 Agent 重建

```python
RunState.from_json(json_str, starting_agent=agent)
```

反序列化时需要传入 `starting_agent`，因为：
1. Agent 包含 Python 函数（无法 JSON 序列化）
2. SDK 用 `_build_agent_map(starting_agent)` 构建名字 → Agent 的映射
3. 通过 `current_agent_name` 查找对应的 Agent 实例

```python
def _build_agent_map(starting_agent):
    """递归构建 agent 名字 → Agent 实例的映射"""
    agent_map = {starting_agent.name: starting_agent}
    for handoff in starting_agent.handoffs:
        target_agent = handoff.agent  # 或 handoff._agent_ref()
        if target_agent:
            agent_map[target_agent.name] = target_agent
            agent_map.update(_build_agent_map(target_agent))  # 递归
    return agent_map
```

> **限制**：Agent 名字必须唯一。如果两个 agent 同名，`from_json` 可能恢复到错误的 agent。

---

## Session 与 RunState 的协作

在中断/恢复场景中，两者可以一起使用：

```python
# 第一次运行
result = await Runner.run(agent, "转 1000 到 B 账户", session=session)
# → 中断（需要审批）

# 审批
result.state.approve(result.interruptions[0])

# 恢复：同时传入 RunState 和 session
result = await Runner.run(result.state, session=session)
```

**注意**：RunState 恢复时，session 历史可能已经包含了中断前保存的部分 items。SDK 通过指纹去重确保不会重复保存。

---

## Session 保存与 Handoff 的交互

Handoff 时的 session 保存需要特别处理：

```python
# session_items_for_turn 中
def session_items_for_turn(turn_result):
    # 优先使用 session_step_items（完整版本）
    items = (
        turn_result.session_step_items
        if turn_result.session_step_items is not None
        else turn_result.new_step_items  # 如果没有，用发给 LLM 的版本
    )
    return list(items)
```

回忆第 04 章：handoff 时可能有 `input_filter` 或 `nest_handoff_history`，这会产生两个版本：
- `new_step_items`：过滤后的，发给 LLM
- `session_step_items`：完整的，用于 session 存储

---

## Compaction（上下文压缩）

当对话变得很长时，OpenAI API 可能返回 `compaction` 类型的输出，表示服务端主动压缩了上下文。

```python
# process_model_response 中
if output_type == "compaction":
    items.append(CompactionItem(agent=agent, raw_item=compaction_raw))
```

SDK 支持感知 compaction 的 session 实现：

```python
if is_openai_responses_compaction_aware_session(session):
    # 传递 compaction 信息给 session
    await session.add_items(items, compaction_args=OpenAIResponsesCompactionArgs(...))
```

这允许 session 实现在 compaction 发生时清理旧历史。

---

## 设计洞察

### 1. 两层持久化的必要性

- **Session** 解决"记忆"问题：用户下次来时，agent 还记得之前说了什么
- **RunState** 解决"暂停"问题：这次调用还没完，需要等人审批后继续

它们的生命周期完全不同，不能合并。

### 2. 增量保存 vs 全量保存

SDK 选择**增量保存**（每 turn 保存新增 items），而不是全量保存（每次保存所有历史）：
- 避免重复写入
- 减少存储压力
- 但需要 `_current_turn_persisted_item_count` 追踪进度

### 3. 格式转换的代价

`RunItem` → `TResponseInputItem` 的转换不是零成本的。每个 RunItem 的 `raw_item` 需要被序列化为 API 兼容格式。这个转换在每次保存时都会发生。

### 4. 会话管理的互斥性

Server-managed conversation（conversation_id / previous_response_id）和本地 session 是两种不同的范式：
- Server-managed：服务端维护上下文，客户端轻量
- Local session：客户端维护完整历史，每次发送

两者可以同时配置（session 做本地存档，server 做上下文管理），但输入准备逻辑会有差异。

---

## 小结

状态持久化体系由三个层面构成：

1. **Session**：跨对话历史存储
   - 5 个保存时机（初始、每轮、guardrail trip、流式中间、恢复后）
   - 增量保存 + 指纹去重
   - `prepare_input_with_session` 加载并合并历史

2. **RunState**：中断恢复快照
   - 完整运行状态的 JSON 序列化
   - Schema 版本控制（1.0 → 1.6）
   - Agent 通过名字映射重建

3. **Server-managed Conversation**：服务端会话追踪
   - `conversation_id` / `previous_response_id` 模式
   - 自动链接（`auto_previous_response_id`）
   - 与本地 session 互补
