# 02 - Transport 层：子进程管理与 I/O

> Transport 是 SDK 与 CLI 之间的"管道工"。
> 它负责启动子进程、读写 stdin/stdout、处理 JSON 缓冲和生命周期管理。
> 本文逐行走读 Transport 抽象和 SubprocessCLITransport 实现。

---

## Transport 抽象接口

源码：`_internal/transport/__init__.py:8-66`

```python
class Transport(ABC):
    @abstractmethod
    async def connect(self) -> None:
        """启动连接（subprocess 启动进程，network 建立连接）"""

    @abstractmethod
    async def write(self, data: str) -> None:
        """写入原始数据（通常是 JSON + 换行符）"""

    @abstractmethod
    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """读取并解析消息"""

    @abstractmethod
    async def close(self) -> None:
        """关闭连接并清理资源"""

    @abstractmethod
    def is_ready(self) -> bool:
        """检查是否可以通信"""

    @abstractmethod
    async def end_input(self) -> None:
        """结束输入流（关闭 stdin）"""
```

> **设计意图**：Transport 是一个抽象层，虽然目前只有 SubprocessCLITransport 一个实现，
> 但接口已经为未来的 network transport（远程 Claude Code）做好了准备。
> 文档明确说"This internal API is exposed for custom transport implementations"。

---

## SubprocessCLITransport — 核心实现

### 构造函数

源码：`_internal/transport/subprocess_cli.py:36-62`

```python
class SubprocessCLITransport(Transport):
    def __init__(self, prompt, options):
        self._prompt = prompt
        self._is_streaming = True           # 始终 True
        self._options = options
        self._cli_path = str(options.cli_path) if options.cli_path else self._find_cli()
        self._cwd = str(options.cwd) if options.cwd else None
        self._process: Process | None = None
        self._stdout_stream: TextReceiveStream | None = None
        self._stdin_stream: TextSendStream | None = None
        self._stderr_stream: TextReceiveStream | None = None
        self._ready = False
        self._exit_error: Exception | None = None
        self._max_buffer_size = options.max_buffer_size or 1024 * 1024  # 1MB
        self._write_lock: anyio.Lock = anyio.Lock()
```

**关键字段**：
- `_write_lock`：防止并发写入 stdin 导致 JSON 交错
- `_exit_error`：记录进程退出错误，后续写入时直接抛出
- `_max_buffer_size`：JSON 缓冲区上限，防止内存泄漏

---

## CLI 查找机制

### _find_cli() — 四步查找

源码：`_internal/transport/subprocess_cli.py:64-95`

```
查找顺序：
1. _find_bundled_cli()  → SDK 包内 _bundled/claude
2. shutil.which("claude")  → 系统 PATH
3. 硬编码路径列表：
   ~/.npm-global/bin/claude
   /usr/local/bin/claude
   ~/.local/bin/claude
   ~/node_modules/.bin/claude
   ~/.yarn/bin/claude
   ~/.claude/local/claude
4. 抛出 CLINotFoundError（附带安装指引）
```

### _find_bundled_cli() — 捆绑 CLI

源码：`_internal/transport/subprocess_cli.py:97-110`

```python
def _find_bundled_cli(self):
    cli_name = "claude.exe" if platform.system() == "Windows" else "claude"
    bundled_path = Path(__file__).parent.parent.parent / "_bundled" / cli_name
    if bundled_path.exists() and bundled_path.is_file():
        return str(bundled_path)
    return None
```

路径计算：`subprocess_cli.py` 位于 `_internal/transport/`，向上三级到 `claude_agent_sdk/`，
然后找 `_bundled/claude`。

### 版本检查

源码：`_internal/transport/subprocess_cli.py:595-633`

