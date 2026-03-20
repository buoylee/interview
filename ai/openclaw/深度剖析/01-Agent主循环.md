# 01 - Agent 主循环：从消息到 LLM 响应

> OpenClaw 的 Agent 执行链路分三层：`agent-command.ts`（入口准备）→ `run.ts`（重试循环）→ `attempt.ts`（单轮执行）。
> 本文按数据流顺序，剖析一条消息从到达到返回结果的完整路径。

---

## 架构总览

```
消息到达
  │
  ▼
agent-command.ts: prepareAgentCommandExecution()
  │
  ├── 加载配置 + 解析 session
  ├── 模型选择 (resolveConfiguredModelRef)
  ├── 认证准备 (resolveAuthProfileOrder)
  │
  ▼
agent-command.ts: runAgentAttempt()
  │
  ├── CLI Provider? → runCliAgent()         (外部 CLI 代理)
  └── 嵌入式?      → runEmbeddedPiAgent()  (核心路径)
        │
        ▼
run.ts: runEmbeddedPiAgent() ← while(true) 重试循环
  │
  ├── 1. 认证 profile 轮换 + API key 解析
  ├── 2. 模型解析 + context window 检查
  │
  └── while(true):
        ├── runEmbeddedAttempt()  ← 单次 LLM 调用
        │
        └── 结果分支:
            ├── 正常完成 → 返回
            ├── 上下文溢出 → compaction → 重试
            ├── 认证失败 → 刷新/轮换 → 重试
            ├── thinking 不支持 → 降级 → 重试
            ├── 超时 → FailoverError
            └── 其他错误 → FailoverError
```

---

## 第一层：入口准备 agent-command.ts

源码：`agents/agent-command.ts:536-600`

```typescript
async function prepareAgentCommandExecution(
  opts: AgentCommandOpts & { senderIsOwner: boolean },
  runtime: RuntimeEnv,
) {
  const message = opts.message ?? "";
  if (!message.trim()) {
    throw new Error("Message (--message) is required");
  }
  const body = prependInternalEventContext(message, opts.internalEvents);

  // 加载配置 + 解析 secrets
  const loadedRaw = loadConfig();
  const { resolvedConfig: cfg } = await resolveCommandSecretRefsViaGateway({
    config: loadedRaw,
    commandName: "agent",
    targetIds: getAgentRuntimeCommandSecretTargetIds(),
  });

  // 模型选择
  const configuredModel = resolveConfiguredModelRef({
    cfg,
    defaultProvider: DEFAULT_PROVIDER,  // "anthropic"
    defaultModel: DEFAULT_MODEL,        // "claude-sonnet-4-20250514"
  });

  // Session 解析
  const {
    sessionId, sessionKey, sessionEntry, sessionFile,
  } = await resolveSession({
    sessionId: opts.sessionId,
    sessionKey: opts.sessionKey,
    to: opts.to,
    agentId: agentIdOverride,
    cfg,
  });

  // ... 返回准备好的参数
}
```

**关键决策点**：

1. **CLI Provider vs 嵌入式**：如果 provider 是 `claude-cli`、`codex-cli` 等，走 `runCliAgent()`（通过子进程调用外部 CLI）；否则走嵌入式路径 `runEmbeddedPiAgent()`
2. **Model Fallback 包装**：整个执行被 `runWithModelFallback()` 包裹（详见第 02 章）

```typescript
// agent-command.ts:352-534
function runAgentAttempt(params) {
  if (isCliProvider(params.providerOverride, params.cfg)) {
    return runCliAgent({...});           // 外部 CLI 路径
  }
  return runEmbeddedPiAgent({...});      // 嵌入式路径（核心）
}
```

---

## 第二层：重试循环 run.ts

源码：`agents/pi-embedded-runner/run.ts:266-1707`

### 函数签名

```typescript
export async function runEmbeddedPiAgent(
  params: RunEmbeddedPiAgentParams,
): Promise<EmbeddedPiRunResult>
```

### 并发控制：Lane 排队

```typescript
const sessionLane = resolveSessionLane(params.sessionKey?.trim() || params.sessionId);
const globalLane = resolveGlobalLane(params.lane);

return enqueueSession(() =>
  enqueueGlobal(async () => {
    // ... 实际执行
  }),
);
```

