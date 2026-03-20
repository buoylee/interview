# 04 - Handoff 机制：不只是切换 Agent

> Handoff 是 Agents SDK 多 Agent 协作的核心原语。
> 本文剖析 Handoff 从注册到触发到历史传递的完整流程，并对比 Handoff 与 Agent-as-Tool 两种模式。

---

## Handoff 概览

```
Agent A (路由)                    Agent B (专家)
    │                                  │
    ├── LLM 调用 transfer_to_专家B     │
    │     (伪装成 function_call)       │
    │                                  │
    ├── process_model_response 识别     │
    │     → ToolRunHandoff             │
    │                                  │
    ├── execute_handoffs()             │
    │     ├── on_invoke_handoff()      │
    │     ├── 历史过滤/嵌套            │
    │     └── return NextStepHandoff   │
    │                                  │
    └── 主循环设置 current_agent = B  ──→ B 开始处理
                                       └── B 看到完整(或过滤后的)历史
```

---

## 第一步：Handoff 的注册

### 方式一：直接传 Agent

```python
agent_b = Agent(name="专家B", instructions="你是一个专家")
agent_a = Agent(name="路由", handoffs=[agent_b])
```

SDK 在 `get_handoffs()` 时自动将 `Agent` 转换为 `Handoff` 对象：

源码：`run_internal/turn_preparation.py` 中 `get_handoffs()`

```python
for item in agent.handoffs:
    if isinstance(item, Agent):
        # 自动创建 Handoff
        handoff_obj = Handoff(
            tool_name="transfer_to_专家B",      # 自动生成
            tool_description="Handoff to the 专家B agent...",
            input_json_schema={},
            on_invoke_handoff=lambda ctx, args: agent_b,
            agent_name="专家B",
        )
    elif isinstance(item, Handoff):
        handoff_obj = item
```

### 方式二：handoff() 函数

```python
from agents import handoff

my_handoff = handoff(
    agent=agent_b,
    on_handoff=lambda ctx: print("切换到专家B"),  # 副作用回调
    input_filter=my_filter,                        # 历史过滤
    nest_handoff_history=True,                     # 嵌套历史
)
agent_a = Agent(name="路由", handoffs=[my_handoff])
```

源码：`handoffs/__init__.py:216-329`

`handoff()` 函数做的事：

1. 验证 `on_handoff` 和 `input_type` 的一致性
2. 为 `on_handoff` 创建类型验证（如果有 `input_type`）
3. 构建 `_invoke_handoff` 闭包：执行 `on_handoff` 回调，然后返回 `agent`
4. 生成默认 `tool_name`：`transfer_to_{agent_name}`（转为函数风格命名）
5. 对 `input_json_schema` 应用 `ensure_strict_json_schema`

### 带参数的 Handoff

```python
from pydantic import BaseModel

class EscalationData(BaseModel):
    reason: str
    priority: int

def on_escalate(ctx, data: EscalationData):
    print(f"升级原因: {data.reason}, 优先级: {data.priority}")

escalation = handoff(
    agent=agent_b,
    on_handoff=on_escalate,
    input_type=EscalationData,
)
```

这种情况下，LLM 不仅调用 `transfer_to_专家B`，还会传递 JSON 参数：

```json
{"reason": "用户问题涉及退款政策", "priority": 1}
```

SDK 会用 `TypeAdapter(EscalationData)` 验证参数，然后传给 `on_handoff`。

---

## 第二步：Handoff 在 LLM 侧的表现

Handoff 对 LLM 来说就是一个普通的 function tool：

```python
{
    "type": "function",
    "name": "transfer_to_专家B",
    "description": "Handoff to the 专家B agent to handle the request.",
    "parameters": {}  # 或者有参数 schema
}
```

LLM 返回：

```python
ResponseFunctionToolCall(
    type="function_call",
    name="transfer_to_专家B",
    call_id="call_xyz",
    arguments="{}",
)
```

