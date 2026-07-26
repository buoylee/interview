# Claude Code Controlled Effects Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Explain how Claude Code turns a model-produced Tool Intent into a validated, ordered, permission-checked, sandboxed machine effect and then returns a protocol-correct Tool Observation.

**Architecture:** Build one Controlled Effects overview around a single E1–E8 causal path, then deepen it through five owner chapters: Tool Contract and Orchestration, Permission Decision, Bash Security Analysis, Sandbox Runtime, and File Editing Safety. Keep Permission and Sandbox as separate decisions, treat MCP as a Tool adapter rather than a parallel runtime, and return to the Query Loop only through the Tool Observation contract.

**Tech Stack:** Markdown, GitHub-compatible Mermaid, Markdown decision/state tables, TypeScript source reading through codebase-memory-mcp, read-only Claude Code source at the pinned commit, optional separately pinned sandbox-runtime source, Git, rg, Python 3 link verification, and @mermaid-js/mermaid-cli 11.15.0.

## Global Constraints

- Execute only after the Model Turn plan has passed its review gate.
- Work only in the isolated redesign worktree.
- Treat /Users/buoy/Development/gitrepo/Claude-Code-true as read-only.
- Use source snapshot 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf; stop and record drift if HEAD differs.
- Use codebase-memory-mcp search_graph, trace_path, and get_code_snippet before native code search.
- Build overall cognition before implementation detail.
- Include a detail only when it changes a flow, state, ordering, concurrency, safety result, recovery behavior, module contract, invariant, or design trade-off.
- Explain the canonical built-in Tool path before MCP adapters, rejected permissions, hook alterations, concurrent batches, aborts, and sandbox variants.
- Keep model prompting and stream parsing in Model Turn; Controlled Effects begins at Tool Intent and ends at Tool Observation.
- Keep transcript recovery, Compaction, Continue, and Resume in Session Continuity.
- Keep child Agent lifecycle in Subagent Delegation, even though Agent is exposed as a Tool.
- Keep Permission and Sandbox distinct: Permission decides whether an effect is authorized; Sandbox constrains how an authorized process can act.
- Explain mechanisms before pseudocode, and pseudocode before real source excerpts.
- Record evidence as commit + repository-relative path + symbol; line numbers are auxiliary.
- Distinguish Source-confirmed, Architectural interpretation, General principle, and External dependency claims.
- Use editable Markdown-compatible diagrams only.
- Use a trusted local Mermaid CLI only when already installed or cached; otherwise apply the browser-isolated Mermaid 11.x verification policy recorded in the plan-suite index, once per diagram block.
- Make one focused commit per independently reviewable article or overview integration.

---

## File Structure

**Create:**

- ai/claude-code-source/02-controlled-effects/README.md
- ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md
- ai/claude-code-source/02-controlled-effects/02-permission-decision.md
- ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md
- ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md
- ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md

**Modify:**

- ai/claude-code-source/README.md
- ai/claude-code-source/00-one-agent-turn.md
- ai/claude-code-source/01-model-turn/README.md
- ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md

**Historical material to inspect but not edit:**

- ai/claude-code-source/_archive/2026-06-runtime-pipeline/05-tool-system-and-orchestration.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/06-permission-and-sandbox.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/deep-dives/06a-permission-decision.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/deep-dives/06b-bash-security-analysis.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/deep-dives/06c-sandbox-runtime.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/07-shell-and-file-editing.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/12-mcp-plugin-bridge-appendix.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/13-source-code-map.md

## Interfaces

- Consumes Tool Intent from Model Turn at canonical node A5.
- Produces local nodes E1 through E8:
  - E1 Tool Intent Boundary
  - E2 Resolve Tool and Prepare Input
  - E3 Choose Execution Order
  - E4 Validate, Run Hooks, and Decide Permission
  - E5 Execute Inside the Applicable Effect Boundary
  - E6 Normalize Success, Error, Denial, or Cancellation
  - E7 Return Tool Observation
  - E8 Update Runtime and Model-visible State
- Produces an associable Tool Observation consumed by the Query Loop at A7.
- Exposes permission-state and running-effect boundaries consumed by Session Continuity when interruption occurs.
- Treats AgentTool as a specialized adapter whose child lifecycle is owned by Subagent Delegation.

