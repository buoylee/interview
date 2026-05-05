# RAG Chunking Tuning Playbook Design

## Context

`ai/rag-lab` already explains the RAG pipeline and gives a starter chunking configuration in `02-mini-rag-from-scratch.md`:

```text
chunk_size: 500-800 tokens or approximate characters
overlap: 50-100 tokens or approximate characters
```

The current material also explains the trade-off: chunks that are too small lose conditions and exceptions; chunks that are too large mix unrelated topics and add prompt noise; excessive overlap creates duplicate chunks. The missing piece is a practical playbook that shows how to tune `chunk_size` and `overlap` with representative questions, retrieval metrics, answer metrics, and cost checks.

## Goal

Add a hands-on document that teaches how to tune chunking parameters scientifically in a real RAG project.

The document should let a reader answer:

- What initial `chunk_size` and `overlap` values should I try?
- How do I build a small evaluation set for chunking?
- How do I compare multiple chunking configurations?
- Which metric tells me the chunk is too small, too large, or too repetitive?
- How do I choose a final configuration with accuracy, latency, and cost in mind?
- How should I explain this in an interview or project review?

## Non-Goals

- Do not introduce a full RAG framework implementation.
- Do not depend on a specific vector database, embedding model, or reranker.
- Do not rewrite the existing RAG Lab documents.
- Do not turn the playbook into a broad RAG evaluation guide; it should stay focused on chunking and overlap tuning.

## Proposed Changes

### 1. Add A New RAG Lab Document

Create:

```text
ai/rag-lab/08-chunking-tuning-playbook.md
```

This should be an independent practical guide placed after the hybrid/rerank debugging material.

### 2. Update RAG Lab Navigation

Update `ai/rag-lab/README.md`:

- Add the new document to the learning sequence.
- Add the new document to the completion expectations if needed.
- Preserve existing links and numbering style.

### 3. Cross-Link From Existing Chunking Step

Update `ai/rag-lab/02-mini-rag-from-scratch.md` lightly:

- Keep the current starter values.
- Add a short pointer from Step 3 to the new playbook for scientific tuning.

## Document Structure

The new playbook should use this structure:

1. **What This Playbook Solves**
   Explain that starter values are only a baseline; production chunking must be evaluated against real questions and real documents.

2. **Start With Conservative Defaults**
   Provide a small candidate matrix:

   ```text
   500 / 50
   800 / 100
   1000 / 150
   ```

   Explain when to add smaller or larger candidates.

3. **Build A Chunking Golden Set**
   Define a minimal evaluation row:

   ```text
   question
   expected_resource_id
   expected_section_or_span
   reference_answer
   failure_risk
   ```

   Recommend starting with 30-50 high-quality samples and expanding toward 100-200 as the system matures.

4. **Run A Parameter Matrix**
   For each chunking configuration:

   ```text
   parse documents
   split chunks
   rebuild embeddings/index
   run the same question set
   capture retrieved chunks, reranked chunks, final context, answer, citations
   ```

5. **Measure Retrieval And Answer Quality**
   Use the existing vocabulary from RAG mainline docs:

   - `recall@k`
   - `precision@k`
   - `MRR` or first-correct-rank
   - `faithfulness/grounding`
   - `citation accuracy`
   - answer correctness

6. **Measure Cost And Latency**
   Track:

   - number of chunks
   - embedding cost
   - vector index size
   - rerank candidate count and latency
   - prompt context size
   - duplicate chunk rate from overlap

7. **Diagnose Common Patterns**
   Include a table:

   - chunk too small: partial hit, missing conditions, missing exceptions
   - chunk too large: noisy matches, mixed topics, lower precision
   - overlap too small: boundary facts lost
   - overlap too large: duplicate candidates, higher cost, repetitive context
   - structure ignored: headings separated from body, tables split incorrectly

8. **Choose The Final Configuration**
   Recommend choosing the smallest chunk size that preserves enough semantic boundary and the smallest overlap that fixes boundary loss. The final choice should be justified by eval results, not by a universal default.

9. **Interview / Project Answer Template**
   Provide a concise answer showing how to describe this process in a real project.

## Success Criteria

- The new document is understandable without reading external sources.
- The document makes clear that there is no universal default.
- The document gives a concrete experiment workflow, not just conceptual advice.
- The document distinguishes retrieval quality, answer quality, and cost.
- Existing RAG Lab navigation points to the new document.
- Existing starter chunking guidance remains intact.

## Risks And Mitigations

| Risk | Mitigation |
|------|------------|
| The document becomes too abstract | Include concrete parameter matrix, eval row schema, and diagnosis table |
| The document duplicates the RAG evaluation page | Keep focus on chunking; link metrics only as needed |
| Readers think metrics alone are enough | Require manual inspection of chunks and citations |
| Readers overfit to one default value | Emphasize candidate comparison and corpus-specific tuning |

## Implementation Notes

The implementation should be limited to Markdown documentation edits. No code, tests, or dependency changes are needed.

Verification should use:

```text
rg -n "08-chunking-tuning-playbook|chunk_size|overlap|recall@k|citation accuracy" ai/rag-lab docs/superpowers/specs
```

and manual review of the new document for broken links, numbering, and duplicated wording.
