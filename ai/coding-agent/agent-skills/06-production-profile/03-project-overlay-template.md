# 03 - Project Overlay Template

## Template Status and Copy Instructions

這是copyable、instructional template，不是可直接宣告完成的policy。複製到project canonical docs後：

1. 保留section與Core rule IDs；
2. 將每個`Required project fact` guidance替換成已確認的具體值；
3. 填入可讀/可執行的Evidence location與具名Owner；
4. 不確定的row標`deferred + owner + decision date`，不能留白或讓AI猜；
5. Project owner、domain/security/operations等對應authority批准後才成為review input。

## Completion Rules

- 每個Core rule在Applicability Matrix恰有一個狀態：`applicable`、`not-applicable + reason`或`deferred + owner/date`。
- Guidance、unresolved placeholder、`unknown`與example不能作production fact；delivery前所有blocking deferred清零。
- 數值要有unit與boundary；語義要列success/failure/forbidden states；evidence要能定位candidate/version。
- 一個owner是具名role/team，不是`engineering`或`someone`。
- 變更domain、dependency、SLO、consumer、security或recovery fact時，觸發Overlay review。

## 1. System Purpose and Risk Classification

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `REQ-001` | 一句話system purpose、primary user journeys及每條journey的observable success/failure acceptance；替換本guidance | `<product spec / acceptance suite>` | `<product/domain owner>` |
| `REQ-002` | User impact、affected actors、criticality tier、maximum tolerable impact/blast radius、reversibility；列regulated/sensitive data classes | `<risk register / data classification>` | `<service + risk owner>` |
| `REQ-003` | Canonical traceability位置與linking convention：requirement → task → code → test/evidence → finding/decision | `<traceability index>` | `<delivery owner>` |

## 2. Domain Vocabulary and Invariants

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `REQ-001` | Canonical terms、同義/禁用詞、aggregate/ownership boundaries與具體scenario；不能只貼class names | `<CONTEXT.md / domain glossary>` | `<domain owner>` |
| `DAT-001` | 每個state machine的states、allowed/forbidden transitions、preconditions、atomic business operation與failure state | `<state model / tests>` | `<domain + data owner>` |
| `DAT-003` | 每條conservation/uniqueness/reference invariant、system of record、derived copies與authoritative repair direction | `<invariant catalog / schema>` | `<data owner>` |

## 3. Data, Transactions, Concurrency, and Idempotency

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `DAT-001` | 每個multi-step write的transaction boundary、storage isolation/consistency model、commit/visibility point、讀者何時可見與external side-effect boundary | `<transaction design + failure tests>` | `<data/domain owner>` |
| `DAT-002` | Concurrency control/lock or compare-and-set、conflict winner、race handling；明確寫`idempotency-key scope`、retention、same-key/different-payload behavior | `<race/replay tests>` | `<data/service owner>` |
| `DAT-002` | Event partition/ordering assumptions、duplicate/out-of-order policy、dedupe key/retention與unknown-outcome retry semantics | `<event contract + tests>` | `<producer/consumer owners>` |
| `DAT-003` | Database constraints、drift detection query/metric、reconciliation trigger/frequency、quarantine/manual repair與SLA | `<DDL/check/reconcile runbook>` | `<data operations owner>` |

## 4. External Dependencies and Resilience

為每個dependency複製一row，不把多個dependencies合併成「HTTP defaults」。

| Core rule | Dependency | Required project fact | Evidence location | Owner |
|---|---|---|---|---|
| `RES-001`, `RES-002`, `RES-003` | `<dependency-name>` | Criticality；total budget；`per-attempt timeout`；max attempts/backoff；retryable errors；idempotency prerequisite/unknown outcome；fallback semantic與forbidden states；circuit/bulkhead/backpressure；caller-facing error | `<contract + timeout/failure tests>` | `<dependency owner>` |
| `OBS-001`, `OBS-002` | `<dependency-name>` | Metric/log/trace names、low-cardinality dimensions、SLO/alert threshold、dashboard/runbook與escalation owner | `<telemetry check + runbook>` | `<operations owner>` |
| `TST-002` | `<dependency-name>` | Required injected scenarios：timeout、partial response、non-retryable error、retry exhaustion、fallback、circuit/open、overload；列exact test command | `<fixture/test output>` | `<test owner>` |

