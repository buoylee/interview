# Claude Code Model Turn Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Explain how Claude Code constructs the model’s current view and drives one or more model decisions until it emits final text or crosses the Tool Intent boundary.

**Architecture:** Create a self-contained Model Turn overview followed by two causal detail chapters: Context Assembly, then Query Loop and Streaming. The overview owns the local M1–M7 flow; detail chapters enlarge those nodes without duplicating Tool execution, Permission, Session persistence, or Subagent lifecycle.

**Tech Stack:** Markdown, GitHub-compatible Mermaid, Markdown state tables, TypeScript source reading through codebase-memory-mcp, read-only Claude Code source at the pinned commit, Git, rg, Python 3 link verification, and @mermaid-js/mermaid-cli 11.15.0.

## Global Constraints

- Execute only after the Foundation plan has passed its review gate.
- Work only in the isolated redesign worktree.
- Treat /Users/buoy/Development/gitrepo/Claude-Code-true as read-only.
- Use source snapshot 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf; stop and record drift if HEAD differs.
- Use codebase-memory-mcp search_graph, trace_path, and get_code_snippet before native code search.
- Build overall cognition before implementation detail.
- Include a detail only when it changes a flow, state, ordering, concurrency, safety result, recovery behavior, module contract, invariant, or design trade-off.
- Explain the canonical interactive main-agent path before SDK/headless, streaming fallback, feature-gated, and abort variants.
- Keep Tool execution internals in Controlled Effects. Model Turn owns only Tool Intent / Tool Observation protocol boundaries.
- Keep durable transcript, Compaction, Continue, and Resume internals in Session Continuity.
- Put complete interview answers at chapter ends.
- Explain mechanisms before pseudocode, and pseudocode before real source excerpts.
- Record evidence as commit + repository-relative path + symbol; line numbers are auxiliary.
- Distinguish Source-confirmed, Architectural interpretation, and General principle claims.
- Use editable Markdown-compatible diagrams only.
- Use a trusted local Mermaid CLI only when already installed or cached; otherwise apply the browser-isolated Mermaid 11.x verification policy recorded in the plan-suite index, once per diagram block.
- Make one focused commit per independently reviewable article or overview integration.

---

## File Structure

**Create:**

- ai/claude-code-source/01-model-turn/README.md
- ai/claude-code-source/01-model-turn/01-context-assembly.md
- ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md

**Modify:**

- ai/claude-code-source/README.md
- ai/claude-code-source/00-one-agent-turn.md

**Historical material to inspect but not edit:**

- ai/claude-code-source/_archive/2026-06-runtime-pipeline/02-query-loop.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/03-prompt-and-context-assembly.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/04-model-streaming.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/13-source-code-map.md

## Interfaces

- Consumes canonical nodes A2, A3, A4, A5, and A7 from 00-one-agent-turn.md.
- Produces local nodes M1 through M7:
  - M1 Context Sources
  - M2 Effective System Layer
  - M3 Conversation Messages
  - M4 Tool Definitions
  - M5 Attachments and Dynamic Context
  - M6 Model Request and Stream
  - M7 Text Completion or Tool Intent
- Produces the Tool Intent boundary consumed by Controlled Effects.
- Consumes Tool Observation as an opaque return contract from Controlled Effects.
- Produces the distinction among model-visible context, runtime-only turn state, and durable transcript consumed by Session Continuity.

---

### Task 1: Build the Model Turn evidence map

**Files:**

- Inspect only: /Users/buoy/Development/gitrepo/Claude-Code-true/src/
- Use historical notes only as leads, never as proof.

- [ ] **Step 1: Confirm graph freshness and source revision**

Use codebase-memory-mcp list_projects and index_status for project Users-buoy-Development-gitrepo-Claude-Code-true. If the project is missing or stale relative to the pinned commit, run index_repository on /Users/buoy/Development/gitrepo/Claude-Code-true before discovery.

Run:

~~~bash
git -C /Users/buoy/Development/gitrepo/Claude-Code-true rev-parse HEAD
~~~

Expected: 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf.

- [ ] **Step 2: Discover the Context Assembly symbols**

Use search_graph with these exact name patterns or natural-language queries:

~~~text
getSystemPrompt
buildEffectiveSystemPrompt
fetchSystemPromptParts
toolToAPISchema
getQueuedCommandAttachments
getAgentPendingMessageAttachments
ToolUseContext
onQueryImpl
QueryEngine.submitMessage
~~~

