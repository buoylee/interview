# 13 - 源码地图

## 如何使用这张地图

这张地图只放第一批源码锚点，用来快速从章节跳到 Claude Code 源码仓库：

```text
/Users/buoy/Development/gitrepo/Claude-Code-true
```

使用方式是先按 runtime 阶段定位文件，再回到对应章节理解实现逻辑。这里不做逐行解释，也不替代后续章节的细读。

## Runtime Entry

- `src/main.tsx` / `run()`：CLI / runtime 的主入口之一，负责 Commander command setup、顶层 flags、模式分流、system prompt 文件选项、模型/权限/MCP/session 参数处理。
- `src/main.tsx` / `getInputPrompt()`：stdin 与命令行 prompt 的合流点；text 模式拼接 stdin，`stream-json` 模式保留 stdin stream。
- `src/screens/REPL.tsx` / `REPL()`：交互式输入入口和 runtime 容器，持有 messages、AbortController、工具 UI 状态和 `ToolUseContext` 构造逻辑。
- `src/screens/REPL.tsx` / `onQuery()`、`onQueryImpl()`：交互式输入进入 `query()` 的直接调用点。
- `src/utils/handlePromptSubmit.ts` / `executeUserInput()`：queued command 或 prompt 输入转 `newMessages`，再触发 REPL 的 `onQuery()`。
- `src/QueryEngine.ts` / `QueryEngine.submitMessage()`：print/SDK/headless 模式的输入处理、prompt/context 组装和 `query()` 调用入口。

## Query Loop

- `src/query.ts` / `query()`：主 query loop 的核心锚点，关注 messages 如何送入模型、stream 如何被消费、tool_result 如何进入下一轮。
- `src/query.ts` / `useStreamingToolExecution`：是否使用流式工具执行的分支。
- `src/query.ts` / `toolUpdates`：统一消费 `StreamingToolExecutor.getRemainingResults()` 或 `runTools()` 的工具结果。
- `src/query/deps.ts`：query loop 的依赖集合，适合观察 runtime 如何把外部服务、工具、状态和配置注入主循环。
- `src/services/tools/StreamingToolExecutor.ts` / `StreamingToolExecutor`：流式工具执行器，适合看并发控制、结果缓冲、中断和 `ToolUseContext` 更新。

## Prompt / Context

- `src/constants/prompts.ts` / `getSystemPrompt()`：系统提示词和基础行为约束的主要来源，包含 cwd/env、memory、tool guidance、MCP instructions 和输出风格等 sections。
- `src/utils/systemPrompt.ts` / `buildEffectiveSystemPrompt()`：有效 system prompt precedence，处理 override、coordinator、agent-specific、custom、default、append prompt。
- `src/utils/queryContext.ts` / `fetchSystemPromptParts()`：query 前的上下文构造入口之一，并行获取 default system prompt、user context、system context。
- `src/query.ts` / `appendSystemContext()` 调用点：`query()` 将 `systemContext` 追加到实际发送给模型的 `fullSystemPrompt`。
- `src/utils/api.ts` / `toolToAPISchema()`：把 resolved tool pool 转换成模型可见 tool schema。
- `src/services/api/claude.ts` / `toolSchemas` 构造处：构建模型请求时过滤工具并调用 `toolToAPISchema()`；`hasPendingMcpServers` 主要用于保留 ToolSearch 发现能力。
- `src/utils/attachments.ts` / `getQueuedCommandAttachments()`：把 queued command/task notification 转为模型可见 attachment。
- `src/utils/attachments.ts` / `getAgentPendingMessageAttachments()`：把 pending subagent/coordinator messages 转为 meta queued command attachment。
- `src/Tool.ts` / `ToolUseContext`：runtime-only state 与请求相关 options 的集合，区分模型可见 context 和运行时控制状态。

## Model Streaming

