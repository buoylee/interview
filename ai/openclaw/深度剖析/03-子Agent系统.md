# 03 - 子 Agent 系统：派生、控制与生命周期

> OpenClaw 的子 Agent 不是简单的函数调用，而是有完整生命周期的独立会话。
> 本文剖析子 Agent 的派生（spawn）、注册跟踪（registry）、控制操作（control）三个核心模块。

---

## 架构总览

```
父 Agent 会话
  │
  ├── spawnSubagentDirect()                  [spawn]
  │     · 验证深度/并发/权限
  │     · 创建子 session key
  │     · 发送消息到 gateway
  │     · 注册 run record
  │
  ▼
子 Agent 会话（独立 session）
  │
  ├── registerSubagentRun()                  [registry]
  │     · 写入 run record
  │     · 启动完成等待超时
  │
  ├── 执行中...（独立的 runEmbeddedPiAgent）
  │
  ├── completeSubagentRun()                  [registry]
  │     · 记录 outcome
  │     · 冻结结果文本
  │     · 触发 announce/cleanup
  │
  └── announceSubagentCompletion()           [announce]
        · 将结果通知父 Agent
        · 指数退避重试（最多 3 次）
        · 清理 session（如果 cleanup="delete"）
```

---

## 子 Agent 派生：subagent-spawn.ts

源码：`agents/subagent-spawn.ts:294-841`

### 核心函数

```typescript
export async function spawnSubagentDirect(
  params: SpawnSubagentParams,
  ctx: SpawnSubagentContext,
): Promise<SpawnSubagentResult>
```

### Phase 1: 安全验证

```typescript
// 1. 深度限制 — 防止无限递归
const currentDepth = resolveSessionDepth(params.controllerSessionKey);
const maxDepth = params.config.agents?.maxSpawnDepth ?? 3;
if (currentDepth >= maxDepth) {
  return { status: "rejected", note: `Spawn depth limit reached (max=${maxDepth})` };
}

// 2. 并发上限 — 每个 session 的活跃子 agent 数
const activeCount = countActiveRunsForSession(params.controllerSessionKey);
const maxChildren = params.config.agents?.maxActiveChildren ?? 5;
if (activeCount >= maxChildren) {
  return { status: "rejected", note: `Active children limit reached (max=${maxChildren})` };
}

// 3. Agent 允许列表 — 跨 agent 派生需要白名单
const allowedAgents = params.config.agents?.allowedSpawnAgents;
if (allowedAgents && !allowedAgents.includes(params.agentId)) {
  return { status: "rejected", note: `Agent "${params.agentId}" not in spawn allowlist` };
}

// 4. 沙箱兼容性
if (params.sandboxMode === "require" && !ctx.sandboxAvailable) {
  return { status: "rejected", note: "Sandbox required but not available" };
}
```

### Phase 2: Session 创建

```typescript
// 子 session key 格式: agent:{agentId}:subagent:{uuid}
const childSessionKey = `agent:${params.agentId}:subagent:${generateSecureToken(8)}`;

// 用 gateway 创建 session，注入上下文
const sessionPatch = {
  depth: currentDepth + 1,
  role: "subagent",
  parentSessionKey: params.controllerSessionKey,
  model: params.model,                    // 可指定不同模型
  thinkLevel: params.thinking ?? "off",   // 可指定 thinking level
};
```

### Phase 3: 附件处理

```typescript
// 子 agent 可以携带附件（文件）
if (params.attachments?.length > 0) {
  const materialized = await materializeSubagentAttachments({
    attachments: params.attachments,
    workspaceDir: params.workspaceDir,
    childSessionKey,
  });
  // base64 解码 → 写入临时目录 → 注入系统 prompt 告知位置
}
```

### Phase 4: 发送 + 注册

