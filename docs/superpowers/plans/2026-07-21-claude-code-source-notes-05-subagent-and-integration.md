# Claude Code Subagent Delegation and Final Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Explain how Claude Code turns an Agent Tool Intent into an isolated child loop, manages foreground/background lifecycle and communication, returns the child result to the parent, then finish the complete interview-oriented learning path with bounded runtime-entry and evidence appendices.

**Architecture:** Build one Subagent Delegation overview around D1–D8, then deepen it through four owner chapters: Child Loop and Context Isolation, Foreground/Background Lifecycle, Communication and Result Return, and Fork / Prompt Cache. Finish with two intentionally narrow appendices and an interview playbook. Run a repository-wide ownership, navigation, diagram, evidence, and readability review before declaring the redesign complete.

**Tech Stack:** Markdown, GitHub-compatible Mermaid, Markdown lifecycle/state tables, TypeScript source reading through codebase-memory-mcp, read-only Claude Code source at the pinned commit, Git, rg, Python 3 link verification, and @mermaid-js/mermaid-cli 11.15.0.

## Global Constraints

- Execute only after the Session Continuity plan has passed its review gate.
- Work only in the isolated redesign worktree.
- Treat /Users/buoy/Development/gitrepo/Claude-Code-true as read-only.
- Use source snapshot 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf; stop and record drift if HEAD differs.
- Use codebase-memory-mcp search_graph, trace_path, and get_code_snippet before native code search.
- Build overall cognition before implementation detail.
- Include a detail only when it changes a flow, state, ordering, concurrency, safety result, recovery behavior, module contract, invariant, or design trade-off.
- Explain one canonical foreground child Agent path before backgrounding, Resume, SendMessage wake-up, fork, worktree, and cache variants.
- Treat AgentTool as both a parent Tool boundary and an adapter into a child Query Loop; do not describe it as a normal function call.
- Keep generic Tool resolution/Permission/result pairing in Controlled Effects.
- Keep parent transcript projection and recovery in Session Continuity.
- Keep runtime entry forms and MCP/Plugin/Bridge out of the primary learning spine. Runtime entry receives one bounded appendix; MCP remains a Tool adapter in Controlled Effects.
- Keep child model-visible context, child runtime-only state, child durable/task state, and parent state explicitly separate.
- Explain mechanisms before pseudocode, and pseudocode before real source excerpts.
- Record evidence as commit + repository-relative path + symbol; line numbers are auxiliary.
- Distinguish Source-confirmed, Architectural interpretation, and General principle claims.
- Use editable Markdown-compatible diagrams only.
- Use a trusted local Mermaid CLI only when already installed or cached; otherwise apply the browser-isolated Mermaid 11.x verification policy recorded in the plan-suite index, once per diagram block.
- Make one focused commit per independently reviewable article or integration unit.
- Do not merge, delete the worktree, or delete its branch as part of this plan.

---

## File Structure

**Create:**

- ai/claude-code-source/04-subagent-delegation/README.md
- ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md
- ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md
- ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md
- ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
- ai/claude-code-source/appendices/runtime-entry-adapters.md
- ai/claude-code-source/appendices/source-evidence-index.md
- ai/claude-code-source/99-interview-playbook.md

**Modify:**

- ai/claude-code-source/README.md
- ai/claude-code-source/00-one-agent-turn.md
- ai/claude-code-source/03-session-continuity/README.md
- ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
- all previously created part README files and detail chapters for final previous/next navigation and evidence-index links

**Historical material to inspect but not edit:**

- ai/claude-code-source/_archive/2026-06-runtime-pipeline/01-runtime-entry.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/10-subagent-runtime.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/11-fork-subagent-and-prompt-cache.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/12-mcp-plugin-bridge-appendix.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/13-source-code-map.md

## Interfaces

- Consumes an Agent Tool Intent through Controlled Effects at canonical node A5/A6.
- Produces local nodes D1 through D8:
  - D1 Parent Emits Agent Tool Intent
  - D2 AgentTool Resolves Route and Mode
  - D3 Construct Child Context and Tool Set
  - D4 Run Child Query Loop
  - D5 Manage Foreground or Background Task Lifecycle
  - D6 Communicate, Resume, or Drain Notifications
  - D7 Normalize Child Result as Parent Tool Observation
  - D8 Parent Query Loop Continues
- Adds a fork branch from D2/D3 that reuses selected parent messages under explicit cache-safe and isolation rules.
- Returns to the already-defined parent Query Loop; it does not create a second top-level architecture.
- Final integration closes the canonical A1–A8 learning loop and exposes interview-length answer paths.

---

### Task 1: Build the Subagent Delegation evidence map

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

- [ ] **Step 2: Trace the canonical AgentTool-to-child-query path**

Use search_graph for:

~~~text
AgentTool.call
runAgent
createSubagentContext
LocalAgentTask
runAsyncAgentLifecycle
resumeAgent
SendMessageTool
TaskOutputTool
~~~

Use trace_path outbound from AgentTool.call, runAgent, and createSubagentContext. Use trace_path inbound for query or the exact child-query symbol returned by the graph. Resolve React/file naming ambiguity by qualified name before reading snippets.

