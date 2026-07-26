# Child Loop 与 Context Isolation：一次 Tool 调用里的第二个 Query Loop

## 1. 先看全景：为什么不是调用一个函数

> 父 Agent 发出 Agent Tool Intent 后，Claude Code 为什么不是调用一个函数，而是构造并运行另一个受约束的 agent loop？

结论先说：**Subagent 是父 Tool 调用内部的一次独立 Query Loop。父侧只看见结构化的 Tool Intent 与最终 Tool Observation；子侧则拥有单独组装的模型视图、工具集、权限上下文和生命周期。**

这使 `AgentTool` 同时承担两个角色：对父循环，它是一个接受通用 Tool 编排、Permission 检查和结果映射的普通 Tool；对内，它又是把一次委派适配成另一个 `query()` / Query Loop 的入口。两层循环共处一个进程，不等于共享一份可随意改写的运行时状态。

```mermaid
sequenceDiagram
    participant P as Parent Query Loop
    participant A as AgentTool
    participant R as Child Runtime
    participant M as Child Model
    participant T as Task Registry

    P->>A: D1 Parent Emits Agent Tool Intent
    Note over P,A: generic Tool resolution + Permission gate
    A->>A: D2 AgentTool Resolves Route and Mode
    A->>T: register foreground record and registry controller
    Note over A,T: physical prerequisite before D3; not a D milestone
    A->>R: D3 Construct Child Context and Tool Set
    R->>M: D4 Run Child Query Loop
    loop child model/tool feedback rounds
        M->>R: assistant message / child Tool Intent
        R->>M: controlled Tool Observation / next request
    end
    Note over A,T: D5 Manage Foreground or Background Task Lifecycle
    Note over R,T: D6 Communicate, Resume, or Drain Notifications (canonical foreground skips)
    R-->>A: child iterator settles; collected messages remain data
    A->>T: foreground cleanup unregisters record (before D7)
    A->>A: D7 Normalize Child Result as Parent Tool Observation
    A-->>P: D8 Parent Query Loop Continues
    Note over P: parent Query Loop continues; child mutable runtime does not cross back
```

这张图的关键不是“又调了一次模型”，而是所有权发生了切换：

- D1–D2 仍属于父 Tool 调用；此时尚无 child Query Loop。
- foreground registration 是 D3 之前的实现前置事件，不占用或改写任何 D milestone。
- D3 固定表示 Construct Child Context and Tool Set；D4 固定表示 Run Child Query Loop。
- D5 固定表示 lifecycle ownership；在规范 foreground 路径中，record 已提前注册，D5 不是“此刻才注册”。D6 是 communication / resume / notification 变体，本路径跳过。
- child iterator settle 后先运行 foreground unregister cleanup，D7 才归一化结果；D8 让父 Query Loop 继续。

本文只跟踪规范路径：**本地、前台、非 fork 的 child task**。D5–D6 只保留足够解释所有权的生命周期信息；后台调度、通信、恢复和 fork/cache 都不是本章主线。

## 2. Parent / Child 状态边界

“隔离”不是“任何东西都不共享”。更准确的判断方法是逐项问：跨边界时它是 copy、derived、fresh、shared，还是仅引用稳定配置？谁还能改它？模型是否可见？