```typescript
// 通过 gateway 发送消息（不投递到外部渠道）
const result = await gateway.send({
  sessionKey: childSessionKey,
  message: params.task,
  lane: AGENT_LANE_SUBAGENT,  // 子 agent 专用 lane
  deliver: false,              // 不投递到消息渠道
});
const runId = result.runId;

// 注册 run record
registerSubagentRun({
  runId,
  childSessionKey,
  controllerSessionKey: params.controllerSessionKey,
  requesterSessionKey: params.requesterSessionKey,
  task: params.task,
  label: params.label,
  cleanup: params.cleanup ?? "delete",  // 完成后删除 session
  spawnMode: resolveSpawnMode(params),  // "run" 或 "session"
});

return {
  status: "accepted",
  childSessionKey,
  runId,
};
```

### Spawn Mode

```typescript
// subagent-spawn.ts:212-221
function resolveSpawnMode(params): "run" | "session" {
  // "run": 一次性执行，完成后可删除 session
  // "session": 持久会话，完成后保留，可继续对话

  if (params.mode) return params.mode;         // 显式指定
  if (params.thread) return "session";          // thread-bound 默认持久
  return "run";                                 // 默认一次性
}
```

---

## 子 Agent 注册表：subagent-registry.ts

源码：`agents/subagent-registry.ts:1-1705`

### Run Record 数据结构

```typescript
type SubagentRunRecord = {
  // 标识
  runId: string;
  childSessionKey: string;
  controllerSessionKey: string;   // 控制者（父 agent）
  requesterSessionKey: string;    // 请求者（可能是祖父）
  requesterDisplayKey: string;

  // 任务
  task: string;
  label?: string;
  cleanup: "delete" | "keep";
  spawnMode: "run" | "session";

  // 生命周期时间戳
  createdAt: number;
  startedAt?: number;
  sessionStartedAt?: number;
  endedAt?: number;

  // 完成状态
  outcome?: {
    status: "ok" | "error" | "timeout";
    error?: string;
  };
  endedReason?: "complete" | "error" | "killed";

  // 清理追踪
  cleanupHandled?: boolean;
  cleanupCompletedAt?: number;

  // 完成通知
  frozenResultText?: string;          // 冻结的结果文本（最大 100KB）
  frozenResultCapturedAt?: number;
  expectsCompletionMessage?: boolean;
  announceRetryCount?: number;        // 通知重试次数
  lastAnnounceRetryAt?: number;

  // 运行时
  model?: string;
  workspaceDir?: string;
  runTimeoutSeconds?: number;
  attachmentsDir?: string;
};
```

### 生命周期状态机

```
┌─────────┐     registerSubagentRun()
│ pending  │ ←── 创建 run record，设置 createdAt
└────┬─────┘
     │ lifecycle "start" 事件
     ▼
┌─────────┐
│ active   │ ←── startedAt 记录，子 agent 正在执行
└────┬─────┘
     │ lifecycle "end"/"error" 事件
     ▼
┌─────────┐     completeSubagentRun()
│  ended   │ ←── outcome 记录，endedAt 设置
└────┬─────┘
     │ announceSubagentCompletion()
     ▼
┌──────────────┐
│ announcing   │ ←── 将结果通知父 agent
└────┬─────────┘
     │ 成功 / 重试耗尽
     ▼
┌─────────┐     cleanup: "delete" → 删除 session
│ cleanup  │ ←── cleanup: "keep"   → 保留
└──────────┘     cleanupCompletedAt 设置
```

### 注册

```typescript
// subagent-registry.ts:1337-1403
export function registerSubagentRun(params): void {
  const record: SubagentRunRecord = {
    runId: params.runId,
    childSessionKey: params.childSessionKey,
    controllerSessionKey: params.controllerSessionKey,
    requesterSessionKey: params.requesterSessionKey,
    task: params.task,
    cleanup: params.cleanup,
    spawnMode: params.spawnMode,
    createdAt: Date.now(),
    startedAt: Date.now(),  // 创建即开始
  };

  // 持久化到磁盘
  persistRunRecord(record);

  // 启动完成等待超时
  if (params.runTimeoutSeconds) {
    scheduleRunTimeout(record.runId, params.runTimeoutSeconds * 1000);
  }
}
```

