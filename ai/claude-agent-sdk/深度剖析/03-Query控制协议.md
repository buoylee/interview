# 03 - Query 控制协议：双向消息路由

> Query 是 SDK 的"交换机"——所有从 CLI 来的消息都经过它的路由，
> 所有发给 CLI 的控制请求都由它管理。
> 本文逐行走读 Query 类的完整实现。

---

## Query 的定位

```
用户代码 ←→ ClaudeSDKClient / InternalClient
                    ↕
               Query（本章）
                    ↕
            Transport（子进程 stdin/stdout）
                    ↕
            Claude Code CLI（Agent 执行引擎）
```

Query 在 Transport 之上构建了**控制协议层**，处理三类通信：

| 方向 | 类型 | 例子 |
|------|------|------|
| SDK → CLI | control_request | initialize、interrupt、set_model |
| CLI → SDK | control_request | can_use_tool、hook_callback、mcp_message |
| CLI → SDK | 普通消息 | assistant、result、system、stream_event |

---

## 构造函数 — 状态初始化

源码：`_internal/query.py:64-117`

```python
class Query:
    def __init__(self, transport, is_streaming_mode, can_use_tool=None,
                 hooks=None, sdk_mcp_servers=None, initialize_timeout=60.0,
                 agents=None):
        self.transport = transport
        self.is_streaming_mode = is_streaming_mode      # 始终 True
        self.can_use_tool = can_use_tool                # 权限回调
        self.hooks = hooks or {}                        # Hook 配置
        self.sdk_mcp_servers = sdk_mcp_servers or {}    # 进程内 MCP servers

        # 控制协议状态
        self.pending_control_responses: dict[str, anyio.Event] = {}
        self.pending_control_results: dict[str, dict | Exception] = {}
        self.hook_callbacks: dict[str, Callable] = {}   # callback_id → 函数
        self.next_callback_id = 0
        self._request_counter = 0

        # 消息流：memory_object_stream（带 100 条缓冲）
        self._message_send, self._message_receive = anyio.create_memory_object_stream[
            dict[str, Any]
        ](max_buffer_size=100)

        # 任务组（管理后台读取任务）
        self._tg: anyio.abc.TaskGroup | None = None

        # 用于跟踪第一个 result，决定何时关闭 stdin
        self._first_result_event = anyio.Event()
        self._stream_close_timeout = float(
            os.environ.get("CLAUDE_CODE_STREAM_CLOSE_TIMEOUT", "60000")
        ) / 1000.0  # ms → s
```

**核心数据结构**：

```
pending_control_responses:
  "req_1_abc" → anyio.Event()    ← SDK 发出请求后等待
  "req_2_def" → anyio.Event()

pending_control_results:
  "req_1_abc" → {"subtype": "success", "response": {...}}   ← CLI 返回后填入

hook_callbacks:
  "hook_0" → <async function pre_tool_use_handler>
  "hook_1" → <async function post_tool_use_handler>

message_stream:
  send端: _read_messages 推入
  receive端: receive_messages() 消费
```

---

## 消息路由 — _read_messages()

源码：`_internal/query.py:172-234`

这是整个 SDK 最核心的后台任务：

```python
async def _read_messages(self):
    try:
        async for message in self.transport.read_messages():
            if self._closed:
                break

            msg_type = message.get("type")

            # ──── 路由 1：CLI 返回控制响应 ────
            if msg_type == "control_response":
                response = message.get("response", {})
                request_id = response.get("request_id")
                if request_id in self.pending_control_responses:
                    event = self.pending_control_responses[request_id]
                    if response.get("subtype") == "error":
                        self.pending_control_results[request_id] = Exception(
                            response.get("error", "Unknown error")
                        )
                    else:
                        self.pending_control_results[request_id] = response
                    event.set()     # ← 唤醒等待的 _send_control_request
                continue

            # ──── 路由 2：CLI 发来控制请求 ────
            elif msg_type == "control_request":
                request: SDKControlRequest = message
                if self._tg:
                    self._tg.start_soon(self._handle_control_request, request)
                continue

            # ──── 路由 3：取消请求（TODO） ────
            elif msg_type == "control_cancel_request":
                continue

            # ──── 路由 4：普通消息 → 用户流 ────
            if msg_type == "result":
                self._first_result_event.set()

            await self._message_send.send(message)

    except anyio.get_cancelled_exc_class():
        raise  # 取消是正常行为
    except Exception as e:
        # 错误处理：唤醒所有等待的控制请求
        for request_id, event in list(self.pending_control_responses.items()):
            if request_id not in self.pending_control_results:
                self.pending_control_results[request_id] = e
                event.set()
        await self._message_send.send({"type": "error", "error": str(e)})
    finally:
        self._first_result_event.set()     # 解除可能的等待
        await self._message_send.send({"type": "end"})  # 结束信号
```

