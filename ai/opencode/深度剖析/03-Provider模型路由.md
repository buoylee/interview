# 03 - Provider 模型路由：多厂商 SDK 的统一调度

> OpenCode 支持 20+ 家 LLM 提供商，每家的 SDK 初始化、认证方式、模型 ID 格式都不同。
> `provider.ts` 是将这些差异抹平的统一路由层。
> 本文剖析 Provider 的加载链、SDK 实例化、以及模型查找的完整数据流。

---

## 架构总览

```
LLM.stream()
    │
    ├── Provider.getModel(providerID, modelID)     → Model 元数据
    ├── Provider.getLanguage(model)                 → LanguageModelV2 实例
    │       │
    │       ├── getSDK(model)                       → SDK 实例（缓存）
    │       │       │
    │       │       ├── BUNDLED_PROVIDERS[npm]()     → 直接创建
    │       │       └── BunProc.install(npm)         → 动态安装 + import
    │       │
    │       └── modelLoaders[providerID]?(sdk, id)  → 特殊模型创建
    │           └── sdk.languageModel(id)            → 默认模型创建
    │
    └── streamText({ model: language, ... })        → Vercel AI SDK 调用
```

---

## Provider 状态初始化

源码：`provider/provider.ts:833-1080`

整个 Provider 系统通过 `Instance.state()` 懒加载，只在首次访问时初始化：

```typescript
const state = Instance.state(async () => {
    const config = await Config.get()
    const modelsDev = await ModelsDev.get()        // ① 从 models.dev 加载模型数据库
    const database = mapValues(modelsDev, fromModelsDevProvider)

    const disabled = new Set(config.disabled_providers ?? [])
    const enabled = config.enabled_providers ? new Set(config.enabled_providers) : null

    const providers: Record<ProviderID, Info> = {}
    const languages = new Map<string, LanguageModelV2>()   // 模型实例缓存
    const modelLoaders: Record<string, CustomModelLoader> = {}
    const varsLoaders: Record<string, CustomVarsLoader> = {}
    const sdk = new Map<string, SDK>()                     // SDK 实例缓存

    // ... 6 步加载链 ...

    return { models: languages, providers, sdk, modelLoaders, varsLoaders }
})
```

### 6 步加载链

#### Step 1：从配置扩展模型数据库

```typescript
for (const [providerID, provider] of configProviders) {
    const existing = database[providerID]
    const parsed: Info = {
        id: ProviderID.make(providerID),
        name: provider.name ?? existing?.name ?? providerID,
        env: provider.env ?? existing?.env ?? [],
        options: mergeDeep(existing?.options ?? {}, provider.options ?? {}),
        source: "config",
        models: existing?.models ?? {},
    }
    // 合并每个 model 的配置
    for (const [modelID, model] of Object.entries(provider.models ?? {})) {
        // ... 深度合并 existing model 和 config model
        parsed.models[modelID] = parsedModel
    }
    database[providerID] = parsed
}
```

用户在 `opencode.json` 中配置的 provider/model 信息会与 models.dev 数据库合并。可以覆盖已有模型的参数，也可以定义全新的模型。

#### Step 2：环境变量探测

```typescript
const env = Env.all()
for (const [id, provider] of Object.entries(database)) {
    const apiKey = provider.env.map((item) => env[item]).find(Boolean)
    if (!apiKey) continue
    mergeProvider(providerID, {
        source: "env",
        key: provider.env.length === 1 ? apiKey : undefined,
    })
}
```

每个 provider 定义了一组环境变量名（如 Anthropic 的 `ANTHROPIC_API_KEY`）。如果检测到对应的环境变量，provider 就被标记为可用。

#### Step 3：Auth 存储的 API Key

```typescript
for (const [id, provider] of Object.entries(await Auth.all())) {
    if (provider.type === "api") {
        mergeProvider(providerID, {
            source: "api",
            key: provider.key,
        })
    }
}
```

通过 `opencode auth <provider>` 命令存储的 key。

#### Step 4：Plugin 认证

```typescript
for (const plugin of await Plugin.list()) {
    if (!plugin.auth) continue
    const auth = await Auth.get(providerID)
    if (auth) {
        const options = await plugin.auth.loader(...)
        mergeProvider(providerID, { source: "custom", options: opts })
    }
}
```

插件可以提供自定义的认证加载器。

#### Step 5：Custom Loaders

```typescript
for (const [id, fn] of Object.entries(CUSTOM_LOADERS)) {
    const data = database[providerID]
    const result = await fn(data)
    if (result && (result.autoload || providers[providerID])) {
        if (result.getModel) modelLoaders[providerID] = result.getModel
        if (result.vars) varsLoaders[providerID] = result.vars
        mergeProvider(providerID, { source: "custom", options: opts })
    }
}
```

