# Production Profile and Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable Production Engineering Core Profile, a project-specific Overlay template, workflow integration rules, and an adoption playbook that make production-quality expectations explicit without forking either upstream skill library.

**Architecture:** Treat production readiness as four separate layers: universal engineering baseline, project-specific invariants, executable evidence, and a delivery gate. Put cross-project judgment in stable Core rules, concrete project facts in an Overlay, and orchestration glue in thin local instructions or wrapper skills only when repeated workflow behavior justifies it.

**Tech Stack:** Traditional-Chinese Markdown, Mermaid, Git, `rg`, Python 3 standard-library documentation checks, and the completed AI Code Review fixture runner.

## Global Constraints

- Execute after both `2026-07-21-agent-skills-learning-foundations.md` and `2026-07-21-ai-code-review-protocol-and-lab.md` complete cleanly.
- Work only in `/Users/buoy/Development/gitrepo/interview/.worktrees/agent-skills-learning` on branch `codex/agent-skills-learning`.
- Keep both upstream repositories unmodified and upgradeable.
- Label the Core Profile, Project Overlay, integration policy, and adoption playbook as local normative artifacts (`本專題定義`).
- Preserve the formula `Production-ready = universal engineering baseline + project-specific invariants + executable evidence + delivery gate`.
- Core Profile defines what every applicable project must answer; Project Overlay supplies exact project answers.
- Every Core rule uses exactly: Rule ID, Applicability, Requirement, Rationale, Required Evidence, Review Severity When Violated, and Allowed Exception Process.
- Cover all ten domains: Requirements and Invariants; Data Consistency and Concurrency; Error Handling and Resilience; Interface and Module Design; Compatibility and Migration; Security and Privacy; Performance and Capacity; Observability and Operability; Testing and Verification; Deployment, Rollback and Recovery.
- Do not encode a language/framework style guide into the cross-language Core Profile.
- A rule must be testable or reviewable: avoid slogans such as “handle errors well” or “write clean code.”
- Project-specific differences go in the Overlay; reusable cross-project obligations go in Core; repeated artifact/gate behavior may become a thin wrapper skill; fork upstream only when trigger, hard gate, artifact contract, or flow order fundamentally conflicts.
- Critical findings always block. Important findings block by default unless an authorized, time-bounded exception records ownership and compensating controls.
- Small changes scale down by applicability and risk, not by silently dropping applicable invariants.
- Every task ends with fresh verification and a focused commit.

---

## File Structure

```text
ai/coding-agent/agent-skills/
├── README.md                                      # finalize navigation
├── 06-production-profile/
│   ├── README.md
│   ├── 01-production-quality-model.md
│   ├── 02-core-profile.md
│   ├── 03-project-overlay-template.md
│   └── 04-integrating-with-skills.md
└── 07-adoption-playbook.md

ai/README.md                                       # add canonical entry
```

## Stable Identifiers

Core rule prefixes are fixed:

| Domain | Prefix |
|---|---|
| Requirements and Invariants | `REQ` |
| Data Consistency and Concurrency | `DAT` |
| Error Handling and Resilience | `RES` |
| Interface and Module Design | `MOD` |
| Compatibility and Migration | `CMP` |
| Security and Privacy | `SEC` |
| Performance and Capacity | `PER` |
| Observability and Operability | `OBS` |
| Testing and Verification | `TST` |
| Deployment, Rollback and Recovery | `DPL` |

IDs are stable references for specs, plans, review findings, exceptions, and later revisions. Renaming prose must not renumber an existing rule.

### Task 1: Establish the Production-Quality Model and Entry Point

**Files:**

- Create: `ai/coding-agent/agent-skills/06-production-profile/README.md`
- Create: `ai/coding-agent/agent-skills/06-production-profile/01-production-quality-model.md`

**Interfaces:**

- Consumes: the learning track’s workflow-vs-policy distinction and AI Review decision-system model.
- Produces: the four-layer production formula, applicability model, evidence categories, severity semantics, and rule schema used by every later profile artifact.

