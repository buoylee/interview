# 01 - Subagent 心智模型

> 先不要陷进文件名。Claude Code 里的 local subagent 最好先理解成：同一 Node.js 进程里的另一个 `query()` 循环。

源码根目录：`/Users/buoy/Development/gitrepo/Claude-Code-true`

## 一句话结论

```text
subagent 不是独立 agent server。
subagent 是被 Agent tool 启动的另一个 query() loop。

它和主 agent 的区别不是 runtime 本质，而是运行时上下文：
agentId、agentType、ToolUseContext、messages、tools、abortController、sidechain transcript。
```

## 最小模型

主 agent 的循环可以简化成：

```text
query(mainMessages, mainToolUseContext)
  |
  |-- callModel()
  |-- 收 assistant message
  |-- 如果有 tool_use，执行工具
  |-- 把 tool_result 作为 user message 回填
  |-- 继续下一轮 callModel()
```

subagent 也一样：

```text
query(subagentMessages, subagentToolUseContext)
  |
  |-- callModel()
  |-- tool_use / tool_result
  |-- 写 sidechain transcript
  |-- 直到完成、失败、被 kill 或到达 maxTurns
```

所以更准确的图是：

```text
main query()
  |
  |-- tool_use: Agent(...)
        |
        v
      runAgent()
        |
        v
      subagent query()
```

`src/tools/AgentTool/runAgent.ts` 中的关键循环：

```ts
for await (const message of query({
  messages: initialMessages,
  systemPrompt: agentSystemPrompt,
  userContext: resolvedUserContext,
  systemContext: resolvedSystemContext,
  canUseTool,
  toolUseContext: agentToolUseContext,
  querySource,
  maxTurns: maxTurns ?? agentDefinition.maxTurns,
})) {
  onQueryProgress?.()
  recordSidechainTranscript([message], agentId, lastRecordedUuid)
  yield message
}
```

这段代码是理解 subagent 的锚点：

```text
subagent 最终还是进入 query()。
```

## 主 agent 和 subagent 的差别

| 维度 | 主 agent | subagent |
|------|----------|----------|
| 核心循环 | `query()` | `query()` |
| 触发方式 | 用户输入、SDK 输入、queue 输入 | 主 agent 调用 `Agent` tool |
| 身份 | 通常没有 `agentId` | 有独立 `agentId` |
| 类型 | main session | `agentType`，如 `general-purpose`、`fork`、自定义 agent |
| messages | 主 session transcript | 子 agent prompt messages / forked messages |
| system prompt | 主 agent system prompt | selected agent 或 fork parent system prompt |
| tools | 主 agent 可用工具 | 过滤后工具，或 fork 时 exact tools |
| abort | 当前 turn 的 abortController | sync 可能共享，async 有独立 controller |
| transcript | 主 session JSONL | sidechain transcript |
| task state | 主 REPL/loading state | `AppState.tasks[agentId]` local_agent |
| 通信方式 | 用户输入、tool_result、attachments | `task-notification`、`pendingMessages`、output file |

## 三层协议栈

很多困惑来自“agent 之间是不是直接通信”。答案是：local subagent 之间没有直接 RPC。

更像下面这几层：

```text
LLM tool protocol
  tool_use / tool_result

Runtime message protocol
  QueuedCommand(mode, priority, agentId)
  <task-notification> XML-ish payload
  pendingMessages mailbox

Durable state protocol
  sidechain transcript
  task output file
  agent metadata
```

`Agent` tool 的启动返回，是 `tool_result`。

subagent 完成后的通知，是 `<task-notification>` 进入全局 queue。

给运行中 subagent 发消息，是 `pendingMessages` mailbox。

查询 subagent 输出，是 `TaskOutput` 或 output file / sidechain transcript。

所以它不是：

```text
main agent -> socket/RPC/MCP -> subagent
```

而是：

```text
main agent -> runtime tool/message/task layer -> subagent
```

## background 的真实含义

background 不是新进程，也不是 worker thread。

它是：

```text
同一个 Node.js 进程
同一个 event loop
同一个 heap
同一个 AppState root store
一个 detached async lifecycle
一个 LocalAgentTask 记录
一个独立 abortController
一个独立 sidechain transcript
```

关键词是 `void runWithAgentContext(...)`：

```text
启动 async lifecycle，但 Agent tool call 不等待它完成。
```

因此主 agent 拿到的是：

```text
Async agent launched successfully
```

subagent 则继续在后台跑自己的 `query()`。

## “直接通信”的误解

如果说“agent 直接通信”，容易让人误以为有下面这种结构：

```text
main agent process
  -> RPC request
subagent process
  -> RPC response
```

Claude Code local subagent 不是这样。

更准确的说法是：

```text
runtime-mediated communication
```

也就是通信由运行时中介完成：

- 模型通过 `Agent` tool 启动任务。
- runtime 注册 task、启动 background lifecycle。
- subagent 结束后 runtime 构造 `<task-notification>`。
- 主 agent 后续通过 queue drain 读到通知。
- 主 agent 需要继续 subagent 时，通过 `SendMessage` 写 mailbox。
- stopped subagent 通过 transcript + metadata 重建上下文。

## 快速判断题

| 问题 | 答案 |
|------|------|
| subagent 是新进程吗？ | local subagent 不是，是同进程 async lifecycle |
| subagent 有自己的模型调用吗？ | 有，它进入自己的 `query()`，会自己 `callModel()` |
| subagent 和主 agent 共用一个 messages 吗？ | 不直接共用，subagent 有自己的 messages / sidechain transcript |
| ESC 会杀 background subagent 吗？ | 通常不会，ESC 取消主 foreground turn |
| kill agents 会杀 background subagent 吗？ | 会，kill 它自己的 task abortController |
| 用户说“继续”会恢复旧 generator 吗？ | 不会，是新 turn 或从 transcript resume |
| agent 间通信是 MCP 吗？ | local subagent 通信不是 MCP |
| fork subagent 为什么 cache 友好？ | 它复用 system prompt、tools、messages prefix，把差异放到最后 directive |

## 阅读下一篇

下一篇看启动链路：[02 - Subagent 后台生命周期](./02-subagent-background-lifecycle.md)。
