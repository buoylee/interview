# Agent Skills Learning Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source-backed learning foundation for Superpowers and Matt Pocock Skills, archive the obsolete three-library report, and publish a clear comparison without yet defining the local production policy.

**Architecture:** Keep upstream description, cross-library comparison, and later local policy as distinct layers. Organize Superpowers by lifecycle, organize Matt Pocock around the selected 8+2+2 set, and make every drift-prone claim traceable to a pinned local snapshot.

**Tech Stack:** Traditional-Chinese Markdown, Mermaid, Git, `rg`, POSIX shell verification, local source repositories at `/Users/buoy/Development/gitrepo/superpowers` and `/Users/buoy/Development/gitrepo/skills`.

## Global Constraints

- Work only in `/Users/buoy/Development/gitrepo/interview/.worktrees/agent-skills-learning` on branch `codex/agent-skills-learning`.
- Do not modify either upstream repository.
- Superpowers facts use commit `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`).
- Matt Pocock facts use commit `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`).
- Source-analysis pages begin with library name, local path, commit/tag, verified date `2026-07-21`, and primary source files.
- Body copy is Traditional Chinese; skill names, commands, artifact names, frontmatter fields, and exact technical terms remain English.
- Mark mutable counts, platform support, invocation behavior, and maturity as snapshot facts.
- Mark conclusions synthesized by this project as `本專題判斷`; never attribute them to an upstream author.
- Explain workflows and invariants before individual commands or isolated facts.
- Superpowers `v6.1.1` task review means one fresh task reviewer returns ordered Spec Compliance and Code Quality verdicts, followed later by broad whole-branch review; do not describe two separate task-reviewer agents.
- Cover all 14 Superpowers skills in depth.
- Cover exactly 12 Matt skills in depth: the eight core workflow skills, two quality foundations, and two conditional skills specified below.
- Treat `setup-matt-pocock-skills` and `ask-matt` as intro-only routing/prerequisite skills; give every remaining Matt skill index-only coverage.
- Do not claim the selected Matt skills are telemetry-ranked or objectively most downloaded.
- Do not define the local AI Code Review Protocol, Core Profile, or Project Overlay in this plan; later plans own those normative artifacts.
- Every task ends with fresh verification and a focused commit containing only that task's files.

---

## File Structure

This plan produces:

```text
ai/coding-agent/agent-skills/
├── README.md
├── 00-agent-skills-mental-model.md
├── 01-two-libraries-workflow-map.md
├── 02-superpowers/
│   ├── README.md
│   ├── 01-methodology-and-lifecycle.md
│   ├── 02-all-skills-guide.md
│   └── 03-strengths-and-boundaries.md
├── 03-matt-pocock/
│   ├── README.md
│   ├── 01-main-flow.md
│   ├── 02-core-skills-guide.md
│   └── 03-quality-foundations-and-boundaries.md
├── 04-comparison-and-composition.md
└── _archive/
    └── legacy-three-library-report/
        ├── README.md
        ├── 00-overview.md
        ├── 01-superpowers.md
        ├── 02-mattpocock-skills.md
        ├── 03-agent-skills.md
        └── _design.md
```

The root README is deliberately foundation-complete at the end of this plan. The next two plans extend it with normative Code Review and Production Profile navigation only after those targets exist.

## Shared Skill Explanation Contract

Every in-depth skill entry must contain these labeled fields in this order:

1. `Failure mode`
2. `Trigger and preconditions`
3. `Inputs`
4. `Outputs`
5. `Internal flow`
6. `Composition`
7. `Guarantees`
8. `Non-guarantees`
9. `When not to use`
10. `Production gap`
11. `Source anchors`

The fields may be compact tables for short skills and subsections for complex skills, but none may be omitted.

### Task 1: Archive the Legacy Three-Library Report

**Files:**

- Move: `ai/coding-agent/agent-skills-comparison/00-overview.md`
- Move: `ai/coding-agent/agent-skills-comparison/01-superpowers.md`
- Move: `ai/coding-agent/agent-skills-comparison/02-mattpocock-skills.md`
- Move: `ai/coding-agent/agent-skills-comparison/03-agent-skills.md`
- Move: `ai/coding-agent/agent-skills-comparison/_design.md`
- Create: `ai/coding-agent/agent-skills/_archive/legacy-three-library-report/README.md`
- Modify: the five moved Markdown files to add an archive banner