| state | inherited / copy / derived / fresh / shared? | parent can mutate? | child can mutate? | model-visible to whom? | lifetime |
|---|---|---:|---:|---|---|
| task prompt | **derived + fresh**：由父 `Agent` Tool Intent 的 `prompt` 生成新的 child user message | 父只能拥有原始 Tool Intent | 子循环可追加后续消息，不回写原 intent | 父看 intent；子看新 user message | 本次 child Query Loop |
| description | **copy / derived**：用于任务展示、注册与结果描述，不自动成为可变对话状态 | 可经 task registry 观察任务 | child 不把它当会话消息改写 | 通常是 runtime / UI 元数据 | task record 生命周期 |
| system prompt / persona | **derived**：由选中的 agent definition、base prompt 与受控上下文组装 | 父不能在 child 启动后借此改写子历史 | child 读取，Query Loop 不把它当普通消息回写 | 只对 child model 可见 | child 请求序列 |
| selected conversation / context | 正常路径为 **fresh + derived**：从任务 prompt 和选定上下文起步，不复制父完整 transcript | 父继续拥有自己的 history | child 只增长自己的 messages | 各模型只看各自组装的视图 | 各自 Query Loop |
| Tool capability pool | **independently assembled + filtered**：`AgentTool.call` 按 worker Permission mode 独立 `assembleToolPool`；`runAgent` 再以 agent definition 过滤，normal child 排除 `AgentTool` | 父 Tool list 与 normal worker pool 各自拥有；不是父集合的直接上/子集关系 | child 只能调用最终 `resolvedTools` | child model 看过滤后的 child tools | child Query Loop |
| `ToolUseContext` / AppState | **fresh shell + selective copy/clone/share**：新 agent/query identity、新 Sets/denial state，clone file/replacement state；canonical sync 明确 `shareSetAppState: true`，但 UI callbacks 仍移除 | sync 父子经共享 setter 更新同一 AppState；其余 mutable child fields 仍分离 | child 可经共享 setter 更新 AppState，也可改 child-owned fields | runtime-only；字段衍生物才进模型请求 | child Query Loop |
| Permission mode / effect rules | **derived with explicit precedence/replacement**：agent mode 在若干父 mode 例外之外可 override；`allowedTools` 可替换 session allow rules，同时保留 CLI rules | 不能概括为“父 policy 永远是上界” | 每次 child Tool effect 仍经过普通 Permission / Controlled Effects | policy 本身 runtime-only；sync Ask 可走交互路径 | child Tool 执行期间 |
| model and request options | **derived / selected reference**：选 agent model，并继承或改写必要的请求选项 | 父请求配置不被 child 回写 | child 只消费自己的 options | child model 请求可感知结果，不见 runtime object | child Query Loop |
| cwd / worktree / environment metadata | **derived / selected reference**：默认从父运行环境选 cwd；显式 isolation 可换 worktree；不是复制整个进程环境 | 父可继续改自己的文件世界 | child Tool 在被选中的 cwd/worktree 内产生受控效果 | 路径可进入 child 上下文；环境对象主要 runtime-only | child execution；worktree 可更长 |
| `AbortController` | 规范前台 sync 使用 **shared named override**：`runAgent` 把父 controller 明确交给 child；通用构造器在无 override 时才建立 linked child controller | 父 abort 会直接终止这条共享取消链 | child 只观察/触发所持信号的取消语义 | runtime-only | 单次执行 |
| task identity / registry controller | **fresh + separate owners**：child ID 作为 registry key；`registerAgentForeground` 另建 registry controller，它不是传给 child query 的 sync controller | task helpers 管 registry record/controller | child 用 ID 标记消息；query cancel 走另一条 controller ownership | runtime / UI 元数据 | foreground record 到 unregister；child controller 到 query settle |
| output buffer (`agentMessages`) | **fresh outer aggregation buffer**：收集进度与终态输出；不是 child 下一次模型请求，也不是可恢复 transcript | adapter 可汇总、归一化 | child query 产出的消息被追加进去 | child model 不把该数组本身当 context；父最终只见映射结果 | 一次 AgentTool 调用 |
| task store access | **shared, explicit**：`setAppStateForTasks` 总能指向 root task store；canonical sync 还共享一般 `setAppState` | root helpers 与 sync child 可经相应 setter 更新 | child 不因此获得已移除的 UI callbacks | runtime / UI，不直接进模型 | task / app session |
| UI callbacks | **removed**：`addNotification`、`setToolJSX`、`openMessageSelector` 等不进入 child context | 父 UI 仍正常工作 | child 不能直接控制这些 UI callback；但 sync Permission Ask 可由独立 permission path bubble | 不可见 | child execution |

这里最容易混淆三组对象：

1. **child messages** 是下一轮 child model request 的输入，会随子循环增长。
2. **`agentMessages`** 是 `AgentTool.call` 外层的聚合 / 进度 / 结果缓冲，不自动喂回 child。
3. **task registry** 是显式共享的运行时记录，用来表示 `running`、完成或取消，不是任何一侧模型的 transcript。

因此，“child context 隔离”应读成：**模型 history 与大部分 per-child mutable state 分离，但 runtime crossing 必须逐项确认。** 规范前台不仅共享 abort controller 和 root task store，也明确共享一般 `setAppState`；这仍不等于共享 messages、query tracking、caches 或 UI callbacks。

## 3. 一次失败测试调查如何穿过两层循环

假设父 Agent 正在修复测试：`payments/refund.test.ts` 的 “releases reservation after timeout” 失败。父循环已有大量实现上下文，但现在只需要回答一个有边界的问题：失败断言来自生产逻辑、fixture，还是 fake timer 的推进顺序？

### D1：父模型只提交委派意图

父 history 的末尾可以抽象为：

```text
Parent assistant:
  tool_use Agent {
    description: "定位退款超时测试失败原因",
    prompt: "只读检查失败测试与直接生产调用链；给出根因、证据和最小修复建议。",
    subagent_type: "Explore"
  }
```

这不是 child 的第一轮 assistant message。它先进入通用 Tool 层：从父 `ToolUseContext.options.tools` 中解析 `AgentTool`，执行 hooks / Permission 检查，再多态调用 `AgentTool.call`。所以委派没有绕过父 Tool 的 Controlled Effects 边界。

### D2–D3：物理 registration 先行，D3 仍是 context construction

`AgentTool.call` 在 D2 选择 normal foreground route，解析 `Explore` agent definition，并按 worker Permission mode 独立组装 worker tool pool。然后它先调用 `registerAgentForeground`；注册完成后才创建并推进 `runAgent` iterator。下面是 **D3 之前的物理前置快照**，不是 D3 的重新命名：

```text
Task Registry
  taskId / agentId = fresh stable key
  status           = running
  isBackgrounded   = false
  abortController  = fresh registry controller

Child Query Runtime
  not constructed or advanced yet
```

registry controller 服务于 foreground record 的 task lifecycle；它不是 `runAgent` 规范 sync 路径使用的 parent-shared query controller。随后 iterator advance 触发 `runAgent` 组装 context/tool set。**D3 的固定状态快照**是：