**路由决策图**：

```
stdout 消息
  │
  ├── type == "control_response"
  │     └── 找到 pending request → 填结果 → event.set()
  │
  ├── type == "control_request"
  │     └── 启动新协程 → _handle_control_request()
  │
  ├── type == "control_cancel_request"
  │     └── TODO（当前跳过）
  │
  └── 其他（user/assistant/system/result/stream_event/...）
        ├── type == "result" → _first_result_event.set()
        └── → message_stream（用户消费）
```

> **control_request 用 start_soon**：因为处理可能涉及 I/O（调用 Python hook 函数），
> 不能阻塞消息读取循环。每个请求在独立协程中处理。

---

## 发送控制请求 — _send_control_request()

源码：`_internal/query.py:347-392`

```python
async def _send_control_request(self, request, timeout=60.0):
    if not self.is_streaming_mode:
        raise Exception("Control requests require streaming mode")

    # 1. 生成唯一 request_id
    self._request_counter += 1
    request_id = f"req_{self._request_counter}_{os.urandom(4).hex()}"

    # 2. 注册等待事件
    event = anyio.Event()
    self.pending_control_responses[request_id] = event

    # 3. 构建并发送请求
    control_request = {
        "type": "control_request",
        "request_id": request_id,
        "request": request,
    }
    await self.transport.write(json.dumps(control_request) + "\n")

    # 4. 等待响应（带超时）
    try:
        with anyio.fail_after(timeout):
            await event.wait()

        result = self.pending_control_results.pop(request_id)
        self.pending_control_responses.pop(request_id, None)

        if isinstance(result, Exception):
            raise result

        response_data = result.get("response", {})
        return response_data if isinstance(response_data, dict) else {}
    except TimeoutError as e:
        self.pending_control_responses.pop(request_id, None)
        self.pending_control_results.pop(request_id, None)
        raise Exception(f"Control request timeout: {request.get('subtype')}") from e
```

**请求-响应匹配机制**：

```
SDK:   send({request_id: "req_1_abc", request: {subtype: "initialize"}})
       ↓ stdin
CLI:   处理...
       ↓ stdout
SDK:   recv({type: "control_response", response: {request_id: "req_1_abc", ...}})
       → pending_control_responses["req_1_abc"].set()
       → _send_control_request 中的 await event.wait() 返回
```

> **request_id 格式**：`req_{counter}_{random_hex}`。计数器保证递增，随机后缀防止重放。

---

## 处理 CLI 发来的控制请求

### _handle_control_request() — 三种 subtype

源码：`_internal/query.py:236-345`

```python
async def _handle_control_request(self, request: SDKControlRequest):
    request_id = request["request_id"]
    request_data = request["request"]
    subtype = request_data["subtype"]

    try:
        response_data = {}

        if subtype == "can_use_tool":
            # ──── 工具权限回调 ────
            ...

        elif subtype == "hook_callback":
            # ──── Hook 回调 ────
            ...

        elif subtype == "mcp_message":
            # ──── SDK MCP Server 消息 ────
            ...

        else:
            raise Exception(f"Unsupported subtype: {subtype}")

        # 发送成功响应
        success_response = {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": request_id,
                "response": response_data,
            },
        }
        await self.transport.write(json.dumps(success_response) + "\n")

    except Exception as e:
        # 发送错误响应
        error_response = {
            "type": "control_response",
            "response": {
                "subtype": "error",
                "request_id": request_id,
                "error": str(e),
            },
        }
        await self.transport.write(json.dumps(error_response) + "\n")
```

