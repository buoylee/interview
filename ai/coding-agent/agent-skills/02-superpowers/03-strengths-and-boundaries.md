# Superpowers 的強項與邊界

| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
| Primary sources | `README.md`, all 14 `SKILL.md`, SDD prompts/scripts, code-reviewer prompt |

## 先給結論

Superpowers 很擅長把「Agent 容易偷步」轉成 process gate；它不是一份全產業、全 domain 通用的 production standard。你感受到的資料一致性、兜底、封裝、可讀性、複用、interface orientation、decoupling 等缺口，有一部分是刻意的 YAGNI/minimal implementation，更多是 generic workflow 不可能替專案決定的 policy/invariant boundary。

> **本專題判斷**：正確做法通常是保持 upstream 可升級，讓 Superpowers 管 workflow，再用 Core Profile、Project Overlay、executable evidence 和 review gate提供 production facts；不是先 fork 全部 skills。

## 它刻意強化的 Failure Modes

| Failure mode | Superpowers 的控制 |
|---|---|
| 未判斷適用 skill 就行動 | `using-superpowers` 把 discovery 前置 |
| 需求未決就 implementation | `brainstorming` approval hard gate |
| 污染 dirty checkout | `using-git-worktrees` isolation/baseline |
| Plan 太抽象、fresh agent只能猜 | `writing-plans` exact files/interfaces/commands |
| 長 context和自我確認 | fresh implementer/reviewer、bounded artifacts |
| Test-after 偏差 | TDD 必須先看到正確 RED |
| 猜測式修 bug | systematic root-cause/hypothesis phases |
| Review object飄動 | fixed base/head 和 diff package |
| 盲目接受 review | receiving-review technical verification |
| 用自信冒充完成 | fresh verification gate |
| 誤刪/誤合 branch/worktree | provenance-aware branch finishing |
| Skill 未經行為測試就部署 | writing-skills 的 RED-GREEN-REFACTOR |

## 它提供的 Workflow Guarantees

當使用者、host 和 Agent 都遵循契約時，可以合理期待：

- 重大 design decision 有 durable spec，而不是只留在 conversation；
- implementation 以隔離 workspace 和明確 base 開始；
- task 有可交接的 inputs/outputs 和 verification command；
- behavior change 先證明 test能失敗；
- bug fix 連到 root cause和 regression evidence；
- task review與whole-branch review有不同 scope；
- implementer claims、diff evidence和review verdict分離；
- completion claim對應當下 command output；
- branch disposition是明確 human decision。

這些保證的本質是降低 process variance 和已知 Agent anti-pattern，不是保證「零缺陷」。

## 它不提供的 Project Facts

Generic skill 無法替專案回答：

| Area | 必須由專案提供的 facts |
|---|---|
| Data consistency | source of truth、transaction boundary、isolation、atomicity、讀寫可見性、constraint/reconciliation |
| Concurrency | competing writers、lock/version strategy、ordering、lost-update policy |
| Idempotency | key scope、payload conflict、retention、dedupe store、crash window、external side effect semantics |
| Resilience | total time budget、per-attempt timeout、retry/backoff、circuit/backpressure、fallback meaning |
| Interfaces | stable consumer、public surface、dependency direction、compatibility ownership |
| Security/privacy | actor/permission matrix、data classification、retention/redaction/deletion、threat model |
| Performance | SLO、capacity/load shape、queue/pool bounds、resource budget |
| Operations | signals、alert owner、runbook、rollout、rollback、recovery、RPO/RTO |

若這些 facts 不在 spec、repository instructions 或 Overlay，Agent主動補值反而可能是危險的幻覺。

## 為什麼輸出仍可能不像 Production Code

### Data consistency

TDD 只會驅動已寫下的行為。若 spec只寫「transfer money」而沒有「失敗時不得留下 partial debit」「concurrent requests不得 lost update」，最小實作可能通過 happy-path test卻破壞守恆。這不是 TDD證明了錯誤，而是 test oracle缺少 invariant。

### Timeout、retry 與 fallback

Workflow 鼓勵 error handling，但 generic rubric不知道 dependency budget和fallback業務語義。隨意加 retry可能重複扣款；回傳空物件可能把 outage偽裝成正常空資料。真正要求應包含 budget、idempotency、retry exhaustion、degraded state和operator signals。

### Encapsulation、interface orientation 與 decoupling

Superpowers reviewers會看 separation、interface和file responsibility，但 plan若只要求某 concrete repository，minimal code可能直接依賴其內部 shape。是否抽 interface取決於穩定 consumer seam、替換需求、testability和dependency direction，不能用「所有 class都要 interface」取代設計。

### Readability、reuse 與 abstraction

TDD 的 GREEN刻意要求 minimal code，REFACTOR才改善命名/重複。YAGNI反對預測性 framework，因此第一版不一定有你期待的泛化層。Production要求應是 cohesive、可理解、可測、policy不重複；不是 abstraction越多越好。過早複用也會把錯誤邊界鎖死。

### Compatibility、migration 與 recovery

Task-scoped diff很容易只看到新 schema/API的本地 correctness。Mixed-version rollout、backfill/restart、old consumer、data rollback和forward recovery需要 project-specific plan與 rehearsal output。Generic code review不會自動知道 consumer inventory。

## Code Review 的實際覆蓋

Superpowers `v6.1.1` 有三個互補層次：

1. **Task reviewer**：bounded task brief/report/diff；先 spec，再 quality。
2. **Whole-branch reviewer**：所有 tasks後看 integration、broader regression與production readiness。
3. **Receiving review**：controller/implementer驗證 feedback，再逐項 fix/re-review。

這比單次 self-review 強，但仍有明確限制：

- reviewer看到的是 packet，不是完整 runtime；
- task reviewer刻意避免無界 codebase crawl和重跑重型 suite；
- generic code-quality questions不等於 project risk lenses；
- severity calibration依賴已知 impact；
- 無 evidence finding仍需驗證，不能因模型語氣強就 block。

因此 production AI review 還需要固定四軸、條件 risk lenses、structured finding contract、evidence verification和go/no-go policy。

## 適合與不適合的任務

適合：

- requirements仍需收斂的 feature；
- 有多 task、需要隔離和review traceability的變更；
- 容易出現 test-after或猜測修復的 bugfix；
- 需要可靠 handoff和fresh verification的長任務；
- 希望把個人習慣轉成可重複methodology的團隊。

需要縮放或改用局部 skill：

- 純 read-only explanation；
- 一行 mechanically verifiable的文件/設定變更；
- 強 shared-state、無法切 task boundary的探索；
- throwaway prototype（仍需 human確認它真的是throwaway）；
- incident emergency中的即時止血——可以縮短artifact，但root cause、risk和follow-up不能永久省略。

## 如何加本地規範而不 Fork

使用以下決策順序：

```text
只屬於一個 project 的具體值/不變量
  -> Project Overlay

跨 project 都應成立的品質義務
  -> Core Profile

反覆需要相同 review packet / finding schema / gate
  -> thin wrapper or orchestration skill

upstream trigger / hard gate / artifact contract / flow order 根本不相容
  -> 評估 fork
```

Wrapper 應引用 upstream skill並注入 artifacts，不要複製整份正文。Fork 的代價包括 source drift、merge/rebase、重新測試、distribution和使用者不知道哪份才是 canonical。

## 一句話總結

Superpowers 故意把「怎麼工作」做得很強，卻不假裝知道「你的 production 系統到底什麼不能錯」；要補的是明確 project policy和evidence，不是把所有上游 skill無差別加長。
