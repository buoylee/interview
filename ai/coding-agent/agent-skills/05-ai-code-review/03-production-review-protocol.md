# 03 - Production AI Code Review Protocol

## Policy Status

本頁是本專題定義的Normative protocol，不是對Superpowers或Matt Pocock source的描述。它可以疊在任一primary lifecycle上，前提是controller能固定candidate、提供project facts、保存finding state並執行go/no-go。

Protocol的目標不是保證AI永不漏錯，而是讓每個review claim可追溯、可驗證、可駁回、可修復，並防止沒有evidence的「approved」進入delivery gate。

固定核心review axes：

1. **Spec Compliance**；
2. **Correctness and Domain Invariants**；
3. **Architecture and Maintainability**；
4. **Test Quality**。

按變更applicability啟用risk lenses：

- Security；
- Reliability and Fallback；
- Performance and Capacity；
- Observability and Operability；
- Data Migration and Compatibility。

## Preconditions and Abort Conditions

開始前必須有可resolve的repository、read-only reviewer環境、candidate owner、delivery authority和finding ledger。

| Abort condition | 必須停止什麼 | 可恢復條件 |
|---|---|---|
| Missing/empty diff | 停止全部semantic review | 重新產生非空candidate diff |
| Unknown/unresolvable review base | 停止全部review；不得猜`HEAD~1` | 明確fixed point或merge-base並記錄SHA |
| Missing spec/acceptance criteria | 停止Spec Compliance verdict；不得聲稱spec pass | 找到canonical spec，或owner明確宣告此change無Spec axis並接受scope limitation |
| Missing invariant for a consistency claim | 該claim只能是needs-verification，不得宣告consistency pass/fail | domain owner提供invariant、state transition和acceptable window |
| Stale deterministic evidence | 停止go/no-go；舊output只作歷史資料 | 對當前HEAD重新執行applicable checks |
| Failed applicable deterministic check | 停止go；可繼續diagnostic review | 修復後在當前HEAD得到pass evidence |
| Missing required Overlay/risk boundary | 停止受影響lens的pass verdict與delivery decision | project owner補齊fact或明確接受unknown risk |

Abort不等於刪除已完成分析。其他independent axes可繼續產生diagnostic findings，但報告必須標示哪個verdict unavailable，controller不能把partial review包裝成overall pass。

## Stage 1: Preflight

Controller執行：

1. resolve fixed point/merge-base與HEAD，記錄full SHA；
2. 確認commit range、diff非空、working-tree/index狀態符合review scope；
3. 定位originating issue/spec、acceptance criteria、ADRs、repo instructions、Core Profile和Project Overlay；
4. 宣告changed data、interfaces、compatibility、operations與rollout boundaries；
5. 根據change surface判斷五個risk lenses是否applicable，未啟用者記理由；
6. 建立finding ledger與delivery authority；
7. 檢查candidate之後是否會被generator或formatter改寫，避免review stale artifact。

Preflight產物是candidate manifest，不是自然語言「請review最新修改」。

## Stage 2: Deterministic Checks

先執行repository實際適用的mechanical checks，對當前HEAD保存command、exit code、timestamp/runtime context和完整或可定位output：

- tests；
- typecheck / compile；
- lint / format check；
- build / package verification；
- dependency/security scan；
- schema、migration、contract或compatibility check；
- generated-artifact freshness check。

不是每個change都要跑所有工具；`not-applicable`必須有scope理由。不能用「CI之後會跑」代替required pre-review evidence，也不能把failed check藏在大段log後仍dispatch reviewer尋求pass。

Deterministic checks處理已編碼規則，semantic reviewer應專注於工具不知道的requirements、invariants、execution paths和risk semantics。

## Stage 3: Build the Review Packet

每個reviewer收到同一candidate truth，再加自己axis所需的bounded context。Required packet：

| Packet component | Required content |
|---|---|
| Candidate identity | merge-base/fixed point SHA、HEAD SHA、commit list、diff stat、full contextual diff |
| Requested behavior | originating spec/issue、user stories、acceptance criteria、explicit out-of-scope |
| Project authority | repository instructions、relevant ADRs、applicable Core Profile rules、Project Overlay facts |
| Fresh evidence | 當前HEAD的test、typecheck、lint、build、security、migration outputs中實際適用者 |
| Data boundary | records/state touched、transaction/consistency/idempotency/concurrency/reconciliation facts |
| Interface boundary | public APIs/events/schemas/modules、consumer/producer、compatibility window與versioning |
| Operational boundary | dependencies、timeouts/retries/fallback/backpressure、SLO/capacity、telemetry、runbook |
| Delivery boundary | deploy sequence、migration order、feature flag、rollback/forward recovery、blast radius |
| Implementer claims | change summary、known concerns、test rationale；明示為untrusted claims |
| Reviewer contract | assignedaxis/lens、finding schema、severity calibration、read-only與scope rules |

