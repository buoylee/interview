# Coding Agent 构建指南 — 学习版

> **定位:** 从零开始，用最少的依赖手撸一个 coding agent，目的是彻底理解原理。
> **约束:** 单一 SDK（Anthropic）、无框架、无抽象层、只处理 happy path。
> **不覆盖:** 多模型适配、流式输出、安全、成本优化、容错 → 这些在 production-guide.md 中。

---

## 一、核心概念速览

### Agent = LLM + 工具 + 循环

```
┌──────────────────────────────┐
│         Agent Loop           │
│   while not done:            │
│     think → act → observe    │
├──────────┬───────────────────┤
│ Tools    │ LLM API           │
│ (执行动作) │ (推理决策)         │
└──────────┴───────────────────┘
```

### Agent Loop (ReAct 模式)

```python
messages = [{"role": "system", "content": system_prompt}]

while True:
    user_input = input("> ")
    messages.append({"role": "user", "content": user_input})

    while True:  # agent 内层循环
        response = llm.chat(messages, tools=tools)
        messages.append(response)

        if response.has_tool_calls:
            for tool_call in response.tool_calls:
                result = execute_tool(tool_call)
                messages.append(tool_result(result))
        else:
            print(response.text)  # 没有工具调用 = 完成
            break
```

### Stop Condition（完成判断）

LLM 不调用工具，直接输出文本 = 它认为任务完成了。
不是硬编码的逻辑，而是 LLM 自己的决策。

### Function Calling 协议

```
你发: messages + tools（JSON Schema 格式）
LLM 返回两种情况:
  ① 文本回复 → 展示给用户，循环结束
  ② tool_use → 你执行工具，把结果拼回 messages，再发一轮
```

tool_result 的 role 是 `user`（从 LLM 视角看，工具结果是外部输入），
tool_use_id 必须和对应的 tool_use 的 id 匹配。

---

## 二、实现路线 (6 个 Phase)

### Phase 1: 最小可用 Agent — LLM + Bash

**一个能对话、能调用 Bash 的 CLI agent。一切的基础。**

#### 要实现

- CLI 交互循环
- 调用 Anthropic Messages API（带 tool use）
- 一个 Bash 工具
- Agent 内层循环

#### 依赖

```bash
pip install anthropic
```

#### Bash 工具定义

```python
bash_tool = {
    "name": "bash",
    "description": "执行 shell 命令并返回输出。用于运行程序、安装依赖、查看系统状态等。",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的 shell 命令"
            }
        },
        "required": ["command"]
    }
}
```

#### Bash 工具执行

```python
import subprocess

def execute_bash(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 30 seconds"
```

#### 验收标准

- "列出当前目录的文件" → agent 调用 `bash("ls")`
- "创建一个 hello.txt 写入 hello world" → 多步完成
- 多轮对话，记住上下文

#### 关键学习点

- Anthropic Messages API 的 tool use 请求/响应格式
- `tool_use` 和 `tool_result` 消息在 messages 数组中的拼接方式

---

### Phase 2: 内置工具系统

**把 Bash 万能工具拆成专用工具。**

#### 为什么要拆

1. 语义更明确 → LLM 调用准确率更高
2. 权限可控 → 读文件自动允许，bash 需确认
3. 结果可控 → 截断、加行号等

#### 工具列表

| 工具 | 功能 | 实现要点 |
|------|------|----------|
| `read_file` | 读取文件 | 带行号；支持 offset/limit |
| `write_file` | 创建/覆盖文件 | 简单 |
| `edit_file` | 编辑局部内容 | 用 Search & Replace 方案 |
| `grep` | 搜索文件内容 | 可调 ripgrep |
| `glob` | 按模式查找文件 | 简单 |
| `bash` | 执行命令 | 保留兜底 |

#### 工具调度器

```python
TOOLS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "grep": grep_search,
    "glob": glob_search,
    "bash": execute_bash,
}

def execute_tool(name: str, params: dict) -> str:
    handler = TOOLS.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return handler(**params)
    except Exception as e:
        return f"Tool error: {e}"
```

#### Edit 工具: 用 Search & Replace

```json
{
  "path": "src/main.py",
  "old_text": "要被替换的原始文本（精确匹配）",
  "new_text": "替换后的文本"
}
```

不依赖行号，LLM 容易用对。要求 old_text 在文件中唯一匹配。

#### Tool Description 的重要性

```python
# 差的
{"description": "读文件"}

# 好的
{"description": "读取指定路径的文件内容，返回带行号的文本。"
               "对于大文件，使用 offset 和 limit 参数分段读取。"
               "修改文件前必须先用此工具读取内容。"}
```

#### 验收标准

- "读一下 src/main.py" → 调用 `read_file` 而非 `bash("cat")`
- "把第 10 行的 foo 改成 bar" → 先 read_file 再 edit_file
- "找所有 TODO" → 调用 grep

---

### Phase 3: System Prompt 工程

**通过 system prompt 控制 agent 行为。**

Agent 的大部分"智能行为"是 system prompt 规定的，不是代码硬编码的。

```python
SYSTEM_PROMPT = """
你是一个命令行 coding agent，帮助用户完成软件工程任务。

## 行为规则
1. 修改文件前必须先 read_file 读取当前内容，禁止盲改
2. 优先使用专用工具而非 bash（用 read_file 而非 bash cat）
3. 每次改动尽量最小化，只改必要的部分
4. 不确定时询问用户，不要猜测

## 工作流程
1. 理解需求，必要时提问澄清
2. 探索相关代码（grep / read_file）
3. 制定方案
4. 执行修改（edit_file）
5. 回读验证
"""
```

