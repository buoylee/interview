# AI Code Review Protocol and Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an evidence-backed AI Code Review protocol and a deterministic six-fixture lab that can compare review strategies without any vendor API integration.

**Architecture:** Separate deterministic evidence, semantic review axes, finding verification, and delivery decisions. Use review packets and fresh context to constrain reviewer inputs, then evaluate review quality against hidden answer keys while a standard-library runner proves every buggy/fixed fixture behaves as declared.

**Tech Stack:** Traditional-Chinese Markdown, Mermaid, Python 3 standard library (`unittest`, `subprocess`, `difflib`, `pathlib`, `dataclasses`, `json`), Git, and local pinned skill sources.

## Global Constraints

- Execute after `2026-07-21-agent-skills-learning-foundations.md` has completed cleanly.
- Work only in `/Users/buoy/Development/gitrepo/interview/.worktrees/agent-skills-learning` on branch `codex/agent-skills-learning`.
- Superpowers analysis is pinned to `d884ae04edebef577e82ff7c4e143debd0bbec99` (`v6.1.1`).
- Matt Pocock analysis is pinned to `ed37663cc5fbef691ddfecd080dff42f7e7e350d` (`v1.1.0-40-ged37663`).
- Upstream mechanism descriptions are descriptive; the Production Review Protocol and finding contract are explicitly labeled `本專題定義`.
- The protocol flow is exactly `Preflight -> deterministic checks -> independent review axes -> finding verification -> aggregation without masking -> fix -> re-review -> go/no-go`.
- Fixed review axes are Spec Compliance, Correctness and Domain Invariants, Architecture and Maintainability, and Test Quality.
- Conditional risk lenses are Security, Reliability and Fallback, Performance and Capacity, Observability and Operability, and Data Migration and Compatibility.
- The implementer cannot approve their own work; semantic review uses fresh context and a bounded review packet.
- A finding without evidence is `needs-verification`, not a blocking defect.
- Never collapse a Critical finding into a passing aggregate score.
- The lab contains exactly six fixtures: data consistency, idempotency, timeout/retry/fallback, interface coupling, error handling, and misleading tests.
- Every fixture is offline, deterministic, and uses only Python standard library code.
- The normal project test passes for both the buggy and fixed candidate; the hidden verification test fails for buggy and passes for fixed.
- Answer keys are outside the reviewer input fixture directories.
- The initial version does not call a model API, require an API key, or claim to benchmark model intelligence automatically.
- Every task ends with fresh verification and a focused commit.

---

## File Structure

```text
ai/coding-agent/agent-skills/05-ai-code-review/
├── README.md
├── 01-mental-model.md
├── 02-two-library-mechanisms.md
├── 03-production-review-protocol.md
├── 04-evaluation-and-lab.md
└── lab/
    ├── README.md
    ├── fixtures/
    │   ├── 01-data-consistency/
    │   │   ├── spec.md
    │   │   ├── project-overlay.md
    │   │   ├── before.py
    │   │   ├── buggy.py
    │   │   ├── fixed.py
    │   │   ├── project_test.py
    │   │   ├── verification_test.py
    │   │   └── change.diff
    │   ├── 02-idempotency/              # same eight-file contract
    │   ├── 03-timeout-retry-fallback/   # same eight-file contract
    │   ├── 04-interface-coupling/       # same eight-file contract
    │   ├── 05-error-handling/           # same eight-file contract
    │   └── 06-misleading-tests/         # same eight-file contract
    ├── answer-key/
    │   ├── 01-data-consistency.md
    │   ├── 02-idempotency.md
    │   ├── 03-timeout-retry-fallback.md
    │   ├── 04-interface-coupling.md
    │   ├── 05-error-handling.md
    │   └── 06-misleading-tests.md
    ├── results-template.md
    └── run-fixtures.py
```

## Shared Fixture Contract

Every fixture uses the same module selection mechanism:

```python
import importlib
import os

implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])
```

`FIXTURE_VARIANT` is always `buggy` or `fixed`. `before.py` represents the review base, `buggy.py` is the candidate diff shown to the reviewer, `fixed.py` is used only by the evaluator, `project_test.py` represents plausible visible tests, and `verification_test.py` is the hidden oracle. `change.diff` is a deterministic unified diff from `before.py` to `buggy.py` with labels `a/implementation.py` and `b/implementation.py`.

Every answer key contains these exact headings:

```markdown
## Defect ID
## Expected lens
## Expected severity
## Evidence
## Why project_test misses it
## Fixed evidence
## Scope boundary
```

