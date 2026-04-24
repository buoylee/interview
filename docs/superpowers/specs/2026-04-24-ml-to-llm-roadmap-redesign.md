# ML to LLM Roadmap Redesign

## Context

The current `ai/ml-to-llm-roadmap.md` and `ai/ml-to-llm-roadmap/` content are organized as a traditional subject sequence:

```text
Math -> ML -> Deep Learning -> NLP/Retrieval -> Transformer -> Pretrained Models -> LLM Core -> Applications -> Interview Synthesis
```

This structure contains useful material, but it does not match the primary learner profile:

- The learner has partial RAG/Agent application experience.
- The learner has only a basic understanding of LLM internals.
- The target interview type is comprehensive, with emphasis on AI Engineer / LLM application roles, while still covering common algorithm and infra follow-ups.

The observed problem is not merely that individual files need small edits. Some files mix multiple document purposes. For example, `02-deep-learning/01-neural-network-basics.md` currently acts as a tutorial, concept encyclopedia, Transformer prerequisite bridge, and interview note at the same time. This creates a jumpy learning experience because concepts such as MLP, universal approximation, backpropagation, gradient issues, BN/LN, Pre-Norm, RMSNorm, and SwiGLU appear in one compressed flow.

## Goal

Redesign the roadmap into a system that is both interview-oriented and systematic:

- The main route is organized by AI Engineer interview capabilities.
- Underlying theory is taught systematically when it becomes necessary.
- Review notes are separated from tutorials so they can be used for memorization and interview practice.
- Existing content can be significantly rewritten, split, moved, or reframed when that improves learning flow.

## Non-Goals

- Do not create a shallow question bank that only supports memorized answers.
- Do not force every learner to start with math, ML, and deep learning before seeing applied LLM topics.
- Do not preserve existing file boundaries when they cause conceptual jumps.
- Do not delete old content during the first migration pass.

## Design Principle

Use this principle for the redesign:

```text
Main route by AI Engineer interview capability.
Foundational knowledge by dependency and learning flow.
```

This means the default entry point should match what the learner is trying to do in interviews, while each module still teaches the necessary concepts in a stable order.

## Information Architecture

The new documentation system has three layers.

### 1. Main Learning Route

The main route is organized around AI Engineer / LLM application interview capability:

```text
ai/ml-to-llm-roadmap.md
ai/ml-to-llm-roadmap/
  01-rag-retrieval/
  02-agent-tool-use/
  03-generation-control/
  04-transformer-foundations/
  05-training-alignment-finetuning/
  06-inference-optimization/
  07-evaluation-safety-debugging/
  08-system-design-projects/
```

These modules are the default learning path. They should start from concrete RAG, Agent, generation, production, or interview problems and then drill into theory.

### 2. Foundations

Foundations contain systematic prerequisite material. They are not the default starting point. They are referenced by main-route documents when needed.

```text
ai/ml-to-llm-roadmap/
  foundations/
    math/
    ml/
    deep-learning/
    nlp/
```

The foundations layer should answer: "What do I need to understand before this main-route concept makes sense?"

### 3. Review Notes

Review notes are optimized for interview recall, not first-time learning.

```text
ai/ml-to-llm-roadmap/
  09-review-notes/
    01-rag-retrieval-cheatsheet.md
    02-agent-tool-calling-cheatsheet.md
    03-transformer-core-cheatsheet.md
    04-finetuning-alignment-cheatsheet.md
    05-inference-optimization-cheatsheet.md
    06-evaluation-safety-cheatsheet.md
    07-top-interview-qa.md
    08-project-story-bank.md
```

The existing interview synthesis content should eventually move into `08-system-design-projects/` and `09-review-notes/`.

## Document Templates

### Main Route Tutorial Template

Use this for `01-rag-retrieval/` through `08-system-design-projects/`.

```markdown
# Title

## Why You Need This
Start from a RAG, Agent, LLM application, production, or interview scenario.

## Prerequisite Check
List the concepts required to understand this document. Link to foundations for each one.

## A Real Problem
Open with a concrete engineering problem.

## Core Concepts
Teach concepts in dependency order. Do not introduce advanced terms before the necessary bridge exists.

## How This Affects LLM Applications
Explain impact on RAG, Agent behavior, prompt reliability, latency, cost, context, or production debugging.

## How Interviews Ask This
List common interview question forms. Link to review notes for full answers.

## Self-Check
Add 3-5 questions that verify real understanding.

## Next Step
Point to the next document and any fallback foundation reading.
```