Packet應以files/immutable artifacts交接，避免controller conversation污染reviewer，也避免把同一巨大context重貼多次。Secret、credential和不必要personal data必須redact。

## Stage 4: Dispatch Independent Review Axes

四個core axes都要有logical verdict；可由多個fresh reviewers平行負責，也可由一位fresh reviewer按順序輸出，但concerns和findings不能合併成模糊總評。

### Spec Compliance

檢查missing、partial、misunderstood、scope creep、acceptance mismatch。只引用canonical spec/decision，不把reviewer preference偽裝成requirement。

### Correctness and Domain Invariants

追蹤state transition、data ownership、transaction boundary、concurrency、idempotency、ordering、failure/recovery，確認每條applicable invariant有可執行或可查證evidence。

### Architecture and Maintainability

檢查module responsibility、interface depth、dependency direction、encapsulation、locality、coupling、duplication、readability、change surface。抽象與reuse必須對應真實variation/consumer，不以「更professional」為理由增加indirection。

### Test Quality

檢查test seam、independent oracle、RED capability、failure/replay/concurrency scenarios、assertion strength、environment parity和test isolation。Tests pass只是input，不是此axis的自動pass。

### Applicable risk lenses

Risk lens只在有明確applicability時加入，並消費相應Overlay facts。若change碰authorization就啟用Security；碰remote dependency就啟用Reliability/Fallback；碰hot path或resource就啟用Performance/Capacity；改runtime failure mode就啟用Observability/Operability；改persistent schema/API/event就啟用Migration/Compatibility。

## Stage 5: Verify Findings

Reviewer輸出的每一項先是claim。Controller/verifier逐項檢查：

1. location是否在candidate或具名cross-cutting path；
2. rule是否真的applicable且有authority；
3. execution path是否reachable；
4. impact是否由evidence支持，而非只靠可能性語氣；
5. severity與confidence是否分開校準；
6. verification是否是可執行、最小且能推翻claim的方法。

可直接從diff/source證實的finding進`open`；需要focused test、unchanged call site、runtime fact或domain decision的finding維持`needs-verification`。Verification可證實、降級、駁回或發現更大scope，但不得因查證麻煩就靜默刪除。

## Stage 6: Aggregate Without Masking

Aggregation可以：

- 合併完全相同root cause的duplicates，保留所有來源lens；
- 建立finding dependency和共同fix方向；
- 統一location格式與verification command；
- 按severity、status和affected boundary排序。

Aggregation禁止：

- 把不同axes做平均分；
- 用多數pass抵消一個Critical；
- 因generic reviewer沒看到就刪除specialist finding；
- 把confidence低等同severity低；
- 把needs-verification當false positive；
- 為縮短報告只保留「最有趣」的findings。

每個axis/lens保留自己的verdict與coverage limitation；overall gate只讀blocking state，不產生虛構quality score。

## Stage 7: Fix and Re-review

Verified Critical/Important按dependency安排fix。Fix dispatch包含finding IDs、rules、expected evidence和covering commands，不直接把reviewer建議當唯一implementation design。

Implementer對每批fix：

1. 修改最小充分scope；
2. 執行covering tests/checks並保存fresh output；
3. 更新implementer report與new HEAD；
4. 不自行把status改成`verified`。

Fresh re-reviewer或原獨立review role檢查new candidate：原finding是否消失、evidence是否對應當前HEAD、fix是否引入regression/scope creep，以及相關risk lens是否需要擴張。Fix後尚未re-review的finding保持`fixed`，不能視為closed；re-review通過才進`verified`。

## Stage 8: Go / No-Go

Severity永不平均。**Go**同時要求：

- 所有applicable deterministic checks對當前HEAD passing；
- zero unresolved Critical findings；
- 每個Important finding已verified fixed，或由authorized human明確accepted-risk；
- changed findings都有re-review evidence；
- required axis/lens verdict可用，coverage limitation已揭露；
- rollout、rollback/forward recovery與observability evidence符合Project Overlay；
- candidate自最後evidence後沒有再改動。

任一條不成立即**No-Go**或明確`decision pending`。Minor不阻擋，但保持可見並由owner決定ledger/follow-up；accepted risk不是pass同義詞，必須有human authority、reason、scope、expiry和mitigation。

## Finding Contract

每個finding只使用以下11個fields：