### Task 1: Establish the AI Code Review Mental Model and Upstream Evidence

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/README.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/01-mental-model.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/02-two-library-mechanisms.md`
- Modify: `ai/coding-agent/agent-skills/README.md`

**Interfaces:**

- Consumes: foundation terminology, Superpowers `v6.1.1` task-review artifacts, and Matt `code-review` source behavior.
- Produces: the review-system vocabulary and source-backed mechanism boundary consumed by Task 2.

- [ ] **Step 1: Create the topic entrypoint and reading routes**

Create `05-ai-code-review/README.md` with:

```markdown
# AI Code Review：從第二雙眼睛到工程決策系統
## 先給結論
## 這個專題解決什麼
## 閱讀順序
## 按角色跳讀
## Descriptive and Normative Boundary
## Lab Entry
## Success Boundary
```

Required verdict: an AI reviewer is neither a linter nor an oracle; useful review combines fixed inputs, independent semantic lenses, reproducible evidence, explicit severity, re-review, and a delivery decision.

At this task boundary, link only `01-mental-model.md` and `02-two-library-mechanisms.md`. Describe the protocol and lab as the next delivery stage without creating links to files that do not yet exist; Task 7 replaces that staged note with complete live navigation.

- [ ] **Step 2: Write the end-to-end mental model**

Create `01-mental-model.md` with:

```markdown
# 01 - AI Code Review 心智模型
## 先給結論
## Review Is a Decision System
## The Eight-Stage Loop
## Deterministic Evidence vs Semantic Judgment
## Context Isolation and Confirmation Bias
## Review Packet as an Interface
## Independent Axes and Risk Lenses
## Findings Are Claims to Verify
## Re-review and Decision State
## Human Responsibility
## 一句話總結
```

Include a Mermaid state/flow diagram for the exact eight-stage loop. Define three separate boundaries:

- `candidate truth`: the fixed diff and repository state;
- `review claim`: a reviewer’s evidence-backed allegation;
- `delivery decision`: go/no-go after findings are verified, fixed, disputed, or explicitly accepted.

Explain why implementer self-review is useful as preflight but cannot be the only approval gate.

- [ ] **Step 3: Reconstruct both upstream review mechanisms without blending them**

Create `02-two-library-mechanisms.md` with:

```markdown
# 02 - 兩個 Skill 庫的 Code Review 機制
## 先給結論
## Superpowers v6.1.1 Task Review
## Superpowers Whole-Branch Review
## Superpowers Receiving Review
## Matt Pocock code-review
## Side-by-Side Mechanism Matrix
## Guarantees and Non-Guarantees
## What This Project Adds
```

Superpowers task review must name: pre-flight plan check, task brief, implementer report, durable progress ledger, fixed base/head review package, one fresh task reviewer, ordered Spec Compliance and Code Quality verdicts, Critical/Important re-review, Minor carry-forward, and final broad branch review. Cite these exact source paths:

- `skills/subagent-driven-development/SKILL.md`
- `skills/subagent-driven-development/implementer-prompt.md`
- `skills/subagent-driven-development/task-reviewer-prompt.md`
- `skills/subagent-driven-development/scripts/task-brief`
- `skills/subagent-driven-development/scripts/review-package`
- `skills/subagent-driven-development/scripts/sdd-workspace`
- `skills/requesting-code-review/SKILL.md`
- `skills/requesting-code-review/code-reviewer.md`
- `skills/receiving-code-review/SKILL.md`

Matt analysis must cite `skills/engineering/code-review/SKILL.md` and explain fixed base, separate Standards/Spec concerns, repository standards precedence, and independent findings without inventing a score.

Begin `02-two-library-mechanisms.md` with two source-card tables containing library name, local path, pinned commit/tag, verified date `2026-07-21`, and the primary source paths above. Treat all version-sensitive statements as snapshot facts.

- [ ] **Step 4: Add live Code Review navigation to the root track**

Replace the foundation README’s prose-only future-Code-Review note with links to:

- `05-ai-code-review/README.md`
- `05-ai-code-review/01-mental-model.md`
- `05-ai-code-review/02-two-library-mechanisms.md`

Keep Production Profile as prose-only future scope until the third plan creates it.

- [ ] **Step 5: Verify snapshot semantics and documentation boundaries**

Run:

```bash
rg -n 'd884ae04edebef577e82ff7c4e143debd0bbec99|ed37663cc5fbef691ddfecd080dff42f7e7e350d' ai/coding-agent/agent-skills/05-ai-code-review
rg -n 'task brief|implementer report|review package|progress ledger|whole-branch' ai/coding-agent/agent-skills/05-ai-code-review/02-two-library-mechanisms.md
rg -n '本專題定義|Descriptive|Normative' ai/coding-agent/agent-skills/05-ai-code-review
! rg -n 'two separate reviewer|兩個獨立 reviewer' ai/coding-agent/agent-skills/05-ai-code-review
git diff --check
```

Expected: both snapshots are cited, all v6.1.1 artifacts are explained, the local/upstream boundary is explicit, and no obsolete reviewer topology appears.

- [ ] **Step 6: Commit the mental model and source mechanisms**

```bash
git add ai/coding-agent/agent-skills/README.md ai/coding-agent/agent-skills/05-ai-code-review/README.md ai/coding-agent/agent-skills/05-ai-code-review/01-mental-model.md ai/coding-agent/agent-skills/05-ai-code-review/02-two-library-mechanisms.md
git commit -m "docs(ai-review): define mental model and source mechanisms"
```

### Task 2: Define the Production Review Protocol and Evaluation Contract

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/03-production-review-protocol.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/04-evaluation-and-lab.md`

**Interfaces:**

- Consumes: Task 1’s review vocabulary and upstream/non-upstream boundary.
- Produces: the exact review packet, axes, finding schema, state transitions, merge gate, experimental matrix, and metrics used by lab result records.

- [ ] **Step 1: Write the executable Production Review Protocol**

Create `03-production-review-protocol.md` with:

```markdown
# 03 - Production AI Code Review Protocol
## Policy Status
## Preconditions and Abort Conditions
## Stage 1: Preflight
## Stage 2: Deterministic Checks
## Stage 3: Build the Review Packet
## Stage 4: Dispatch Independent Review Axes
## Stage 5: Verify Findings
## Stage 6: Aggregate Without Masking
## Stage 7: Fix and Re-review
## Stage 8: Go / No-Go
## Finding Contract
## Severity and Confidence Calibration
## Accepted Risk and Disputes
## Small-Change Scaling
## Copyable Reviewer Instructions
## Completion Checklist
```

The review packet must require:

- merge-base/fixed point, head, commit list, and full diff;
- originating spec/issue and acceptance criteria;
- repository instructions, ADRs, applicable Core Profile rules, and Project Overlay facts;
- fresh test, typecheck, lint, build, security, and migration outputs that actually apply;
- declared data, interface, compatibility, operational, and rollout risk boundaries.

Define abort conditions: missing diff, unknown review base, missing spec for a Spec Compliance claim, missing invariant for a consistency claim, or stale/failed deterministic evidence.

The finding schema must contain exactly: `id`, `lens`, `severity`, `confidence`, `location`, `rule`, `impact`, `evidence`, `direction`, `verification`, and `status`. Allowed status values are `needs-verification`, `open`, `disputed`, `accepted-risk`, `fixed`, and `verified`.

Define severity:

- `Critical`: credible path to data loss/corruption, security boundary violation, irreversible incompatibility, or unbounded severe outage; always blocks.
- `Important`: correctness, resilience, maintainability, or evidence gap that makes the change untrustworthy; blocks by default.
- `Minor`: bounded polish or maintainability improvement that does not invalidate the delivery claim; does not block but remains visible.

The gate must never average severities. Go requires all applicable deterministic checks passing, zero unresolved Critical findings, every Important finding either verified fixed or explicitly accepted by an authorized human, and re-review evidence for changed findings.

- [ ] **Step 2: Define a reproducible evaluation, not a model leaderboard**

Create `04-evaluation-and-lab.md` with:

```markdown
# 04 - 如何評估 AI Code Review
## 先給結論
## What the Lab Measures
## What the Lab Does Not Measure
## Six Fixture Families
## Experimental Matrix
## Metrics
## Answer-Key Isolation
## Running a Review Trial
## Comparing Results
## Cost and Latency Recording
## Threats to Validity
## Promotion Criteria for a Review Strategy
```

The experimental matrix must compare:

- implementer self-review vs fresh-context review;
- single generic review vs four fixed axes plus applicable risk lenses;
- with vs without Core Profile/Project Overlay;
- initial review vs re-review after fixes.

Define metric formulas:

```text
confirmed-defect recall = confirmed expected defects found / total expected defects
false-positive rate = disproven findings / all findings
evidence rate = findings with reproducible evidence / all findings
actionability rate = findings with location + rule + impact + verification / all findings
severity calibration = findings whose severity matches answer key / matched findings
stability = findings reproduced across repeated runs / union of repeated-run findings
```

Record token/cost proxy and latency but do not combine them into a quality score.

- [ ] **Step 3: Verify protocol completeness and executable wording**

Run:

```bash
for field in id lens severity confidence location rule impact evidence direction verification status; do rg -q "\`$field\`" ai/coding-agent/agent-skills/05-ai-code-review/03-production-review-protocol.md || exit 1; done
for stage in Preflight 'Deterministic Checks' 'Build the Review Packet' 'Dispatch Independent Review Axes' 'Verify Findings' 'Aggregate Without Masking' 'Fix and Re-review' 'Go / No-Go'; do rg -q "$stage" ai/coding-agent/agent-skills/05-ai-code-review/03-production-review-protocol.md || exit 1; done
rg -n 'confirmed-defect recall|false-positive rate|evidence rate|actionability rate|severity calibration|stability' ai/coding-agent/agent-skills/05-ai-code-review/04-evaluation-and-lab.md
git diff --check
```

Expected: every field, stage, and metric is found; checks exit zero.

- [ ] **Step 4: Commit the protocol and evaluation contract**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review/03-production-review-protocol.md ai/coding-agent/agent-skills/05-ai-code-review/04-evaluation-and-lab.md
git commit -m "docs(ai-review): add production review protocol"
```

### Task 3: Define the Lab Interface and Results Record

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/README.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/results-template.md`

**Interfaces:**

- Consumes: Task 2’s packet, finding, metric, and experiment contracts.
- Produces: one stable fixture protocol and one result-record schema used by all six fixture tasks and future manual AI review trials.

- [ ] **Step 1: Write the lab README as an operator runbook**

Create `lab/README.md` with:

```markdown
# AI Code Review Evaluation Lab
## Purpose
## Directory Contract
## Reviewer Input Boundary
## Evaluator-Only Boundary
## Candidate Variants
## Deterministic Runner Semantics
## Manual AI Review Procedure
## Result Recording
## Adding a Fixture
## Limitations
```

The runbook must state:

- reviewer input is `spec.md`, `project-overlay.md`, `change.diff`, `buggy.py`, and visible `project_test.py` output;
- `fixed.py`, `verification_test.py`, and `answer-key/` are evaluator-only until the initial review is frozen;
- buggy project tests must pass, buggy hidden verification must fail, and both fixed suites must pass;
- an expected buggy failure is a valid fixture result, while import errors, missing files, stale diffs, or a fixed failure are harness failures;
- AI trials run in the existing Coding Agent harness and are copied into `results-template.md`; the runner never calls a provider.

- [ ] **Step 2: Create a non-empty results schema with one worked example row**

Create `results-template.md` with these sections:

```markdown
# AI Code Review Trial Result
## Run Identity
## Review Mode
## Input Packet
## Raw Findings
## Normalized Findings
## Answer-Key Comparison
## Metrics
## Re-review
## Cost and Latency
## Decision
## Worked Example
```

Each section must explain the exact value to record. `Normalized Findings` uses all 11 finding fields. `Run Identity` records date, harness, model/provider/version, temperature or equivalent, and run ID. `Worked Example` contains one clearly labeled synthetic row so the template is never an empty shell.

