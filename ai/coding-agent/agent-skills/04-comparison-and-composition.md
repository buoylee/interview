# 04 - Superpowers 與 Matt Pocock Skills：差異與組合

## 先給結論

兩個庫不是「誰比較完整就全用誰」的單選題，也不是把所有 skill 串起來就更安全：

- **Superpowers** 是較強的 end-to-end lifecycle 與 gate system，適合做 primary delivery methodology。
- **Matt Pocock Skills** 是較可組合的 engineering toolset，強在 interrogation、artifact transformation、domain modeling、codebase design、fixed-base review 與 handoff。
- **兩者都不是完整的 production policy**。它們能規範 Agent 怎麼工作，不能憑空知道本專案的 transaction、idempotency、SLO、security、migration 與 recovery semantics。
- **組合的原則是補責任缺口，不是疊加所有 gate**。先選一個 primary lifecycle，再只加入它欠缺的能力。

> **本專題判斷**：多跑一個 skill 只有在增加新的 decision、artifact、independent evidence 或 enforcement boundary 時才有價值；若只是用不同措辭重做同一個 stage，增加的是成本與衝突面。

本頁比較固定在以下本地 source snapshots：

- Superpowers `d884ae04edebef577e82ff7c4e143debd0bbec99`（`v6.1.1`）
- Matt Pocock Skills `ed37663cc5fbef691ddfecd080dff42f7e7e350d`（`v1.1.0-40-ged37663`）

## Comparison Matrix

| 比較軸 | Superpowers | Matt Pocock Skills | 選擇含義 |
|---|---|---|---|
| Complete methodology / toolset | 14 個 skills 形成從 discovery 到 branch finishing 的 opinionated lifecycle | 41 個 snapshot skills 是可選、可獨立使用的 capability collection | 要統一團隊 delivery flow，Superpowers 更直接；要精準補一種能力，Matt 更靈活 |
| Control | 用強 trigger、MUST、approval、verification 與 completion gate 約束 transition | 使用者主導何時 grill、轉 spec、拆 tickets、implement、review 或 handoff | 前者降低跳步，後者降低流程綁定 |
| Invocation | 大量 model-invoked discipline，加上由 workflow 明示的下游 skill | README 區分 user-invoked orchestration 與 model-invoked discipline | host 能否 discovery、載入與執行，會直接影響實際強制力 |
| Artifact flow | approved spec、plan、task brief、implementer report、review package、progress file、verification evidence | conversation、glossary/ADR、spec、tickets、fixed-base diff reports、temporary handoff | Superpowers 更像固定 typed pipeline；Matt 更像可重組 artifact transformers |
| Context isolation | worktree、fresh implementer、fresh task reviewer、whole-branch reviewer，或 inline checkpoint | fresh Standards/Spec reviewers、每 ticket fresh context 建議、handoff 給下一個 Agent | 兩者都降低 confirmation bias，但 isolation topology 不相同 |
| Quality loops | TDD、systematic debugging、task/branch review、feedback verification、fresh completion verification | seam-first TDD、six-phase diagnosis、Standards/Spec review、domain/design vocabulary | Superpowers 的 gate coverage 較完整；Matt 的 review/design切面更細 |
| Domain / design support | brainstorming 與 planning 可消費專案資訊，但沒有獨立 domain/design vocabulary skill | `domain-modeling`、`codebase-design`、`prototype`、architecture improvement 是明確能力 | domain words、interface seams 或 codebase entropy 是主風險時，Matt 能補洞 |
| Customization | 透過 project instructions、plan、review inputs 與自製 skills；偏方法論一致性 | setup docs、tracker vocabulary、獨立 skills 與自由 composition；偏局部採用 | 兩者都應優先加 local policy，不要先 fork upstream |
| Production coverage | 強 evidence discipline，但不自帶 project invariants、risk budgets、deploy/recovery policy | 能改善 vocabulary、seams 與 review，但同樣不自帶 production facts | production-ready 必須另外提供 Core Profile、Project Overlay 與 executable evidence |
| Cost and friction | 多 gate、worktree、fresh contexts、task/branch review，對大變更較值得 | 可只選一個 skill，但人工 routing 與 artifact continuity 更依賴使用者 | task 越小，越應縮短流程；風險越高，越值得增加 independent evidence |

