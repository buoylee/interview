# Claude Code Source Learning Docs Redesign

## Goal

Rewrite the notes under `ai/claude-code-source/` into a systematic, interview-oriented learning document about how Claude Code implements a coding agent.

The output should read like a coherent course, not a pile of source-reading notes. It should help the reader explain both:

- how to design a coding agent runtime in principle
- how Claude Code implements that runtime in real source code

## Audience

The primary reader is preparing for interviews and wants to explain the implementation of a coding agent with enough depth to survive follow-up questions.

The reader should be able to:

- give a 1-3 minute interview answer for each major subsystem
- explain the runtime logic of each core feature without reading code line by line
- locate the relevant source files and call paths when asked for implementation evidence
- distinguish core runtime mechanisms from peripheral CLI/UI/product features

## Scope

### In Scope

The main learning path covers the core coding agent runtime:

- runtime entry from CLI, REPL, SDK, and stdin into an agent turn
- query loop and model/tool/result feedback cycle
- prompt and context assembly
- streaming model response handling
- tool abstraction, tool orchestration, and streaming tool execution
- permission modes, approval flow, and sandbox boundaries
- shell command execution
- file search/read/edit/write semantics
- session history, transcript, compaction, and resume
- interrupt, abort, queued commands, and continue semantics
- subagent runtime, background tasks, sidechain transcript, and agent communication
- fork subagent and prompt cache behavior

### Out of Scope for the Main Path

The following areas are useful but should not dominate the main learning path:

- React/Ink UI rendering details
- command catalog details unrelated to the agent loop
- desktop bridge internals
- remote bridge details
- plugin marketplace details
- onboarding, themes, status line, telemetry, and product polish

These may appear only as appendices or as integration points when they connect to the runtime.

## Rewrite Strategy

Use a full rewrite, not a light reorganization.

Existing notes under `ai/claude-code-source/` are useful as source material, especially the subagent notes, but the new document should not inherit their order. The current notes begin from subagents; the rewritten version should begin from the overall coding agent runtime and reach subagents later as an advanced extension.

Old notes should be moved into an archive directory and treated as raw material.

## Document Shape

Use a linear tutorial with interview playbook support:

- the main chapters are meant to be read in order
- each core chapter ends with interview questions and answer templates
- a source map appendix lets the reader jump from source file to chapter

Recommended structure:

```text
ai/claude-code-source/
  README.md
  00-coding-agent-big-picture.md
  01-runtime-entry.md
  02-query-loop.md
  03-prompt-and-context-assembly.md
  04-model-streaming.md
  05-tool-system-and-orchestration.md
  06-permission-and-sandbox.md
  07-shell-and-file-editing.md
  08-session-history-compaction-resume.md
  09-interrupt-abort-continue.md
  10-subagent-runtime.md
  11-fork-subagent-and-prompt-cache.md
  12-mcp-plugin-bridge-appendix.md
  13-source-code-map.md
  14-interview-playbook.md
  _archive/
```

## Chapter Template

Every core chapter should use the same shape:

1. Interview answer
2. Runtime problem
3. Mental model
4. Implementation logic
5. Source anchors
6. Main data structures and runtime state
7. Normal path
8. Failure, interruption, or boundary path
9. Mermaid diagram
10. Design trade-offs
11. Interview follow-ups
12. One-sentence summary

## Depth Standard

The core chapters must explain implementation logic deeply, but they do not need to explain code style or every line of code.

For every core runtime feature, the chapter must answer:

- What runtime problem does this feature solve?
- What input data starts the feature?
- Which runtime modules handle it?
- What state changes while it runs?
- What output does it produce?
- How does the result return to the model, user, transcript, or another agent?
- What happens on permission denial, tool failure, interruption, or context pressure?
- What design trade-off does this implementation make?

The acceptance bar is:

> After reading a core chapter, the reader can explain the feature's implementation principle without looking at code. If asked for evidence, they can jump to the right source files and call paths.

## Core Coverage Matrix

