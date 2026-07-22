# 02 - Production Engineering Core Profile

## Policy Status

本文件是跨語言Normative baseline。Rule IDs是spec、plan、Project Overlay、review finding、exception和delivery record的stable references；修改措辭不重新編號，改變語義必須版本化Profile。

## How to Apply This Profile

每個change對30條規則明確標記：

- `applicable`：列出Overlay facts與required evidence；
- `not-applicable`：寫具體boundary reason；
- `deferred`：只允許在尚未能判定applicability時使用，必須有owner與decision date，delivery前清零或轉成前兩者。

Silence不是decision。Default applicability只是提示，不能以diff行數或「internal change」跳過data、security、compatibility或recovery boundary。

## Severity and Exception Rules

Critical違反預設No-Go，Agent無權接受；Important預設阻擋，只有rule允許且authorized human留下bounded record才可接受；Minor保持可見。Exception包含rule/finding ID、candidate、authority、reason、scope、mitigation、expiry與follow-up。Evidence或candidate改變後重新評估。

## Rule Index

| ID | Title | Default applicability | Default severity |
|---|---|---|---|
| `REQ-001` | Observable requirements and invariants | behavior changes | Important |
| `REQ-002` | Risk and impact classification | all non-trivial changes | Important |
| `REQ-003` | End-to-end traceability | planned/reviewed delivery | Important |
| `DAT-001` | Atomicity and consistency boundary | multi-step state change | Critical |
| `DAT-002` | Concurrency, idempotency and ordering | concurrent/replayed work | Critical |
| `DAT-003` | Integrity constraints and reconciliation | persistent/derived state | Critical |
| `RES-001` | Stable error semantics and causality | fallible boundary | Important |
| `RES-002` | Bounded external work | remote/blocking work | Critical |
| `RES-003` | Explicit degradation and overload | fallback/overload path | Important |
| `MOD-001` | Cohesive module and minimal interface | module/service change | Important |
| `MOD-002` | Stable dependency direction | adapter/infrastructure use | Important |
| `MOD-003` | Readable, justified reuse | abstraction/duplication change | Important |
| `CMP-001` | Public contract compatibility | API/event/schema change | Critical |
| `CMP-002` | Safe data migration | persistent schema/data change | Critical |
| `CMP-003` | Mixed-version rollout | staged/distributed deploy | Critical |
| `SEC-001` | Authentication and authorization boundary | protected action/data | Critical |
| `SEC-002` | Sensitive data lifecycle | sensitive/secret data | Critical |
| `SEC-003` | Untrusted input and abuse paths | trust-boundary input | Critical |
| `PER-001` | SLO-derived resource budgets | runtime/hot-path change | Important |
| `PER-002` | Reproducible critical-path measurement | performance claim | Important |
| `PER-003` | Bounded resources and backpressure | queue/batch/fan-out/pool | Critical |
| `OBS-001` | Correlated bounded telemetry | runtime behavior change | Important |
| `OBS-002` | Actionable alert and runbook | service/SLO failure mode | Important |
| `OBS-003` | Auditable, non-leaking telemetry | audit/sensitive path | Critical |
| `TST-001` | Observable behavior and invariant tests | behavior change | Important |
| `TST-002` | Boundary and failure scenario coverage | applicable risk boundary | Important |
| `TST-003` | Fresh reproducible verification | every delivery candidate | Important |
| `DPL-001` | Staged rollout and abort/rollback | deployable runtime change | Critical |
| `DPL-002` | Proven restore and recovery | durable/critical system | Critical |
| `DPL-003` | Evidence-based go/no-go | every production delivery | Critical |

## 1. Requirements and Invariants

### `REQ-001` - Observable requirements and invariants

