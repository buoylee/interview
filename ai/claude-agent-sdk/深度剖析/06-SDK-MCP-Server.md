# 06 - SDK MCP Server：进程内工具

> SDK MCP Server 让用户在 Python 进程内定义工具，Claude 可以直接调用。
> 这绕过了外部 MCP Server 的子进程开销，但实现上需要手动桥接 JSONRPC。
> 本文逐行分析 @tool 装饰器、create_sdk_mcp_server()、和 Query 中的 MCP 桥接。

---

## 与外部 MCP Server 的区别

```
外部 MCP Server（stdio/sse/http）：
  CLI ←→ [子进程/网络] ←→ MCP Server 进程
  · 独立进程
  · 通过 stdin/stdout 或 HTTP 通信
  · CLI 直接管理

SDK MCP Server（in-process）：
  CLI ←→ [控制协议] ←→ SDK ←→ Python 函数
  · 运行在 SDK 所在的 Python 进程内
  · 通过 control_request/control_response 通信
  · Query 类做 JSONRPC ↔ Python 的桥接
```

| | 外部 MCP Server | SDK MCP Server |
|---|---|---|
| 执行进程 | 独立进程 | Python SDK 进程 |
| 通信开销 | IPC（stdio/HTTP） | 控制协议（stdin/stdout） |
| 启动时间 | 需要启动子进程 | 零启动开销 |
| 状态访问 | 独立隔离 | 直接访问 Python 变量 |
| 调试 | 跨进程调试 | 同进程调试 |

---

## @tool 装饰器

源码：`__init__.py:111-175`

```python
def tool(
    name: str,
    description: str,
    input_schema: type | dict[str, Any],
    annotations: ToolAnnotations | None = None,
) -> Callable[[Callable], SdkMcpTool]:

    def decorator(handler):
        return SdkMcpTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            annotations=annotations,
        )

    return decorator
```

**使用方式**：

```python
@tool("get_weather", "查询天气", {"city": str})
async def get_weather(args):
    city = args["city"]
    return {"content": [{"type": "text", "text": f"{city}今天晴，25°C"}]}
```

**SdkMcpTool dataclass**：

```python
@dataclass
class SdkMcpTool(Generic[T]):
    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]
    annotations: ToolAnnotations | None = None
```

> **input_schema 的三种形式**：
> 1. `dict[str, type]` — 简单映射：`{"city": str, "unit": str}`
> 2. 已有的 JSON Schema dict — `{"type": "object", "properties": {...}}`
> 3. `type` — TypedDict 类（基础 schema 生成）

---

## create_sdk_mcp_server()

源码：`__init__.py:178-340`

这个函数把 `SdkMcpTool` 列表包装成一个 MCP Server 实例：

```python
def create_sdk_mcp_server(name, version="1.0.0", tools=None):
    from mcp.server import Server
    from mcp.types import Tool, TextContent, ImageContent

    server = Server(name, version=version)

    if tools:
        tool_map = {tool_def.name: tool_def for tool_def in tools}
```

### 注册 list_tools handler

```python
@server.list_tools()
async def list_tools():
    tool_list = []
    for tool_def in tools:
        # 转换 input_schema 到 JSON Schema 格式
        if isinstance(tool_def.input_schema, dict):
            if "type" in tool_def.input_schema and "properties" in tool_def.input_schema:
                schema = tool_def.input_schema  # 已经是 JSON Schema
            else:
                # 简单 dict 映射 → JSON Schema
                properties = {}
                for param_name, param_type in tool_def.input_schema.items():
                    if param_type is str:
                        properties[param_name] = {"type": "string"}
                    elif param_type is int:
                        properties[param_name] = {"type": "integer"}
                    elif param_type is float:
                        properties[param_name] = {"type": "number"}
                    elif param_type is bool:
                        properties[param_name] = {"type": "boolean"}
                    else:
                        properties[param_name] = {"type": "string"}  # 默认
                schema = {
                    "type": "object",
                    "properties": properties,
                    "required": list(properties.keys()),
                }
        else:
            schema = {"type": "object", "properties": {}}

        tool_list.append(Tool(
            name=tool_def.name,
            description=tool_def.description,
            inputSchema=schema,
            annotations=tool_def.annotations,
        ))
    return tool_list
```

