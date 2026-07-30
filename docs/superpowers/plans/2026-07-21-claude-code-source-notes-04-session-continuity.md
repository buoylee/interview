# Claude Code Session Continuity Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Explain how Claude Code preserves a coherent session across context pressure, interruption, queued input, Continue, and Resume without confusing the model’s current view with the durable transcript.

**Architecture:** Build one Session Continuity overview around S1–S7, then deepen it through three causal chapters: Transcript and Model Context, Compaction, and Interrupt / Queue / Continue / Resume. Treat the durable transcript as source history, the model-visible request as a projection, and Compaction/recovery as explicit transformations that construct a later turn rather than rewinding an execution stack.

**Tech Stack:** Markdown, GitHub-compatible Mermaid, Markdown state/timeline tables, TypeScript source reading through codebase-memory-mcp, read-only Claude Code source at the pinned commit, Git, rg, Python 3 link verification, and @mermaid-js/mermaid-cli 11.15.0.

## Global Constraints

- Execute only after the Controlled Effects plan has passed its review gate.
- Work only in the isolated redesign worktree.
- Treat /Users/buoy/Development/gitrepo/Claude-Code-true as read-only.
- Use source snapshot 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf; stop and record drift if HEAD differs.
- Use codebase-memory-mcp search_graph, trace_path, and get_code_snippet before native code search.
- Build overall cognition before implementation detail.
- Include a detail only when it changes a flow, state, ordering, concurrency, safety result, recovery behavior, module contract, invariant, or design trade-off.
- Explain the canonical live-session path before process-restart Resume, malformed transcript repair, background-agent attachments, and entry-specific variants.
- Keep Context Assembly’s general Model View construction in Model Turn; this part owns how durable/session state is projected or reconstructed over time.
- Keep Tool execution, Permission, Sandbox, and file mutation internals in Controlled Effects.
- Keep child task creation and Agent result lifecycle in Subagent Delegation; this part may explain only how their pending messages appear in parent session state.
- Keep three terms explicit: latest model-visible view, runtime-only active state, and durable transcript.
- State that Compaction transforms the model-visible continuation context; it does not erase the original durable transcript unless source explicitly proves a storage mutation.
- State that Continue/Resume create a new execution turn from persisted state; they do not resume a suspended JavaScript stack.
- Explain mechanisms before pseudocode, and pseudocode before real source excerpts.
- Record evidence as commit + repository-relative path + symbol; line numbers are auxiliary.
- Distinguish Source-confirmed, Architectural interpretation, and General principle claims.
- Use editable Markdown-compatible diagrams only.
- Use a trusted local Mermaid CLI only when already installed or cached; otherwise apply the browser-isolated Mermaid 11.x verification policy recorded in the plan-suite index, once per diagram block.
- Make one focused commit per independently reviewable article or overview integration.

---

## File Structure

**Create:**

- ai/claude-code-source/03-session-continuity/README.md
- ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md
- ai/claude-code-source/03-session-continuity/02-compaction.md
- ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md

**Modify:**

- ai/claude-code-source/README.md
- ai/claude-code-source/00-one-agent-turn.md
- ai/claude-code-source/02-controlled-effects/README.md
- ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md

**Historical material to inspect but not edit:**

- ai/claude-code-source/_archive/2026-06-runtime-pipeline/08-session-history-compaction-resume.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/09-interrupt-abort-continue.md
- ai/claude-code-source/_archive/2026-06-runtime-pipeline/13-source-code-map.md

## Interfaces

- Consumes completed/partial messages and Tool Observations from the A7/A8 boundary.
- Produces local nodes S1 through S7:
  - S1 Current Model-visible Messages
  - S2 Durable Transcript Append
  - S3 Context-pressure or Lifecycle Trigger
  - S4 Compact, Abort, Queue, Continue, or Resume Transformation
  - S5 Reconstructed Runtime State
  - S6 Rebuilt Model View
  - S7 Next Agent Turn
- Feeds reconstructed messages back into Model Turn rather than bypassing it.
- Exposes parent-session attachment boundaries used by Subagent communication without owning the child task lifecycle.

---

### Task 1: Build the Session Continuity evidence map

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

- [ ] **Step 2: Trace transcript storage and model-view projection**

Use search_graph for:

~~~text
loadInitialMessages
loadConversationForResume
sessionHistory
normalizeMessagesForAPI
ensureToolResultPairing
buildPostCompactMessages
prependUserContext
appendSystemContext
getQueuedCommandAttachments
getAgentPendingMessageAttachments
~~~