每个 session 有独立的队列（sessionLane），同时还有全局队列（globalLane）。请求先排 session 队列，再排全局队列。保证：
- 同一 session 的请求串行执行
- 全局并发受控

### 初始化阶段

```typescript
// 1. 插件 hook：before_model_resolve
if (hookRunner?.hasHooks("before_model_resolve")) {
  modelResolveOverride = await hookRunner.runBeforeModelResolve(
    { prompt: params.prompt }, hookCtx,
  );
}

// 2. 模型解析
const { model, error } = await resolveModelAsync(provider, modelId, agentDir, params.config);

// 3. Context Window 检查
const ctxInfo = resolveContextWindowInfo({
  cfg: params.config, provider, modelId,
  modelContextWindow: runtimeModel.contextWindow,
  defaultTokens: DEFAULT_CONTEXT_TOKENS,  // 128K
});
// 太小直接拒绝
if (ctxGuard.shouldBlock) {
  throw new FailoverError("Model context window too small", { reason: "unknown" });
}

// 4. 认证 Profile 选择
const profileOrder = resolveAuthProfileOrder({
  cfg: params.config, store: authStore, provider,
  preferredProfile: preferredProfileId,
});
```

### 认证 Profile 轮换

```typescript
// run.ts:762-794
while (profileIndex < profileCandidates.length) {
  const candidate = profileCandidates[profileIndex];
  const inCooldown = candidate && isProfileInCooldown(authStore, candidate);
  if (inCooldown) {
    // 跳过冷却中的 profile（除非是 transient cooldown probe）
    profileIndex += 1;
    continue;
  }
  await applyApiKeyInfo(profileCandidates[profileIndex]);  // 设置 API key
  break;
}
```

**Profile 生命周期**：
- 认证成功 → `markAuthProfileGood()`
- 认证失败 → `markAuthProfileFailure()` → 进入冷却期
- 所有 profile 冷却 → 探测或报错

### 运行时认证刷新

```typescript
// run.ts:476-593 — OAuth token 过期自动刷新
const refreshRuntimeAuth = async (reason: string): Promise<void> => {
  const preparedAuth = await prepareProviderRuntimeAuth({
    provider: runtimeModel.provider,
    apiKey: runtimeAuthState.sourceApiKey,
    // ...
  });
  authStorage.setRuntimeApiKey(runtimeModel.provider, preparedAuth.apiKey);
  runtimeAuthState.expiresAt = preparedAuth.expiresAt;
};

// 定时刷新：过期前 5 分钟
const scheduleRuntimeAuthRefresh = (): void => {
  const refreshAt = runtimeAuthState.expiresAt - RUNTIME_AUTH_REFRESH_MARGIN_MS; // 5min
  const delayMs = Math.max(RUNTIME_AUTH_REFRESH_MIN_DELAY_MS, refreshAt - Date.now());
  runtimeAuthState.refreshTimer = setTimeout(() => {
    refreshRuntimeAuth("scheduled").then(() => scheduleRuntimeAuthRefresh());
  }, delayMs);
};
```

### 主循环：while(true)

```typescript
// run.ts:887-920
const MAX_RUN_LOOP_ITERATIONS = resolveMaxRunRetryIterations(profileCandidates.length);
// BASE(24) + profileCount * 8, clamped to [32, 160]

while (true) {
  if (runLoopIterations >= MAX_RUN_LOOP_ITERATIONS) {
    return { payloads: [{ text: "Request failed after repeated internal retries.", isError: true }] };
  }
  runLoopIterations += 1;

  // 调用单次尝试
  const attempt = await runEmbeddedAttempt({...});

  // 根据 attempt 结果决定下一步（见下文）
}
```

### 结果处理分支

**1. 上下文溢出 → Compaction**