- [ ] **Step 3: Verify reviewer/evaluator separation**

Run:

```bash
rg -n 'Reviewer Input Boundary|Evaluator-Only Boundary|buggy|fixed|answer-key' ai/coding-agent/agent-skills/05-ai-code-review/lab/README.md
for field in id lens severity confidence location rule impact evidence direction verification status; do rg -q "\`$field\`" ai/coding-agent/agent-skills/05-ai-code-review/lab/results-template.md || exit 1; done
rg -n 'Worked Example|model|harness|latency|cost' ai/coding-agent/agent-skills/05-ai-code-review/lab/results-template.md
git diff --check
```

Expected: all checks exit zero and the template contains a worked example.

- [ ] **Step 4: Commit the lab contract**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review/lab/README.md ai/coding-agent/agent-skills/05-ai-code-review/lab/results-template.md
git commit -m "docs(ai-review): define evaluation lab contract"
```

### Task 4: Add Data Consistency and Idempotency Fixtures

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/01-data-consistency/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/02-idempotency/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/01-data-consistency.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/02-idempotency.md`

**Interfaces:**

- Consumes: the shared fixture contract.
- Produces: two deterministic cases whose visible tests pass for both variants and whose hidden tests distinguish buggy from fixed.

- [ ] **Step 1: Write the data-consistency base, buggy candidate, and fixed candidate**

Use this base in `01-data-consistency/before.py`:

```python
class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)

    def balance(self, account_id):
        return self.balances[account_id]
```

Use this candidate in `buggy.py`:

```python
class AccountNotFound(LookupError):
    pass


class InsufficientFunds(ValueError):
    pass


class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)

    def balance(self, account_id):
        return self.balances[account_id]

    def transfer(self, source_id, target_id, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        if source_id not in self.balances:
            raise AccountNotFound(source_id)
        if self.balances[source_id] < amount:
            raise InsufficientFunds(source_id)

        self.balances[source_id] -= amount
        if target_id not in self.balances:
            raise AccountNotFound(target_id)
        self.balances[target_id] += amount
```

Use this correction in `fixed.py`:

```python
class AccountNotFound(LookupError):
    pass


class InsufficientFunds(ValueError):
    pass


class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)

    def balance(self, account_id):
        return self.balances[account_id]

    def transfer(self, source_id, target_id, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        if source_id not in self.balances:
            raise AccountNotFound(source_id)
        if target_id not in self.balances:
            raise AccountNotFound(target_id)
        if self.balances[source_id] < amount:
            raise InsufficientFunds(source_id)

        new_source_balance = self.balances[source_id] - amount
        new_target_balance = self.balances[target_id] + amount
        self.balances[source_id] = new_source_balance
        self.balances[target_id] = new_target_balance
```

- [ ] **Step 2: Write visible and hidden data-consistency tests**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class LedgerProjectTest(unittest.TestCase):
    def test_successful_transfer_moves_money(self):
        ledger = implementation.Ledger({"source": 100, "target": 20})
        ledger.transfer("source", "target", 30)
        self.assertEqual(ledger.balance("source"), 70)
        self.assertEqual(ledger.balance("target"), 50)


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class LedgerVerificationTest(unittest.TestCase):
    def test_failed_transfer_leaves_every_balance_unchanged(self):
        ledger = implementation.Ledger({"source": 100, "target": 20})
        before = dict(ledger.balances)

        with self.assertRaises(implementation.AccountNotFound):
            ledger.transfer("source", "missing", 30)

        self.assertEqual(ledger.balances, before)


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires positive amounts, account existence, sufficient funds, conservation of total balance, and atomic failure. `project-overlay.md` states balances represent monetary value and no caller may observe a partial transfer. The answer key uses defect `CONS-001`, lens `Correctness and Domain Invariants`, severity `Critical`, and points to mutation before target validation.

- [ ] **Step 3: Write the idempotency base, buggy candidate, and fixed candidate**

Use this `02-idempotency/before.py`:

```python
class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway

    def charge(self, amount_cents):
        return self.gateway.capture(amount_cents)
```

Use this `buggy.py`:

```python
class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway

    def charge(self, idempotency_key, amount_cents):
        return self.gateway.capture(amount_cents)
```

Use this `fixed.py`:

```python
class IdempotencyConflict(ValueError):
    pass


class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway
        self._completed = {}

    def charge(self, idempotency_key, amount_cents):
        completed = self._completed.get(idempotency_key)
        if completed is not None:
            recorded_amount, receipt = completed
            if recorded_amount != amount_cents:
                raise IdempotencyConflict(idempotency_key)
            return receipt

        receipt = self.gateway.capture(amount_cents)
        self._completed[idempotency_key] = (amount_cents, receipt)
        return receipt
```

- [ ] **Step 4: Write visible and hidden idempotency tests**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class Gateway:
    def __init__(self):
        self.calls = []

    def capture(self, amount_cents):
        self.calls.append(amount_cents)
        return f"receipt-{len(self.calls)}"


class PaymentProjectTest(unittest.TestCase):
    def test_first_charge_returns_gateway_receipt(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)
        self.assertEqual(service.charge("order-7", 2500), "receipt-1")


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class Gateway:
    def __init__(self):
        self.calls = []

    def capture(self, amount_cents):
        self.calls.append(amount_cents)
        return f"receipt-{len(self.calls)}"


