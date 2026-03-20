# 02 - Prompt 组装与系统指令：从配置到 LLM 输入

> 用户发一句话，LLM 收到的却是一个精心组装的多层消息序列。
> 本文剖析 system prompt 的 4 层来源、用户消息的预处理管线、以及 Agent 如何影响整个 prompt 结构。

---

## Prompt 的分层架构

```
发给 LLM 的消息序列:

┌─────────────────────────────────────────────┐
│ system[0]: 模型专用 prompt + agent prompt   │  ← SystemPrompt.provider() / agent.prompt
│            + 自定义 system                  │
│            + 用户消息中的 system 字段        │
├─────────────────────────────────────────────┤
│ system[1]: 环境信息                         │  ← SystemPrompt.environment()
│            (模型名、工作目录、平台、日期)     │
├─────────────────────────────────────────────┤
│ system[2]: Skills 列表                      │  ← SystemPrompt.skills()
├─────────────────────────────────────────────┤
│ system[3..N]: AGENTS.md / CLAUDE.md / URL   │  ← InstructionPrompt.system()
├─────────────────────────────────────────────┤
│ 历史消息（user/assistant 交替）              │  ← MessageV2.toModelMessages()
├─────────────────────────────────────────────┤
│ 最新用户消息                                │
└─────────────────────────────────────────────┘
```

---

## 第 1 层：模型专用 Prompt

源码：`session/system.ts:22-30`

```typescript
export function provider(model: Provider.Model) {
    if (model.api.id.includes("gpt-5")) return [PROMPT_CODEX]
    if (model.api.id.includes("gpt-") || model.api.id.includes("o1") || model.api.id.includes("o3"))
        return [PROMPT_BEAST]
    if (model.api.id.includes("gemini-")) return [PROMPT_GEMINI]
    if (model.api.id.includes("claude")) return [PROMPT_ANTHROPIC]
    if (model.api.id.toLowerCase().includes("trinity")) return [PROMPT_TRINITY]
    return [PROMPT_DEFAULT]
}
```

**不同模型使用不同的 system prompt**。这些是 `.txt` 文件，包含该模型系列的最佳实践提示词（工具使用规范、输出格式偏好等）。

在 `LLM.stream()` 中的组装逻辑：

```typescript
// llm.ts:68-81
const system = []
system.push(
    [
        // agent prompt 优先于 provider prompt
        ...(input.agent.prompt ? [input.agent.prompt] : isCodex ? [] : SystemPrompt.provider(input.model)),
        // 自定义 system
        ...input.system,
        // 用户消息中的 system 字段
        ...(input.user.system ? [input.user.system] : []),
    ]
        .filter((x) => x)
        .join("\n"),
)
```

**优先级**：
1. Agent 自带的 `prompt`（如 explore agent 的专用提示词）→ 完全替代 provider prompt
2. 如果 agent 没有自定义 prompt → 使用 provider prompt（按模型匹配）
3. 附加调用方传入的 `system`（环境、技能、指令等）
4. 附加用户消息中的 `system` 字段

---

## 第 2 层：环境信息

源码：`session/system.ts:32-57`