### subtype: "can_use_tool" — 工具权限回调

```python
if subtype == "can_use_tool":
    permission_request = request_data
    original_input = permission_request["input"]

    if not self.can_use_tool:
        raise Exception("canUseTool callback is not provided")

    context = ToolPermissionContext(
        signal=None,
        suggestions=permission_request.get("permission_suggestions", []) or [],
    )

    # 调用用户提供的 Python 回调
    response = await self.can_use_tool(
        permission_request["tool_name"],    # "Bash"
        permission_request["input"],        # {"command": "rm -rf /"}
        context,
    )

    # 转换为控制协议格式
    if isinstance(response, PermissionResultAllow):
        response_data = {
            "behavior": "allow",
            "updatedInput": response.updated_input or original_input,
        }
        if response.updated_permissions is not None:
            response_data["updatedPermissions"] = [
                p.to_dict() for p in response.updated_permissions
            ]
    elif isinstance(response, PermissionResultDeny):
        response_data = {
            "behavior": "deny",
            "message": response.message,
        }
        if response.interrupt:
            response_data["interrupt"] = True
```

**数据流示例**：
```
CLI:    "我想执行 Bash(rm -rf /tmp/test)，可以吗？"
        → {subtype: "can_use_tool", tool_name: "Bash", input: {command: "rm -rf /tmp/test"}}

SDK:    调用 user_callback("Bash", {command: "rm -rf /tmp/test"}, context)
        → 用户逻辑判断 → PermissionResultAllow()

SDK:    → {behavior: "allow", updatedInput: {command: "rm -rf /tmp/test"}}

CLI:    收到允许 → 执行 Bash
```

> **updatedInput 的能力**：用户可以在允许的同时**修改工具输入**。
> 比如把 `rm -rf /` 改成 `rm -rf /tmp/safe-dir`。

### subtype: "hook_callback" — Hook 回调

```python
elif subtype == "hook_callback":
    callback_id = request_data["callback_id"]
    callback = self.hook_callbacks.get(callback_id)
    if not callback:
        raise Exception(f"No hook callback for ID: {callback_id}")

    hook_output = await callback(
        request_data.get("input"),         # Hook 事件数据
        request_data.get("tool_use_id"),   # 可选的 tool_use_id
        {"signal": None},                  # HookContext
    )
    # 转换字段名：async_ → async, continue_ → continue
    response_data = _convert_hook_output_for_cli(hook_output)
```

### subtype: "mcp_message" — SDK MCP 桥接

```python
elif subtype == "mcp_message":
    server_name = request_data.get("server_name")
    mcp_message = request_data.get("message")
    mcp_response = await self._handle_sdk_mcp_request(server_name, mcp_message)
    response_data = {"mcp_response": mcp_response}
```

详见第 06 章。

---

## 初始化握手 — initialize()

源码：`_internal/query.py:119-163`

```python
async def initialize(self):
    # 1. 构建 hooks 配置
    hooks_config = {}
    if self.hooks:
        for event, matchers in self.hooks.items():
            hooks_config[event] = []
            for matcher in matchers:
                # 为每个回调生成唯一 ID
                callback_ids = []
                for callback in matcher.get("hooks", []):
                    callback_id = f"hook_{self.next_callback_id}"
                    self.next_callback_id += 1
                    self.hook_callbacks[callback_id] = callback  # 保存回调
                    callback_ids.append(callback_id)

                hook_matcher_config = {
                    "matcher": matcher.get("matcher"),
                    "hookCallbackIds": callback_ids,
                }

    # 2. 发送 initialize 请求
    request = {
        "subtype": "initialize",
        "hooks": hooks_config if hooks_config else None,
    }
    if self._agents:
        request["agents"] = self._agents

    # 3. 等待响应（使用初始化超时）
    response = await self._send_control_request(request, timeout=self._initialize_timeout)
    self._initialized = True
    self._initialization_result = response
    return response
```