**类型映射**：

| Python type | JSON Schema type |
|-------------|-----------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| 其他 | `"string"`（降级） |

### 注册 call_tool handler

```python
@server.call_tool()
async def call_tool(name, arguments):
    if name not in tool_map:
        raise ValueError(f"Tool '{name}' not found")

    tool_def = tool_map[name]
    result = await tool_def.handler(arguments)  # 调用 Python 函数

    # 转换返回值为 MCP 格式
    content = []
    if "content" in result:
        for item in result["content"]:
            if item.get("type") == "text":
                content.append(TextContent(type="text", text=item["text"]))
            if item.get("type") == "image":
                content.append(ImageContent(
                    type="image", data=item["data"], mimeType=item["mimeType"]
                ))
    return content  # MCP SDK 自动包装为 CallToolResult
```

### 返回 SDK 配置

```python
return McpSdkServerConfig(type="sdk", name=name, instance=server)
```

`McpSdkServerConfig` 是一个 TypedDict：
```python
class McpSdkServerConfig(TypedDict):
    type: Literal["sdk"]
    name: str
    instance: "McpServer"     # Python MCP Server 对象（不可序列化）
```

---

## Query 中的 MCP 桥接

### CLI 如何知道有 SDK MCP Server？

在 `SubprocessCLITransport._build_command()` 中：

```python
for name, config in self._options.mcp_servers.items():
    if config.get("type") == "sdk":
        # 剥离 instance 字段（不可序列化），传 type/name 给 CLI
        sdk_config = {k: v for k, v in config.items() if k != "instance"}
        servers_for_cli[name] = sdk_config
```

CLI 收到 `--mcp-config '{"mcpServers":{"weather":{"type":"sdk","name":"weather"}}}'`，
知道 `weather` 是一个 SDK MCP Server，工具调用需要通过控制协议路由。

### _handle_sdk_mcp_request() — JSONRPC 桥接

源码：`_internal/query.py:394-530`

这是整个 SDK MCP 实现的核心——手动路由 JSONRPC 方法到 MCP Server 对象：

```python
async def _handle_sdk_mcp_request(self, server_name, message):
    if server_name not in self.sdk_mcp_servers:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32601, "message": f"Server '{server_name}' not found"},
        }

    server = self.sdk_mcp_servers[server_name]
    method = message.get("method")
    params = message.get("params", {})
```

**支持的 JSONRPC 方法**：

#### 1. initialize — MCP 初始化

```python
if method == "initialize":
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": server.name,
                "version": server.version or "1.0.0",
            },
        },
    }
```

> **硬编码响应**：initialize 不需要真正调用 Server 对象，直接返回固定的 capabilities。

#### 2. tools/list — 列出工具

```python
elif method == "tools/list":
    request = ListToolsRequest(method=method)
    handler = server.request_handlers.get(ListToolsRequest)
    if handler:
        result = await handler(request)
        tools_data = []
        for tool in result.root.tools:
            tool_data = {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema.model_dump()
                    if hasattr(tool.inputSchema, "model_dump")
                    else tool.inputSchema,
            }
            if tool.annotations:
                tool_data["annotations"] = tool.annotations.model_dump(exclude_none=True)
            tools_data.append(tool_data)
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": {"tools": tools_data}}
```

#### 3. tools/call — 执行工具

```python
elif method == "tools/call":
    call_request = CallToolRequest(
        method=method,
        params=CallToolRequestParams(
            name=params.get("name"),
            arguments=params.get("arguments", {}),
        ),
    )
    handler = server.request_handlers.get(CallToolRequest)
    if handler:
        result = await handler(call_request)
        content = []
        for item in result.root.content:
            if hasattr(item, "text"):
                content.append({"type": "text", "text": item.text})
            elif hasattr(item, "data") and hasattr(item, "mimeType"):
                content.append({"type": "image", "data": item.data, "mimeType": item.mimeType})

        response_data = {"content": content}
        if hasattr(result.root, "is_error") and result.root.is_error:
            response_data["is_error"] = True
        return {"jsonrpc": "2.0", "id": message.get("id"), "result": response_data}
```