```text
Parent-owned                         Child-owned
------------                         -----------
parent messages                      initialMessages = [fresh user task]
parent tools                         independently assembled + filtered worker tools
parent ToolUseContext                new child ToolUseContext
original Agent tool_use              new agentId / query chain / Sets

Explicit crossing
-----------------
Permission mode/rules with explicit override semantics
shared sync setAppState
shared sync abort-controller override
shared root task-store setter
cloned/selected file and replacement state
```

此刻 parent history 没有被复制成 child history，child 也拿不到父 UI callback。它得到的是为这次调查刻意组装的最小模型视图和执行能力。

### D4：child 自己闭合 Query Loop

D4 的第一份模型视图近似如下：

```text
Child system:
  [Explore persona + base instructions + selected repository/runtime context]
Child user:
  只读检查失败测试与直接生产调用链；给出根因、证据和最小修复建议。
Child tools:
  [resolved read/search tools, ...]  # no normal nested AgentTool
Child runtime only:
  permission policy, cwd, abort signal, caches, task identity
```

随后 child model 可以先发出搜索 Tool Intent，child runtime 执行 Permission / Tool 调度，返回 Tool Observation，再让 **child Query Loop** 发下一次模型请求。这个反馈过程可重复多轮；parent model 此时只是等待 `AgentTool` 的前台调用完成，不会逐条接收 child 的搜索结果，也不会共享 child 的可变 message array。

D4 进入 child Query Loop 并承载内部 model / Tool feedback rounds。task record 在 D3 前已经存在；D5 表示 foreground/background lifecycle 由 registry 与相关 helper 持续管理，并不表示 registration 到 D5 才发生。D6 固定属于 communication、resume 或 notification 机制；规范 foreground walkthrough 不经过这些变体通道。

### D7–D8：终态被压成一个父 Tool Observation

假设 child 最终判断：fixture 在 fake clock 推进前创建 reservation，生产代码按绝对 deadline 比较，因此失败来自测试时钟初始化顺序。child iterator settle 后，`AgentTool.call` 先在 cleanup 中 unregister foreground record；随后 D7 才执行 result finalization。D7 的边界不是把 child context 交还父亲，而是：

```text
Child terminal assistant text
  + usage / tool-use count
  + collected child messages used for finalization
        |
        v
finalizeAgentTool -> AgentToolResult(status = completed)
        |
        v
AgentTool result mapper -> ordinary tool_result content
```

父侧 D8 只增长一条与原 `tool_use` 配对的 Tool Observation，例如：

```text
Parent user/tool_result:
  根因：fixture 建立 reservation 后才安装 fake clock，deadline 使用了真实时间基准……
  证据：……
  最小建议：先固定时钟，再创建 fixture；无需修改生产超时判断。
```

父 Query Loop 接着综合这个结果、决定是否改测试。它看见的是归一化后的调查产物，不是 child 的 controller、cache、Permission state、内部 Tool history 或可恢复执行栈。

这个例子是无错误完成，但 D7 的 `completed` contract 还允许另一种来源：child 已产生 assistant message 后发生非 abort error，adapter 使用 partial output 完成 finalization。父侧不能仅凭 `completed` 反推 child 内部 error-free。

## 4. Child context 为什么按这个顺序构造

在 `runAgent` iterator 被创建和推进前，`AgentTool.call` 已经注册 foreground task；这保证任务能立刻被寻址，而不是等 child model 开始运行后才补登记。随后 `runAgent` 的组装仍是一条因果链：前一步界定后一步能够暴露什么。

| 顺序 | 构造动作 | 直接得到什么 | 防止的失败 / 启用的行为 |
|---:|---|---|---|
| 1 | 选择 agent type / configuration | agent definition、persona、model、允许的能力边界 | 未知 agent type 在 child 创建前失败；避免先创建半套 runtime 再发现无可执行配置 |
| 2 | 派生 task prompt 与 system instructions | fresh child user message，以及针对角色组装的 system / context prompts | 防止把父完整 transcript 当成默认委派上下文；让 child 聚焦有边界的任务 |
| 3 | 建立隔离与继承约束 | 新 identity/query tracking、fresh Sets/denial state、clone 的文件 / replacement state、命名共享通道 | 防止 child 偶然回写父 mutable runtime，同时允许取消和 task tracking 穿透必要边界 |
| 4 | 解析 child Tool set | 对 caller 已按 worker mode 独立组装的 pool，应用 agent allow/disallow 与 normal-child filter | 分开 capability pool ownership 与一次 effect 的 Permission verdict；让 Tool schema 与真正可执行集合一致 |
| 5 | 创建 child runtime controls | child `ToolUseContext`、cwd、abort wiring、sync shared AppState setter、removed UI callbacks | 让 Tool effects 仍走正常受控路径；同时允许 foreground Permission Ask 经独立路径交互 |
| 6 | 以 child-owned messages 进入共享 Query Loop 实现 | `query()` 接收 child prompts、tools、context，再进入 `queryLoop()` | 复用同一套模型 / Tool 反馈机制，但不复用父循环的可变消息所有权 |
| 7 | 收集 terminal child output | outer `agentMessages`、final text、usage、tool-use count | 允许 adapter 映射为稳定的父 Tool Observation，而不暴露 child runtime object |