这是最复杂的一步。每个 provider 可以有一个 Custom Loader，处理特殊逻辑。

#### Step 6：最终过滤

```typescript
for (const [id, provider] of Object.entries(providers)) {
    if (!isProviderAllowed(providerID)) { delete providers[providerID]; continue }
    // 移除 deprecated/alpha 模型
    // 应用 blacklist/whitelist
    // 移除空 provider
}
```

---

## Custom Loaders 详解

源码：`provider/provider.ts:145-667`

Custom Loaders 是 per-provider 的初始化逻辑，处理每个厂商的特殊需求：

### Anthropic

```typescript
async anthropic() {
    return {
        autoload: false,    // 需要 env/auth 才激活
        options: {
            headers: {
                "anthropic-beta": "interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14",
            },
        },
    }
}
```

仅注入 beta feature headers。

### OpenAI

```typescript
openai: async () => {
    return {
        autoload: false,
        async getModel(sdk, modelID) {
            return sdk.responses(modelID)    // 使用 Responses API 而不是 Chat Completions
        },
    }
}
```

OpenAI 使用 `sdk.responses()` 而非 `sdk.chat()`。

### Amazon Bedrock

```typescript
"amazon-bedrock": async () => {
    // 1. 多种认证方式：profile / access key / bearer token / web identity / container creds
    // 2. Region 解析链：config → env → default "us-east-1"
    // 3. 自动跨区域前缀：us.xxx / eu.xxx / global.xxx

    return {
        autoload: true,
        options: providerOptions,
        async getModel(sdk, modelID, options) {
            // 根据 region 自动添加前缀
            const region = options?.region ?? defaultRegion
            let regionPrefix = region.split("-")[0]

            switch (regionPrefix) {
                case "us":
                    if (modelRequiresPrefix && !isGovCloud)
                        modelID = `${regionPrefix}.${modelID}`
                    break
                case "eu":
                    if (regionRequiresPrefix && modelRequiresPrefix)
                        modelID = `${regionPrefix}.${modelID}`
                    break
                case "ap":
                    // Australia → "au.", Tokyo → "jp.", 其他 → "apac."
                    break
            }
            return sdk.languageModel(modelID)
        },
    }
}
```

Bedrock 的 Custom Loader 最复杂——需要处理 AWS 认证链和跨区域模型 ID 前缀。

### Google Vertex

```typescript
"google-vertex": async (provider) => {
    const project = provider.options?.project ?? Env.get("GOOGLE_CLOUD_PROJECT") ?? ...
    const location = String(provider.options?.location ?? Env.get("GOOGLE_VERTEX_LOCATION") ?? "us-central1")

    return {
        autoload: Boolean(project),
        options: {
            project, location,
            fetch: async (input, init) => {
                const auth = new GoogleAuth()
                const client = await auth.getApplicationDefault()
                const token = await client.credential.getAccessToken()
                headers.set("Authorization", `Bearer ${token.token}`)
                return fetch(input, { ...init, headers })
            },
        },
    }
}
```

注入 Google Cloud 认证 token 到每个请求。

### GitHub Copilot

```typescript
"github-copilot": async () => {
    return {
        autoload: false,
        async getModel(sdk, modelID) {
            if (useLanguageModel(sdk)) return sdk.languageModel(modelID)
            return shouldUseCopilotResponsesApi(modelID)
                ? sdk.responses(modelID)
                : sdk.chat(modelID)
        },
    }
}
```

GPT-5+ 用 Responses API，其他用 Chat API。

---

## SDK 实例化

源码：`provider/provider.ts:1086-1217`

```typescript
async function getSDK(model: Model) {
    const provider = s.providers[model.providerID]
    const options = { ...provider.options }

    // 1. 解析 baseURL（支持变量替换如 ${AZURE_RESOURCE_NAME}）
    const baseURL = iife(() => {
        let url = options["baseURL"] || model.api.url
        const loader = s.varsLoaders[model.providerID]
        if (loader) {
            const vars = loader(options)
            for (const [key, value] of Object.entries(vars)) {
                url = url.replaceAll("${" + key + "}", value)
            }
        }
        return url
    })

    // 2. 注入自定义 fetch（SSE 超时 + OpenAI item ID 清理）
    options["fetch"] = async (input, init) => {
        // Strip openai itemId metadata
        if (model.api.npm === "@ai-sdk/openai" && opts.body && opts.method === "POST") {
            const body = JSON.parse(opts.body)
            if (!keepIds && Array.isArray(body.input)) {
                for (const item of body.input) { delete item.id }
                opts.body = JSON.stringify(body)
            }
        }
        const res = await fetchFn(input, opts)
        if (!chunkAbortCtl) return res
        return wrapSSE(res, chunkTimeout, chunkAbortCtl)  // SSE chunk 超时
    }

    // 3. 创建 SDK
    const bundledFn = BUNDLED_PROVIDERS[model.api.npm]
    if (bundledFn) {
        return bundledFn({ name: model.providerID, ...options })
    }
    // 动态安装
    let installedPath = await BunProc.install(model.api.npm, "latest")
    const mod = await import(installedPath)
    const fn = mod[Object.keys(mod).find((key) => key.startsWith("create"))!]
    return fn({ name: model.providerID, ...options })
}
```