- [ ] **Step 1: Create the Production Profile entrypoint**

Create `06-production-profile/README.md` with:

```markdown
# Production Engineering Profile
## Policy Status
## 先給結論
## Why This Layer Exists
## The Four-Layer Formula
## Documents in This Section
## How to Use Core and Overlay
## Relationship to AI Code Review
## What This Does Not Replace
```

Required verdict: the skill libraries improve process reliability, but they cannot infer business invariants, criticality, data sensitivity, consistency semantics, external dependency budgets, SLOs, compatibility commitments, or recovery objectives that the project never supplied.

- [ ] **Step 2: Write the production-quality model**

Create `01-production-quality-model.md` with:

```markdown
# 01 - Production Quality Model
## Policy Status
## 先給結論
## The Four-Layer Formula
## Universal Baseline
## Project-Specific Invariants
## Executable Evidence
## Delivery Gate
## Applicability and Risk
## Rule Schema
## Severity and Exceptions
## Production-Ready Claim Boundary
## Worked Example: External Call
## Common Misreadings
## 一句話總結
```

The worked external-call example must take the vague statement “external calls need a timeout” and derive these concrete requirements:

- Project Overlay names the total time budget and per-attempt timeout;
- retry count/backoff depends on idempotency and remaining budget;
- fallback has an explicit business meaning and forbidden states;
- timeout/retry/fallback paths emit defined metrics and logs;
- tests inject timeout, partial success, retry exhaustion, and fallback behavior;
- review severity follows the dependency’s criticality and failure impact.

Define evidence categories: static contract, deterministic command, behavior test, failure-injection result, runtime/observability evidence, migration/rollback proof, and authorized risk record.

- [ ] **Step 3: Verify the model has all layers and no generic-quality slogans**

Run:

```bash
for layer in 'universal engineering baseline' 'project-specific invariants' 'executable evidence' 'delivery gate'; do rg -qi "$layer" ai/coding-agent/agent-skills/06-production-profile/01-production-quality-model.md || exit 1; done
for field in 'Rule ID' Applicability Requirement Rationale 'Required Evidence' 'Review Severity When Violated' 'Allowed Exception Process'; do rg -q "$field" ai/coding-agent/agent-skills/06-production-profile/01-production-quality-model.md || exit 1; done
rg -n 'time budget|per-attempt timeout|idempotency|fallback|metrics|failure-injection' ai/coding-agent/agent-skills/06-production-profile/01-production-quality-model.md
git diff --check
```

Expected: every layer, schema field, and external-call fact is found; checks exit zero.

- [ ] **Step 4: Commit the production-quality model**

```bash
git add ai/coding-agent/agent-skills/06-production-profile/README.md ai/coding-agent/agent-skills/06-production-profile/01-production-quality-model.md
git commit -m "docs(production-profile): define quality model"
```

### Task 2: Write the Cross-Language Core Profile

**Files:**

- Create: `ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md`

**Interfaces:**

- Consumes: Task 1’s seven-field rule schema, evidence categories, severity definitions, and exception requirements.
- Produces: 30 stable rules referenced by the Overlay, workflow integration, review findings, and adoption playbook.

- [ ] **Step 1: Create the document structure and applicability contract**

Use this section order:

```markdown
# 02 - Production Engineering Core Profile
## Policy Status
## How to Apply This Profile
## Severity and Exception Rules
## Rule Index
## 1. Requirements and Invariants
## 2. Data Consistency and Concurrency
## 3. Error Handling and Resilience
## 4. Interface and Module Design
## 5. Compatibility and Migration
## 6. Security and Privacy
## 7. Performance and Capacity
## 8. Observability and Operability
## 9. Testing and Verification
## 10. Deployment, Rollback and Recovery
## Profile Completion Checklist
```

The Rule Index lists all 30 IDs, titles, default applicability, and default severity. Applicability is decided explicitly as `applicable`, `not-applicable` with reason, or `deferred` with owner and decision date; silence is not a decision.