## 5. Interfaces, Compatibility, and Migration

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `MOD-001`, `MOD-002` | Public module seams、responsibility owner、approved adapters、forbidden infrastructure types/shapes outside adapter | `<architecture map + interface tests>` | `<architecture owner>` |
| `CMP-001` | 每個API/event/schema owner與consumers、`compatibility window`、version negotiation、deprecation notice/support policy與breaking-change authority | `<contract registry/diff>` | `<contract owner>` |
| `CMP-002` | Migration size/duration/lock budget、batch/checkpoint/restart semantics、data validation、rollback限制與forward recovery | `<rehearsal + runbook>` | `<data/release owner>` |
| `CMP-003` | Old/new producer/consumer/data mixed-version behavior、expand/migrate/contract sequence、contract removal gate | `<compatibility matrix/tests>` | `<release owner>` |

## 6. Security and Privacy

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `SEC-001` | Trust boundaries、identity sources/propagation與actor × resource/action `permission matrix`，含deny-by-default和cross-tenant cases | `<threat model + negative tests>` | `<security/domain owner>` |
| `SEC-002` | Sensitive-data flow/classification、collection purpose、secret ownership/storage/rotation、encryption、access、retention、redaction、deletion與backup treatment | `<data flow + config/evidence>` | `<security/privacy owner>` |
| `SEC-003` | Untrusted-input owners、syntax/semantic limits、encoding、upload/query limits、injection/traversal/SSRF/abuse/resource cases | `<threat model + tests/scans>` | `<security + boundary owner>` |

## 7. SLO, Capacity, and Performance Budgets

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `PER-001` | SLI/SLO與window；latency percentiles、throughput、concurrency、payload、CPU/memory/storage/network/dependency budgets | `<SLO doc + budget model>` | `<service owner>` |
| `PER-002` | Representative load shape/data distribution、environment、growth assumption、baseline date/commit、variance與comparison method | `<benchmark/load report>` | `<performance owner>` |
| `PER-003` | Queue/batch/cache/pool/fan-out hard bounds、saturation point、admission/shedding/backpressure behavior與capacity headroom | `<capacity/failure test + signals>` | `<service/operations owner>` |

## 8. Observability and Operations

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `OBS-001` | Structured log events、metric names/types、trace spans/status、correlation keys；每個signal回答的operator question與`cardinality boundary`/retention | `<signal catalog + sample/runtime check>` | `<operations owner>` |
| `OBS-002` | Dashboard links、alert SLO impact/threshold/window、page/ticket owner、runbook、expected response與test signal | `<alert-runbook map>` | `<on-call owner>` |
| `OBS-003` | Audit event actor/action/target/outcome、integrity/access/retention；prohibited fields與logs/metrics/traces redaction checks | `<audit contract + redaction tests>` | `<security/operations owner>` |

## 9. Testing and Verification

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `TST-001` | Approved public test seams、independent oracle source、requirement/invariant-to-test mapping與RED evidence policy | `<test strategy/mapping>` | `<quality/domain owner>` |
| `TST-002` | Required happy/failure/concurrency/replay/compatibility/security/capacity scenarios、fixtures與deterministic outcome | `<scenario matrix>` | `<quality/risk owners>` |
| `TST-003` | Exact unit/integration/contract/e2e/security/migration commands、versions/environment/services、output artifact與retention/freshness | `<verification runbook/CI artifacts>` | `<delivery owner>` |

## 10. Deployment, Rollback, and Recovery

| Core rule | Required project fact | Evidence location | Owner |
|---|---|---|---|
| `DPL-001` | Rollout stages/percentages、health and abort gates、feature flag、code rollback command/limit、data rollback或forward recovery、incident owner | `<deploy runbook/rehearsal>` | `<release/on-call owner>` |
| `DPL-002` | Backup scope/frequency/retention、restore procedure、target `RPO`/`RTO`、latest drill、recovery integrity/reconciliation checks | `<restore drill evidence>` | `<data/recovery owner>` |
| `DPL-003` | Go/no-go meeting/automation、required evidence freshness、blocking severity、accepted-risk authority/expiry與decision record location | `<release decision template>` | `<release authority>` |

## 11. Language and Framework Conventions

這些答案只屬本project，不因一個repository採用就複製進Core。