> **initialize 超时**：默认 60 秒，因为 CLI 可能需要启动多个 MCP servers。
> 可通过 `CLAUDE_CODE_STREAM_CLOSE_TIMEOUT` 环境变量调整。

---

## 便捷方法 — 控制 CLI 行为

### interrupt() — 中断执行

```python
async def interrupt(self):
    await self._send_control_request({"subtype": "interrupt"})
```

### set_permission_mode() — 运行时切换权限

```python
async def set_permission_mode(self, mode):
    await self._send_control_request({
        "subtype": "set_permission_mode",
        "mode": mode,
    })
```

### set_model() — 运行时切换模型

```python
async def set_model(self, model):
    await self._send_control_request({
        "subtype": "set_model",
        "model": model,
    })
```

### get_mcp_status() — 查询 MCP 状态

```python
async def get_mcp_status(self):
    return await self._send_control_request({"subtype": "mcp_status"})
```

### reconnect_mcp_server() / toggle_mcp_server() — MCP 服务器管理

```python
async def reconnect_mcp_server(self, server_name):
    await self._send_control_request({
        "subtype": "mcp_reconnect",
        "serverName": server_name,
    })

async def toggle_mcp_server(self, server_name, enabled):
    await self._send_control_request({
        "subtype": "mcp_toggle",
        "serverName": server_name,
        "enabled": enabled,
    })
```

---

## 消息消费

### receive_messages() — 用户侧的消息迭代器

源码：`_internal/query.py:648-657`

```python
async def receive_messages(self):
    async for message in self._message_receive:
        if message.get("type") == "end":
            break
        elif message.get("type") == "error":
            raise Exception(message.get("error", "Unknown error"))
        yield message
```

> **终止信号**：`_read_messages` 在结束时发送 `{type: "end"}`，
> `receive_messages` 收到后退出迭代。错误消息直接抛异常。

---

## 流式输入 — stream_input()

源码：`_internal/query.py:632-646`

```python
async def stream_input(self, stream):
    try:
        async for message in stream:
            if self._closed:
                break
            await self.transport.write(json.dumps(message) + "\n")
        # 所有输入发完后，等待 result 再关 stdin
        await self.wait_for_result_and_end_input()
    except Exception as e:
        logger.debug(f"Error streaming input: {e}")
```

这个方法用于 `ClaudeSDKClient` 的 `AsyncIterable` prompt 模式，
在后台任务中持续将用户消息发送给 CLI。

---

## 关闭流程

```python
async def close(self):
    self._closed = True          # 停止消息路由
    if self._tg:
        self._tg.cancel_scope.cancel()      # 取消后台读取任务
        with suppress(CancelledError):
            await self._tg.__aexit__(...)    # 等待完成
    await self.transport.close()             # 关闭子进程
```

---

## 设计洞察

### 1. 控制协议是双向的

与大多数 SDK（只有 client → server 请求）不同，Claude SDK 的控制协议是真正双向的：

```
SDK → CLI:  initialize, interrupt, set_model, ...
CLI → SDK:  can_use_tool, hook_callback, mcp_message
```

这种设计让 CLI 可以在执行过程中"回调" SDK，实现：
- Python 侧的工具权限控制
- Python 侧的 Hook 逻辑
- Python 进程内的 MCP 工具执行

### 2. Event-based 请求匹配

`_send_control_request` 使用 `anyio.Event` 做同步等待：
- 发送请求时创建 Event，注册到 `pending_control_responses`
- `_read_messages` 收到响应后 `event.set()`
- 发送方 `await event.wait()` 被唤醒

这比 callback 方式更简洁，也比 Future/Promise 更适合 anyio 的编程模型。

### 3. 控制请求处理的并发安全

每个来自 CLI 的 control_request 都在独立协程中处理（`start_soon`）。
这意味着多个 hook 回调可以并发执行。
但 `transport.write` 有锁保护，所以响应写入不会交错。

### 4. memory_object_stream 的背压

消息流使用 `max_buffer_size=100`。如果用户消费太慢，
`_read_messages` 在 `await self._message_send.send(message)` 时会阻塞，
形成自然的背压。这防止了内存无限增长。