> **设计决策**：Handoff 复用 function_call 协议，这意味着任何支持 function calling 的 LLM 都能做 Handoff，不需要特殊协议支持。

---

## 第三步：process_model_response 的识别

源码：`turn_resolution.py:1625-1631`

```python
# 在 ResponseFunctionToolCall 分支内：
if qualified_output_name == output.name and output.name in handoff_map:
    items.append(HandoffCallItem(raw_item=output, agent=agent))
    run_handoffs.append(ToolRunHandoff(tool_call=output, handoff=handoff_map[output.name]))
```

**关键判断**：`qualified_output_name == output.name`

这确保了只有**无命名空间**的 function_call 才会匹配 handoff。带命名空间的工具（如 MCP 工具 `namespace.transfer_to_xxx`）不会被误识别为 handoff。

---

## 第四步：execute_handoffs() — 核心执行

源码：`turn_resolution.py:285-461`

### 4.1 多 Handoff 处理

```python
multiple_handoffs = len(run_handoffs) > 1
if multiple_handoffs:
    output_message = "Multiple handoffs detected, ignoring this one."
    new_step_items.extend([
        ToolCallOutputItem(output=output_message, ...)
        for handoff in run_handoffs[1:]  # 忽略后续的 handoff
    ])
```

**当 LLM 同时返回多个 handoff 时，SDK 只执行第一个**，其余的被忽略并返回错误消息。这是一个重要的设计约束——一次只能切换到一个 agent。

### 4.2 触发 handoff

```python
actual_handoff = run_handoffs[0]
with handoff_span(from_agent=agent.name) as span:
    handoff = actual_handoff.handoff

    # 调用 on_invoke_handoff → 返回新 agent
    new_agent = await handoff.on_invoke_handoff(context_wrapper, actual_handoff.tool_call.arguments)

    span.span_data.to_agent = new_agent.name
```

### 4.3 生成 HandoffOutputItem

```python
new_step_items.append(
    HandoffOutputItem(
        agent=agent,
        raw_item=ItemHelpers.tool_call_output_item(
            actual_handoff.tool_call,
            handoff.get_transfer_message(new_agent),  # → '{"assistant": "专家B"}'
        ),
        source_agent=agent,
        target_agent=new_agent,
    )
)
```

transfer message 的格式是 `{"assistant": "agent_name"}`，作为 tool_call_output 发给 LLM。

### 4.4 触发钩子

```python
await asyncio.gather(
    hooks.on_handoff(context=context_wrapper, from_agent=agent, to_agent=new_agent),
    agent.hooks.on_handoff(context_wrapper, agent=new_agent, source=agent)
        if agent.hooks else noop(),
)
```

### 4.5 历史过滤（最复杂的部分）

SDK 提供了三种方式控制新 agent 看到的历史：

#### 方式 A：input_filter（自定义过滤）

```python
if input_filter:
    handoff_input_data = HandoffInputData(
        input_history=tuple(original_input),
        pre_handoff_items=tuple(pre_step_items),
        new_items=tuple(new_step_items),
        run_context=context_wrapper,
    )
    filtered = input_filter(handoff_input_data)  # 同步或异步
    # 用 filtered 的结果替换 original_input, pre_step_items, new_step_items
```

`HandoffInputData` 包含三部分历史：

```
input_history     = Runner.run() 调用时传入的原始输入
pre_handoff_items = 之前所有 turn 生成的 items
new_items         = 当前 turn 生成的 items（包括 handoff 调用本身和 transfer message）
```

过滤函数可以自由修改这三个部分。返回的 `HandoffInputData` 还可以额外设置 `input_items` —— 当设置时，`input_items` 用于发给 LLM，而 `new_items` 保留完整版本用于 session 存储。

#### 方式 B：nest_handoff_history（历史嵌套）

源码：`handoffs/history.py:71-112`

