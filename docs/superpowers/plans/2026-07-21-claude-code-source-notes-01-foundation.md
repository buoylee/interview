# Claude Code Source Notes Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Replace the current source-tracing entry point with a stable, interview-oriented overview that gives readers a complete agent-turn mental model before any subsystem detail.

**Architecture:** Preserve the current active notes in a dated archive, then create a new root README and 00-one-agent-turn.md. The new overview owns the canonical flow, shared terminology, state planes, module handoffs, invariants, reading modes, and the failing-test scenario that later plans progressively enlarge.

**Tech Stack:** Markdown, GitHub-compatible Mermaid, Markdown tables, codebase-memory-mcp for source discovery, read-only Claude Code TypeScript source at the pinned commit, Git, rg, Python 3 for read-only local-link verification, and @mermaid-js/mermaid-cli 11.15.0 for render verification.

## Global Constraints

- Work only in the isolated interview-repo worktree and branch created for this redesign.
- Treat /Users/buoy/Development/gitrepo/Claude-Code-true as read-only.
- Use source snapshot 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf; stop and record drift if HEAD differs.
- Use codebase-memory-mcp search_graph, trace_path, and get_code_snippet before native code search.
- Use rg only for literal strings, configuration, Markdown, or evidence the graph cannot surface.
- Build overall cognition before implementation detail.
- Include a detail only when it changes a flow, state, ordering, concurrency, safety result, recovery behavior, module contract, invariant, or design trade-off.
- Explain the canonical path before interactive/headless, streaming/non-streaming, feature-gated, fallback, abort, and recovery variants.
- Put complete interview answers at chapter ends; chapter starts contain only the question and one-sentence thesis.
- Explain mechanisms before pseudocode, and pseudocode before real source excerpts.
- Record source evidence as commit + repository-relative path + symbol; line numbers are auxiliary.
- Distinguish Source-confirmed, Architectural interpretation, and General principle claims.
- Prefer Mermaid, Markdown tables, and text diagrams; do not use raster images for architecture or mechanism explanation.
- Keep Plugin and Bridge out of the main path. Runtime entry remains a thin appendix. MCP remains a Tool adapter inside Controlled Effects.
- Do not delete previous notes; archive them.
- Make one focused commit per independently reviewable deliverable.

---

## File Structure

**Archive existing:**

- Move as ai/claude-code-source/_archive/2026-06-runtime-pipeline/README-old-entry.md: ai/claude-code-source/README.md
- Move: ai/claude-code-source/00-coding-agent-big-picture.md
- Move: ai/claude-code-source/01-runtime-entry.md
- Move: ai/claude-code-source/02-query-loop.md
- Move: ai/claude-code-source/03-prompt-and-context-assembly.md
- Move: ai/claude-code-source/04-model-streaming.md
- Move: ai/claude-code-source/05-tool-system-and-orchestration.md
- Move: ai/claude-code-source/06-permission-and-sandbox.md
- Move: ai/claude-code-source/07-shell-and-file-editing.md
- Move: ai/claude-code-source/08-session-history-compaction-resume.md
- Move: ai/claude-code-source/09-interrupt-abort-continue.md
- Move: ai/claude-code-source/10-subagent-runtime.md
- Move: ai/claude-code-source/11-fork-subagent-and-prompt-cache.md
- Move: ai/claude-code-source/12-mcp-plugin-bridge-appendix.md
- Move: ai/claude-code-source/13-source-code-map.md
- Move: ai/claude-code-source/14-interview-playbook.md
- Move directory: ai/claude-code-source/deep-dives/

**Create:**

- ai/claude-code-source/_archive/2026-06-runtime-pipeline/README.md
- ai/claude-code-source/README.md
- ai/claude-code-source/00-one-agent-turn.md

**Preserve unchanged:**

- ai/claude-code-source/_archive/ entries that predate the 2026-06 runtime-pipeline rewrite.

## Interfaces

- Produces canonical node IDs A1 through A8 for later diagrams.
- Produces the terms Agent Turn, Model View, Runtime State, Machine Effect, Durable Transcript, Child Loop, Tool Intent, and Tool Observation.
- Produces four state planes: model protocol, runtime control, machine effect/security, durable session.
- Produces the canonical scenario: locate and fix a failing test.
- Produces the navigation and chapter-transition wording consumed by Plans 02 through 05.

---

### Task 1: Verify the starting state and archive the current active notes

**Files:**

- Move all current top-level active notes listed in File Structure.
- Preserve the old top-level README as ai/claude-code-source/_archive/2026-06-runtime-pipeline/README-old-entry.md so it does not collide with the new archive guide.
- Move ai/claude-code-source/deep-dives/ into ai/claude-code-source/_archive/2026-06-runtime-pipeline/deep-dives/.
- Create ai/claude-code-source/_archive/2026-06-runtime-pipeline/README.md.

- [ ] **Step 1: Verify branch, worktree, source revision, and current inventory**

Run:

~~~bash
git status --short --branch
git rev-parse --show-toplevel
git -C /Users/buoy/Development/gitrepo/Claude-Code-true rev-parse HEAD
rg --files ai/claude-code-source | sort
~~~