---

### Task 1: Build the Controlled Effects evidence map

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

- [ ] **Step 2: Trace the generic Tool path before studying individual tools**

Use search_graph for:

~~~text
Tool
ToolUseContext
findToolByName
toolToAPISchema
runTools
partitionToolCalls
runSerially
runConcurrently
runToolUse
checkPermissionsAndCallTool
StreamingToolExecutor.addTool
StreamingToolExecutor.canExecuteTool
StreamingToolExecutor.executeTool
StreamingToolExecutor.getRemainingResults
~~~

Use trace_path outbound from runTools, runToolUse, checkPermissionsAndCallTool, and StreamingToolExecutor.addTool. Use trace_path inbound for Tool.call and Tool.checkPermissions. Resolve overloaded names by qualified name before reading snippets.

Record evidence by E1–E8 rather than by file:

~~~text
claim | path + symbol | input state | branch/decision | output state | owner chapter
~~~

- [ ] **Step 3: Trace Permission, Bash, Sandbox, and file-effect branches**

Use search_graph for:

~~~text
initializeToolPermissionContext
hasPermissionsToUseTool
hasPermissionsToUseToolInner
useCanUseTool
getSimpleCommandPrefix
bashPermissionRule
bashToolHasPermission
checkCommandOperatorPermissions
parseForSecurity
shouldUseSandbox
SandboxManager
FileReadTool
GlobTool
GrepTool
FileEditTool
FileWriteTool
~~~

For each branch, identify:

- the generic Tool contract it enters from;
- the decision it uniquely owns;
- the state or policy input it reads;
- the success, denial, cancellation, or error shape it returns;
- whether the behavior is source-local or delegated to an external package.

- [ ] **Step 4: Locate adapter boundaries without widening the scope**

Use search_graph for MCP tool discovery/conversion symbols in:

~~~text
src/services/mcp/client.ts
src/tools.ts
src/utils/api.ts
~~~

Capture only how an external capability becomes a runtime Tool and then a model-visible schema. Do not expand transport negotiation, Plugin installation, Bridge architecture, or remote-server operations into independent chapters.

Also mark AgentTool as a specialized Tool whose E2/E4 boundary is relevant here but whose child execution is deferred to Part 04.

- [ ] **Step 5: Reject misleading evidence and resolve ordering claims**

Before writing, remove:

- UI confirmation rendering that does not change the decision;
- telemetry-only hooks;
- thin forwarding wrappers;
- external sandbox implementation claims not proven by a pinned external source;
- claims that validation, ordering, hooks, and permission always occur in one universal order when the code has per-tool or streaming branches.

Expected: the evidence map can state the canonical causal order while explicitly marking branch-local reordering.

---

### Task 2: Write Tool Contract and Orchestration

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md

**Primary source anchors:**

- src/Tool.ts / ToolUseContext, Tool, findToolByName, call, checkPermissions, prompt, mapToolResultToToolResultBlockParam
- src/tools.ts / built-in and external Tool assembly
- src/utils/api.ts / toolToAPISchema
- src/services/tools/toolOrchestration.ts / runTools, partitionToolCalls, runSerially, runConcurrently
- src/services/tools/toolExecution.ts / runToolUse, checkPermissionsAndCallTool
- src/services/tools/StreamingToolExecutor.ts / addTool, canExecuteTool, executeTool, getCompletedResults, getRemainingResults
- src/services/mcp/client.ts / MCP Tool adapter boundary

- [ ] **Step 1: Open with the Tool Intent-to-Observation contract and E1–E8 map**

Opening question:

~~~text
模型只产生了结构化 Tool Intent；Claude Code 如何把它可靠地变成机器效果，并把结果送回模型？
~~~

Thesis:

~~~text
Tool 系统不是一组可以直接调用的函数，而是一层协议适配与执行控制：它解析意图、选择 Tool、维护顺序、执行每次调用的检查，并把所有终态归一化成可配对的 Tool Observation。
~~~

Draw the full E1–E8 flow. Keep Permission, Bash analysis, Sandbox, file mutation, and child Agent internals collapsed behind clearly named sub-boundaries.

- [ ] **Step 2: Explain the Tool contract in two projections**

