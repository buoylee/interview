# 14 - 面试 Playbook

## 使用方式

这份 playbook 的目标不是背答案，而是帮你把 Claude Code 源码读法转成面试表达。推荐顺序是：

1. 先用 1 分钟回答建立大图。
2. 面试官追问系统设计时，从 runtime pipeline 切入。
3. 面试官追问实现可信度时，主动把回答落到源码章节和文件。
4. 面试官追问风险时，讲 permission、sandbox、context、compaction、subagent 边界。
5. 最后用设计取舍收束：哪里复用统一 contract，哪里保守，哪里为了 prompt cache 做了额外工程。

答题时不要一开始就报文件名。先讲设计，再用源码证明；否则容易显得像在背代码索引，而不是理解系统。

## 1 分钟总览回答

**How would you implement a coding agent?**

我会把 coding agent 实现成一个围绕模型、工具和状态运转的 runtime loop。入口层先接收用户输入、CLI/REPL/SDK 参数、session 状态和权限配置；prompt/context 层组装 system prompt、user/system context、历史 messages、attachments 和 tool schemas；query loop 调模型并消费 streaming response；如果模型产出 `tool_use`，runtime 按工具名找到真实 `Tool`，做 schema validation、permission check、hooks、sandbox 或本地副作用执行；执行结果再映射成 `tool_result` user message，回到下一轮模型输入。这个闭环不断重复，直到模型给出最终回答、被中断、达到轮次限制或触发 compact/resume 等 session 机制。

工程上我会把几个边界拆清楚：模型只看到 prompt、messages 和 tool schemas；runtime-only state 包括 AbortController、permission context、file cache、UI setters 和 task state；工具系统用统一 contract 描述 schema、权限、并发性、执行和结果映射；长上下文用 session history、auto compact 和 resume 管理；subagent 复用同一套 query loop，但用单独 task、tool context 和 transcript 隔离；fork subagent 进一步为了 prompt cache 复用 parent prompt prefix。Claude Code 源码基本就是这个结构：`src/query.ts` 是主循环，`src/Tool.ts` 和 tools services 是工具 contract 与编排，`src/utils/permissions` 和具体工具目录负责安全边界，`src/services/compact`、`src/tasks/LocalAgentTask`、`src/tools/AgentTool` 处理长会话和多 agent。

## 系统设计类问题

### 问：coding agent 的核心架构是什么？

答题框架：

- 先画 pipeline：input -> prompt/context -> query loop -> model stream -> tool_use -> tool execution -> tool_result -> next loop。
- 强调模型不直接执行副作用，runtime 才执行工具。
- 强调工具结果必须结构化回到下一轮模型，而不是 runtime 私下改状态后结束。
- 源码落点：第 01 章入口，02 章 query loop，03 章 prompt/context，04 章 model streaming，05 章 tool system。

可以补一句：Claude Code 的复杂度不在“调用一次模型”，而在每一轮都要维持合法 transcript、工具配对、权限边界、中断恢复和上下文窗口。

### 问：怎么把工具暴露给模型？

答题框架：

- 每个工具实现统一 `Tool` contract：name、schema、prompt、permission、isReadOnly、isConcurrencySafe、call、result mapping。
- API 请求前把 runtime `Tool` 转成模型可见 schema。
- 模型返回 `tool_use` 后，再按 name 找回 runtime `Tool`。
- `tool_use.id` 和 `tool_result.tool_use_id` 是配对主键。
- 源码落点：第 05 章，`src/Tool.ts`、`src/utils/api.ts`、`src/services/tools/toolExecution.ts`。

常见追问是“为什么 schema 不够，还要 runtime validation”。回答：模型输出可能不合法，schema 是模型约束和提示，副作用前还需要 runtime validation、permission 和 hooks。

### 问：怎么支持流式工具执行？

答题框架：

- 普通路径等 assistant message 完整结束后批量执行 `toolUseBlocks`。
- 流式路径在 `tool_use` block 出现后就让 `StreamingToolExecutor` 排队执行。
- 两条路径最终都产出相同协议形态的 `tool_result`。
- 必须处理 fallback、abort、并发安全、synthetic error result。
- 源码落点：第 04、05 章，`src/query.ts`、`src/services/tools/StreamingToolExecutor.ts`。

这里可以强调设计取舍：流式执行降低延迟，但增加了 discard、sibling abort 和结果缓冲的复杂度。

### 问：如果工具调用失败怎么办？

答题框架：

- 工具不存在、schema validation 失败、permission denied、hook blocked、abort、runtime error 都应尽量转成 `tool_result`。
- 这样模型下一轮能观察失败原因并修正计划。
- 只有模型 API 或 runtime 不可恢复错误才应该中断整体 loop。
- 源码落点：第 05 章，`src/services/tools/toolExecution.ts`；第 04 章 request / stream error handling。

