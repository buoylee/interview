# 05 - Hook 系统：拦截与扩展

> Hook 系统让 SDK 用户可以在 CLI 执行过程中注入 Python 逻辑。
> 这是 SDK 从"只读观察者"变成"有控制权的参与者"的关键机制。
> 本文分析 Hook 的注册、回调、和数据流。

---

## Hook 的定位

```
CLI 执行流程：
  收到 prompt → 调用 API → 返回 tool_use
                                  ↓
                         ┌── PreToolUse Hook ──┐
                         │  SDK 回调 Python 函数 │
                         │  可以：允许/拒绝/修改  │
                         └──────────────────────┘
                                  ↓
                            执行工具 (Bash/Read/...)
                                  ↓
                         ┌── PostToolUse Hook ──┐
                         │  SDK 回调 Python 函数  │
                         │  可以：添加上下文/修改   │
                         └──────────────────────┘
                                  ↓
                         结果喂回 API → 返回文本
```

---

## 10 种 Hook 事件

源码：`types.py:165-176`

```python
HookEvent = (
    Literal["PreToolUse"]
    | Literal["PostToolUse"]
    | Literal["PostToolUseFailure"]
    | Literal["UserPromptSubmit"]
    | Literal["Stop"]
    | Literal["SubagentStop"]
    | Literal["PreCompact"]
    | Literal["Notification"]
    | Literal["SubagentStart"]
    | Literal["PermissionRequest"]
)
```

| 事件 | 触发时机 | 典型用途 |
|------|---------|---------|
| `PreToolUse` | 工具执行**前** | 审批/拒绝/修改工具输入 |
| `PostToolUse` | 工具执行**后** | 添加上下文/修改 MCP 工具输出 |
| `PostToolUseFailure` | 工具执行**失败后** | 错误处理/额外上下文 |
| `UserPromptSubmit` | 用户提交 prompt 时 | 输入验证/上下文注入 |
| `Stop` | 主 Agent 停止时 | 清理/通知 |
| `SubagentStop` | 子 Agent 停止时 | 子任务完成通知 |
| `PreCompact` | 上下文压缩**前** | 自定义压缩指令 |
| `Notification` | CLI 发送通知时 | 通知转发 |
| `SubagentStart` | 子 Agent 启动时 | 子任务追踪 |
| `PermissionRequest` | 权限请求时 | 动态权限决策 |

---

## Hook 类型定义

### HookCallback — 回调函数签名

源码：`types.py:469-476`

```python
HookCallback = Callable[
    [HookInput, str | None, HookContext],
    Awaitable[HookJSONOutput],
]
```

三个参数：
1. `HookInput` — 事件数据（区分联合类型，每种事件不同）
2. `str | None` — tool_use_id（工具相关事件有值，其他为 None）
3. `HookContext` — 上下文（目前只有 `signal: None`，预留 abort 支持）

### HookInput — 区分联合类型

每种事件有对应的 TypedDict：

```python
class PreToolUseHookInput(BaseHookInput, _SubagentContextMixin):
    hook_event_name: Literal["PreToolUse"]
    tool_name: str              # "Bash" / "Read" / "Write" / ...
    tool_input: dict[str, Any]  # {"command": "ls -la"} / {"file_path": "..."} / ...
    tool_use_id: str

class PostToolUseHookInput(BaseHookInput, _SubagentContextMixin):
    hook_event_name: Literal["PostToolUse"]
    tool_name: str
    tool_input: dict[str, Any]
    tool_response: Any          # 工具执行结果
    tool_use_id: str

class SubagentStartHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStart"]
    agent_id: str               # 子 Agent ID
    agent_type: str             # "general-purpose" / "code-reviewer" / ...
```

### BaseHookInput — 公共字段

```python
class BaseHookInput(TypedDict):
    session_id: str
    transcript_path: str
    cwd: str
    permission_mode: NotRequired[str]
```

### _SubagentContextMixin — 子 Agent 归属

```python
class _SubagentContextMixin(TypedDict, total=False):
    agent_id: str      # 子 Agent ID（主线程不存在）
    agent_type: str    # Agent 类型
```

> **为什么用 Mixin？** 工具生命周期事件（PreToolUse/PostToolUse/PostToolUseFailure）
> 可能在主 Agent 或子 Agent 中触发。`agent_id` 用于在多个并行子 Agent 中归属事件。

---

## HookJSONOutput — 回调返回值

