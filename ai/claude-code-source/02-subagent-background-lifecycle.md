# 02 - Subagent 后台生命周期

> 这一篇只回答一个问题：`Agent` tool 被调用以后，Claude Code 如何把一个 subagent 注册成后台任务，并让它独立跑自己的 `query()` 循环。

源码根目录：`/Users/buoy/Development/gitrepo/Claude-Code-true`

核心文件：

| 文件 | 作用 |
|------|------|
| `src/tools/AgentTool/AgentTool.tsx` | `Agent` tool 入口，决定 sync/async/fork，注册 task，启动 lifecycle |
| `src/tasks/LocalAgentTask/LocalAgentTask.tsx` | `registerAsyncAgent()`、task state、kill/complete/fail |
| `src/tools/AgentTool/agentToolUtils.ts` | `runAsyncAgentLifecycle()`，驱动 background agent 从运行到完成通知 |
| `src/tools/AgentTool/runAgent.ts` | 构造 subagent context 并进入 `query()` |
| `src/utils/forkedAgent.ts` | `createSubagentContext()`，复制并隔离 `ToolUseContext` |
| `src/query.ts` | 主 agent 和 subagent 共用的核心 loop |

---

## 1. 总流程

```text
主 agent 输出 tool_use Agent(...)
  |
  v
AgentTool.call()
  |
  |-- 选择 selectedAgent / fork agent
  |-- 构造 promptMessages / systemPrompt
  |-- 过滤或继承工具列表
  |-- 判断 shouldRunAsync
  |
  +-- async path
        |
        |-- registerAsyncAgent()
        |-- void runWithAgentContext(... runAsyncAgentLifecycle(...))
        |-- 立即返回 tool_result: async_launched
        |
        v
      background lifecycle
        |
        |-- runAgent()
        |-- createSubagentContext()
        |-- query()
        |-- recordSidechainTranscript()
        |-- complete / fail / kill
        |-- enqueueAgentNotification()
```

这个流程有两个同时存在的时间线：

```text
主 agent 时间线：Agent tool 很快返回 async_launched。
subagent 时间线：background lifecycle 继续跑到完成。
```

---

## 2. AgentTool.call() 是入口

`AgentTool` 的输入大致是：

```ts
{
  description: string,
  prompt: string,
  subagent_type?: string,
  model?: string,
  run_in_background?: boolean,
  name?: string,
  team_name?: string,
  mode?: string,
  isolation?: string,
  cwd?: string,
}
```

主 agent 调用它时，本质是一次模型 tool call：

```text
assistant -> tool_use: Agent({ prompt, description, subagent_type })
```

`AgentTool.call()` 内部先做几类决策：

- 这是普通 subagent、fork subagent、还是 teammate/remote agent？
- `subagent_type` 是否指定？
- 是否启用 fork subagent？
- agent 的 model、tools、permissionMode 是什么？
- 是否 `run_in_background`？
- 是否需要 worktree isolation？

这些决策最后会汇总成 `runAgentParams`。

---

## 3. async/background 的核心分叉

`AgentTool.tsx` 会计算：

```text
forceAsync
assistantForceAsync
shouldRunAsync
```

fork subagent 开启时通常会 `forceAsync`，因为 fork 的交互模型依赖 `<task-notification>` 回到主 agent。

async path 的核心是：

```ts
const agentBackgroundTask = registerAsyncAgent({
  agentId: asyncAgentId,
  description,
  prompt,
  selectedAgent,
  setAppState: rootSetAppState,
  // Don't link to parent's abort controller -- background agents should
  // survive when the user presses ESC to cancel the main thread.
  // They are killed explicitly via chat:killAgents.
  toolUseId: toolUseContext.toolUseId,
})
```

这一步创建并注册 background task。

然后是最关键的 fire-and-forget：