- **Rule ID:** `REQ-001`
- **Applicability:** Any behavior, state, interface or operational change; docs-only mechanics may be `not-applicable` with reason.
- **Requirement:** Name observable acceptance criteria and business invariants before implementation, including success, failure and forbidden states.
- **Rationale:** Without an observable boundary, implementation and tests can agree on the same wrong assumption while reviewers invent missing intent.
- **Required Evidence:** Canonical spec links every invariant to concrete scenarios, inputs and expected results.
- **Review Severity When Violated:** Important; Critical when the unnamed invariant protects money, security, irreversible state or safety.
- **Allowed Exception Process:** Only a product/domain owner may accept a bounded discovery spike; no production delivery until criteria exist.

### `REQ-002` - Risk and impact classification

- **Rule ID:** `REQ-002`
- **Applicability:** All non-trivial changes and any change touching persistent data, external actors, security or runtime behavior.
- **Requirement:** Declare system criticality, data sensitivity, affected actors, blast radius, reversibility and failure impact in the Overlay.
- **Rationale:** Severity, evidence depth and rollout controls cannot be calibrated from code shape alone.
- **Required Evidence:** Approved Overlay risk classification with owner and links to data/SLO/security sources.
- **Review Severity When Violated:** Important; Critical when unknown classification hides a plausible critical boundary.
- **Allowed Exception Process:** Authorized project owner may time-bound classification for non-production prototype only.

### `REQ-003` - End-to-end traceability

- **Rule ID:** `REQ-003`
- **Applicability:** Work delivered through a spec/plan/review gate; tiny mechanical changes may use a compact single-row mapping.
- **Requirement:** Maintain traceability from requirement to plan task, implementation, test/evidence and review finding/decision.
- **Rationale:** Unlinked artifacts let requirements disappear between conversation, code, tests and release approval.
- **Required Evidence:** Traceability table or durable linked artifacts covering every applicable requirement and rule ID.
- **Review Severity When Violated:** Important when missing links make completeness untrustworthy; otherwise Minor for a recoverable documentation gap.
- **Allowed Exception Process:** Delivery owner records the missing link, recovery owner and expiry; behavioral coverage may not be waived by paperwork.

## 2. Data Consistency and Concurrency

### `DAT-001` - Atomicity and consistency boundary

- **Rule ID:** `DAT-001`
- **Applicability:** Every multi-step state change across memory, database, cache, event or external side effect.
- **Requirement:** Define transaction/atomicity boundary, visibility and consistency model, plus allowed failure states before the first mutation.
- **Rationale:** Application sequencing is not a storage transaction, and a database commit does not atomically include an external side effect; partial success must be designed explicitly.
- **Required Evidence:** Transaction/state design plus failure-injection test proving atomic failure or named compensation/reconciliation.
- **Review Severity When Violated:** Critical when partial state can corrupt/loss data or money; otherwise Important.
- **Allowed Exception Process:** Critical integrity risk has no Agent exception; domain/data owner must approve an explicit temporary inconsistency window and repair proof.

### `DAT-002` - Concurrency, idempotency and ordering

- **Rule ID:** `DAT-002`
- **Applicability:** Concurrent writers, message delivery, retries, scheduled jobs, user resubmission or cross-service ordering.
- **Requirement:** Define concurrency control, idempotency scope/key/payload conflict/retention, duplicate handling and ordering assumptions. Retries do not create idempotency automatically.
- **Rationale:** Application checks race without atomic storage guarantees; external effects can repeat even when local state deduplicates; ordering differs across queues and replicas.
- **Required Evidence:** Race/replay/out-of-order test or formal reason each dimension is `not-applicable`, tied to storage/external guarantees.
- **Review Severity When Violated:** Critical for duplicate side effects, lost updates or broken ordering invariants; otherwise Important.
- **Allowed Exception Process:** No exception for uncontrolled critical side effects; authorized owner may accept bounded at-least-once behavior with detection and repair.

### `DAT-003` - Integrity constraints and reconciliation

