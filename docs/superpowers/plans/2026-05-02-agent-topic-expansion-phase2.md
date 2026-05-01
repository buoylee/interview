# Agent Topic Expansion Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Agent topic by adding the advanced multi-agent, coding-agent, and platform-case-study chapters and connecting them into the roadmap.

**Architecture:** Keep Phase 1 as the engineering core. Add three advanced chapters (`09`, `12`, `13`) that deepen coordination, coding agent internals, and end-to-end platform narrative, then update README, interview path, and cheatsheet so the full Agent topic is complete.

**Tech Stack:** Markdown documentation in `ai/ml-to-llm-roadmap/`, Git task commits, `rg`/`sed`/`git diff --check` verification.

---

## Scope

Create:

- `ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md`

Modify:

- `ai/ml-to-llm-roadmap/02-agent-tool-use/README.md`
- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md`
- `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md`

## Working Tree Notes

Before each task, inspect `git status --short`. Do not revert unrelated local files. Known unrelated files may include `.obsidian/`, `Untitled.base`, and `financial-consistency/README.md`.

## Shared Chapter Contract

Every new chapter must contain these sections in this order:

```markdown
# <Chinese chapter title>

## 这篇解决什么问题
## 学前检查
## 概念为什么出现
## 最小心智模型
## 客服退款/工单 Agent 案例
## 工程控制点
## 和应用/面试的连接
## 常见误区
## 自测
## 回到主线
```

`12-coding-agent-architecture.md` may additionally use a coding-agent example, but it should still include the客服退款/工单 Agent comparison where useful.

## Task 1: Create Multi-Agent Coordination Chapter

**Files:**

- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md`

- [ ] **Step 1: Read related docs**

Run:

```bash
sed -n '1,260p' ai/ml-to-llm-roadmap/02-agent-tool-use/05-agent-patterns-and-architectures.md
sed -n '1,260p' ai/ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/11-agent-eval-practice.md
```

Expected: Outputs cover pattern overview, durable coordination, and evaluation concepts.

- [ ] **Step 2: Create the document**

Create `09-multi-agent-coordination.md` with this exact scope:

````markdown
# Multi-Agent 协作机制

## 这篇解决什么问题

Explain how to design multi-agent systems as explicit coordination protocols rather than free-form role chat.

## 学前检查

Link to:
- `./03-state-memory-and-planning.md`
- `./05-agent-patterns-and-architectures.md`
- `./11-agent-eval-practice.md`

## 概念为什么出现

Cover when one Agent becomes too broad: different tools, permissions, contexts, evaluation criteria, and independently verifiable subtasks.

## 最小心智模型

Include this flow:

```text
supervisor -> assign task -> worker acts with scoped tools -> report structured result -> merge/check conflicts -> decide next handoff or stop
```

Add a table comparing handoff, manager-worker, blackboard, debate/competition, and sequential pipeline.

## 客服退款/工单 Agent 案例

Show how a supervisor can route to refund-status specialist, policy specialist, ticket specialist, and human handoff; explain why most simple refunds should not become multi-agent.

## 工程控制点

Cover handoff payload, role/tool permissions, shared state ownership, blackboard write rules, conflict resolution, judge/supervisor responsibility, communication schema, cost/latency budget, multi-agent eval, and when not to split.

## 和应用/面试的连接

Answer:
- Multi-agent 什么时候有必要？
- 怎么避免 multi-agent 变成混乱聊天？
- Supervisor 和 multi-agent 的区别是什么？

## 常见误区

Include misconceptions:
- agent 越多越强
- 多角色对话等于 multi-agent 架构
- shared state 可以随便写
- supervisor 可以不做权限控制
- debate 没有明确 judge 也有价值

## 自测

Ask five questions covering handoff, manager-worker, blackboard, conflict resolution, and multi-agent eval.

## 回到主线

Link to `./10-agent-security-deep-dive.md` and note that `./12-coding-agent-architecture.md` applies these coordination ideas to coding agents.
````

- [ ] **Step 3: Verify**

Run:

```bash
rg -n "^# |^## " ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md
rg -n "handoff|manager-worker|blackboard|debate|competition|shared state|conflict|supervisor|multi-agent eval|客服退款" ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md
git diff --check -- ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md
```

Expected: Required sections and concepts exist; whitespace check has no output.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md
git commit -m "docs: add multi-agent coordination"
```

Expected: Commit contains only `09-multi-agent-coordination.md`.

## Task 2: Create Coding Agent Architecture Chapter

**Files:**

- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md`

- [ ] **Step 1: Read related docs**

Run:

```bash
sed -n '1,240p' ai/ml-to-llm-roadmap/02-agent-tool-use/06-agent-runtime-engineering.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md
sed -n '1,220p' ai/coding-agent/build-guide.md
sed -n '1,220p' ai/coding-agent/production-guide.md
```

Expected: Outputs cover runtime, coordination, and existing coding-agent notes.

- [ ] **Step 2: Create the document**

Create `12-coding-agent-architecture.md` with this exact scope:

````markdown
# Coding Agent 架构

## 这篇解决什么问题

Explain how coding agents work as repo-aware, tool-using, test-driven agents rather than generic chatbots that write code.

## 学前检查

Link to:
- `./06-agent-runtime-engineering.md`
- `./09-multi-agent-coordination.md`
- `./11-agent-eval-practice.md`

## 概念为什么出现

Cover why coding agents need repository context, file selection, patch discipline, test loops, review loops, sandboxing, and user-change protection.

## 最小心智模型

Include this loop:

```text
task -> inspect repo -> plan edits -> select files -> generate patch -> apply patch -> run checks -> debug/revise -> review -> commit/report
```

Add a table with component, responsibility, and failure mode. Rows must include repo context/indexing, file selection, planner, patch writer, tool runner, test loop, review loop, compaction, subagent delegation, sandbox/permission.

## 客服退款/工单 Agent 案例

Briefly contrast business-action agents with coding agents: refund agents mutate business systems; coding agents mutate source code and must protect user edits, tests, and repo history.

## 工程控制点

Cover repo indexing, file selection, planning, patch generation, apply patch, test loop, code review loop, context compaction, subagent delegation, sandbox/permission, avoiding overwrite of user changes, and commit hygiene.

## 和应用/面试的连接

Answer:
- Cursor / Codex / Claude Code 这类 coding agent 大概怎么工作？
- Coding agent 为什么要读代码而不是直接改？
- 如何防止 coding agent 覆盖用户改动？

## 常见误区

Include misconceptions:
- coding agent 只是会写代码的聊天机器人
- 把整个 repo 塞进上下文最好
- 直接重写文件比 patch 更简单
- 测试失败说明模型不行
- subagent 越多越快

## 自测

Ask five questions covering repo context, patch discipline, test loop, compaction, and user-change protection.

## 回到主线

Link to `./13-agent-platform-case-study.md`.
````

- [ ] **Step 3: Verify**

Run:

```bash
rg -n "^# |^## " ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md
rg -n "repo|file selection|patch|test loop|code review|compaction|subagent|sandbox|permission|覆盖用户改动" ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md
git diff --check -- ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md
```

Expected: Required sections and concepts exist; whitespace check has no output.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md
git commit -m "docs: add coding agent architecture"
```

Expected: Commit contains only `12-coding-agent-architecture.md`.

## Task 3: Create Agent Platform Case Study Chapter

**Files:**

- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md`

- [ ] **Step 1: Read related docs**

Run:

```bash
sed -n '1,180p' ai/ml-to-llm-roadmap/02-agent-tool-use/README.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/07-agent-workflow-and-durable-state.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/08-agent-memory-deep-dive.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/10-agent-security-deep-dive.md
sed -n '1,220p' ai/ml-to-llm-roadmap/02-agent-tool-use/11-agent-eval-practice.md
```

Expected: Outputs cover the engineering building blocks this case study integrates.

- [ ] **Step 2: Create the document**

Create `13-agent-platform-case-study.md` with this exact scope:

````markdown
# Agent 平台案例：客服退款/工单系统

## 这篇解决什么问题

Explain how to assemble the Agent topic into a complete platform narrative for interviews and real system design.

## 学前检查

Link to:
- `./06-agent-runtime-engineering.md`
- `./07-agent-workflow-and-durable-state.md`
- `./10-agent-security-deep-dive.md`
- `./11-agent-eval-practice.md`

## 概念为什么出现

Cover why platform design needs routing, tool registry, permission model, workflow graph, memory, eval, observability, human handoff, and cost control together.

## 最小心智模型

Include this architecture flow:

```text
user -> gateway/router -> agent runtime -> workflow graph -> tool registry/policy -> memory/eval/observability -> response or human handoff
```

Add a table with platform component, responsibility, and key design decision.

## 客服退款/工单 Agent 案例

Make this the main case: refund query, order ownership, refund status read, ticket creation, approval/human handoff, final response.

## 工程控制点

Cover intent routing, tool registry, permission model, workflow graph, memory, eval, observability, human handoff, cost control, model routing, context trimming, tool caching, and step limits.

## 和应用/面试的连接

Answer:
- 讲一个你设计过的 Agent 平台，架构怎么讲？
- 这个平台如何处理安全、成本、失败恢复和人工升级？
- 怎么把 Agent 项目讲成系统设计而不是 prompt demo？