## Methodology vs Composable Toolset

Superpowers 的基本單位不是「一個很好用的 prompt」，而是受 gate 約束的 state transition：

```text
idea
  -> approved design
  -> isolated workspace
  -> executable plan
  -> implementation tasks
  -> task review
  -> whole-branch review
  -> fresh verification
  -> explicit branch decision
```

因此它特別適合回答「Agent 容易在哪一步跳過必要工作」：還沒理解就 coding、沒有看到 RED、修 bug 靠猜、接受 review 不驗證、用舊 output 聲稱完成。

Matt 的基本單位更像有窄 responsibility 的 transformer 或 discipline：

```text
conversation --to-spec--> durable spec
spec --to-tickets--> tracer-bullet graph
fixed base + standards + spec --code-review--> two reports
current state --handoff--> fresh-agent context
```

因此它特別適合回答「現在缺哪一種認知或 artifact」：要 challenge assumptions、統一 domain language、選 interface seam、把討論固化、把工作拆成 tickets、做兩軸 review 或跨 session 接續。

> **本專題判斷**：如果團隊缺的是一致 delivery lifecycle，先採 Superpowers；如果已經有成熟 lifecycle，只缺特定 engineering capability，直接選 Matt 的窄 skill。

## Invocation and User Control

Skill file 寫了什麼，與它何時真的被執行，是兩個問題。

Superpowers 的 `using-superpowers` 要求先檢查適用 skills，其他 skills 又用 trigger 和 hard rule 銜接。例如 creative work 先 brainstorm、bug 先 systematic debugging、完成主張前先 fresh verification。這提高預設一致性，但也要求 harness 正確 discovery 並遵循 workflow-required transition。

Matt 把 orchestration 更多留給使用者。`ask-matt` 只做 routing；`grill-with-docs`、`to-spec`、`to-tickets` 等可依工作形狀組合。這能避免一套 methodology 壟斷所有 task，但使用者必須知道當前缺口，並維持 artifacts 之間的 continuity。

實際控制力由四者共同決定：

1. host/system instructions；
2. skill 的 trigger 與正文；
3. repository instructions 與 artifacts；
4. tool permissions 和真正可執行的 checks。

只把 `SKILL.md` 放進目錄，不代表 Markdown 裡的 MUST 已成為 runtime enforcement。

## Artifact Flow and Context Hygiene

Superpowers 偏向先定義 execution topology，再固定每個角色收到的 packet。`v6.1.1` SDD 中，fresh implementer 收 bounded task brief；fresh task reviewer讀 task brief、implementer report 和固定 BASE..HEAD review package，依序給出 Spec Compliance 與 Code Quality verdict；最後再做 whole-branch review。

Matt 偏向先定義 artifact 的用途：

- `CONTEXT.md` 保存精確 glossary，不拿來塞整份 spec；
- `to-spec` 把已討論內容合成 durable specification，不重新展開訪談；
- `to-tickets` 形成可獨立抓取的 vertical slices 和 blocking edges；
- `code-review` 固定 three-dot diff，將 Standards 與 Spec 分開；
- `handoff` 把當前狀態壓成 temporary artifact，讓 fresh Agent 接續。

Fresh context 解決的是記憶污染和 self-approval，不解決 input completeness。Reviewer 若沒有 Project Overlay、originating spec 或 exact diff，再獨立也只能對缺失資料做推測。

## TDD, Debugging, Review, and Verification

| 能力 | Superpowers 的重點 | Matt 的重點 | 不應誤解成 |
|---|---|---|---|
| TDD | 強制看見正確原因的 RED，再 minimal GREEN、REFACTOR | 先與使用者確認 public seam，再做 vertical red-green slices；refactor 留到 review stage | tests 綠就代表需求與 production risks 完整 |
| Debug | reproduce、pattern、hypothesis、experiment、implementation 的 root-cause discipline | 先建立 tight red-capable command，再經最小化、假設、instrumentation 等六階段 | 看見 error 就直接改最可疑的 code |
| Task review | execution lifecycle 內的一位 fresh reviewer先後判 Spec Compliance、Code Quality | standalone `code-review` 以 Standards 與 Spec 兩個 independent subagents 分軸輸出 | 同名「兩階段／兩軸」就是相同 agent topology |
| Feedback | `receiving-code-review` 要先技術驗證，不做表演式同意 | findings side-by-side 保留來源責任，不跨軸 rerank | 每條建議都應照單全收 |
| Completion | `verification-before-completion` 要求 fresh command output；branch finishing 處理整合選擇 | `implement` 要 final full suite + review + commit，但 standalone skills 不構成完整 merge gate | review 完就可以宣告可上 production |