### 完成

```typescript
// subagent-registry.ts:526-631
export function completeSubagentRun(params: {
  runId: string;
  outcome: { status: "ok" | "error" | "timeout"; error?: string };
  resultText?: string;
}): void {
  const record = getRunRecord(params.runId);
  if (!record || record.endedAt) return;  // 幂等

  // 更新状态
  record.endedAt = Date.now();
  record.outcome = params.outcome;
  record.endedReason = params.outcome.status === "ok" ? "complete" : "error";

  // 冻结结果文本（最大 100KB，防止内存爆炸）
  if (params.resultText) {
    const MAX_FROZEN_TEXT = 100 * 1024;
    record.frozenResultText = params.resultText.length > MAX_FROZEN_TEXT
      ? params.resultText.slice(0, MAX_FROZEN_TEXT) + "\n[truncated]"
      : params.resultText;
    record.frozenResultCapturedAt = Date.now();
  }

  persistRunRecord(record);

  // 触发完成通知
  if (record.expectsCompletionMessage) {
    scheduleAnnounce(record);
  }
}
```

### 恢复（进程重启后）

```typescript
// subagent-registry.ts:682-759
export function resumeSubagentRun(runId: string): void {
  const record = getRunRecord(runId);
  if (!record) return;

  // 检查是否是孤儿 run（session 已不存在）
  if (!sessionExists(record.childSessionKey)) {
    markSubagentRunTerminated({ runId, reason: "orphaned" });
    return;
  }

  // 重试通知
  if (record.endedAt && !record.cleanupCompletedAt) {
    // 指数退避: attempt 1 → 5s, attempt 2 → 15s, attempt 3 → 45s
    const retryCount = record.announceRetryCount ?? 0;
    if (retryCount >= 3) {
      // 超过重试限制，强制过期
      forceExpireRun(record);
      return;
    }
    const delay = 5000 * Math.pow(3, retryCount);
    scheduleRetry(record, delay);
  }

  // 强制过期：非完成状态 5 分钟，完成状态 30 分钟
  const maxAge = record.endedAt ? 30 * 60_000 : 5 * 60_000;
  if (Date.now() - record.createdAt > maxAge) {
    forceExpireRun(record);
  }
}
```

---

## 子 Agent 控制：subagent-control.ts

源码：`agents/subagent-control.ts:1-827`

### 控制权模型

```typescript
type ResolvedSubagentController = {
  controllerSessionKey: string;  // 控制者 session
  callerSessionKey: string;      // 调用者 session（可能不同）
  callerIsSubagent: boolean;     // 调用者是否是子 agent
  controlScope: "children" | "none";
};
```

**规则**：
- 只有父 agent（控制者）可以控制子 agent
- 叶子节点（深度达到上限）的 `controlScope` 为 `"none"`，不能派生或控制
- 控制操作会级联到子树

### Kill：终止子 Agent

```typescript
// subagent-control.ts:470-534
export async function killControlledSubagentRun(params: {
  controller: ResolvedSubagentController;
  targetRunId: string;
}): Promise<{ killed: number; cascadeCount: number }> {
  // 1. 验证控制权
  const record = getRunRecord(params.targetRunId);
  if (record.controllerSessionKey !== params.controller.controllerSessionKey) {
    throw new Error("Not authorized to kill this subagent");
  }

  // 2. 终止目标
  killSubagentRun(record);

  // 3. 级联终止所有后代
  const descendants = findDescendantRuns(record.childSessionKey);
  for (const desc of descendants) {
    killSubagentRun(desc);
  }

  return { killed: 1, cascadeCount: descendants.length };
}
```

**级联 Kill**：父死子亡。当 kill 一个子 agent 时，它的所有后代也会被 kill。

### Kill All