```ts
void runWithAgentContext(asyncAgentContext, () =>
  wrapWithCwd(() =>
    runAsyncAgentLifecycle({
      taskId: agentBackgroundTask.agentId,
      abortController: agentBackgroundTask.abortController!,
      makeStream: onCacheSafeParams =>
        runAgent({
          ...runAgentParams,
          override: {
            ...runAgentParams.override,
            agentId: asAgentId(agentBackgroundTask.agentId),
            abortController: agentBackgroundTask.abortController!,
          },
          onCacheSafeParams,
        }),
      metadata,
      description,
      toolUseContext,
      rootSetAppState,
      agentIdForCleanup: asyncAgentId,
    })
  )
)
```

`void` 的含义：

```text
启动它，但不要 await 它。
```

因此 `AgentTool.call()` 可以马上返回：

```text
status: async_launched
agentId: ...
outputFile: ...
```

---

## 4. registerAsyncAgent() 注册什么状态？

`src/tasks/LocalAgentTask/LocalAgentTask.tsx` 中的 `registerAsyncAgent()` 把后台 subagent 注册成 `LocalAgentTaskState`。

核心代码形态：

```ts
const abortController = parentAbortController
  ? createChildAbortController(parentAbortController)
  : createAbortController()

const taskState: LocalAgentTaskState = {
  type: 'local_agent',
  status: 'running',
  agentId,
  prompt,
  selectedAgent,
  agentType: selectedAgent.agentType ?? 'general-purpose',
  abortController,
  isBackgrounded: true,
  pendingMessages: [],
  retain: false,
  diskLoaded: false,
}

registerTask(taskState, setAppState)
```

它注册的是这个实体：

```text
AppState.tasks[agentId] = LocalAgentTaskState
```

这个 task state 后续被很多地方使用：

| 字段 | 用途 |
|------|------|
| `status` | running / completed / failed / killed |
| `abortController` | kill background agent |
| `selectedAgent` | resume 时知道用哪个 agent definition |
| `agentType` | UI、metadata、resume 路由 |
| `pendingMessages` | `SendMessage` 给 running subagent 留消息 |
| `retain` / `messages` | UI 查看 subagent transcript 时实时追加 |
| `toolUseId` | 完成通知关联原始 Agent tool call |

---

## 5. runAsyncAgentLifecycle() 驱动后台生命周期

`runAsyncAgentLifecycle()` 是 background agent 的 driver。

它做的事可以分成三段。

第一段：消费 `runAgent()` stream。

```ts
const agentMessages: MessageType[] = []

for await (const message of makeStream(onCacheSafeParams)) {
  agentMessages.push(message)
  updateAsyncAgentProgress(...)
  emitTaskProgress(...)
}
```

第二段：正常完成。

```ts
const agentResult = finalizeAgentTool(agentMessages, taskId, metadata)
completeAsyncAgent(agentResult, rootSetAppState)
enqueueAgentNotification({
  taskId,
  description,
  status: 'completed',
  finalMessage,
  usage,
})
```

第三段：异常或取消。

```ts
if (error instanceof AbortError) {
  killAsyncAgent(taskId, rootSetAppState)
  enqueueAgentNotification({
    taskId,
    description,
    status: 'killed',
    finalMessage: partialResult,
  })
  return
}

failAsyncAgent(taskId, msg, rootSetAppState)
enqueueAgentNotification({
  taskId,
  description,
  status: 'failed',
  error: msg,
})
```

所以 lifecycle 的责任是：

```text
run stream -> 收集 messages -> 更新进度 -> 标记 task 状态 -> 发完成通知
```

---

## 6. runAgent() 进入真正的 query loop

`runAgent()` 里会构造 subagent 的运行环境：

- 生成或接收 `agentId`。
- 构造 `initialMessages`。
- clone / fresh `readFileState`。
- 包装 `getAppState`。
- 选择 abortController。
- 跑 SubagentStart hooks。
- 初始化 MCP / skills / options。
- 调 `createSubagentContext()`。
- 写 sidechain transcript metadata。
- 进入 `query()`。

关键片段：

```ts
const agentToolUseContext = createSubagentContext({
  parentContext: toolUseContext,
  options: agentOptions,
  agentId,
  agentType: agentDefinition.agentType,
  messages: initialMessages,
  readFileState,
  abortController,
  getAppState: agentGetAppState,
  shareSetAppState: !isAsync,
  shareSetResponseLength: true,
})
```