class PaymentVerificationTest(unittest.TestCase):
    def test_duplicate_delivery_does_not_repeat_capture(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)

        first = service.charge("order-7", 2500)
        second = service.charge("order-7", 2500)

        self.assertEqual(second, first)
        self.assertEqual(gateway.calls, [2500])

    def test_same_key_with_different_amount_is_rejected(self):
        gateway = Gateway()
        service = implementation.PaymentService(gateway)
        service.charge("order-7", 2500)

        conflict_type = getattr(implementation, "IdempotencyConflict", None)
        if conflict_type is None:
            self.fail("IDEM-001 idempotency-key payload conflict is not detected")
        with self.assertRaises(conflict_type):
            service.charge("order-7", 3000)
        self.assertEqual(gateway.calls, [2500])


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires same-key/same-payload replay without another gateway call and same-key/different-payload rejection. `project-overlay.md` explicitly limits the guarantee to repeated delivery in one process; it does not claim crash-safe exactly-once payment. The answer key uses defect `IDEM-001`, lens `Correctness and Domain Invariants`, severity `Critical`, and names the repeated external side effect.

- [ ] **Step 5: Run the four variant/test combinations for both fixtures**

Run in each fixture directory:

```bash
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q verification_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q verification_test.py
```

Expected per fixture: first command exits 0, second exits nonzero with the named invariant failure, third exits 0, fourth exits 0. The nonzero buggy verification is expected evidence, not a task failure.

- [ ] **Step 6: Commit the two fixtures**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/01-data-consistency ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/02-idempotency ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/01-data-consistency.md ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/02-idempotency.md
git commit -m "test(ai-review): add consistency and idempotency fixtures"
```

### Task 5: Add Resilience and Interface-Coupling Fixtures

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/03-timeout-retry-fallback/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/04-interface-coupling/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/03-timeout-retry-fallback.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/04-interface-coupling.md`

**Interfaces:**

- Consumes: the shared fixture contract.
- Produces: one explicit time-budget/fallback case and one dependency-direction case.

- [ ] **Step 1: Write the timeout/retry/fallback variants**

Use this `03-timeout-retry-fallback/before.py`:

```python
def fetch_profile(client, user_id):
    return client.get(user_id)
```

Use this `buggy.py`:

```python
def fetch_profile(client, user_id):
    for _ in range(3):
        try:
            return client.get(user_id)
        except TimeoutError:
            pass
    return {}
```

Use this `fixed.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileResult:
    status: str
    profile: object
    attempts: int
    error: object


def fetch_profile(
    client,
    user_id,
    *,
    timeout_seconds=0.05,
    max_attempts=2,
):
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    for attempt in range(1, max_attempts + 1):
        try:
            profile = client.get(user_id, timeout=timeout_seconds)
            return ProfileResult("ok", profile, attempt, None)
        except TimeoutError:
            if attempt == max_attempts:
                return ProfileResult(
                    "degraded",
                    None,
                    attempt,
                    "upstream-timeout",
                )

    raise AssertionError("unreachable")
```

- [ ] **Step 2: Write visible and hidden resilience tests**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class HealthyClient:
    def get(self, user_id, timeout=None):
        return {"id": user_id, "name": "Ada"}


class ProfileProjectTest(unittest.TestCase):
    def test_returns_profile_when_dependency_is_healthy(self):
        result = implementation.fetch_profile(HealthyClient(), "user-1")
        profile = result.profile if hasattr(result, "profile") else result
        self.assertEqual(profile, {"id": "user-1", "name": "Ada"})


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class TimingOutClient:
    def __init__(self):
        self.timeouts = []

    def get(self, user_id, timeout=None):
        self.timeouts.append(timeout)
        raise TimeoutError(user_id)


class ProfileVerificationTest(unittest.TestCase):
    def test_timeout_budget_retry_cap_and_fallback_are_explicit(self):
        client = TimingOutClient()
        result = implementation.fetch_profile(client, "user-1")

        self.assertEqual(
            client.timeouts,
            [0.05, 0.05],
            "RES-001 calls must carry a bounded timeout and retry cap",
        )
        self.assertEqual(result.status, "degraded")
        self.assertIsNone(result.profile)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.error, "upstream-timeout")


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires a 100 ms total request budget, at most two 50 ms attempts, propagation of non-timeout exceptions, and an explicit degraded result after timeouts. `project-overlay.md` states that an empty profile and dependency failure are different business states. The answer key uses `RES-001`, lens `Reliability and Fallback`, severity `Important`, and cites the missing timeout plus ambiguous `{}` fallback.

- [ ] **Step 3: Write the interface-coupling variants**

Use this `04-interface-coupling/before.py`:

```python
class OrderSummaryService:
    def summary(self, customer_id, orders):
        total = sum(
            row["amount_cents"]
            for row in orders
            if row["customer_id"] == customer_id
        )
        return {"customer_id": customer_id, "total_cents": total}
```

Use this `buggy.py`:

```python
class OrderSummaryService:
    def __init__(self, repository):
        self.repository = repository

    def summary(self, customer_id):
        rows = self.repository.connection.orders
        total = sum(
            row["amount_cents"]
            for row in rows
            if row["customer_id"] == customer_id
        )
        return {"customer_id": customer_id, "total_cents": total}
```

Use this `fixed.py`:

```python
from typing import Protocol


class OrderRepository(Protocol):
    def total_for_customer(self, customer_id):
        ...


class OrderSummaryService:
    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def summary(self, customer_id):
        return {
            "customer_id": customer_id,
            "total_cents": self.repository.total_for_customer(customer_id),
        }
```

- [ ] **Step 4: Write visible and hidden interface tests**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class Connection:
    orders = [
        {"customer_id": "c-1", "amount_cents": 1200},
        {"customer_id": "c-1", "amount_cents": 300},
        {"customer_id": "c-2", "amount_cents": 900},
    ]