- `src/query.ts` / `query()`：主 stream consumer；关注 `deps.callModel()` 如何 yield stream event、assistant message、tool result。
- `src/query.ts:557` / `toolUseBlocks`：本轮 assistant `tool_use` block 的收集队列。
- `src/query.ts:562` / `useStreamingToolExecution` + `StreamingToolExecutor`：是否启用流式工具执行，以及执行器初始化位置。
- `src/query.ts:659` / `deps.callModel()` loop：模型 streaming 输出进入 runtime 的消费点。
- `src/query.ts:727` / streaming fallback reset：fallback 发生后清空 assistant/tool 状态。
- `src/query.ts:733` / `streamingToolExecutor.discard()`：丢弃失败 streaming attempt 的工具结果，避免 orphan `tool_result`。
- `src/query.ts:827` / `assistantMessages.push(message)`：完成 content block 对应的 assistant message 被纳入 durable transcript 的位置。
- `src/query.ts:829` / `msgToolUseBlocks`：从 assistant content 中提取 `tool_use`。
- `src/query.ts:842` / `streamingToolExecutor.addTool()`：流式路径在模型响应期间提前启动工具。
- `src/query.ts:851` / `getCompletedResults()`：模型仍在 streaming 时取出已完成工具结果。
- `src/query.ts:980` / query error handling：模型流异常时为已出现的 `tool_use` 补 missing result。
- `src/query.ts:1012` / streaming abort handling：中断后继续消费 executor，生成 synthetic `tool_result`。
- `src/query.ts:1380` / `toolUpdates`：统一消费 `StreamingToolExecutor.getRemainingResults()` 或 `runTools()` 的工具结果。
- `src/query.ts:1384` / tool update loop：把工具 message yield 出去，并 normalize 成下一轮 user `tool_result`。
- `src/query.ts:1437` / tool summary extraction：用 `tool_use.id` 匹配 `tool_result.tool_use_id`。
- `src/query.ts:1535` / next-turn boundary：工具完成后再拼接 assistant/tool result/attachments，避免 interleave 非法消息。
- `src/services/api/claude.ts:709` / `queryModelWithoutStreaming()`：非流式 fallback / non-streaming 消费完整 generator 后返回 assistant message。
- `src/services/api/claude.ts:752` / `queryModelWithStreaming()`：对 query loop 暴露 `StreamEvent | AssistantMessage | SystemAPIErrorMessage`。
- `src/services/api/claude.ts:1120` / `queryModel()` request preparation：tool search、filtered tools、beta headers、schema 构建的起点。
- `src/services/api/claude.ts:1235` / `toolSchemas`：调用 `toolToAPISchema()` 生成模型可见 tools。
- `src/services/api/claude.ts:1260` / `normalizeMessagesForAPI()`：API 请求前规范化 transcript。
- `src/services/api/claude.ts:1292` / `ensureToolResultPairing()`：请求边界修复 `tool_use` / `tool_result` 配对。
- `src/services/api/claude.ts:1930` / stream part loop：消费 Anthropic stream，处理 stall、TTFT、`message_start`、content block events。
- `src/services/api/claude.ts:2171` / `content_block_stop`：把单个完成 content block normalize 成 assistant message 并 yield。
- `src/services/api/claude.ts:2229` / `message_delta`：把真实 usage 和 stop reason 回写到最近 yield 的 assistant message。
- `src/utils/messages.ts:2930` / `handleMessageFromStream()`：UI 层根据 stream event 更新 responding、thinking、tool-input、tool-use 状态。

## Tool System