Expected:

- current branch is codex/claude-code-notes-redesign;
- worktree root ends in .worktrees/claude-code-notes-redesign;
- source revision is 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf;
- the active 00–14 notes and deep-dives directory are present;
- git status is clean before archive changes.

- [ ] **Step 2: Create the dated archive directory**

Run:

~~~bash
mkdir -p ai/claude-code-source/_archive/2026-06-runtime-pipeline
~~~

Expected: the target directory exists inside the tracked notes tree.

- [ ] **Step 3: Move the active generation without touching older archive entries**

Use git mv with the exact active files from File Structure. Move the deep-dives directory into the dated archive as a child directory.

Expected inventory:

~~~text
ai/claude-code-source/_archive/2026-06-runtime-pipeline/
  README.md
  README-old-entry.md
  00-coding-agent-big-picture.md
  ...
  14-interview-playbook.md
  deep-dives/
~~~

Do not move ai/claude-code-source/_archive/ itself and do not overwrite its older entries.

- [ ] **Step 4: Write the archive README**

The README must state:

- this is the 2026-06 runtime-pipeline generation;
- it is preserved as historical source-reading material;
- it is not the current recommended learning path;
- its organizing style over-promoted source anchors and repeated chapter templates;
- useful evidence should be revalidated against the pinned source before reuse;
- the current entry point is ../../README.md.

- [ ] **Step 5: Verify archive completeness**

Run:

~~~bash
rg --files ai/claude-code-source/_archive/2026-06-runtime-pipeline | sort
git status --short
git diff --check
~~~

Expected:

- all previous active files appear under the dated archive;
- the old active README appears as README-old-entry.md and the new README.md is the archive guide;
- no previous active 00–14 file remains at the top level;
- older archive entries remain;
- no content appears as deleted without a corresponding rename.

- [ ] **Step 6: Commit the archive move**

Run:

~~~bash
git add ai/claude-code-source
git diff --cached --check
git commit -m "docs(claude-code): archive source-tracing notes"
~~~

Expected: one rename-focused commit with no new learning content.

---

### Task 2: Create the new track README

**Files:**

- Create: ai/claude-code-source/README.md

- [ ] **Step 1: Establish the README contract before writing**

The README must answer, in this order:

1. What this track teaches.
2. What it deliberately excludes.
3. The one-sentence spine.
4. The canonical A1–A8 map.
5. The three reading modes.
6. The four-part learning path.
7. Source snapshot and evidence labels.
8. How to use code excerpts and diagrams.
9. Archive navigation.

It must not start with a file list.

- [ ] **Step 2: Write the one-sentence spine and scope boundary**

Use this exact conceptual promise:

~~~text
一次 agent turn 如何把用户意图转换成安全的机器操作，再把观察结果写回状态，让模型继续决策；当任务跨越时间或需要委派时，同一套机制如何扩展。
~~~

State that the track is interview-oriented mechanism study, not a full Claude Code product encyclopedia and not a build-your-own-agent tutorial.

- [ ] **Step 3: Add the canonical navigation map**

Use stable node IDs:

~~~text
A1 User Task
A2 Model View Assembly
A3 Model Request and Stream
A4 Runtime Decision
A5 Tool Intent
A6 Controlled Machine Effect
A7 Tool Observation and State Update
A8 Continue, Stop, Recover, or Delegate
~~~

The README may use a compact Mermaid flowchart, but 00-one-agent-turn.md owns the authoritative full diagram.

- [ ] **Step 4: Add three explicit reading modes**

The modes are:

- Overview: README → 00 → each part README → 99 Interview Playbook.
- Full learning: every file in numeric order.
- Interview review: 00 → chapter-end interview answers → 99 Interview Playbook.

Only link files that exist in the current phase. List later parts as a plain roadmap until their files are created, so the foundation commit contains no broken links.

- [ ] **Step 5: Add evidence and visual rules**

State:

- source snapshot is 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf;
- evidence uses path + symbol;
- claims are labelled Source-confirmed, Architectural interpretation, or General principle when the distinction matters;
- Mermaid, Markdown tables, and text diagrams are preferred;
- raster images do not explain core mechanisms.

- [ ] **Step 6: Verify README structure**

Run:

~~~bash
rg -n '^#|A[1-8]|总览路径|完整学习路径|面试复习路径|712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf' ai/claude-code-source/README.md
rg -n 'Plugin|Bridge|逐行|完整 agent' ai/claude-code-source/README.md
git diff --check
~~~

Expected: all required concepts appear, and exclusions are stated as boundaries rather than advertised as main topics.

---

### Task 3: Write the canonical one-agent-turn overview

**Files:**

- Create: ai/claude-code-source/00-one-agent-turn.md

- [ ] **Step 1: Write the opening question and thesis**

Opening question:

~~~text
用户输入一句任务后，Claude Code 如何把它变成可控的机器效果，并决定继续还是结束？
~~~

The thesis must say that a coding agent is a stateful feedback loop connecting a model-visible view, runtime-controlled effects, and durable state. Do not begin with an interview answer or source function.