class CompatibleRepository:
    def __init__(self):
        self.connection = Connection()

    def total_for_customer(self, customer_id):
        return sum(
            row["amount_cents"]
            for row in self.connection.orders
            if row["customer_id"] == customer_id
        )


class SummaryProjectTest(unittest.TestCase):
    def test_calculates_customer_total(self):
        service = implementation.OrderSummaryService(CompatibleRepository())
        self.assertEqual(
            service.summary("c-1"),
            {"customer_id": "c-1", "total_cents": 1500},
        )


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class InterfaceOnlyRepository:
    def total_for_customer(self, customer_id):
        return 1500


class SummaryVerificationTest(unittest.TestCase):
    def test_service_depends_only_on_repository_interface(self):
        service = implementation.OrderSummaryService(InterfaceOnlyRepository())
        try:
            result = service.summary("c-1")
        except AttributeError as exc:
            self.fail(f"ARCH-001 service leaked persistence internals: {exc}")

        self.assertEqual(
            result,
            {"customer_id": "c-1", "total_cents": 1500},
        )


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires `OrderSummaryService` to depend only on a repository method that returns the total. `project-overlay.md` defines `total_for_customer(customer_id)` as the stable seam and makes connection/storage layout private. The answer key uses `ARCH-001`, lens `Architecture and Maintainability`, severity `Important`, and cites dependency inversion plus the leaked `.connection.orders` shape.

- [ ] **Step 5: Run all four combinations for both fixtures**

Run in `03-timeout-retry-fallback/`:

```bash
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q verification_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q verification_test.py
```

Run the identical explicit sequence in `04-interface-coupling/`:

```bash
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q verification_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q verification_test.py
```

Expected: buggy project passes; buggy verification fails with `RES-001` or `ARCH-001`; fixed project and fixed verification pass.

- [ ] **Step 6: Commit the two fixtures**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/03-timeout-retry-fallback ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/04-interface-coupling ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/03-timeout-retry-fallback.md ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/04-interface-coupling.md
git commit -m "test(ai-review): add resilience and interface fixtures"
```

### Task 6: Add Error-Handling and Misleading-Test Fixtures

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/05-error-handling/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/06-misleading-tests/{spec.md,project-overlay.md,before.py,buggy.py,fixed.py,project_test.py,verification_test.py}`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/05-error-handling.md`
- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/06-misleading-tests.md`

**Interfaces:**

- Consumes: the shared fixture contract.
- Produces: one error-classification case and one case proving that green visible tests can still fail the actual spec.

- [ ] **Step 1: Write the error-handling variants**

Use this `05-error-handling/before.py`:

```python
import json


def load_config(raw):
    return json.loads(raw)
```

Use this `buggy.py`:

```python
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    timeout_ms: int


def load_config(raw):
    try:
        data = json.loads(raw)
        return Config(timeout_ms=int(data["timeout_ms"]))
    except Exception:
        return Config(timeout_ms=1000)
```

Use this `fixed.py`:

```python
import json
from dataclasses import dataclass


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    timeout_ms: int


def load_config(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError("config must be valid JSON") from exc

    try:
        timeout_ms = data["timeout_ms"]
    except (KeyError, TypeError) as exc:
        raise ConfigError("timeout_ms is required") from exc

    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise ConfigError("timeout_ms must be an integer")
    if timeout_ms <= 0:
        raise ConfigError("timeout_ms must be positive")
    return Config(timeout_ms=timeout_ms)
```

- [ ] **Step 2: Write visible and hidden error-handling tests**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class ConfigProjectTest(unittest.TestCase):
    def test_loads_valid_timeout(self):
        config = implementation.load_config('{"timeout_ms": 250}')
        self.assertEqual(config.timeout_ms, 250)


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import json
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class ConfigVerificationTest(unittest.TestCase):
    def test_invalid_json_is_classified_and_preserves_cause(self):
        error_type = getattr(implementation, "ConfigError", None)
        if error_type is None:
            self.fail("ERR-001 invalid input is silently replaced by a default")

        with self.assertRaises(error_type) as captured:
            implementation.load_config("{")
        self.assertIsInstance(captured.exception.__cause__, json.JSONDecodeError)

    def test_missing_timeout_is_not_silently_defaulted(self):
        error_type = getattr(implementation, "ConfigError", None)
        if error_type is None:
            self.fail("ERR-001 missing input is silently replaced by a default")
        with self.assertRaises(error_type):
            implementation.load_config("{}")


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires invalid/missing values to fail with `ConfigError`, preserve parse causes, and reject non-positive/non-integer timeouts. `project-overlay.md` states that silent defaults can alter production dependency budgets and are forbidden. The answer key uses `ERR-001`, lens `Correctness and Domain Invariants`, severity `Important`, and cites broad exception swallowing.

- [ ] **Step 3: Write the misleading-test variants**

Use this `06-misleading-tests/before.py`:

```python
def normalize_email(value):
    return value
```

Use this `buggy.py`:

```python
def normalize_email(value):
    return value.lower()
```

Use this `fixed.py`:

```python
def normalize_email(value):
    normalized = value.strip().lower()
    if normalized.count("@") != 1:
        raise ValueError("email must contain exactly one @")

    local_part, domain = normalized.split("@", 1)
    if not local_part or not domain:
        raise ValueError("email local part and domain are required")
    if any(character.isspace() for character in normalized):
        raise ValueError("email must not contain whitespace")
    return normalized
```

- [ ] **Step 4: Write visible and hidden misleading-test cases**