- **Rule ID:** `DAT-003`
- **Applicability:** Persistent canonical or derived state with uniqueness, reference, range, conservation or synchronization constraints.
- **Requirement:** Enforce integrity in the strongest owning layer available and define detection, quarantine and reconciliation for residual inconsistency.
- **Rationale:** Application validation can be bypassed or race; storage constraints cannot cover distributed/external state, so residual drift needs operational repair.
- **Required Evidence:** Schema/constraint output, negative tests, drift query/metric and executable reconciliation procedure with ownership.
- **Review Severity When Violated:** Critical when corruption can persist undetected; Important for bounded rebuildable derived data.
- **Allowed Exception Process:** Data owner may accept a time-bounded derived-state gap only with detection threshold, repair SLA and rollback/forward plan.

## 3. Error Handling and Resilience

### `RES-001` - Stable error semantics and causality

- **Rule ID:** `RES-001`
- **Applicability:** Any fallible parser, domain operation, adapter, API or background job boundary.
- **Requirement:** Classify expected errors, preserve causal context and expose stable caller-facing semantics without swallowing unrelated failures.
- **Rationale:** Broad catch/default behavior converts actionable faults into ambiguous success and destroys diagnosis; leaking raw infrastructure errors couples callers.
- **Required Evidence:** Error taxonomy/contract plus behavior tests for each class and cause preservation where applicable.
- **Review Severity When Violated:** Important; Critical when ambiguity can cause unsafe action, corruption or security bypass.
- **Allowed Exception Process:** Owner may accept redacted causal detail, never silent success, with an alternate diagnostic signal.

### `RES-002` - Bounded external work

- **Rule ID:** `RES-002`
- **Applicability:** Network, subprocess, lock, storage or other blocking/external work.
- **Requirement:** Define total budget, per-attempt timeout, retry count/backoff, cancellation and idempotency/unknown-outcome semantics within remaining budget.
- **Rationale:** Library defaults may be unbounded; retries amplify load and duplicate side effects unless application, dependency and external guarantees align.
- **Required Evidence:** Injected timeout/retry-exhaustion/unknown-outcome results plus attempt/budget metrics and non-retryable propagation tests.
- **Review Severity When Violated:** Critical for critical path, side effects or unbounded exhaustion; otherwise Important.
- **Allowed Exception Process:** No unbounded production call exception; authorized owner may temporarily disable retry while retaining a hard deadline and explicit failure.

### `RES-003` - Explicit degradation and overload

- **Rule ID:** `RES-003`
- **Applicability:** Fallback, cache/stale read, circuit breaker, queue, admission control or overload behavior.
- **Requirement:** Define degradation/fallback business meaning, forbidden consumers, freshness, circuit/backpressure behavior and never represent failure as ambiguous success.
- **Rationale:** A fallback can silently corrupt decisions; unlimited queues and retry storms move failure rather than contain it.
- **Required Evidence:** Degradation/overload scenarios, saturation signals, caller contract and operator-visible state transitions.
- **Review Severity When Violated:** Important; Critical when false success affects money, authorization, irreversible action or severe outage.
- **Allowed Exception Process:** Domain/operations owners jointly accept bounded degraded mode with metric, expiry and kill/disable path.

## 4. Interface and Module Design

### `MOD-001` - Cohesive module and minimal interface

- **Rule ID:** `MOD-001`
- **Applicability:** New/changed modules, services, packages, classes or public functions.
- **Requirement:** Give each module one coherent responsibility behind a minimal explicit interface; keep change reasons and owned invariants together.
- **Rationale:** Wide surfaces and mixed responsibilities expose internals, scatter policy and make tests/refactors expensive.
- **Required Evidence:** Public-surface review, responsibility statement and focused tests through the interface.
- **Review Severity When Violated:** Important when coupling or invariant ownership makes change untrustworthy; Minor for bounded naming/surface polish.
- **Allowed Exception Process:** Architecture owner may accept a temporary facade during migration with removal trigger and date.

