# 06 - Guardrail 系统：并行竞态与 Tripwire 传播

> Guardrail（护栏）是 SDK 的安全机制，分为输入、输出、工具三个层级。
> 本文剖析 Guardrail 的执行时机、并行竞态处理、以及 tripwire 触发后的中止逻辑。

---

## Guardrail 类型总览

```
                          Agent 执行流程
                               │
 Input Guardrail ──────────→  LLM 调用  ──────────→ Output Guardrail
 (检查用户输入)            │         │              (检查最终输出)
                          │         │
                    ┌─────┴─────┐   │
                    │ Tool Call │   │
                    └─────┬─────┘   │
                          │         │
              Tool Input  │         │  Tool Output
              Guardrail ──┤         ├── Guardrail
              (检查工具入参)│         │  (检查工具出参)
                          │         │
                    ┌─────┴─────┐   │
                    │ Tool 执行  │   │
                    └───────────┘   │
```

| 层级 | 类型 | 检查时机 | 配置位置 |
|------|------|---------|---------|
| Agent 级 | InputGuardrail | 第一轮 LLM 调用前/并行 | `agent.input_guardrails` / `run_config.input_guardrails` |
| Agent 级 | OutputGuardrail | 最终输出产生后 | `agent.output_guardrails` / `run_config.output_guardrails` |
| Tool 级 | ToolInputGuardrail | 工具执行前 | `function_tool.tool_input_guardrails` |
| Tool 级 | ToolOutputGuardrail | 工具执行后 | `function_tool.tool_output_guardrails` |

---

## Input Guardrail：详细剖析

### 定义

源码：`guardrail.py:72-130`

```python
@dataclass
class InputGuardrail(Generic[TContext]):
    guardrail_function: Callable[
        [RunContextWrapper[TContext], Agent[Any], str | list[TResponseInputItem]],
        MaybeAwaitable[GuardrailFunctionOutput],
    ]
    name: str | None = None
    run_in_parallel: bool = True   # ← 关键配置
```

### GuardrailFunctionOutput

```python
@dataclass
class GuardrailFunctionOutput:
    output_info: Any              # 附加信息（检查细节、日志等）
    tripwire_triggered: bool      # 是否触发中止
```

### 使用示例

```python
async def check_off_topic(ctx, agent, input):
    # 用另一个 LLM 判断是否离题
    result = await classify_input(input)
    return GuardrailFunctionOutput(
        output_info={"classification": result},
        tripwire_triggered=(result == "off_topic"),
    )

agent = Agent(
    name="客服",
    input_guardrails=[
        InputGuardrail(guardrail_function=check_off_topic),
    ],
)
```

---

## Input Guardrail 的执行时机

源码：`run.py:985-1064`

**只在第一轮**（`current_turn <= 1`）执行，因为输入只需要检查一次。

### 执行分为两阶段

```python
all_input_guardrails = starting_agent.input_guardrails + (run_config.input_guardrails or [])

# 第一阶段：串行 guardrail
sequential_guardrails = [g for g in all_input_guardrails if not g.run_in_parallel]
# 第二阶段：并行 guardrail（与 LLM 调用并行）
parallel_guardrails = [g for g in all_input_guardrails if g.run_in_parallel]
```

### 串行执行（run_in_parallel=False）

```python
if sequential_guardrails:
    sequential_results = await run_input_guardrails(
        starting_agent,
        sequential_guardrails,
        copy_input_items(prepared_input),
        context_wrapper,
    )
```

串行 guardrail 在 LLM 调用**之前**执行。如果 tripwire 触发，LLM 调用根本不会发生。

### 并行执行（run_in_parallel=True，默认）

```python
# 先创建 LLM 调用任务
model_task = asyncio.create_task(run_single_turn(...))

if parallel_guardrails:
    try:
        parallel_results, turn_result = await asyncio.gather(
            run_input_guardrails(starting_agent, parallel_guardrails, input, context),
            model_task,
        )
    except InputGuardrailTripwireTriggered:
        # guardrail 触发了！
        if should_cancel_parallel_model_task_on_input_guardrail_trip():
            if not model_task.done():
                model_task.cancel()  # 取消 LLM 调用
            await asyncio.gather(model_task, return_exceptions=True)
        raise  # 传播异常
```

**并行竞态的关键点**：

1. guardrail 和 LLM 调用**同时启动**（`asyncio.gather`）
2. 如果 guardrail **先完成**并触发 tripwire：
   - 取消尚未完成的 LLM 任务（`model_task.cancel()`）
   - 抛出 `InputGuardrailTripwireTriggered` 异常