因果关系可以压缩成一句话：**先确定身份和边界，再解析能力和控制面，最后才允许模型循环运行。** 如果把顺序反过来，例如先复用父 tools/context 再过滤，child model 可能已经看见实际不可执行或不应暴露的能力；如果把 `agentMessages` 当作下一轮 child input，则前台聚合、恢复 transcript 与 model history 三种不同语义会被错误合并。

## 5. 三条窄边界：recursion、Permission、cancel

### 5.1 normal child 默认不能再调用 AgentTool

答案是：**规范 normal child 的已解析工具集中没有 `AgentTool`，所以不能从自己的 Tool round 再委派一层 normal child。**

这不是靠 prompt 说“请勿递归”。`resolveAgentTools` 在 subagent 路径先运行 `filterToolsForAgent`；`Agent` 属于 subagent 禁用项。即使 agent definition 的 tool spec 写了 `Agent(...)`，resolver 也只保留其中 `allowedAgentTypes` 元数据，不会把 `AgentTool` 实例加入 `resolvedTools`。因此：

```text
agent definition mentions Agent(...) metadata
        !=
child executable tool set contains AgentTool
```

fork 的防递归是另一道门，不能拿来解释 normal path。fork 会在 `AgentTool.call` 路由阶段检查 `options.querySource === "agent:builtin:fork"`，并保留 message scan 作为 fallback；这是“已经处于 fork child 时拒绝再次选 fork route”的 gate。一个边界是 **tool capability filtering**，另一个是 **route recursion rejection**。

### 5.2 避免 Permission prompt 不等于自动 Allow

child 的 capability pool 与 effect Permission 不能混为一句“继承父权限”：

1. 父侧调用 `AgentTool` 本身先经过通用 Tool Permission / hook pipeline。
2. `AgentTool.call` 以 `selectedAgent.permissionMode ?? "acceptEdits"` 独立组装 worker tool pool；normal path 不从 `parentContext.options.tools` 派生这个 pool。`runAgent` 随后才按 agent definition 过滤它。
3. `agentGetAppState` 从当前 AppState 派生 effect Permission context，但带明确 precedence：agent mode 可 override，父处于 `bypassPermissions`、`acceptEdits` 或特定 `auto` 情况时例外；传入 `allowedTools` 时会替换 session allow rules，但保留 CLI allow rules。因此不存在一个通用的“父 policy 永远是上界”。
4. canonical sync 的默认 `shouldAvoidPrompts` 是 `isAsync`，也就是 `false`；`bubble` mode 也明确允许 prompt。`runAgent` 把这个 `agentGetAppState` 作为 override 交给 `createSubagentContext`，所以不会走 helper 那条默认强制 `shouldAvoidPermissionPrompts=true` 的分支。
5. child 内每次 Tool effect 仍进入普通 Tool orchestration、tool-specific Permission 与 Controlled Effects 路径。

`createSubagentContext` 仍会移除 `addNotification`、`setToolJSX`、`openMessageSelector` 等直接 UI callbacks，但这不等于 canonical sync 无法 Ask：Permission prompt 可以经 `canUseTool` / permission machinery bubble 到父终端。反过来，允许 Ask 也不等于自动 Allow；最终 verdict 仍由 mode、rules、hooks 与 tool-specific Permission 决定。

AppState 也必须按 mode 区分：canonical sync 传 `shareSetAppState: true`，所以共享一般 setter；async 默认才把一般 setter 变为 no-op。无论哪种 mode，`setAppStateForTasks` 都必须抵达 root task store，以免异步进程失去登记和清理。UI callbacks 被移除，与 AppState setter 是否共享是两条独立轴。

### 5.3 sync cancel 是命名共享；通用 helper 默认是 linked child

规范前台路径中，`runAgent` 先选择 `agentAbortController`：override 优先；async 使用新的 unlinked controller；sync 明确取 `toolUseContext.abortController`。这个 controller 又作为 override 传给 `createSubagentContext`，所以本章的 foreground child 与父 Tool 调用共享同一个命名 controller。父侧 cancel 因而能到达正在执行的 child query / Tool stage。

不要把它和 D3 前置 foreground registry 的 controller 混在一起：`registerAgentForeground` 自己调用 `createAbortController()` 并把它放进 task record；它不接收 `runAgent` 的 sync query controller。一个属于 registry/task lifecycle，一个属于 child query cancellation。

通用 helper 本身的默认语义不同：

```text
explicit override
  > explicitly share parent controller
  > createChildAbortController(parent controller)
```

最后一种是 linked child controller：父信号能传播到 child，但 child 持有单独 controller。把这两种实现都概括为“child 总有独立 controller”会写错 canonical sync；把它们都说成“父子共享所有 lifecycle state”也同样错误。共享的是这条取消通道，不是 messages、caches、denial state 或 UI callbacks。

