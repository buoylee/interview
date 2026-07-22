# 01 - Production Quality Model

## Policy Status

本頁定義本專題的Normative production-quality model，供Core Profile、Project Overlay、spec/plan和AI Review共同使用。規則是否applicable仍由change surface與project facts決定。

## 先給結論

Production-ready不是code的單一屬性，也不是tests green或review approved的同義詞。它是一個bounded claim：對某個candidate、某組applicable requirements、某個runtime/deployment boundary，在fresh evidence與明確authority下可交付。

## The Four-Layer Formula

```text
Production-ready claim
  = universal engineering baseline
  + project-specific invariants
  + executable evidence
  + delivery gate
```

缺任何一層都會產生不同假象：

| 缺少層 | 假象 | 真正缺口 |
|---|---|---|
| universal engineering baseline | 每個task都從零回想failure/security/testing | 跨project最低責任沒有穩定ID |
| project-specific invariants | generic code很乾淨，但business state錯 | consistency、criticality、SLO等facts不存在 |
| executable evidence | spec/review措辭完整，看不到runtime truth | claim無法重現或推翻 |
| delivery gate | findings和tests都有，仍無人決定是否可上 | severity、exception、freshness與authority不明 |

## Universal Baseline

Universal baseline只放跨語言、跨stack反覆成立的責任，例如：

- business invariant必須可定位並有acceptance evidence；
- multi-step state change要定義atomicity與failure state；
- external call要有bounded budget和failure semantics；
- public contract change要處理compatibility與migration；
- sensitive data要有classification和access/logging rules；
- delivery要有rollback或forward recovery。

Baseline不放本project的timeout數字、table名稱、metric label或deployment command。它使用stable rule IDs，使spec、finding、exception和revision能引用同一責任。

## Project-Specific Invariants

Overlay把baseline問題回答成不可猜測的project facts：

- canonical domain vocabulary、state machine與forbidden transitions；
- transaction/consistency/idempotency/concurrency/reconciliation semantics；
- dependency budgets、retry/fallback/backpressure與unknown-outcome處理；
- API/event/schema consumers、compatibility window與migration order；
- data classification、authorization、retention和redaction；
- SLO/capacity、metrics/logs/traces、runbook和ownership；
- deploy、rollback、forward recovery、RPO/RTO與manual repair。

「strong consistency」「graceful fallback」「高可用」仍不是fact；必須命名observable behavior、time/window、owner和evidence。

## Executable Evidence

本Profile接受七類evidence；一條rule可要求多類：

| Evidence category | 內容 | 例子 |
|---|---|---|
| Static contract | 可版本化的spec/schema/type/ADR/rule mapping | state transition table、OpenAPI compatibility report |
| Deterministic command | 對當前candidate可重跑且有exit/output | tests、typecheck、lint、build、schema check |
| Behavior test | 從public seam驗證需求與independent oracle | duplicate delivery、authorization denial |
| Failure-injection result | 主動觸發timeout、partial failure、crash或resource limit | target不存在時不部分扣款 |
| Runtime/observability evidence | 指標、log、trace、dashboard/alert或staging observation | retry exhaustion metric與trace status |
| Migration/rollback proof | rehearsal、backfill validation、compatibility window、restore/forward-repair結果 | expand/migrate/contract演練 |
| Authorized risk record | 有authority、scope、reason、mitigation和expiry的exception | 限時接受Important finding |

Evidence必須對應當前HEAD/artifact version；歷史CI pass不能證明後來修改的candidate。

## Delivery Gate

Delivery gate消費：

1. candidate identity；
2. applicable Core rules與Overlay facts；
3. fresh required evidence；
4. review findings及status；
5. accepted risks與authority；
6. deploy/recovery readiness。

Go不是quality平均分。Critical永遠阻擋；Important預設阻擋，只有policy允許且authorized human明確接受才例外；Minor不阻擋但保持可見。Candidate在evidence後改動，gate失效並重新驗證。

## Applicability and Risk

不是每個change都要產生所有evidence。Applicability由change觸及的boundary決定：

| Change surface | 至少考慮 |
|---|---|
| persistent writes/state transitions | invariants、atomicity、concurrency、idempotency、migration/recovery |
| external dependency | time budget、retry safety、fallback、backpressure、telemetry |
| API/event/schema | consumer、compatibility、versioning、rollout order |
| auth/sensitive data | threat boundary、least privilege、redaction、audit |
| hot path/resource use | SLO、capacity、bounds、load evidence |
| deploy/runtime behavior | observability、feature flag、rollback/forward recovery、runbook |
| internal rename/docs-only | focused static checks；高風險lenses可明確N/A |