## 源码深挖类问题

### 问：用户在 REPL 输入一句话后，源码链路怎么走？

回答线索：

- `src/screens/REPL.tsx` 持有交互式 runtime container。
- 输入经过处理后触发 `onQuery()` / `onQueryImpl()`。
- prompt/context 组装后进入 `src/query.ts` 的 `query()`。
- `query()` 调 `deps.callModel()`，消费 stream，再处理 tool_use / tool_result。
- 章节参考：01 -> 03 -> 02 -> 04 -> 05。

一句话收束：REPL 是输入和 UI 状态容器，真正的 agent loop 在 `query()`。

### 问：`src/query.ts` 为什么跨这么多章节？

回答线索：

- 它是 runtime loop 的中轴，不是单一职责的小工具文件。
- 第 02 章看 loop 结构和 turn boundary。
- 第 04 章看 model streaming 和 assistant message 生成。
- 第 05 章看 tool_use 收集和 tool_result 回填。
- 第 08 章看 auto compact / reactive compact。
- 第 09 章看 queued commands、abort/continue 边界。

面试中可以说：`query.ts` 的职责宽，但不是无序堆叠；它把多个 runtime stage 串成合法的模型协议循环。

### 问：system prompt、context、attachments 分别在哪里看？

回答线索：

- 默认 system prompt：`src/constants/prompts.ts`。
- prompt precedence：`src/utils/systemPrompt.ts`。
- headless / shared context parts：`src/utils/queryContext.ts`。
- queued command、pending subagent message、图片、nested memory 等：`src/utils/attachments.ts`。
- 章节参考：第 03 章。

要强调 model-visible context 和 runtime-only state 的区别。permission context、AbortController、UI setters 等不应该被说成模型直接看见的上下文。

### 问：MCP/plugin/bridge 应该怎么讲？

回答线索：

- 它们是 extension surfaces，不是核心 loop。
- MCP 工具被包装成内部 `Tool` 后进入 tool pool。
- plugin 贡献 agents、commands、skills、hooks 或 MCP config。
- bridge 把外部环境接入 REPL，远端消息通过 queued commands / control responses 进入本地 runtime。
- 章节参考：第 12 章；源码参考 `src/tools.ts`、`src/services/mcp/client.ts`、`src/utils/plugins/*`、`src/hooks/useReplBridge.tsx`。

## 安全与权限类问题

### 问：coding agent 执行本地命令如何做安全控制？

答题框架：

- 权限上下文在启动或模式切换时初始化，合并 CLI、settings、policy、session allow/deny/ask rules。
- 工具执行前统一经过 permission gate，不是 Bash 自己随便跑。
- Bash 还会解析 shell command、识别危险/过宽规则、生成 prefix suggestion，并结合 sandbox policy。
- 文件工具有 read-before-write、mtime、防 stale write、diff/review 等边界。
- 源码落点：第 06、07 章，`src/utils/permissions/permissionSetup.ts`、`src/utils/permissions/permissions.ts`、`src/tools/BashTool/`、`src/tools/FileEditTool/`、`src/tools/FileWriteTool/`。

可以补一句：安全不是一个 if，而是 policy、permission rules、tool validation、sandbox、hook 和 UI confirmation 的组合。

### 问：permission 和 tool schema 的关系是什么？

答题框架：

- schema 决定模型可以提出什么结构的调用。
- permission 决定 runtime 是否允许这个调用产生副作用。
- 模型看到工具，不等于一定能执行。
- deny rules 甚至可以在 tool pool assembly 阶段让某些工具不进入模型可见集合。
- 源码参考：第 05、06、12 章。

### 问：如何避免后台 subagent 卡住权限弹窗？

答题框架：

- subagent 有自己的 task lifecycle 和 permission mode 处理。
- async non-bubble agent 需要避免后台直接弹交互式 permission prompt。
- Agent definition 可以设置 permissionMode，父上下文也会影响可用规则。
- 源码落点：第 10 章，`src/tools/AgentTool/runAgent.ts` 的 permission inheritance 区域。

## 长上下文 / Session 类问题

### 问：长对话超过 context window 怎么办？

答题框架：

- 先估算 token pressure 和 threshold。
- auto compact 满足条件时生成 compact summary 和 messagesToKeep。
- compact 后用 post-compact messages 替换 query 输入。
- reactive compact 可在 context 失败后重试。
- compact 是有损摘要，不是完整历史压缩。
- 源码落点：第 08 章，`src/services/compact/autoCompact.ts`、`src/services/compact/compact.ts`、`src/query.ts`。

这里可以自然提到 prompt cache：稳定 prompt prefix 和 compact boundary 都会影响缓存效果；不能把所有动态内容无脑放在 system prompt 前部。

### 问：resume 和 continue 要保存什么？

答题框架：

