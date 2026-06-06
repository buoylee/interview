# 04 - 取消、继续与恢复

> 这一篇解释 ESC、kill agents、用户说“继续”、以及 stopped subagent resume 的真实代码语义。

源码根目录：`/Users/buoy/Development/gitrepo/Claude-Code-true`

核心文件：

| 文件 | 作用 |
|------|------|
| `src/hooks/useCancelRequest.ts` | ESC / Ctrl+C / kill agents 交互入口 |
| `src/screens/REPL.tsx` | `onCancel()`、`onQuery()`、重新提交用户输入 |
| `src/utils/handlePromptSubmit.ts` | 用户输入如何变成新 turn 或 queued command |
| `src/tools/AgentTool/runAgent.ts` | subagent abortController 选择逻辑 |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | `killAsyncAgent()`、`registerAsyncAgent()`、`registerAgentForeground()` |
| `src/tools/SendMessageTool/SendMessageTool.ts` | running agent queue message，stopped agent resume |
| `src/tools/AgentTool/resumeAgent.ts` | transcript replay + background resume |
| `src/utils/abortController.ts` | `createAbortController()`、`createChildAbortController()` |

---

## 1. 先看 abort controller 拓扑

最关键的一段在 `runAgent()`：

```ts
const abortController =
  override.abortController ??
  (isAsync
    ? createAbortController()
    : toolUseContext.abortController)
```

这决定了取消边界：

```text
sync subagent
  默认复用 parent toolUseContext.abortController
  -> parent 被 abort，subagent 也停

async/background subagent
  使用 override.abortController 或自己 createAbortController()
  -> 不默认跟随 parent ESC
```

background path 中 `AgentTool` 明确不把它挂到主 agent：

```ts
// Don't link to parent's abort controller -- background agents should
// survive when the user presses ESC to cancel the main thread.
// They are killed explicitly via chat:killAgents.
```

因此 background subagent 的拓扑是：

```text
main turn abortController M

background subagent A abortController A
background subagent B abortController B

M.abort('user-cancel') 不会自动触发 A/B.abort()
```

---

## 2. ESC 取消主 agent 时发生什么？

用户按 ESC 后，大致路径是：

```text
ESC
  |
  v
useCancelRequest.handleCancel()
  |
  v
REPL.onCancel()
  |
  v
abortController.abort('user-cancel')
  |
  v
当前 foreground query() 收到 abort
  |
  v
当前主 turn 结束
```

结果：

```text
主 agent 当前 turn 停止。
已经 registerAsyncAgent 的 background subagent 继续运行。
```

但要注意边界：

```text
如果 subagent A/B 已经 registerAsyncAgent，ESC 不会杀它们。
如果 ESC 发生在主 agent 还没执行到第二个 Agent tool call 前，第二个可能根本没启动。
```

---

## 3. sync subagent 为什么会被 ESC 停掉？

sync/foreground subagent 默认使用 parent controller：

```text
sync subagent abortController = parent toolUseContext.abortController
```

所以：

```text
用户 ESC
  -> parent controller abort
  -> sync subagent 也看到 abort
  -> runAgent/query/tool execution 退出
```

这就是 async 和 sync 的关键差别。

| 场景 | abortController | ESC 主 turn 后果 |
|------|-----------------|------------------|
| sync subagent | parent controller | 一起停 |
| async/background subagent | task controller | 通常继续 |
| foreground agent 后来 backgrounded | task controller | background 后继续 |

---

## 4. 什么会杀 background subagent？

显式 kill。

`killAsyncAgent()` 的核心：

```ts
task.abortController?.abort()
```

典型入口：

- `chat:killAgents`。
- UI/命令显式停止 task。
- 某些 viewing teammate 场景下的 kill all。
- cleanup handler。

语义：

```text
ESC
  取消当前前台 query turn

kill agents
  取消 background task 自己的 abortController
```

所以不要把 ESC 和 kill agents 混为一谈。

---

## 5. background subagent 被 kill 后 lifecycle 怎么收尾？

`runAsyncAgentLifecycle()` 捕获 `AbortError`：

```ts
if (error instanceof AbortError) {
  killAsyncAgent(taskId, rootSetAppState)
  const partialResult = extractPartialResult(agentMessages)
  enqueueAgentNotification({
    taskId,
    description,
    status: 'killed',
    finalMessage: partialResult,
  })
  return
}
```

所以 kill 不是静默消失。

它会：

```text
abort task controller
  |
  v
runAgent/query/tool execution 抛 AbortError
  |
  v
runAsyncAgentLifecycle catch
  |
  |-- task.status = killed
  |-- extract partial result
  |-- enqueue killed task-notification
```

主 agent 后续可能会收到：

```xml
<task-notification>
  <status>killed</status>
  <summary>Agent "..." was stopped</summary>
  <result>partial...</result>
</task-notification>
```

---

## 6. 用户说“继续”：继续主 agent

如果用户 ESC 取消了主 agent，原来的 `query()` 已经结束。