Record by D1–D8:

~~~text
claim | path + symbol | parent input | child state transition | parent output | canonical or variant
~~~

- [ ] **Step 3: Trace foreground/background state and notification delivery**

Use search_graph for symbols in:

~~~text
src/tasks/LocalAgentTask/LocalAgentTask.tsx
src/tools/AgentTool/agentToolUtils.ts
src/tools/AgentTool/resumeAgent.ts
src/tools/SendMessageTool
src/tools/TaskOutputTool
~~~

Identify source-confirmed states and transitions for:

- creation/registration;
- running in foreground;
- conversion or launch into background;
- completion, failure, cancellation;
- notification queueing/draining;
- output polling or retrieval;
- resumption/wake-up caused by communication.

Do not invent a generic task-state enum if the implementation distributes state across types and helpers; synthesize only with an Architectural interpretation label.

- [ ] **Step 4: Trace fork, worktree, and prompt-cache behavior**

Use search_graph for:

~~~text
ForkedAgentParams
CacheSafeParams
createSubagentContext
forkSubagent
FORK_AGENT
isInForkChild
buildForkedMessages
worktree
prompt cache
~~~

Use exact graph results to establish:

- eligibility/gates for fork mode;
- which parent messages/context are reused;
- which runtime state is freshly constructed;
- how recursive fork is prevented;
- how worktree/isolation notices enter the child;
- what CacheSafeParams actually guarantees;
- how the fork returns into normal task/result lifecycle.

- [ ] **Step 5: Reject boundary confusion**

Remove or rewrite any evidence that implies:

- the child shares the parent’s mutable runtime state;
- foreground/background changes the semantic result contract;
- SendMessage mutates a suspended child stack directly;
- fork means cloning an entire process/session without filtering;
- prompt-cache reuse is the reason for every context-isolation rule;
- AgentTool bypasses generic Tool Permission and Tool Observation contracts.

Expected: every cross-boundary claim names what is copied, referenced, queued, reconstructed, or returned.

---

### Task 2: Write Child Loop and Context Isolation

**Files:**

- Create: ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md

**Primary source anchors:**

- src/tools/AgentTool/AgentTool.tsx / input schema, AgentTool.call, routing and prompt branches
- src/tools/AgentTool/runAgent.ts / child initial state, Permission inheritance, Tool resolution, system prompt, abort wiring
- src/utils/forkedAgent.ts / createSubagentContext and shared child-context construction
- src/query.ts or source-confirmed query entry / child Query Loop boundary

- [ ] **Step 1: Open with the nested-loop question and D1–D8 map**

Opening question:

~~~text
父 Agent 发出 Agent Tool Intent 后，Claude Code 为什么不是调用一个函数，而是构造并运行另一个受约束的 agent loop？
~~~

Thesis:

~~~text
Subagent 是父 Tool 调用内部的一次独立 Query Loop：父侧只看见 Tool Intent 与最终 Tool Observation，子侧拥有单独组装的模型视图、工具集、权限上下文和生命周期。
~~~

Draw the full D1–D8 sequence with Parent Query Loop, AgentTool, Child Runtime, Child Model, and Task Registry participants.

- [ ] **Step 2: Define the parent/child state boundary**

Create a table:

~~~text
state | inherited/copy/derived/fresh/shared? | parent can mutate? | child can mutate? | model-visible to whom? | lifetime
~~~

Include source-confirmed handling of:

- task prompt and description;
- system prompt/persona;
- selected conversation/context;
- Tool set and ToolUseContext;
- Permission context/mode;
- model and request options;
- cwd/worktree/environment metadata;
- AbortController;
- task identity and output buffer.

- [ ] **Step 3: Walk one canonical foreground child task**

Use the failing-test scenario:

1. parent decides a bounded investigation should be delegated;
2. model emits Agent Tool Intent;
3. generic Tool layer resolves/checks AgentTool;
4. AgentTool chooses the normal foreground route;
5. runtime constructs child context and allowed tools;
6. child runs its own model/tool feedback loop;
7. child terminal output is normalized;
8. parent receives one Tool Observation and continues.

Show parent and child message snapshots at D1, D3, D4, and D7.

- [ ] **Step 4: Explain child context construction in causal order**

Explain:

1. select agent type/configuration;
2. derive child prompt/system instructions;
3. establish isolation and inherited constraints;
4. resolve the child Tool set;
5. create child runtime-only controls;
6. enter the shared Query Loop with child-owned messages;
7. collect terminal child output.

For each step, state what failure it prevents or behavior it enables.

- [ ] **Step 5: Explain recursion, Permission, and cancellation boundaries**

Cover source-confirmed behavior for:

- whether the child can invoke AgentTool again;
- how parent Permission mode/rules constrain or seed the child;
- whether the child can ask the user directly;
- how parent cancellation reaches child execution;
- how child Tool effects remain subject to the normal Controlled Effects path.

Do not turn this into a repeat of Permission or Tool orchestration.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
runAgentTool(parentIntent, parentContext) -> parentToolObservation
~~~

Then include short excerpts for:

- route selection inside AgentTool.call;
- child context construction;
- child Tool/Permission setup;
- child Query Loop invocation;
- terminal result mapping.

- [ ] **Step 7: Add failure cases, trade-offs, interview answer, and lifecycle handoff**

Cover:

- unknown agent type;
- invalid prompt/route;
- child Tool restriction;
- child model/tool error;
- abort;
- context isolation versus useful inheritance;
- bounded delegation versus nested complexity;
- why parent receives a summarized/normalized result rather than child runtime state.

End by asking how the same semantic child task changes operationally when it runs in the background.

- [ ] **Step 8: Verify and commit Child Loop / Context Isolation**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md -o /tmp/claude-code-child-loop-rendered.md
rg -n 'D[1-8]|Parent|Child|Query Loop|Tool Intent|Tool Observation|context|Permission|隔离|继承|面试' ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md
git diff --check
~~~

Expected: the diagram makes nested ownership clear and the article never describes shared mutable parent/child context without evidence.

Run:

~~~bash
git add ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md
git commit -m "docs(claude-code): explain child agent loop"
~~~

---

### Task 3: Write Foreground / Background Lifecycle as a task state machine

**Files:**

- Create: ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md

**Primary source anchors:**

- src/tools/AgentTool/AgentTool.tsx / async registration and foreground-to-background branches
- src/tasks/LocalAgentTask/LocalAgentTask.tsx / task state, output queue, notification draining, foreground/background registration
- src/tools/AgentTool/agentToolUtils.ts / runAsyncAgentLifecycle
- src/tools/AgentTool/resumeAgent.ts / task resume behavior
- src/tools/TaskOutputTool or source-confirmed equivalent / observation/polling boundary

- [ ] **Step 1: Open with operational mode versus semantic contract**

Use source-confirmed states, normalized into a diagram such as:

~~~text
Created → Registered → RunningForeground → Completed
                         ↘ Backgrounding → RunningBackground → Completed/Failed/Cancelled
Completed/Failed → NotificationPending → Observed/Drained
~~~

If actual states differ, adapt names to the source and mark any synthesized state machine as Architectural interpretation.

- [ ] **Step 2: Define lifecycle ownership**

Create a table:

~~~text
state/resource | owner | entered by | exited by | durable? | visible to parent model? | cancellation behavior
~~~

Include task identity, promise/process handle, output/progress buffer, notification queue, foreground mode, background mode, terminal result, and Tool Observation delivery.

- [ ] **Step 3: Walk the canonical foreground lifecycle**

Show create → register → run → stream/collect child events → terminal output → unregister/settle → parent Tool Observation. Explain why foreground blocks the parent Tool call while not collapsing the parent and child loops.

- [ ] **Step 4: Walk background launch and foreground-to-background conversion**

Establish separately:

- requested-as-background at launch;
- a running foreground task moved to background;
- what returns immediately to the parent in each case;
- how the task remains discoverable;
- how completion is announced later;
- what output/result remains retrievable.

Do not imply identical timing or return shapes without source proof.

- [ ] **Step 5: Explain completion, failure, cancellation, and cleanup**

For every terminal path, identify:

- task registry transition;
- retained output/result;
- parent notification;
- Tool Observation or attachment path;
- cleanup ownership;
- race behavior when completion and mode change coincide.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
manageLocalAgentTask(taskSpec, executionMode) -> ImmediateHandle or TerminalResult
~~~

Then include short excerpts for:

- task registration;
- async lifecycle wrapper;
- foreground-to-background transition;
- terminal-state/notification handling;
- output retrieval or resume.

- [ ] **Step 7: Add trade-offs, misconceptions, interview answer, and communication handoff**

Correct:

- background means detached and untracked;
- foreground means the parent and child share one model loop;
- completion notification contains the whole child runtime;
- changing mode restarts the child;
- cancellation necessarily undoes completed effects.

Discuss responsiveness versus deterministic result timing, retention versus cleanup, and task registry complexity.

End by asking how parent, child, and sibling tasks exchange messages without breaking isolation.

- [ ] **Step 8: Verify and commit Foreground / Background Lifecycle**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md -o /tmp/claude-code-agent-lifecycle-rendered.md
rg -n 'Created|Registered|Foreground|Background|Completed|Failed|Cancelled|notification|registry|race|面试' ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md
git diff --check
~~~

Expected: every state has an owner and every terminal branch has an explicit parent-visible outcome.

Run:

~~~bash
git add ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md
git commit -m "docs(claude-code): explain agent task lifecycle"
~~~

---

### Task 4: Write Communication and Result Return as queued boundary crossings

**Files:**

- Create: ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md

**Primary source anchors:**

- src/tools/SendMessageTool or source-confirmed equivalent / local recipient routing and message delivery
- src/tasks/LocalAgentTask/LocalAgentTask.tsx / message/output queue and notification draining
- src/tools/AgentTool/resumeAgent.ts / waking/resuming an addressable task
- src/tools/TaskOutputTool or source-confirmed equivalent / task-output retrieval
- src/utils/attachments.ts or source-confirmed equivalent / pending-agent-message attachments
- src/query.ts / attachment injection and next-turn boundary

