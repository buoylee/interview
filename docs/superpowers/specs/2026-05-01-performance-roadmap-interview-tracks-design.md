# Performance Tuning Roadmap Interview Tracks Design

## Context

`performance-tuning-roadmap.md` and `performance-tuning-roadmap/` already cover a broad performance engineering body of knowledge: operating systems, methodology, Linux tools, observability, runtime profiling, load testing, database and middleware debugging, distributed systems, architecture, containers, SRE, and capstone exercises.

The current material is stronger than a normal knowledge checklist. It already has:

- A "phenomenon -> metric -> hypothesis -> tool -> diagnosis -> fix -> verification -> review" learning loop.
- A P0 PerfShop lab that can run a minimal end-to-end experiment.
- Templates for investigation, profiling, load testing, and postmortems.
- Capstone scenarios and self-assessment questions.

The remaining gap is not content volume. The gap is organization: the route should more clearly support senior interview preparation and smooth learning for experienced developers who lack systematic performance engineering training.

## Problem

The current roadmap has three practical issues:

1. **Learning route ambiguity**
   Experienced learners can see many stages, but may not know which stages matter most for Backend Senior, SRE/Platform, or Staff/Tech Lead interviews.

2. **Runnable lab ambiguity**
   The top-level roadmap still describes a full three-language PerfShop system in several places, while the currently implemented lab is `labs/perfshop-p0`, a Python standard-library minimal loop. This is a reasonable phased approach, but the documentation should make the phase boundary explicit.

3. **Senior interview standard ambiguity**
   The material explains tools and mechanisms, but it does not yet provide a dedicated rubric for what separates junior, mid-level, senior, and Staff-level answers.

## Goals

- Preserve one shared performance engineering core loop for all learners.
- Add three interview-oriented tracks:
  - Backend Senior
  - SRE / Platform
  - Staff / Tech Lead
- Make the lab maturity model explicit: P0 now, P1 next, P2 target state.
- Help learners understand what "senior-level performance debugging" means in interviews.
- Improve navigation without duplicating the existing 45K+ lines of technical content.

## Non-Goals

- Do not add another large batch of technical articles in this pass.
- Do not implement the full Java/Go/Python PerfShop system in this pass.
- Do not rewrite every existing learning unit.
- Do not turn the top-level roadmap into a much larger interview manual.

## Recommended Structure

All learners start with one shared core:

```text
P0 lab
-> methodology
-> Linux tools
-> observability
-> load generation
-> one primary runtime profiling path
-> load testing
-> database / network / distributed debugging
-> capstone
```

After the core, learners branch into target-specific tracks:

| Track | Target | Emphasis |
| --- | --- | --- |
| Backend Senior | Senior backend engineer interviews | Runtime profiling, slow SQL, connection pools, caching, distributed timeouts, production debugging narrative |
| SRE / Platform | SRE and platform interviews | SLI/SLO, Prometheus, alerting, capacity planning, cgroup/K8s, incident response, chaos engineering |
| Staff / Tech Lead | Staff engineer and tech lead interviews | System-level trade-offs, capacity models, performance governance, cross-team reliability practice, long-term risk reduction |

This avoids three fully duplicated roadmaps while still giving learners clear interview-oriented paths.

## New Documents

### `performance-tuning-roadmap/TRACKS.md`

Purpose: define the three interview tracks.

Content:

- Target audience for each track.
- Required stages.
- Optional stages.
- Stages that can be deferred.
- 4-week, 8-week, and 12-week versions.
- Required capstone outputs for each track.

This document should answer: "I am preparing for a specific interview type. What should I study first?"

### `performance-tuning-roadmap/INTERVIEW-MATRIX.md`

Purpose: map interview scenarios to required skills.

Organize by scenario rather than by existing chapter order:

- Interface latency / P99 spikes
- High CPU
- Memory leak / OOM
- GC or runtime pause
- Slow SQL / lock waits
- Redis slow command / big key
- Kafka consumer lag
- Connection pool exhaustion
- Downstream timeout / retry storm
- Packet loss / TLS handshake issue
- K8s CPU throttling / OOMKilled
- Capacity planning / SLO / incident review

For each scenario, include:

- What the candidate should notice.
- First-pass triage path.
- Tools and evidence.
- Mechanism to explain.
- Fix and verification strategy.
- Relevant roadmap chapters.

This document should answer: "What does senior-level interview readiness require for this scenario?"

