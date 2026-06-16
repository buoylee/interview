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
- `src/services/api/claude.ts` / `toolToAPISchema()`：把 resolved tool pool 转换成模型可见 tool schema；`hasPendingMcpServers` 主要用于保留 ToolSearch 发现能力。
- `src/utils/attachments.ts` / `getQueuedCommandAttachments()`：把 queued command/task notification 转为模型可见 attachment。
- `src/utils/attachments.ts` / `getAgentPendingMessageAttachments()`：把 pending subagent/coordinator messages 转为 meta queued command attachment。
- `src/Tool.ts` / `ToolUseContext`：runtime-only state 与请求相关 options 的集合，区分模型可见 context 和运行时控制状态。

## Model Streaming

Model streaming 当前先从 `src/query.ts` 和 `src/services/api/claude.ts` 两个入口看起：前者负责消费 stream 并把 assistant message / tool_use 分流进 runtime，后者靠近 Claude API 调用边界。更细的 stream event 符号放到 model streaming 章节展开。

## Tool System

- `src/Tool.ts`：工具抽象定义，适合先看 tool 的接口边界和执行约定。
- `src/tools.ts`：工具注册/聚合入口，适合看 runtime 暴露给模型的工具集合。
- `src/services/tools/toolOrchestration.ts`：工具编排逻辑，关注 `tool_use` 如何被 runtime 接管。
- `src/services/tools/StreamingToolExecutor.ts`：流式工具执行器，适合看执行过程、结果产出和中断/状态更新如何配合。

## Permission / Sandbox

- `src/utils/permissions/permissionSetup.ts`：权限初始化和策略设置入口。
- `src/tools/BashTool/`：Bash 工具相关实现，适合观察命令执行、权限校验和沙箱约束如何落到具体工具。

## Shell / File Editing

Shell 与文件编辑会在工具章节里展开。源码定位时先从这些具体工具目录进入，再回看 `src/Tool.ts` 的统一接口：

- `src/tools/BashTool/`：命令执行入口，适合看 shell effect、权限和沙箱如何结合。
- `src/tools/FileReadTool/`：文件读取工具入口，适合看读文件结果如何回填给模型。
- `src/tools/FileEditTool/`：文件编辑工具入口，适合看局部修改、校验和结果描述。
- `src/tools/FileWriteTool/`：文件写入工具入口，适合看创建/覆盖文件的执行边界。
- `src/tools/GrepTool/`：文本搜索工具入口，适合看搜索参数、输出裁剪和 tool_result 表达。
- `src/tools/GlobTool/`：文件匹配工具入口，适合看路径发现如何作为模型观察结果。

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