3. 如果 LLM **先完成**：
   - 等待 guardrail 完成
   - 如果 guardrail 此时触发 tripwire，LLM 结果被丢弃
4. 如果 LLM 调用出错：
   - `asyncio.gather` 会传播异常
   - guardrail 结果被丢弃

> **为什么默认并行？** 为了减少延迟。guardrail 通常需要调用另一个 LLM（分类检查），与主 LLM 调用并行可以节省时间。代价是可能浪费一次 LLM 调用（如果 guardrail 触发）。

---

## Output Guardrail：最终输出检查

### 定义

源码：`guardrail.py:133-185`

```python
@dataclass
class OutputGuardrail(Generic[TContext]):
    guardrail_function: Callable[
        [RunContextWrapper[TContext], Agent[Any], Any],  # 第三个参数是 agent 输出
        MaybeAwaitable[GuardrailFunctionOutput],
    ]
    name: str | None = None
```

Output guardrail **没有** `run_in_parallel` 选项——它总是在最终输出确定后才执行。

### 执行时机

当 `execute_tools_and_side_effects` 返回 `NextStepFinalOutput` 时，主循环在返回结果前执行 output guardrails：

```python
# 简化逻辑
if isinstance(next_step, NextStepFinalOutput):
    output_guardrail_results = await run_output_guardrails(
        agent.output_guardrails + run_config.output_guardrails,
        context_wrapper,
        agent,
        next_step.output,
    )
    # 如果 tripwire 触发 → OutputGuardrailTripwireTriggered
```

---

## Tool Guardrail：工具级别的检查

### ToolInputGuardrail

在工具执行**之前**检查输入参数：

```python
@dataclass
class ToolInputGuardrail(Generic[TContext]):
    guardrail_function: Callable[
        [RunContextWrapper[TContext], ToolInputGuardrailData],
        MaybeAwaitable[ToolGuardrailFunctionOutput],
    ]
```

`ToolInputGuardrailData` 包含：
- `agent`: 当前 agent
- `tool`: 被调用的工具
- `tool_call`: LLM 的工具调用请求
- `input_args`: 解析后的参数

### ToolOutputGuardrail

在工具执行**之后**检查输出：

```python
@dataclass
class ToolOutputGuardrail(Generic[TContext]):
    guardrail_function: Callable[
        [RunContextWrapper[TContext], ToolOutputGuardrailData],
        MaybeAwaitable[ToolGuardrailFunctionOutput],
    ]
```

`ToolOutputGuardrailData` 包含：
- `agent`, `tool`, `tool_call`: 同上
- `output`: 工具的返回值

### ToolGuardrailFunctionOutput 的三种行为

```python
class ToolGuardrailFunctionOutput:
    output_info: Any
    behavior: AllowBehavior | RaiseExceptionBehavior | RejectContentBehavior
```

| 行为 | 效果 |
|------|------|
| `AllowBehavior` | 通过检查，工具调用继续 |
| `RaiseExceptionBehavior` | 抛出异常，终止运行（类似 tripwire） |
| `RejectContentBehavior(content="...")` | 不终止运行，但用拒绝内容替代工具输出发给 LLM |

`RejectContentBehavior` 是 tool guardrail 独有的——它允许"软拒绝"，让 LLM 知道工具调用被安全策略阻止了，LLM 可以换个策略。

---

## Tripwire 传播机制

### InputGuardrailTripwireTriggered

```python
class InputGuardrailTripwireTriggered(GuardrailTripwireTriggered):
    """An input guardrail tripwire was triggered."""
    guardrail_result: InputGuardrailResult
```

这个异常从 guardrail 执行处抛出，沿调用栈向上传播：

```
run_input_guardrails()
  └── guardrail.run() → tripwire_triggered=True → raise InputGuardrailTripwireTriggered
        ↑
asyncio.gather(guardrails, model_task)
  └── 捕获异常 → cancel model_task → re-raise
        ↑
AgentRunner.run() 主循环
  └── 捕获异常 → persist session (如果配置了) → re-raise
        ↑
用户代码
  └── try/except InputGuardrailTripwireTriggered as e:
        e.guardrail_result.output.output_info  # 检查细节
```

### OutputGuardrailTripwireTriggered

类似，但发生在最终输出产生后。

### ToolInputGuardrailTripwireTriggered / ToolOutputGuardrailTripwireTriggered

工具级别的 tripwire，发生在单个工具调用的前/后。

---

## 流式场景中的 Guardrail

流式模式（`run_streamed`）的 guardrail 处理更复杂，因为需要在事件流进行中检查。