### `performance-tuning-roadmap/LAB-CONTRACT.md`

Purpose: make the lab maturity model explicit.

Content:

- P0: currently runnable minimal loop.
- P1: planned multi-component debugging loop.
- P2: planned three-language symmetric PerfShop.
- Labels for exercises:
  - `Runnable now`
  - `Runnable with manual setup`
  - `Target-state example`
- Rule: target-state examples must not imply the current repository already implements the full scenario.

This document should answer: "Can I run this exercise today, and what environment does it assume?"

### `performance-tuning-roadmap/SENIOR-RUBRIC.md`

Purpose: define seniority levels for performance interview answers.

Rubric:

- Junior: knows tool names and isolated concepts.
- Mid-level: can follow a debugging checklist and use tools correctly.
- Senior: forms falsifiable hypotheses, gathers evidence, explains mechanisms, rules out alternatives, quantifies verification.
- Staff: designs systemic prevention, capacity models, reliability governance, rollout strategy, and organizational follow-up.

This document should answer: "What makes an answer senior rather than merely tool-aware?"

## Existing Document Changes

### `performance-tuning-roadmap.md`

Update the top-level roadmap to:

- State that the roadmap targets Backend Senior, SRE/Platform, and Staff/Tech Lead performance interviews.
- Keep the main roadmap as the universal core route.
- Add links to `TRACKS.md`, `INTERVIEW-MATRIX.md`, `LAB-CONTRACT.md`, and `SENIOR-RUBRIC.md`.
- Replace wording that says stage P requires the full three-language PerfShop with wording that says:
  - P0 first runs one minimal service.
  - P1 extends to multi-component scenarios.
  - P2 reaches three-language symmetric PerfShop.
- Keep detailed interview guidance out of the top-level file to prevent it from growing into an overloaded manual.

### `performance-tuning-roadmap/LEARNING-GUIDE.md`

Add a section explaining how to use the roadmap by interview goal:

- Everyone starts with the same P0 loop.
- Then choose one track.
- Each checkpoint should produce an interview-ready artifact:
  - triage notes
  - dashboard evidence
  - profile or flamegraph
  - slow-query or trace evidence
  - fix verification
  - postmortem or design trade-off write-up

### `performance-tuning-roadmap/14-capstone/README.md`

Add track-specific graduation expectations:

- Backend Senior capstone: production debugging narrative with runtime/database/distributed evidence.
- SRE / Platform capstone: SLO breach investigation, alert/runbook/capacity response.
- Staff / Tech Lead capstone: systemic performance improvement proposal with risk, rollout, governance, and measurement plan.

## Learning Flow

The learner experience should become:

1. Read `performance-tuning-roadmap.md` to understand the full map.
2. Read `LEARNING-GUIDE.md` to understand how to study.
3. Run `labs/perfshop-p0` and complete one full loop.
4. Read `TRACKS.md` and select the interview target.
5. Use `INTERVIEW-MATRIX.md` to connect scenarios to study units.
6. Use `SENIOR-RUBRIC.md` to evaluate whether answers are senior-level.
7. Complete the track-specific capstone output.

## Acceptance Criteria

After implementation, the documentation should clearly answer:

- Where should an experienced developer start?
- How should Backend Senior, SRE/Platform, and Staff/TL candidates choose chapters?
- Which exercises are runnable now, and which are target-state examples?
- What does a senior-level answer look like compared with junior or mid-level answers?
- How does a learner prove readiness through capstone artifacts?

## Risks And Controls

| Risk | Control |
| --- | --- |
| New documents increase navigation burden | Keep each new document focused on one responsibility and link them from the top-level roadmap |
| Tracks duplicate existing stage descriptions | Tracks should link to existing stages instead of restating their technical content |
| Lab contract exposes incomplete implementation | Present this directly as a phased maturity model, not as a defect |
| Staff track becomes vague | Require concrete artifacts: capacity model, rollout plan, governance loop, measurement plan |

## Implementation Notes

- Prefer additive documentation changes first.
- Keep edits to existing files small and navigational.
- Do not change technical tutorial content unless it conflicts with the P0/P1/P2 lab contract.
- Use consistent naming:
  - `Backend Senior Track`
  - `SRE / Platform Track`
  - `Staff / Tech Lead Track`
  - `P0`, `P1`, `P2`
  - `Runnable now`, `Runnable with manual setup`, `Target-state example`