Diff小不等於risk小；一行改transaction order或authorization condition可能Critical。反之，不適用的rule應記理由，不製造形式化noise。

## Rule Schema

每條Core rule固定七個fields：

| Field | Meaning |
|---|---|
| **Rule ID** | 穩定reference，如`DAT-001`；修改prose不重新編號 |
| **Applicability** | 哪種change/boundary觸發；如何記not-applicable |
| **Requirement** | 可判定的MUST/SHOULD行為，不用slogan |
| **Rationale** | 防止的failure mode與trade-off |
| **Required Evidence** | 交付前可重現的最小proof |
| **Review Severity When Violated** | Critical/Important/Minor的default與升降級條件 |
| **Allowed Exception Process** | 誰可接受、需記什麼、何時到期；`None`表示不可例外 |

Rule fields不能由reviewer臨時省略。Project可加stack-specific reference，但不得改變stable ID語義而不版本化Profile。

## Severity and Exceptions

| Severity | Production meaning | Default action |
|---|---|---|
| Critical | credible data loss/corruption、security boundary breach、irreversible incompatibility或unbounded severe outage | No-Go；Agent不能接受exception |
| Important | correctness、resilience、maintainability或evidence gap使change不可信 | 預設No-Go；authorized human按rule process接受 |
| Minor | bounded polish/maintainability，不使delivery claim失效 | 保持可見，可排follow-up |

Exception不是刪規則。Record至少含rule/finding ID、candidate、owner/authority、reason、scope、mitigation、expiry和follow-up。到期或scope改變後重新open。

## Production-Ready Claim Boundary

完整claim應能回答：

```text
Candidate C 在 environment/deployment boundary E，
對 applicable rules R 與 project facts P，
已有 fresh evidence V；unresolved blocking findings為零，
exceptions A由具名authority接受，故 decision D有效至candidate或facts改變。
```

以下都不是充分claim：

- 「unit tests都過」；
- 「AI reviewer說LGTM」；
- 「用了TDD」；
- 「遵循best practices」；
- 「只是小diff」；
- 「CI部署後會測」。

## Worked Example: External Call

模糊句子：

> External calls need a timeout.

它不足以實作或review。四層展開如下。

### Universal baseline

Remote dependency call必須有bounded end-to-end time、明確failure classification，以及不超出budget的retry/fallback policy。

### Project Overlay facts

- 命名**total time budget**與每次**per-attempt timeout**，並說明connect/read或client deadline如何映射。
- retry count/backoff由operation **idempotency**與remaining budget共同決定；unknown outcome不得盲重試side effect。
- **fallback**有明確business meaning，例如`degraded-unavailable`；禁止用空object、stale data或success status掩蓋dependency failure，除非Overlay明示允許。
- timeout、retry、retry exhaustion與fallback paths發出定義好的**metrics**、structured logs和trace status，含必要low-cardinality labels。

### Executable evidence

- behavior tests注入success與合法empty result；
- **failure-injection**注入timeout、partial success/unknown outcome、retry exhaustion和fallback behavior；
- 確認attempt timeout、total elapsed/budget propagation、retry count和non-retryable propagation；
- staging/runtime evidence顯示metrics/logs/traces能區分failure states；
- 若fallback讀stale cache，驗證freshness bound與forbidden consumer。

### Delivery gate

Review severity跟dependency criticality與failure impact走：支付capture無timeout或錯誤retry可升Critical；非關鍵read path缺一個非必要metric可能Minor；無法證明budget/fallback semantics通常Important並阻擋。不得因diff只有一行client call而降級。

## Common Misreadings

| 誤讀 | 修正 |
|---|---|
| Core Profile越長越production-grade | 規則要stable、可適用、可證明；無owner checklist只製造noise |
| Overlay可以由AI自動填滿 | AI可提出問題，project owner必須確認facts與trade-offs |
| 所有fallback都提高可靠性 | 語義不明的fallback會把failure變成silent corruption |
| 抽interface一定更解耦 | 只有穩定seam、真實variation與正確dependency direction才有價值 |
| 100% test coverage證明correctness | Coverage不證明oracle、scenario或environment正確 |
| Accepted risk等於rule不適用 | Risk成立但限時接受；not-applicable表示boundary根本未觸發 |
| Review可以補spec | Reviewer只能揭露missing fact，不能替domain owner發明invariant |

## 一句話總結

Production quality不是要求Agent「多想一點」，而是把跨project底線、本project事實、可執行證據和放行authority連成一個可驗證claim。