### Input Guardrail（流式）

```python
# run_loop.py 中的流式主循环
# 串行 guardrail：先执行，再开始流式
if sequential_guardrails:
    await run_input_guardrails_with_queue(
        event_queue, sequential_guardrails, input, context
    )

# 并行 guardrail：作为后台任务
if parallel_guardrails:
    streamed_result._input_guardrails_task = asyncio.create_task(
        run_input_guardrails_with_queue(
            event_queue, parallel_guardrails, input, context
        )
    )
```

`run_input_guardrails_with_queue` 会将 guardrail 结果推送到事件队列，调用方可以通过流式事件观察 guardrail 状态。

### 流式中的 Tripwire 检查

```python
# 流式结束时检查
if streamed_result._input_guardrails_task:
    triggered = await input_guardrail_tripwire_triggered_for_stream(streamed_result)
    if triggered:
        raise InputGuardrailTripwireTriggered(...)
```

如果并行 guardrail 在流式传输过程中触发 tripwire，SDK 会在流结束时（而不是立即）抛出异常。这是因为已经发送的流式事件无法"撤回"。

---

## 场景走读：并行 Input Guardrail

```python
async def toxicity_check(ctx, agent, input):
    """调用毒性分类模型"""
    is_toxic = await classify_toxicity(input)
    return GuardrailFunctionOutput(
        output_info={"is_toxic": is_toxic, "model": "toxicity-v2"},
        tripwire_triggered=is_toxic,
    )

agent = Agent(
    name="助手",
    input_guardrails=[
        InputGuardrail(guardrail_function=toxicity_check, run_in_parallel=True),
    ],
    tools=[get_weather],
)

result = await Runner.run(agent, "你这个蠢东西，告诉我北京天气")
```

### 执行时间线（guardrail 先完成）

```
t=0ms   asyncio.gather 启动：
        - Task A: toxicity_check("你这个蠢东西...")
        - Task B: LLM 调用（run_single_turn）

t=50ms  Task A 完成：is_toxic=True → tripwire!
        → InputGuardrailTripwireTriggered 被抛出
        → Task B 被 cancel

t=50ms  异常传播到用户代码
```

### 执行时间线（LLM 先完成）

```
t=0ms   asyncio.gather 启动

t=200ms Task B 完成：LLM 返回 tool_call(get_weather, ...)
        → 但 asyncio.gather 还在等 Task A

t=250ms Task A 完成：is_toxic=True → tripwire!
        → InputGuardrailTripwireTriggered
        → LLM 结果被丢弃
```

---

## 设计洞察

### 1. 并行的成本-收益权衡

| | 串行（run_in_parallel=False） | 并行（run_in_parallel=True） |
|---|---|---|
| **延迟** | guardrail 时间 + LLM 时间 | max(guardrail 时间, LLM 时间) |
| **成本** | 如果 tripwire 触发，省下 LLM 调用 | 可能浪费一次 LLM 调用 |
| **适用** | 高触发率的 guardrail | 低触发率的 guardrail |

### 2. Guardrail 不改变输入

Input guardrail 只能"通过"或"中止"，不能修改输入。如果需要修改输入（如脱敏），应该用其他机制（如 `input_filter`）。

### 3. Tool Guardrail 的三态设计

与 Agent 级 guardrail 的二态（通过/中止）不同，Tool guardrail 有三态：

- **Allow**：通过
- **Raise**：中止整个运行
- **Reject**：软拒绝，用替代内容回复 LLM

这是因为工具调用不一定需要终止整个对话——可能只是这一次调用不被允许，LLM 可以换个方法。

### 4. Session 保存的时机

当 tripwire 触发时，SDK 仍然会尝试将已有的 session 数据持久化（如果配置了 session）：

```python
except InputGuardrailTripwireTriggered:
    await persist_session_items_for_guardrail_trip(session, ...)
    raise  # 然后再传播异常
```

这确保了即使运行被中止，session 历史也不会丢失。

---

## 小结

Guardrail 系统是 SDK 的安全网，通过四层检查保护 agent 运行：

1. **Input Guardrail**：第一轮检查用户输入，支持串行/并行
2. **Tool Input Guardrail**：每次工具调用前检查参数
3. **Tool Output Guardrail**：每次工具调用后检查结果
4. **Output Guardrail**：最终输出产生后检查

关键设计：
- 并行 guardrail 与 LLM 调用竞速，减少延迟
- Tripwire 触发后的 LLM 任务取消和 session 保存
- Tool guardrail 的三态设计（allow/raise/reject）允许更细粒度的控制