```typescript
export async function environment(model: Provider.Model) {
    const project = Instance.project
    return [
        [
            `You are powered by the model named ${model.api.id}. The exact model ID is ${model.providerID}/${model.api.id}`,
            `Here is some useful information about the environment you are running in:`,
            `<env>`,
            `  Working directory: ${Instance.directory}`,
            `  Workspace root folder: ${Instance.worktree}`,
            `  Is directory a git repo: ${project.vcs === "git" ? "yes" : "no"}`,
            `  Platform: ${process.platform}`,
            `  Today's date: ${new Date().toDateString()}`,
            `</env>`,
        ].join("\n"),
    ]
}
```

让 LLM 知道它在哪里运行、操作的是什么项目。

---

## 第 3 层：Skills

源码：`session/system.ts:59-71`

```typescript
export async function skills(agent: Agent.Info) {
    if (PermissionNext.disabled(["skill"], agent.permission).has("skill")) return

    const list = await Skill.available(agent)
    return [
        "Skills provide specialized instructions and workflows for specific tasks.",
        "Use the skill tool to load a skill when a task matches its description.",
        Skill.fmt(list, { verbose: true }),
    ].join("\n")
}
```

如果 agent 的权限允许使用 skill 工具，就把可用的 skill 列表注入到 system prompt 中。

---

## 第 4 层：Instruction 文件

源码：`session/instruction.ts:72-142`

```typescript
export async function systemPaths() {
    const paths = new Set<string>()

    // 1. 项目目录中的 AGENTS.md / CLAUDE.md / CONTEXT.md（向上查找）
    if (!Flag.OPENCODE_DISABLE_PROJECT_CONFIG) {
        for (const file of FILES) {
            const matches = await Filesystem.findUp(file, Instance.directory, Instance.worktree)
            if (matches.length > 0) {
                matches.forEach((p) => paths.add(path.resolve(p)))
                break  // 只使用第一个找到的文件类型
            }
        }
    }

    // 2. 全局 AGENTS.md 或 ~/.claude/CLAUDE.md
    for (const file of globalFiles()) {
        if (await Filesystem.exists(file)) {
            paths.add(path.resolve(file))
            break
        }
    }

    // 3. 配置中指定的额外指令文件（本地或 URL）
    if (config.instructions) {
        for (let instruction of config.instructions) {
            if (instruction.startsWith("https://") || instruction.startsWith("http://")) continue
            // 处理 ~ 路径、glob 模式等
            const matches = path.isAbsolute(instruction)
                ? await Glob.scan(...)
                : await resolveRelative(instruction)
            matches.forEach((p) => paths.add(path.resolve(p)))
        }
    }
    return paths
}