### `MOD-002` - Stable dependency direction

- **Rule ID:** `MOD-002`
- **Applicability:** Domain/application code using storage, transport, framework, SDK or other infrastructure.
- **Requirement:** Point dependencies toward stable domain/application interfaces and prevent infrastructure shape from leaking across the seam.
- **Rationale:** Reach-through to connections, rows or SDK objects couples policy to replaceable details and makes fakes accidentally bless forbidden design.
- **Required Evidence:** Dependency map or focused interface-only test/review showing callers use only the declared seam.
- **Review Severity When Violated:** Important; Critical if leakage also bypasses security, transaction or compatibility control.
- **Allowed Exception Process:** Architecture owner may time-bound an adapter migration; direct infrastructure dependency must remain isolated and named.

### `MOD-003` - Readable, justified reuse

- **Rule ID:** `MOD-003`
- **Applicability:** New abstraction, shared utility/framework, duplicated policy or readability-affecting refactor.
- **Requirement:** Optimize naming, cohesion and locality first; extract reuse only for demonstrated shared policy/variation with a clear contract.
- **Rationale:** Reuse is not measured by abstraction count. A direct cohesive implementation can be safer than a premature generic framework that hides control flow.
- **Required Evidence:** Reviewer evidence of duplicated policy/real consumers or abstraction rationale, examples and tests at the stable seam.
- **Review Severity When Violated:** Important for speculative framework/cross-module policy drift; Minor for local clarity improvements.
- **Allowed Exception Process:** Architecture owner records the concrete future migration/removal criterion; speculative extension points without a consumer are removed.

## 5. Compatibility and Migration

### `CMP-001` - Public contract compatibility

- **Rule ID:** `CMP-001`
- **Applicability:** Public/internal APIs with independent consumers, events, schemas, CLI/config or persisted format changes.
- **Requirement:** Define compatibility commitment, consumer inventory, versioning and supported transition before changing a contract.
- **Rationale:** Producer tests cannot prove unknown consumers are safe; additive syntax can still change semantics or cardinality.
- **Required Evidence:** Contract diff, consumer sign-off/inventory and compatibility/old-new tests.
- **Review Severity When Violated:** Critical for unknown or irreversible consumer break; otherwise Important.
- **Allowed Exception Process:** A code review cannot accept unknown consumer compatibility as probably safe; contract owner must bound consumers and authorize a migration.

### `CMP-002` - Safe data migration

- **Rule ID:** `CMP-002`
- **Applicability:** Schema, data shape, backfill, index, encoding or ownership migration.
- **Requirement:** Make migration bounded, restartable, observable and reversible or forward-recoverable, with invariant checks before/after.
- **Rationale:** Code rollback may not undo data transformation; partial backfills and long locks can damage correctness/availability.
- **Required Evidence:** Rehearsal output, representative data checks, duration/capacity estimate and rollback/forward-repair plan.
- **Review Severity When Violated:** Critical.
- **Allowed Exception Process:** Data owner and release authority may choose forward-only recovery only with tested repair path; no unowned irreversible migration.

### `CMP-003` - Mixed-version rollout

- **Rule ID:** `CMP-003`
- **Applicability:** Rolling/staged deploys, multiple service versions, asynchronous consumers or old/new data coexistence.
- **Requirement:** Sequence expand/migrate/contract so old/new code and data interoperate throughout rollout and rollback windows.
- **Rationale:** Individually correct versions can fail during overlap; replication/event lag extends the mixed state.
- **Required Evidence:** Deployment sequence, compatibility matrix and mixed-version/old-new data test.
- **Review Severity When Violated:** Critical when rollout can break reads/writes or strand data; otherwise Important.
- **Allowed Exception Process:** Release authority may require coordinated downtime with explicit user impact and restore gate; never assume atomic fleet deploy.

## 6. Security and Privacy