- `src/Tool.ts:158` / `ToolUseContext`：工具执行时的 runtime-only 上下文，包含 tools、AbortController、AppState、permission、UI setters 和 in-progress ids。
- `src/Tool.ts:358` / `findToolByName()`：按 primary name 或 alias 查找工具。
- `src/Tool.ts:362` / `Tool`：工具 runtime contract；看 name、schema、prompt、permission、call、render、result mapping。
- `src/Tool.ts:379` / `Tool.call()`：工具副作用执行入口的统一签名。
- `src/Tool.ts:500` / `Tool.checkPermissions()`：工具级权限判断入口。
- `src/Tool.ts:518` / `Tool.prompt()`：生成模型可见 tool description。
- `src/Tool.ts:557` / `mapToolResultToToolResultBlockParam()`：把内部结果映射成 API `tool_result` block。
- `src/tools.ts`：工具注册/聚合入口，适合看 runtime 暴露给模型的工具集合。
- `src/utils/api.ts:119` / `toolToAPISchema()`：把 `Tool` 转成模型请求里的 API schema。
- `src/utils/api.ts:147` / tool schema cache key：包含 `inputJSONSchema`，避免 StructuredOutput / MCP schema 混用。
- `src/utils/api.ts:157` / input schema selection：优先直接使用 `inputJSONSchema`，否则由 Zod 转 JSON Schema。
- `src/utils/api.ts:169` / API schema base：生成 `name`、`description`、`input_schema`。
- `src/utils/api.ts:194` / `eager_input_streaming`：fine-grained tool streaming 的 per-tool API 字段。
- `src/services/tools/toolOrchestration.ts:19` / `runTools()`：普通工具编排入口。
- `src/services/tools/toolOrchestration.ts:91` / `partitionToolCalls()`：按 `isConcurrencySafe()` 切分并发 batch 和串行 batch。
- `src/services/tools/toolOrchestration.ts:118` / `runToolsSerially()`：非并发工具按顺序执行。
- `src/services/tools/toolOrchestration.ts:152` / `runToolsConcurrently()`：并发安全工具通过 `all()` 并行执行，受最大并发限制。
- `src/services/tools/toolOrchestration.ts:179` / `markToolUseAsComplete()`：删除 in-progress set 中的 `toolUseID`。
- `src/services/tools/toolExecution.ts:337` / `runToolUse()`：单个 `tool_use` 的 runtime 执行入口。
- `src/services/tools/toolExecution.ts:345` / tool lookup：先在模型可见 tools 中找，再兼容 alias fallback。
- `src/services/tools/toolExecution.ts:397` / unknown tool result：找不到工具时生成 is_error `tool_result`。
- `src/services/tools/toolExecution.ts:443` / aborted tool result：abort 时生成取消类 `tool_result`。
- `src/services/tools/toolExecution.ts:455` / `streamedCheckPermissionsAndCallTool()`：把 permission/call/progress 包成 async iterable。
- `src/services/tools/toolExecution.ts:599` / `checkPermissionsAndCallTool()`：schema validation、value validation、hooks、permission、call、result mapping 主流程。
- `src/services/tools/toolExecution.ts:624` / input validation error：Zod 失败转 is_error `tool_result`。
- `src/services/tools/toolExecution.ts:800` / PreToolUse hooks：工具执行前 hook 入口。
- `src/services/tools/toolExecution.ts:921` / permission decision：统一处理 hook/canUseTool/classifier 决策。
- `src/services/tools/toolExecution.ts:1207` / `tool.call()`：真正执行工具，并注入 `toolUseId` 到 context。
- `src/services/tools/toolExecution.ts:1292` / `mapToolResultToToolResultBlockParam()`：工具成功后生成 API result block。
- `src/services/tools/StreamingToolExecutor.ts:40` / `StreamingToolExecutor`：流式工具执行器，适合看执行过程、结果产出和中断/状态更新如何配合。
- `src/services/tools/StreamingToolExecutor.ts:76` / `addTool()`：接收 stream 中新出现的 `tool_use`。
- `src/services/tools/StreamingToolExecutor.ts:129` / `canExecuteTool()`：根据当前 executing tools 和 `isConcurrencySafe` 决定是否能启动。
- `src/services/tools/StreamingToolExecutor.ts:153` / `createSyntheticErrorMessage()`：为 sibling error、user interrupt、streaming fallback 生成 synthetic `tool_result`。
- `src/services/tools/StreamingToolExecutor.ts:265` / `executeTool()`：启动工具、设置 in-progress、收集结果和 context modifiers。
- `src/services/tools/StreamingToolExecutor.ts:412` / `getCompletedResults()`：非阻塞产出 progress 和已完成结果，并调用 `markToolUseAsComplete()`。
- `src/services/tools/StreamingToolExecutor.ts:453` / `getRemainingResults()`：等待所有未完成工具并产出剩余结果。

## Permission / Sandbox

- `src/utils/permissions/permissionSetup.ts:872` / `initializeToolPermissionContext()`：权限上下文初始化入口，合并 CLI allow/deny/base tools、settings/policy/session 规则、额外目录、bypass/auto 可用性和危险权限检测结果。
- `src/types/permissions.ts:28` / `InternalPermissionMode` 与 `src/types/permissions.ts:29` / `PermissionMode`：权限模式类型锚点，覆盖 default/plan/auto/bypass/dontAsk/acceptEdits 等运行时分支。
- `src/Tool.ts:123` / `ToolPermissionContext`：工具权限上下文，保存 mode、alwaysAllowRules、alwaysDenyRules、alwaysAskRules、additionalWorkingDirectories 等状态。
- `src/hooks/useCanUseTool.tsx:27` / `CanUseToolFn`：交互式 runtime 的 permission gate，接收 tool、input、context、assistant message 和 tool_use id。
- `src/utils/permissions/permissions.ts:473` / `hasPermissionsToUseTool()`：通用权限裁决入口，处理 allow 后的 denial tracking、dontAsk 转 deny、auto classifier 等逻辑。
- `src/utils/permissions/permissions.ts:1158` / `hasPermissionsToUseToolInner()`：核心顺序锚点，先 whole-tool deny，再 whole-tool ask，再工具 `checkPermissions()`，再处理工具级 deny/ask/safety，最后才进入 bypass/allow/auto fast path。
- `src/utils/permissions/permissionSetup.ts:379` / `findOverlyBroadBashPermissions()`：识别 `Bash(*)` 等过宽 shell allow 规则。
- `src/utils/permissions/permissionSetup.ts:510` / `stripDangerousPermissionsForAutoMode()`：进入 auto mode 时剥离会绕过 classifier 的危险 allow 规则，并记录可恢复的 stripped rules。
- `src/utils/permissions/permissionSetup.ts:597` / `transitionPermissionMode()`：权限模式切换入口，进入 auto 时调用 `stripDangerousPermissionsForAutoMode()`，离开 classifier 模式时恢复危险规则。
- `src/utils/permissions/permissionSetup.ts:472` / `removeDangerousPermissions()`：底层 helper，把危险 allow 规则从可更新来源移除。
- `src/tools/BashTool/shouldUseSandbox.ts:130` / `shouldUseSandbox()`：Bash sandbox 决策入口，检查 sandbox enablement、`dangerouslyDisableSandbox`、policy 和 excluded commands。
- `src/utils/sandbox/sandbox-adapter.ts` / `SandboxManager`：sandbox 能力、policy 和失败注释的适配层。

