# RAG Chunking Tuning Playbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a practical RAG Lab playbook that teaches how to tune `chunk_size` and `overlap` with real evaluation data.

**Architecture:** This is a Markdown-only documentation change. The new playbook becomes a standalone RAG Lab chapter, while `README.md` and the mini RAG chapter link to it.

**Tech Stack:** Markdown documentation in `ai/rag-lab`; verification with `rg` and manual link review.

---

### Task 1: Add The Chunking Tuning Playbook

**Files:**
- Create: `ai/rag-lab/08-chunking-tuning-playbook.md`

- [ ] **Step 1: Create the playbook file**

Add a new Markdown document with these sections:

```markdown
# Chunking Tuning Playbook：如何科学调整 chunk_size 和 overlap

## 这篇解决什么问题

## 先记住结论

## 从保守初始值开始

## 建一个 chunking golden set

## 跑参数矩阵

## 看 retrieval 指标

## 看 answer 指标

## 看成本和延迟

## 常见现象诊断

## 如何选最终配置

## 一个完整例子

## 面试 / 项目回答模板

## 自测
```

The document must explain:

- There is no universal default.
- `500/50`, `800/100`, and `1000/150` are candidate configurations, not guaranteed defaults.
- The same question set must be replayed against each rebuilt index.
- Tuning must compare retrieval quality, answer quality, and cost.
- Manual inspection of chunks and citations is still required.

- [ ] **Step 2: Include concrete schemas and tables**

The playbook must include:

```text
question
expected_resource_id
expected_section_or_span
reference_answer
failure_risk
```

and a diagnosis table covering:

```text
chunk too small
chunk too large
overlap too small
overlap too large
structure ignored
```

- [ ] **Step 3: Include a concise project answer template**

The template must let the reader say:

```text
我们不是直接拍一个 chunk_size。先用 500/50、800/100、1000/150 建三套索引，
用同一批 golden set 跑 recall@k、precision@k、citation accuracy 和 answer grounding，
再结合 chunk 数量、rerank 延迟和 prompt 长度选配置。
```

### Task 2: Update RAG Lab Navigation

**Files:**
- Modify: `ai/rag-lab/README.md`

- [ ] **Step 1: Add the new chapter to the learning sequence**

Insert the new chapter after `03-hybrid-rerank-debugging.md`:

```markdown
4. [Chunking 调参手册：科学确定 chunk_size 和 overlap](./08-chunking-tuning-playbook.md)
```

Renumber the existing following entries so the sequence stays ordered.

- [ ] **Step 2: Update completion standards**

Add a completion expectation that says the reader should be able to explain how to tune `chunk_size` and `overlap` using a golden set, retrieval metrics, answer metrics, and cost checks.

### Task 3: Add Cross-Link From Mini RAG

**Files:**
- Modify: `ai/rag-lab/02-mini-rag-from-scratch.md`

- [ ] **Step 1: Link Step 3 to the playbook**

After the starter chunk configuration, add one short sentence:

```markdown
真实项目不要停在这组初始值；如何用 golden set 和指标调参，见 [Chunking 调参手册](./08-chunking-tuning-playbook.md)。
```

### Task 4: Verify Documentation

**Files:**
- Verify: `ai/rag-lab/08-chunking-tuning-playbook.md`
- Verify: `ai/rag-lab/README.md`
- Verify: `ai/rag-lab/02-mini-rag-from-scratch.md`

- [ ] **Step 1: Search for expected anchors**

Run:

```bash
rg -n "08-chunking-tuning-playbook|chunk_size|overlap|recall@k|citation accuracy|golden set" ai/rag-lab docs/superpowers/plans docs/superpowers/specs
```

Expected: the new file, README link, mini RAG link, plan, and spec all appear.

- [ ] **Step 2: Review Markdown manually**

Run:

```bash
sed -n '1,260p' ai/rag-lab/08-chunking-tuning-playbook.md
```

Expected: no broken headings, no unfinished text, and no duplicate numbering in the README learning sequence.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff -- ai/rag-lab/08-chunking-tuning-playbook.md ai/rag-lab/README.md ai/rag-lab/02-mini-rag-from-scratch.md
```

Expected: only the intended documentation changes appear.