Use trace_path inbound and outbound for loadInitialMessages, loadConversationForResume, and buildPostCompactMessages. Identify the actual transcript read/write symbols returned by the graph rather than assuming filenames alone define persistence.

Record:

~~~text
state artifact | producer | storage lifetime | consumer | transformation | visible to model?
~~~

- [ ] **Step 3: Trace Compaction decisions and transformations**

Use search_graph for:

~~~text
AutoCompactTrackingState
getAutoCompactThreshold
shouldAutoCompact
autoCompactIfNeeded
trySessionMemoryCompaction
CompactionResult
buildPostCompactMessages
compact
~~~

Use trace_path outbound from autoCompactIfNeeded, trySessionMemoryCompaction, and buildPostCompactMessages. Then locate their call sites in query through graph queries or inbound traces.

Capture:

- trigger inputs;
- threshold/budget logic;
- compaction request inputs;
- summary or boundary metadata;
- post-compact message reconstruction;
- failure/fallback behavior;
- what happens to the durable original messages.

- [ ] **Step 4: Trace interruption, queueing, Continue, and Resume**

Use search_graph for:

~~~text
useCancelRequest
abortController
useSessionBackgrounding
messageQueueManager
QueuedCommand
queuedCommandsSnapshot
loadInitialMessages
loadConversationForResume
conversationRecovery
continue
resume
~~~

Resolve broad names by qualified result. Use trace_path to establish:

- who owns and signals the active AbortController;
- what state is aborted immediately;
- where queued input is stored and snapshotted;
- when queued input becomes a model-visible attachment/message;
- how Continue chooses a prior session;
- how Resume loads a specific session;
- how incomplete Tool Intent/Observation pairs are normalized or recovered.

- [ ] **Step 5: Reject state-model ambiguity**

Remove or rewrite any evidence note that uses one word such as history, context, memory, or session for multiple artifacts. Every claim must identify one of:

~~~text
durable transcript | model-visible projection | runtime-only active state | queued input | compacted continuation state
~~~

Expected: S1–S7 can be traced without implying that one array is the entire session architecture.

---

### Task 2: Write Transcript and Model Context as separate state planes

**Files:**

- Create: ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md

**Primary source anchors:**

- src/cli/print.ts / loadInitialMessages
- src/utils/conversationRecovery.ts / loadConversationForResume
- src/assistant/sessionHistory.ts / durable session-history helpers
- src/services/api/claude.ts / normalizeMessagesForAPI, ensureToolResultPairing
- src/query.ts / model-view transformation and transcript/update call sites
- src/utils/attachments.ts or source-confirmed equivalents / queued and pending-message attachment builders
- src/services/compact/compact.ts / buildPostCompactMessages

- [ ] **Step 1: Open with the three-state-plane model**

Opening question:

~~~text
Claude Code 说“会话历史”时，究竟是在说落盘记录、当前模型窗口，还是正在运行的一次 turn？
~~~

Use local nodes:

~~~text
T1 Durable Transcript
T2 Selection / Recovery
T3 Projection and Normalization
T4 Current Model-visible Messages
T5 Runtime-only Active State
T6 Newly Produced Events
T7 Append / Reproject
~~~

Draw a three-lane Mermaid flowchart or sequence diagram. T1, T4, and T5 must be visually distinct.

- [ ] **Step 2: Define artifacts by ownership and lifetime**

Create a table:

~~~text
artifact | contains | omits | owner | lifetime | reconstructed from | model-visible?
~~~

Include:

- durable transcript entries;
- active model request/messages;
- runtime ToolUseContext, AbortController, Permission, and executor state;
- queued user input;
- compaction metadata/summary;
- pending child-agent messages only as parent-facing attachments.

- [ ] **Step 3: Walk one ordinary turn across all three planes**

Use the failing-test scenario and show snapshots at:

1. before the user request;
2. after user input is accepted;
3. while model/tool execution is active;
4. after assistant Tool Intent and Tool Observation;
5. after final answer;
6. before the next model call.

For every snapshot, distinguish what is durable, what the model sees, and what exists only while runtime code is active.

- [ ] **Step 4: Explain transcript-to-model projection**

Explain in causal order:

1. select/load relevant durable entries;
2. recover/normalize protocol structure;
3. apply compaction projection when present;
4. add current entry-specific context and attachments;
5. construct the model-visible request;
6. keep runtime-only controls outside the request.

Link back to Context Assembly for general request composition; this chapter owns only the time/persistence boundary.

- [ ] **Step 5: Explain append and incomplete-state semantics**

State when user, assistant, Tool Intent, Tool Observation, cancellation, or synthetic recovery information becomes durable according to source. If persistence timing differs by entry point, mark each applicability rather than inventing one universal transaction.

