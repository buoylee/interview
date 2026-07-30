# Superpowers 的方法論與生命週期

| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
| Primary sources | `README.md`, `skills/using-superpowers/SKILL.md`, `skills/brainstorming/SKILL.md`, `skills/writing-plans/SKILL.md`, `skills/subagent-driven-development/*` |

## 先給結論

Superpowers 的方法論不是「多用幾個 prompts」，而是用一連串禁止過早 transition 的 gates 對抗 Agent 最常見的錯誤：沒讀 skill 就行動、沒理解就寫 code、沒 isolation 就污染工作區、沒 failing test 就實作、沒 root cause 就猜修復、沒 independent review 就批准自己，以及沒 fresh evidence 就宣稱完成。

完整路徑可以濃縮為：

```text
discover applicable skill
  -> approved design
  -> isolated clean workspace
  -> exact implementation plan
  -> choose execution strategy
  -> TDD / evidence-first debugging
  -> task-scoped review and fixes
  -> whole-branch review
  -> fresh verification
  -> explicit branch disposition
```

## Invocation Discipline

`using-superpowers` 把 skill discovery 放在所有 response/action 之前。這個規則的意義不是儀式感，而是避免 Agent 先憑直覺開始，再事後挑一個 skill 為既有行為背書。

合理的判定順序是：

1. 當前情境是否匹配某個 skill 的 trigger？
2. 若匹配，先讀完整正文和必要 reference。
3. 公開說明正在使用哪個 skill 及原因。
4. 按正文的 checklist/gate 執行，而不是只沿用 `description` 摘要。

這也是為什麼 `writing-skills` 強調 `description` 只寫「何時使用」：若 description 預先濃縮 workflow，Agent 可能把它當捷徑而不讀正文。

## Design Before Implementation

`brainstorming` 的 hard gate 很直接：approved design 之前，不得 write code、scaffold 或進入 implementation skill。它要求先探索 project context、逐一釐清、比較 2–3 個 approach、分段呈現 design、寫入 spec、自檢，再由使用者 review written spec。

Terminal transition 固定到 `writing-plans`。這能阻止「邊寫 code 邊決定需求」，但仍要注意兩個邊界：

- approval 證明雙方接受 spec，不證明 spec 已包含 production invariants；
- YAGNI 防止 speculative scope，不等於忽略已知的 failure/rollback/security requirement。

## Isolation and Artifact Flow

`using-git-worktrees` 先偵測 current checkout 是否已是 linked worktree，再考慮 native worktree capability 或 Git fallback。它同時要求 project-local worktree directory 必須被 ignore，以及建立後要做 setup/baseline verification。

Isolation 不是為了「Git 看起來整齊」；它固定三個 review facts：

- task 的 base state；
- 本次變更的 scope；
- 與使用者其他 dirty work 的 ownership boundary。

主要 artifact flow：

| Stage | Artifact | 下一階段依賴它什麼 |
|---|---|---|
| Brainstorm | committed design spec | requirements、decisions、non-goals、approval |
| Plan | implementation plan | exact files、interfaces、steps、commands、expected output |
| SDD setup | task brief | isolated task contract and global constraints |
| Implementer | code commits + report | claims、TDD evidence、changed files、risks |
| Controller | fixed review package | base/head、commits、stat、extended-context diff |
| Reviewer | two verdicts + findings | spec/quality gate、severity、fix direction |
| Ledger | `.superpowers/sdd/progress.md` | task state、deferred Minor findings、durable progress |
| Verification | fresh command output | completion/delivery claim |

## Planning and Execution Strategies

`writing-plans` 要求把 spec 轉成 task-scoped、可獨立 review 的交付單位。Plan 的 Global Constraints 承載跨 task 不變條件；每個 task 的 Interfaces 明確寫 consumes/produces，避免 fresh implementer 只看到自己的 task 時猜錯鄰接名稱或型別。

執行有兩條主要路徑：

- **`subagent-driven-development`**：同一 session 由 controller 調度 fresh implementer/reviewer，隔離 confirmation bias 和 accumulated context。
- **`executing-plans`**：inline 或 checkpoint execution；適合沒有採用 per-task subagent orchestration、或在分開 session 執行既有 plan。

兩者不是品質高低的單一排序。SDD 提供更強的 context/role isolation，但付出更多 model calls、artifacts 和 review latency；inline execution context 連續、成本較低，但 controller 必須更主動防止自我確認。

## v6.1.1 Subagent-Driven Development

`v6.1.1` 的 SDD 先做 plan pre-flight：controller 檢查 task 之間是否矛盾、Global Constraints/Interfaces 是否足以讓 fresh agent 單獨工作。之後每 task 的完整路徑是：

```text
pre-flight plan check
  -> scripts/task-brief writes task-N-brief.md
  -> fresh implementer reads brief and writes implementer report
  -> scripts/review-package fixes BASE_SHA..HEAD_SHA
     and writes commits + stat + extended-context diff
  -> one fresh task reviewer reads bounded artifacts once
  -> Part 1: Spec Compliance verdict
  -> Part 2: Code Quality verdict
  -> Critical / Important findings fixed and re-reviewed
  -> Minor findings recorded in .superpowers/sdd/progress.md
  -> after every task: broad whole-branch review
```