Every full rule entry begins with an H3 in the form ``### `REQ-001` - Observable requirements and invariants`` (using its actual ID and title), then renders all seven schema fields with their exact labels.

- [ ] **Step 2: Write Requirements and Data rules**

Create these full seven-field rule entries:

| ID | Requirement focus | Required evidence | Default severity |
|---|---|---|---|
| `REQ-001` | Name observable acceptance criteria and business invariants before implementation. | Spec links each invariant to scenarios and expected results. | Important |
| `REQ-002` | Declare system criticality, data sensitivity, affected actors, and failure impact. | Approved Overlay risk classification. | Important |
| `REQ-003` | Maintain traceability from requirement to plan task, implementation, test/evidence, and review finding. | Traceability table or linked artifacts. | Important |
| `DAT-001` | Define transaction/atomicity boundary and consistency model for every multi-step state change. | Transaction design plus failure-path test. | Critical |
| `DAT-002` | Define concurrency control, idempotency scope, duplicate handling, and ordering assumptions. | Race/replay test or formal reason it is not applicable. | Critical |
| `DAT-003` | Protect integrity with constraints where possible and define detection/reconciliation for residual inconsistency. | Schema/constraint evidence plus reconciliation procedure. | Critical |

Each rule’s rationale must distinguish application behavior, storage guarantees, and distributed/external side effects. `DAT-002` must state that retries do not create idempotency automatically.

- [ ] **Step 3: Write Resilience and Module rules**

Create:

| ID | Requirement focus | Required evidence | Default severity |
|---|---|---|---|
| `RES-001` | Classify errors, preserve causal context, and expose stable caller-facing semantics. | Error taxonomy plus failure tests. | Important |
| `RES-002` | Bound external work with total budget, per-attempt timeout, retry policy, and idempotency analysis. | Injected timeout/retry-exhaustion results and metrics. | Critical |
| `RES-003` | Define fallback, degradation, circuit/backpressure, and overload behavior without ambiguous success. | Degradation scenarios and operator signals. | Important |
| `MOD-001` | Give each module one responsibility behind a minimal, explicit interface. | Public-surface review and focused tests. | Important |
| `MOD-002` | Keep dependency direction toward stable domain interfaces; prevent infrastructure-shape leakage. | Dependency map or focused review evidence. | Important |
| `MOD-003` | Optimize readability and reuse through naming, cohesion, and justified abstraction—not speculative generalization. | Reviewer evidence showing duplicated policy or abstraction rationale. | Important |

`MOD-003` must explain that reuse is not measured by abstraction count; a direct cohesive implementation can be better than a premature generic framework.

- [ ] **Step 4: Write Compatibility and Security rules**

Create:

| ID | Requirement focus | Required evidence | Default severity |
|---|---|---|---|
| `CMP-001` | Define public API/event/schema compatibility and supported consumer transition. | Contract diff plus compatibility tests. | Critical |
| `CMP-002` | Make data migrations bounded, restartable, observable, and reversible or forward-recoverable. | Rehearsal output, data checks, and rollback/forward plan. | Critical |
| `CMP-003` | Use rollout sequencing that handles mixed versions and old/new data during transition. | Deployment sequence and mixed-version test. | Critical |
| `SEC-001` | Enforce authentication, authorization, least privilege, and deny-by-default boundaries. | Threat/permission matrix and negative tests. | Critical |
| `SEC-002` | Classify sensitive data and define secret storage, encryption, retention, redaction, and deletion. | Data-flow inventory plus configuration/runtime evidence. | Critical |
| `SEC-003` | Validate untrusted input and model abuse/threat paths at the owning boundary. | Threat model, validation tests, and security scan where applicable. | Critical |

State that a code review cannot accept unknown consumer compatibility or unknown authorization ownership as “probably safe.”

- [ ] **Step 5: Write Performance and Observability rules**

Create:

| ID | Requirement focus | Required evidence | Default severity |
|---|---|---|---|
| `PER-001` | Define latency, throughput, concurrency, payload, and resource budgets from an SLO/capacity model. | Approved budgets and representative measurements. | Important |
| `PER-002` | Measure critical paths with realistic data and preserve a reproducible baseline. | Benchmark/load profile, environment, and comparison. | Important |
| `PER-003` | Bound queues, batches, memory, connection pools, and fan-out; define overload backpressure. | Capacity/failure test and saturation signals. | Critical |
| `OBS-001` | Emit structured logs, metrics, and traces with stable correlation and bounded cardinality. | Signal examples and automated/runtime checks. | Important |
| `OBS-002` | Connect actionable alerts to SLO impact, ownership, dashboards, and runbooks. | Alert-to-runbook mapping and test signal. | Important |
| `OBS-003` | Preserve auditability while preventing secrets or sensitive payload leakage in telemetry. | Audit-event contract plus redaction test. | Critical |

Clarify that “add logs” is insufficient: every signal must name operator question, dimensions, retention/cardinality boundary, and expected response.

- [ ] **Step 6: Write Test and Delivery rules**

Create:

| ID | Requirement focus | Required evidence | Default severity |
|---|---|---|---|
| `TST-001` | Test observable behavior and named invariants, not implementation trivia or mocks alone. | Requirement-to-test mapping with red/green evidence for changes. | Important |
| `TST-002` | Cover applicable failure, concurrency, replay, compatibility, and contract boundaries. | Scenario matrix and deterministic outcomes. | Important |
| `TST-003` | Record exact fresh verification commands, environment assumptions, and complete outputs. | Re-runnable verification packet. | Important |
| `DPL-001` | Define rollout stages, health gates, abort criteria, rollback action, and rollback limitations. | Deployment rehearsal or reviewed runbook. | Critical |
| `DPL-002` | Define backup/restore, recovery point, recovery time, and post-recovery integrity checks. | Restore drill or equivalent recovery evidence. | Critical |
| `DPL-003` | Make go/no-go depend on unresolved findings, evidence freshness, owners, and time-bounded accepted risk. | Signed decision record and open-risk inventory. | Critical |

`DPL-001` must distinguish code rollback from data rollback. `DPL-002` must state that backup existence is not restore proof. `DPL-003` must prohibit aggregate scoring from masking Critical findings.

- [ ] **Step 7: Verify rule count, schema completeness, and domain coverage**

Run:

```bash
test "$(rg '^### `(REQ|DAT|RES|MOD|CMP|SEC|PER|OBS|TST|DPL)-[0-9]{3}`' ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md | wc -l | tr -d ' ')" = "30"
for prefix in REQ DAT RES MOD CMP SEC PER OBS TST DPL; do test "$(rg "^### \`$prefix-[0-9]{3}\`" ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md | wc -l | tr -d ' ')" = "3" || exit 1; done
test "$(rg -o 'Rule ID|Applicability|Requirement|Rationale|Required Evidence|Review Severity When Violated|Allowed Exception Process' ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md | wc -l | tr -d ' ')" -ge "210"
! rg -n 'handle errors well|write clean code|best practices apply' ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md
git diff --check
```

Expected: exactly 30 rule headings, three per prefix, at least `30 × 7 = 210` schema-field occurrences, no rejected slogan, and a clean diff check.

- [ ] **Step 8: Commit the Core Profile**

```bash
git add ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md
git commit -m "docs(production-profile): add core engineering rules"
```

### Task 3: Create the Project Overlay Template

**Files:**

- Create: `ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md`

**Interfaces:**

- Consumes: all 30 Core rule IDs and the AI Review packet contract.
- Produces: a copyable project-fact document whose answers can be cited by specs, plans, implementers, reviewers, and delivery gates.

- [ ] **Step 1: Create the template contract and completion semantics**

Use this section order:

```markdown
# 03 - Project Overlay Template
## Template Status and Copy Instructions
## Completion Rules
## 1. System Purpose and Risk Classification
## 2. Domain Vocabulary and Invariants
## 3. Data, Transactions, Concurrency, and Idempotency
## 4. External Dependencies and Resilience
## 5. Interfaces, Compatibility, and Migration
## 6. Security and Privacy
## 7. SLO, Capacity, and Performance Budgets
## 8. Observability and Operations
## 9. Testing and Verification
## 10. Deployment, Rollback, and Recovery
## 11. Language and Framework Conventions
## Rule Applicability Matrix
## Exception Register
## Approval and Review Cadence
## Worked Mini Example
```

The template is instructional, not blank: every table’s `Required answer` cell explains the concrete value and evidence format to supply. Copying teams replace the guidance cell with project facts and retain a link to evidence. No section may contain an empty table.

- [ ] **Step 2: Define exact required answers for system, domain, and data**

Require:

- system purpose, user impact, owners, criticality tier, regulated/sensitive data, and maximum tolerable impact;
- canonical domain terms, aggregate/ownership boundaries, state machines, invariants, forbidden states, and source of truth;
- transaction boundary, isolation/consistency model, write/read visibility, concurrency control, idempotency-key scope/retention/conflict behavior, event ordering/deduplication, and reconciliation.

Each answer row includes `Core rule`, `Required project fact`, `Evidence location`, and `Owner`.

- [ ] **Step 3: Define resilience, interface, security, and capacity answers**

Require one row per external dependency with: criticality, total budget, per-attempt timeout, retry/backoff, idempotency prerequisite, fallback semantic, circuit/bulkhead/backpressure, ownership, metric, and test.

Require:

- public API/event/schema owners, compatibility window, deprecation policy, mixed-version behavior, migration/rollback constraints;
- trust boundaries, actor/permission matrix, sensitive-data flow, secret ownership, retention/redaction/deletion, and abuse cases;
- SLOs, latency/throughput/concurrency/payload/resource budgets, load shape, growth assumption, saturation point, and capacity evidence.

- [ ] **Step 4: Define operations, verification, delivery, and conventions answers**

Require:

- structured log/metric/trace names, correlation keys, cardinality boundary, dashboards, alerts, runbooks, audit events, and redaction checks;
- test seams, exact commands, required happy/failure/concurrency/replay/compatibility scenarios, fixtures, environments, and evidence retention;
- rollout stages, health/abort gates, code rollback, data rollback/forward recovery, backup/restore/RPO/RTO, incident ownership, and recovery integrity checks;
- language/framework versions, canonical commands, module/import conventions, approved interface patterns, and project-specific static-analysis rules.

The conventions section must stay project-specific and must not be copied into Core merely because one repository uses it.

- [ ] **Step 5: Define applicability, exception, and approval records**

The Rule Applicability Matrix has one row per Core ID and records `applicable`, `not-applicable` with reason, or `deferred` with owner/date.

Every exception record requires:

```text
exception ID
Core rule ID
scope
decision owner
rationale
measured impact
compensating controls
verification evidence
approver
created date
expiry or mandatory review date
removal plan
```

The worked mini example fills one dependency row for a fictional payment-risk API and one `RES-002` applicability row with concrete values; label it illustrative, not a universal default.

- [ ] **Step 6: Verify all Core IDs and project-fact categories are represented**

Run:

```bash
comm -23 <(rg -o '(REQ|DAT|RES|MOD|CMP|SEC|PER|OBS|TST|DPL)-[0-9]{3}' ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md | sort -u) <(rg -o '(REQ|DAT|RES|MOD|CMP|SEC|PER|OBS|TST|DPL)-[0-9]{3}' ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md | sort -u)
for term in 'idempotency-key scope' 'per-attempt timeout' 'compatibility window' 'permission matrix' 'cardinality boundary' 'RPO' 'RTO' 'rollback' 'recovery integrity'; do rg -qi "$term" ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md || exit 1; done
rg -n 'exception ID|decision owner|compensating controls|expiry|removal plan' ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md
! rg -n '^\|[^|]*\|[[:space:]]*\|[[:space:]]*$' ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md
git diff --check
```

Expected: `comm` prints nothing, all categories and exception fields are present, no empty two-column data row is found, and diff check passes.