Explain why durable history may contain more information than the next model window and why the next window may contain derived context not stored as an original user message.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
reconstructModelView(sessionId, newInput) -> { durableBase, projectedMessages, runtimeState }
~~~

Then include short excerpts for:

- session load/recovery;
- protocol normalization/pairing;
- one durable-history read or append boundary;
- projection into model-visible messages.

If persistence is distributed across helpers, label the combined explanation Architectural interpretation.

- [ ] **Step 7: Add misconceptions, trade-offs, interview answer, and Compaction handoff**

Correct:

- transcript equals prompt;
- all runtime state can be restored from transcript;
- a model-visible summary replaces original storage;
- aborting execution automatically removes prior durable entries;
- Resume can recover arbitrary in-memory objects.

End by asking how the projection changes when the model context budget becomes the limiting resource.

- [ ] **Step 8: Verify and commit Transcript / Model Context**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md -o /tmp/claude-code-transcript-rendered.md
rg -n 'T[1-7]|durable|transcript|model-visible|runtime-only|投影|恢复|配对|面试' ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md
git diff --check
~~~

Expected: all three state planes remain distinct in prose, diagram, and examples.

Run:

~~~bash
git add ai/claude-code-source/03-session-continuity/01-transcript-and-model-context.md
git commit -m "docs(claude-code): explain transcript and model context"
~~~

---

### Task 3: Write Compaction as a continuation transformation

**Files:**

- Create: ai/claude-code-source/03-session-continuity/02-compaction.md

**Primary source anchors:**

- src/services/compact/autoCompact.ts / AutoCompactTrackingState, getAutoCompactThreshold, shouldAutoCompact, autoCompactIfNeeded
- src/services/compact/sessionMemoryCompact.ts / trySessionMemoryCompaction
- src/services/compact/compact.ts / CompactionResult, buildPostCompactMessages
- src/query.ts / automatic-compaction call sites and retry/continuation branches

- [ ] **Step 1: Open with the budget problem and C1–C8 map**

Use local nodes:

~~~text
C1 Current Model Projection
C2 Estimate Context Pressure
C3 Choose No-op, Session-memory Compact, or Full Compact
C4 Select Compactable History
C5 Ask for / Build Compressed Representation
C6 Construct Post-compact Messages
C7 Preserve Continuity Metadata
C8 Retry or Continue Query Loop
~~~

Draw a state diagram with success, no-op, failure, and prompt-too-long retry paths.

- [ ] **Step 2: Explain triggers before summary format**

Cover source-confirmed trigger inputs:

- model context window and reserved budget;
- current token estimate/usage;
- automatic threshold;
- prior compaction tracking state;
- explicit/manual versus automatic trigger if both exist;
- prompt-too-long recovery path.

State what is known before the request, learned only after a failed request, or carried from prior turns.

- [ ] **Step 3: Walk the canonical automatic-compaction path**

Show:

1. current projection approaches threshold;
2. runtime decides compaction is needed;
3. compactable content and preserved tail are selected;
4. a compressed representation and metadata are produced;
5. post-compact model messages are rebuilt;
6. query loop continues with the rebuilt projection;
7. original durable transcript remains available unless source proves otherwise.

Use before/after message snapshots, not just token counts.

- [ ] **Step 4: Separate session-memory compaction from full compaction**

Establish from source:

~~~text
variant | trigger | transformed content | output shape | fallback | applicability
~~~

Explain why the variants exist and how control chooses among them. Do not infer names from filenames alone.

- [ ] **Step 5: Explain continuity invariants and information loss**

Cover:

- Tool Intent/Observation pairing after reconstruction;
- preserving the current task and recent turn boundary;
- retaining enough state to continue rather than merely summarize;
- marking files or memory already read when source carries this data;
- summary drift and irreversible loss inside the model-visible projection;
- durable transcript as a recovery/audit source, not automatically active context.

- [ ] **Step 6: Add pseudocode and decisive source lenses**

Include pseudocode for:

~~~text
maybeCompact(modelProjection, usage, trackingState) -> NoChange | CompactedProjection | RetryableFailure
~~~

Then include short excerpts for:

- threshold calculation;
- shouldCompact decision;
- variant selection;
- buildPostCompactMessages;
- query-loop integration/retry.

- [ ] **Step 7: Add failure paths, trade-offs, interview answer, and interruption handoff**

Cover:

- compaction request failure;
- output too large or invalid;
- prompt still too long;
- repeated-compaction guard/tracking;
- abort during compaction;
- compression quality versus token headroom;
- stable continuation versus perfect replay.