### Task brief

`skills/subagent-driven-development/scripts/task-brief` 從 implementation plan 抽出單一 `Task N`，寫到 `.superpowers/sdd/task-N-brief.md`。Fresh implementer 不需要讀完整 controller history；它收到完整 task text 和全域 constraints。

### Implementer report

Implementer prompt 要求實作者讀 task brief、在 worktree 中實作、測試、commit，並把 report 寫成檔案。Reviewer 對 report 採不信任原則：report 是 claims，不是 evidence；「YAGNI 所以沒做」也不能由實作者自行降低 finding severity。

### Review package

`scripts/review-package BASE HEAD` 把 commit list、stat 和 `git diff -U10` 寫成獨立檔案。使用記錄的 per-task BASE，而不是假設 `HEAD~1`，因此能涵蓋多 commit task。Reviewer 被要求先讀 package，不要重跑無邊界的 Git crawl；只有具體 named risk 才向 diff 外做 focused check。

### One reviewer, two verdicts

`task-reviewer-prompt.md` 的 Part 1 檢查 missing、extra、misunderstood requirements；Part 2 檢查 error handling、edge cases、tests、separation、interfaces 和 file responsibility。這是兩個 ordered logical verdict，當前版本不是兩位 reviewer agents。

### Re-review and final review

Critical/Important findings 修復後必須產生新的 head/review package 再 review。Minor 不消失，而是進 durable ledger，供最後 branch review 看跨 task pattern。全部 tasks 完成後的 broad review負責 task-scoped reviewer不容易看到的整體 integration、compatibility 和 production-readiness風險。

這套機制有效降低 context pollution、diff truncation 和 implementer confirmation bias；它不能彌補 brief/spec 沒寫的 domain facts。

## TDD, Debugging, Review, and Verification Boundaries

四個 quality mechanisms 負責不同問題：

| Mechanism | 防止什麼 | 成功邊界 |
|---|---|---|
| TDD | test-after bias、未證明 test 能抓錯 | test 先以預期原因失敗，再由最小 code 變綠並 refactor |
| Systematic debugging | 猜測式 patch、一次改多個變數 | 可重現、root cause、single hypothesis、regression proof |
| Code review | 實作者盲點、spec miss、maintainability risk | fixed range 上有 evidence 的 findings，並完成 fix/re-review |
| Verification | 用信心或過期結果替代證據 | 對 exact claim 跑 fresh full command 並讀完整 output |

它們不能互相替代：tests green 不代表 spec complete；review approved 不代表 build/test fresh；linter clean 不證明 runtime invariant；debug root cause 不等於 recovery plan。

## Branch Completion

`finishing-a-development-branch` 只在 implementation 完成且 tests 通過後進入。它先偵測 normal repo、named worktree 或 detached externally-managed workspace，再呈現可用的 merge/PR/keep/discard option。

安全重點：

- merge 前後都要驗證；
- PR 路徑保留 worktree 供 feedback iteration；
- discard 要求精確確認；
- 只 cleanup 自己建立、位置可辨識的 worktree；
- remove worktree 前先離開該目錄，成功後再刪 branch。

這個 skill 管的是 Git delivery hygiene，不是 production deploy。

## Cost and Friction

強流程的成本是真實的：更多對話 round、spec/plan 文件、worktree、per-task commits、review packages、review/fix loops 和 final checks。Task 太小時，完整 lifecycle 的固定成本可能高於變更本身。

但縮放方式應是按 risk/applicability 選 task size、review depth 和 optional branches，而不是破壞核心 proof boundary。例如純文案變更可以少用 risk lenses，卻仍應固定 diff 並跑適用的 link/format check；涉及金流、授權、migration 或 concurrency 的 task 則不能因 diff 小就跳過 invariant review。

## What the Workflow Actually Guarantees

在正確遵循且 inputs 完整時，Superpowers 能合理增加：

- design/implementation boundary；
- clean workspace 和 review scope；
- plan/task/interface traceability；
- TDD 和 root-cause discipline；
- role/context isolation；
- task-scoped + branch-scoped review；
- fresh verification evidence；
- 可控的 Git branch completion。

這些都應表述為「提高 assurance」，而不是數學上的絕對保證：Agent、tools、tests 和 human decisions 仍可能出錯。

## What It Does Not Know

Generic workflow 不知道：

- 哪個 business state transition 必須 atomic；
- retry 是否安全，fallback 是否會製造假成功；
- module interface 的穩定 consumer 是誰；
- schema/event/API 的 compatibility window；
- data classification、authorization matrix 和 threat model；
- SLO/capacity/observability/rollback/recovery 的具體值。

因此 production 使用的正確方向是讓 spec/plan/review packet 消費 Core Profile 和 Project Overlay，而不是期待 upstream skill 自行猜出所有規範。