然后：

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

这里再次确认：

```text
subagent 生命周期的核心，最终就是 query()。
```

---

## 7. createSubagentContext() 隔离 ToolUseContext

`createSubagentContext()` 的设计可以理解成：

```text
复制一份工具运行环境，但只共享必须共享的根状态。
```

隔离内容：

- `agentId`。
- `agentType`。
- `messages`。
- `abortController`。
- `readFileState`。
- `localDenialTracking`。
- `queryTracking`。
- `contentReplacementState`。
- UI callbacks。

保留共享通道：

- `setAppStateForTasks`，让 subagent 能更新 task registry / progress / kill 状态。
- `options.mcpClients` / tools 等可按 agent policy 继承或过滤。
- `getAppState`，但可能包装成 avoid permission prompts 的版本。

重要心智模型：

```text
普通交互状态隔离。
任务生命周期状态共享。
```

---

## 8. sync path 和 async path 的生命周期差别

async/background path：

```text
AgentTool.call()
  -> registerAsyncAgent()
  -> void runAsyncAgentLifecycle()
  -> return async_launched immediately
```

sync/foreground path：

```text
AgentTool.call()
  -> registerAgentForeground()
  -> for await (message of runAgent())
  -> 等 subagent 跑完
  -> finalizeAgentTool()
  -> return completed tool_result
```

差异表：

| 维度 | async/background | sync/foreground |
|------|------------------|-----------------|
| Agent tool 是否等待完成 | 不等待 | 等待 |
| 返回给主 agent 的 tool_result | `async_launched` | `completed` |
| abortController | 独立 task controller | 默认复用 parent controller |
| ESC 主 turn | 通常不杀 subagent | 会影响 subagent |
| 完成结果 | 后续 `<task-notification>` | 当前 tool_result |
| 通信方式 | queue / notification / SendMessage | 当前 tool call result |

---

## 9. 并发启动多个 Agent tool

`AgentTool` 声明：

```ts
isReadOnly() {
  return true
}

isConcurrencySafe() {
  return true
}
```

因此工具调度层可以把多个 `Agent` tool 并发启动。

非 streaming 路径在 `toolOrchestration.ts`：

```ts
async function* runToolsConcurrently(...) {
  yield* all(
    toolUseMessages.map(async function* (toolUse) {
      yield* runToolUse(...)
    }),
    getMaxToolUseConcurrency(),
  )
}
```

streaming 路径在 `StreamingToolExecutor.ts`，concurrency-safe tools 可以同时执行。

所以两个 Agent tool 的时间线可能是：

```text
assistant message:
  tool_use Agent(A)
  tool_use Agent(B)

executor:
  A.call() 和 B.call() 并发执行

A.call():
  registerAsyncAgent(A)
  void lifecycle(A)
  return async_launched

B.call():
  registerAsyncAgent(B)
  void lifecycle(B)
  return async_launched
```

注意：这是 Node async 并发，不是 CPU 线程并行。

---

## 10. 一张生命周期图

```text
AgentTool.call()
  |
  |-- selectedAgent / fork / tools / prompt / model
  |
  |-- shouldRunAsync ?
       |
       |-- yes
       |     |
       |     |-- registerAsyncAgent()
       |     |     |
       |     |     +-- AppState.tasks[agentId]
       |     |     +-- abortController
       |     |     +-- output symlink
       |     |
       |     |-- void runAsyncAgentLifecycle()
       |     |     |
       |     |     |-- runAgent()
       |     |     |     |
       |     |     |     |-- createSubagentContext()
       |     |     |     |-- query()
       |     |     |     |-- recordSidechainTranscript()
       |     |     |
       |     |     |-- complete/fail/kill task
       |     |     |-- enqueueAgentNotification()
       |     |
       |     +-- return async_launched
       |
       |-- no
             |
             |-- runAgent() inline
             |-- wait for completion
             |-- return completed
```

## 下一篇

下一篇看通信机制：[03 - Agent 间通信协议](./03-agent-communication-protocol.md)。