- [ ] **Step 2: Draw the authoritative A1–A8 Mermaid flowchart**

Use a GitHub-compatible Mermaid flowchart. It must:

- contain A1 through A8;
- show the feedback edge from A7 to A2/A3;
- show text completion as an exit from A4;
- show recovery/delegation as extensions from A8;
- keep source filenames and function names out of the diagram.

Follow the diagram with prose explaining every node and arrow.

- [ ] **Step 3: Define the core objects and four state planes**

Add a Markdown table with these rows:

~~~text
Model Request
Messages
Tool Definition
Tool Intent
Tool Observation
Runtime Turn State
Durable Transcript
Child Task State
~~~

Columns:

~~~text
object | visible to model? | owned by | lifetime | why it exists
~~~

Then define:

- model protocol plane;
- runtime control plane;
- machine effect/security plane;
- durable session plane.

- [ ] **Step 4: State the canonical invariants**

Explain, rather than merely list:

- the model proposes effects but does not directly execute them;
- a protocol-visible tool intent must receive an associable observation;
- authorization and containment are distinct;
- model context and transcript are distinct;
- interruption must preserve a legal next model request;
- child loops cross explicit context and result boundaries.

- [ ] **Step 5: Walk the failing-test scenario end to end**

Use one continuous scenario:

~~~text
User: locate and fix a failing test.
~~~

Walk through:

1. task enters A1;
2. runtime assembles A2;
3. model stream reaches A3;
4. runtime distinguishes text from tool intent at A4;
5. read/search/edit/test intents cross A5;
6. runtime produces controlled effects at A6;
7. observations update messages and transcript at A7;
8. runtime continues, stops, recovers, or delegates at A8.

At each step, state the input, decision, state mutation, and output. Defer permission modes, compaction algorithms, and subagent lifecycle details to later parts.

- [ ] **Step 6: Add before/after state snapshots**

Include at least:

- before the first model request;
- after an assistant tool intent;
- after its tool observation;
- before the next model request.

Use small text or JSON-like blocks. The snapshots must distinguish model-visible messages from runtime-only state and durable transcript.

- [ ] **Step 7: Add misconceptions and chapter handoff**

Correct these false models:

- the model directly runs tools;
- tool schema and actual Tool runtime are the same object;
- permission and sandbox are the same gate;
- transcript equals current model context;
- subagent necessarily means another OS process.

End by asking:

~~~text
这张全景图成立后，下一步要先回答：模型在 A2 到底看到了什么？
~~~

Link back to README. Add the next link only after Plan 02 creates 01-model-turn/README.md.

- [ ] **Step 8: Render and review the overview**

Run:

~~~bash
npx -y @mermaid-js/mermaid-cli@11.15.0 -i ai/claude-code-source/00-one-agent-turn.md -o /tmp/claude-code-00-rendered.md
rg -n 'A[1-8]|模型协议|runtime 控制|机器效果|持久化|不变量|失败测试' ai/claude-code-source/00-one-agent-turn.md
git diff --check
~~~

Expected:

- Mermaid CLI exits 0 and writes rendered Markdown plus SVG artifacts under /tmp;
- all A1–A8 nodes and four state planes are explained;
- the chapter is understandable without source code;
- no source line-number inventory appears.

- [ ] **Step 9: Commit the new entry point**

Run:

~~~bash
git add ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md
git diff --cached --check
git commit -m "docs(claude-code): establish agent turn mental model"
~~~

Expected: one focused commit containing the new current entry point.

---

### Task 4: Foundation review gate

**Files:**

- Inspect: ai/claude-code-source/README.md
- Inspect: ai/claude-code-source/00-one-agent-turn.md
- Inspect: ai/claude-code-source/_archive/2026-06-runtime-pipeline/

- [ ] **Step 1: Check placeholders and accidental source-first writing**

Run:

~~~bash
rg -n -i 'TB.?D|TO.?DO|FIX.?ME|占位|待补|以后补' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md
rg -n 'src/.*:[0-9]+' ai/claude-code-source/README.md ai/claude-code-source/00-one-agent-turn.md
~~~

Expected: both commands exit 1.

- [ ] **Step 2: Check local links**

Run this read-only verifier:

~~~bash
python3 -c 'from pathlib import Path; import re, sys; files=list(Path("ai/claude-code-source").glob("*.md")); bad=[]; [(bad.append((str(f),t)) if not (f.parent/t).resolve().exists() else None) for f in files for t in re.findall(r"\]\((?!https?://|#)([^)#]+)", f.read_text())]; print("\n".join(f"{f}: {t}" for f,t in bad)); sys.exit(bool(bad))'
~~~

Expected: no output and exit 0.

- [ ] **Step 3: Confirm archive preservation and clean focused history**

Run:

~~~bash
rg --files ai/claude-code-source | sort
git log --oneline --decorate --max-count=5
git status --short
~~~

Expected:

- old generations remain under _archive;
- the current root contains README.md and 00-one-agent-turn.md;
- two focused foundation commits exist;
- worktree is clean.