取消之后，child 不会把半套 runtime 塞进父 context。`AbortError` 会被明确重新抛出，保持 interruption 语义。非 abort error 则不同：如果已经收集到 assistant message，`AgentTool.call` 会用 partial messages 继续 `finalizeAgentTool` 并返回 `status: "completed"`；只有完全没有 assistant message 时才重新抛错。因此 `completed` 是 result-contract 状态，不保证 child 内部从未发生错误。

## 6. 从父 Tool Intent 到父 Tool Observation 的伪代码

下面只保留 canonical foreground route，刻意省略 teammate、remote、background 与 fork 细节：

```ts
async function runAgentTool(
  parentIntent,
  parentContext,
): Promise<ParentToolObservation> {
  // D1 Parent Emits Agent Tool Intent.
  const agentInput = validateAgentInput(parentIntent)
  await checkGenericToolPermission(AgentTool, agentInput, parentContext)

  // D2 AgentTool Resolves Route and Mode.
  const definition = resolveAgentDefinition(agentInput.subagent_type)
  if (!definition) return toolError("unknown agent type")

  const agentId = createAgentId()
  const initialMessages = [freshUserMessage(agentInput.prompt)]
  const workerPermissionContext = {
    ...parentContext.getAppState().toolPermissionContext,
    mode: definition.permissionMode ?? "acceptEdits",
  }
  const workerPool = assembleToolPool(workerPermissionContext, mcpTools)

  // Physical prerequisite before D3: registration owns a separate controller.
  const registration = registerAgentForeground({
    agentId,
    description: agentInput.description,
    prompt: agentInput.prompt,
    selectedAgent: definition,
    setAppState: rootSetAppState,
  })

  const collected = []
  let childError
  try {
    // D3 Construct Child Context and Tool Set happens as runAgent advances:
    // it filters workerPool, derives sync Permission state, shares parent setAppState,
    // and uses the parent controller as the sync query override.
    const agentIterator = runAgent({
      agentDefinition: definition,
      promptMessages: initialMessages,
      availableTools: workerPool,
      toolUseContext: parentContext,
      isAsync: false,
      override: { agentId },
    })[Symbol.asyncIterator]()

    // D4 Run Child Query Loop.
    while (true) {
      const next = await agentIterator.next()
      if (next.done) break
      collected.push(next.value)
    }
    // D5 Manage Foreground or Background Task Lifecycle:
    // the already-registered record remains the lifecycle owner.
    // D6 Communicate, Resume, or Drain Notifications is skipped in foreground.
  } catch (error) {
    if (isAbortError(error)) throw error
    childError = error
  } finally {
    // Physical cleanup before D7: remove, do not mark completed.
    unregisterAgentForeground(registration.taskId, rootSetAppState)
  }

  // D7 Normalize Child Result as Parent Tool Observation.
  // Partial assistant output can still finalize after a non-abort error.
  if (childError && !collected.some(isAssistantMessage)) throw childError
  const result = finalizeAgentTool(collected)
  return mapAgentResultToOrdinaryToolResult({ status: "completed", ...result })
}
```

这段伪代码表达五个不变量：registration 是 D3 前置事件，不重新定义 D3；D3 构造 context/tool set，D4 运行 child Query Loop，D5 维持 lifecycle ownership；registry controller 与 sync child-query controller 各有 owner；foreground unregister cleanup 先于 D7 finalization。只要 partial assistant output 足够 finalization，非 abort error 仍可能映射为 completed Tool Observation。

## 7. 决定性源码镜头

所有源码事实固定在 commit `712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf`。下面使用 `commit + repository-relative path + symbol` 作为证据身份；pinned link 的行号只用于定位，不作为正文结构。

### Lens 1：route 落定后，foreground registration 先于 iterator

**[Source-confirmed]** `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/AgentTool.tsx, AgentTool.call)` 与 `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tasks/LocalAgentTask/LocalAgentTask.tsx, registerAgentForeground / unregisterAgentForeground)`：

```ts
const useFork = /* gated fork route */
const shouldRunAsync = /* explicit input + runtime decision */

// local foreground branch, after route selection
const registration = registerAgentForeground({
  agentId: syncAgentId,
  description,
  prompt,
  selectedAgent,
  setAppState: rootSetAppState,
})

const agentIterator = runAgent({ ...runAgentParams, override: { agentId: syncAgentId } })
  [Symbol.asyncIterator]()

try {
  // advance iterator and collect messages
} finally {
  unregisterAgentForeground(foregroundTaskId, rootSetAppState)
}

const agentResult = finalizeAgentTool(agentMessages, syncAgentId, metadata)
```