```typescript
// subagent-control.ts:426-468
export async function killAllControlledSubagentRuns(params: {
  controller: ResolvedSubagentController;
}): Promise<{ killed: number }> {
  const children = listSubagentRunsForRequester(params.controller.controllerSessionKey);
  let killed = 0;
  for (const child of children) {
    if (child.endedAt) continue;  // 已经结束的跳过
    killSubagentRun(child);
    killed += 1;
    // 级联
    const descendants = findDescendantRuns(child.childSessionKey);
    for (const desc of descendants) {
      killSubagentRun(desc);
      killed += 1;
    }
  }
  return { killed };
}
```

### Steer：中途改方向

Steer 是最复杂的控制操作——中断当前执行，发送新消息，创建新 run。

```typescript
// subagent-control.ts:570-729
export async function steerControlledSubagentRun(params: {
  controller: ResolvedSubagentController;
  targetRunId: string;
  message: string;
}): Promise<{ newRunId: string }> {
  // 1. 频率限制（同一 controller→target 对，至少 2 秒间隔）
  const lastSteerAt = getLastSteerTimestamp(controller, target);
  if (Date.now() - lastSteerAt < 2000) {
    throw new Error("Steer rate limit exceeded");
  }

  // 2. 标记旧 run 为 "steer-restart" 抑制
  markRunForSteerRestart(params.targetRunId);

  // 3. 中断当前执行
  abortEmbeddedPiRun(record.childSessionKey);

  // 4. 清除排队消息
  clearQueuedMessages(record.childSessionKey);

  // 5. 发送新消息
  const result = await gateway.send({
    sessionKey: record.childSessionKey,
    message: params.message,
  });

  // 6. 创建新 run record（继承旧 run 的时间）
  const newRecord = replaceSubagentRunAfterSteer({
    oldRunId: params.targetRunId,
    newRunId: result.runId,
    preserveSessionStartedAt: true,
  });

  return { newRunId: result.runId };
}
```

### Send：发送消息（不中断）

```typescript
// subagent-control.ts:731-804
export async function sendControlledSubagentMessage(params: {
  controller: ResolvedSubagentController;
  targetRunId: string;
  message: string;
}): Promise<{ replyText: string }> {
  // 发送消息，等待回复（30 秒超时）
  const result = await gateway.send({
    sessionKey: record.childSessionKey,
    message: params.message,
  });

  // 等待完成
  const reply = await waitForCompletion(result.runId, 30_000);
  return { replyText: reply.lastAssistantText };
}
```

### List：列出子 Agent

```typescript
// subagent-control.ts:257-328
export function buildSubagentList(params: {
  controllerSessionKey: string;
  windowMs?: number;
}): BuiltSubagentList {
  const allRuns = listSubagentRunsForRequester(params.controllerSessionKey);

  // 分类
  const active = allRuns.filter(r =>
    !r.endedAt || countPendingDescendantRuns(r.childSessionKey) > 0
  );
  const recent = allRuns.filter(r =>
    r.endedAt && Date.now() - r.endedAt < (params.windowMs ?? 10 * 60_000)
  );

  // 格式化
  return {
    active: active.map(r => ({
      runId: r.runId,
      label: r.label ?? r.task.slice(0, 80),
      status: r.endedAt ? "ended" : "running",
      runtime: formatDuration(Date.now() - r.startedAt),
      childCount: countActiveRunsForSession(r.childSessionKey),
    })),
    recent: recent.map(r => ({
      runId: r.runId,
      label: r.label ?? r.task.slice(0, 80),
      outcome: r.outcome?.status ?? "unknown",
      runtime: formatDuration(r.endedAt - r.startedAt),
    })),
  };
}
```

---

## 完成通知：subagent-announce.ts

源码：`agents/subagent-announce.ts:1-1508`

当子 agent 完成时，需要通知父 agent。这个过程有重试机制：