- [ ] **Step 7: Commit the Overlay template**

```bash
git add ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md
git commit -m "docs(production-profile): add project overlay template"
```

### Task 4: Integrate the Profile with Both Skill Libraries and AI Review

**Files:**

- Create: `ai/coding-agent/agent-skills/06-production-profile/04-integrating-with-skills.md`

**Interfaces:**

- Consumes: Superpowers lifecycle, Matt main flow, Core Profile, Overlay, and Production AI Code Review Protocol.
- Produces: stage-by-stage artifact injection rules plus an explicit Overlay/Core/wrapper/fork decision model.

- [ ] **Step 1: Map production facts through the delivery lifecycle**

Create `04-integrating-with-skills.md` with:

```markdown
# 04 - 把 Production Profile 接進 Agent Skills
## Policy Status
## 先給結論
## Integration Principle
## Brainstorm / Grill
## Spec
## Plan and Tickets
## TDD and Implementation
## AI Code Review
## Verification
## Merge / Delivery Gate
## Superpowers Integration Map
## Matt Pocock Integration Map
## Overlay vs Core vs Wrapper vs Fork
## Conflict Resolution
## Minimal Examples
## 一句話總結
```

For every workflow stage, state:

- which Core/Overlay inputs are consumed;
- what artifact must be produced or updated;
- what evidence is required before transition;
- what claims remain unavailable if facts are missing.

Use this fixed flow:

```text
brainstorm / grill
  -> identify applicable rules and invariants
spec
  -> turn them into acceptance criteria
plan / tickets
  -> map each criterion to implementation and evidence
TDD / implementation
  -> prove behavior at agreed seams
AI Code Review
  -> review against spec, Core, and Overlay
verification
  -> collect fresh command and runtime evidence
merge gate
  -> block unresolved Critical and unauthorized Important findings
```

- [ ] **Step 2: Define exact integration points for Superpowers and Matt**

For Superpowers, map Profile use into `brainstorming`, `writing-plans` Global Constraints/Interfaces, implementer task brief/report, task review packet, whole-branch review, verification, and branch completion. Clarify that editing upstream prompts is unnecessary when the controller can supply the artifacts as constraints.

For Matt, map it into `grill-with-docs`, `to-spec`, `to-tickets`, `implement`, `tdd`, `code-review`, `domain-modeling`, `codebase-design`, and `handoff`. Explain that Matt helpers can enrich a Superpowers primary lifecycle without duplicating the entire gate sequence.

- [ ] **Step 3: Write the customization decision tree**

Include a Mermaid decision tree with these terminal decisions:

```text
project-specific fact or threshold -> Project Overlay
cross-project invariant or evidence obligation -> Core Profile
same packet/schema/gate repeated across projects -> thin wrapper/orchestration skill
upstream trigger/hard gate/artifact/flow fundamentally incompatible -> fork upstream
one-off task difference -> task/spec instruction, not a new skill
```

Define fork cost: source drift monitoring, merge/rebase burden, skill testing, distribution, and user confusion. Default to composition unless a structural conflict is evidenced.

- [ ] **Step 4: Verify every stage and customization outcome**

Run:

```bash
for stage in 'Brainstorm / Grill' Spec 'Plan and Tickets' 'TDD and Implementation' 'AI Code Review' Verification 'Merge / Delivery Gate'; do rg -q "$stage" ai/coding-agent/agent-skills/06-production-profile/04-integrating-with-skills.md || exit 1; done
for outcome in 'Project Overlay' 'Core Profile' 'wrapper' 'fork upstream' 'task/spec instruction'; do rg -qi "$outcome" ai/coding-agent/agent-skills/06-production-profile/04-integrating-with-skills.md || exit 1; done
test "$(rg -c '^```mermaid$' ai/coding-agent/agent-skills/06-production-profile/04-integrating-with-skills.md)" -ge "1"
git diff --check
```

Expected: all lifecycle stages and decisions appear; at least one Mermaid decision diagram exists; diff check passes.

- [ ] **Step 5: Commit workflow integration**

```bash
git add ai/coding-agent/agent-skills/06-production-profile/04-integrating-with-skills.md
git commit -m "docs(production-profile): integrate rules with skills"
```

### Task 5: Add Adoption Playbook and Finalize Canonical Navigation

**Files:**

- Create: `ai/coding-agent/agent-skills/07-adoption-playbook.md`
- Modify: `ai/coding-agent/agent-skills/README.md`
- Modify: `ai/README.md`

**Interfaces:**

- Consumes: the complete learning track, review protocol/lab, Core Profile, Overlay, and integration policy.
- Produces: the canonical end-to-end entrypoint, risk-scaled adoption procedure, exception lifecycle, and upstream-refresh procedure.

- [ ] **Step 1: Write the adoption playbook**

Create `07-adoption-playbook.md` with:

```markdown
# 07 - Agent Skills 與 Production Profile Adoption Playbook
## 先給結論
## First Adoption in a New Project
## Referencing from AGENTS.md
## Choose a Primary Lifecycle
## Risk-Scaled Workflow
## Feature Entry
## Bug Entry
## Architecture Entry
## Review-Only Entry
## When to Create a Wrapper Skill
## Exception and Accepted-Risk Lifecycle
## Upstream Snapshot Refresh
## Governance Cadence
## Anti-Patterns
## Adoption Checklist
```

Define three risk tiers:

- `Tier S`: docs, comments, mechanically verified low-risk edits; run applicable deterministic checks and focused review, without spawning every semantic lens.
- `Tier M`: normal feature/bug work; use a primary lifecycle, applicable Core rules, completed Overlay facts, four fixed review axes, and risk lenses selected by change scope.
- `Tier H`: money, identity, authorization, sensitive data, migrations, concurrency, external irreversible side effects, or SLO-critical paths; require all applicable risk lenses, explicit human risk acceptance, rollout/rollback/recovery evidence, and whole-change review.

State that risk tier changes review depth, not the truth of an applicable invariant.

- [ ] **Step 2: Provide copyable project-instruction and exception patterns**

Include a concise `AGENTS.md` example that links rather than copies:

```markdown
## Production engineering

- Apply the Core Profile at `docs/engineering/production-core.md`.
- Project facts and exceptions live in `docs/engineering/project-overlay.md`.
- Specs and plans must cite applicable rule IDs.
- Code Review follows `docs/engineering/ai-code-review-protocol.md`.
- Do not approve unresolved Critical findings; Important exceptions require the Overlay exception record.
```

Explain that paths are examples to adapt. Give an accepted-risk lifecycle: proposed -> evidence reviewed -> authorized with expiry -> monitored -> removed/renewed. Expired exceptions become open findings.

- [ ] **Step 3: Define upstream refresh and drift handling**

The refresh procedure must:

1. record old/new commit and tag;
2. inspect changed README, SKILL, prompt, script, and distribution files;
3. re-index or otherwise refresh source discovery where applicable;
4. update snapshot facts before interpretations;
5. re-check lifecycle topology, artifacts, invocation, and review gates;
6. run documentation coverage/link checks and the fixture runner;
7. record whether local wrappers or Profile integration assumptions still hold.

Use the Superpowers `v5.1.0 -> v6.1.1` task-review change as a concrete drift example without treating the old topology as current.

- [ ] **Step 4: Finalize the root Agent Skills README**

Replace the staged “future production layer” prose with live links to all five `06-production-profile/` files and `07-adoption-playbook.md`. Ensure the root README offers:

- full linear reading order from `00` through `07`;
- task routes for feature, bug, review, architecture, production hardening, and upstream refresh;
- visible labels for descriptive, comparative, and normative documents;
- pinned source snapshots;
- direct lab runner command;
- archive link labeled historical-only.

- [ ] **Step 5: Add the canonical entry to `ai/README.md`**

Under `coding-agent/` in the directory tree, add:

```text
│   ├── agent-skills/         # 兩庫 workflow、AI Code Review、Production Profile
```

In `路线 B: 构建 Coding Agent`, add a third item after the build and production guides:

```markdown
3. [`coding-agent/agent-skills/README.md`](coding-agent/agent-skills/README.md) — 再建立 Coding Agent 的規範化工作流、AI Code Review gate 與 Production Engineering Profile
```

Do not rewrite unrelated AI learning routes.

- [ ] **Step 6: Run the complete repository-scoped verification**

Run the fixture gate:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
```

