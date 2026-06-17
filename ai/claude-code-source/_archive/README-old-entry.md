# Old Top-Level README

> 这是新版目录重写前的旧版顶层 README，保留在 archive 中作为旧阅读入口和迁移素材。

# Claude Code 源码分析笔记

> 这里专门记录 Claude Code CLI 执行引擎的源码阅读笔记。
> 和 `ai/claude-agent-sdk/` 区分开：Claude Agent SDK 更像遥控器，负责启动 CLI 子进程、收发 JSONL、桥接 hook/MCP；Claude Code CLI 才是真正运行 agent loop、tool execution、subagent、session、permission、compaction 的引擎。

源码仓库：`/Users/buoy/Development/gitrepo/Claude-Code-true`

## 阅读目标

这组笔记主要回答这些问题：

- 主 agent 的核心 `query()` 循环怎么跑？
- tool calling 是如何调度、并发、返回 `tool_result` 的？
- `Agent` tool 如何启动 subagent？
- subagent 为什么能后台运行？它是不是新进程？
- 主 agent 和 subagent 如何通信？有没有 RPC/MCP/协议？
- ESC 取消主 agent 时，background subagent 为什么通常不停止？
- 用户说“继续”时，是恢复旧 call stack，还是开启新 turn？
- fork subagent 如何最大化 prompt cache 命中？
- `ToolUseContext` 里到底有什么，subagent 如何复制和隔离它？

## 章节

| 章节 | 主题 | 说明 |
|------|------|------|
| [01 - Subagent 心智模型](./01-subagent-mental-model.md) | 总览 | 先建立大图：subagent 不是新 runtime，而是另一个 `query()` loop |
| [02 - Subagent 后台生命周期](./02-subagent-background-lifecycle.md) | 启动与执行 | 从 `AgentTool.call()` 到 `registerAsyncAgent()`、`runAsyncAgentLifecycle()`、`runAgent()`、`query()` |
| [03 - Agent 间通信协议](./03-agent-communication-protocol.md) | 通信机制 | 解释 `tool_result`、`task-notification`、`commandQueue`、`pendingMessages`、sidechain transcript |
| [04 - 取消、继续与恢复](./04-cancel-resume-and-abort.md) | ESC / kill / continue | 为什么 ESC 通常不杀 background subagent，用户说“继续”到底发生什么 |
| [05 - Fork Subagent 与 Prompt Cache](./05-fork-subagent-prompt-cache.md) | 性能优化 | fork subagent 如何复用 prompt prefix，哪些条件影响 cache 命中 |

旧入口 [01-subagent-background-and-communication.md](./01-subagent-background-and-communication.md) 已改成迁移索引，避免旧链接失效。

## 总体心智模型

Claude Code CLI 可以先理解成三个嵌套层：

```text
REPL / SDK / non-interactive input
  |
  v
query() 主循环
  |
  |-- callModel()
  |-- 收 assistant message / tool_use
  |-- runTools() / StreamingToolExecutor
  |-- tool_result 作为 user message 回填
  |-- 循环直到停止
  |
  +-- Agent tool 可以再启动一个 runAgent()
        |
        v
      subagent query() 循环
```

最重要的一点：

```text
subagent 不是另一套 agent runtime。
subagent 本质上仍然是 query() 循环。

区别主要在：
  agentId / agentType
  ToolUseContext
  system prompt / messages
  available tools
  abortController
  sidechain transcript
  AppState task registry
```

## 和 Claude Agent SDK 笔记的边界

`ai/claude-agent-sdk/` 关注：

```text
Python SDK -> Claude Code CLI 子进程
stdin/stdout JSONL
control_request / control_response
SDK MCP Server
Session JSONL 读取
```

本目录关注：

```text
Claude Code CLI 内部
query loop
tool execution
AgentTool / subagent
ToolUseContext
message queue
local task registry
sidechain transcript
permission / abort / compaction
```

一句话：

```text
SDK 笔记讲“怎么驱动 Claude Code”。
本目录讲“Claude Code 自己怎么工作”。
```
