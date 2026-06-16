# 03 - Agent 间通信协议

> 这一篇专门解释“主 agent 和 subagent 到底怎么通信”。核心结论：Claude Code local subagent 之间没有直接 RPC/MCP/socket，而是 runtime-mediated communication。

源码根目录：`/Users/buoy/Development/gitrepo/Claude-Code-true`

核心文件：

| 文件 | 作用 |
|------|------|
| `src/tools/AgentTool/AgentTool.tsx` | 启动 subagent，返回 `async_launched` 或 `completed` tool result |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | task state、`pendingMessages`、`enqueueAgentNotification()` |
| `src/utils/messageQueueManager.ts` | 全局 `commandQueue`，保存 prompt / task-notification 等 queued commands |
| `src/types/textInputTypes.ts` | `QueuedCommand` 类型，包含 `mode`、`priority`、`agentId` |
| `src/query.ts` | drain queue，把 queued commands 转成 attachments |
| `src/utils/attachments.ts` | `getQueuedCommandAttachments()`、`getAgentPendingMessageAttachments()` |
| `src/tools/SendMessageTool/SendMessageTool.ts` | 给 running/stopped subagent 发消息 |
| `src/tools/TaskOutputTool/TaskOutputTool.tsx` | 读取 background task 输出 |

---

## 1. 先定义“通信”

如果把“直接通信”理解成：

```text
main agent process -> RPC/socket/MCP -> subagent process
```

那 Claude Code local subagent 不是直接通信。

更准确的说法：

```text
runtime-mediated communication
```

意思是：

```text
主 agent 和 subagent 不直接互相调用。
它们通过 Claude Code runtime 提供的工具结果、任务状态、全局队列、mailbox、transcript 文件进行信息交接。
```

---

## 2. 通信通道总表

| 场景 | 入口 | 通道/存储 | 送达时机 | 本质 |
|------|------|-----------|----------|------|
| 主 agent 启动 subagent | `Agent` tool | `tool_use -> tool_result` | 当前 tool round | LLM tool protocol |
| subagent 完成通知主 agent | `enqueueAgentNotification()` | global `commandQueue` + `<task-notification>` | 主 agent 下次 queue drain | runtime queue protocol |
| 主 agent 给 running subagent 发消息 | `SendMessage` | `AppState.tasks[agentId].pendingMessages` | subagent 下次 attachment collection | mailbox |
| 主 agent 查询 subagent 输出 | `TaskOutput` / output file | sidechain transcript / task result | 主动读取，可 block | durable output |
| stopped subagent 继续 | `resumeAgentBackground()` | sidechain transcript + metadata | 新 background run | transcript replay |
| subagent 身份识别 | `AsyncLocalStorage` | async context | 当前 async chain | attribution，不是通信 |

一句话：

```text
通信不是一条线，而是多条 runtime 通道。
```

---

## 3. 通道一：启动 subagent 的 tool_use / tool_result

主 agent 启动 subagent，本质是模型调用工具：

```text
assistant:
  tool_use Agent({
    description,
    prompt,
    subagent_type,
    run_in_background
  })
```

`AgentTool.call()` 执行后，如果是 async/background，会返回一个 `tool_result`：

```text
Async agent launched successfully.
agentId: <id>
The agent is working in the background.
You will be notified automatically when it completes.
```

这一步的通信语义是：

```text
主 agent -> runtime: 我要启动一个 Agent tool。
runtime -> 主 agent: 已启动，agentId 是 X，后续会通知。
```

注意：这时 subagent 还没把最终结果给主 agent。

它只是被启动了。

---

## 4. 通道二：完成通知 task-notification

background subagent 完成后，`runAsyncAgentLifecycle()` 会调用 `enqueueAgentNotification()`。

`enqueueAgentNotification()` 构造 XML-ish payload：

```xml
<task-notification>
  <task-id>...</task-id>
  <tool-use-id>...</tool-use-id>
  <output-file>...</output-file>
  <status>completed</status>
  <summary>Agent "..." completed</summary>
  <result>...</result>
  <usage>
    <total_tokens>...</total_tokens>
    <tool_uses>...</tool_uses>
    <duration_ms>...</duration_ms>
  </usage>
</task-notification>
```