| Topic | Required project fact | Evidence location | Owner |
|---|---|---|---|
| Runtime/toolchain | Language/framework/runtime/package-manager versions與upgrade/support policy | `<lock/tool version files>` | `<platform owner>` |
| Canonical commands | Setup、format、lint、typecheck、test、build、security、migration和local services exact commands | `<Makefile/task docs/CI>` | `<developer-experience owner>` |
| Modules/imports | Directory/package boundaries、dependency/import direction、generated code與public export convention | `<architecture/coding standards>` | `<architecture owner>` |
| Interface patterns | Project-approved repository/client/adapter/error/config patterns及明確禁用patterns | `<reference modules/ADR>` | `<architecture owner>` |
| Static rules | Project-specific compiler/linter/analyzer rules、warning policy、suppress/exception process | `<tool config + CI>` | `<quality owner>` |

## Rule Applicability Matrix

複製本表後，`Decision`只填三種合法形式：`applicable`、`not-applicable: <reason>`、`deferred: <owner>, <decision date>`。

| Core rule | Decision | Overlay/evidence reference | Decision owner |
|---|---|---|---|
| `REQ-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `REQ-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `REQ-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DAT-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DAT-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DAT-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `RES-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `RES-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `RES-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `MOD-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `MOD-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `MOD-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `CMP-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `CMP-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `CMP-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `SEC-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `SEC-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `SEC-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `PER-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `PER-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `PER-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `OBS-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `OBS-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `OBS-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `TST-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `TST-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `TST-003` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DPL-001` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DPL-002` | `<legal decision form>` | `<section/link>` | `<owner>` |
| `DPL-003` | `<legal decision form>` | `<section/link>` | `<owner>` |

## Exception Register

每個exception複製一row；不允許缺欄。

| Required field | Required answer |
|---|---|
| exception ID | Stable project identifier，例如`EXC-2026-004` |
| Core rule ID | 一個被例外的Core ID；多rule分開或明確列關係 |
| scope | Candidate/service/traffic/data/user/time的精確bounded scope |
| decision owner | 提出與維護exception的具名role/person |
| rationale | 為何現在不能符合rule及替代方案trade-off |
| measured impact | 已量測或最壞credible impact；未知值不能省略 |
| compensating controls | 限制exposure、detect/contain/recover的具體controls |
| verification evidence | Commands、runtime signal或test證明controls有效 |
| approver | 依severity/rule有authority的human |
| created date | ISO date與candidate/version |
| expiry or mandatory review date | 到期自動reopen；不得填永久 |
| removal plan | Owner、milestone、success evidence與rollback |

## Approval and Review Cadence

| Trigger | Required reviewers | Output |
|---|---|---|
| Initial adoption | Domain、data、security、operations、architecture、release owners中applicable者 | Approved v1 Overlay + applicability matrix |
| Feature/spec change | Affected fact owners | Updated rows、rule mapping、evidence plan |
| New/changed dependency or contract | Dependency/contract、operations、security owners | Budget/compatibility/failure updates |
| Incident or escaped defect | Incident owner + affected rule owners | Corrected fact/rule/evidence and regression scenario |
| Scheduled review | At least quarterly for critical systems; project填確切cadence | Stale owner/link/exception cleanup and version record |

## Worked Mini Example

以下完全是**illustrative fictional values，不是universal defaults**。

### Payment-risk API dependency row

| Core rule | Dependency | Required project fact | Evidence location | Owner |
|---|---|---|---|---|
| `RES-001`, `RES-002`, `RES-003` | `payment-risk-api` | Tier-1 decision read；total budget `400 ms`；最多`2 × 150 ms` attempts，固定`25 ms` backoff；operation為idempotent read；只retry timeout/503；timeout exhaustion回`risk-unavailable`並禁止自動approve；20-request bulkhead；metric`risk_client_requests_total{outcome}`與`risk_client_latency_ms`；failure test注入timeout/503/empty-success | `tests/contract/test_risk_client.py`; `runbooks/risk-api.md` | `Payments Risk` |

### `RES-002` applicability row

| Core rule | Decision | Overlay/evidence reference | Decision owner |
|---|---|---|---|
| `RES-002` | `applicable` | Dependency row above；timeout/retry-exhaustion tests與staging metric screenshot attached to release evidence | `Payments Risk tech lead` |

此example只示範answer precision。真實project必須從自己的SLO、dependency contract、side-effect semantics與capacity導出數值。