```python
MINIMUM_CLAUDE_CODE_VERSION = "2.0.0"

async def _check_claude_version(self):
    with anyio.fail_after(2):  # 2 秒超时
        version_process = await anyio.open_process([self._cli_path, "-v"], ...)
        stdout = await version_process.stdout.receive()
        version = re.match(r"([0-9]+\.[0-9]+\.[0-9]+)", stdout.decode())
        if version_parts < min_parts:
            logger.warning(f"Warning: Claude Code version {version} is unsupported...")
```

> **只 warning 不 raise**：低版本 CLI 仍然可以用，只是某些功能可能不正常。
> `CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK` 环境变量可以跳过检查。

---

## 命令构建 — ClaudeAgentOptions → CLI 参数

### _build_command() 完整映射表

源码：`_internal/transport/subprocess_cli.py:166-333`

| Options 字段 | CLI 参数 | 说明 |
|-------------|---------|------|
| `system_prompt` (str) | `--system-prompt "..."` | 系统提示词 |
| `system_prompt` (None) | `--system-prompt ""` | 显式清空 |
| `system_prompt` (preset+append) | `--append-system-prompt "..."` | 追加到默认提示词 |
| `tools` (list) | `--tools "tool1,tool2"` | 基础工具集 |
| `tools` (preset) | `--tools default` | 预设工具集 |
| `allowed_tools` | `--allowedTools "tool1,tool2"` | 允许的额外工具 |
| `max_turns` | `--max-turns N` | 最大轮次 |
| `max_budget_usd` | `--max-budget-usd N` | 最大预算 |
| `disallowed_tools` | `--disallowedTools "..."` | 禁用的工具 |
| `model` | `--model "..."` | 模型选择 |
| `fallback_model` | `--fallback-model "..."` | 备用模型 |
| `betas` | `--betas "beta1,beta2"` | Beta 功能 |
| `permission_prompt_tool_name` | `--permission-prompt-tool "..."` | 权限回调方式 |
| `permission_mode` | `--permission-mode "..."` | 权限模式 |
| `continue_conversation` | `--continue` | 继续上次对话 |
| `resume` | `--resume "session_id"` | 恢复指定会话 |
| `settings` + `sandbox` | `--settings "..."` | 合并后的设置 JSON |
| `add_dirs` | `--add-dir "path"` (多次) | 额外工作目录 |
| `mcp_servers` | `--mcp-config "..."` | MCP 服务器配置 |
| `include_partial_messages` | `--include-partial-messages` | 流式部分消息 |
| `fork_session` | `--fork-session` | 分叉会话 |
| `setting_sources` | `--setting-sources "user,project"` | 设置来源 |
| `plugins` | `--plugin-dir "path"` (多次) | 插件目录 |
| `thinking` | `--max-thinking-tokens N` | 思考 token 预算 |
| `effort` | `--effort "low/medium/high/max"` | 思考深度 |
| `output_format` | `--json-schema "..."` | 结构化输出 schema |
| `extra_args` | 直接映射为 `--flag value` | 未来 CLI 参数 |

### thinking 配置的解析逻辑

```python
# thinking 优先于废弃的 max_thinking_tokens
resolved = self._options.max_thinking_tokens
if self._options.thinking is not None:
    t = self._options.thinking
    if t["type"] == "adaptive":
        if resolved is None:
            resolved = 32_000           # adaptive 默认 32K
    elif t["type"] == "enabled":
        resolved = t["budget_tokens"]   # 用户指定
    elif t["type"] == "disabled":
        resolved = 0                    # 禁用思考
```

### settings 与 sandbox 的合并

源码：`_internal/transport/subprocess_cli.py:112-164`

```python
def _build_settings_value(self):
    # 只有 settings 路径，没有 sandbox → 直接传路径
    if has_settings and not has_sandbox:
        return self._options.settings

    # 有 sandbox → 必须合并为 JSON
    settings_obj = {}
    if has_settings:
        # settings 可能是 JSON 字符串或文件路径
        if settings_str.startswith("{"):
            settings_obj = json.loads(settings_str)
        else:
            settings_obj = json.load(open(settings_str))

    settings_obj["sandbox"] = self._options.sandbox
    return json.dumps(settings_obj)
```