- durable transcript / session history 保存消息历史。
- resume 要过滤 incomplete tool calls，恢复可继续的 messages。
- background task resume 还要恢复 task metadata、selected agent、worktree、content replacement state。
- 源码落点：第 08、10 章，`src/utils/conversationRecovery.ts`、`src/cli/print.ts`、`src/tools/AgentTool/resumeAgent.ts`。

### 问：interrupt 之后如何保持 transcript 合法？

答题框架：

- cancel/abort 不只是停 UI，而是要给已出现的 tool_use 一个结局。
- `StreamingToolExecutor` 会为中断、fallback、sibling error 等生成 synthetic `tool_result`。
- queued command 不应被普通 ESC 全部清空；kill agents 是更强的显式路径。
- 源码落点：第 09 章，`src/hooks/useCancelRequest.ts`、`src/utils/messageQueueManager.ts`、`src/services/tools/StreamingToolExecutor.ts`。

## Subagent / Fork 类问题

### 问：subagent 是不是另一个完全不同的 runtime？

答题框架：

- 不是。subagent 复用同一套 `query()`、tool system、permission、attachments、compact 思路。
- 不同的是它有独立 `AgentDefinition`、task state、sidechain transcript、agent id、tool context 和 lifecycle。
- foreground / background task 决定 UI 与通知方式。
- 源码落点：第 10 章，`src/tools/AgentTool/`、`src/tools/AgentTool/runAgent.ts`、`src/tasks/LocalAgentTask/`。

### 问：background subagent 如何把结果返回主 agent？

答题框架：

- background task 运行时维护 `LocalAgentTaskState`。
- 完成、失败或 killed 后生成 `<task-notification>`。
- notification 进入 message queue，再作为 attachment 被主 query loop 读取。
- 主 agent 下一轮把它当作上下文继续推理。
- 源码参考：第 09、10 章，`src/utils/messageQueueManager.ts`、`src/tasks/LocalAgentTask/LocalAgentTask.tsx`。

### 问：fork subagent 和普通 subagent 差异是什么？

答题框架：

- 普通 subagent 根据 selected agent definition 构造 system prompt、tools 和 user prompt。
- fork subagent 复用 parent rendered system prompt、parent messages prefix、exact tools 和 model。
- `buildForkedMessages()` 克隆 parent assistant message，给 tool_use 补稳定 `tool_result`，最后追加 child directive。
- 这样多个 child 的前缀更稳定，有利于 prompt cache。
- 源码落点：第 11 章，`src/tools/AgentTool/forkSubagent.ts`、`src/utils/forkedAgent.ts`。

### 问：prompt cache 在 fork 里为什么重要？

答题框架：

- 多个 fork child 往往共享大段 parent context。
- 如果差异出现在 prompt 前部，后面大段内容都难以复用缓存。
- fork 把 child-specific directive 放到末尾，并稳定 system prompt、tools、messages 和 placeholder tool_result。
- cache 风险来自 system prompt、user/system context、tools schema/order、model、thinking budget、content replacement state 等变化。
- 章节参考：第 11 章。

## 如何把高层设计引到源码证据

面试中最稳的节奏是“三段式”：

第一段先给高层设计：
“我会把 coding agent 做成 model-tool-result loop，模型只提出工具意图，runtime 负责验证、权限和执行。”

第二段给关键不变量：
“不变量是 tool_use / tool_result 必须配对，工具副作用必须过 permission，长上下文要 compact，subagent 不能破坏主线程 transcript。”

第三段落到源码：
“Claude Code 里可以看 `src/query.ts` 的 turn boundary，看 `src/Tool.ts` 的 Tool contract，看 `src/services/tools/toolExecution.ts` 的 validation/permission/call，看 `src/services/compact` 的 compact，看 `src/tools/AgentTool` 的 subagent path。”

这样回答的好处是，面试官可以任选一个点深挖，你都能顺着章节进入源码，而不是把自己困在某一行实现里。

## 常见失分点

- 把 Claude Code 说成“一次 prompt + 一堆工具函数”，忽略多轮 `tool_result` 回填。
- 把 system prompt、attachments、tools schema 混成一个纯文本 prompt。
- 说“模型执行 Bash”，而不是“模型发出 Bash tool_use，runtime 校验和执行”。
- 只讲 allow/deny，不讲 sandbox、hooks、schema validation、runtime-only state。
- 把 subagent 说成远端服务，忽略它复用本地 `query()` loop 和 task lifecycle。
- 把 fork subagent 说成普通 subagent 的别名，忽略 prompt cache 设计。
- 把 MCP/plugin/bridge 当成核心 loop，忽略它们只是 extension surfaces。

## 一句话总结

面试里要先讲闭环，再讲边界，最后用源码证明：Claude Code 的本质是一个维护合法 transcript、工具副作用、安全权限、长上下文和 subagent 生命周期的 coding agent runtime。