- [ ] **Step 1: Open with communication as message passing, not shared memory**

Use local nodes:

~~~text
G1 Sender Emits SendMessage or Requests Task Output
G2 Resolve Recipient / Task Identity
G3 Validate Delivery State
G4 Queue Message or Read Output Snapshot
G5 Wake / Resume Recipient if Applicable
G6 Inject Pending Message at Recipient Turn Boundary
G7 Recipient Produces New Output
G8 Notify / Return Result to Requester
~~~

Draw one sequence for parent-to-child SendMessage and one compact reverse-result path.

- [ ] **Step 2: Define identities, channels, and payloads**

Create a table:

~~~text
channel | sender | recipient | identity key | payload shape | delivery timing | acknowledgement/result
~~~

Include only source-supported combinations such as parent-to-child, child-to-parent, or sibling/team messaging. Explicitly mark unsupported or separately implemented remote/team paths.

- [ ] **Step 3: Walk one message delivery**

Show:

1. sender forms structured message Tool Intent;
2. runtime resolves an addressable task/agent;
3. state validation prevents delivery to an invalid target;
4. message enters the recipient’s pending queue;
5. dormant/background recipient is resumed if source does so;
6. attachment/message enters the recipient’s next model-visible context;
7. recipient continues its own Query Loop.

State exactly when delivery is considered successful.

- [ ] **Step 4: Walk child completion back to the parent**

Contrast:

- foreground direct terminal result;
- background completion notification;
- explicit TaskOutput retrieval/poll;
- pending-agent-message attachment on a later parent turn.

Show which path produces a Tool Observation, which produces an attachment/message, and which only returns status.

- [ ] **Step 5: Explain ordering, duplication, and wake-up semantics**

Cover source-confirmed guarantees for:

- queued order;
- drain/acknowledgement;
- repeated polling;
- duplicate notification prevention;
- recipient already completed/failed;
- message and completion racing;
- resume without restoring a suspended call stack.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
deliverAgentMessage(sender, recipientId, payload) -> DeliveryResult
collectAgentResult(taskId) -> Pending | TerminalResult
~~~

Then include short excerpts for:

- local recipient routing;
- pending-message queue mutation;
- recipient wake/resume;
- output/notification draining;
- parent-facing result normalization.

- [ ] **Step 7: Add failure cases, trade-offs, interview answer, and fork handoff**

Cover:

- unknown recipient;
- completed recipient;
- full/closed queue if source supports it;
- cancellation race;
- repeated output request;
- message passing versus shared mutable state;
- eventual notification versus immediate parent blocking.

End by asking how fork mode can reuse parent context efficiently while retaining child isolation.

- [ ] **Step 8: Verify and commit Communication / Result Return**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md -o /tmp/claude-code-agent-communication-rendered.md
rg -n 'G[1-8]|SendMessage|TaskOutput|queue|recipient|notification|attachment|resume|Tool Observation|面试' ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md
git diff --check
~~~

Expected: every communication path names its queue/identity/result boundary and does not imply shared mutable conversational state.

Run:

~~~bash
git add ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md
git commit -m "docs(claude-code): explain agent communication"
~~~

---

### Task 5: Write Fork and Prompt Cache as an optimized child-context variant

**Files:**

- Create: ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md

**Primary source anchors:**

- src/tools/AgentTool/AgentTool.tsx / fork routing and prompt branches
- src/utils/forkedAgent.ts / CacheSafeParams, ForkedAgentParams, createSubagentContext
- src/tools/AgentTool/forkSubagent.ts / fork gates, FORK_AGENT, isInForkChild, buildForkedMessages, worktree notice
- source-confirmed prompt-cache configuration/usage reached through trace_path

- [ ] **Step 1: Open by locating fork as a D2/D3 variant**

Use local nodes:

~~~text
K1 Parent Context Candidate
K2 Fork Eligibility and Recursion Gate
K3 Select Cache-safe / Shareable Prefix
K4 Build Forked Child Messages
K5 Add Child-specific Prompt and Isolation Notice
K6 Create Fresh Child Runtime State
K7 Run Normal Child Query Loop
K8 Return Through Normal Task Result Contract
~~~

Draw fork as a side branch that rejoins D4 and D7. Do not draw it as a parallel agent framework.

- [ ] **Step 2: Define reuse versus isolation precisely**

Create a table:

~~~text
parent artifact | reused verbatim | transformed | omitted | fresh child equivalent | cache implication | safety reason
~~~

Include messages, system prompt layers, Tool schemas, dynamic attachments, Permission/runtime state, task identity, cwd/worktree context, AbortController, and mutable queues.

- [ ] **Step 3: Walk the canonical fork path**

Show:

1. AgentTool selects fork route;
2. gates reject unsupported/nested cases;
3. runtime builds fork-safe parent message prefix;
4. child-specific task prompt and isolation notices are appended;
5. fresh child controls and Tool context are created;
6. child enters the normal Query Loop;
7. result returns through the normal Agent task/Tool Observation path.

Show before/after message shapes and identify the cache-stable prefix.

- [ ] **Step 4: Explain prompt-cache relevance without overclaiming**