### `SEC-001` - Authentication and authorization boundary

- **Rule ID:** `SEC-001`
- **Applicability:** Protected action/data, identity propagation, service-to-service access or permission change.
- **Requirement:** Enforce authentication, object/action authorization, least privilege and deny-by-default at the owning boundary.
- **Rationale:** UI hiding and upstream checks can be bypassed; identity without resource/action authorization is insufficient.
- **Required Evidence:** Threat/permission matrix, negative/cross-tenant tests and runtime/config evidence of least privilege.
- **Review Severity When Violated:** Critical.
- **Allowed Exception Process:** Unknown authorization ownership cannot be accepted as probably safe; security/data owner must define and approve the boundary.

### `SEC-002` - Sensitive data lifecycle

- **Rule ID:** `SEC-002`
- **Applicability:** Secrets, credentials, personal, payment, health or otherwise classified data.
- **Requirement:** Classify data and define collection, storage, encryption, access, retention, redaction, deletion and backup/telemetry treatment.
- **Rationale:** Protection at rest alone does not prevent logs, caches, backups or over-broad roles from leaking data.
- **Required Evidence:** Data-flow inventory, secret/config/runtime evidence, access controls and redaction/deletion tests.
- **Review Severity When Violated:** Critical for exposure or unbounded retention; Important for incomplete evidence with containment.
- **Allowed Exception Process:** Only designated security/privacy authority may accept a bounded gap where law/policy permits, with mitigation and expiry.

### `SEC-003` - Untrusted input and abuse paths

- **Rule ID:** `SEC-003`
- **Applicability:** Any user/external input, upload, query, template, command, webhook or resource-consuming action.
- **Requirement:** Validate syntax and semantics at the owning boundary, encode safely and model abuse, injection, traversal and resource-exhaustion paths.
- **Rationale:** Downstream sanitization assumptions drift; valid-looking input can still violate domain or capacity constraints.
- **Required Evidence:** Threat model, positive/negative/boundary tests and relevant static/dependency/dynamic scan output.
- **Review Severity When Violated:** Critical for reachable exploit/security boundary; otherwise Important.
- **Allowed Exception Process:** Security owner may classify a path unreachable only with enforceable boundary evidence, not reviewer assumption.

## 7. Performance and Capacity

### `PER-001` - SLO-derived resource budgets

- **Rule ID:** `PER-001`
- **Applicability:** Runtime path, payload, concurrency, storage or dependency behavior affecting user/service SLO.
- **Requirement:** Derive latency, throughput, concurrency, payload and resource budgets from an approved SLO/capacity model.
- **Rationale:** “Fast enough” has no review boundary; local latency can consume a shared end-to-end budget or shift load elsewhere.
- **Required Evidence:** Approved budgets, workload assumptions and representative measurements tied to environment.
- **Review Severity When Violated:** Important; Critical when unbounded load threatens severe outage or data processing deadlines.
- **Allowed Exception Process:** Service owner may accept a measured temporary regression within error/capacity budget and expiry.

### `PER-002` - Reproducible critical-path measurement

- **Rule ID:** `PER-002`
- **Applicability:** Performance optimization/regression claim or material hot-path change.
- **Requirement:** Measure with realistic data/workload and preserve reproducible baseline, environment, variance and comparison.
- **Rationale:** Microbenchmarks and one-off local timings can optimize the wrong bottleneck or hide tail/resource cost.
- **Required Evidence:** Benchmark/load profile, dataset, environment, repeated results and before/after comparison.
- **Review Severity When Violated:** Important for a delivery performance claim; Minor when no performance claim/risk is made.
- **Allowed Exception Process:** Owner may ship an instrumented experiment behind a bounded flag with rollback and measurement plan.

### `PER-003` - Bounded resources and backpressure