用户再输入“继续”，不是恢复旧 JS call stack，也不是继续旧 async generator。

它是新 turn：

```text
用户输入 "继续"
  |
  v
handlePromptSubmit()
  |
  v
executeUserInput()
  |
  v
createAbortController()
  |
  v
processUserInput()
  |
  v
onQuery(newMessages, abortController)
  |
  v
query() 重新开始
```

为什么看起来能接上？

因为主 session transcript 里还在：

- 之前用户需求。
- 主 agent 已经输出的内容。
- 已启动 background subagent 的 `async_launched` tool_result。
- background subagent 后续完成时 enqueue 的 `<task-notification>`。

所以“继续”的真实语义是：

```text
new user message + existing transcript + new query loop
```

---

## 7. 用户说“继续”：继续某个 running subagent

如果主 agent 要继续某个正在运行的 subagent，应该用 `SendMessage`。

路径：

```text
main agent tool_use: SendMessage({ to: agentId, message: '继续...' })
  |
  v
SendMessageTool
  |
  |-- 找到 AppState.tasks[agentId]
  |-- task.status === 'running'
  |-- queuePendingMessage(agentId, message)
```

`queuePendingMessage()` 写：

```text
AppState.tasks[agentId].pendingMessages[]
```

subagent 下一次 attachment collection 时读取：

```text
getAgentPendingMessageAttachments()
  |
  v
drainPendingMessages()
  |
  v
queued_command attachment
```

所以它不会立刻打断 subagent 当前 API call。

更像：

```text
给 subagent mailbox 留一封信。
```

---

## 8. 用户说“继续”：继续 stopped / evicted subagent

如果 task 已停止，`SendMessage` 会尝试：

```text
resumeAgentBackground({ agentId, prompt: message })
```

resume 路径：

```text
resumeAgentBackground()
  |
  |-- loadTranscriptWithMetadata(agentId)
  |-- filter resumedMessages
  |-- reconstruct contentReplacementState
  |-- resolve selectedAgent / agentType / model
  |-- 如果是 fork，恢复 parent system prompt
  |-- promptMessages = resumedMessages + createUserMessage(prompt)
  |-- registerAsyncAgent(agentId)
  |-- runAsyncAgentLifecycle(... runAgent(...))
```

这里也不是恢复旧 generator。

它是：

```text
transcript replay + appended user message + new background run
```

---

## 9. interrupted while active：用户输入可能变成 queue

如果用户在主 query 还 active 的时候提交输入，`handlePromptSubmit()` 会看 `queryGuard` 和当前 tool interrupt behavior。

可能结果：

- 如果当前工具可 interrupt，abort 当前 turn，reason 可能是 `interrupt`。
- 把用户输入 enqueue，等待当前 query 结束或 drain。
- 如果没有 active query，直接开新 turn。

这和 ESC 后说“继续”不同。

ESC 后通常已经结束当前 turn；active 时提交可能进入 queue。

---

## 10. 状态机总结

```text
main running
  |
  |-- ESC
  |     |
  |     +-- main abortController abort
  |     +-- main query exits
  |     +-- async subagents continue
  |
  |-- kill agents
  |     |
  |     +-- each background task abortController abort
  |     +-- lifecycle emits killed notification
  |
  |-- user says continue after cancel
        |
        +-- new main user turn
        +-- new abortController
        +-- query() starts again
```

subagent 状态机：

```text
running
  |
  |-- SendMessage
  |     +-- pendingMessages += msg
  |
  |-- complete
  |     +-- completeAsyncAgent
  |     +-- task-notification completed
  |
  |-- kill
  |     +-- abort task controller
  |     +-- task-notification killed
  |
  |-- stopped + SendMessage
        +-- resumeAgentBackground
        +-- new background run
```

## 11. 面试式回答

如果有人问：并发启动两个 subagent，用户按 ESC 取消主 agent，这两个 subagent 会停吗？

可以回答：

```text
通常不会。

Claude Code 的 background local subagent 会通过 registerAsyncAgent 注册成 LocalAgentTask，拥有自己的 abortController。AgentTool 的 async path 明确不把它链接到主 agent 的 abort controller，因为设计上 background agents 应该在用户 ESC 取消主线程时继续运行。ESC 只 abort 当前 foreground query turn。

只有 sync subagent 默认共享 parent abortController，会随主 turn 停止。background subagent 需要显式 kill agents 或 task stop，才会 abort 它自己的 task controller。
```

如果继续问：用户说“继续”怎么恢复？

可以回答：

```text
不是恢复旧 call stack。
主 agent 的“继续”是新的 user turn，基于已有 transcript 重新进入 query()。
subagent 的“继续”如果还 running，就通过 SendMessage 写 pendingMessages mailbox；如果 stopped/evicted，就通过 resumeAgentBackground 读取 sidechain transcript 和 metadata，追加新的 user message，再启动新的 background runAgent。
```

下一篇看 fork prompt cache：[05 - Fork Subagent 与 Prompt Cache](./05-fork-subagent-prompt-cache.md)。