Establish from source:

- which parameters are named or treated as cache-safe;
- which content ordering helps prefix reuse;
- which dynamic child data must come after the stable prefix;
- whether caching is an explicit API feature, an architectural optimization, or both;
- what happens semantically if the cache is cold or unavailable.

State that correctness cannot depend on a cache hit unless source explicitly proves otherwise.

- [ ] **Step 5: Explain recursion and worktree isolation boundaries**

Cover source-confirmed handling of:

- isInForkChild/FORK_AGENT guard;
- nested fork prevention;
- child Tool availability;
- worktree or cwd notice injection;
- shared filesystem versus isolated workspace semantics;
- parent changes visible/not visible to the child.

Do not infer filesystem isolation solely from a prompt notice.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
buildForkedChild(parentState, task) -> { cacheSafePrefix, childMessages, freshRuntime }
~~~

Then include short excerpts for:

- route/gate selection;
- CacheSafeParams/ForkedAgentParams contract;
- buildForkedMessages;
- recursion guard;
- worktree notice or child-specific suffix.

- [ ] **Step 7: Add failure cases, trade-offs, interview answer, and main-spine return**

Cover:

- ineligible/nested fork;
- oversized inherited context;
- stale contextual assumptions;
- cache miss;
- worktree mismatch;
- reuse efficiency versus context leakage;
- semantic isolation versus physical resource sharing.

End by reconnecting K8 to D7/D8 and the parent A7/A8 loop.

- [ ] **Step 8: Verify and commit Fork / Prompt Cache**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md -o /tmp/claude-code-fork-rendered.md
rg -n 'K[1-8]|fork|CacheSafe|prefix|cache|recursion|worktree|fresh|隔离|面试' ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
git diff --check
~~~

Expected: the article distinguishes logical context reuse, fresh runtime state, and filesystem/worktree isolation.

Run:

~~~bash
git add ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
git commit -m "docs(claude-code): explain fork and prompt cache"
~~~

---

### Task 6: Write the Subagent Delegation overview and integrate the fourth part

**Files:**

- Create: ai/claude-code-source/04-subagent-delegation/README.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/00-one-agent-turn.md
- Modify: ai/claude-code-source/03-session-continuity/README.md
- Modify: ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
- Modify: detail chapter navigation created in Tasks 2–5.

- [ ] **Step 1: Write the self-contained D1–D8 overview**

The overview must:

- locate AgentTool inside A5–A7 rather than beside the main architecture;
- draw one complete D1–D8 nested-loop flow;
- walk the failing-test investigation from parent delegation through child Tool work and parent continuation;
- show parent, child, and task-registry state separately;
- contrast foreground and background timing without changing the semantic result contract;
- summarize communication and fork as attached variants;
- state isolation, explicit task lifecycle, queued communication, normal Tool Observation return, and fresh-runtime invariants;
- route readers to the four detail chapters.

A reader who stops after this README must understand why a child Agent is a nested loop exposed through a Tool boundary.

- [ ] **Step 2: Add fluent chapter transitions**

Use this order:

~~~text
04-subagent-delegation/README.md
  → 01-child-loop-and-context-isolation.md
  → 02-foreground-background-lifecycle.md
  → 03-communication-and-result-return.md
  → 04-fork-and-prompt-cache.md
  → 99-interview-playbook.md when Task 9 creates it
~~~

Until Task 9 exists, end with a plain-text return to the A1–A8 map rather than a broken link.

- [ ] **Step 3: Update upstream navigation without duplicating detail**

In root README:

- turn Subagent Delegation from roadmap text into a link;
- add overview and full-learning routes.

In 00:

- add AgentTool as an A5–A7 specialization and link to Part 04;
- keep the canonical turn map authoritative.

In Session Continuity:

- replace the plain-text handoff with a link to Subagent Delegation;
- keep child lifecycle internals out of recovery chapters.

- [ ] **Step 4: Run the fourth-part review gate**

Run:

~~~bash
for file in ai/claude-code-source/04-subagent-delegation/*.md; do npx -y @mermaid-js/mermaid-cli@11.15.0 -i "$file" -o "/tmp/$(basename "$file" .md)-rendered.md" || exit 1; done
python3 -c 'from pathlib import Path; import re, sys; files=list(Path("ai/claude-code-source").rglob("*.md")); bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn ai/claude-code-source/02-controlled-effects ai/claude-code-source/03-session-continuity ai/claude-code-source/04-subagent-delegation
git diff --check
~~~

Expected: all diagrams render, local links pass, placeholder scan exits 1, and D1–D8 rejoins the parent Tool contract cleanly.

- [ ] **Step 5: Commit fourth-part integration**

Run:

~~~bash
git add ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/03-session-continuity ai/claude-code-source/04-subagent-delegation
git diff --cached --check
git commit -m "docs(claude-code): integrate subagent delegation path"
git status --short
~~~

Expected: integration commit succeeds and worktree is clean.

---

### Task 7: Write the bounded Runtime Entry Adapters appendix

**Files:**

- Create: ai/claude-code-source/appendices/runtime-entry-adapters.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/00-one-agent-turn.md

**Primary source anchors:**

- src/main.tsx / CLI mode selection and getInputPrompt call sites
- src/screens/REPL.tsx / onQueryImpl
- src/utils/handlePromptSubmit.ts / prompt submission
- src/QueryEngine.ts / QueryEngine.submitMessage
- source-confirmed stdin/print/SDK adapters found through trace_path

- [ ] **Step 1: Define the appendix’s single question**

Answer only:

~~~text
CLI、REPL、SDK 和 stdin 等入口，如何把不同形态的输入归一化成主线 A1 的一次 turn 请求？
~~~

Explicitly state that the appendix does not own Query Loop, Tool, Permission, Session, or child Agent logic.

- [ ] **Step 2: Draw the adapter funnel**

Use a Mermaid flowchart:

~~~text
CLI args / interactive prompt / stdin / SDK call
  → entry-specific parse and defaults
  → normalized prompt + options + session selector + output mode
  → shared turn/query submission contract
  → A1–A8 main spine
~~~

- [ ] **Step 3: Compare only behavior-changing entry differences**

Create a table:

~~~text
entry | input source | system-prompt semantics | session selection | can ask permission? | streaming/output mode | shared downstream boundary
~~~

Include a difference only when it changes context composition, Permission interaction, session lifecycle, output streaming, or error behavior.

- [ ] **Step 4: Walk one canonical REPL submission and attach variants**

Explain REPL first, then attach print/stdin and SDK/headless variants to the corresponding adapter node. End exactly at the shared submission/query boundary; link to Model Turn for what follows.

- [ ] **Step 5: Add minimal source lenses and interview relevance**

Use at most three short excerpts:

- top-level mode selection;
- interactive submit normalization;
- programmatic QueryEngine submission.

End with a concise answer for: why several product surfaces do not imply several agent runtimes.

- [ ] **Step 6: Verify and commit Runtime Entry appendix**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/appendices/runtime-entry-adapters.md -o /tmp/claude-code-runtime-entry-rendered.md
rg -n 'CLI|REPL|SDK|stdin|adapter|归一化|A1|QueryEngine|面试' ai/claude-code-source/appendices/runtime-entry-adapters.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/appendices/runtime-entry-adapters.md
git diff --check
~~~

Expected: the appendix stays an adapter comparison and never becomes a second runtime walkthrough.

Run:

~~~bash
git add ai/claude-code-source/appendices/runtime-entry-adapters.md ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md
git commit -m "docs(claude-code): add runtime entry appendix"
~~~

---

### Task 8: Build the claim-oriented Source Evidence Index

**Files:**

- Create: ai/claude-code-source/appendices/source-evidence-index.md
- Modify: every part README and detail chapter to link its evidence section to the index.

- [ ] **Step 1: Define evidence metadata and labels**

At the top, record:

~~~text
primary repository: /Users/buoy/Development/gitrepo/Claude-Code-true
branch at study time: note
source commit: 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf
indexing project: Users-buoy-Development-gitrepo-Claude-Code-true
external repositories/packages: separately listed with exact versions/commits
~~~

Define labels:

- Source-confirmed: directly proven by named source symbols at the pinned commit.
- Architectural interpretation: synthesis across multiple source-confirmed facts.
- General principle: explanatory background, not a claim about this implementation.
- External dependency: behavior proven outside the primary repository and separately pinned.

- [ ] **Step 2: Organize by reader claim, not file inventory**

Create sections matching canonical and local nodes:

~~~text
A1–A8
M1–M7 / Q1–Q8
E1–E8 / P / B / X / F nodes
S1–S7 / T / C / R nodes
D1–D8 / G / K nodes
runtime-entry adapter boundary
~~~

Each row must be:

~~~text
claim ID | concise claim | label | repository-relative path + symbol | what the evidence proves | applicability/boundary | article link
~~~

Do not copy historical line-by-line call traces.

- [ ] **Step 3: Populate from article evidence blocks**

For every Source-confirmed or Architectural interpretation statement central to an article:

1. confirm the source symbol through codebase-memory-mcp;
2. add one index row;
3. link the article’s claim/evidence marker to that row or section;
4. mark branch, feature gate, entry mode, or external dependency applicability;
5. omit line numbers except as optional review convenience.

Expected: a reviewer can validate a claim without forcing an ordinary reader through source order.

- [ ] **Step 4: Audit external and ambiguous claims**

Check especially:

- sandbox-runtime behavior and version;
- prompt-cache semantics;
- filesystem/worktree isolation;
- Permission precedence;
- transcript persistence timing;
- background task durability;
- message delivery guarantees.

Downgrade unsupported wording, label interpretation, or remove the claim. Never leave a claim as an unlabeled assumption.

- [ ] **Step 5: Verify evidence coverage**

Run:

~~~bash
rg -n 'Source-confirmed|Architectural interpretation|General principle|External dependency' ai/claude-code-source --glob '*.md'
rg -n '712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf|source commit|源码版本' ai/claude-code-source/appendices/source-evidence-index.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source --glob '*.md' --glob '!_archive/**'
git diff --check
~~~

Expected:

- every article uses the shared evidence vocabulary;
- the pinned source commit is explicit;
- line-number matches are absent or deliberately labelled auxiliary references;
- evidence rows are claim-oriented rather than file-oriented.

- [ ] **Step 6: Commit Evidence Index integration**

Run:

~~~bash
git add ai/claude-code-source/appendices/source-evidence-index.md ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn ai/claude-code-source/02-controlled-effects ai/claude-code-source/03-session-continuity ai/claude-code-source/04-subagent-delegation
git diff --cached --check
git commit -m "docs(claude-code): add source evidence index"
~~~

---

### Task 9: Write the Interview Playbook from the completed architecture

**Files:**

- Create: ai/claude-code-source/99-interview-playbook.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md

- [ ] **Step 1: Define four answer depths without duplicating the textbook**

For each primary part, provide:

- 30-second thesis;
- 3-minute causal walkthrough;
- whiteboard diagram using the same canonical/local node IDs;
- one deep follow-up path;
- common misconception and correction;
- implementation evidence link.

Link to detail chapters instead of copying their source excerpts.

- [ ] **Step 2: Write one end-to-end interview answer**

Answer:

~~~text
请设计一个像 Claude Code 一样、能安全使用工具并可恢复会话的 coding agent runtime。
~~~

Use A1–A8 as the backbone and cover:

1. Model View construction;
2. streamed Query Loop;
3. Tool Intent/Observation protocol;
4. ordering, Permission, Sandbox, and file safety;
5. durable transcript versus model projection;
6. Compaction and interruption/recovery;
7. child Agent delegation.

Keep the first pass architectural. Attach details only where an interviewer would naturally probe.

- [ ] **Step 3: Add contrast and trade-off questions**

Include concise answer structures for:

- Why not expose arbitrary functions directly to the model?
- Permission and Sandbox solve different problems—how?
- Why stream Tool calls before the entire model response completes?
- Why persist a full transcript if the model sees a compacted projection?
- What can and cannot Resume reconstruct?
- Why implement a child Agent as a nested loop behind a Tool boundary?
- What does foreground/background change?
- What does fork reuse, and what must remain fresh?

- [ ] **Step 4: Add failure-injection questions**

For each, require state-before, trigger, invariant, terminal state, and recovery:

- model emits malformed Tool input;
- two Tool calls finish out of order;
- user denies Permission;
- sandbox launch fails;
- file changes after Read but before Edit;
- context remains too large after Compaction;
- user interrupts during an irreversible Tool effect;
- child Agent finishes as it is backgrounded;
- Resume finds an unmatched Tool Intent.

- [ ] **Step 5: Add a final self-test rubric**

The reader passes only if they can:

- redraw A1–A8 from memory;
- expand one local map without source order;
- identify the owner chapter for a question;
- state the key invariants;
- distinguish source fact from architectural interpretation;
- explain one trade-off and one failure path per primary part;
- cite a path + symbol for a decisive implementation claim.

- [ ] **Step 6: Verify and commit Interview Playbook**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/99-interview-playbook.md -o /tmp/claude-code-interview-rendered.md
rg -n '30 秒|3 分钟|白板|A[1-8]|Tool Intent|Permission|Sandbox|Compaction|Resume|Subagent|权衡|失败' ai/claude-code-source/99-interview-playbook.md
git diff --check
~~~

Expected: the playbook reuses the learning architecture and contains complete answers, not a second set of disconnected flashcards.

Run:

~~~bash
git add ai/claude-code-source/99-interview-playbook.md ai/claude-code-source/README.md ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
git commit -m "docs(claude-code): add interview playbook"
~~~

---

### Task 10: Run the full redesign integration and readability review

**Files:**

- Modify as required: all active Markdown under ai/claude-code-source/, excluding _archive/
- Inspect only: ai/claude-code-source/_archive/

- [ ] **Step 1: Verify the target active tree exactly**

Run:

~~~bash
find ai/claude-code-source -path '*/_archive/*' -prune -o -type f -print | sort
~~~

Expected active learning files:

~~~text
ai/claude-code-source/README.md
ai/claude-code-source/00-one-agent-turn.md
ai/claude-code-source/01-model-turn/README.md
ai/claude-code-source/01-model-turn/01-context-assembly.md
ai/claude-code-source/01-model-turn/02-query-loop-and-streaming.md
ai/claude-code-source/02-controlled-effects/README.md
ai/claude-code-source/02-controlled-effects/01-tool-contract-and-orchestration.md
ai/claude-code-source/02-controlled-effects/02-permission-decision.md
ai/claude-code-source/02-controlled-effects/03-bash-security-analysis.md
ai/claude-code-source/02-controlled-effects/04-sandbox-runtime.md
ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md
ai/claude-code-source/03-session-continuity/README.md
ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md
ai/claude-code-source/03-session-continuity/02-compaction.md
ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
ai/claude-code-source/04-subagent-delegation/README.md
ai/claude-code-source/04-subagent-delegation/01-child-loop-and-context-isolation.md
ai/claude-code-source/04-subagent-delegation/02-foreground-background-lifecycle.md
ai/claude-code-source/04-subagent-delegation/03-communication-and-result-return.md
ai/claude-code-source/04-subagent-delegation/04-fork-and-prompt-cache.md
ai/claude-code-source/appendices/runtime-entry-adapters.md
ai/claude-code-source/appendices/source-evidence-index.md
ai/claude-code-source/99-interview-playbook.md
~~~

Expected: old numbered runtime-pipeline notes exist only under _archive/2026-06-runtime-pipeline/.

- [ ] **Step 2: Verify the three reading modes**

Follow links manually and record pass/fail for:

1. Ten-minute overview: README → 00 → four part READMEs.
2. Full learning path: README → every chapter in intended order → playbook.
3. Interview lookup: README/topic table → requested owner chapter → evidence index.

Every page must answer where the reader is, what question this page owns, what prior contract it consumes, and what next question follows.

- [ ] **Step 3: Run the causal-flow reading review**

Read active prose in this order without opening source:

~~~text
README → 00 → Model Turn → Controlled Effects → Session Continuity → Subagent Delegation → Interview Playbook
~~~

For every article, check:

- opening question and one-sentence thesis;
- local diagram before details;
- canonical failing-test walkthrough;
- state changes after each causal step;
- variants attached after the canonical path;
- decisive code lenses only;
- failure/recovery and trade-offs;
- complete interview answer;
- explicit handoff to the next chapter.

Rewrite any passage that reads as a call trace, unordered helper inventory, or detached code excerpt.

- [ ] **Step 4: Audit concept ownership and repetition**

Use the design’s ownership matrix and confirm one owner for each:

~~~text
Model View composition
Query Loop and streaming
Tool contract and orchestration
Permission
Bash security analysis
Sandbox
file edit safety
transcript/model projection
Compaction
interrupt/queue/Continue/Resume
child context
foreground/background lifecycle
communication/result return
fork/cache
runtime entry adapters
source evidence
~~~

For repeated explanations outside the owner article, retain only a one-paragraph contract summary plus link.

- [ ] **Step 5: Render every active Markdown document**

Run:

~~~bash
for file in $(find ai/claude-code-source -path '*/_archive/*' -prune -o -name '*.md' -print); do npx -y @mermaid-js/mermaid-cli@11.15.0 -i "$file" -o "/tmp/claude-code-$(echo "$file" | tr '/' '-')" || exit 1; done
~~~

Expected: every active Markdown file parses and every Mermaid diagram renders.

- [ ] **Step 6: Verify links, placeholders, source snapshot, and line-number discipline**

Run:

~~~bash
python3 -c 'from pathlib import Path; import re, sys; files=[f for f in Path("ai/claude-code-source").rglob("*.md") if "_archive" not in f.parts]; bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source --glob '*.md' --glob '!_archive/**'
rg -n '712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf' ai/claude-code-source/README.md ai/claude-code-source/appendices/source-evidence-index.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source --glob '*.md' --glob '!_archive/**'
git -C /Users/buoy/Development/gitrepo/Claude-Code-true rev-parse HEAD
git diff --check
~~~

Expected:

- local-link script exits 0;
- placeholder scan exits 1;
- source commit appears in both root and evidence index;
- line-number inventory is empty or contains only explicitly auxiliary references;
- source HEAD equals 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf;
- diff check passes.

- [ ] **Step 7: Run a claim spot-check against the source graph**

Choose at least two decisive claims from each primary part, including these high-risk claims:

- Tool serial/concurrent ordering;
- Permission precedence;
- Sandbox selection;
- FileEdit stale/read-before-write behavior;
- Compaction’s effect on durable transcript versus model projection;
- Resume reconstruction;
- foreground/background terminal result;
- fork/cache-safe context.

For each, use search_graph, trace_path, and get_code_snippet to reconfirm path + symbol + applicability. Record corrections directly in the article and evidence index.

- [ ] **Step 8: Run an interview-reader acceptance review**

Without source code open, answer these from the notes:

1. Draw one complete agent turn and identify all state boundaries.
2. Explain why Tool Intent does not directly cause an effect.
3. Explain Permission versus Sandbox versus file-edit safety.
4. Explain transcript versus model context and what Compaction changes.
5. Explain what interrupt can stop and cannot undo.
6. Explain how Resume constructs a new turn.
7. Explain a child Agent as a nested loop behind AgentTool.
8. Explain foreground/background and fork as variants, not alternate architectures.

Expected: each answer follows the same node IDs and causal vocabulary as the learning chapters.

- [ ] **Step 9: Commit final integration corrections**

Run:

~~~bash
git add ai/claude-code-source
git diff --cached --check
git commit -m "docs(claude-code): finish source notes redesign"
~~~

If no files changed during review, skip the empty commit and record that the prior commits already satisfy the gate.

- [ ] **Step 10: Verify branch handoff state**

Run:

~~~bash
git status --short
git log --oneline --decorate -15
git diff main...HEAD --stat
~~~

Expected:

- worktree is clean;
- commits are focused and reviewable;
- diff contains the archive move plus the new learning architecture;
- no source repository files were changed;
- branch remains codex/claude-code-notes-redesign for user review.
