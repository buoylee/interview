# Claude Code Source Notes Redesign Plan Suite

## Objective

Execute the approved redesign in five independently reviewable phases. Each phase leaves the notes in a coherent state, has its own verification gate, and can be accepted or revised without coupling all remaining topics into one giant diff.

Approved design:

~~~text
docs/superpowers/specs/2026-07-21-claude-code-source-notes-redesign.md
~~~

Read-only source:

~~~text
/Users/buoy/Development/gitrepo/Claude-Code-true
branch: note
commit: 712b24f22a63eb6d1a2f86697bf6dbbaa39ae3cf
~~~

## Execution Order

1. Foundation and one-agent-turn overview
   - Plan: 2026-07-21-claude-code-source-notes-01-foundation.md
   - Produces the new navigation, archives the current active notes, establishes the canonical map, terminology, state ownership, invariants, and writing contract.

2. Model Turn
   - Plan: 2026-07-21-claude-code-source-notes-02-model-turn.md
   - Produces the Context Assembly and Query Loop / Streaming learning path.

3. Controlled Effects
   - Plan: 2026-07-21-claude-code-source-notes-03-controlled-effects.md
   - Produces Tool orchestration, Permission, Bash analysis, Sandbox, and File safety.

4. Session Continuity
   - Plan: 2026-07-21-claude-code-source-notes-04-session-continuity.md
   - Produces Transcript / Context, Compaction, Interrupt / Queue / Continue / Resume.

5. Subagent Delegation and final integration
   - Plan: 2026-07-21-claude-code-source-notes-05-subagent-and-integration.md
   - Produces child-loop isolation, task lifecycle, communication, Fork / Prompt Cache, appendices, interview playbook, and final cross-track verification.

## Dependency Contract

The plans are sequential:

~~~text
Foundation
  → Model Turn
  → Controlled Effects
  → Session Continuity
  → Subagent Delegation and Integration
~~~

Later plans may consume terminology, diagram node IDs, navigation conventions, and invariants established by earlier plans. They must not silently rename those interfaces. If source evidence forces a correction, update the owning earlier document in the same commit and record the reason.

## Execution Environment Decisions

- Treat each `npx @mermaid-js/mermaid-cli` command in the phase plans as the preferred trusted-local renderer, not as authorization to download and execute a package.
- When the pinned CLI is not already installed or cached, validate every Mermaid block in an isolated Mermaid 11.x browser runtime instead.
- For browser validation, record the exact Mermaid block hash, representative rendered-node checks, and zero browser console errors before committing.
- Never execute a network-fetched npm package against the notes worktree merely to validate diagrams.

## Per-Article Definition of Done

Every mechanism article follows the same reading progression. This is a content contract, not a template that permits repetitive filler:

1. Locate the topic in A1–A8 and name the prior contract it consumes.
2. Ask one concrete question and give a one-sentence thesis.
3. Draw the complete local flow before discussing source symbols.
4. Walk the shared failing-test scenario through the canonical path.
5. Explain each causal step through input, decision, state mutation, and output.
6. Show before/after state snapshots at transitions where ownership or visibility changes.
7. Attach variants and failures to the exact node where they diverge.
8. Explain the mechanism in pseudocode, then show only decisive source excerpts.
9. State invariants, boundaries, and design trade-offs.
10. End with a complete interview answer, current system state, and the question that leads to the next article.

An implementation detail belongs in the main prose only when it explains a node, arrow, state, invariant, failure branch, or module contract. Otherwise move it to the evidence index or omit it.

## Shared Concept Ownership

Each concept has one authoritative owner. Other articles may summarize its input/output contract and link back, but must not redefine it:

| Concept | Owner |
|---|---|
| Model-visible context | Model Turn / Context Assembly |
| Query continuation, termination, and Tool Intent/Observation pairing | Model Turn / Query Loop and Streaming |
| Tool contract, validation, and orchestration | Controlled Effects / Tool Contract and Orchestration |
| Allow, ask, and deny | Controlled Effects / Permission Decision |
| Bash semantic analysis | Controlled Effects / Bash Security Analysis |
| Post-authorization process containment | Controlled Effects / Sandbox Runtime |
| Read/match/freshness mutation safeguards | Controlled Effects / File Editing Safety |
| Durable transcript versus current model projection | Session Continuity / Transcript and Model Context |
| Compaction | Session Continuity / Compaction |
| Interrupt, queue, Continue, and Resume | Session Continuity / Interrupt / Queue / Continue / Resume |
| Child context and task lifecycle | Subagent Delegation |
| Fork and prompt-cache variant | Subagent Delegation / Fork and Prompt Cache |
| Entry-form normalization | Runtime Entry Adapters appendix |
| Claim-to-source lookup | Source Evidence Index appendix |

## Review Gates

After each plan:

- Review the completed part as a reader, not only as a source audit.
- Confirm that its overview is understandable without opening source code.
- Confirm that every detail attaches to a flow node, state, invariant, failure branch, or module contract.
- Confirm that standard behavior appears before variants.
- Render all Mermaid blocks.
- Verify local links and navigation.
- Commit only that phase’s files.

Do not start the next plan until the current phase passes its review gate.

## Completion State

The suite is complete only when:

- all five plans are implemented in order;
- the main reading path is linear from README through 00 and all four parts;
- the overview path works without reading detail chapters;
- the interview path works from the canonical map to chapter-end answers and the final playbook;
- the previous active notes remain available under the dated archive;
- the worktree is clean and all focused commits are present.