export async function system() {
    const paths = await systemPaths()
    // 读取所有文件
    const files = Array.from(paths).map(async (p) => {
        const content = await Filesystem.readText(p).catch(() => "")
        return content ? "Instructions from: " + p + "\n" + content : ""
    })
    // 读取 URL
    const fetches = urls.map((url) =>
        fetch(url, { signal: AbortSignal.timeout(5000) })
            .then((res) => res.ok ? res.text() : "")
            .then((x) => x ? "Instructions from: " + url + "\n" + x : ""),
    )
    return Promise.all([...files, ...fetches]).then((result) => result.filter(Boolean))
}
```

**指令来源优先级**：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `AGENTS.md` / `CLAUDE.md` / `CONTEXT.md` | 项目目录向上查找，找到一种就停 |
| 2 | `~/.config/opencode/AGENTS.md` 或 `~/.claude/CLAUDE.md` | 全局配置 |
| 3 | `config.instructions` 中的文件路径或 URL | 用户自定义 |

**动态指令发现**（`instruction.ts:168-191`）：

当 read 工具读取文件时，还会沿着文件路径向上查找 AGENTS.md：

```typescript
export async function resolve(messages, filepath, messageID) {
    const system = await systemPaths()
    const already = loaded(messages)
    const results = []

    let current = path.dirname(filepath)
    const root = path.resolve(Instance.directory)

    while (current.startsWith(root) && current !== root) {
        const found = await find(current)
        // 如果找到了指令文件，且不是系统级的，且还没加载过
        if (found && !system.has(found) && !already.has(found) && !isClaimed(messageID, found)) {
            claim(messageID, found)
            const content = await Filesystem.readText(found)
            results.push({ filepath: found, content: "Instructions from: " + found + "\n" + content })
        }
        current = path.dirname(current)
    }
    return results
}
```

这意味着当 LLM 读取 `src/components/Button.tsx` 时，如果 `src/components/AGENTS.md` 存在，它会被自动注入到上下文中。

---

## Agent 系统

源码：`agent/agent.ts:24-252`

### Agent 定义

```typescript
export const Info = z.object({
    name: z.string(),
    description: z.string().optional(),
    mode: z.enum(["subagent", "primary", "all"]),
    permission: PermissionNext.Ruleset,
    model: z.object({ modelID, providerID }).optional(),
    variant: z.string().optional(),
    prompt: z.string().optional(),        // ← 自定义 system prompt
    options: z.record(z.string(), z.any()),
    temperature: z.number().optional(),
    topP: z.number().optional(),
    steps: z.number().int().positive().optional(),  // ← 最大步数限制
})
```

### 内置 Agent

| Agent | Mode | 用途 | 权限特点 |
|-------|------|------|---------|
| `build` | primary | 默认 agent，执行工具 | 大多数工具允许，question + plan_enter 额外开放 |
| `plan` | primary | 计划模式，只读 | edit 仅允许 .opencode/plans/*.md |
| `general` | subagent | 通用子 agent | 禁用 todoread/todowrite |
| `explore` | subagent | 代码探索 | 只允许 grep/glob/read/bash 等只读工具 |
| `compaction` | primary (hidden) | 上下文压缩 | 禁用所有工具 |
| `title` | primary (hidden) | 生成标题 | 禁用所有工具 |
| `summary` | primary (hidden) | 生成摘要 | 禁用所有工具 |

### 权限合并

```typescript
build: {
    permission: PermissionNext.merge(
        defaults,           // 基础权限（大多数工具 allow）
        PermissionNext.fromConfig({
            question: "allow",
            plan_enter: "allow",
        }),
        user,               // 用户自定义权限（来自 config）
    ),
}
```

权限是分层合并的：`defaults → agent 特定 → 用户自定义`。后面的会覆盖前面的。

### 用户自定义 Agent

```typescript
// agent.ts:206-233
for (const [key, value] of Object.entries(cfg.agent ?? {})) {
    if (value.disable) {
        delete result[key]       // 禁用内置 agent
        continue
    }
    let item = result[key]
    if (!item)
        item = result[key] = {   // 创建新 agent
            name: key,
            mode: "all",
            permission: PermissionNext.merge(defaults, user),
            options: {},
            native: false,
        }
    // 合并用户配置
    if (value.model) item.model = Provider.parseModel(value.model)
    item.prompt = value.prompt ?? item.prompt
    item.permission = PermissionNext.merge(item.permission, PermissionNext.fromConfig(value.permission ?? {}))
    // ...
}
```

用户可以在 `opencode.json` 中：
1. 覆盖内置 agent 的任何属性（model、prompt、permission...）
2. 禁用内置 agent（`disable: true`）
3. 创建全新的自定义 agent

---

## 用户消息预处理

源码：`session/prompt.ts:966-1356`

`createUserMessage()` 是一个复杂的预处理管线：

### 文件引用处理

```typescript
// prompt.ts:999-1269
const parts = await Promise.all(
    input.parts.map(async (part): Promise<Draft<MessageV2.Part>[]> => {
        if (part.type === "file") {
            // MCP 资源
            if (part.source?.type === "resource") {
                const resourceContent = await MCP.readResource(clientName, uri)
                // → 转为 text part
            }

            switch (url.protocol) {
                case "data:":
                    // data URL → 直接解码
                case "file:":
                    if (part.mime === "text/plain") {
                        // 文本文件 → 调用 ReadTool 读取，注入为 synthetic text part
                        const result = await ReadTool.init().then((t) => t.execute(args, readCtx))
                        // 生成: "Called the Read tool with the following input: {...}"
                        //       + 文件内容
                    }
                    if (part.mime === "application/x-directory") {
                        // 目录 → 调用 ReadTool 列出内容
                    }
                    // 其他 MIME → 转 base64
            }
        }
        if (part.type === "agent") {
            // @agent 引用 → 注入 "Use the above message to call the task tool with subagent: ..."
        }
        return [{ ...part, messageID: info.id, sessionID: input.sessionID }]
    }),
)
```

**关键**：当用户拖入文件时，OpenCode 不是简单地把文件内容塞进消息。它会：
1. 生成一条伪造的 "Called the Read tool..." 消息（synthetic）
2. 这样 LLM 看到的是一个"已经读取过文件"的上下文，保持与正常工具调用一致的格式

### Reminder 注入

```typescript
// prompt.ts:1358-1496
async function insertReminders(input) {
    // Plan 模式 → 注入 plan workflow 指令
    if (input.agent.name === "plan") {
        userMessage.parts.push({
            type: "text",
            text: PROMPT_PLAN,  // 详细的计划模式工作流
            synthetic: true,
        })
    }

    // Plan → Build 切换 → 注入 "执行计划" 指令
    if (wasPlan && input.agent.name === "build") {
        userMessage.parts.push({
            type: "text",
            text: BUILD_SWITCH,
            synthetic: true,
        })
    }
}
```

### 排队消息包装

```typescript
// prompt.ts:634-651
if (step > 1 && lastFinished) {
    for (const msg of msgs) {
        if (msg.info.role !== "user" || msg.info.id <= lastFinished.id) continue
        for (const part of msg.parts) {
            if (part.type !== "text" || part.ignored || part.synthetic) continue
            part.text = [
                "<system-reminder>",
                "The user sent the following message:",
                part.text,
                "",
                "Please address this message and continue with your tasks.",
                "</system-reminder>",
            ].join("\n")
        }
    }
}
```

当 LLM 正在执行工具时用户发送的新消息，会被包装在 `<system-reminder>` 标签中，防止 LLM 偏离正在执行的任务。

---

## LLM 调用参数组装

源码：`session/llm.ts:47-251`

### 参数合并链

```typescript
// llm.ts:96-110
const variant =
    !input.small && input.model.variants && input.user.variant
        ? input.model.variants[input.user.variant]
        : {}