```
子 agent 完成
  │
  ├── 冻结结果文本（最大 100KB）
  │
  ├── 尝试通知父 agent
  │     ├── 成功 → 清理 session → 完成
  │     │
  │     └── 失败（父 agent 忙 / 网络问题）
  │           ├── retry 1: 5 秒后
  │           ├── retry 2: 15 秒后
  │           ├── retry 3: 45 秒后
  │           └── 放弃 → 强制过期
  │
  └── 清理（cleanup="delete" → 删除 session 文件）
```

**通知是异步的**——不是同步 RPC，而是排队投递。这避免了子 agent 完成时父 agent 正忙的死锁问题。

---

## 完整示例：一次子 Agent 生命周期

```
1. 父 Agent 收到: "帮我研究一下 React 19 的新特性"

2. 父 Agent 决定派生子 Agent:
   spawnSubagentDirect({
     task: "Research React 19 new features",
     agentId: "default",
     model: "anthropic/claude-haiku-3-5",  // 用便宜模型
     thinking: "off",
     cleanup: "delete",                      // 完成后删除
     spawnMode: "run",                       // 一次性任务
   })

3. 验证通过:
   depth=0 < maxDepth=3 ✓
   activeChildren=0 < maxChildren=5 ✓

4. 创建子 session:
   childSessionKey = "agent:default:subagent:a1b2c3d4"

5. 注册 run record:
   { runId: "run-xyz", status: pending, createdAt: now }

6. 子 Agent 执行:
   runEmbeddedPiAgent({
     sessionKey: "agent:default:subagent:a1b2c3d4",
     prompt: "Research React 19 new features",
     model: "anthropic/claude-haiku-3-5",
   })
   → 搜索网页 → 整理结果 → 返回

7. 完成:
   completeSubagentRun({
     runId: "run-xyz",
     outcome: { status: "ok" },
     resultText: "React 19 新特性包括: 1. Actions...",
   })

8. 通知父 Agent:
   announceSubagentCompletion({
     controllerSessionKey: "agent:default:session:main",
     resultText: "React 19 新特性包括: 1. Actions...",
   })

9. 清理:
   deleteSession("agent:default:subagent:a1b2c3d4")
```

---

## 设计洞察

### 为什么需要独立 Session？

子 agent 使用独立的 session 文件（JSONL），而不是共享父 agent 的上下文。原因：
1. **隔离**：子 agent 的工具调用不会污染父 agent 的上下文
2. **并行**：多个子 agent 可以同时执行
3. **独立模型**：子 agent 可以使用不同的（更便宜的）模型
4. **清理**：完成后可以直接删除 session 文件

### 级联 Kill 的必要性

```
父 Agent
  ├── 子 Agent A
  │     ├── 孙 Agent A1
  │     └── 孙 Agent A2
  └── 子 Agent B
```

如果只 kill 子 Agent A 而不级联，A1 和 A2 会变成孤儿——没人等待它们的结果，浪费资源。级联 kill 确保树形结构的一致性。

### Steer vs Send 的区别

| | Steer | Send |
|---|---|---|
| 中断当前执行 | 是 | 否 |
| 创建新 run | 是 | 否 |
| 用途 | 改变任务方向 | 追加信息 |
| 频率限制 | 2 秒 | 无 |

Steer 更像"重启并给新指令"，Send 更像"在当前对话中追加一条消息"。

### 与 OpenCode 的对比

| | OpenClaw 子 Agent | OpenCode Task |
|---|---|---|
| 隔离级别 | 独立 session 文件 | 独立 session（数据库） |
| 生命周期 | 完整状态机 + 重试 | 简单委派 |
| 控制能力 | kill/steer/send/list | 无 |
| 深度限制 | 可配置（默认 3） | 无 |
| 模型选择 | 可独立指定 | 继承父 agent |
| 结果通知 | 异步 announce + 重试 | 同步返回 |

OpenClaw 的子 Agent 系统远比 OpenCode 复杂，因为它需要处理：多用户并发、长时间运行、进程重启恢复等产品级场景。
