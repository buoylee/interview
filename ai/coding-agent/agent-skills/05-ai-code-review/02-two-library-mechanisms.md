# 02 - 兩個 Skill 庫的 Code Review 機制

## Source Snapshots

| Source field | Value |
|---|---|
| Library | `obra/superpowers` |
| Local path | `/Users/buoy/Development/gitrepo/superpowers` |
| Pinned snapshot | `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`) |
| Verified | `2026-07-21` |
| Primary sources | `skills/subagent-driven-development/SKILL.md`; `implementer-prompt.md`; `task-reviewer-prompt.md`; `scripts/task-brief`; `scripts/review-package`; `scripts/sdd-workspace`; `skills/requesting-code-review/SKILL.md`; `code-reviewer.md`; `skills/receiving-code-review/SKILL.md` |

| Source field | Value |
|---|---|
| Library | `mattpocock/skills` |
| Local path | `/Users/buoy/Development/gitrepo/skills` |
| Pinned snapshot | `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`) |
| Verified | `2026-07-21` |
| Primary source | `skills/engineering/code-review/SKILL.md` |

以下機制是Descriptive snapshot，不把版本敏感的agent topology、prompt或script行為外推為永久規格。本頁末尾「What This Project Adds」才是本專題定義的Normative增量。

## 先給結論

Superpowers把review嵌入完整execution lifecycle：每task有bounded artifacts、一位fresh task reviewer依序判Spec Compliance與Code Quality，Critical/Important進fix/re-review，Minor帶入durable ledger，全部tasks後再做broad whole-branch review。

Matt `code-review`是standalone two-axis capability：先固定three-dot diff，再讓Standards與Spec concerns在隔離context中獨立產生findings，side-by-side保留，不合併rerank。

兩者都能減少self-review偏誤，但都沒有完整定義本專題需要的production risk lenses、finding evidence lifecycle與go/no-go authority。

## Superpowers v6.1.1 Task Review

Task review不是一個孤立prompt，而是SDD controller維持的artifact protocol。

### 1. Pre-flight plan check

Task 1前，controller一次掃描plan與Global Constraints是否互相矛盾，或plan是否明令要求review rubric視為defect的做法。可預見的conflict先批次交給human裁決，不把同一矛盾拖到每task才發現。

### 2. Task brief and implementer report

`scripts/task-brief PLAN_FILE N`把一個task的完整requirements抽成唯一file。Fresh implementer先讀task brief，收到必要interfaces/decisions與report path；實作、測試、自審後，把詳細claims、tests、files、concerns寫入implementer report，只返回短status。

Implementer report是待驗證claim，不是review verdict。Reviewer prompt明確要求不信任optimistic rationale，並對照diff驗證。

### 3. Fixed review package

Controller在dispatch implementer前記錄BASE，完成後用`scripts/review-package BASE HEAD`建立唯一review package。它包含commit list、stat與full contextual diff；不能用`HEAD~1`取代，否則multi-commit task會被截斷。

Fresh reviewer拿到三個paths：task brief、implementer report、review package，再加binding global constraints。這個packet避免把controller整段session history或巨大diff灌進共享context。

### 4. One fresh task reviewer, ordered verdicts

`task-reviewer-prompt.md`定義的是**一位 fresh task reviewer**。它讀一次task diff，依序輸出：

1. Spec Compliance：missing、extra、misunderstood，以及無法從diff判定的事項；
2. Code Quality：strengths、Critical/Important/Minor findings和task quality verdict。

因此「spec + quality」是同一task review中的兩個logical verdict，不應誤讀成兩位task-reviewer agents。

Reviewer原則上不重跑implementer已跑的suite；只有code引出具名、既有evidence未回答的疑問，才做focused check。它不能crawl整庫，除非有具體cross-cutting risk，例如lock ordering、API contract或shared mutable state。

### 5. Finding resolution and progress ledger

- Critical / Important：dispatch fix，fix report追加covering tests、command和output，再用更新後packet re-review。
- Minor：寫入durable progress ledger，最後whole-branch reviewer需要看到並triage，不能生成後無人讀取。
- `Cannot verify from diff`：controller利用plan/cross-task context自行查證；若是真gap，當failed spec review處理。
- plan-mandated defect：並列finding與plan原文交給human，不因plan authored it就自動降級，也不擅自做違反plan的fix。

`.superpowers/sdd/progress.md`是compaction後的recovery map。`scripts/sdd-workspace`建立workspace；每task clean後，ledger記task、commit range與review state，防止上下文壓縮後重派已完成工作。

## Superpowers Whole-Branch Review

Task-scoped review只看該task requirements與BASE..HEAD。全部tasks完成後，controller使用branch merge-base到HEAD建立完整review package，交給較強的final reviewer做broad whole-branch review。

Whole-branch review的責任是找task-local review難以看見的整合、跨task interaction、整體spec和architecture問題。若有findings，SDD建議一次dispatch一個fix subagent處理完整列表，避免每finding重建context與重跑suite；修復後仍需驗證與re-review。

`skills/requesting-code-review/SKILL.md`與`code-reviewer.md`也支援major feature、pre-merge、stuck、complex bug等時機，要求固定BASE/HEAD、requirements和severity。SDD `v6.1.1`在此基礎上增加task artifacts與final branch package的具體orchestration。