```typescript
// run.ts:1068-1275
if (
  !attempt.aborted &&
  (attempt.promptError
    ? isLikelyContextOverflowError(attempt.promptError.message)
    : isCompactionFailureError(lastAssistant))
) {
  if (overflowCompactionAttempts >= MAX_OVERFLOW_COMPACTION_ATTEMPTS) { // 3
    // 尝试截断工具结果
    if (!toolResultTruncationAttempted) {
      const truncated = await truncateOversizedToolResultsInSession(sessionManager);
      if (truncated) { toolResultTruncationAttempted = true; continue; }
    }
    // 都不行，报错
    return { payloads: [{ text: "...", isError: true }] };
  }
  overflowCompactionAttempts += 1;

  // 执行 compaction
  const compacted = await contextEngine.compact({
    sessionFile: params.sessionFile,
    observedTokens: extractObservedOverflowTokenCount(errorText),
    // ...
  });
  if (compacted?.ok) continue;  // 压缩成功，重试
}
```

**2. 认证失败 → 刷新/轮换**

```typescript
// run.ts:1315-1410
if (isAuthAssistantError(assistantText) || isAuthAssistantError(attempt.promptError?.message)) {
  // 先尝试 runtime auth 刷新（OAuth token 可能过期）
  const retried = await maybeRefreshRuntimeAuthForAuthError(errorText, runtimeAuthRetry);
  if (retried) { authRetryPending = true; continue; }

  // 刷新失败，标记当前 profile 失败
  await maybeMarkAuthProfileFailure({ profileId: lastProfileId, reason: "auth" });

  // 轮换到下一个 profile
  const advanced = await advanceAuthProfile();
  if (advanced) continue;

  // 没有更多 profile → FailoverError（外层切换模型）
  throw new FailoverError("Authentication failed", { reason: "auth" });
}
```

**3. Thinking Level 降级**

```typescript
// run.ts:1446-1456
if (someAssistantTextIndicatesThinkingNotSupported) {
  const fallback = pickFallbackThinkingLevel(thinkLevel, attemptedThinking);
  if (fallback && !attemptedThinking.has(fallback)) {
    thinkLevel = fallback;  // 降级（如 "high" → "medium" → "off"）
    continue;
  }
}
```

**4. 正常完成 → 返回**

```typescript
// run.ts: 正常路径
if (!attempt.promptError && !isFailoverAssistantError(lastAssistant)) {
  mergeUsageIntoAccumulator(usageAccumulator, normalizeUsage(lastAssistant?.usage));
  markAuthProfileGood(authStore, lastProfileId);  // 标记认证成功

  return {
    payloads: buildEmbeddedRunPayloads({
      attempt, model, provider, thinkLevel,
    }),
    meta: {
      durationMs: Date.now() - started,
      agentMeta: { sessionId, provider, model: model.id, usage: toNormalizedUsage(usageAccumulator) },
    },
  };
}
```

---

## 第三层：单轮执行 attempt.ts

源码：`agents/pi-embedded-runner/run/attempt.ts:1393-2936`

这是最核心的函数，做了四件事：

### Phase 1: SessionManager + 工具准备

```typescript
// 打开会话文件
sessionManager = guardSessionManager(
  SessionManager.open(params.sessionFile),
  { agentId, sessionKey: params.sessionKey },
);

// 创建工具
const rawTools = createOpenClawCodingTools({
  workspaceDir: effectiveWorkspace,
  agentDir,
  sessionId: params.sessionId,
  sessionKey: params.sessionKey,
  config: params.config,
  // ...
});
// + MCP 工具 + LSP 工具 + 客户端工具

// 对 Google 模型做特殊处理
if (isGoogleProvider) {
  sanitizeToolsForGoogle(allCustomTools);
}
```

### Phase 2: 系统 Prompt 构建

```typescript
const appendPrompt = buildEmbeddedSystemPrompt({
  workspaceDir: effectiveWorkspace,
  defaultThinkLevel: params.thinkLevel,
  tools: effectiveTools,
  ownerNumbers: params.config.owner_numbers,
  userTimezone: params.config.user_timezone,
  skillsPrompt,
  sandboxInfo,
  runtimeInfo: {
    host: os.hostname(),
    os: `${os.type()} ${os.release()}`,
    model: `${params.provider}/${params.model.id}`,
    shell: detectRuntimeShell(),
    messageChannels: listDeliverableMessageChannels(params.config),
  },
  // ... 更多参数
});

// 创建 pi-coding-agent 会话
({ session } = await createAgentSession({
  cwd: resolvedWorkspace,
  agentDir,
  model: params.model,
  thinkingLevel: mapThinkingLevel(params.thinkLevel),
  tools: builtInTools,
  customTools: allCustomTools,
  sessionManager,
  settingsManager,
}));

// 注入系统 prompt
applySystemPromptOverrideToSession(session, systemPromptText);
```

