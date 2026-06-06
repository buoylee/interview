# 05 - Fork Subagent 与 Prompt Cache

> fork subagent 的核心目标是：从主 agent 当前上下文 fork 出后台分支，同时最大化 prompt cache 命中。

源码根目录：`/Users/buoy/Development/gitrepo/Claude-Code-true`

核心文件：

| 文件 | 作用 |
|------|------|
| `src/tools/AgentTool/forkSubagent.ts` | fork agent definition、`buildForkedMessages()`、worktree notice |
| `src/tools/AgentTool/AgentTool.tsx` | 判断 fork path，构造 `runAgentParams` |
| `src/tools/AgentTool/runAgent.ts` | 暴露 cache-safe params，进入 `query()` |
| `src/utils/forkedAgent.ts` | `CacheSafeParams` 类型、`createSubagentContext()`、fork context 工具 |
| `src/services/api/promptCacheBreakDetection.ts` | prompt cache tracking / cleanup |

---

## 1. fork subagent 解决什么问题？

普通 subagent 更像：

```text
给一个 specialist 一个新 prompt，让它独立完成任务。
```

fork subagent 更像：

```text
从主 agent 当前上下文分出一条后台分支，让它基于几乎相同的上下文继续做另一件事。
```

比如主 agent 已经读了大量上下文，马上要并发做多个方向：

```text
fork A: 继续分析测试失败
fork B: 检查安全风险
fork C: 总结迁移计划
```

如果每个 fork 都重新发送完整系统 prompt、tools、history，成本很高。

所以 fork subagent 的优化目标是：

```text
让多个 child 的 prompt prefix 尽可能相同。
```

---

## 2. prompt cache 命中的核心条件

`src/utils/forkedAgent.ts` 中的 `CacheSafeParams` 说明 cache key 相关维度。

可以理解成：

```text
cache-safe params:
  systemPrompt
  userContext
  systemContext
  toolUseContext.options.tools
  model
  messages prefix
  thinkingConfig
```

实际心智模型：

```text
prompt cache 看的是“前缀是否一样”。

越靠前的内容越稳定，越容易 cache。
越早产生差异，后面的 cache 越难复用。
```

对 fork subagent 来说，想命中 cache，就要让这些东西一致：

- 同一个 rendered system prompt。
- 同一个 model。
- 同一个 tools 列表和 schema。
- 同一个 thinking config。
- 同一个 parent messages prefix。
- 尽可能相同的 placeholder tool_result。
- 把 child-specific directive 放到最后。

---

## 3. AgentTool fork path 做了什么？

`AgentTool.tsx` 中 fork path 会优先复用 parent 上下文：

```ts
runAgentParams = {
  ...,
  override: {
    systemPrompt: forkParentSystemPrompt,
    availableTools: toolUseContext.options.tools,
    forkContextMessages: toolUseContext.messages,
    useExactTools: true,
  },
}
```

关键点：

```text
systemPrompt: 复用 parent rendered system prompt
availableTools: 复用 parent 当前 tools
default messages: 复用 parent messages prefix
useExactTools: 避免重新过滤/重排 tools 导致 schema 差异
```

这就是 fork cache 友好的第一层。

---

## 4. buildForkedMessages() 如何构造相同 prefix？

`src/tools/AgentTool/forkSubagent.ts` 中的 `buildForkedMessages()` 做了一个很巧的处理。

它会：

- clone 当前 assistant message。
- 保留 thinking/text/tool_use blocks。
- 收集当前 assistant message 里的所有 `tool_use`。
- 构造一个 user message，为每个 `tool_use` 放一个 placeholder `tool_result`。
- placeholder 文本保持稳定，比如 `Fork started — processing in background`。
- 最后再追加 child-specific directive。

抽象结构：

```text
parent messages prefix
  ...

assistant:
  thinking block
  text block
  tool_use Agent(A)
  tool_use Agent(B)
  tool_use Agent(C)

user:
  tool_result for Agent(A): Fork started — processing in background
  tool_result for Agent(B): Fork started — processing in background
  tool_result for Agent(C): Fork started — processing in background
  text: <child-specific directive>
```

为什么需要 placeholder tool_result？

因为 LLM tool calling 的消息结构要求：

```text
assistant tool_use 后面必须有对应 user tool_result。
```

fork child 要从这个 assistant trajectory 分叉，就必须补齐这些 tool_result。