| Chapter | Required implementation logic |
|---|---|
| Runtime Entry | How CLI, REPL, SDK, and stdin become an agent turn. Explain what is runtime input versus UI/input plumbing. |
| Query Loop | How `messages -> model -> stream -> tool_use -> tool_result -> next loop` forms the main closure of the agent. |
| Prompt and Context Assembly | How system prompt, agent prompt, tool descriptions, user messages, attachments, memory, CLAUDE.md, queued commands, compaction summary, and tool history become model input. |
| Model Streaming | How stream events accumulate into assistant text and tool use blocks, and when the runtime can execute tools. |
| Tool System and Orchestration | How tool schemas, permissions, calls, rendering, result IDs, parallel/streaming execution, and failures fit together. |
| Permission and Sandbox | How model intent is separated from runtime authorization, including permission modes, allow/deny rules, approval prompts, and sandbox execution. |
| Shell and File Editing | How Bash, Read, Glob/Grep, Edit, MultiEdit, and Write implement coding capability while keeping operations inspectable and recoverable. |
| Session, Compaction, Resume | How transcript and message history survive long tasks, when compaction happens, and how summaries re-enter context. |
| Interrupt, Abort, Continue | What ESC cancels, how AbortController scopes work, where queued commands go, and why continue starts a new turn rather than restoring a call stack. |
| Subagent Runtime | How Agent tool starts another query loop, how context is isolated, how background tasks are tracked, and how sidechain transcript/pending messages/task output communicate. |
| Fork and Prompt Cache | How fork agents preserve prompt prefix, why that helps prompt cache, and what breaks cache compatibility. |
| MCP/Plugin/Bridge Appendix | How external capabilities enter the tool pool or runtime surface without becoming the core loop. |

## Prompt and Context Assembly Requirement

Prompt/context assembly is a first-class core chapter, not a small subsection.

It must explain that the model input is not a single prompt string. It is a runtime-assembled request containing several sources:

- default system prompt
- custom, append, or override system prompt
- main-thread or subagent-specific prompt
- tool descriptions and schemas
- current user message
- previous assistant and tool result messages
- queued command attachments
- pending subagent message attachments
- pasted images and file attachments
- memory and CLAUDE.md-style project instructions
- current working directory and environment details
- compaction summaries and session history

The chapter should use source anchors such as:

- `src/constants/prompts.ts`
- `src/utils/systemPrompt.ts`
- `src/utils/queryContext.ts`
- `src/utils/attachments.ts`
- `src/Tool.ts`
- `src/tools/AgentTool/loadAgentsDir.ts`

It should include a Mermaid diagram showing how prompt sources flow into the model request.

## Source Anchors

Use source anchors as evidence, not as the organizing principle.

Important anchors include:

- `src/main.tsx`
- `src/screens/REPL.tsx`
- `src/query.ts`
- `src/query/deps.ts`
- `src/constants/prompts.ts`
- `src/utils/systemPrompt.ts`
- `src/utils/queryContext.ts`
- `src/utils/attachments.ts`
- `src/Tool.ts`
- `src/tools.ts`
- `src/services/api/claude.ts`
- `src/services/tools/toolOrchestration.ts`
- `src/services/tools/StreamingToolExecutor.ts`
- `src/utils/permissions/permissionSetup.ts`
- `src/tools/BashTool/`
- `src/tools/FileReadTool/`
- `src/tools/FileEditTool/`
- `src/tools/FileWriteTool/`
- `src/services/compact/autoCompact.ts`
- `src/services/compact/compact.ts`
- `src/utils/messageQueueManager.ts`
- `src/tools/AgentTool/`
- `src/tasks/LocalAgentTask/`
- `src/utils/forkedAgent.ts`

## Diagrams

Use Mermaid where diagrams clarify runtime behavior.

Expected diagram types:

- flowchart for the overall runtime pipeline
- sequence diagram for a user turn with tool calls
- flowchart for prompt/context assembly
- state diagram for interrupt/abort/continue
- sequence diagram for background subagent completion
- flowchart for compaction and resume

## Interview Playbook

The final interview playbook should collect common questions and point back to chapters.

Example question categories:

- How would you implement a coding agent?
- How does the agent decide when to use tools?
- How are tool calls executed safely?
- How do you prevent a model from directly mutating files without approval?
- How do long sessions avoid context overflow?
- What does continue mean after interruption?
- How do subagents work without becoming separate processes?
- Why does forked context help prompt cache?
- How would MCP or plugins fit into this architecture?

## Worktree Workflow

Work should happen in the `interview` notes repo on branch:

```text
codex/claude-code-source-docs
```

Worktree path:

```text
/Users/buoy/Development/gitrepo/interview/.worktrees/claude-code-source-docs
```

Main should not be modified directly. After the rewrite is complete and reviewed, merge the branch back into `main`.

## Verification

Since this is a Markdown-heavy notes repo, verification should focus on:

- clean git status before and after planned edits
- all expected chapter files exist
- README links point to existing files
- archive links still preserve old material
- headings follow the agreed template where applicable
- Mermaid blocks are syntactically plausible
- source anchors use accurate repository paths
- the interview playbook maps questions to chapters

## Implementation Planning Guidance

The implementation plan should not rewrite all chapters in one unstructured pass. It should create the skeleton first, preserve old notes in `_archive/`, then fill the highest-value core chapters in order:

1. big picture
2. query loop
3. prompt/context assembly
4. tool system/orchestration
5. permission/sandbox
6. shell/file editing
7. session/compaction/resume
8. interrupt/abort/continue
9. subagent/fork