#### 4. notifications/initialized — 初始化完成通知

```python
elif method == "notifications/initialized":
    return {"jsonrpc": "2.0", "result": {}}
```

---

## 完整数据流：SDK MCP 工具调用

```
1. CLI 决定调用 get_weather 工具
   → 检查 server type == "sdk"
   → 通过控制协议发送 mcp_message

2. CLI → SDK (stdout):
   {
     "type": "control_request",
     "request_id": "cli_req_99",
     "request": {
       "subtype": "mcp_message",
       "server_name": "weather",
       "message": {
         "jsonrpc": "2.0",
         "id": "mcp_1",
         "method": "tools/call",
         "params": {
           "name": "get_weather",
           "arguments": {"city": "北京"}
         }
       }
     }
   }

3. SDK 处理：
   Query._handle_control_request()
   → subtype == "mcp_message"
   → _handle_sdk_mcp_request("weather", message)
   → server.request_handlers[CallToolRequest](request)
   → get_weather({"city": "北京"})
   → {"content": [{"type": "text", "text": "北京今天晴，25°C"}]}

4. SDK → CLI (stdin):
   {
     "type": "control_response",
     "response": {
       "subtype": "success",
       "request_id": "cli_req_99",
       "response": {
         "mcp_response": {
           "jsonrpc": "2.0",
           "id": "mcp_1",
           "result": {
             "content": [{"type": "text", "text": "北京今天晴，25°C"}]
           }
         }
       }
     }
   }

5. CLI 收到结果 → 喂回 Claude API → 生成最终回复
```

---

## 局限性

### 源码中的 TODO 注释

```python
# TODO: Python MCP SDK lacks the Transport abstraction that TypeScript has.
# TypeScript: server.connect(transport) allows custom transports
# Python: server.run(read_stream, write_stream) requires actual streams
#
# This forces us to manually route methods. When Python MCP adds Transport
# support, we can refactor to match the TypeScript approach.
```

**问题**：
- TypeScript MCP SDK 有 `Transport` 抽象，可以自定义通信方式
- Python MCP SDK 只有 `server.run(read_stream, write_stream)`，要求真正的 I/O stream
- SDK 不能把"控制协议消息"伪装成 I/O stream
- 所以只能手动路由每个 JSONRPC 方法

**后果**：
- 每当 MCP 协议增加新方法（如 resources、prompts），SDK 需要手动添加路由
- 代码在注释中说 "Add more methods here as MCP SDK adds them"

### 不支持 client → server 方向

SDK MCP Server 只支持 server 响应 client 请求（list_tools、call_tool），
不支持 server 主动向 client 推送（如 tools/changed 通知）。
这是因为控制协议是请求-响应模式，没有 server-initiated 推送机制。

---

## 与 OpenAI Agents SDK 的工具系统对比

| 维度 | OpenAI FunctionTool | Claude SDK MCP Tool |
|------|-------------------|-------------------|
| 定义方式 | `@function_tool` 装饰器 | `@tool` 装饰器 |
| 通信协议 | 直接 Python 调用 | MCP over 控制协议 |
| Schema 生成 | 从函数签名自动推断 | 手动定义 input_schema |
| 执行位置 | SDK 进程内 | SDK 进程内 |
| 与 LLM 交互 | SDK 内 `invoke_function_tool()` | CLI 通过控制协议回调 |
| 返回格式 | 任意 Python 对象 → str(result) | MCP content format |
| 错误处理 | `ToolCallError` → tool_call_output | `is_error: true` in content |

> **关键区别**：OpenAI 的工具是 SDK 原生概念，直接调用 Python 函数。
> Claude 的 SDK MCP 工具需要经过 MCP 协议封装 + 控制协议传输，
> 多了两层间接性，但换来了与 MCP 生态的兼容性。