Use this `project_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class EmailProjectTest(unittest.TestCase):
    def test_lowercases_email(self):
        self.assertEqual(
            implementation.normalize_email("ADA@EXAMPLE.COM"),
            "ada@example.com",
        )


if __name__ == "__main__":
    unittest.main()
```

Use this `verification_test.py`:

```python
import importlib
import os
import unittest


implementation = importlib.import_module(os.environ["FIXTURE_VARIANT"])


class EmailVerificationTest(unittest.TestCase):
    def test_trims_boundary_whitespace(self):
        self.assertEqual(
            implementation.normalize_email("  ADA@EXAMPLE.COM  "),
            "ada@example.com",
            "TEST-001 visible tests prove only lowercasing, not normalization",
        )

    def test_rejects_malformed_email(self):
        with self.assertRaises(ValueError):
            implementation.normalize_email("not-an-email")


if __name__ == "__main__":
    unittest.main()
```

`spec.md` requires trim, lowercase, exactly one `@`, non-empty local/domain parts, and no embedded whitespace. `project-overlay.md` states normalized email is used as an identity key. The answer key uses `TEST-001`, primary lens `Test Quality` with a linked Spec Compliance miss, severity `Important`, and explains why a green happy-path test proves too little.

- [ ] **Step 5: Run all four combinations for both fixtures**

Run in `05-error-handling/`:

```bash
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q verification_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q verification_test.py
```

Run the identical explicit sequence in `06-misleading-tests/`:

```bash
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=buggy python3 -m unittest -q verification_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q project_test.py
PYTHONDONTWRITEBYTECODE=1 FIXTURE_VARIANT=fixed python3 -m unittest -q verification_test.py
```

Expected: buggy project passes; buggy verification fails with `ERR-001` or `TEST-001`; fixed project and fixed verification pass.