const base = input.small
    ? ProviderTransform.smallOptions(input.model)
    : ProviderTransform.options({ model, sessionID, providerOptions })
const options = pipe(
    base,                    // provider 默认选项
    mergeDeep(input.model.options),   // model 级选项
    mergeDeep(input.agent.options),   // agent 级选项
    mergeDeep(variant),               // variant 级选项
)
```

**四级合并**：provider → model → agent → variant。每一级可以覆盖前一级的配置。

### 工具修复

```typescript
// llm.ts:179-198
async experimental_repairToolCall(failed) {
    // 尝试 1：大小写修复（LLM 可能返回 "Bash" 而不是 "bash"）
    const lower = failed.toolCall.toolName.toLowerCase()
    if (lower !== failed.toolCall.toolName && tools[lower]) {
        return { ...failed.toolCall, toolName: lower }
    }
    // 尝试 2：转发给 invalid 工具
    return {
        ...failed.toolCall,
        input: JSON.stringify({
            tool: failed.toolCall.toolName,
            error: failed.error.message,
        }),
        toolName: "invalid",
    }
}
```

LLM 可能调用不存在的工具，OpenCode 会尝试修复，否则转给 `invalid` 工具（返回错误提示让 LLM 重试）。

### 最终 streamText 调用

```typescript
return streamText({
    temperature: params.temperature,
    topP: params.topP,
    providerOptions: ProviderTransform.providerOptions(input.model, params.options),
    tools,
    toolChoice: input.toolChoice,
    maxOutputTokens,
    abortSignal: input.abort,
    messages: [
        ...system.map((x) => ({ role: "system", content: x })),  // system prompts
        ...input.messages,                                         // 历史 + 当前
    ],
    model: wrapLanguageModel({
        model: language,
        middleware: [{
            async transformParams(args) {
                // 消息格式转换（provider 特定的适配）
                args.params.prompt = ProviderTransform.message(args.params.prompt, input.model, options)
                return args.params
            },
        }],
    }),
})
```

`streamText` 来自 Vercel AI SDK，是实际发起 LLM 调用的入口。

---

## 设计洞察

### 1. Synthetic 消息的巧妙使用

OpenCode 大量使用 `synthetic: true` 标记的消息：
- 文件读取结果 → 伪装成 Read tool 输出
- Agent 引用 → 转化为 task tool 指令
- 排队用户消息 → 包装在 `<system-reminder>` 中
- Plan 模式指令 → 注入到用户消息尾部

这些消息对 LLM 可见，但在 UI 中可以选择性隐藏。

### 2. 指令的动态发现

与 Claude Code 类似，OpenCode 会：
1. 启动时查找 AGENTS.md / CLAUDE.md
2. 运行中读取文件时，沿路径向上查找额外的指令文件
3. 用 `claim()` 机制确保同一条消息不会重复加载同一个指令文件

### 3. Agent 不是独立进程

Agent 不是独立运行的实体——它只是一组配置（prompt、permission、model、options）。切换 agent 只是改变传给 LLM 的参数，不涉及进程或状态的切换。

---

## 小结

Prompt 组装是 OpenCode 中最复杂的环节之一：

1. **System prompt** 由 4 层构成：模型专用 → 环境信息 → Skills → Instruction 文件
2. **Agent** 定义了 prompt、权限、模型偏好，但只是配置对象，不是运行实体
3. **用户消息** 经过预处理管线：文件引用解析、agent 引用转化、reminder 注入
4. **LLM 参数** 通过 4 级合并链组装：provider → model → agent → variant
5. **工具修复** 机制处理 LLM 的工具名错误，增强鲁棒性