## Superpowers Receiving Review

`skills/receiving-code-review/SKILL.md`把外部feedback視為需要技術評估的suggestion，而不是命令：

```text
READ -> UNDERSTAND -> VERIFY -> EVALUATE -> RESPOND -> IMPLEMENT
```

不清楚的related items先一起clarify；外部建議要對照本codebase、compatibility、既有decision和YAGNI；正確則逐項fix/test，錯誤則用code/tests推回。若與human先前decision衝突，停下裁決。

這補上review reception的常見failure：performative agreement、盲改、一次batch多項卻沒有逐項test，以及reviewer不了解context時仍被當成authority。

## Matt Pocock code-review

Matt的`skills/engineering/code-review/SKILL.md`從使用者給定fixed point開始。沒有fixed point就詢問；先`rev-parse`確認ref、確認diff非空，再固定：

```text
git diff <fixed-point>...HEAD
git log <fixed-point>..HEAD --oneline
```

Three-dot的語義是與merge-base比較，而不是任意兩端snapshot差。接著尋找originating issue/PRD/spec；若使用者確認沒有spec，Spec axis明確skip，不假裝補出需求。

Standards sources來自repository文件；另帶Fowler smell baseline。兩條校準規則很重要：repo documented standard優先於generic baseline；smell永遠是judgment call，且tooling已enforce的事項不重複。

兩個general-purpose subagents平行工作：

- **Standards**：找documented-standard violations與baseline smells，區分hard rule和heuristic。
- **Spec**：找missing/partial requirements、scope creep，以及表面implemented但behavior錯誤的requirements。

Aggregation只把兩份reports放在`## Standards`和`## Spec`下，verbatim或light cleanup。結尾可報各軸finding count與各自worst issue，但不能merge/rerank、不能選跨軸總winner。這讓「code很乾淨但做錯需求」不被style pass掩蓋，也讓「spec做到但破壞repo convention」保持可見。

## Side-by-Side Mechanism Matrix

| Mechanism | Superpowers `v6.1.1` | Matt `code-review` |
|---|---|---|
| Primary role | lifecycle內task gate + final branch gate | standalone fixed-range review capability |
| Candidate | task BASE..HEAD package；最後merge-base..HEAD package | user-supplied fixed-point...HEAD |
| Requirements input | task brief + global constraints + implementer report | originating issue/PRD/spec；可明確缺失 |
| Standards input | reviewer rubric、plan/repo constraints | repo standards優先 + Fowler smell baseline |
| Context topology | 一位fresh task reviewer依序判兩個logical verdict；最後fresh broad reviewer | Standards與Spec subagents平行、context隔離 |
| Aggregation | Spec verdict、severity groups、task quality；controller處理status | 兩軸side-by-side，不跨軸rerank |
| Fix loop | Critical/Important fix + covering evidence + re-review；Minor進ledger | source skill輸出report，未定義完整fix/re-review state machine |
| Cross-task view | explicit final whole-branch review | fixed range可涵蓋整branch，但沒有task-to-final orchestration |
| Feedback reception | 獨立`receiving-code-review`要求verify再implement | source skill停在aggregated report |
| Delivery authority | 有proceed/finish discipline，但仍依human/project decisions | 不宣稱總winner或merge decision |

## Guarantees and Non-Guarantees

### Superpowers增加的保證

- task requirements、implementer claims和candidate diff分離；
- fresh reviewer不繼承implementer完整history；
- spec與quality都必須有verdict；
- Critical/Important不應帶病進下一task；
- Minor與progress在compaction後仍有durable record；
- task-local pass後還有whole-branch integration視角。

它不保證task brief已包含domain invariant、review rubric涵蓋所有production risk、test report真實完整，或human永遠做出正確trade-off。

### Matt增加的保證

- fixed point先驗證、three-dot diff range明確；
- Spec與Standards不互相mask；
- repo-specific standards勝過generic smell；
- 缺spec時明確降級，不偽造source；
- 不以跨軸總分製造false confidence。

它不保證findings有統一severity/confidence/evidence status，也沒有原生定義security、reliability、performance、operability等applicability lenses與fix/re-review gate。

### 共同邊界

兩者都只能review收到的candidate和policy。Fresh context不能補出未提供的transaction boundary；parallel reviewers不能證明tests的oracle正確；更多findings不等於更好decision。

## What This Project Adds

本專題定義的Normative增量不是第三套generic review，而是補齊delivery contract：

1. 固定八階段loop：preflight、deterministic checks、independent axes、finding verification、aggregation without masking、fix、re-review、go/no-go；
2. 四個core axes與按applicability啟用的production risk lenses；
3. structured finding fields，明確分開severity、confidence、evidence和status；
4. 沒有足夠evidence時標needs-verification，不以語氣冒充fact；
5. unresolved blocking finding、accepted risk authority與re-review freshness成為merge gate；
6. executable fixtures用hidden oracle測試reviewer能否找出visible tests漏掉的production defect。

這些規則會在下一交付階段建立；在那之前，本頁只作upstream mechanism的source-backed boundary。