如果每个 child 的 tool_result 内容都不同，prefix 会很早分叉，cache 不友好。

所以统一 placeholder：

```text
Fork started — processing in background
```

让多个 fork child 在最后 directive 之前保持相同。

---

## 5. 为什么差异要放最后？

假设有三个 fork child。

不 cache-friendly 的结构：

```text
system prompt
child A directive
parent history...
```

```text
system prompt
child B directive
parent history...
```

差异出现在很早的位置，后面的 parent history 也难复用。

cache-friendly 的结构：

```text
system prompt
parent history...
stable placeholder tool_results...
child A directive
```

```text
system prompt
parent history...
stable placeholder tool_results...
child B directive
```

差异只出现在最后，前面大段 prefix 可以共享 cache。

这就是 fork subagent 的核心设计。

---

## 6. fork subagent 为什么通常 async？

fork 模式依赖 background 通知模型。

它要让主 agent 继续，不等待所有 fork child 同步完成：

```text
主 agent 发起多个 fork
  |
  |-- 每个 fork 立即返回 async_launched
  |-- 主 agent 得知它们在后台跑
  |-- 子 agent 完成后用 task-notification 回来
```

这也有利于并发：

```text
多个 fork child 同时进行 API call / tool call / IO
```

---

## 7. 哪些因素会破坏 prompt cache？

| 因素 | 为什么破坏 |
|------|------------|
| system prompt 不同 | cache prefix 从最前面就变了 |
| tools 列表不同 | tool schema 是 prompt 的一部分 |
| tools 顺序不同 | schema 序列不同也可能破坏 prefix |
| model 不同 | cache 通常按 model 隔离 |
| thinking config 不同 | thinking budget/配置参与请求结构 |
| parent messages prefix 不同 | history 变了，prefix 变了 |
| placeholder tool_result 内容不同 | tool_use 后紧接着分叉 |
| child directive 放太前 | 差异过早出现 |
| content replacement state 不一致 | tool result 内容替换/恢复不一致 |

实践判断：

```text
fork child 越像同一个请求的不同尾巴，越容易命中 cache。
fork child 越像全新 agent，cache 命中越差。
```

---

## 8. fork cache 和普通 subagent 的区别

| 维度 | 普通 subagent | fork subagent |
|------|---------------|---------------|
| system prompt | selected agent prompt | parent rendered system prompt |
| tools | 按 agent definition 过滤 | 尽量复用 parent exact tools |
| messages | 通常是 `prompt` 单独构造 | 复用 parent messages prefix |
| prompt 差异 | 一开始就不同 | 尽量推迟到最后 directive |
| cache 目标 | 不特别优化 | 最大化 shared prefix |
| 使用场景 | specialist delegation | 从当前上下文分叉并行处理 |

---

## 9. 和 ToolUseContext 的关系

fork subagent 仍然会创建自己的 `ToolUseContext`。

但是它会特别注意这些字段：

- `renderedSystemPrompt`：复用 parent prompt。
- `options.tools`：复用 exact tools。
- `messages`：使用 forked messages。
- `contentReplacementState`：clone，确保 tool result budget / resume 一致。
- `thinkingConfig`：继承，避免 cache 维度变化。

这就是为什么 fork 不是简单 `new Agent(prompt)`。

它是：

```text
复用 parent request 的 cache-sensitive 部分，
只在最后加上 fork-specific instruction。
```

---

## 10. 面试式回答

如果有人问：fork subagent 如何最大化 prompt cache？

可以回答：

```text
Claude Code 的 fork subagent 不是重新构造一个完全独立的 prompt，而是尽量复用主 agent 当前请求的 cache-safe prefix。它会复用 parent rendered system prompt、exact tools、model、thinking config 和 parent messages prefix。

对于当前 assistant message 中已经产生的 tool_use，它会构造稳定的 placeholder tool_result，比如 “Fork started — processing in background”，保证不同 fork child 在 tool_use 之后仍然有相同结构。真正不同的 child directive 被放到最后，这样多个 fork child 只有尾部不同，前面大段 prefix 可以命中 prompt cache。
```

## 11. 一句话总结

```text
fork subagent 的 prompt cache 策略，就是把“不同”推迟到最后，把 system prompt、tools、history、tool_result placeholder 这些昂贵前缀保持一致。
```