Show separately:

1. model-visible projection: Tool name, description, input schema;
2. runtime projection: input validation, ToolUseContext, permission function, call lifecycle, progress, result mapping, cancellation.

Use a table:

~~~text
contract field | seen by model? | consumed by runtime? | why it exists | failure if violated
~~~

State that a Tool Intent is data, not arbitrary code execution.

- [ ] **Step 3: Walk a canonical Read/Grep Tool call**

Follow one Tool Intent through:

1. name resolution;
2. input preparation and validation;
3. execution-order classification;
4. per-call hook and Permission path;
5. Tool.call;
6. result/error/cancel mapping;
7. Tool Observation pairing by tool-use ID;
8. return to Query Loop.

At every node, show the state shape before and after. Avoid replacing the mechanism with a call-chain list.

- [ ] **Step 4: Explain serial/concurrent/streaming orchestration as ordering constraints**

Explain:

- why some Tool calls can be concurrent;
- why some must form a serial boundary;
- how calls discovered during streaming may begin early;
- why output observations must preserve protocol ordering even when effects finish out of order;
- how remaining results are drained at stream completion or cancellation.

Use a Mermaid sequence diagram containing two independent reads and one mutating call. Identify the invariant, not merely the implementation class.

- [ ] **Step 5: Place MCP and AgentTool as adapters**

Add a short subsection showing:

~~~text
external capability → runtime Tool adapter → common Tool contract → model-visible schema
~~~

For MCP, explain only capability discovery/schema/result adaptation and link to the generic Tool path. For AgentTool, explain only that it crosses into a child-loop adapter and link forward to Part 04. Do not create a standalone MCP architecture narrative.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Write mechanism-first pseudocode for:

~~~text
executeToolBatch(toolIntents, context) -> ordered ToolObservations
~~~

Then include short excerpts for:

- Tool resolution and runtime contract;
- serial/concurrent partitioning;
- the per-call execution wrapper;
- final Tool result normalization.

For each excerpt, explain input, branch, state/output, and invariant. If the exact order differs between batch and streaming paths, say so explicitly.

- [ ] **Step 7: Add failure branches, trade-offs, interview answer, and handoff**

Cover:

- unknown Tool and malformed input;
- validation failure before effect;
- hook rejection or transformation;
- Permission denial/cancel;
- Tool exception;
- abort while pending/running;
- missing or out-of-order observations;
- uniform contract versus specialized Tool behavior.

End by asking who authorizes an otherwise valid Tool call and link to Permission Decision.

- [ ] **Step 8: Verify and commit Tool Contract / Orchestration**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md -o /tmp/claude-code-tool-contract-rendered.md
rg -n 'E[1-8]|Tool Intent|Tool Observation|串行|并发|stream|MCP|AgentTool|配对|面试' ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md
git diff --check
~~~

Expected: diagrams render, E1–E8 is complete, MCP remains an adapter, and line numbers do not organize the article.

Run:

~~~bash
git add ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md
git commit -m "docs(claude-code): explain tool contract and orchestration"
~~~

---

### Task 3: Write Permission Decision as an explicit policy pipeline

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/02-permission-decision.md

**Primary source anchors:**

- src/utils/permissions/permissionSetup.ts / initializeToolPermissionContext
- src/types/permissions.ts / permission modes, rule and decision types
- src/Tool.ts / ToolPermissionContext and per-Tool checkPermissions contract
- src/hooks/useCanUseTool.tsx / useCanUseTool
- src/utils/permissions/permissions.ts / hasPermissionsToUseTool, hasPermissionsToUseToolInner
- source-confirmed permission-mode transition helpers found during Task 1

- [ ] **Step 1: Open with the authorization question and P1–P7 map**

Use local nodes:

~~~text
P1 Candidate Effect
P2 Effective Permission Context
P3 Hard Safety / Mode Constraints
P4 Rule Matching
P5 Tool-specific Permission Check
P6 Ask, Allow, or Deny
P7 Updated Permission State and Decision
~~~

Draw one decision flow. Put Sandbox after P6 as a separate downstream boundary, never as a synonym for allow/deny.

- [ ] **Step 2: Define the state model before rule precedence**

Explain:

- session permission mode;
- allow/deny/ask rule sources;
- Tool-specific inputs and path/command scope;
- interactive confirmation capability;
- persisted or updated decision state;
- non-interactive behavior when asking is impossible.

Use state snapshots for a harmless read, an edit outside the normal scope, and a dangerous Bash command.

- [ ] **Step 3: Walk one canonical decision from candidate effect to result**

Trace:

1. build effective Permission context;
2. apply hard safety/mode constraints;
3. match applicable rules;
4. ask the Tool for Tool-specific analysis;
5. decide allow, deny, or ask;
6. if asked, interpret the user response and any rule update;
7. return a decision to the generic Tool executor.

For each step, state whether the effect has happened yet. It must remain false throughout Permission evaluation.

- [ ] **Step 4: Explain precedence only from source-confirmed branches**

Build a table:

~~~text
condition | competing rules/modes | winning decision | can prompt? | state update | evidence
~~~

Include only precedence actually established by the pinned code. If a rule depends on Tool-specific checkPermissions, show that delegation instead of inventing a universal matrix.

- [ ] **Step 5: Explain mode transitions and dangerous bypass boundaries**

Cover:

- normal interactive mode;
- accept-edits or equivalent constrained convenience modes found in source;
- plan/read-only restrictions found in source;
- non-interactive denial behavior;
- any bypass/dangerously-skip mode, its explicit activation boundary, and why it is not ordinary Permission success.

Do not imply that Sandbox compensates for an unsafe Permission mode unless source explicitly establishes that relationship.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Write pseudocode returning a typed result such as:

~~~text
PermissionDecision = Allow | Deny(reason) | Ask(prompt, suggestedRule)
~~~

Then include short excerpts for:

- effective context initialization;
- top-level policy routing;
- one rule-precedence branch;
- interactive decision/state update.

Label UI-only code separately from decision logic.

- [ ] **Step 7: Add failure cases, misconceptions, trade-offs, interview answer, and handoff**

Correct these misconceptions:

- Permission means a UI dialog always appears;
- allow means unrestricted process access;
- Sandbox denial and Permission denial are the same error;
- every Tool shares Bash’s rule grammar;
- a prior allow necessarily applies to every future input.

End by handing a permitted Bash candidate to Bash Security Analysis.

- [ ] **Step 8: Verify and commit Permission Decision**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/02-controlled-effects/02-permission-decision.md -o /tmp/claude-code-permission-rendered.md
rg -n 'P[1-7]|allow|deny|ask|mode|规则|副作用|Sandbox|非交互|面试' ai/claude-code-source/02-controlled-effects/02-permission-decision.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/02-controlled-effects/02-permission-decision.md
git diff --check
~~~

Expected: decision diagram renders, the article proves precedence rather than assuming it, and no effect is described before Allow.

Run:

~~~bash
git add ai/claude-code-source/02-controlled-effects/02-permission-decision.md
git commit -m "docs(claude-code): explain permission decisions"
~~~

---

### Task 4: Write Bash Security Analysis as semantic classification

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md

**Primary source anchors:**

- src/tools/BashTool/BashTool.tsx / Bash Tool contract and permission/sandbox call sites
- src/tools/BashTool/bashPermissions.ts / getSimpleCommandPrefix, bashPermissionRule, bashToolHasPermission
- src/tools/BashTool/bashCommandHelpers.ts / checkCommandOperatorPermissions
- src/utils/bash/ast.ts / parseForSecurity and security-relevant AST representation

- [ ] **Step 1: Open with why raw string prefix matching is insufficient**

Use local nodes:

~~~text
B1 Raw Command
B2 Parse Security-relevant Structure
B3 Classify Operators and Subcommands
B4 Derive Permission Candidates
B5 Match Bash Rules
B6 Allow, Deny, Ask, or Parse-safe Fallback
~~~

Draw a flow using one simple command and one compound command.

- [ ] **Step 2: Establish the Bash-specific threat and trust boundaries**

Explain only the risks that shape this implementation:

- shell operators compose multiple effects;
- redirection changes file state;
- command substitution can hide nested execution;
- quoting and escaping make string splitting unsafe;
- wrappers and environment prefixes can obscure the effective executable;
- a shared prefix does not imply a shared effect.