Expected: six PASS lines and `All 6 fixtures are valid.`

Run the Markdown link checker:

```bash
python3 -c 'from pathlib import Path; import re,sys; roots=[Path("ai/coding-agent/agent-skills"),Path("ai/README.md")]; files=[]; [files.extend(r.rglob("*.md")) if r.is_dir() else files.append(r) for r in roots]; bad=[]; [(bad.append((str(p),u)) if not (p.parent/u.split("#",1)[0]).resolve().exists() else None) for p in files for u in re.findall(r"\[[^]]+\]\(([^)]+)\)",p.read_text()) if u and not u.startswith(("http://","https://","#","/"))]; print("\n".join(f"{p}: {u}" for p,u in bad)); sys.exit(bool(bad))'
```

Expected: no output and exit zero.

Run coverage and hygiene checks:

```bash
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md | wc -l | tr -d ' ')" = "14"
test "$(rg '^### `[a-z0-9-]+`$' ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md ai/coding-agent/agent-skills/03-matt-pocock/03-quality-foundations-and-boundaries.md | wc -l | tr -d ' ')" = "12"
test "$(rg '^### `(REQ|DAT|RES|MOD|CMP|SEC|PER|OBS|TST|DPL)-[0-9]{3}`' ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md | wc -l | tr -d ' ')" = "30"
test "$(find ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures -name change.diff | wc -l | tr -d ' ')" = "6"
! rg -n 'T[B]D|T[O]DO|implemen[t] later|fill i[n] details' ai/coding-agent/agent-skills --glob '*.md'
rg -n 'agent-skills/README.md' ai/README.md
git diff --check
git status --short
```

Expected: counts are 14, 12, 30, and 6; no accidental placeholder marker; canonical AI README link exists; only Task 5 files are uncommitted.

- [ ] **Step 7: Commit adoption and final navigation**

```bash
git add ai/coding-agent/agent-skills/07-adoption-playbook.md ai/coding-agent/agent-skills/README.md ai/README.md
git commit -m "docs(agent-skills): add production adoption playbook"
```

## Plan Completion Gate

Use `superpowers:verification-before-completion` and run fresh:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
git status --short
git log --oneline --decorate --max-count=20
git diff --check 8b34827063f060cd2190ce60108ca49bca7ab0f2..HEAD
```

Then verify final file inventory:

```bash
for artifact in \
  ai/coding-agent/agent-skills/README.md \
  ai/coding-agent/agent-skills/00-agent-skills-mental-model.md \
  ai/coding-agent/agent-skills/01-two-libraries-workflow-map.md \
  ai/coding-agent/agent-skills/02-superpowers/02-all-skills-guide.md \
  ai/coding-agent/agent-skills/03-matt-pocock/02-core-skills-guide.md \
  ai/coding-agent/agent-skills/04-comparison-and-composition.md \
  ai/coding-agent/agent-skills/05-ai-code-review/03-production-review-protocol.md \
  ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py \
  ai/coding-agent/agent-skills/06-production-profile/02-core-profile.md \
  ai/coding-agent/agent-skills/06-production-profile/03-project-overlay-template.md \
  ai/coding-agent/agent-skills/07-adoption-playbook.md; do test -f "$artifact" || exit 1; done
```

Expected:

- all six fixtures pass;
- worktree is clean;
- the diff from the fixed base passes whitespace checks;
- every canonical artifact exists;
- the final navigation answers the user’s original questions: what each library is for, how they differ, why their output may not be production-ready, how to add project policy without casually forking, and how AI Code Review becomes a measurable merge gate.