**Interfaces:**

- Consumes: the existing `ai/coding-agent/agent-skills-comparison/` snapshot.
- Produces: one historical-only archive at `ai/coding-agent/agent-skills/_archive/legacy-three-library-report/`; later navigation must not use it as a factual source.

- [ ] **Step 1: Confirm branch, source files, and clean starting state**

Run:

```bash
git branch --show-current
git status --short
rg --files ai/coding-agent/agent-skills-comparison | sort
```

Expected:

- branch output is `codex/agent-skills-learning`;
- status is empty;
- exactly five existing files are listed.

- [ ] **Step 2: Create the archive parent and move all five files with Git history**

Run:

```bash
mkdir -p ai/coding-agent/agent-skills/_archive/legacy-three-library-report
git mv ai/coding-agent/agent-skills-comparison/00-overview.md ai/coding-agent/agent-skills/_archive/legacy-three-library-report/00-overview.md
git mv ai/coding-agent/agent-skills-comparison/01-superpowers.md ai/coding-agent/agent-skills/_archive/legacy-three-library-report/01-superpowers.md
git mv ai/coding-agent/agent-skills-comparison/02-mattpocock-skills.md ai/coding-agent/agent-skills/_archive/legacy-three-library-report/02-mattpocock-skills.md
git mv ai/coding-agent/agent-skills-comparison/03-agent-skills.md ai/coding-agent/agent-skills/_archive/legacy-three-library-report/03-agent-skills.md
git mv ai/coding-agent/agent-skills-comparison/_design.md ai/coding-agent/agent-skills/_archive/legacy-three-library-report/_design.md
```

Expected: every move exits zero and `ai/coding-agent/agent-skills-comparison/` no longer contains tracked files.

- [ ] **Step 3: Add the same historical warning after the H1 of each moved file**

Insert this exact block after each document title:

```markdown
> [!WARNING]
> 這是已封存的三庫比較舊快照，只保留作為思考歷史。Matt Pocock 的 skill 數量、invocation model、workflow 與 distribution 描述已漂移；Superpowers 內容也不代表目前固定的 `v6.1.1` 快照。新的主線文件不得引用本頁作為當前事實來源。
```

Expected: the banner appears once in each of the five files and no original body content is deleted.

- [ ] **Step 4: Create the archive README with explicit provenance and exit route**

Create `ai/coding-agent/agent-skills/_archive/legacy-three-library-report/README.md` with these sections and assertions:

```markdown
# Legacy Three-Library Report

> [!WARNING]
> 本目錄是歷史快照，不是目前 Agent Skills 學習路徑，也不是兩個上游庫的當前事實來源。

## 為什麼封存

- 舊報告同時比較三個庫，已偏離目前只研究 Superpowers 與 Matt Pocock Skills 的範圍。
- Matt Pocock 的數量、invocation model、workflow 與 distribution 已漂移。
- Superpowers 的 SDD 和 Code Review 拓撲也已更新。

## 如何使用

只用來追溯早期問題拆解與比較維度；當前結論從 `../../README.md` 進入，並回到固定 commit 的上游來源驗證。

## 歷史文件

- [00 Overview](./00-overview.md)
- [01 Superpowers](./01-superpowers.md)
- [02 Matt Pocock Skills](./02-mattpocock-skills.md)
- [03 Agent Skills](./03-agent-skills.md)
- [Original Design](./_design.md)
```

- [ ] **Step 5: Verify archive completeness and scope**

Run:

```bash
test "$(rg -l '這是已封存的三庫比較舊快照' ai/coding-agent/agent-skills/_archive/legacy-three-library-report/*.md | wc -l | tr -d ' ')" = "5"
test "$(rg --files ai/coding-agent/agent-skills/_archive/legacy-three-library-report | wc -l | tr -d ' ')" = "6"
test ! -d ai/coding-agent/agent-skills-comparison
git diff --check
git status --short
```

Expected: all `test` commands and `git diff --check` exit zero; status contains only the five renames and the new archive README.

- [ ] **Step 6: Commit the archive migration**

```bash
git add ai/coding-agent/agent-skills/_archive/legacy-three-library-report
git commit -m "docs(agent-skills): archive legacy comparison"
```

### Task 2: Build the Mental Model and Two Workflow Maps

**Files:**

- Create: `ai/coding-agent/agent-skills/00-agent-skills-mental-model.md`
- Create: `ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md`