- **Rule ID:** `PER-003`
- **Applicability:** Queue, batch, cache, buffer, memory, thread/connection pool, fan-out or untrusted-size work.
- **Requirement:** Set enforceable bounds and define admission, shedding/backpressure, timeout and saturation behavior.
- **Rationale:** Unlimited buffering converts transient overload into memory exhaustion and latency collapse; fan-out multiplies downstream pressure.
- **Required Evidence:** Capacity/failure test at/over bounds plus queue/pool/memory/fan-out saturation signals.
- **Review Severity When Violated:** Critical for unbounded severe outage path; otherwise Important.
- **Allowed Exception Process:** No unbounded production resource; operations owner may choose a conservative temporary cap with telemetry and tuning date.

## 8. Observability and Operability

### `OBS-001` - Correlated bounded telemetry

- **Rule ID:** `OBS-001`
- **Applicability:** New/changed runtime success, failure, retry, state transition or dependency path.
- **Requirement:** Emit structured logs, metrics and traces needed to answer named operator questions, with stable correlation and bounded dimensions/cardinality/retention.
- **Rationale:** “Add logs” is insufficient: unstructured or high-cardinality signals can be unusable, expensive and privacy-risking.
- **Required Evidence:** Signal examples and automated/runtime checks naming operator question, dimensions, retention/cardinality boundary and expected response.
- **Review Severity When Violated:** Important; Critical when absence prevents detecting/recovering a critical failure.
- **Allowed Exception Process:** Operations owner may accept one signal type if another proves the same question within SLO and runbook.

### `OBS-002` - Actionable alert and runbook

- **Rule ID:** `OBS-002`
- **Applicability:** Service/SLO failure mode requiring operator action or automated remediation.
- **Requirement:** Connect alerts to user/SLO impact, threshold/window, owner, dashboard, runbook and expected response.
- **Rationale:** Symptom-free low-level alerts create noise; missing ownership and action delay containment.
- **Required Evidence:** Alert-to-runbook mapping and test/staging signal showing notification, context and recovery action.
- **Review Severity When Violated:** Important; Critical for an otherwise invisible critical failure.
- **Allowed Exception Process:** Operations owner may defer paging only with a monitored dashboard, response owner and decision date.

### `OBS-003` - Auditable, non-leaking telemetry

- **Rule ID:** `OBS-003`
- **Applicability:** Security/business audit event or telemetry touching secrets/sensitive payloads.
- **Requirement:** Preserve tamper-aware audit identity/action/outcome while excluding or redacting prohibited secrets and data.
- **Rationale:** Ordinary debug logs are neither a reliable audit trail nor safe storage for raw sensitive values.
- **Required Evidence:** Audit-event contract, access/retention control and redaction/negative tests across logs, metrics and traces.
- **Review Severity When Violated:** Critical for leakage or missing mandated audit; otherwise Important.
- **Allowed Exception Process:** Security/privacy authority only, within legal/policy bounds, with alternate audit/containment and expiry.

## 9. Testing and Verification

### `TST-001` - Observable behavior and invariant tests

- **Rule ID:** `TST-001`
- **Applicability:** Any behavior/invariant change.
- **Requirement:** Test public observable behavior and named invariants with independent expected values, not implementation trivia or mocks alone.
- **Rationale:** Tests sharing implementation logic or private seams can stay green while the real contract is wrong and block safe refactor.
- **Required Evidence:** Requirement-to-test mapping and red/green evidence for the change at agreed public seams.
- **Review Severity When Violated:** Important; Critical when missing test is the only proof for a critical invariant.
- **Allowed Exception Process:** Owner may substitute stronger formal/runtime evidence where deterministic test is infeasible, with rationale.

### `TST-002` - Boundary and failure scenario coverage