然后写入全局 queue：

```ts
enqueuePendingNotification({
  value: message,
  mode: 'task-notification',
})
```

这是 subagent -> main agent 的主要完成通知。

链路：

```text
subagent query() 完成
  |
  |-- finalizeAgentTool()
  |-- completeAsyncAgent()
  |-- enqueueAgentNotification()
  |
  v
commandQueue.push({
  value: '<task-notification>...</task-notification>',
  mode: 'task-notification',
  priority: 'later'
})
  |
  v
主 agent 后续 drain queue
  |
  v
作为 user-role attachment 进入模型上下文
```

---

## 5. 全局 commandQueue 是轻量消息总线

`src/utils/messageQueueManager.ts` 中有一个 module-level queue：

```ts
const commandQueue: QueuedCommand[] = []
```

写入函数：

```ts
export function enqueue(command: QueuedCommand): void {
  commandQueue.push({ ...command, priority: command.priority ?? 'next' })
  notifySubscribers()
}

export function enqueuePendingNotification(command: QueuedCommand): void {
  commandQueue.push({ ...command, priority: command.priority ?? 'later' })
  notifySubscribers()
}
```

`QueuedCommand` 的关键字段：

```ts
export type QueuedCommand = {
  value: string | Array<ContentBlockParam>
  mode: 'bash' | 'prompt' | 'orphaned-permission' | 'task-notification'
  priority?: 'now' | 'next' | 'later'
  uuid?: UUID
  isMeta?: boolean
  origin?: MessageOrigin
  agentId?: AgentId
}
```

这里 `agentId` 是路由键：

```text
agentId === undefined
  给 main thread

agentId === 当前 subagent id
  给指定 subagent
```

---

## 6. query.ts 如何 drain queue 并隔离 main/subagent

`query.ts` 在工具执行之后，会检查 queue，把 queued commands 转成 attachments。

关键逻辑可以简化为：

```ts
const isMainThread =
  querySource.startsWith('repl_main_thread') || querySource === 'sdk'
const currentAgentId = toolUseContext.agentId

const queuedCommandsSnapshot = getCommandsByMaxPriority(...).filter(cmd => {
  if (isSlashCommand(cmd)) return false
  if (isMainThread) return cmd.agentId === undefined
  return cmd.mode === 'task-notification' && cmd.agentId === currentAgentId
})
```

含义：

```text
main thread 只 drain agentId undefined 的命令。
subagent 只 drain 发给自己的 task-notification。
普通用户 prompt 不会被 subagent 偷走。
```

这解决了一个重要问题：

```text
所有 agent 共享同一个 module-level commandQueue，但不会互相吃掉消息。
```

---

## 7. 通道三：SendMessage 给 running subagent 发消息

`SendMessage` 是主 agent 给某个 subagent 发消息的工具。

`src/tools/SendMessageTool/SendMessageTool.ts` 的核心逻辑：

```ts
if (isLocalAgentTask(task) && task.status === 'running') {
  queuePendingMessage(
    agentId,
    input.message,
    context.setAppStateForTasks ?? context.setAppState,
  )
  return {
    data: {
      success: true,
      message: `Message queued for delivery...`,
    },
  }
}
```

`queuePendingMessage()` 只是写入 task state：

```ts
export function queuePendingMessage(taskId, msg, setAppState): void {
  updateTaskState(taskId, setAppState, task => ({
    ...task,
    pendingMessages: [...task.pendingMessages, msg],
  }))
}
```

所以 SendMessage 并不直接打断 subagent 当前 API call。

它是 mailbox：

```text
主 agent SendMessage
  |
  v
AppState.tasks[agentId].pendingMessages.push(message)
  |
  v
subagent 下一次 attachment collection
  |
  v
drainPendingMessages()
  |
  v
queued_command attachment
  |
  v
subagent 模型读到消息
```

---

## 8. pendingMessages 如何进入 subagent 上下文

`src/utils/attachments.ts` 中有：