调优方式: 根据 agent 实际行为反复迭代 —
agent 总用 bash cat → prompt 强调优先级；agent 不读就改 → 加"必须先读"。

---

### Phase 4: Context 管理

**让 agent 能处理长对话。**

#### 问题

messages 每轮增长，读几个文件就可能逼近 context 上限。

#### 策略（从简到复杂）

**1. 工具结果截断（必须做）:**

```python
def truncate_output(output: str, max_chars=10000) -> str:
    if len(output) > max_chars:
        return output[:max_chars] + f"\n\n... (截断，共 {len(output)} 字符)"
    return output
```

**2. 滑动窗口:**

```python
def trim_messages(messages):
    if len(messages) > 50:
        return [messages[0]] + messages[-50:]
    return messages
```

**3. LLM 摘要压缩 (Claude Code 的做法):**

```python
def maybe_compress(messages, max_tokens):
    if count_tokens(messages) < max_tokens * 0.8:
        return messages
    old = messages[1:-5]
    summary = llm.chat([...总结指令...])
    return [messages[0], summary_msg, *messages[-5:]]
```

#### 验收标准

- 20 轮以上不崩
- 读大文件后仍正常
- 压缩后仍记得关键上下文

---

### Phase 5: MCP 集成

**连接外部 MCP Server，动态加载工具。**

MCP = 标准化的工具连接协议。Agent 通过 JSON-RPC over stdio 和 MCP Server 通信。

```
Agent (MCP Client)  ←— JSON-RPC —→  MCP Server (子进程)
```

#### 通信流程

```
1. 启动子进程
2. initialize（握手）
3. tools/list（获取工具列表）
4. tools/call（调用工具）
```

#### 简易 MCP Client

```python
class MCPClient:
    def __init__(self, command):
        self.process = subprocess.Popen(
            command, stdin=PIPE, stdout=PIPE, stderr=PIPE
        )
        self._id = 0

    def _request(self, method, params=None):
        self._id += 1
        req = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        self.process.stdin.write((json.dumps(req) + "\n").encode())
        self.process.stdin.flush()
        return json.loads(self.process.stdout.readline())

    def initialize(self):
        return self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "my-agent", "version": "0.1.0"}
        })

    def list_tools(self):
        return self._request("tools/list").get("result", {}).get("tools", [])

    def call_tool(self, name, args):
        result = self._request("tools/call", {"name": name, "arguments": args})
        content = result.get("result", {}).get("content", [])
        return "\n".join(c.get("text", "") for c in content)
```

#### 集成到 Agent

```python
# 动态合并工具列表
all_tools = builtin_tools + [
    {"name": f"mcp__{server}__{t['name']}", **t}
    for server, client in mcp_clients.items()
    for t in client.list_tools()
]

# 执行时路由
def execute_tool(name, params):
    if name in BUILTIN: return BUILTIN[name](**params)
    if name in mcp_tools:
        client, real_name = mcp_tools[name]
        return client.call_tool(real_name, params)
```

#### 验收标准

- 连接一个现成 MCP Server，工具出现在列表中
- LLM 能调用 MCP 工具并拿到结果

---

### Phase 6: Skills 系统

**支持 `/commit`、`/simplify` 等快捷指令。**

Skill 就是预定义的 prompt 模板，用户输入 `/commit`，展开成详细 prompt 喂给 agent loop。

```python
SKILLS = {
    "commit": {
        "description": "生成 commit message 并提交",
        "prompt": "1. git diff --cached 查看改动\n2. 生成 commit message\n3. 用户确认后提交"
    },
    "simplify": {
        "description": "审查并简化代码",
        "prompt": "1. git diff 看改动\n2. 检查重复/过度抽象\n3. 直接修改"
    },
}

def handle_input(user_input):
    if user_input.startswith("/"):
        skill = SKILLS.get(user_input[1:].split()[0])
        if skill: return skill["prompt"]
    return user_input
```

---

## 三、完整链路示例: "修一个 Bug"

```
用户: 登录接口返回 500

Agent Think → grep("login|auth") → 找到 auth.py, user_service.py
Agent Think → read_file("auth.py") → 看到调 authenticate()
Agent Think → read_file("user_service.py") → 第 42 行明文比较 password
Agent Think → edit_file(old="user.password == password", new="verify_password(...)")
Agent Think → read_file 回读确认
Agent Think → bash("python -c 'import ...'") 编译通过
Agent → 输出总结，循环结束
```

---

## 四、这个版本的局限（生产版要解决的）

| 本版本 | 生产版 |
|--------|--------|
| 单一 SDK（Anthropic 硬编码） | 多模型适配层，支持任意 provider |
| 无流式输出（等完才显示） | 流式逐 token 展示 |
| 无错误处理（crash 就完了） | 重试、降级、循环检测 |
| 无权限控制 | 分级权限 + prompt injection 防御 |
| 无成本意识 | prompt caching + 预算控制 + 模型路由 |
| MCP 自己实现 JSON-RPC | 用 MCP SDK |
| 无可观测性 | 结构化日志、token 追踪 |

**→ 完成 Phase 1-6 后，阅读 `production-guide.md` 进入生产版。**

---

## 五、学习资源

| 资源 | 用途 |
|------|------|
| [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview) | Function calling API |
| [Anthropic Agent 设计指南](https://docs.anthropic.com/en/docs/build-with-claude/agentic) | 官方 Agent 最佳实践 |
| [MCP 官方规范](https://modelcontextprotocol.io/) | MCP 协议 |
| [ReAct 论文](https://arxiv.org/abs/2210.03629) | Agent Loop 理论基础 |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | 开源 coding agent 参考 |