- **Rule ID:** `TST-002`
- **Applicability:** Every failure, concurrency, replay, compatibility, contract or security boundary marked applicable.
- **Requirement:** Cover the applicable scenario matrix including partial failure, duplicate/reorder, limits and old/new interactions.
- **Rationale:** Happy-path coverage says nothing about the paths that production controls are meant to contain.
- **Required Evidence:** Scenario matrix mapped to deterministic outcomes/failure injection, with explicit not-applicable reasons.
- **Review Severity When Violated:** Important; Critical when untested path can cause critical impact.
- **Allowed Exception Process:** Risk owner may stage a bounded canary only with observability, abort gate and follow-up test date.

### `TST-003` - Fresh reproducible verification

- **Rule ID:** `TST-003`
- **Applicability:** Every delivery candidate.
- **Requirement:** Record exact fresh commands, environment assumptions, candidate identity, exit status and complete/locatable output.
- **Rationale:** Historical or summarized “tests pass” claims cannot prove current HEAD and hide warnings, skips or environment differences.
- **Required Evidence:** Re-runnable verification packet produced after the last candidate change.
- **Review Severity When Violated:** Important; Critical when no other proof protects a critical boundary.
- **Allowed Exception Process:** Delivery authority may mark a check externally blocked only with equivalent evidence and explicit No-Go/Pending until resolved when required.

## 10. Deployment, Rollback and Recovery

### `DPL-001` - Staged rollout and abort/rollback

- **Rule ID:** `DPL-001`
- **Applicability:** Deployable runtime, config, dependency, contract or data change.
- **Requirement:** Define rollout stages, health gates, abort criteria, rollback action and limitations. Distinguish code rollback from data rollback.
- **Rationale:** Reverting binaries does not undo writes, migrations, emitted events or external effects; late health checks expand blast radius.
- **Required Evidence:** Deployment rehearsal or reviewed runbook with commands, owners, health queries and forward-repair when rollback is unsafe.
- **Review Severity When Violated:** Critical.
- **Allowed Exception Process:** Release authority may approve forward-only deploy only with tested recovery, bounded blast radius and stop gate.

### `DPL-002` - Proven restore and recovery

- **Rule ID:** `DPL-002`
- **Applicability:** Durable/critical state or service with declared RPO/RTO.
- **Requirement:** Define and prove backup/restore, recovery point/time and post-recovery integrity/reconciliation checks.
- **Rationale:** Backup existence is not restore proof; unreadable, slow or inconsistent backups fail only during incident.
- **Required Evidence:** Restore drill or equivalent recovery exercise measuring RPO/RTO and verifying business invariants afterward.
- **Review Severity When Violated:** Critical for irreplaceable/critical data; Important for fully rebuildable derived state.
- **Allowed Exception Process:** Data/business owner may classify state rebuildable only with demonstrated source, duration and capacity.

### `DPL-003` - Evidence-based go/no-go

- **Rule ID:** `DPL-003`
- **Applicability:** Every production delivery decision.
- **Requirement:** Base go/no-go on candidate identity, evidence freshness, unresolved findings, owners and time-bounded accepted risk; never average severity to mask Critical findings.
- **Rationale:** A quality score or majority pass can conceal one catastrophic path; unowned exceptions silently become permanent policy.
- **Required Evidence:** Signed/attributed decision record, open-risk inventory, verification packet and exact candidate/deployment boundary.
- **Review Severity When Violated:** Critical.
- **Allowed Exception Process:** None for unresolved Critical or unknown candidate; authorized human may accept eligible Important risks under their rule process.

## Profile Completion Checklist

- [ ] Every rule is `applicable`, `not-applicable + reason` or `deferred + owner/date`.
- [ ] All deferred decisions are resolved before production go/no-go.
- [ ] Applicable rules link exact Overlay facts and evidence.
- [ ] Critical findings are zero; Important findings are verified or valid accepted-risk.
- [ ] Evidence was produced after the final candidate change.
- [ ] Contract/migration/deploy/recovery boundaries include mixed and failure states.
- [ ] Decision record names candidate, authority, scope and open risks.