```ts
export function getAgentPendingMessageAttachments(
  toolUseContext: ToolUseContext,
): Attachment[] {
  const agentId = toolUseContext.agentId
  if (!agentId) return []

  const drained = drainPendingMessages(
    agentId,
    toolUseContext.getAppState,
    toolUseContext.setAppStateForTasks ?? toolUseContext.setAppState,
  )

  return drained.map(msg => ({
    type: 'queued_command' as const,
    prompt: msg,
    origin: { kind: 'coordinator' as const },
    isMeta: true,
  }))
}
```

这个 attachment 被 subagent 的 `query()` loop 在合适的时机加入上下文。

所以 delivery timing 是：

```text
不是实时 interrupt。
不是 websocket push。
是 subagent 下一次收集 attachments 时读取 mailbox。
```

---

## 9. 通道四：TaskOutput / output file / sidechain transcript

background agent 启动时，会初始化 output file symlink：

```ts
initTaskOutputAsSymlink(agentId, getAgentTranscriptPath(agentId))
```

`runAgent()` 会持续写 sidechain transcript：

```ts
recordSidechainTranscript(initialMessages, agentId)
recordSidechainTranscript([message], agentId, lastRecordedUuid)
```

`TaskOutput` 可以读取：

- 已完成 task 的 clean result。
- 运行中/完成后的 output file。
- 必要时 block 等 task 完成。

这条通道是 pull 模式：

```text
主 agent 主动用 TaskOutput 查询。
```

和 task-notification 的区别：

| 通道 | 模式 | 适合场景 |
|------|------|----------|
| `task-notification` | push 到 queue | subagent 完成后自动告诉主 agent |
| `TaskOutput` | pull 读取 | 主 agent 想主动查看进度或完整输出 |

---

## 10. stopped subagent 的通信：resume 是 transcript replay

如果目标 subagent 已经 stopped，`SendMessage` 会走 `resumeAgentBackground()`：

```text
SendMessage(to=agentId, message)
  |
  |-- task exists but stopped
  |-- resumeAgentBackground(agentId, prompt)
```

resume 的本质是：

```text
读取 sidechain transcript + metadata
恢复 messages / selectedAgent / contentReplacementState
追加新的 user message
重新 registerAsyncAgent()
重新 runAsyncAgentLifecycle()
```

所以这里也不是直接唤醒旧 runtime。

更准确：

```text
用 durable transcript 重新构造上下文，然后启动一个新的 background run。
```

---

## 11. MCP 在哪里？

local subagent 通信本身不是 MCP。

MCP 可能出现在工具调用层：

```text
agent -> mcp__server__tool tool_use
  -> Claude Code MCP client
  -> external MCP server
```

但 main agent 和 local subagent 之间不是：

```text
main -> MCP -> subagent
```

它们之间是：

```text
Agent tool
LocalAgentTask
commandQueue
task-notification
pendingMessages
sidechain transcript
```

---

## 12. 送达时机总表

| 消息 | 发送者 | 接收者 | 何时送达 | 会不会打断当前 API call |
|------|--------|--------|----------|--------------------------|
| `async_launched` tool_result | runtime | main agent | Agent tool call 返回时 | 不涉及 |
| `<task-notification>` | background lifecycle | main agent | 主 agent 下次 queue drain | 不会 |
| `SendMessage` to running subagent | main agent | subagent | subagent 下次 attachment collection | 不会 |
| `TaskOutput` | main agent 主动调用 | task output | tool 执行时读取，可 block | 不会 |
| 用户 prompt | 用户/REPL | main agent | 新 turn 或 queue drain | 可能 interrupt 当前 turn，取决于 priority |

## 13. 一句话总结

```text
Claude Code local agent 间通信不是 RPC，而是 runtime message passing。

启动靠 tool_use/tool_result。
完成靠 task-notification。
继续 running agent 靠 pendingMessages mailbox。
读取结果靠 TaskOutput/output file/sidechain transcript。
恢复 stopped agent 靠 transcript replay。
```

下一篇看取消和恢复：[04 - 取消、继续与恢复](./04-cancel-resume-and-abort.md)。