**三层缓存**：
1. SDK 实例缓存（`sdk Map`）— 同 provider + npm + options → 复用 SDK
2. 模型实例缓存（`languages Map`）— 同 providerID + modelID → 复用 LanguageModel
3. 打包 vs 动态安装 — 20 个常用 SDK 直接打包，其他运行时 `bun install`

### SSE 超时保护

```typescript
function wrapSSE(res: Response, ms: number, ctl: AbortController) {
    const reader = res.body.getReader()
    const body = new ReadableStream({
        async pull(ctrl) {
            const part = await new Promise((resolve, reject) => {
                const id = setTimeout(() => {
                    const err = new Error("SSE read timed out")
                    ctl.abort(err)
                    reject(err)
                }, ms)
                reader.read().then(
                    (part) => { clearTimeout(id); resolve(part) },
                    (err) => { clearTimeout(id); reject(err) },
                )
            })
            if (part.done) { ctrl.close(); return }
            ctrl.enqueue(part.value)
        },
    })
    return new Response(body, { headers: res.headers, status: res.status })
}
```

如果 SSE 流中两个 chunk 之间的间隔超过 `chunkTimeout`，自动断开连接。防止 LLM 服务挂起导致无限等待。

---

## 模型查找

### getModel：元数据查找

```typescript
export async function getModel(providerID: ProviderID, modelID: ModelID) {
    const provider = s.providers[providerID]
    if (!provider) {
        // fuzzy search 建议
        const matches = fuzzysort.go(providerID, availableProviders, { limit: 3, threshold: -10000 })
        throw new ModelNotFoundError({ providerID, modelID, suggestions: matches.map(m => m.target) })
    }
    const info = provider.models[modelID]
    if (!info) {
        const matches = fuzzysort.go(modelID, availableModels, { limit: 3, threshold: -10000 })
        throw new ModelNotFoundError({ providerID, modelID, suggestions })
    }
    return info
}
```

找不到时使用 fuzzysort 给出建议（"Did you mean: ..."）。

### getLanguage：实例化

```typescript
export async function getLanguage(model: Model): Promise<LanguageModelV2> {
    const key = `${model.providerID}/${model.id}`
    if (s.models.has(key)) return s.models.get(key)!   // 缓存命中

    const sdk = await getSDK(model)

    const language = s.modelLoaders[model.providerID]
        ? await s.modelLoaders[model.providerID](sdk, model.api.id, provider.options)
        : sdk.languageModel(model.api.id)   // 默认走 languageModel()

    s.models.set(key, language)
    return language
}
```

如果 provider 有 Custom Loader 中注册了 `getModel`（如 OpenAI 的 `sdk.responses()`），就用它。否则走默认的 `sdk.languageModel()`。

### Small Model 选择

```typescript
export async function getSmallModel(providerID: ProviderID) {
    // 1. 用户配置优先
    if (cfg.small_model) return getModel(parseModel(cfg.small_model))

    // 2. 按优先级查找小模型
    let priority = [
        "claude-haiku-4-5",
        "gemini-3-flash",
        "gpt-5-nano",
    ]
    if (providerID.startsWith("opencode")) priority = ["gpt-5-nano"]
    if (providerID.startsWith("github-copilot")) priority = ["gpt-5-mini", "claude-haiku-4.5", ...priority]

    for (const item of priority) {
        for (const model of Object.keys(provider.models)) {
            if (model.includes(item)) return getModel(providerID, ModelID.make(model))
        }
    }
}
```

Small Model 用于标题生成、摘要等轻量任务，避免用大模型浪费 token。

---

## Model 数据结构

```typescript
export const Model = z.object({
    id: ModelID.zod,
    providerID: ProviderID.zod,
    api: z.object({
        id: z.string(),       // 实际发给 API 的 model ID
        url: z.string(),       // API endpoint
        npm: z.string(),       // SDK 包名（如 "@ai-sdk/anthropic"）
    }),
    name: z.string(),
    capabilities: z.object({
        temperature: z.boolean(),
        reasoning: z.boolean(),
        attachment: z.boolean(),
        toolcall: z.boolean(),
        input: z.object({ text, audio, image, video, pdf }),
        output: z.object({ text, audio, image, video, pdf }),
        interleaved: z.boolean() | z.object({ field: z.enum(["reasoning_content", "reasoning_details"]) }),
    }),
    cost: z.object({
        input: z.number(),    // per 1M tokens
        output: z.number(),
        cache: z.object({ read, write }),
    }),
    limit: z.object({
        context: z.number(),  // 上下文窗口
        input: z.number().optional(),
        output: z.number(),   // 最大输出
    }),
    options: z.record(z.string(), z.any()),
    headers: z.record(z.string(), z.string()),
    variants: z.record(z.string(), z.record(z.string(), z.any())).optional(),
})
```