### 异步 Hook

```python
class AsyncHookJSONOutput(TypedDict):
    async_: Literal[True]         # → CLI 收到 "async": true
    asyncTimeout: NotRequired[int]  # 毫秒
```

返回 `async_: True` 告诉 CLI："不用等我，继续执行。我的结果稍后通过其他方式通知。"

### 同步 Hook

```python
class SyncHookJSONOutput(TypedDict):
    # 控制字段
    continue_: NotRequired[bool]        # False → CLI 停止执行
    suppressOutput: NotRequired[bool]   # True → 隐藏 stdout
    stopReason: NotRequired[str]        # continue=False 时的停止原因

    # 决策字段
    decision: NotRequired[Literal["block"]]   # "block" → 阻止执行
    systemMessage: NotRequired[str]     # 显示给用户的警告
    reason: NotRequired[str]            # 给 Claude 的反馈

    # Hook 特定输出
    hookSpecificOutput: NotRequired[HookSpecificOutput]
```

### Hook 特定输出

每种事件的 hookSpecificOutput 不同：

```python
class PreToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PreToolUse"]
    permissionDecision: NotRequired[Literal["allow", "deny", "ask"]]
    permissionDecisionReason: NotRequired[str]
    updatedInput: NotRequired[dict[str, Any]]   # 修改工具输入
    additionalContext: NotRequired[str]          # 注入额外上下文

class PostToolUseHookSpecificOutput(TypedDict):
    hookEventName: Literal["PostToolUse"]
    additionalContext: NotRequired[str]
    updatedMCPToolOutput: NotRequired[Any]       # 修改 MCP 工具输出
```

---

## Hook 注册流程

### 用户侧配置

```python
async def my_pre_tool_hook(input, tool_use_id, context):
    if input["tool_name"] == "Bash":
        command = input["tool_input"].get("command", "")
        if "rm -rf" in command:
            return {
                "decision": "block",
                "reason": "Dangerous command blocked",
            }
    return {}  # 默认允许

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(
                matcher="Bash",           # 只匹配 Bash 工具
                hooks=[my_pre_tool_hook],  # 回调函数列表
                timeout=30.0,             # 30 秒超时
            ),
        ],
    },
)
```

### SDK 内部转换

源码：`_internal/client.py:26-42`

```python
def _convert_hooks_to_internal_format(self, hooks):
    internal_hooks = {}
    for event, matchers in hooks.items():
        internal_hooks[event] = []
        for matcher in matchers:
            internal_matcher = {
                "matcher": matcher.matcher,    # "Bash"
                "hooks": matcher.hooks,        # [my_pre_tool_hook]
            }
            if matcher.timeout is not None:
                internal_matcher["timeout"] = matcher.timeout
            internal_hooks[event].append(internal_matcher)
    return internal_hooks
```

### Query.initialize() 中的 callback 注册

源码：`_internal/query.py:130-147`

```python
# 在 initialize 时为每个回调生成唯一 ID
for event, matchers in self.hooks.items():
    hooks_config[event] = []
    for matcher in matchers:
        callback_ids = []
        for callback in matcher.get("hooks", []):
            callback_id = f"hook_{self.next_callback_id}"   # "hook_0"
            self.next_callback_id += 1
            self.hook_callbacks[callback_id] = callback     # 保存引用
            callback_ids.append(callback_id)

        hook_matcher_config = {
            "matcher": matcher.get("matcher"),              # "Bash"
            "hookCallbackIds": callback_ids,                # ["hook_0"]
        }
```

**发给 CLI 的 initialize 请求**：
```json
{
  "subtype": "initialize",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hookCallbackIds": ["hook_0"],
        "timeout": 30
      }
    ]
  }
}
```

> **callback_id 的巧妙之处**：Python 函数对象不能序列化到 JSON，
> 所以 SDK 给每个回调分配一个字符串 ID，发给 CLI。
> CLI 需要回调时发送这个 ID，SDK 通过 `hook_callbacks` dict 找到对应函数。

---

## Hook 回调数据流

### 完整流程