## 常见误区

Include misconceptions:
- Agent 平台就是聊天 UI 加工具
- 工具越多平台越强
- 只要接了人工就安全
- eval 可以上线后再补
- 成本控制只是换便宜模型

## 自测

Ask five questions covering routing, tool registry, permissions, workflow graph, observability, and handoff.

## 回到主线

Link back to `./README.md` and note that the Agent topic is complete at this stage.
````

- [ ] **Step 3: Verify**

Run:

```bash
rg -n "^# |^## " ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md
rg -n "intent routing|tool registry|permission model|workflow graph|observability|human handoff|cost control|model routing|context trimming|客服退款" ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md
git diff --check -- ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md
```

Expected: Required sections and concepts exist; whitespace check has no output.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md
git commit -m "docs: add agent platform case study"
```

Expected: Commit contains only `13-agent-platform-case-study.md`.

## Task 4: Connect Phase 2 Chapters

**Files:**

- Modify: `ai/ml-to-llm-roadmap/02-agent-tool-use/README.md`
- Modify: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md`
- Modify: `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md`

- [ ] **Step 1: Update README**

Modify README:

- Add default learning-order entries for 09, 12, 13:
  - `9. [Multi-Agent 协作机制](./09-multi-agent-coordination.md)`
  - Keep security/eval as 10 and 11.
  - `12. [Coding Agent 架构](./12-coding-agent-architecture.md)`
  - `13. [Agent 平台案例：客服退款/工单系统](./13-agent-platform-case-study.md)`
- Change the 高级层 target from `后续扩展...` to actual learning goal.
- Extend 系统落地 path to include `13`.
- Add one short sentence that the full topic now covers foundation, engineering, and advanced platform narrative.

- [ ] **Step 2: Update interview path**

Modify interview path:

- Add a section `## 一天以上：高级专题与项目叙事`.
- Link 09, 12, 13 with goals.
- Add questions:
  - `Multi-agent 怎么设计交接、共享状态和冲突裁决？`
  - `Coding agent 如何选文件、生成 patch、跑测试和保护用户改动？`
  - `如何把客服 Agent 平台讲成完整系统设计？`

- [ ] **Step 3: Update cheatsheet**

Modify cheatsheet:

- Add high-frequency rows for multi-agent coordination, coding agent architecture, and platform case study.
- Add easy-confusion rows:
  - multi-agent vs role-play chat
  - coding agent vs code generator
  - platform case study vs prompt demo
- Add project connection bullets for coding agent and platform case study.
- Add backlinks to 09, 12, 13.

- [ ] **Step 4: Verify**

Run:

```bash
rg -n "09-multi-agent-coordination|12-coding-agent-architecture|13-agent-platform-case-study" ai/ml-to-llm-roadmap/02-agent-tool-use/README.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md
rg -n "后续扩展" ai/ml-to-llm-roadmap/02-agent-tool-use/README.md
git diff --check -- ai/ml-to-llm-roadmap/02-agent-tool-use/README.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md
```

Expected: Phase 2 filenames are linked; README no longer treats 09/12/13 as future-only; whitespace check has no output.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use/README.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md
git commit -m "docs: connect advanced agent chapters"
```

Expected: Commit contains only the three modified index/review files.

## Final Verification

- [ ] **Step 1: Verify all planned files exist**

Run:

```bash
for f in \
  ai/ml-to-llm-roadmap/02-agent-tool-use/09-multi-agent-coordination.md \
  ai/ml-to-llm-roadmap/02-agent-tool-use/12-coding-agent-architecture.md \
  ai/ml-to-llm-roadmap/02-agent-tool-use/13-agent-platform-case-study.md; do test -f "$f" || exit 1; done
```

Expected: No output and exit code 0.

- [ ] **Step 2: Verify index coverage**

Run:

```bash
rg -n "09-multi-agent-coordination|12-coding-agent-architecture|13-agent-platform-case-study" ai/ml-to-llm-roadmap/02-agent-tool-use/README.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md
```

Expected: All three files are referenced from the roadmap index/review materials.

- [ ] **Step 3: Verify Markdown whitespace**

Run:

```bash
git diff --check HEAD~4..HEAD
```

Expected: No output and exit code 0.

- [ ] **Step 4: Inspect final status**

Run:

```bash
git status --short
```

Expected: No Agent-topic files remain unstaged or uncommitted. Pre-existing unrelated files may still appear.

## Final Report Requirements

Report commit hashes, verification commands/results, remaining unrelated dirty files, and a concise summary of the completed full Agent topic.
