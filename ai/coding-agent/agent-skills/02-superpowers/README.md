# Superpowers 學習入口

| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
| Primary sources | `README.md`, `skills/*/SKILL.md`, SDD prompts and scripts |

## 先給結論

Superpowers 是一套 opinionated software-development methodology，不只是 14 份互不相關的提示詞。它的核心價值是把常見 Agent failure modes 轉成強制 transition：先 discovery，再 design approval，再 isolated workspace、implementation plan、TDD、review、fresh verification 和 branch completion。

它最強的是 workflow discipline、artifact continuity、fresh-context execution/review 和 evidence-before-claim；它不會自行知道某專案的 transaction boundary、idempotency semantics、SLO、security policy 或 recovery objective。

## Source Snapshot

本章只描述本地 `v6.1.1`。數量、支援平台、prompt topology、scripts 和 distribution 都是 snapshot facts；未經重新比對 source，不把它們外推成永久事實。

`v6.1.1` 相對舊報告最重要的閱讀修正是 SDD review topology：每個 task 使用一位 fresh task reviewer，該 reviewer 先判斷 Spec Compliance，再判斷 Code Quality；全部 tasks 完成後，另做 broad whole-branch review。高階文件仍可把它稱為 two-stage review，但不應解讀成兩位 task-reviewer agents。

## 作者提供的是什麼

Superpowers 把開發過程拆成三種東西：

- **discipline skills**：例如 design-before-code、TDD、root-cause debugging、verification-before-completion；
- **orchestration skills**：例如 worktree、plans、SDD、inline execution、parallel dispatch、branch finishing；
- **meta skill**：`writing-skills` 用類 TDD 方法驗證新的流程文件是否真的改變 Agent 行為。

它同時提供 supporting prompts/scripts，特別是 SDD 的 task brief、implementer report、review package 和 progress workspace。這些 artifacts 的作用是限制 context、固定 task review range，以及讓 controller 不必把整份 diff 塞回自己的對話 context。

## 建議閱讀順序

1. [方法論與生命週期](./01-methodology-and-lifecycle.md)：先理解整條 control flow。
2. [14 Skills Guide](./02-all-skills-guide.md)：逐一看 failure mode、inputs/outputs、gate 和 production gap。
3. [強項與邊界](./03-strengths-and-boundaries.md)：回答為什麼流程完整仍不等於 production policy。
4. 回到 [兩庫 Workflow 全景](../01-two-libraries-workflow-map.md)和後續 comparison，判斷是否需要 Matt Pocock 的補充能力。

## 按任務跳讀

| 當前任務 | 優先閱讀 |
|---|---|
| 需求模糊、要加 feature | `brainstorming` → `using-git-worktrees` → `writing-plans` |
| 已有 approved plan | `subagent-driven-development` 或 `executing-plans` |
| 有互不依賴的多個 investigation | `dispatching-parallel-agents` |
| 實作 behavior | `test-driven-development` |
| test failure / bug / unexpected behavior | `systematic-debugging` |
| task 或 branch 準備 review | `requesting-code-review` |
| 收到 review feedback | `receiving-code-review` |
| 準備聲稱完成 | `verification-before-completion` |
| tests 已綠、要處理 branch | `finishing-a-development-branch` |
| 要建立/修改自己的 skill | `writing-skills` |

## 14 Skills Inventory

| Lifecycle group | Skills | 核心責任 |
|---|---|---|
| Discovery/design | [`using-superpowers`](./02-all-skills-guide.md#using-superpowers), [`brainstorming`](./02-all-skills-guide.md#brainstorming) | 找到適用流程；把想法變成 approved spec |
| Isolation/planning | [`using-git-worktrees`](./02-all-skills-guide.md#using-git-worktrees), [`writing-plans`](./02-all-skills-guide.md#writing-plans) | 建立乾淨 workspace；把 spec 變成 exact tasks |
| Execution | [`subagent-driven-development`](./02-all-skills-guide.md#subagent-driven-development), [`executing-plans`](./02-all-skills-guide.md#executing-plans), [`dispatching-parallel-agents`](./02-all-skills-guide.md#dispatching-parallel-agents) | fresh-context、inline/checkpoint 或獨立並行執行 |
| Quality control | [`test-driven-development`](./02-all-skills-guide.md#test-driven-development), [`systematic-debugging`](./02-all-skills-guide.md#systematic-debugging), [`requesting-code-review`](./02-all-skills-guide.md#requesting-code-review), [`receiving-code-review`](./02-all-skills-guide.md#receiving-code-review) | behavior proof、root cause、review 和 feedback verification |
| Completion | [`verification-before-completion`](./02-all-skills-guide.md#verification-before-completion), [`finishing-a-development-branch`](./02-all-skills-guide.md#finishing-a-development-branch) | fresh evidence 和明確 branch 決策 |
| Meta | [`writing-skills`](./02-all-skills-guide.md#writing-skills) | 測試並部署可重用的 Agent 流程 |

## Snapshot 限制

本章不根據舊報告推斷當前行為。遇到 upstream update 時，至少重新檢查 `README.md`、所有 changed `SKILL.md`、review prompt、SDD scripts、platform/distribution files，再更新 snapshot facts 和流程判斷。
