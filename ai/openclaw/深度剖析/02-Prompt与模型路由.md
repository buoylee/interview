# 02 - Prompt 与模型路由：系统指令构建 + 多模型降级

> 系统 prompt 决定了 Agent 的"人格"和能力边界。
> 模型路由决定了用哪个 LLM、失败了怎么切换。
> 本文剖析 `system-prompt.ts` 的 16+ 区段构建，以及 `model-selection.ts` + `model-fallback.ts` 的降级链。

---

## 系统 Prompt 架构

源码：`agents/system-prompt.ts:1-719`

### Prompt 模式

```typescript
export type PromptMode = "full" | "minimal" | "none";
// full: 主 agent，包含所有区段
// minimal: 子 agent，精简版（只有 Tooling + Workspace + Runtime）
// none: 仅基础身份行
```

### 区段列表

`buildAgentSystemPrompt()` 构建的完整 prompt 包含以下区段（按顺序）：

```
┌─────────────────────────────────────────────┐
│ 身份声明                                     │
│ "You are a personal assistant running       │
│  inside OpenClaw."                          │
├─────────────────────────────────────────────┤
│ ## Tooling                                  │
│  · 可用工具列表 (read/write/exec/grep...)   │
│  · 叙事风格指引                              │
│  · 审批处理规则                              │
│  · 安全规则                                  │
├─────────────────────────────────────────────┤
│ ## Tool Call Style                          │
│  · 何时叙事 vs 直接调用                      │
├─────────────────────────────────────────────┤
│ ## Skills (mandatory)             [条件]    │
│  · 可用 skill 列表                          │
│  · skill 选择规则                            │
├─────────────────────────────────────────────┤
│ ## Memory Recall                  [条件]    │
│  · memory_search 使用指引                   │
│  · 引用模式 (on/off)                        │
├─────────────────────────────────────────────┤
│ ## Authorized Senders             [条件]    │
│  · 允许的发送者标识                          │
├─────────────────────────────────────────────┤
│ ## Time                           [条件]    │
│  · 用户时区 + 当前时间                       │
├─────────────────────────────────────────────┤
│ ## Messaging                      [渠道相关] │
│  · 消息工具能力                              │
│  · Telegram 表情/按钮指引                    │
│  · Signal 表情指引                           │
├─────────────────────────────────────────────┤
│ ## Silent Replies                 [条件]    │
│  · SILENT_REPLY_TOKEN 使用规则              │
├─────────────────────────────────────────────┤
│ ## Heartbeats                     [条件]    │
│  · HEARTBEAT_OK 发射规则                    │
├─────────────────────────────────────────────┤
│ ## Model Aliases                  [条件]    │
│  · provider/model 别名映射                  │
├─────────────────────────────────────────────┤
│ ## Workspace                                │
│  · 工作目录路径                              │
│  · 沙箱信息（如果启用）                      │
├─────────────────────────────────────────────┤
│ ## Runtime                                  │
│  · host, OS, model, shell                   │
│  · channel capabilities                     │
│  · thinking level                           │
├─────────────────────────────────────────────┤
│ # Project Context                 [条件]    │
│  · bootstrap 文件内容 (SOUL.md 等)          │
├─────────────────────────────────────────────┤
│ ## Reasoning Format               [条件]    │
│  · <think>...</think> 格式指引              │
└─────────────────────────────────────────────┘
```

### Skills 区段

