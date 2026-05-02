# Financial Consistency Interview Synthesis Design

## Goal

Build `financial-consistency/08-interview-synthesis` as the capstone chapter for the financial consistency learning route.

The chapter should help learners turn the previous technical material into a coherent interview and architecture review narrative. It must not repeat each scenario mechanically. It should teach how to explain financial-grade consistency as a system of facts, invariants, state machines, pattern choices, verification, reconciliation, repair, and audit.

## Background

The route already covers:

- `01-transfer`: transfer as the minimal money-movement consistency problem.
- `02-payment-recharge-withdraw`: external channel, callback, polling, and unknown result handling.
- `03-order-payment-inventory`: payment, order, inventory, and delivery coupling.
- `04-travel-booking-saga`: multi-provider reservation, compensation, and real-world Saga limits.
- `05-patterns`: Local Transaction, Outbox, TCC, Saga, 2PC, workflow engines, and selection criteria.
- `06-verification-lab`: invariants, failure injection, model checking mindset, property-based testing, and production verification.
- `07-reconciliation`: cross-system fact comparison, difference classification, controlled repair, audit, and closure.

Existing per-phase interview synthesis files are useful, but they are local summaries. The new chapter should synthesize the whole route into a final answer system.

## Non-Goals

- Do not introduce a new consistency pattern.
- Do not build executable Java or Go labs in this chapter.
- Do not turn the chapter into a generic interview question dump.
- Do not claim that any framework, MQ, workflow engine, database transaction, or distributed transaction protocol is enough by itself for financial safety.
- Do not simplify real-world financial correctness into eventual consistency slogans.

## Audience

The target reader is a backend engineer who understands basic transactions and wants to speak credibly about financial-grade distributed consistency in interviews, design reviews, or internal architecture discussions.

The chapter should help the learner progress from:

- "I know distributed transactions are hard"
- to "I can explain the consistency target, failure surface, pattern choice, verification method, reconciliation plan, and operational controls for a real money-related workflow."

## Content Architecture

Create a new directory:

```text
financial-consistency/08-interview-synthesis/
```

The chapter should contain these files:

```text
README.md
01-master-narrative.md
02-architecture-review-playbook.md
03-question-bank.md
04-scenario-drills.md
05-red-flags-and-bad-answers.md
06-senior-answer-rubric.md
07-final-summary.md
```

Update the root `financial-consistency/README.md` so the route links to this new chapter.

## File Responsibilities

### README.md

Provide the chapter entry point:

- Explain the purpose of the capstone chapter.
- Show the recommended reading order.
- Clarify that this chapter aggregates the whole route rather than replacing earlier scenario chapters.
- Define the final learning target: the learner should be able to defend a consistency design under questioning.

### 01-master-narrative.md

Create the final story the learner should be able to tell.

Core message:

> Financial-grade consistency is not magic distributed transaction technology. It is a closed loop of authoritative facts, explicit invariants, controlled state transitions, idempotent side effects, observable uncertainty, reconciliation, repair, and audit.

The narrative should cover:

- Why local database ACID is necessary but not sufficient once external systems and asynchronous flows appear.
- Why "success" must mean business fact closure, not only API success, MQ publish success, workflow step completion, or log persistence.
- How to move from a simple transfer to real-world scenarios involving payment channels, inventory, providers, delayed callbacks, duplicates, partial success, and unknown outcomes.
- How verification and reconciliation complete the safety model.

### 02-architecture-review-playbook.md

Teach how to present the system in an architecture review.

The playbook should give an ordered speaking path:

1. Define business scenario and money/user-visible impact.
2. Define authoritative facts and ownership boundaries.
3. Define invariants.
4. Define state machines and allowed transitions.
5. Define transaction boundaries.
6. Define async messaging and idempotency.
7. Define unknown-state handling.
8. Choose consistency pattern and explain why alternatives are weaker.
9. Define verification strategy.
10. Define reconciliation, repair, audit, and operational controls.

It should include reviewer-style prompts and the expected shape of strong answers.

### 03-question-bank.md

Create a structured question bank grouped by topic:

- Transfer and ledger consistency.
- Payment/recharge/withdraw external-channel consistency.
- Order/payment/inventory coupling.
- Saga and provider booking.
- Pattern selection.
- Verification and failure injection.
- Reconciliation and repair.
- Audit, compliance, and operations.

Answers should be concise but not shallow. Each answer should mention the relevant mental model and the practical controls that make it safe.

### 04-scenario-drills.md

Provide scenario drills that force the learner to apply the route end to end.

Required drills:

- Internal account transfer.
- Recharge where the channel succeeds but local callback is delayed.
- Withdraw where local success is recorded but provider result is unknown.
- Ecommerce order paid but inventory reservation times out.
- Travel booking where flight succeeds, hotel fails, and refund is delayed.
- Reconciliation finds local success but no external settlement evidence.
- Reconciliation finds external success but no local business order.

Each drill should include:

- Problem statement.
- Facts to identify.
- Invariants to protect.
- Safe state transitions.
- Pattern choice.
- Verification strategy.
- Reconciliation and repair strategy.
- Interview-ready answer outline.

### 05-red-flags-and-bad-answers.md

List dangerous claims and explain why they are unsafe.

Required red flags:

- "Use 2PC everywhere."
- "Use Saga and compensate, so consistency is solved."
- "MQ delivered means the business succeeded."
- "Workflow history is the source of financial truth."
- "Callback success means the channel definitely settled."
- "Unknown can be treated as failure."
- "Reconciliation can directly update balances."
- "Retry until success is safe."
- "Idempotency key alone prevents all duplicates."
- "Strong consistency means no asynchronous process is allowed."

For each red flag, provide:

- What the answer sounds like.
- Why it is wrong.
- What a safer answer should say.

### 06-senior-answer-rubric.md

Define answer quality levels so learners can evaluate their own explanations.

Levels:

- Junior: knows basic terms but over-trusts tools.
- Mid-level: can describe common patterns but misses operational closure.
- Senior: can reason from invariants, facts, state transitions, and failure modes.
- Staff/principal: can connect architecture, operations, compliance, observability, risk controls, and organizational boundaries.

The rubric should include scoring dimensions:

- Fact ownership clarity.
- Invariant precision.
- Failure-mode coverage.
- Pattern selection quality.
- Idempotency and retry safety.
- Unknown-state handling.
- Verification rigor.
- Reconciliation and repair controls.
- Auditability.
- Communication clarity.

### 07-final-summary.md

Provide a final compressed study sheet.

It should include:

- One-sentence thesis.
- One architecture review checklist.
- One pattern selection checklist.
- One verification checklist.
- One reconciliation checklist.
- One list of "never say this in an interview."
- One final answer template for a financial consistency design question.

## Learning Flow

The chapter should be read after all previous phases.

The flow is:

1. Build a master narrative.
2. Learn the architecture review speaking order.
3. Practice topic-specific questions.
4. Apply the answer model to scenario drills.
5. Learn to detect unsafe answers.
6. Calibrate answer quality by seniority.
7. Finish with a compact final summary.

## Quality Bar

The chapter is acceptable only if it satisfies these properties:

- It connects all previous phases explicitly.
- It keeps "authoritative facts" separate from logs, workflow history, reports, messages, and derived views.
- It treats unknown states as first-class states, not as failure shortcuts.
- It distinguishes business completion from technical completion.
- It explains when compensation is safe and when it is only a business remediation process.
- It treats reconciliation repair as controlled, approved, auditable action, not automatic mutation.
- It shows how verification, failure injection, and reconciliation form a scientific safety loop.
- It gives interview answers that are realistic enough for international financial/backend engineering contexts, not only one local market.

## Acceptance Criteria

- The new `08-interview-synthesis` directory exists with all seven content files plus `README.md`.
- The root `financial-consistency/README.md` links to the new chapter.
- Each file has concrete content, not placeholders.
- Scenario drills cover transfer, payment/recharge/withdraw, ecommerce, travel booking, and reconciliation incidents.
- Bad-answer analysis includes all required red flags.
- The final summary gives a reusable answer template.
- The content is consistent with previous phases and does not contradict the safety rules established in verification and reconciliation chapters.

## Risks

- The chapter may become repetitive if it copies earlier per-phase interview files. Mitigation: write it as a synthesis layer and reference prior concepts without re-explaining every scenario from scratch.
- The question bank may become too broad. Mitigation: group questions by the route's existing phases and keep answers focused on facts, invariants, failure handling, verification, and reconciliation.
- The chapter may sound too theoretical. Mitigation: use scenario drills and architecture review prompts to force concrete application.
- The chapter may imply financial safety comes from one tool or pattern. Mitigation: emphasize the closed-loop safety system across design, execution, verification, reconciliation, repair, and audit.

## Implementation Notes

This is a documentation phase. The implementation plan should create the chapter incrementally and commit each meaningful document separately.

The implementation should not modify unrelated files. Current unrelated dirty worktree entries must be ignored unless the user explicitly asks to handle them.