兩庫原生 review 的共同缺口是 production finding contract：如何表示 evidence、confidence、severity、verification status，哪些 risk lens 必須適用，誰可接受 exception，以及 Critical/Important 修復後如何 re-review。這些責任應由本地 review protocol 補上，不該假設 generic reviewer能自行推導。

## Domain Language and Codebase Design

Matt 的 `domain-modeling` 與 `codebase-design` 是最值得補進 Superpowers 主線的能力之一，因為它們提供了較精確的思考語言：

- fuzzy/overloaded terms、concrete scenarios、invariants；
- Module、Interface、Depth、Seam、Adapter、Leverage、Locality；
- public behavior test seam 與 dependency direction；
- `CONTEXT.md` glossary 和少量符合條件的 ADR。

但 vocabulary 不等於 policy。即使 Agent 正確說出「idempotency」，仍要由專案回答：key scope 是 account、order 還是 request？retention 多久？同 key 不同 payload 是 conflict 還是 replay？寫入與 response cache 是否在同一 transaction？

Superpowers 的 brainstorm/spec/plan 可以消費這些答案並建立 gate；Matt 的 foundation skills可幫助把答案問清楚、放到穩定 artifact。兩者在這裡是上下游，不是互斥替代。

## Production Coverage and Gaps

覺得 skill 產出的 code 不夠「生產等級」，不一定是 skill 失效，也不全是作者故意省略。要分三種情況：

| 原因 | 表現 | 正確處理 |
|---|---|---|
| Deliberate scope | TDD 只寫 minimal GREEN；prototype 明確無 tests、persistence、error handling；YAGNI 不做未批准抽象 | 尊重該 stage 的目的，在 production path 的後續 gate 補齊，不把 prototype直接 merge |
| Information boundary | Skill 不知道 consistency、fallback、capacity、compatibility 或 recovery fact | 把事實寫進 Project Overlay/spec，不能要求 Agent「縝密一點」自行猜 |
| Acceptance boundary | Spec/tests只覆蓋 happy path，review也沒有 risk lenses | 擴充 acceptance/evidence，讓 review gate 對明確規則負責 |

Generic skills可以促進封裝、可讀性、復用、面向 interface 和解耦，但不能把這些詞當無條件目標：

- 多一層 abstraction 可能降低 locality；
- 為單一 implementation 建 interface 可能只是 indirection；
- fallback 若語義錯誤，會把 hard failure 變成 silent data corruption；
- retry 若沒有 idempotency，會放大 side effect；
- eventual consistency 若沒有 reconciliation，不能只靠一句「最終會一致」；
- reusable API 若沒有 compatibility policy，只是擴大 change surface。

Production quality 應表達為：

```text
universal baseline
  + project-specific invariants
  + executable evidence
  + delivery gate
```

## Cost, Friction, and Task Size

流程成本應跟 change risk 與 uncertainty 成比例，而不是跟作者提供多少 skills 成比例。

| 變更形狀 | 合理流程 | 不成比例的做法 |
|---|---|---|
| 一行 typo、無 behavior change | repo-required checks + focused diff review | 為它建立完整 spec、tickets、prototype與多輪 agents |
| 小而明確 behavior fix | fixed requirement + TDD + focused review + fresh verification | 重跑兩套 brainstorm/spec/review的同義 stages |
| 一般 feature | approved design + isolated execution + task review + branch verification | 每個可選 skill 全部串接 |
| 資料、支付、權限、migration 等高風險 change | Project Overlay + failure design + independent review lenses + rollout/rollback evidence | 只因 unit tests綠就縮短 gate |
| 未知 UI/state/design choice | bounded throwaway prototype後回到正式 lifecycle | 把 production abstraction、tests和observability先加進 prototype |