```python
def nest_handoff_history(handoff_input_data, *, history_mapper=None):
    # 1. 将所有历史（input_history + pre_items + new_items）合并为一个转录本
    transcript = flattened_history + pre_items_as_inputs + new_items_as_inputs

    # 2. 用 mapper 将转录本压缩为摘要
    history_items = mapper(transcript)

    # 3. 过滤 pre_items 和 new_items，移除已被摘要的项
    return handoff_input_data.clone(
        input_history=tuple(history_items),
        pre_handoff_items=tuple(filtered_pre_items),
        input_items=tuple(filtered_input_items),
    )
```

默认的 `default_handoff_history_mapper` 将整个转录本变成一条 assistant 消息：

```
For context, here is the conversation so far between the user and the previous agent:
<CONVERSATION HISTORY>
1. [user] 北京天气怎么样？
2. [assistant] 让我查一下...
3. [tool_call] get_weather({"city": "北京"})
4. [tool_output] 北京今天晴，25°C
5. [assistant] 北京今天晴，25°C。还有什么问题？
</CONVERSATION HISTORY>
```

> **为什么要嵌套？** 如果直接传递完整历史，新 agent 会看到之前 agent 的 tool_call 和 tool_output，但这些工具可能不属于新 agent，导致混乱。嵌套历史将它们压缩成一段可读文本。

#### 方式 C：不过滤（默认）

新 agent 看到完整的 `original_input` + `pre_step_items` + `new_step_items`。

### 过滤中的 session 分离

```python
# input_filter 模式：
if filtered.input_items is not None:
    session_step_items = list(filtered.new_items)     # session 保存完整版
    new_step_items = list(filtered.input_items)       # 发给 LLM 的过滤版

# nest_handoff_history 模式：
session_step_items = list(nested.new_items)           # session 保存完整版
new_step_items = list(nested.input_items or nested.new_items)  # LLM 用过滤版
```

**设计洞察**：session 存储的是完整历史（用于审计和恢复），发给 LLM 的是过滤后的历史（用于效率和避免混乱）。这两者可以不同。

---

## 第五步：回到主循环

```python
return SingleStepResult(
    original_input=original_input,      # 可能已被过滤器修改
    model_response=new_response,
    pre_step_items=pre_step_items,      # 可能已被过滤器修改
    new_step_items=new_step_items,      # 可能已被过滤器修改
    next_step=NextStepHandoff(new_agent),
    session_step_items=session_step_items,  # 完整版本，用于 session
)
```

主循环收到 `NextStepHandoff` 后：

```python
# run.py 主循环中：
if isinstance(next_step, NextStepHandoff):
    current_agent = next_step.new_agent
    # 更新 pre_step_items, original_input 等
    # 继续下一轮循环
```

---

## Handoff vs Agent-as-Tool

SDK 提供两种多 Agent 协作模式：

### Handoff

```python
agent_a = Agent(name="路由", handoffs=[agent_b])
```

### Agent-as-Tool

```python
agent_b_tool = agent_b.as_tool(
    tool_name="ask_expert",
    tool_description="向专家咨询",
)
agent_a = Agent(name="路由", tools=[agent_b_tool])
```

源码：`agent.py:470-560+`

| 特性 | Handoff | Agent-as-Tool |
|------|---------|---------------|
| **控制权** | 转移给新 agent | 仍在原 agent |
| **历史传递** | 新 agent 看到完整历史 | 新 agent 只看到工具输入 |
| **对话延续** | 新 agent 继续对话 | 原 agent 收到工具输出后继续 |
| **LLM 表现** | function_call → NextStepHandoff | function_call → 嵌套 Runner.run() |
| **适用场景** | 任务路由、转接 | 子任务查询、专家咨询 |
| **主循环行为** | 切换 current_agent | 不切换，工具输出回传 |

### Agent-as-Tool 的执行