| Field | Contract |
|---|---|
| `id` | 穩定唯一ID，跨fix/re-review不改名 |
| `lens` | 產生finding的core axis或applicable risk lens |
| `severity` | `Critical`、`Important`或`Minor` |
| `confidence` | `high`、`medium`或`low`，描述claim可信度，不改變impact |
| `location` | 可定位file:line/hunk/symbol；cross-cutting時列primary path |
| `rule` | canonical spec、ADR、Core rule、Overlay fact或明示review rule |
| `impact` | 對user/data/security/reliability/maintainability/delivery的具體後果 |
| `evidence` | diff/source/test/trace/log等目前支持claim的可重現資料 |
| `direction` | 修復目標與constraint，不強迫未驗證patch設計 |
| `verification` | 能證實修復或駁回claim的focused procedure/command |
| `status` | `needs-verification`、`open`、`disputed`、`accepted-risk`、`fixed`或`verified` |

不得增加自由欄位讓不同reviewers各自發明schema；補充背景放在field內容或finding外的packet metadata。

Allowed status transitions：

```text
needs-verification -> open | disputed
open -> fixed | disputed | accepted-risk
disputed -> open | accepted-risk
fixed -> verified | open
```

`verified`表示re-review已確認問題解決；不是「finding原本是真的」。被證據駁回的claim不進delivery ledger，可在evaluation record標為false positive。

## Severity and Confidence Calibration

| Severity | Definition | Gate effect |
|---|---|---|
| `Critical` | credible path to data loss/corruption、security boundary violation、irreversible incompatibility或unbounded severe outage | always blocks；不可由Agent接受risk |
| `Important` | correctness、resilience、maintainability或evidence gap使change不可信 | blocks by default；只可由authorized human明確接受 |
| `Minor` | bounded polish或maintainability improvement，不使delivery claim失效 | 不阻擋，但保持可見 |

Confidence回答「目前evidence多確定」，severity回答「若claim成立impact多大」。Low-confidence possible data corruption仍可能是Critical needs-verification；high-confidence typo通常仍是Minor。

## Accepted Risk and Disputes

`disputed`需要反證或缺失fact，不等於implementer不同意。Controller記錄雙方claim、最小裁決方法與authority；可驗證就先驗證，policy conflict交給project owner。

`accepted-risk`至少記錄finding ID、接受者、reason、bounded scope、mitigation、expiry/follow-up和為何此人有authority。Critical不可接受；Important若project policy禁止exception也不可接受。到期未處理自動回到open。

## Small-Change Scaling

小change可以縮短context和角色數量，不能刪除truth boundary：

- fixed base/head與diff仍要存在；
- applicable deterministic checks仍要fresh；
- 一位fresh reviewer可依序負責四軸，但不能讓implementer自批；
- 明確not-applicable的risk lenses只記理由，不派specialist；
- finding schema和go/no-go不變；
- typo/docs-only change可用focused checks，不需要虛構migration或capacity review。

風險由data/interface/security/rollout surface決定，不由diff行數單獨決定。

## Copyable Reviewer Instructions

```text
You are an independent, read-only reviewer. Read the review packet first.
Review only the assigned axis/lens against the fixed BASE..HEAD candidate.
Treat the implementer report and passing tests as claims/evidence, not truth.

For every issue, output exactly these fields:
id, lens, severity, confidence, location, rule, impact, evidence,
direction, verification, status.

Use status needs-verification when the packet cannot prove the claim.
Do not invent project invariants or standards. Name the missing fact.
Do not average axes, rerank another reviewer's finding, mutate the checkout,
or approve delivery. Point to reproducible evidence and the smallest check
that could disprove you. Return an explicit axis/lens verdict and coverage
limitations after the findings.
```

## Completion Checklist

- [ ] Fixed base、HEAD、commit list、full diff已保存。
- [ ] Spec/acceptance、repo instructions、ADRs、Core rules與Overlay facts完整或明確abort。
- [ ] Applicable deterministic checks對當前HEAD fresh且passing。
- [ ] Data、interface、compatibility、operational、rollout boundaries已宣告。
- [ ] 四個core axes都有獨立logical verdict。
- [ ] Risk lenses有applicability理由與必要verdict。
- [ ] 每個finding完全符合11-field contract。
- [ ] Needs-verification claims已查證或仍明確阻擋相關pass claim。
- [ ] Critical為零；Important已verified或authorized accepted-risk。
- [ ] 每個fix都有covering evidence與re-review。
- [ ] Aggregation沒有平均severity或mask axis。
- [ ] Go/no-go authority、decision與candidate SHA已記錄。