Do not turn the chapter into a general shell-security catalog.

- [ ] **Step 3: Walk simple-command permission derivation**

Show how a canonical simple command becomes:

~~~text
raw command → security parse → effective command/prefix → rule candidate → Permission decision
~~~

State what information is intentionally preserved or discarded at each transformation.

- [ ] **Step 4: Walk compound-command and operator analysis**

Use representative source-compatible forms containing sequence, pipeline, logical operators, redirection, and substitution. For each form, explain:

- parsed structure;
- independently checked components;
- aggregation rule for allow/deny/ask;
- conservative fallback when analysis cannot prove safety.

Avoid claiming parser coverage beyond the pinned implementation.

- [ ] **Step 5: Connect analysis to Permission without merging the layers**

Explain that Bash analysis produces Tool-specific facts/rule candidates; the Permission pipeline owns the authorization decision. Show the interface in a compact table.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include mechanism-first pseudocode for:

~~~text
analyzeBashForPermission(command) -> commandComponents or conservativeDecision
~~~

Then include short excerpts for:

- AST/security parse entry;
- simple prefix derivation;
- operator/subcommand aggregation;
- mapping to a Bash permission rule.

- [ ] **Step 7: Add edge cases, trade-offs, interview answer, and Sandbox handoff**

Cover:

- parse failure;
- unsupported syntax;
- nested commands;
- quoting/escaping ambiguity;
- overly broad allow rules;
- false positives versus unsafe false negatives;
- semantic parsing cost versus naive prefix matching.

End with: authorization has been decided; execution containment is a different question handled by Sandbox Runtime.

- [ ] **Step 8: Verify and commit Bash Security Analysis**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md -o /tmp/claude-code-bash-security-rendered.md
rg -n 'B[1-6]|AST|operator|prefix|重定向|替换|allow|deny|ask|保守|面试' ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md
git diff --check
~~~

Expected: the article explains semantic classification and does not present string splitting as the mechanism.

Run:

~~~bash
git add ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md
git commit -m "docs(claude-code): explain bash security analysis"
~~~

---

### Task 5: Write Sandbox Runtime as post-authorization containment

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md

**Primary source anchors:**

- src/tools/BashTool/shouldUseSandbox.ts / sandbox eligibility and bypass decision
- src/utils/sandbox/sandbox-adapter.ts / Claude Code to sandbox-runtime adapter
- src/utils/sandbox/sandbox-adapter.ts / SandboxManager adapter facade
- src/tools/BashTool/BashTool.tsx / sandboxed versus unsandboxed launch path
- External dependency only if separately pinned and verified: @anthropic-ai/sandbox-runtime

- [ ] **Step 1: Open with the Permission-versus-containment distinction**

Use local nodes:

~~~text
X1 Authorized Command
X2 Sandbox Eligibility and Policy
X3 Build Runtime Configuration
X4 Launch Through Sandbox Adapter or Explicit Unsandboxed Path
X5 Observe Violation, Exit, Error, or Cancellation
X6 Normalize Bash Result
~~~

Draw a diagram that places Permission before X1 and Tool Observation after X6.

- [ ] **Step 2: Define what can be proven from each repository**

Add an evidence-boundary table:

~~~text
claim | Claude Code source proves | external sandbox-runtime source required | platform-dependent
~~~

Before using external implementation details, verify and record its exact package version and commit. The historical lead is version 0.0.56 at commit 12a3cc172cf343c33a0af6b3e0e98426f9b16139; treat this only as a lead until independently confirmed.

- [ ] **Step 3: Walk sandbox selection and configuration**

Explain:

1. authorized Bash call arrives;
2. source checks sandbox enablement/eligibility and explicit exceptions;
3. runtime builds filesystem/network/process policy inputs found in source;
4. adapter launches the command through the selected path;
5. result or violation returns to BashTool;
6. generic Tool result mapping produces Tool Observation.

State exactly which choices belong to Claude Code and which are delegated.

- [ ] **Step 4: Explain bypass and fallback paths without normalizing them**

Cover only source-confirmed cases:

- sandbox disabled or unavailable;
- command/tool marked incompatible;
- explicit unsandboxed execution path;
- permission escalation/request relationship, if present;
- platform capability differences;
- sandbox initialization or runtime failure.