**Interfaces:**

- Consumes: the pinned source snapshots and the shared skill explanation contract.
- Produces: the vocabulary and lifecycle positions reused by every later chapter: `Harness and invocation -> Skill workflow -> Project policy -> Domain invariants -> Tools and evidence -> Delivery gate`.

- [ ] **Step 1: Write the layered Agent Skills mental model**

Create `00-agent-skills-mental-model.md` with this section order:

```markdown
# 00 - Agent Skills 心智模型

## 先給結論
## 六層工程模型
## Skill 的檔案與載入機制
## Trigger、Hard Gate 與停止條件
## Reference、Artifact 與 Composition
## Skill 能保證什麼
## Skill 不能保證什麼
## 為什麼 Workflow Discipline 不等於 Production Policy
## 如何閱讀後續章節
## 一句話總結
```

The six-layer section must define and distinguish:

```text
Harness and invocation
  -> Skill workflow
  -> Project policy
  -> Domain invariants
  -> Tools and evidence
  -> Delivery gate
```

Required assertions:

- `SKILL.md` packages behavior and process, not all facts needed by a project.
- `description` is primarily a discovery trigger; the body defines the actual workflow.
- user-invoked and model-invoked behavior depends on the host harness, not Markdown alone.
- a hard gate blocks transition until evidence or approval exists; advice only influences judgment.
- artifacts preserve decisions across context boundaries, but only if their contract is explicit.
- tests and tools provide evidence; a skill cannot manufacture a missing business invariant.
- production readiness is a claim across policy, domain facts, evidence, and delivery decisions.

- [ ] **Step 2: Write the two-library map before any skill-by-skill detail**

Create `01-two-libraries-workflow-map.md` with this section order:

```markdown
# 01 - 兩個 Skill 庫的 Workflow 全景

## 先給結論
## Superpowers 主流程
## Superpowers 的分支與 Meta Skills
## Matt Pocock 主流程
## Matt Pocock 的品質基礎與條件式能力
## 相同名稱不代表相同責任
## 從任務類型選入口
## 讀圖限制
## 一句話總結
```

Include one Mermaid flowchart per library. The Superpowers diagram must show:

```text
using-superpowers -> brainstorming -> using-git-worktrees -> writing-plans
writing-plans -> subagent-driven-development OR executing-plans
implementation -> test-driven-development
unexpected behavior -> systematic-debugging
task review -> requesting-code-review -> receiving-code-review
all tasks -> whole-branch review -> verification-before-completion
verification -> finishing-a-development-branch
dispatching-parallel-agents as a conditional branch
writing-skills as a meta capability outside the feature path
```

The Matt diagram must show:

```text
setup-matt-pocock-skills -> grill-with-docs -> to-spec -> to-tickets -> implement
implement -> tdd -> code-review
diagnosing-bugs as a bug on-ramp
handoff as a cross-session boundary
domain-modeling and codebase-design as quality foundations
prototype and improve-codebase-architecture as conditional paths
ask-matt as a router, not a lifecycle stage
```

State explicitly that arrows represent recommended control flow inferred from the pinned sources, not runtime-enforced transitions on every host.

- [ ] **Step 3: Verify vocabulary, diagrams, and normative boundary**

Run:

```bash
rg -n '^## ' ai/coding-agent/agent-skills/00-agent-skills-mental-model.md ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md
rg -n 'Harness and invocation|Project policy|Domain invariants|Delivery gate' ai/coding-agent/agent-skills/00-agent-skills-mental-model.md
test "$(rg -c '^```mermaid$' ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md)" = "2"
rg -n '本專題判斷|不等於|不能保證' ai/coding-agent/agent-skills/00-agent-skills-mental-model.md ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md
git diff --check
```

Expected: all commands exit zero; exactly two Mermaid blocks exist; both files state what is descriptive and what is inferred.

- [ ] **Step 4: Commit the foundation chapters**

```bash
git add ai/coding-agent/agent-skills/00-agent-skills-mental-model.md ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md
git commit -m "docs(agent-skills): add mental model and workflow maps"
```

### Task 3: Explain the Complete Superpowers Lifecycle

**Files:**

- Create: `ai/coding-agent/agent-skills/02-superpowers/README.md`
- Create: `ai/coding-agent/agent-skills/02-superpowers/01-methodology-and-lifecycle.md`
- Create: `ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md`
- Create: `ai/coding-agent/agent-skills/02-superpowers/03-strengths-and-boundaries.md`

**Interfaces:**

- Consumes: the Superpowers `v6.1.1` source tree and vocabulary from Task 2.
- Produces: one lifecycle model plus 14 entries conforming to the shared skill explanation contract; the comparison chapter in Task 5 relies on its stated guarantees and non-guarantees.

- [ ] **Step 1: Create the Superpowers source card and reading entry**

The top of every file in `02-superpowers/` must include this metadata table immediately after the title:

```markdown
| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
```

Create `02-superpowers/README.md` with:

```markdown
# Superpowers 學習入口
## 先給結論
## Source Snapshot
## 作者提供的是什麼
## 建議閱讀順序
## 按任務跳讀
## 14 Skills Inventory
## Snapshot 限制
```

The inventory groups skills into discovery/design, isolation/planning, execution, quality control, completion, and meta capability; each item links to its entry in `02-all-skills-guide.md`.

- [ ] **Step 2: Explain methodology, gates, artifacts, and the v6.1.1 SDD topology**

Create `01-methodology-and-lifecycle.md` with:

```markdown
# Superpowers 的方法論與生命週期
## 先給結論
## Invocation Discipline
## Design Before Implementation
## Isolation and Artifact Flow
## Planning and Execution Strategies
## v6.1.1 Subagent-Driven Development
## TDD, Debugging, Review, and Verification Boundaries
## Branch Completion
## Cost and Friction
## What the Workflow Actually Guarantees
## What It Does Not Know
```

The SDD section must trace this exact artifact flow:

```text
pre-flight plan check
  -> task-brief writes task-N-brief.md
  -> fresh implementer writes implementer report
  -> review-package fixes BASE_SHA..HEAD_SHA and writes commit/stat/diff
  -> one fresh task reviewer returns two ordered verdicts
  -> Critical/Important fix and re-review loop
  -> Minor findings enter .superpowers/sdd/progress.md
  -> after all tasks, broad whole-branch review