End by asking what happens when continuity is challenged by a user interrupt or a later process rather than context pressure.

- [ ] **Step 8: Verify and commit Compaction**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/03-session-continuity/02-compaction.md -o /tmp/claude-code-compaction-rendered.md
rg -n 'C[1-8]|threshold|token|projection|transcript|summary|retry|pair|信息损失|面试' ai/claude-code-source/03-session-continuity/02-compaction.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/03-session-continuity/02-compaction.md
git diff --check
~~~

Expected: Compaction is described as a projection transformation, not transcript deletion or stack suspension.

Run:

~~~bash
git add ai/claude-code-source/03-session-continuity/02-compaction.md
git commit -m "docs(claude-code): explain compaction continuity"
~~~

---

### Task 4: Write Interrupt, Queue, Continue, and Resume as one lifecycle

**Files:**

- Create: ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md

**Primary source anchors:**

- src/hooks/useCancelRequest.ts or source-confirmed equivalent / active cancellation flow
- src/utils/abortController.ts / AbortController ownership and propagation
- src/hooks/useSessionBackgrounding.ts / active-session backgrounding boundary
- src/utils/messageQueueManager.ts / queued message state and draining
- src/types/textInputTypes.ts / QueuedCommand
- src/query.ts / queuedCommandsSnapshot and query-loop injection points
- src/utils/attachments.ts / queued command and pending-agent-message attachments
- src/cli/print.ts / loadInitialMessages
- src/utils/conversationRecovery.ts / loadConversationForResume
- src/assistant/sessionHistory.ts / session lookup/history

- [ ] **Step 1: Open with a single event timeline and R1–R9 states**

Use local states:

~~~text
R1 Active Turn
R2 New Input Arrives or User Cancels
R3 Queue or Signal Abort
R4 Active Model/Tool Work Settles
R5 Persist Explicit Terminal State
R6 Select Existing Session for Continue/Resume
R7 Load and Repair Durable Conversation
R8 Build New Runtime State and Model View
R9 Start a New Turn
~~~

Draw one timeline showing both immediate cancel and queued steering. Make it visually clear that R9 is a new invocation.

- [ ] **Step 2: Separate interrupt, queued input, backgrounding, Continue, and Resume**

Build a comparison table:

~~~text
operation | trigger | affects active turn? | durable state used | process may restart? | next model call | identity/session selection
~~~

Define exact source-confirmed semantics for:

- cancel/interrupt;
- steering or queued command during active work;
- session backgrounding;
- Continue latest/selected prior conversation;
- Resume explicit session.

Do not equate UI labels with identical backend paths unless trace evidence supports it.

- [ ] **Step 3: Walk cancellation propagation**

Trace:

1. cancel input reaches the current owner;
2. AbortController is signalled;
3. model stream and/or Tool execution observes abort;
4. pending work settles into cancellation/error results;
5. protocol pairing and durable state are repaired or finalized;
6. UI/SDK receives a terminal outcome.

State what cannot be rolled back, especially already completed external effects.

- [ ] **Step 4: Walk queued steering into the next turn**

Show:

1. input arrives while work is active;
2. queue manager stores a typed QueuedCommand or equivalent;
3. current query snapshots or drains it at a defined boundary;
4. runtime converts it into a model-visible message/attachment;
5. the next model decision incorporates it;
6. queue state is acknowledged/cleared according to source.

Distinguish queueing from cancel-and-restart if both paths exist.

- [ ] **Step 5: Walk Continue and Resume reconstruction**

For each command:

1. determine the session identity/selection rule;
2. load durable entries;
3. detect and repair incomplete protocol state;
4. derive current model-visible projection;
5. initialize fresh runtime-only controls;
6. submit a new turn.

Explain what is restored exactly, reconstructed approximately, or not restorable.

- [ ] **Step 6: Attach process and entry variants**

Only after the canonical path, cover:

- same-process continuation versus process restart;
- interactive UI versus print/headless entry behavior;
- active backgrounded sessions;
- pending child-agent notifications entering the parent;
- missing/corrupt session data;
- interrupted Tool call with a durable intent but no observation.

Child lifecycle details remain links to Part 04.

- [ ] **Step 7: Add pseudocode and decisive source lenses**

Include two small pseudocode blocks:

~~~text
interruptActiveTurn(reason) -> settled terminal state
resumeSession(sessionSelector, newInput) -> new turn
~~~

Then include short excerpts for:

- AbortController propagation;
- queue snapshot/drain;
- session load/selection;
- recovery/pairing normalization;
- fresh Query submission.

- [ ] **Step 8: Add failure cases, trade-offs, interview answer, and Subagent handoff**