```typescript
// system-prompt.ts:20-36
function buildSkillsSection(params: { skillsPrompt?: string; readToolName: string }) {
  const trimmed = params.skillsPrompt?.trim();
  if (!trimmed) return [];
  return [
    "## Skills (mandatory)",
    "Before replying: scan <available_skills> <description> entries.",
    `- If exactly one skill clearly applies: read its SKILL.md at <location> with \`${params.readToolName}\`, then follow it.`,
    "- If multiple could apply: choose the most specific one, then read/follow it.",
    "- If none clearly apply: do not read any SKILL.md.",
    "Constraints: never read more than one skill up front; only read after selecting.",
    trimmed,
  ];
}
```

**Skill 的工作方式**：不是把 skill 内容直接注入 prompt，而是告诉 Agent skill 的位置，让 Agent 自己用 read 工具去读。这样避免 prompt 膨胀。

### Memory 区段

```typescript
// system-prompt.ts:38-64
function buildMemorySection(params: {
  isMinimal: boolean;
  availableTools: Set<string>;
  citationsMode?: MemoryCitationsMode;
}) {
  if (params.isMinimal) return [];
  if (!params.availableTools.has("memory_search") && !params.availableTools.has("memory_get")) {
    return [];
  }
  const lines = [
    "## Memory Recall",
    "Before answering anything about prior work, decisions, dates, people, preferences, or todos: " +
    "run memory_search on MEMORY.md + memory/*.md; then use memory_get to pull only the needed lines.",
  ];
  if (params.citationsMode === "off") {
    lines.push("Citations are disabled: do not mention file paths or line numbers in replies.");
  } else {
    lines.push("Citations: include Source: <path#line> when it helps the user verify memory snippets.");
  }
  return lines;
}
```

### 身份保护

```typescript
// system-prompt.ts:73-95
function buildOwnerIdentityLine(ownerNumbers, ownerDisplay, ownerDisplaySecret?) {
  // 支持两种模式:
  // "raw": 直接显示号码
  // "hash": HMAC-SHA256 哈希（前 12 位）— 防止 prompt 泄露真实号码
  const displayOwnerNumbers = ownerDisplay === "hash"
    ? normalized.map(id => formatOwnerDisplayId(id, ownerDisplaySecret))
    : normalized;
  return `Authorized senders: ${displayOwnerNumbers.join(", ")}.`;
}
```

---

## 模型选择：model-selection.ts

源码：`agents/model-selection.ts:1-675`

### 模型引用解析

```typescript
// model-selection.ts:140-155
export function parseModelRef(raw: string, defaultProvider: string): ModelRef {
  // "anthropic/claude-sonnet-4" → { provider: "anthropic", model: "claude-sonnet-4" }
  // "claude-sonnet-4" → { provider: defaultProvider, model: "claude-sonnet-4" }
  const parts = raw.split("/");
  if (parts.length >= 2) {
    return { provider: parts[0], model: parts.slice(1).join("/") };
  }
  return { provider: defaultProvider, model: raw };
}
```

### Provider 归一化

```typescript
// model-selection.ts:134-138
export function normalizeModelRef(provider: string, model: string): ModelRef {
  // 处理各种别名:
  // "opus-4.5" → "claude-opus-4-5"
  // "gemini-2.5-pro" → Google 归一化
  // openrouter native model → 添加前缀
  // Vercel AI Gateway Claude → 标准化
  return { provider: normalizeProviderId(provider), model: normalizedModel };
}
```

### 配置模型解析

```typescript
// model-selection.ts:271-335
export function resolveConfiguredModelRef(params: {
  cfg: OpenClawConfig;
  defaultProvider: string;  // "anthropic"
  defaultModel: string;     // "claude-sonnet-4-20250514"
}): { provider: string; model: string } {
  // 优先级:
  // 1. config.model (如 "anthropic/claude-opus-4")
  // 2. config.provider + config.model (分开配置)
  // 3. 别名解析 (config 中定义的 alias → 真实模型)
  // 4. 默认值 (anthropic/claude-sonnet-4-20250514)
}
```

### 别名系统

```typescript
// model-selection.ts:220-246
export function buildModelAliasIndex(params): ModelAliasIndex {
  // config.model_aliases: { "fast": "anthropic/claude-haiku-3-5", "smart": "anthropic/claude-opus-4" }
  // 构建双向索引:
  // aliasToModel: "fast" → { provider: "anthropic", model: "claude-haiku-3-5" }
  // modelToAliases: "anthropic/claude-haiku-3-5" → ["fast"]
}
```

### 子 Agent 模型选择

```typescript
// model-selection.ts:389-407
export function resolveSubagentSpawnModelSelection(params): ModelRef {
  // 优先级:
  // 1. 显式 override (spawn 参数指定)
  // 2. agent 配置的默认模型
  // 3. 全局默认模型
}
```

---

## 模型回退链：model-fallback.ts

源码：`agents/model-fallback.ts:1-828`

### 核心函数

```typescript
// model-fallback.ts:511-775
export async function runWithModelFallback<T>(params: {
  run: (provider: string, model: string, opts?: ModelFallbackRunOptions) => Promise<T>;
  provider: string;
  model: string;
  fallbacks: Array<{ provider: string; model: string }>;
  isContextOverflowError?: (err: unknown) => boolean;
}): Promise<{ result: T; provider: string; model: string; attempts: FallbackAttempt[] }> {
  const candidates = resolveFallbackCandidates(params);

  for (const candidate of candidates) {
    try {
      const result = await params.run(candidate.provider, candidate.model, runOpts);
      return { result, provider: candidate.provider, model: candidate.model, attempts };
    } catch (err) {
      // 上下文溢出不可回退 — 直接向上抛
      if (params.isContextOverflowError?.(err)) throw err;

      attempts.push({ provider: candidate.provider, model: candidate.model, error: err });
      // 继续尝试下一个候选
    }
  }

  throw lastError;  // 所有候选都失败
}
```

### 候选链构建

```typescript
// model-fallback.ts:258-333
function resolveFallbackCandidates(params): ModelCandidate[] {
  const candidates: ModelCandidate[] = [];

  // 1. 主模型
  candidates.push({ provider: params.provider, model: params.model });

  // 2. 配置的 fallback 列表
  for (const fb of params.fallbacks) {
    const key = modelKey(fb.provider, fb.model);
    if (!seen.has(key)) {
      candidates.push(fb);
      seen.add(key);
    }
  }

  // 3. 全局默认（如果不在候选中）
  const defaultKey = modelKey(DEFAULT_PROVIDER, DEFAULT_MODEL);
  if (!seen.has(defaultKey)) {
    candidates.push({ provider: DEFAULT_PROVIDER, model: DEFAULT_MODEL });
  }

  return candidates;
}
```

### 冷却探测

当所有认证 profile 都在冷却期时，是否应该尝试？

```typescript
// model-fallback.ts:384-407
function shouldProbePrimaryDuringCooldown(params): boolean {
  // 条件:
  // 1. 是主模型（不是 fallback）
  // 2. 有配置的 fallback（探测失败还有退路）
  // 3. 距上次探测 > 30 秒
  // 4. 接近冷却期结束（< 2 分钟）

  const timeSinceLastProbe = Date.now() - lastProbeTimestamp;
  if (timeSinceLastProbe < 30_000) return false;

  const nearExpiry = cooldownExpiresAt - Date.now() < 2 * 60_000;
  return nearExpiry || timeSinceLastProbe > 60_000;
}
```

### 冷却决策

```typescript
// model-fallback.ts:434-509
function resolveCooldownDecision(params): CooldownDecision {
  // "skip": 持久性问题（auth 失败），跳过
  // "probe": 瞬态问题（rate limit），探测一下
  // "attempt": 同 provider 的兄弟模型冷却，可能我们这个没问题

  if (reason === "rate_limit" || reason === "overloaded") {
    if (isPrimary && hasFallbacks) return "probe";
    return "skip";
  }
  if (reason === "auth" || reason === "billing") {
    return "skip";  // 认证/账单问题不会自愈
  }
  return "attempt";  // 未知原因，试试看
}
```

---

## 多层 StreamFn 包装

源码：`agents/pi-embedded-runner/run/attempt.ts:1944-2127`

这是 OpenClaw 最有特色的设计之一：通过层层包装 `streamFn`，适配不同 LLM provider 的行为差异。

```
Layer 0: streamSimple (pi-ai)
  ↓ 基础 HTTP 流式调用