Fresh agents、worktrees、full suites 與 broad review 都有時間/context成本；省略它們也有 defect與返工成本。決策應基於 blast radius、reversibility、unknowns、regulatory/security impact 和 evidence cost。

## Minimal Sufficient Compositions

以下是「最小充分」參考，不是每個 repository 的硬編排。

### Normal Feature

```text
Primary: Superpowers
brainstorming -> using-git-worktrees -> writing-plans
-> SDD or executing-plans -> TDD/task review
-> whole-branch review -> verification -> branch decision

Optional Matt additions:
domain-modeling only when vocabulary/invariants are unclear
codebase-design only when a seam/interface decision is material
```

為一般 feature 不必再跑 Matt 的整套 grill/spec/tickets；只有 Superpowers spec/plan 欠缺的 artifact能力才補。

### Production-Critical Feature

```text
Primary: Superpowers lifecycle
+ Matt domain-modeling / codebase-design where applicable
+ local Project Overlay and explicit risk lenses
+ failure, migration, capacity, observability, rollback evidence
+ independent fix/re-review and human go/no-go
```

這裡增加的不是更多同義 prompts，而是 project facts、risk-specific evidence 和 approval authority。

### Bug Diagnosis

```text
Choose one diagnosis loop:
systematic-debugging OR diagnosing-bugs
-> regression test at the correct public seam
-> minimal fix
-> focused fixed-base review
-> fresh verification
```

不要同時逐字執行兩套 diagnosis phases。若 production incident需要跨 session，才補 Matt `handoff`；若修復進入 Superpowers execution plan，就回到其 review/completion gate。

### Architecture Improvement

```text
Matt improve-codebase-architecture
-> visual candidates + user grilling + selected boundary
-> domain-modeling / codebase-design
-> approved narrow spec
-> Superpowers worktree + writing-plans + execution/review/verification
```

前半段找值得改的 architecture problem，後半段把已批准範圍當正常 production change交付；不可把探索報告直接授權成全面 refactor。

## Conflict Resolution Rules

當兩個 skills、repo instructions 或已批准決策互相衝突時，按以下優先序處理：

1. system/tool/safety boundary 與使用者明確授權；
2. repository 的明確 project instructions，以及使用者已接受的 spec/ADR/decision；
3. 本次選定的 primary lifecycle；
4. 為填補特定缺口而加入的 optional helper skills；
5. generic style preference 或未被專案採納的建議。

若上層規則與下層 helper衝突，下層不得靜默覆蓋。應指出衝突、保留 primary lifecycle 的 transition，必要時請使用者決定。

常見例子：

- Superpowers 的 plan已是 approved execution artifact時，不再讓 `to-spec` 改寫需求；新發現先回報並修改 canonical artifact。
- 選擇 Matt fixed-base review時，可把報告餵給 Superpowers feedback loop，但不必再做一份同範圍、同責任的 task review。
- Matt `tdd` 把 refactor 留到 review stage；若 primary lifecycle要求 RED-GREEN-REFACTOR，保留 primary loop，但仍需 public seam與behavior-first原則。
- prototype 的「無 production hardening」只適用 throwaway branch；進入正式 lifecycle後，以 production acceptance為準。

## When Not to Combine Them

以下情況應只用一套或一個 skill：

- 現有團隊 lifecycle 已固定，只需單一 `handoff`、`domain-modeling` 或 `code-review` 能力；
- 小 change 的第二套流程不會產生新 evidence；
- 兩套 skills 對同一 artifact有不同 owner，會造成 spec/plan/ticket 多個 truth sources；
- 同一 diff 被多個 generic reviewers重複掃描，卻沒有 security、reliability或domain專門 lens；
- task正處於 incident response，增加 orchestration 反而延遲重現與 containment；
- harness不支援某 skill依賴的 subagent、worktree或tracker能力。

當流程重疊時，先刪除沒有新增責任的 stage；當 production coverage不足時，加入具體規則與 evidence，不是加入更多泛化 reviewer。

## 一句話總結

用 Superpowers 管完整交付生命週期，用 Matt Pocock Skills 精準補 domain、design、artifact、review 或 handoff能力；再用本地 production policy定義什麼不能錯、如何證明，以及誰能放行。