### Phase 3: 多层 StreamFn 包装

`streamFn` 是实际调用 LLM 的函数。OpenClaw 在基础 streamFn 上包了多层适配器：

```
基础层: streamSimple (pi-ai)
  │
  ├── [Ollama] createConfiguredOllamaStreamFn()     ← Ollama 适配
  ├── [OpenAI] createOpenAIWebSocketStreamFn()       ← OpenAI Responses API (WebSocket)
  │
  ├── wrapStreamFnTrimToolCallNames()                ← 修复工具名空格
  ├── wrapStreamFnRepairMalformedToolCallArguments() ← 修复 Kimi/xAI 格式
  ├── wrapStreamFnDecodeXaiToolCallArguments()       ← HTML entity 解码
  │
  ├── dropThinkingBlocks()                           ← 清理 Anthropic thinking 块
  ├── sanitizeToolCallIdsForCloudCodeAssist()        ← Mistral ID 格式修复
  │
  └── [Anthropic] 注入 prompt caching TTL
```

**每层都是一个函数包装器**，形如：

```typescript
// 工具名修剪示例
const originalStreamFn = activeSession.agent.streamFn;
activeSession.agent.streamFn = (model, context, options) => {
  // 修改 context.messages 中的工具调用名
  const cleanedMessages = trimToolCallNames(context.messages, allowedToolNames);
  return originalStreamFn(model, { ...context, messages: cleanedMessages }, options);
};
```

### Phase 4: LLM 调用 + 事件订阅

```typescript
// 1. 订阅事件（流式输出、工具结果、压缩等）
const subscription = subscribeEmbeddedPiSession({
  session: activeSession,
  onToolResult: params.onToolResult,
  onPartialReply: params.onPartialReply,
});

// 2. before_prompt_build 插件 hook
const hookResult = await resolvePromptBuildHookResult({...});
if (hookResult?.prependContext) {
  effectivePrompt = `${hookResult.prependContext}\n\n${effectivePrompt}`;
}

// 3. 加载图片
const imageResult = await detectAndLoadPromptImages({...});

// 4. 核心调用 — 这里阻塞直到 LLM 完成所有工具循环
if (imageResult.images.length > 0) {
  await abortable(activeSession.prompt(effectivePrompt, { images: imageResult.images }));
} else {
  await abortable(activeSession.prompt(effectivePrompt));
}
```

**`activeSession.prompt()` 内部**（由 pi-coding-agent 实现）：
1. 将用户消息加入 session
2. 调用 `streamFn(model, context, options)` 获取 LLM 响应
3. 如果 LLM 返回工具调用 → 自动执行工具 → 将结果加入 session → 再次调用 LLM
4. 重复直到 LLM 返回纯文本（无工具调用）

### Phase 5: 返回结果

```typescript
return {
  aborted,                    // 是否被中断
  timedOut,                   // 是否超时
  timedOutDuringCompaction,   // 是否在压缩时超时
  promptError,                // prompt 阶段的错误
  sessionIdUsed,              // 使用的 session ID
  messagesSnapshot,           // 消息快照
  assistantTexts,             // 助手回复文本列表
  toolMetas,                  // 工具调用元数据
  lastAssistant,              // 最后一条助手消息
  lastToolError,              // 最后一个工具错误
  attemptUsage,               // token 用量
  compactionCount,            // 压缩次数
  clientToolCall,             // 是否有客户端工具调用
  yieldDetected,              // 是否触发了 sessions_yield
};
```

---

## 上下文压缩：compact.ts

源码：`agents/pi-embedded-runner/compact.ts:384-1119`

当 LLM 报告上下文溢出时，执行压缩：