## Shell / File Editing

Shell 与文件编辑会在工具章节里展开。源码定位时先从这些具体工具目录进入，再回看 `src/Tool.ts` 的统一接口：

- `src/tools/BashTool/BashTool.tsx:223` / Bash input schema：`command`、`timeout`、`description`、`run_in_background`、`dangerouslyDisableSandbox` 和内部 `_simulatedSedEdit` 的边界。
- `src/tools/BashTool/BashTool.tsx:420` / `BashTool`：Bash 工具定义，覆盖 read-only 判断、permission matcher、schema、权限、执行和 output mapping。
- `src/tools/BashTool/bashPermissions.ts:161` / `getSimpleCommandPrefix()`：从 shell command 生成 approval suggestion prefix 的规则。
- `src/tools/BashTool/bashPermissions.ts:364` / `bashPermissionRule`：Bash permission rule 解析入口。
- `src/tools/BashTool/bashPermissions.ts:1663` / `bashToolHasPermission()`：Bash 内容级权限判断，串起命令安全、规则匹配和建议。
- `src/tools/BashTool/bashCommandHelpers.ts:181` / `checkCommandOperatorPermissions()`：复合命令、分段命令和 shell operator 的权限处理。
- `src/utils/bash/ast.ts:381` / `parseForSecurity()`：tree-sitter shell 解析入口，返回 simple / too-complex / parse-unavailable。
- `src/tools/FileReadTool/FileReadTool.ts:337` / `FileReadTool`：Read 工具定义，关注 read permission、token/size 限制、PDF/image/notebook/text 映射和 `readFileState`。
- `src/tools/GlobTool/GlobTool.ts:57` / `GlobTool`：Glob 路径发现工具。
- `src/tools/GrepTool/GrepTool.ts:160` / `GrepTool`：Grep 文本搜索工具，关注忽略规则、裁剪和 read permission。
- `src/tools/FileEditTool/FileEditTool.ts:86` / `FileEditTool`：Edit 工具定义，关注 old_string/new_string 校验、mtime 防护、patch 生成和写入。
- `src/tools/FileWriteTool/FileWriteTool.ts:94` / `FileWriteTool`：Write 工具定义，关注 create/overwrite、read-before-write、防 stale write 和整文件 diff。
- `src/components/permissions/FileWritePermissionRequest/FileWritePermissionRequest.tsx:15` / `ideDiffSupport`：Write 权限 UI 的 diff/review 集成。
- `src/bridge/sessionRunner.ts:70` / `TOOL_VERBS`：Read、Write、Edit、MultiEdit、Bash 的用户可见动作动词映射；当前 CodeGraph 未发现独立 `MultiEditTool` 符号，可把这里作为 MultiEdit 名称归一化锚点。

## Session / Compaction / Resume

- `src/services/compact/autoCompact.ts`：自动压缩触发逻辑，关注上下文过长时 runtime 如何决定压缩。
- `src/services/compact/compact.ts`：压缩执行逻辑，适合看历史 transcript 如何变成下一轮可用摘要。

## Interrupt / Abort / Continue

中断与继续会跨 query loop、stream 消费和工具执行多个层面。阅读时先从 `src/query.ts` 的控制流入手，再结合具体章节补齐。

## Subagent / Fork

- `src/tools/AgentTool/`：主 agent 调用 subagent 的工具入口，适合看 subagent 如何表现为一个 tool。
- `src/tasks/LocalAgentTask/`：本地 agent task 的执行承载，关注子任务生命周期和结果回传。
- `src/utils/forkedAgent.ts`：fork agent 相关逻辑，适合看隔离 agent loop 与主会话之间的关系。

## Appendix Areas

MCP、plugin、bridge 等扩展面会放到附录章节。源码地图后续可以继续补充锚点，但主阅读顺序仍然以 runtime pipeline 为准。