route failure 与 unknown agent type 仍可在 child 创建前结束；进入 local foreground branch 后，registration 明确先于 iterator。`registerAgentForeground` 内部另建 registry controller；iterator settle 后，`unregisterAgentForeground` 在 `finally` 中删除仍为 foreground 的 record，随后代码才运行 error/partial 判断与 `finalizeAgentTool`。[查看 route 与 worker run parameters](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L318-L630) · [查看 registration-before-iterator](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L808-L858) · [查看 unregister-before-finalize cleanup](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L1150-L1238) · [查看 registry controller 创建](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tasks/LocalAgentTask/LocalAgentTask.tsx#L526-L556) · [查看 foreground record removal](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tasks/LocalAgentTask/LocalAgentTask.tsx#L657-L682)。

### Lens 2：canonical sync 会 override helper 默认值

**[Source-confirmed]** `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/runAgent.ts, runAgent / agentGetAppState)` 与 `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/utils/forkedAgent.ts, createSubagentContext)`：

```ts
const shouldAvoidPrompts = canShowPermissionPrompts !== undefined
  ? !canShowPermissionPrompts
  : agentPermissionMode === "bubble" ? false : isAsync

createSubagentContext(toolUseContext, {
  getAppState: agentGetAppState,
  shareSetAppState: !isAsync,
  abortController: agentAbortController,
})

// helper still removes direct child UI callbacks
addNotification: undefined
openMessageSelector: undefined
```

helper 自身在没有 override 时可强制 avoid prompts；canonical `runAgent` 却传入 `agentGetAppState`，且 sync 共享一般 `setAppState`。UI callback removal 与 Permission Ask / AppState sharing 不能互相推导。[查看 sync Permission derivation](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/runAgent.ts#L436-L478) · [查看 canonical context overrides](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/runAgent.ts#L697-L714) · [查看 helper defaults 与 UI removal](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/utils/forkedAgent.ts#L356-L438)。

### Lens 3：capability pool 与 effect Permission 是两条轴

**[Source-confirmed]** `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/AgentTool.tsx, AgentTool.call)`、`(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/runAgent.ts, runAgent / agentGetAppState)` 与 `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/agentToolUtils.ts, resolveAgentTools)`：

```ts
const workerPermissionContext = {
  ...appState.toolPermissionContext,
  mode: selectedAgent.permissionMode ?? "acceptEdits",
}
const workerTools = assembleToolPool(workerPermissionContext, appState.mcp.tools)

// normal route
availableTools: workerTools

const resolvedTools = resolveAgentTools(agentDefinition, availableTools, isAsync)

// allowedTools replaces session rules, while preserving cliArg rules
alwaysAllowRules: { cliArg: previous.cliArg, session: [...allowedTools] }
```

normal worker pool 是独立 assembly 的结果，不是 parent tool list 的直接副本；`resolveAgentTools` 再负责 agent-level filtering。具体 effect 的 mode/rules 又由 `agentGetAppState` 派生。[查看 worker pool assembly 与 route input](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L568-L630) · [查看 worker pool contract 与 filtering](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/runAgent.ts#L292-L300) · [查看 mode / session-rule semantics](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/runAgent.ts#L420-L502)。

### Lens 4：共享 Query Loop 实现，不共享父 message ownership

**[Source-confirmed]** `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/runAgent.ts, runAgent)` 与 `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/query.ts, query / queryLoop)`：

```ts
const agentToolUseContext = createSubagentContext(toolUseContext, {
  messages: initialMessages,
  options: agentOptions,
  abortController: agentAbortController,
  ...
})

for await (const message of query({
  messages: initialMessages,
  tools: resolvedTools,
  toolUseContext: agentToolUseContext,
  ...
})) {
  yield message
}
```

`query()` 随后进入同一套 `queryLoop()` 机制；复用的是算法和协议，不是父 loop 的 mutable messages。[查看 `runAgent` 的 child query entry](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/runAgent.ts#L667-L757) · [查看 `query` wrapper](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/query.ts#L219-L239)。

### Lens 5：partial error 也可能进入 completed mapping

**[Source-confirmed]** `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/agentToolUtils.ts, finalizeAgentTool)` 与 `(712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf, src/tools/AgentTool/AgentTool.tsx, AgentTool.mapToolResultToToolResultBlockParam)`：

```ts
if (error instanceof AbortError) throw error

if (syncAgentError) {
  const hasAssistantMessages = agentMessages.some(msg => msg.type === "assistant")
  if (!hasAssistantMessages) throw syncAgentError
}

const agentResult = finalizeAgentTool(agentMessages)
return { status: "completed", ...agentResult }

// later, through the generic Tool result mapper
return [{ type: "text", text: normalizedAgentContent }]
```

Abort 始终重抛；非 abort error 只有在没有 assistant message 时才重抛。已有 partial assistant output 时，normalizer 与 mapper仍可产生普通 completed `tool_result`，但这不抹去内部曾发生 error 的事实。[查看 sync catch / Abort rethrow](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L1127-L1149) · [查看 partial-error finalization](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L1205-L1259) · [查看 Agent result mapper](https://github.com/buoylee/Claude-Code-true/blob/712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf/src/tools/AgentTool/AgentTool.tsx#L1298-L1379)。

## 8. 失败发生在哪一层

把所有失败都叫作“subagent failed”会失去恢复信息。判断是否已经存在 child runtime，才知道该看 route、Permission、child loop 还是 parent mapping。

| 失败 | 最早边界 | 此时 child 是否存在 | 父侧得到什么 | 正确诊断重点 |
|---|---|---:|---|---|
| input schema / prompt 无效 | D1 generic Tool validation | 否 | 普通 Tool input error | 检查 `prompt`、`subagent_type` 与 route 参数，不查 child transcript |
| unknown agent type | D2 `AgentTool.call` routing | 否 | route / Tool error | 检查 agent definition 是否存在、是否在当前环境可选 |
| route 前置条件失败 | D2 route selection | 否 | 立即失败或非本地 route result | 检查所选执行模式的 gate；不要声称 child query 已启动 |
| agent 配置声明了不可用 Tool | D3 context / tool-set construction | 尚未进入模型循环 | 配置可被判 invalid，或 child 只得到过滤后的集合 | 对比独立 worker pool、agent spec、disallowed tools 与 normal-child filter |
| child Tool 被 Permission 拒绝 | D4 child Query Loop | 是 | child 收到受控拒绝并可能改换方案；终态再由 AgentTool 返回 | 区分“Tool 不在 schema”与“Tool 存在但这次 effect 不获准” |
| child model / Tool 非 abort error | D4 child Query Loop | 是 | 有 assistant message：finalize partial output 并返回 `completed`；没有：重抛给 Tool framework | 同时检查 first error 与是否已有 assistant output，不能仅按 parent status 反推内部无错 |
| parent cancel / abort | D4 execution / D5 lifecycle | 是 | `AbortError` 明确重抛，不进入 partial completed recovery | 分开 parent-shared query controller 与 registry controller，再看取消在哪个 stage settle |
| child 有 partial assistant output | D7 finalization | 是，已结束或异常结束 | 即使此前有非 abort error，也可归一化为 completed Tool Observation | 保留“partial after error”的解释，不把 `completed` 解读为 error-free |
| parent result mapping 失败 | D7–D8 adapter / generic Tool mapper | child 已结束 | 父缺少合法配对的 Tool Observation | 检查 mapper contract 与 `tool_use` / `tool_result` pairing |

两个常见误诊值得单独指出：

- child 搜索了文件，不代表 parent model 已经“知道”搜索结果；只有 D8 的 mapped observation 跨回父 history。
- task registry 显示 `running`，不代表 child model request 正在 streaming；registry、model stream 与 outer message aggregation 是不同 owner 的状态。

## 9. 设计取舍：为什么值得多造一层 loop

### 9.1 Context isolation 与 useful inheritance

全量继承最省组装代码，却会让 child 看见无关历史、父临时状态和过宽能力；全量隔离最干净，却会丢失 cwd、Permission constraints、取消传播与任务治理。Claude Code 的选择是逐字段 crossing：

```text
model view        -> derived / fresh
mutable caches    -> clone or fresh
tool capability   -> independently assembled, then filtered
permission policy -> explicit mode precedence / rule replacement
task registry     -> explicit record + separate registry controller
sync AppState     -> explicitly shared setter
sync cancellation -> explicitly shared controller override
stable config     -> selected reference where safe
```

代价是理解成本更高：不能靠一句“继承 parent context”描述实现。但收益是每个例外都有名字，审查者可以追问它为什么需要穿过边界。

### 9.2 Bounded delegation 与 nested complexity

child loop 适合有明确输入、有限搜索空间和可压缩输出的任务，例如定位一个失败测试、梳理一条调用链或评估几个实现点。它不适合把模糊的主任务原封不动再问一遍，因为：

- parent 与 child 各自消耗 model rounds；边界不清会重复探索。
- child 看不到父完整 mutable history；隐含前提若没写入 prompt，就不会自动穿越。
- parent 最终只消费归一化结果；需要逐步协作的任务会损失中间信息。
- normal child 无 `AgentTool`，复杂工作不能依赖无限递归来自动拆解。

这也是“第二个 Query Loop”优于“调用一个 helper function”的地方：child 可以自主进行多轮模型 / Tool 反馈；也是它更昂贵的地方：必须为另一套模型状态、Tool rounds、Permission 与生命周期付费。

### 9.3 为什么只返回 normalized result

如果 parent 收到整个 child runtime，会同时引入四个问题：mutable ownership 冲突、Permission state 泄漏、不可序列化的 controller/callback、以及父 model context 被中间 Tool 噪音淹没。归一化结果把 contract 收窄为父真正需要的信息：terminal 或 partial content、usage / 计数，以及映射后的 result status。这个 status 描述 adapter 的交付形式，不完整记录 child 内部是否曾出现可恢复的非 abort error。

这个 contract 也让 foreground 与未来的其他 delivery mode 可以保持相同的语义目标：**交付 child 工作产物，而非迁移 child execution stack。** 执行时序和运输渠道可以改变，父子所有权边界不必跟着改写。

## 10. 必须守住的不变量

1. **一个 Agent Tool call 内有两个 Query Loop ownership。** 父 loop 发 intent、收 observation；child loop 独立增长自己的模型 / Tool history。
2. **`AgentTool` 仍是普通 Tool boundary。** 父侧 generic Permission、call 和 result mapping 没有被绕开。
3. **child context 不是 parent context alias。** 每个 crossing 都必须被描述为 derived、copy/clone、fresh、shared 或 selected reference。
4. **normal capability pool 独立组装后再过滤。** 它不是 `parentContext.options.tools` 的派生子集；最终 `filterToolsForAgent` 仍排除 nested AgentTool。
5. **Permission 有显式 precedence。** agent mode override、父 mode 例外、session-rule replacement 与保留 CLI rules 必须分别描述，不能压成“父 policy 是上界”。
6. **removed UI callbacks 不等于 sync 无 Ask。** canonical sync 的 `agentGetAppState` 默认允许 prompt，且 `shareSetAppState: true`；Permission verdict 仍不等于自动 Allow。
7. **query cancel 与 registry cancel state 不是同一 controller。** sync child query 使用 parent controller override；`registerAgentForeground` 另建 registry controller。
8. **foreground cleanup 是 remove，并先于 D7。** `unregisterAgentForeground` 在 `finally` 中删除仍为 foreground 的 record，不写泛化的 completed state；随后才运行 error/partial 判断与 `finalizeAgentTool`。
9. **`agentMessages` 是 outer aggregation，不是隐式 child next-request context，也不是 resumable transcript。**
10. **`completed` 不保证 error-free。** 有 assistant output 的非 abort error 可 finalization 为 partial completed；Abort 与无 assistant output 的 error 会重抛。
11. **D8 只跨回数据。** parent 不接收 child caches、controller、denial state、callbacks 或 live stack。

## 11. 常见误解校正

**误解：Subagent 就是父 Agent 调用了一个带 LLM 的函数。**

校正：函数调用只是 adapter 表面；内部建立的是带独立 messages、system prompt、tools、Permission context 与 Tool feedback 的第二个 Query Loop。

**误解：隔离表示任何字段都不能共享。**

校正：隔离的是 model history 与 per-child mutable state。canonical sync 还共享 parent abort controller 与一般 AppState setter，root task store 也显式共享；UI callbacks 仍被移除。

**误解：child 继承父 tools，所以也能无限创建 grandchildren。**

校正：normal path 先按 worker Permission mode 独立组装 pool，再由 `runAgent` 解析和过滤；`AgentTool` 不进入 child executable set。fork 的防递归则在 route 层另行判断。

**误解：child 没有 UI callbacks，所以 sync Permission 无法 Ask。**

校正：canonical sync 提供 `agentGetAppState` override，默认不强制 `shouldAvoidPermissionPrompts`，Permission prompt 可经独立 machinery bubble；removed UI callbacks 只禁止 child 直接控制那些 UI 接口。

**误解：parent cancel 只能等 child 自己轮询 registry。**

校正：canonical foreground 明确共享 parent abort controller override，cancel 直接进入 child query / Tool execution 的取消链；foreground registry 自己还有另一个 controller，不能混用。

**误解：父侧拿到 `status: "completed"`，证明 child 没出错。**

校正：非 abort error 发生前若已有 assistant message，`AgentTool.call` 会 finalize partial output 并返回 completed；只有 Abort 或没有 assistant output 的 error 才重抛。

**误解：parent 可以继续使用 child 的完整思考和工具历史。**

校正：D7 normalizer 与 mapper只交付终态 content / usage 等稳定数据。中间 runtime 不属于 parent model context。

## 12. 面试回答

如果面试官问“Claude Code 的 subagent 隔离是怎样实现的”，可以用下面这版：

> `AgentTool` 外部是普通 Tool：父 Query Loop 产生 Tool Intent，先走通用 Tool orchestration 和 Permission。local foreground route 会按 worker Permission mode 独立组装 tool pool，并先注册 foreground task；registry 自己创建 controller，随后才创建/推进 `runAgent` iterator。`runAgent` 过滤 worker pool，为 child 派生 prompt、persona、model 和 effect Permission context，再用 `createSubagentContext` 创建独立 messages、identity、query tracking、Sets 与 cloned caches。canonical sync 会共享 parent abort controller 和一般 AppState setter，默认允许 Permission prompt 走独立 machinery；直接 UI callbacks 仍被移除。child 使用相同 `queryLoop()` 机制完成自己的 Tool feedback rounds。结束时 foreground record 被 remove；Abort 始终重抛，非 abort error 若已有 assistant output 则可 finalize partial data 为 `completed` Tool Observation，否则重抛。跨回 parent 的始终是 normalized data，不是 child mutable runtime。

继续追问时，先画出 D1–D8，再按“fresh / derived / clone / shared / reference”解释状态矩阵；这比笼统说“上下文复制”更能回答所有权、权限与取消边界。

## 13. 阅读衔接与下一问

如果对“消息为什么分为 model context、transcript 与 runtime state”还不牢，先返回 [Session Continuity 总览](../03-session-continuity/README.md)。本章是在那个区分之上，再增加 parent / child 两套所有权。

未来生命周期章节接手的问题可以先用纯文本固定：

```text
foreground child
  parent Agent tool_use
    -> same Tool call waits
    -> child Query Loop reaches terminal
    -> one completed Tool Observation returns
    -> parent Query Loop continues

background child
  parent Agent tool_use
    -> launch observation returns first
    -> task registry owns ongoing lifecycle
    -> terminal result arrives through a later delivery boundary
    -> parent re-enters with normalized data, never with child live runtime
```

由此留下下一问：**同一个语义上的 child task 改为 background 后，哪些只是交付时序改变，哪些 lifecycle owner、取消与结果回流路径必须随之改变？**