> **设计洞察**：`settings` 支持三种格式：JSON 字符串、文件路径、None。
> 当需要与 `sandbox` 合并时，统一转为 JSON 字符串。

### MCP servers 的特殊处理

```python
if isinstance(self._options.mcp_servers, dict):
    servers_for_cli = {}
    for name, config in self._options.mcp_servers.items():
        if config.get("type") == "sdk":
            # SDK servers：剥离 instance 字段（不可序列化）
            sdk_config = {k: v for k, v in config.items() if k != "instance"}
            servers_for_cli[name] = sdk_config
        else:
            # 外部 servers：原样传递
            servers_for_cli[name] = config
    cmd.extend(["--mcp-config", json.dumps({"mcpServers": servers_for_cli})])
```

> SDK MCP Server 的 `instance` 字段是一个 Python MCP Server 对象，不能序列化到命令行。
> 所以传给 CLI 时剥离 instance，让 CLI 知道有这个 server 存在，
> 但实际的工具调用通过控制协议回调 SDK 处理。

---

## 写入机制

### write() — 带锁的原子写入

源码：`_internal/transport/subprocess_cli.py:489-513`

```python
async def write(self, data: str):
    async with self._write_lock:
        # 锁内检查所有状态，防止 TOCTOU
        if not self._ready or not self._stdin_stream:
            raise CLIConnectionError("Not ready")

        if self._process and self._process.returncode is not None:
            raise CLIConnectionError(f"Process terminated (exit: {self._process.returncode})")

        if self._exit_error:
            raise CLIConnectionError(f"Process error: {self._exit_error}")

        try:
            await self._stdin_stream.send(data)
        except Exception as e:
            self._ready = False
            self._exit_error = CLIConnectionError(f"Write failed: {e}")
            raise self._exit_error from e
```

> **为什么需要锁？** 多个协程可能并发写入 stdin（比如 Query 发 control_request 的同时，
> stream_input 在发送用户消息）。锁确保每条 JSON 消息是原子的。

### end_input() — 关闭 stdin

```python
async def end_input(self):
    async with self._write_lock:
        if self._stdin_stream:
            await self._stdin_stream.aclose()
            self._stdin_stream = None
```

---

## 读取机制 — JSON 缓冲

### _read_messages_impl() — 投机式 JSON 解析

源码：`_internal/transport/subprocess_cli.py:527-578`

```python
async def _read_messages_impl(self):
    json_buffer = ""

    async for line in self._stdout_stream:
        line_str = line.strip()
        if not line_str:
            continue

        # TextReceiveStream 可能在一个 yield 中返回多行
        json_lines = line_str.split("\n")

        for json_line in json_lines:
            json_line = json_line.strip()
            if not json_line:
                continue

            # 累积到缓冲区
            json_buffer += json_line

            # 防内存泄漏
            if len(json_buffer) > self._max_buffer_size:
                json_buffer = ""
                raise SDKJSONDecodeError(f"Buffer exceeded {self._max_buffer_size}")

            # 投机式解析
            try:
                data = json.loads(json_buffer)
                json_buffer = ""  # 成功！清空缓冲
                yield data
            except json.JSONDecodeError:
                continue  # 不完整，继续累积
```

**投机式解析的工作原理**：

```
收到: '{"type":"assis'     → json_buffer = '{"type":"assis'     → 解析失败，继续
收到: 'tant","message":'   → json_buffer = '{"type":"assistant","message":'  → 失败，继续
收到: '{"content":[]}}'    → json_buffer = '{"type":"assistant","message":{"content":[]}}' → 成功！yield
```

> **为什么不用换行符分隔？** 因为 `TextReceiveStream` 不保证按行返回。
> 它可能在任意字节边界切割，甚至在一个 chunk 内包含多条完整 JSON。
> 投机式解析是最稳健的方案。