```

Explain that README wording such as “two-stage review” describes two logical judgments; in `v6.1.1`, task-level agent topology uses one reviewer prompt containing Part 1 and Part 2.

Primary anchors must include:

- `README.md`
- `skills/using-superpowers/SKILL.md`
- `skills/brainstorming/SKILL.md`
- `skills/writing-plans/SKILL.md`
- `skills/subagent-driven-development/SKILL.md`
- `skills/subagent-driven-development/implementer-prompt.md`
- `skills/subagent-driven-development/task-reviewer-prompt.md`
- `skills/subagent-driven-development/scripts/task-brief`
- `skills/subagent-driven-development/scripts/review-package`
- `skills/subagent-driven-development/scripts/sdd-workspace`

- [ ] **Step 3: Write all 14 skill contracts in lifecycle order**

Create `02-all-skills-guide.md` with exactly these H3 entries and no alphabetical reordering:

```markdown
### `using-superpowers`
### `brainstorming`
### `using-git-worktrees`
### `writing-plans`
### `subagent-driven-development`
### `executing-plans`
### `dispatching-parallel-agents`
### `test-driven-development`
### `systematic-debugging`
### `requesting-code-review`
### `receiving-code-review`
### `verification-before-completion`
### `finishing-a-development-branch`
### `writing-skills`
```

For every entry, fill all 11 shared contract fields. Preserve these distinctions:

- `using-superpowers` governs discovery and mandatory invocation before acting.
- `brainstorming` ends at an approved, committed spec and transitions only to `writing-plans`.
- `using-git-worktrees` detects existing isolation before creating anything and verifies baseline state.
- `writing-plans` defines exact file boundaries, interfaces, tests, commands, and frequent commits.
- `subagent-driven-development` is current-session task execution with fresh implementers, bounded review packages, task review, and final branch review.
- `executing-plans` is a checkpointed alternative when work is executed in another session or without per-task subagent orchestration.
- `dispatching-parallel-agents` applies only to genuinely independent investigations or tasks.
- `test-driven-development` proves a test can fail before minimal implementation and refactoring.
- `systematic-debugging` requires root-cause evidence before a fix and escalates after repeated failed hypotheses.
- `requesting-code-review` fixes the review range and asks a broad reviewer to inspect against requirements and production readiness.
- `receiving-code-review` requires technical verification, not performative agreement or blind implementation.
- `verification-before-completion` requires fresh evidence for the exact completion claim.
- `finishing-a-development-branch` verifies tests, detects workspace provenance, then offers merge, PR, keep, or discard behavior.
- `writing-skills` applies RED-GREEN-REFACTOR to process documentation and distinguishes discovery descriptions from workflow bodies.

- [ ] **Step 4: State Superpowers strengths and production boundaries**

Create `03-strengths-and-boundaries.md` with:

```markdown
# Superpowers 的強項與邊界
## 先給結論
## 它刻意強化的 Failure Modes
## 它提供的 Workflow Guarantees
## 它不提供的 Project Facts
## 為什麼輸出仍可能不像 Production Code
## Code Review 的實際覆蓋
## 適合與不適合的任務
## 如何加本地規範而不 Fork
## 一句話總結
```

The production-gap section must explicitly cover data consistency, concurrency, idempotency, timeout/retry/fallback, compatibility/migration, encapsulation, readability, reuse, interface orientation, decoupling, observability, rollback, and recovery. The conclusion must be: the omissions are primarily scope boundaries of a generic workflow library, not evidence that production safety is intentionally rejected; some simplicity is deliberate YAGNI, but project-specific invariants still have to be supplied externally.

- [ ] **Step 5: Verify Superpowers inventory, source anchors, and review semantics**

Run:

```bash
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md | wc -l | tr -d ' ')" = "14"
for skill in using-superpowers brainstorming using-git-worktrees writing-plans subagent-driven-development executing-plans dispatching-parallel-agents test-driven-development systematic-debugging requesting-code-review receiving-code-review verification-before-completion finishing-a-development-branch writing-skills; do rg -q "### \`$skill\`" ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md || exit 1; done
test "$(rg -c 'Failure mode|Trigger and preconditions|Inputs|Outputs|Internal flow|Composition|Guarantees|Non-guarantees|When not to use|Production gap|Source anchors' ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md)" -ge "154"
rg -n 'one fresh task reviewer|同一位 fresh task reviewer|two logical|兩個 logical' ai/coding-agent/agent-skills/02-superpowers
rg -n 'd884ae04edebef577e82ff7c4e143debd0bbec99|v6.1.1' ai/coding-agent/agent-skills/02-superpowers
git diff --check
```

Expected: all commands exit zero; the contract-field count is at least `14 × 11 = 154`; no text claims two separate task reviewer agents.

- [ ] **Step 6: Commit the Superpowers chapters**

```bash
git add ai/coding-agent/agent-skills/02-superpowers
git commit -m "docs(agent-skills): explain superpowers lifecycle"
```

### Task 4: Explain the Selected Matt Pocock Workflow and Index the Rest

**Files:**

- Create: `ai/coding-agent/agent-skills/03-matt-pocock/README.md`
- Create: `ai/coding-agent/agent-skills/03-matt-pocock/01-main-flow.md`
- Create: `ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md`
- Create: `ai/coding-agent/agent-skills/03-matt-pocock/03-quality-foundations-and-boundaries.md`

**Interfaces:**

- Consumes: Matt snapshot `ed37663cc5fbef691ddfecd080dff42f7e7e350d` and vocabulary from Task 2.
- Produces: 12 full skill contracts, two intro-only entries, and one complete 41-skill snapshot inventory used by comparison and future source-drift checks.

- [ ] **Step 1: Create the Matt source card, selection rationale, and complete inventory**

Every file in `03-matt-pocock/` starts with:

```markdown
| Source field | Value |
|---|---|
| Library | `mattpocock/skills` |
| Local path | `/Users/buoy/Development/gitrepo/skills` |
| Snapshot | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Verified | `2026-07-21` |
```

Create `README.md` with:

```markdown
# Matt Pocock Skills 學習入口
## 先給結論
## Source Snapshot
## 為什麼不深挖全部 41 個 Skills
## 8 + 2 + 2 選擇模型
## Prerequisite and Router
## 建議閱讀順序
## Complete Snapshot Inventory
## Snapshot 限制
```

The inventory must contain all 41 names in a table with columns `Skill`, `Source bucket`, `Coverage`, `One-line purpose`, and `Why this depth`. Use these coverage values:

- `deep-core`: `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`, `diagnosing-bugs`, `handoff`;
- `deep-foundation`: `domain-modeling`, `codebase-design`;
- `deep-conditional`: `prototype`, `improve-codebase-architecture`;
- `intro-only`: `setup-matt-pocock-skills`, `ask-matt`;
- `index-only`: every other snapshot skill.

Use the source directory as the maturity bucket: `engineering`, `productivity`, `in-progress`, `deprecated`, `misc`, or `personal`. State that the selection is based on author-defined main flow, cross-task reuse, and this project’s production-quality questions—not usage telemetry.

- [ ] **Step 2: Explain the main flow and control boundaries**

Create `01-main-flow.md` with:

```markdown
# Matt Pocock Skills 主流程
## 先給結論
## Setup and Routing
## Grill -> Spec -> Tickets
## Implement -> TDD -> Code Review
## Bug On-Ramp
## Handoff Across Context Boundaries
## Quality Foundations
## Conditional Prototype and Architecture Paths
## Artifact Flow
## Where Human Control Remains
## 一句話總結
```

Include a Mermaid diagram showing the exact flow fixed in the design spec. Explain whether each transition is explicit in a skill, implied by an artifact, or this project’s composition recommendation.

- [ ] **Step 3: Write the eight core workflow contracts**

Create `02-core-skills-guide.md` with exactly these H3 entries:

```markdown
### `grill-with-docs`
### `to-spec`
### `to-tickets`
### `implement`
### `tdd`
### `code-review`
### `diagnosing-bugs`
### `handoff`
```

Fill all 11 shared fields for each. Preserve these boundaries:

- `grill-with-docs` challenges a design against repository/domain documents and updates the agreed artifact.
- `to-spec` turns conversation context into a durable implementation specification.
- `to-tickets` decomposes a spec into independently grabbable work with dependency information.
- `implement` is an execution orchestrator and must not be confused with an engineering-quality policy.
- `tdd` provides a red/green/refactor behavior loop but does not prove missing domain invariants.
- `code-review` separates Standards and Spec concerns, pins the review base, and does not collapse findings into an opaque score.
- `diagnosing-bugs` starts from evidence and hypotheses rather than speculative edits.
- `handoff` preserves enough state for a new context without pretending all tacit knowledge survived.

- [ ] **Step 4: Write the four foundation/conditional contracts and the production boundary**

Create `03-quality-foundations-and-boundaries.md` with exactly these in-depth H3 entries:

```markdown
### `domain-modeling`
### `codebase-design`
### `prototype`
### `improve-codebase-architecture`
```

After the four 11-field contracts, add:

```markdown
## Why These Four Matter to Production Quality
## What They Still Cannot Infer
## Intro-Only Skills
## Index-Only Boundary
## When to Add Project Policy
## 一句話總結
```

The quality discussion must connect domain vocabulary and invariants to interface seams, deep modules, dependency direction, encapsulation, testability, and controlled architecture improvement. It must also state that architectural taste cannot choose transaction semantics, retry budgets, privacy rules, compatibility policy, or recovery objectives without project facts.

- [ ] **Step 5: Verify the 12 deep contracts and all 41 inventory names**

Run:

```bash
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md | wc -l | tr -d ' ')" = "8"
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/03-matt-pocock/03-quality-foundations-and-boundaries.md | wc -l | tr -d ' ')" = "4"
test "$(rg -o 'Failure mode|Trigger and preconditions|Inputs|Outputs|Internal flow|Composition|Guarantees|Non-guarantees|When not to use|Production gap|Source anchors' ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md ai/coding-agent/agent-skills/03-matt-pocock/03-quality-foundations-and-boundaries.md | wc -l | tr -d ' ')" -ge "132"
comm -23 <(rg --files /Users/buoy/Development/gitrepo/skills | rg '/SKILL\.md$' | sed -E 's#^.*/([^/]+)/SKILL\.md$#\1#' | sort -u) <(rg -o '`[a-z0-9-]+`' ai/coding-agent/agent-skills/03-matt-pocock/*.md | tr -d '`' | sort -u)
git diff --check
```

Expected: the first two counts are 8 and 4, contract fields total at least `12 × 11 = 132`, `comm` prints nothing, and `git diff --check` exits zero.

- [ ] **Step 6: Commit the Matt Pocock chapters**

```bash
git add ai/coding-agent/agent-skills/03-matt-pocock
git commit -m "docs(agent-skills): explain matt pocock core workflow"
```

### Task 5: Compare, Compose, and Publish the Foundation Navigation

**Files:**

- Create: `ai/coding-agent/agent-skills/04-comparison-and-composition.md`
- Create: `ai/coding-agent/agent-skills/README.md`

**Interfaces:**

- Consumes: Tasks 1–4.
- Produces: the descriptive/comparative entrypoint extended later by the AI Code Review and Production Profile plans.

- [ ] **Step 1: Write the comparison along ten explicit axes**

Create `04-comparison-and-composition.md` with:

```markdown
# 04 - Superpowers 與 Matt Pocock Skills：差異與組合
## 先給結論
## Comparison Matrix
## Methodology vs Composable Toolset
## Invocation and User Control
## Artifact Flow and Context Hygiene
## TDD, Debugging, Review, and Verification
## Domain Language and Codebase Design
## Production Coverage and Gaps
## Cost, Friction, and Task Size
## Minimal Sufficient Compositions
## Conflict Resolution Rules
## When Not to Combine Them
## 一句話總結
```

The matrix must cover complete methodology/toolset, control, invocation, artifacts, context isolation, quality loops, domain/design support, customization, production gaps, and cost. Required verdicts:

- Superpowers is the stronger end-to-end lifecycle and gate system.
- Matt is the more composable collection for interrogation, artifact transformation, domain modeling, design, review, and handoff.
- Neither is a complete production policy.
- Combining every gate is counterproductive; choose a primary lifecycle and add only missing capabilities.
- When rules conflict, explicit project instructions and accepted spec decisions win; then the chosen primary lifecycle; then optional helper skills.

Provide four minimal compositions: normal feature, production-critical feature, bug diagnosis, and architecture improvement.

- [ ] **Step 2: Create the root learning-track README**

Create `ai/coding-agent/agent-skills/README.md` with:

```markdown
# Agent Skills：Workflow、Code Review 與 Production Engineering
## 先給結論
## 這條學習路徑回答什麼
## Descriptive、Comparative、Normative 三種文件
## 線性閱讀順序
## 按任務跳讀
## Source Snapshots
## 目前已完成的範圍
## 後續規範層
```

At this phase, link all existing foundation/library/comparison files and the archive. Under `後續規範層`, explain without broken links that the next plans add AI Code Review and Production Engineering Profile; later plans will replace that paragraph with live navigation.

- [ ] **Step 3: Verify links, boundaries, and source coverage**

Run this link checker from the worktree root:

```bash
python3 -c 'from pathlib import Path; import re,sys; root=Path("ai/coding-agent/agent-skills"); bad=[]; [(bad.append((str(p),u)) if not (p.parent/u.split("#",1)[0]).resolve().exists() else None) for p in root.rglob("*.md") for u in re.findall(r"\[[^]]+\]\(([^)]+)\)",p.read_text()) if u and not u.startswith(("http://","https://","#","/"))]; print("\n".join(f"{p}: {u}" for p,u in bad)); sys.exit(bool(bad))'
```

Run additional checks:

```bash
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md | wc -l | tr -d ' ')" = "14"
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md ai/coding-agent/agent-skills/03-matt-pocock/03-quality-foundations-and-boundaries.md | wc -l | tr -d ' ')" = "12"
rg -n 'Descriptive|Comparative|Normative|本專題判斷' ai/coding-agent/agent-skills/README.md ai/coding-agent/agent-skills/04-comparison-and-composition.md
! rg -n 'T[B]D|T[O]DO|implemen[t] later|fill i[n] details' ai/coding-agent/agent-skills --glob '*.md'
git diff --check
git status --short
```

Expected: the link checker prints nothing and exits zero; counts are 14 and 12; no accidental placeholder marker is found; only Task 5 files are uncommitted.

- [ ] **Step 4: Commit the comparison and foundation entrypoint**

```bash
git add ai/coding-agent/agent-skills/04-comparison-and-composition.md ai/coding-agent/agent-skills/README.md
git commit -m "docs(agent-skills): compare and compose workflows"
```

## Plan Completion Gate

Before starting the AI Code Review plan, run:

```bash
git status --short
git log --oneline --max-count=5
git diff --check HEAD~5..HEAD
```

Expected:

- worktree is clean;
- the five task commits are visible after the design-spec commits;
- the foundation track contains the archive, mental model, two workflow maps, all 14 Superpowers contracts, 12 deep Matt contracts, a complete Matt inventory, comparison, and a working root README.