```typescript
export async function compactEmbeddedPiSessionDirect(
  params: CompactEmbeddedPiSessionParams,
): Promise<EmbeddedPiCompactResult> {
  // 1. 用同样的 SessionManager + 工具 + prompt 打开会话
  // 2. 采集压缩前指标
  const preMetrics = summarizeCompactionMessages(session.messages);

  // 3. 调用 pi-coding-agent 的 compact()，带安全超时
  const result = await compactWithSafetyTimeout(
    () => session.compact(params.customInstructions),
    compactionTimeoutMs,
    { abortSignal, onCancel: () => session.abortCompaction() },
  );

  // 4. 采集压缩后指标
  const postMetrics = summarizeCompactionMessages(session.messages);
  const delta = {
    messages: preMetrics.messageCount - postMetrics.messageCount,
    tokens: preMetrics.estimatedTokens - postMetrics.estimatedTokens,
  };

  // 5. 触发 after_compaction hook
  if (hookRunner?.hasHooks("after_compaction")) {
    await hookRunner.runAfterCompaction({ messageCount, compactedCount, tokenCount }, ctx);
  }

  return { ok: true, compacted: true, result: { summary, tokensBefore, tokensAfter } };
}
```

**压缩策略**：
- 由 pi-coding-agent 内部实现，使用 LLM 对旧消息生成摘要
- 删除中间工具结果、system 消息、自定义条目
- 保留摘要 + 最近的消息
- 安全超时：如果压缩耗时过长，中断并回退

---

## 数据流总结：一次完整请求

以用户发送 `"帮我查一下明天的天气"` 为例：

```
1. agent-command.ts
   ├── message = "帮我查一下明天的天气"
   ├── model = anthropic/claude-sonnet-4-20250514
   ├── session = sessions/abc123.jsonl
   └── auth profile = "default" (API key)

2. run.ts — runEmbeddedPiAgent()
   ├── context window = 200K tokens
   ├── profile candidates = ["default", "backup-oauth"]
   ├── apply API key for "default"
   └── while(true) iteration 1:

3. attempt.ts — runEmbeddedAttempt()
   ├── SessionManager.open("sessions/abc123.jsonl")
   ├── 工具: [read, write, exec, grep, web_fetch, web_search, memory_search, ...]
   ├── system prompt: [Identity + Tooling + Skills + Memory + Workspace + Runtime]
   ├── streamFn: streamSimple → trimToolNames → dropThinking
   │
   ├── activeSession.prompt("帮我查一下明天的天气")
   │   ├── LLM → "我来搜索天气信息" + tool_call(web_search, {query: "明天天气"})
   │   ├── 执行 web_search → 返回结果
   │   ├── LLM → "根据搜索结果，明天天气是..."
   │   └── finish (no more tool calls)
   │
   └── return { assistantTexts: ["根据搜索结果，明天天气是..."], ... }

4. run.ts — 正常完成
   ├── markAuthProfileGood("default")
   ├── buildEmbeddedRunPayloads() → [{text: "根据搜索结果，明天天气是..."}]
   └── return { payloads, meta: { durationMs, usage } }

5. agent-command.ts
   └── deliverAgentCommandResult() → 发送到消息渠道
```

---

## 设计洞察

### 为什么用 pi-coding-agent 而不是自研？

OpenClaw 选择嵌入 `@mariozechner/pi-coding-agent` 作为底层 Agent 引擎，在此之上做大量定制。好处是：
- 不需要自己实现工具循环、消息管理、会话持久化
- 专注在产品层的差异化（多渠道、认证、重试、UI）

代价是：
- 对底层行为的控制力受限（需要通过 hook/wrapper 间接修改）
- streamFn 包装层叠（7+ 层），调试困难

### 重试策略的层次感

```
外层: runWithModelFallback() — 模型级重试
  中层: while(true) in run.ts — 操作级重试（认证、压缩、thinking 降级）
    内层: pi-coding-agent — 工具循环（自动重试工具调用）
```

每层只处理自己能处理的错误，无法处理的向上抛。这是一个典型的**责任链模式**。

### 并发模型

- 每个 session 有独立的 Lane（串行队列）
- 全局有一个 Lane（控制总并发）
- 双层排队保证：同一 session 不会并发执行，全局不会过载