- [ ] **Step 6: Commit the two fixtures**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/05-error-handling ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures/06-misleading-tests ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/05-error-handling.md ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/06-misleading-tests.md
git commit -m "test(ai-review): add error and test-quality fixtures"
```

### Task 7: Build the Deterministic Runner and Complete Lab Navigation

**Files:**

- Create: `ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py`
- Create: six `change.diff` files under `lab/fixtures/*/`
- Modify: `ai/coding-agent/agent-skills/05-ai-code-review/README.md`
- Modify: `ai/coding-agent/agent-skills/05-ai-code-review/lab/README.md`

**Interfaces:**

- Consumes: all six fixture directories, six answer keys, and the shared failure markers.
- Produces: `main(argv=None) -> int`, a read-only default verification command, and deterministic diff generation behind `--write-diffs`.

- [ ] **Step 1: Add explicit defect markers to the first two hidden tests**

In `01-data-consistency/verification_test.py`, change the final assertion to:

```python
self.assertEqual(
    ledger.balances,
    before,
    "CONS-001 failed transfer left a partial balance mutation",
)
```

In `02-idempotency/verification_test.py`, change the call assertion to:

```python
self.assertEqual(
    gateway.calls,
    [2500],
    "IDEM-001 duplicate delivery repeated the gateway side effect",
)
```

These markers let the runner distinguish the intended oracle failure from an unrelated import or harness error.

- [ ] **Step 2: Implement the runner with exact expected-state semantics**

Create `lab/run-fixtures.py` with:

```python
#!/usr/bin/env python3
import argparse
import difflib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures"
ANSWER_KEY_ROOT = ROOT / "answer-key"

FIXTURES = (
    "01-data-consistency",
    "02-idempotency",
    "03-timeout-retry-fallback",
    "04-interface-coupling",
    "05-error-handling",
    "06-misleading-tests",
)

FAILURE_MARKERS = {
    "01-data-consistency": "CONS-001",
    "02-idempotency": "IDEM-001",
    "03-timeout-retry-fallback": "RES-001",
    "04-interface-coupling": "ARCH-001",
    "05-error-handling": "ERR-001",
    "06-misleading-tests": "TEST-001",
}

REQUIRED_FIXTURE_FILES = (
    "spec.md",
    "project-overlay.md",
    "before.py",
    "buggy.py",
    "fixed.py",
    "project_test.py",
    "verification_test.py",
)

REQUIRED_ANSWER_HEADINGS = (
    "## Defect ID",
    "## Expected lens",
    "## Expected severity",
    "## Evidence",
    "## Why project_test misses it",
    "## Fixed evidence",
    "## Scope boundary",
)


def render_diff(fixture_dir):
    before = (fixture_dir / "before.py").read_text(encoding="utf-8")
    buggy = (fixture_dir / "buggy.py").read_text(encoding="utf-8")
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            buggy.splitlines(keepends=True),
            fromfile="a/implementation.py",
            tofile="b/implementation.py",
        )
    )


def run_suite(fixture_dir, variant, suite):
    environment = os.environ.copy()
    environment["FIXTURE_VARIANT"] = variant
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "unittest", "-q", suite],
        cwd=fixture_dir,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def combined_output(result):
    return f"{result.stdout}\n{result.stderr}"


def validate_fixture(slug, write_diffs):
    fixture_dir = FIXTURE_ROOT / slug
    errors = []

    missing = [
        name for name in REQUIRED_FIXTURE_FILES
        if not (fixture_dir / name).is_file()
    ]
    if missing:
        return [f"missing fixture files: {', '.join(missing)}"]

    expected_diff = render_diff(fixture_dir)
    diff_path = fixture_dir / "change.diff"
    if not expected_diff:
        errors.append("before.py and buggy.py produced an empty review diff")
    if write_diffs:
        diff_path.write_text(expected_diff, encoding="utf-8")
    elif not diff_path.is_file():
        errors.append("missing change.diff")
    elif diff_path.read_text(encoding="utf-8") != expected_diff:
        errors.append("change.diff is stale")

    answer_key = ANSWER_KEY_ROOT / f"{slug}.md"
    if not answer_key.is_file():
        errors.append("missing answer key")
    else:
        answer_text = answer_key.read_text(encoding="utf-8")
        for heading in REQUIRED_ANSWER_HEADINGS:
            if heading not in answer_text:
                errors.append(f"answer key missing heading: {heading}")

    buggy_project = run_suite(fixture_dir, "buggy", "project_test.py")
    if buggy_project.returncode != 0:
        errors.append(
            "buggy project test must pass:\n" + combined_output(buggy_project)
        )

    buggy_verification = run_suite(
        fixture_dir,
        "buggy",
        "verification_test.py",
    )
    marker = FAILURE_MARKERS[slug]
    if buggy_verification.returncode == 0:
        errors.append("buggy verification unexpectedly passed")
    elif marker not in combined_output(buggy_verification):
        errors.append(
            f"buggy verification failed without expected marker {marker}:\n"
            + combined_output(buggy_verification)
        )

    for suite in ("project_test.py", "verification_test.py"):
        fixed_result = run_suite(fixture_dir, "fixed", suite)
        if fixed_result.returncode != 0:
            errors.append(
                f"fixed {suite} failed:\n" + combined_output(fixed_result)
            )

    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify deterministic AI Code Review fixtures."
    )
    parser.add_argument(
        "--write-diffs",
        action="store_true",
        help="regenerate deterministic before-to-buggy change.diff files",
    )
    arguments = parser.parse_args(argv)

    failed = False
    for slug in FIXTURES:
        errors = validate_fixture(slug, arguments.write_diffs)
        if errors:
            failed = True
            print(f"[FAIL] {slug}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[PASS] {slug}")

    if failed:
        return 1

    print(f"All {len(FIXTURES)} fixtures are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Generate the six stable review diffs**

Run:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py --write-diffs
```

Expected:

```text
[PASS] 01-data-consistency
[PASS] 02-idempotency
[PASS] 03-timeout-retry-fallback
[PASS] 04-interface-coupling
[PASS] 05-error-handling
[PASS] 06-misleading-tests
All 6 fixtures are valid.
```

Six `change.diff` files now exist and contain `--- a/implementation.py` plus `+++ b/implementation.py`.

- [ ] **Step 4: Prove the normal runner is read-only and detects stale artifacts**

Run the normal command twice:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
```

Expected: both runs print the same six PASS lines and exit zero; the second run creates no Git changes.

- [ ] **Step 5: Complete topic navigation and operator commands**

Update `05-ai-code-review/README.md` so every topic document and `lab/README.md` is linked. Update `lab/README.md` with these exact commands:

```bash
# Verify all declared behavior without changing artifacts
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py

# Regenerate diffs after intentionally editing before.py or buggy.py
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py --write-diffs
```

State that `--write-diffs` is a maintenance action and the default command is the delivery gate.

- [ ] **Step 6: Run the complete topic verification**

Run:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
test "$(find ai/coding-agent/agent-skills/05-ai-code-review/lab/fixtures -name change.diff | wc -l | tr -d ' ')" = "6"
test "$(find ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key -name '*.md' | wc -l | tr -d ' ')" = "6"
for heading in '## Defect ID' '## Expected lens' '## Expected severity' '## Evidence' '## Why project_test misses it' '## Fixed evidence' '## Scope boundary'; do test "$(rg -l "$heading" ai/coding-agent/agent-skills/05-ai-code-review/lab/answer-key/*.md | wc -l | tr -d ' ')" = "6" || exit 1; done
! rg -n 'API_KEY|requests|httpx|urllib\.request' ai/coding-agent/agent-skills/05-ai-code-review/lab --glob '*.py'
python3 -c 'from pathlib import Path; import re,sys; root=Path("ai/coding-agent/agent-skills/05-ai-code-review"); bad=[]; [(bad.append((str(p),u)) if not (p.parent/u.split("#",1)[0]).resolve().exists() else None) for p in root.rglob("*.md") for u in re.findall(r"\[[^]]+\]\(([^)]+)\)",p.read_text()) if u and not u.startswith(("http://","https://","#","/"))]; print("\n".join(f"{p}: {u}" for p,u in bad)); sys.exit(bool(bad))'
! rg -n 'T[B]D|T[O]DO|implemen[t] later|fill i[n] details' ai/coding-agent/agent-skills/05-ai-code-review --glob '*.md'
git diff --check
git status --short
```

Expected: runner passes all six; file and heading counts are six; no provider/network integration is found; only Task 7 files are uncommitted.

- [ ] **Step 7: Commit the runner and complete lab**

```bash
git add ai/coding-agent/agent-skills/05-ai-code-review
git commit -m "test(ai-review): add deterministic fixture runner"
```

## Plan Completion Gate

Run fresh:

```bash
python3 ai/coding-agent/agent-skills/05-ai-code-review/lab/run-fixtures.py
git status --short
git log --oneline --max-count=7
git diff --check HEAD~7..HEAD
```

Expected:

- all six fixture lines pass and the final line is `All 6 fixtures are valid.`;
- worktree is clean;
- seven task commits follow the foundation-plan commits;
- review docs clearly separate upstream mechanisms from the local protocol;
- the lab can measure manual AI reviews but contains no automatic model call.