### 进程退出处理

```python
# stdout 读完后检查退出码
returncode = await self._process.wait()

if returncode is not None and returncode != 0:
    self._exit_error = ProcessError(
        f"Command failed with exit code {returncode}",
        exit_code=returncode,
    )
    raise self._exit_error
```

---

## 关闭机制 — 优雅退出

### close() — 三阶段关闭

源码：`_internal/transport/subprocess_cli.py:442-487`

```python
async def close(self):
    # 阶段 1：关闭 stderr 任务组
    if self._stderr_task_group:
        self._stderr_task_group.cancel_scope.cancel()
        await self._stderr_task_group.__aexit__(...)

    # 阶段 2：关闭 stdin（带锁）
    async with self._write_lock:
        self._ready = False      # 锁内设置，防止 TOCTOU
        if self._stdin_stream:
            await self._stdin_stream.aclose()

    # 阶段 3：等待子进程优雅退出
    if self._process.returncode is None:
        try:
            with anyio.fail_after(5):      # 5 秒优雅期
                await self._process.wait()
        except TimeoutError:
            self._process.terminate()      # 超时强制终止
            await self._process.wait()
```

> **5 秒优雅期的必要性**：CLI 收到 stdin EOF 后需要将 session 写入 JSONL 文件。
> 如果立即 SIGTERM，可能丢失最后的 assistant 消息。
> 这个 bug（#625）曾导致实际丢失数据，修复后增加了这个等待。

---

## stderr 处理

### _handle_stderr() — 可选调试输出

源码：`_internal/transport/subprocess_cli.py:414-440`

```python
async def _handle_stderr(self):
    async for line in self._stderr_stream:
        line_str = line.rstrip()
        if not line_str:
            continue

        # 优先使用新的 callback API
        if self._options.stderr:
            self._options.stderr(line_str)
        # 向后兼容：debug_stderr 文件对象
        elif "debug-to-stderr" in self._options.extra_args:
            self._options.debug_stderr.write(line_str + "\n")
```

> **两种 stderr 处理方式**：
> 1. `options.stderr`：回调函数（推荐）
> 2. `options.debug_stderr`：文件对象（废弃，向后兼容）
>
> stderr 只在 `options.stderr` 非空或 `extra_args` 包含 `debug-to-stderr` 时才 pipe。

---

## 设计洞察

### 1. 为什么用子进程而不是 HTTP？

Claude Code CLI 不仅是一个 API 客户端——它是一个完整的 Agent 执行环境：
- 文件系统访问（Read/Write/Edit）
- Shell 执行（Bash）
- Git 操作
- MCP Server 管理
- Session 持久化
- 权限控制

把这些都重新实现在 Python SDK 里不现实。通过子进程复用 CLI 的全部能力，SDK 只需要做消息收发。

### 2. anyio 而非 asyncio

SDK 使用 anyio 而非 asyncio，这意味着它可以在 asyncio 和 trio 两种异步运行时下工作。但有一个限制：`ClaudeSDKClient` 不能跨不同的异步上下文使用（因为内部的 task group 绑定了创建时的上下文）。

### 3. 写入锁的必要性

```
不加锁时的竞态：
  协程 A: stdin.send('{"type":"control_request",...}\n')
  协程 B: stdin.send('{"type":"user",...}\n')

  可能交错为：
  '{"type":"control_re{"type":"user",...}\nquest",...}\n'
  → CLI 收到损坏的 JSON → 崩溃
```

### 4. JSON 缓冲的权衡

投机式解析比基于分隔符的方案更稳健，但代价是：
- 每次收到数据都尝试 `json.loads()`（成功前都是浪费）
- 需要 `_max_buffer_size` 防止内存泄漏
- 嵌套 JSON 中的 `}` 不会导致误解析（因为 `json.loads` 验证完整性）