```
1. CLI 执行到 PreToolUse 检查点
   → 检查 hooks 配置：有 "Bash" matcher 匹配
   → 向 SDK 发送 control_request

2. CLI → SDK (stdout):
   {
     "type": "control_request",
     "request_id": "cli_req_42",
     "request": {
       "subtype": "hook_callback",
       "callback_id": "hook_0",
       "input": {
         "hook_event_name": "PreToolUse",
         "tool_name": "Bash",
         "tool_input": {"command": "ls -la"},
         "tool_use_id": "toolu_123",
         "session_id": "abc",
         "transcript_path": "~/.claude/...",
         "cwd": "/home/user/project"
       },
       "tool_use_id": "toolu_123"
     }
   }

3. SDK 处理：
   Query._handle_control_request()
   → subtype == "hook_callback"
   → callback_id == "hook_0"
   → 找到 my_pre_tool_hook
   → await my_pre_tool_hook(input, "toolu_123", {"signal": None})
   → 用户函数返回 {}（允许）

4. SDK → CLI (stdin):
   {
     "type": "control_response",
     "response": {
       "subtype": "success",
       "request_id": "cli_req_42",
       "response": {}
     }
   }

5. CLI 收到允许 → 继续执行 Bash 工具
```

### Python → CLI 字段名转换

源码：`_internal/query.py:34-50`

```python
def _convert_hook_output_for_cli(hook_output):
    converted = {}
    for key, value in hook_output.items():
        if key == "async_":
            converted["async"] = value      # Python async_ → JSON async
        elif key == "continue_":
            converted["continue"] = value   # Python continue_ → JSON continue
        else:
            converted[key] = value
    return converted
```

> **为什么需要转换？** `async` 和 `continue` 是 Python 关键字，不能用作字典键名。
> SDK 使用 `async_` 和 `continue_`，发给 CLI 前转换回去。

---

## 实际使用场景

### 场景 1：阻止危险命令

```python
async def safety_hook(input, tool_use_id, context):
    if input["tool_name"] == "Bash":
        cmd = input["tool_input"].get("command", "")
        if any(danger in cmd for danger in ["rm -rf /", ":(){ :|:& };:", "dd if=/dev/zero"]):
            return {
                "decision": "block",
                "reason": f"Blocked dangerous command: {cmd}",
                "systemMessage": "This command has been blocked for safety.",
            }
    return {}

options = ClaudeAgentOptions(
    hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[safety_hook])]},
)
```

### 场景 2：修改工具输入

```python
async def sandbox_hook(input, tool_use_id, context):
    if input["tool_name"] == "Bash":
        cmd = input["tool_input"].get("command", "")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": {"command": f"sandbox-exec {cmd}"},
            }
        }
    return {}
```

### 场景 3：注入上下文

```python
async def context_hook(input, tool_use_id, context):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "Note: this tool was executed in staging environment",
        }
    }
```

### 场景 4：子 Agent 监控

```python
async def subagent_monitor(input, tool_use_id, context):
    agent_id = input.get("agent_id")
    agent_type = input.get("agent_type")
    print(f"Sub-agent started: {agent_type} ({agent_id})")
    return {}

options = ClaudeAgentOptions(
    hooks={"SubagentStart": [HookMatcher(hooks=[subagent_monitor])]},
)
```

---

## HookMatcher 的 matcher 字段

```python
@dataclass
class HookMatcher:
    matcher: str | None = None    # 匹配模式
    hooks: list[HookCallback] = field(default_factory=list)
    timeout: float | None = None  # 秒
```

`matcher` 的语法：
- `None` → 匹配所有
- `"Bash"` → 匹配工具名
- `"Write|MultiEdit|Edit"` → 匹配多个工具名（用 `|` 分隔）

---

## 与 OpenAI Agents SDK 的 Hook 对比

| 维度 | OpenAI RunHooks | Claude Hook System |
|------|----------------|-------------------|
| **实现方式** | Python 类方法重载 | 回调函数 + 控制协议 |
| **执行位置** | SDK 进程内 | SDK 进程内，但通过 IPC 与 CLI 同步 |
| **事件类型** | on_agent_start/end、on_llm_start/end、on_tool_start/end | PreToolUse、PostToolUse、SubagentStart 等 10 种 |
| **能力** | 纯观察者（不影响执行） | 可以拦截/修改/拒绝（有控制权） |
| **匹配** | 全局或 Agent 级别 | 按工具名 matcher 过滤 |
| **返回值** | 无返回值 | 返回 HookJSONOutput（控制执行流程） |

> **关键区别**：OpenAI 的 hooks 是**观察者模式**——你能看到发生了什么，但不能阻止。
> Claude 的 hooks 是**拦截器模式**——你可以在执行前拒绝、修改输入、或在执行后修改结果。