Cover:

- cancellation race with a completed effect;
- duplicated or lost queued input prevention;
- incomplete transcript pairs;
- stale/missing session;
- replay safety versus continuing from observations;
- responsive steering versus deterministic turn boundaries;
- durable recovery versus non-serializable runtime state.

End by asking how the same parent loop delegates work to an isolated child loop and later incorporates its result.

- [ ] **Step 9: Verify and commit Interrupt / Recovery**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md -o /tmp/claude-code-recovery-rendered.md
rg -n 'R[1-9]|Abort|queue|QueuedCommand|Continue|Resume|新.*turn|repair|副作用|面试' ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
git diff --check
~~~

Expected: the article distinguishes all five lifecycle operations and never describes Resume as resuming a call stack.

Run:

~~~bash
git add ai/claude-code-source/03-session-continuity/03-interrupt-queue-continue-resume.md
git commit -m "docs(claude-code): explain interrupt and session recovery"
~~~

---

### Task 5: Write the Session Continuity overview and integrate navigation

**Files:**

- Create: ai/claude-code-source/03-session-continuity/README.md
- Modify: ai/claude-code-source/README.md
- Modify: ai/claude-code-source/00-one-agent-turn.md
- Modify: ai/claude-code-source/02-controlled-effects/README.md
- Modify: ai/claude-code-source/02-controlled-effects/05-file-editing-safety.md
- Modify: detail chapter navigation created in Tasks 2–4.

- [ ] **Step 1: Write the self-contained S1–S7 overview**

The overview must:

- locate A7/A8 and the next-turn return edge in the canonical map;
- draw one complete S1–S7 continuity flow;
- show durable transcript, model-visible projection, and runtime-only state as separate planes;
- walk one failing-test session through ordinary persistence, context pressure/Compaction, user interrupt, queued steering, and later Resume;
- state projection-not-transcript, pairing, explicit-terminal-state, no-stack-resume, and no-effect-rollback invariants;
- route readers to the three detail chapters.

A reader who stops after this README must understand how continuity survives both token pressure and process lifecycle changes.

- [ ] **Step 2: Add fluent chapter transitions**

Use this order:

~~~text
03-session-continuity/README.md
  → 01-transcript-and-model-context.md
  → 02-compaction.md
  → 03-interrupt-queue-continue-resume.md
  → 04-subagent-delegation/README.md when Plan 05 creates it
~~~

Until Plan 05 exists, end with a plain-text forward handoff rather than a broken link.

- [ ] **Step 3: Update upstream navigation without duplicating detail**

In root README:

- turn Session Continuity from roadmap text into a link;
- add overview and full-learning routes.

In 00:

- connect A8 to persisted/projected state and next-turn reconstruction;
- retain a single authoritative A1–A8 map.

In Controlled Effects:

- replace the plain-text handoff with a link to Session Continuity;
- keep persistence/recovery mechanics out of Tool chapters.

- [ ] **Step 4: Run the Session Continuity review gate**

Run:

~~~bash
for file in ai/claude-code-source/03-session-continuity/*.md; do npx -y @mermaid-js/mermaid-cli@11.15.0 -i "$file" -o "/tmp/$(basename "$file" .md)-rendered.md" || exit 1; done
python3 -c 'from pathlib import Path; import re, sys; files=list(Path("ai/claude-code-source").rglob("*.md")); bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/01-model-turn ai/claude-code-source/02-controlled-effects ai/claude-code-source/03-session-continuity
git diff --check
~~~

Expected:

- all Mermaid documents render;
- local links pass;
- placeholder scan exits 1;
- every recovery path identifies its durable input and newly initialized runtime state;
- all three reading modes remain valid for currently existing files.

- [ ] **Step 5: Review concept ownership and temporal continuity**

Confirm:

- Transcript / Model Context owns state-plane distinctions and projection.
- Compaction owns context-pressure transformation.
- Interrupt / Queue / Continue / Resume owns active cancellation and later reconstruction.
- Model Turn still owns general request assembly and Query Loop semantics.
- Controlled Effects still owns running Tool cancellation/result normalization.
- child task storage, communication, and result return remain in Part 04.

Read the state snapshots in chronological order and ensure no state appears without a producer or disappears without an explicit transition.

- [ ] **Step 6: Commit Session Continuity integration**

Run:

~~~bash
git add ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md ai/claude-code-source/02-controlled-effects ai/claude-code-source/03-session-continuity
git diff --cached --check
git commit -m "docs(claude-code): integrate session continuity path"
git status --short
~~~

Expected: integration commit succeeds and worktree is clean.