Use trace_path outbound from buildEffectiveSystemPrompt, fetchSystemPromptParts, onQueryImpl, and QueryEngine.submitMessage. Use get_code_snippet only on exact qualified names returned by search_graph.

Record an evidence matrix with:

~~~text
claim | path + symbol | what it proves | canonical or variant | model-visible or runtime-only
~~~

- [ ] **Step 3: Discover the Query Loop and Streaming symbols**

Use search_graph for:

~~~text
query
queryModel
queryModelWithStreaming
queryModelWithoutStreaming
handleMessageFromStream
normalizeMessagesForAPI
ensureToolResultPairing
StreamingToolExecutor.addTool
StreamingToolExecutor.getCompletedResults
StreamingToolExecutor.getRemainingResults
~~~

Use trace_path outbound from query and queryModelWithStreaming. Capture:

- current-turn state initialization;
- model call boundary;
- stream-event normalization;
- assistant message accumulation;
- Tool Intent detection;
- continuation/termination decision;
- Tool Observation normalization;
- fallback reset;
- abort and missing-result repair.

- [ ] **Step 4: Reject source-map noise**

Before writing, remove any candidate evidence that only proves:

- UI rendering;
- logging or telemetry;
- a pure forwarding wrapper;
- line-number location without mechanism meaning;
- a feature flag that does not change the explained semantic path.

Expected: the evidence map is organized by M1–M7 claims, not source files.

---

### Task 2: Write Context Assembly from full picture to detail

**Files:**

- Create: ai/claude-code-source/01-model-turn/01-context-assembly.md

**Primary source anchors:**

- src/constants/prompts.ts / getSystemPrompt
- src/utils/systemPrompt.ts / buildEffectiveSystemPrompt
- src/utils/queryContext.ts / fetchSystemPromptParts
- src/screens/REPL.tsx / onQueryImpl
- src/QueryEngine.ts / QueryEngine.submitMessage
- src/query.ts / prependUserContext and appendSystemContext call sites
- src/utils/api.ts / toolToAPISchema
- src/services/api/claude.ts / tool schema construction
- src/utils/attachments.ts / attachment builders
- src/Tool.ts / ToolUseContext

- [ ] **Step 1: Write the opening question, thesis, and M1–M6 local map**

Opening question:

~~~text
模型发起一次决策前，Claude Code 如何决定它此刻能看到什么？
~~~

Thesis:

~~~text
模型输入不是一段 prompt 字符串，而是 runtime 根据稳定规则组装出的模型视图；这个视图与 runtime 自己持有的控制状态并不相同。
~~~

Draw a Mermaid flowchart from M1 Context Sources through M6 Model Request. Keep precedence variants out of the first diagram.

- [ ] **Step 2: Walk the canonical failing-test context**

Show the minimum canonical request containing:

- effective system instructions;
- current user task;
- prior assistant Tool Intent and returned Tool Observation when present;
- model-visible tool schemas;
- relevant file/image/queued attachments;
- cwd/project memory when applicable.

For every component, state:

~~~text
source | transformed by | model-visible form | lifetime | omission consequence
~~~

- [ ] **Step 3: Separate the three kinds of state**

Add a table separating:

- model-visible request content;
- runtime-only ToolUseContext and cancellation/permission state;
- durable transcript state that may later be projected into the request.

Explicitly prevent these false equivalences:

- system prompt equals the whole request;
- tools are natural-language prompt text only;
- ToolUseContext is fully model-visible;
- transcript equals the active model window.

- [ ] **Step 4: Explain assembly mechanics in causal order**

Explain:

1. collect stable and dynamic context sources;
2. choose the effective system layer;
3. construct/normalize conversation messages;
4. convert resolved tools to model-visible schemas;
5. attach conditional runtime observations;
6. form the request consumed by the model boundary.

After each step, show the before/after shape of the model view. Do not list helper calls without a corresponding state transformation.

- [ ] **Step 5: Add precedence and entry variants only after the canonical path**

Attach these variants to the relevant node:

- override, agent-specific, custom, default, and append system prompt;
- interactive REPL versus SDK/headless context assembly;
- MCP instruction delta;
- nested memory and already-loaded path tracking;
- queued command and pending agent message attachments.