```python
# agent.py: as_tool() 内部
async def _run_agent_impl(context, input_json):
    # 解析输入
    input_data = json.loads(input_json)

    # 以嵌套方式运行 agent
    result = await Runner.run(self, input_data["input"])  # 或 Runner.run_streamed

    # 提取输出
    if custom_output_extractor:
        return await custom_output_extractor(result)
    return result.final_output  # 最后一条消息
```

**Agent-as-Tool 本质上是在工具调用中嵌套了一个完整的 Runner.run()**。

---

## 场景走读：路由 Agent 转接到专家

```python
expert = Agent(name="退款专家", instructions="处理退款相关问题")
router = Agent(
    name="客服路由",
    instructions="根据问题类型转接到对应专家",
    handoffs=[expert],
)

result = await Runner.run(router, "我要退款")
```

### 第一轮：路由 Agent

1. LLM 收到消息 "我要退款" + 工具 `transfer_to_退款专家`
2. LLM 返回 `function_call(transfer_to_退款专家, {})`
3. `process_model_response`：识别为 handoff → `HandoffCallItem` + `ToolRunHandoff`
4. `execute_tools_and_side_effects`：发现 `processed_response.handoffs` 不为空 → 调用 `execute_handoffs()`
5. `execute_handoffs`：
   - 调用 `on_invoke_handoff()` → 返回 `expert` Agent
   - 创建 `HandoffOutputItem`（transfer message: `{"assistant": "退款专家"}`）
   - 不过滤历史（默认模式）
   - 返回 `NextStepHandoff(new_agent=expert)`
6. 主循环：`current_agent = expert`

### 第二轮：退款专家 Agent

1. 退款专家看到的输入：
   ```
   原始输入: "我要退款"
   + HandoffCallItem(transfer_to_退款专家)
   + HandoffOutputItem({"assistant": "退款专家"})
   ```
2. LLM（作为退款专家）返回最终回答
3. 主循环：`NextStepFinalOutput` → 结束

---

## 深入：历史嵌套的实现

源码：`handoffs/history.py`

### _flatten_nested_history_messages

如果已经有嵌套历史（多次 handoff），这个函数会把之前嵌套的 `<CONVERSATION HISTORY>` 展平：

```
第一次 handoff: A → B
  B 的输入 = [嵌套历史(A的对话)]

第二次 handoff: B → C
  C 的输入 = [嵌套历史(展平的 A 对话 + B 的对话)]
```

### _should_forward_pre_item / _should_forward_new_item

过滤逻辑：已被嵌套摘要涵盖的 `function_call`、`function_call_output`、`reasoning` 类型不再单独发送，避免重复。

```python
_SUMMARY_ONLY_INPUT_TYPES = {
    "function_call",
    "function_call_output",
    "reasoning",
}
```

---

## 设计洞察

### 1. Handoff 是单向的

一旦 A handoff 到 B，主循环的 `current_agent` 变成 B。A 不再参与。如果 B 需要回到 A，B 也需要配置到 A 的 handoff。

### 2. 历史是可控的

三层控制：
- **不过滤**：新 agent 看到一切（默认）
- **嵌套**：压缩为摘要，但信息不丢失
- **自定义过滤**：完全控制新 agent 看到什么

### 3. Session 和 LLM 输入的分离

通过 `session_step_items` vs `new_step_items` 的分离，SDK 可以：
- 给 LLM 一个精简的、过滤后的输入
- 在 session 中保存完整的、未过滤的历史

### 4. 多 Handoff 的防御

只执行第一个 handoff，其余忽略。这避免了"同时切换到多个 agent"的未定义行为。

---

## 小结

Handoff 机制的核心是三个阶段：

1. **注册**：Agent 或 `handoff()` → Handoff 对象 → 伪装成 function tool
2. **识别**：`process_model_response` 通过 `handoff_map` 将 function_call 识别为 handoff
3. **执行**：`execute_handoffs()` 触发回调 → 过滤/嵌套历史 → 返回 `NextStepHandoff`
4. **切换**：主循环更新 `current_agent`，新 agent 在下一轮开始处理