Layer 1: [Ollama] createConfiguredOllamaStreamFn
  ↓ Ollama 本地模型适配
Layer 2: [OpenAI WS] createOpenAIWebSocketStreamFn
  ↓ OpenAI Responses API WebSocket 适配
Layer 3: wrapStreamFnTrimToolCallNames
  ↓ 修复 " read " → "read" (空格问题)
Layer 4: [Kimi/xAI] wrapStreamFnRepairMalformedToolCallArguments
  ↓ 修复畸形 JSON 参数
Layer 5: [xAI/Grok] wrapStreamFnDecodeXaiToolCallArguments
  ↓ HTML entity 解码 (&amp; → &)
Layer 6: [Anthropic] dropThinkingBlocks
  ↓ 清理后续请求中的 thinking 块
Layer 7: [Mistral] sanitizeToolCallIdsForCloudCodeAssist
  ↓ ID 格式修复 (Mistral 要求特定格式)
Layer 8: [Anthropic] appendCacheTtlTimestamp
  ↓ prompt caching TTL 时间戳
```

**每一层都只处理一个问题**，这是经典的**装饰器模式**。每层的实现形式都一样：

```typescript
const inner = activeSession.agent.streamFn;
activeSession.agent.streamFn = (model, context, options) => {
  // 修改 context 或 options
  const modifiedContext = transform(context);
  return inner(model, modifiedContext, options);
};
```

---

## 设计洞察

### Prompt 的"按需注入"策略

OpenClaw 不像 OpenCode 那样把所有信息堆在 system prompt 里。它采用**按需注入**：
- Skills → 只给位置，Agent 自己读
- Memory → 只给指引，Agent 自己搜索
- Bootstrap 文件 → 有预算限制（`resolveBootstrapMaxChars`），超出截断

这在 200K token 上下文窗口下是合理的——让 Agent 自己决定需要什么信息，而不是把所有信息都塞进去。

### 模型回退 vs OpenCode 的做法

| | OpenClaw | OpenCode |
|---|---|---|
| 回退范围 | 完整模型切换（anthropic → openai） | 无模型回退 |
| 认证回退 | 多 profile 轮换 + 冷却探测 | 无 |
| Thinking 降级 | high → medium → off | 无 |
| 上下文溢出 | compaction → 工具截断 → 报错 | prune → compaction |

OpenClaw 的回退策略远比 OpenCode 复杂，因为它是一个需要 7×24 运行的助手——不能因为一次 API 限流就停止服务。

### StreamFn 包装的真实动机

每一层包装都对应一个**真实的 LLM bug 或差异**：
- Kimi 返回畸形 JSON → 需要修复
- xAI 对工具参数做 HTML entity 编码 → 需要解码
- Anthropic 的 thinking 块在后续请求中会导致错误 → 需要清理
- Mistral 对工具调用 ID 有严格格式要求 → 需要修复

这些不是过度工程，而是**多模型支持的真实代价**。