State exact applicability. Do not generalize a headless-only rule to REPL or vice versa.

- [ ] **Step 6: Add pseudocode and source lenses**

First add pseudocode that returns:

~~~text
ModelView {
  system,
  messages,
  tools,
  request_options
}
~~~

Then include only decisive source excerpts for:

- effective system-prompt precedence;
- tool schema conversion;
- one conditional attachment path.

Each excerpt must immediately explain input, branch, state/output, and why it matters. Mark inference when the architectural interpretation spans multiple symbols.

- [ ] **Step 7: Add trade-offs, misconceptions, interview answer, and handoff**

Cover:

- cache-stable prefix versus dynamic context;
- explicit model view versus convenient all-in-one runtime context;
- why more context is not always better;
- why custom prompt semantics must be entry-specific.

End with:

~~~text
模型视图已经构造完成；下一步是 runtime 如何消费模型 stream，并决定继续、执行工具还是结束。
~~~

Add previous/next navigation.

- [ ] **Step 8: Verify and commit Context Assembly**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/01-model-turn/01-context-assembly.md -o /tmp/claude-code-context-rendered.md
rg -n 'M[1-6]|model-visible|runtime-only|transcript|标准路径|变体|源码确认|架构解释|面试' ai/claude-code-source/01-model-turn/01-context-assembly.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/01-model-turn/01-context-assembly.md
git diff --check
~~~

Expected:

- render succeeds;
- first command finds all required concepts;
- line-number inventory command exits 1, except a deliberately labelled auxiliary line reference;
- the article reads coherently without opening source.

Run:

~~~bash
git add ai/claude-code-source/01-model-turn/01-context-assembly.md
git commit -m "docs(claude-code): explain model context assembly"
~~~

---

### Task 3: Write Query Loop and Streaming as one causal mechanism

**Files:**

- Create: ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md

**Primary source anchors:**

- src/query.ts / query
- src/query/deps.ts
- src/services/api/claude.ts / queryModel, queryModelWithStreaming, queryModelWithoutStreaming
- src/services/api/claude.ts / normalizeMessagesForAPI, ensureToolResultPairing
- src/services/tools/StreamingToolExecutor.ts / addTool, getCompletedResults, getRemainingResults
- src/utils/messages.ts / handleMessageFromStream

- [ ] **Step 1: Write the opening question, thesis, and Q1–Q8 map**

Opening question:

~~~text
模型视图准备好后，runtime 如何把一次模型输出推进成最终回答或下一轮决策？
~~~

Use local nodes:

~~~text
Q1 Current Turn State
Q2 Call Model
Q3 Consume Stream
Q4 Accumulate Assistant Content
Q5 Detect Text or Tool Intent
Q6 Cross Controlled-Effects Boundary
Q7 Normalize Tool Observation
Q8 Build Next Turn or Stop
~~~

Draw a sequence diagram and a small state diagram. Controlled Effects remains an opaque participant at Q6.

- [ ] **Step 2: Walk one normal text-only turn**

Show:

- prepared Model View enters Q1;
- runtime calls the model at Q2;
- stream events become completed assistant content at Q3/Q4;
- no Tool Intent appears at Q5;
- stop hooks/budget checks aside, the loop returns final text at Q8.

State what is yielded to UI/SDK versus what becomes durable history.

- [ ] **Step 3: Walk one Tool Intent feedback turn**

Use the failing-test scenario:

1. model emits a Read or Grep Tool Intent;
2. runtime records the assistant intent;
3. Controlled Effects returns an associable Tool Observation;
4. runtime normalizes it into the next model-visible message;
5. the next turn contains prior user task, assistant intent, and observation;
6. model continues.

Show before/after message snapshots and the tool ID pairing invariant.

- [ ] **Step 4: Explain streaming without turning it into event inventory**

Explain only stream details that change semantics:

- partial content versus completed assistant blocks;
- when Tool Intent becomes executable;
- why early streaming execution can reduce latency;
- why results cannot violate message ordering;
- why fallback must discard or repair work from the abandoned attempt;
- when final usage/stop reason becomes authoritative.

UI progress rendering and telemetry stay out of scope.

- [ ] **Step 5: Explain continuation and termination**

Provide pseudocode that distinguishes:

~~~text
no Tool Intent → finalize/stop
Tool Intent present → obtain observations → construct next turn
abort/fallback/error → repair protocol state or return explicit terminal transition
~~~

State whether each transition changes:

- current model view;
- runtime turn state;
- durable transcript;
- pending tool execution.

- [ ] **Step 6: Attach failure variants to Q2–Q8**

Cover:

- prompt too long before or after request;
- streaming fallback;
- abort while streaming;
- abort during Tool execution;
- missing Tool Observation repair;
- max-turn termination;
- queued input injection boundary.

Only explain the local contract. Compaction algorithms, queue implementation, and Tool execution internals link forward to their owner chapters.

- [ ] **Step 7: Add decisive source lenses**

Include short excerpts for:

- continuation based on observed Tool Intent;
- assistant message / Tool Intent accumulation;
- Tool Observation normalization into the next turn;
- one abort or fallback repair path.

Do not paste the entire query function. Explain why each selected branch is causally important.

- [ ] **Step 8: Add trade-offs, interview answer, and Controlled Effects handoff**

Cover:

- message history as loop state versus a separate workflow state machine;
- streaming latency versus ordering complexity;
- protocol repair versus simply dropping interrupted work;
- why Tool execution is a runtime concern, not a model concern.

End with:

~~~text
Query Loop 已经得到 Tool Intent；下一部分要回答它如何被解析、调度、授权并转化为机器效果。
~~~

- [ ] **Step 9: Verify and commit Query Loop / Streaming**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md -o /tmp/claude-code-query-rendered.md
rg -n 'Q[1-8]|Tool Intent|Tool Observation|配对|继续|停止|fallback|abort|面试' ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md
git diff --check
~~~

Expected: diagrams render, all state transitions are explained, and source line numbers do not organize the prose.

Run:

~~~bash
git add ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md
git commit -m "docs(claude-code): explain query loop and streaming"
~~~

---

### Task 4: Write the Model Turn overview and integrate navigation

**Files:**

- Create: ai/claude-code-source/01-model-turn/README.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/00-one-agent-turn.md
- Modify: detail chapter navigation created in Tasks 2 and 3.

- [ ] **Step 1: Write the self-contained M1–M7 overview**

The overview must:

- locate A2–A5/A7 in the canonical map;
- draw one complete M1–M7 flow;
- walk the failing-test scenario through Model View → stream → Tool Intent/Observation → next turn;
- state the model-visible/runtime-only/durable distinction;
- state the Tool Intent pairing invariant;
- summarize canonical behavior without source snippets;
- route readers to Context Assembly and Query Loop / Streaming details.

A reader who stops after this README must still understand the full Model Turn mechanism.

- [ ] **Step 2: Add chapter transitions**

Use this order:

~~~text
01-model-turn/README.md
  → 01-context-assembly.md
  → 02-query-loop-and-streaming.md
  → 02-controlled-effects/README.md when Plan 03 creates it
~~~

Until Plan 03 exists, end with a plain-text forward handoff rather than a broken link.

- [ ] **Step 3: Update root navigation and 00**

In root README:

- turn Model Turn from roadmap text into a link;
- add its overview and full-learning routes.

In 00:

- add the next link to 01-model-turn/README.md;
- keep the A1–A8 diagram authoritative;
- do not duplicate M1–M7 details.

- [ ] **Step 4: Run the Model Turn review gate**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/01-model-turn/README.md -o /tmp/claude-code-model-turn-rendered.md
python3 -c 'from pathlib import Path; import re, sys; files=list(Path("ai/claude-code-source").rglob("*.md")); bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn
git diff --check
~~~

Expected:

- Mermaid renders;
- local links pass;
- placeholder scan exits 1;
- all three reading modes remain valid for currently existing files.

- [ ] **Step 5: Review concept ownership**

Confirm:

- Context Assembly owns Model View composition.
- Query Loop / Streaming owns Tool Intent detection, pairing contract, continuation, and termination.
- Neither article explains Permission algorithms, Sandbox internals, durable recovery, or child task lifecycle.
- Repeated explanations are replaced with links and local contract summaries.

- [ ] **Step 6: Commit Model Turn integration**

Run:

~~~bash
git add ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn
git diff --cached --check
git commit -m "docs(claude-code): integrate model turn learning path"
git status --short
~~~

Expected: integration commit succeeds and worktree is clean.