### Foundation Template

Use this for `foundations/`.

```markdown
# Title

## What This File Covers
Define the boundary. Avoid turning the file into a full textbook chapter.

## Where This Appears in the Main Route
List main-route documents that depend on this concept.

## Minimal Intuition
Explain without formulas first.

## Minimal Formula
Include only necessary formulas. Define every symbol.

## Step-by-Step Example
Walk through a small concrete example.

## Common Misunderstandings
Name likely confusions and correct them.

## Return to the Main Route
Link back to the documents this unlocks.
```

### Review Note Template

Use this for `09-review-notes/`.

```markdown
# Topic

## 30-Second Answer
A concise first-pass interview answer.

## 2-Minute Expansion
Deeper explanation with mechanisms, trade-offs, and engineering implications.

## Follow-Up Questions
Common interviewer follow-ups and concise answers.

## Easy-to-Confuse Points
Comparison tables for similar concepts.

## Memory Hook
A short mnemonic, analogy, or sentence.

## Project Connection
How to connect the concept to the learner's RAG/Agent project experience.

## Deeper Reading
Links back to main-route tutorials and foundations.
```

## Migration Strategy

Do not migrate everything at once. Use a staged migration:

1. Create the new structure and one complete sample module.
2. Keep old files during migration.
3. Add migration notices to old files once their content has a new home.
4. Move or archive the old subject-based structure only after the new route is complete.

When a legacy file is migrated, add a notice like:

```markdown
> This content has been migrated into the new route:
> - Tutorial: ...
> - Review note: ...
> - Foundation: ...
```

## First Migration Batch

Build the first complete sample around Transformer foundations. This module is the best first target because it supports RAG, Agent, generation, inference optimization, and most LLM interview topics.

Create:

```text
ai/ml-to-llm-roadmap/
  04-transformer-foundations/
    README.md
    01-why-ai-engineers-need-transformer.md
    02-token-to-vector.md
    03-self-attention-qkv.md
    04-transformer-block.md
    05-decoder-only-and-generation.md

  foundations/
    deep-learning/
      01-neuron-mlp-activation.md
      02-backprop-gradient-problems.md
      03-normalization-residual-initialization.md
      04-ffn-gating-for-transformer.md

  09-review-notes/
    03-transformer-core-cheatsheet.md
```

This first batch should separate concepts currently compressed in `02-deep-learning/01-neural-network-basics.md`:

- `neuron / MLP / activation` belongs in a basic foundation file.
- `backprop / gradient vanishing / gradient explosion` belongs in a training foundation file.
- `normalization / residual / initialization` belongs in a foundation file that prepares for Transformer blocks.
- `FFN / GELU / SwiGLU / gating` belongs near the Transformer FFN context, not in the first neural-network basics lesson.

## Later Migration Batches

After the Transformer sample is validated, migrate the application modules:

```text
01-rag-retrieval/
  01-rag-system-map.md
  02-text-chunking-and-tokenization.md
  03-embedding-models.md
  04-hybrid-search-reranking.md
  05-rag-failure-debugging.md

02-agent-tool-use/
  01-agent-system-map.md
  02-tool-calling-and-structured-output.md
  03-planning-memory-reflection.md
  04-agent-failure-debugging.md
```

Then migrate:

```text
05-training-alignment-finetuning/
06-inference-optimization/
07-evaluation-safety-debugging/
08-system-design-projects/
09-review-notes/
```

## Acceptance Criteria

The redesign is successful when:

- A learner with RAG/Agent experience can start from `ml-to-llm-roadmap.md` without being forced through math-first sequencing.
- Each main-route document clearly states why it matters, what prerequisites it assumes, and where to backfill missing concepts.
- Advanced terms do not appear before the document provides a bridge or links to one.
- Interview notes are concise and reusable without bloating tutorial documents.
- The first migration batch provides a complete example of the new system: main tutorial, foundations, and review note.

## Implementation Defaults

- Old subject-based directories should remain during the migration. Once their useful content has been moved, foundational material should be merged into `foundations/`; any remaining obsolete subject-route files can be archived under `legacy-subject-roadmap/`.
- Review notes should use both topic grouping and question grouping: topic cheat sheets for systematic review, plus a top interview Q&A file for quick recall.
- The final route should include at least two time-boxed plans: a short interview sprint and a longer systematic track.