这个结构驱动了整个系统的行为：
- `capabilities.toolcall` → 决定是否注册工具
- `capabilities.reasoning` → 决定是否处理 reasoning 事件
- `limit.context` → 决定 compaction 触发阈值
- `cost` → 决定费用计算
- `api.npm` → 决定用哪个 SDK

---

## 费用计算

源码：`session/index.ts:791-868`

```typescript
export const getUsage = fn(z.object({ model, usage, metadata }), (input) => {
    // 1. 区分 Anthropic 和其他 provider 的 token 计算方式
    const excludesCachedTokens = !!(input.metadata?.["anthropic"] || input.metadata?.["bedrock"])
    const adjustedInputTokens = excludesCachedTokens
        ? inputTokens
        : inputTokens - cacheReadInputTokens - cacheWriteInputTokens

    // 2. 计算费用
    return {
        cost: new Decimal(0)
            .add(new Decimal(tokens.input).mul(costInfo?.input ?? 0).div(1_000_000))
            .add(new Decimal(tokens.output).mul(costInfo?.output ?? 0).div(1_000_000))
            .add(new Decimal(tokens.cache.read).mul(costInfo?.cache?.read ?? 0).div(1_000_000))
            .add(new Decimal(tokens.cache.write).mul(costInfo?.cache?.write ?? 0).div(1_000_000))
            .add(new Decimal(tokens.reasoning).mul(costInfo?.output ?? 0).div(1_000_000))
            .toNumber(),
        tokens,
    }
})
```

**Anthropic 特殊处理**：Anthropic 的 `inputTokens` 不包含缓存命中的 token，需要分开计算。其他 provider（OpenAI、Gemini）的 `inputTokens` 包含所有输入 token。

---

## 设计洞察

### 1. 打包 vs 动态安装

```typescript
const BUNDLED_PROVIDERS = {
    "@ai-sdk/anthropic": createAnthropic,
    "@ai-sdk/openai": createOpenAI,
    "@ai-sdk/google": createGoogleGenerativeAI,
    // ... 20 个
}

// 非打包的 → 运行时安装
let installedPath = await BunProc.install(model.api.npm, "latest")
const mod = await import(installedPath)
```

常用 SDK 直接打包（零延迟），长尾 SDK 按需安装。这避免了包体积膨胀的同时保持了扩展性。

### 2. 三级缓存策略

```
请求: anthropic/claude-sonnet-4-5
    │
    ├── languages.get("anthropic/claude-sonnet-4-5") → 命中? 直接返回
    │
    ├── sdk.get(hash({providerID, npm, options})) → 命中? 复用 SDK
    │                                                     └── sdk.languageModel("claude-sonnet-4-5")
    │
    └── 首次: createAnthropic({...options}) → 缓存 SDK
              └── sdk.languageModel("claude-sonnet-4-5") → 缓存 language
```

### 3. Custom Loader 模式

不同 provider 的特殊需求通过 Custom Loader 处理，而不是硬编码的 `if-else`。新增 provider 只需添加一个 loader 函数。

### 4. 与 OpenAI Agents SDK 的对比

| | OpenAI Agents SDK | OpenCode |
|---|---|---|
| **Provider 数量** | 1（OpenAI） | 20+ |
| **SDK 管理** | 直接用 OpenAI SDK | Vercel AI SDK 统一抽象层 |
| **模型数据** | 硬编码 | models.dev 动态数据库 |
| **认证方式** | 单一 API key | 环境变量 / Auth 存储 / OAuth / IAM |
| **动态安装** | 无 | 支持运行时 `bun install` |

---

## 小结

Provider 层是 OpenCode 支持多厂商的关键：

1. **6 步加载链**：models.dev → config 合并 → env 探测 → auth → plugin → custom loaders → 过滤
2. **Custom Loaders**：每个 provider 的特殊逻辑（认证、模型 ID 转换、API 选择）
3. **SDK 实例化**：打包 20 个常用 SDK + 动态安装长尾 SDK + 三级缓存
4. **模型查找**：fuzzy search 建议 + small model 优先级选择
5. **统一抽象**：所有差异最终收敛到 Vercel AI SDK 的 `LanguageModelV2` 接口