Do not imply that every allowed Bash command is sandboxed.

- [ ] **Step 5: Explain cancellation and result semantics**

Show how abort, exit status, stderr/stdout, policy violation, and launch failure become distinguishable runtime outcomes before generic Tool normalization.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
runAuthorizedBash(command, permissionResult, sandboxContext) -> BashExecutionResult
~~~

Then include short excerpts for:

- shouldUseSandbox;
- adapter configuration;
- sandboxed/unsandboxed launch branch;
- result/violation normalization.

If the external package is unavailable, explain the adapter contract and mark internals as outside the source boundary instead of guessing.

- [ ] **Step 7: Add trade-offs, misconceptions, interview answer, and file-effect handoff**

Cover:

- defense in depth rather than replacement authorization;
- compatibility versus containment;
- platform abstraction versus leaky OS semantics;
- why an external dependency boundary must be version-pinned;
- why Permission allow does not guarantee successful execution.

End by contrasting process containment with direct file-edit safety.

- [ ] **Step 8: Verify and commit Sandbox Runtime**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md -o /tmp/claude-code-sandbox-rendered.md
rg -n 'X[1-6]|Permission|授权|隔离|adapter|外部依赖|版本|bypass|abort|面试' ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md
git diff --check
~~~

Expected: the article never collapses authorization into containment and labels every external claim.

Run:

~~~bash
git add ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md
git commit -m "docs(claude-code): explain sandbox containment"
~~~

---

### Task 6: Write File Editing Safety around read-before-write invariants

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md

**Primary source anchors:**

- src/tools/FileReadTool or source-confirmed equivalent / read contract and result metadata
- src/tools/GlobTool or source-confirmed equivalent / discovery boundary
- src/tools/GrepTool or source-confirmed equivalent / search boundary
- src/tools/FileEditTool or source-confirmed equivalent / targeted replacement and stale-read checks
- src/tools/FileWriteTool or source-confirmed equivalent / creation/overwrite and permission checks
- shared file-state/cache helpers discovered through trace_path

- [ ] **Step 1: Open with why a permitted write can still be unsafe**

Use local nodes:

~~~text
F1 Discover Target
F2 Read and Capture Observed State
F3 Propose Exact Edit or Write
F4 Validate Path, Prior Read, and Match Preconditions
F5 Apply Atomic-enough Mutation
F6 Return Diff/Result or Explicit Conflict
~~~

Draw the read-before-write path and one stale-state rejection branch.

- [ ] **Step 2: Separate the safety layers**

Create a table separating:

- Permission authorization;
- workspace/path boundary checks;
- prior-read or freshness checks;
- exact-match/uniqueness checks;
- mutation mechanics;
- post-write result reporting.

State which layer prevents which failure and which failures remain possible.

- [ ] **Step 3: Walk a canonical targeted edit**

Use the failing-test scenario:

1. discover the relevant test/source file;
2. read current content;
3. construct a narrowly scoped replacement;
4. verify target/path/prior state and match cardinality;
5. apply mutation;
6. return a diff-like observation;
7. let the model decide whether to test or continue.

Show state snapshots before read, after read, before edit, and after mutation.

- [ ] **Step 4: Contrast Edit and Write contracts**

Explain source-confirmed differences among:

- modifying an existing file;
- creating a new file;
- overwriting an existing file;
- multiple/no match failures;
- stale content or file changed after read;
- line-ending/encoding/large-file constraints if they affect behavior.

Do not generalize a FileEdit invariant to FileWrite unless the source proves it.

- [ ] **Step 5: Explain discovery tools only as prerequisites**

Show how Glob, Grep, and Read reduce uncertainty before mutation. Keep their matching/rendering internals out unless they change file selection, truncation, or the model’s ability to form a safe edit.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
applyTargetedEdit(path, observedState, oldText, newText) -> Applied | Conflict | Rejected
~~~

Then include short excerpts for:

- prior-read/freshness validation;
- match cardinality;
- path/permission boundary;
- result/diff construction.

- [ ] **Step 7: Add failure cases, trade-offs, interview answer, and Session handoff**

Cover:

- nonexistent target;
- unread target;
- stale target;
- ambiguous replacement;
- overwrite boundary;
- abort during effect;
- partial failure or result uncertainty if source permits it;
- exact edit safety versus convenience of arbitrary writes.

End with the question: after effects and observations accumulate, what persists across context pressure, interruption, and a later process?

- [ ] **Step 8: Verify and commit File Editing Safety**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md -o /tmp/claude-code-file-safety-rendered.md
rg -n 'F[1-6]|read|Edit|Write|stale|match|Permission|路径|冲突|面试' ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md
git diff --check
~~~

Expected: the article explains distinct safety layers and never treats a successful Permission decision as sufficient mutation safety.

Run:

~~~bash
git add ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md
git commit -m "docs(claude-code): explain file editing safety"
~~~

---

### Task 7: Write the Controlled Effects overview and integrate navigation

**Files:**

- Create: ai/claude-code-source/02-controlled-effects/README.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/00-one-agent-turn.md
- Modify: ai/claude-code-source/01-model-turn/README.md
- Modify: ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md
- Modify: detail chapter navigation created in Tasks 2–6.

- [ ] **Step 1: Write the self-contained E1–E8 overview**

The overview must:

- locate A5–A7 in the canonical map;
- draw one complete E1–E8 path;
- walk the failing-test Tool Intent through resolution, ordering, Permission, execution, and Tool Observation;
- show Permission, Bash analysis, Sandbox, and file safety as distinct nested decisions;
- state the result-pairing, no-effect-before-authorization, ordering, and explicit-terminal-result invariants;
- summarize adapters, including MCP and AgentTool, without opening standalone architecture tracks;
- route readers to the five detail chapters.

A reader who stops after this README must understand the entire controlled-effect mechanism.

- [ ] **Step 2: Add fluent chapter transitions**

Use this order:

~~~text
02-controlled-effects/README.md
  → 01-tool-contract-and-orchestration.md
  → 02-permission-decision.md
  → 03-bash-security-analysis.md
  → 04-sandbox-runtime.md
  → 05-file-editing-safety.md
  → 03-session-continuity/README.md when Plan 04 creates it
~~~

Until Plan 04 exists, end with a plain-text forward handoff rather than a broken link.

- [ ] **Step 3: Update upstream navigation without duplicating detail**

In root README:

- turn Controlled Effects from roadmap text into a link;
- add overview and full-learning routes.

In 00:

- add the relevant A5–A7 deep link;
- keep A1–A8 authoritative.

In Model Turn:

- replace the plain-text handoff with a link to Controlled Effects;
- keep Controlled Effects opaque inside Q6.

- [ ] **Step 4: Run the Controlled Effects review gate**

Run:

~~~bash
for file in ai/claude-code-source/02-controlled-effects/*.md; do npx -y @mermaid-js/mermaid-cli@11.15.0 -i "$file" -o "/tmp/$(basename "$file" .md)-rendered.md" || exit 1; done
python3 -c 'from pathlib import Path; import re, sys; files=list(Path("ai/claude-code-source").rglob("*.md")); bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn ai/claude-code-source/02-controlled-effects
git diff --check
~~~

Expected:

- all Mermaid documents render;
- local links pass;
- placeholder scan exits 1;
- every effect path produces a success, denial, error, or cancellation observation;
- all three reading modes remain valid for currently existing files.

- [ ] **Step 5: Review concept ownership and causal continuity**

Confirm:

- Tool Contract owns common protocol and orchestration.
- Permission owns authorization and interactive decisions.
- Bash Security owns command semantics used for Bash-specific permission facts.
- Sandbox owns post-authorization process containment.
- File Safety owns read/match/freshness/mutation invariants.
- MCP remains an adapter subsection.
- Query Loop owns continuation after Tool Observation.
- Session Continuity will own durable state and interruption recovery.

Read the closing paragraph of each article followed immediately by the opening paragraph of the next. Revise any abrupt topic jump.

- [ ] **Step 6: Commit Controlled Effects integration**

Run:

~~~bash
git add ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn ai/claude-code-source/02-controlled-effects
git diff --cached --check
git commit -m "docs(claude-code): integrate controlled effects path"
git status --short
~~~

Expected: integration commit succeeds and worktree is clean.
