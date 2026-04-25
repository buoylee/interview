# ML to LLM Systematic Transformer Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Transformer sample from an interview-compressed module into a systematic learning chain, then derive a Transformer interview path and recalibrated review note from that chain.

**Architecture:** Keep the existing `04-transformer-foundations/` directory as the systematic learning module, but split the current 5-file chain into a 9-file dependency-ordered chain. Preserve existing foundation files, update legacy migration links, and add a separate `interview-paths/` document so review notes are used after learning rather than as first-time tutorials.

**Tech Stack:** Markdown documentation, existing repository layout, shell verification with `rg`, `find`, `git diff --check`, and a Node-based local Markdown link checker.

---

## File Structure

Modify:

- `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`
  Update the learning path from 5 lessons to 9 lessons, and state that this module is for first-time systematic learning.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md`
  Keep the motivation lesson, but update next-step links and ensure it introduces the systematic-learning-first rule.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md`
  Keep the token-to-vector lesson, but update next-step links to the new Attention motivation lesson.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md`
  Move to `04-self-attention-qkv.md`, then revise so it assumes the new `03-why-attention-needs-context.md` exists.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md`
  Move to `05-transformer-block.md`, then update links and prerequisites.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md`
  Move useful content into `08-decoder-only-generation.md` and `09-kv-cache-context-cost.md`, then remove the old file.

- `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md`
  Recalibrate links and answer scope after the systematic chain exists.

- `ai/ml-to-llm-roadmap.md`
  Update the sample status and interview path link.

- `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`
  Update legacy migration notice links to the new 9-file chain.

- `ai/ml-to-llm-roadmap/04-transformer-architecture/README.md`
  Update migration wording if it points readers only to the old 5-file chain.

Create:

- `ai/ml-to-llm-roadmap/04-transformer-foundations/03-why-attention-needs-context.md`
  Bridge from token vectors to Attention motivation before Q/K/V formulas.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md`
  Explain the original Encoder/Decoder architecture, source sequence, target sequence, masked self-attention, and cross-attention.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md`
  Explain Encoder-only, Encoder-Decoder, and Decoder-only as task-driven architecture choices, not disconnected names.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/08-decoder-only-generation.md`
  Explain next-token prediction, causal mask, logits, and decoding after the reader already understands Decoder-side generation.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/09-kv-cache-context-cost.md`
  Explain prefill, decode, KV Cache, context length, latency, memory, and why long conversations get expensive.

- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md`
  Provide a Transformer-specific interview reading path derived from the systematic module.

Do not modify:

- RAG, Agent, generation-control, training, inference, evaluation, or system-design modules beyond links that directly refer to the Transformer module.
- Foundation content unless a broken link or prerequisite mismatch is discovered during verification.

## Content Standards

Every systematic Transformer lesson must include:

```markdown
## 你为什么要学这个
## 学前检查
## 一个真实问题
## 核心概念
## 最小心智模型
## 和 LLM 应用的连接
## 常见误区
## 自测
## 下一步
```

Rules:

- A table can summarize, but cannot replace the explanation before it.
- Do not introduce three unexplained concepts in a row.
- Every new core term must have one of: a local explanation, a tiny example, or a foundation link.
- Interview content in systematic lessons is limited to why the concept matters and how it is usually asked.
- Review-note answers must link back to systematic lessons and must not introduce new core concepts that the systematic chain does not explain.

## Task 1: Restructure the Transformer Module Index

**Files:**

- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`

- [ ] **Step 1: Read current README**

Run:

```bash
sed -n '1,140p' ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
```

Expected: The learning path currently lists 5 lessons and sends readers from Self-Attention directly to Transformer Block and Decoder-only generation.

- [ ] **Step 2: Rewrite the learning path**

Update the README so the path is:

```markdown
| 顺序 | 文件 | 解决的问题 |
|------|------|------------|
| 1 | [01-why-ai-engineers-need-transformer.md](./01-why-ai-engineers-need-transformer.md) | 为什么应用工程师也要系统理解 Transformer |
| 2 | [02-token-to-vector.md](./02-token-to-vector.md) | 文本如何变成模型能处理的向量 |
| 3 | [03-why-attention-needs-context.md](./03-why-attention-needs-context.md) | 为什么 token 需要读取上下文 |
| 4 | [04-self-attention-qkv.md](./04-self-attention-qkv.md) | Self-Attention 和 Q/K/V 到底在算什么 |
| 5 | [05-transformer-block.md](./05-transformer-block.md) | 一个 Transformer 层如何把 Attention、FFN、Residual、Norm 组合起来 |
| 6 | [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md) | 原始 Transformer 的 Encoder 和 Decoder 分别负责什么 |
| 7 | [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md) | BERT、T5、GPT 三种架构范式为什么不同 |
| 8 | [08-decoder-only-generation.md](./08-decoder-only-generation.md) | GPT 类模型为什么能逐 token 生成 |
| 9 | [09-kv-cache-context-cost.md](./09-kv-cache-context-cost.md) | KV Cache、prefill、decode 和长上下文成本如何关联 |
```

Also update the opening description to say:

```markdown
> **定位**：这是第一次系统学习 Transformer 的主线，不是面试速记。读完这里，再进入 `interview-paths/` 和 `09-review-notes/` 做压缩复习。
```

- [ ] **Step 3: Update expected outcomes**

Ensure the "学完后你应该能回答" list includes:

```markdown
- 原始 Transformer 为什么分 Encoder 和 Decoder。
- Encoder-only、Encoder-Decoder、Decoder-only 分别适合什么任务。
- KV Cache 为什么加速 decode，但不消除长 prompt 的 prefill 成本。
```

- [ ] **Step 4: Verify no stale 5-lesson path remains in the README**

Run:

```bash
rg -n "05-decoder-only-and-generation|5 \\|" ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
```

Expected: No references to `05-decoder-only-and-generation.md`. The row containing `5 |` should refer to `05-transformer-block.md`.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
git commit -m "docs: expand transformer systematic learning path"
```

Expected: Commit succeeds.

## Task 2: Insert the Attention Motivation Lesson

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/03-why-attention-needs-context.md`
- Move: `ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md` to `ai/ml-to-llm-roadmap/04-transformer-foundations/04-self-attention-qkv.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/04-self-attention-qkv.md`

- [ ] **Step 1: Move the Q/K/V lesson**

Run:

```bash
git mv ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md ai/ml-to-llm-roadmap/04-transformer-foundations/04-self-attention-qkv.md
```

Expected: The file is renamed and tracked by git.

- [ ] **Step 2: Create `03-why-attention-needs-context.md`**

Write a full lesson with this exact heading order:

```markdown
# 4.3 为什么 Attention 需要“看上下文”

## 你为什么要学这个

讲完 token 变成向量后，读者还不知道模型怎样处理“同一个词在不同句子里含义不同”的问题。本篇只解决一个问题：为什么每个 token 不能只看自己的 embedding，而需要读取周围 token 的信息。

## 学前检查

- 你知道 token ID 和 embedding 的区别；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- 你知道一个 token 可以表示成一个向量；不需要先懂 Q/K/V。

## 一个真实问题

在句子 `Apple released a new model` 和 `I ate an apple` 里，`Apple/apple` 的含义不同。只看单个 token 的向量，很难判断它是公司还是水果。模型必须让 token 读取上下文。

## 核心概念

### 只看自己为什么不够

Embedding 给每个 token 一个初始向量，但这个向量还没有吸收当前句子的上下文。

### 上下文读取是什么

上下文读取就是：当前 token 根据当前句子里的其他 token，更新自己的表示。

### Attention 的目标

Attention 要回答三个问题：

1. 当前 token 想找什么信息。
2. 其他 token 能提供什么信息。
3. 当前 token 应该从每个 token 读取多少信息。

这三个问题会在下一篇变成 Q、K、V。

## 最小心智模型

输入：一串 token embedding。

中间：每个 token 观察同一句子里的其他 token，决定哪些信息更相关。

输出：每个 token 得到一个带上下文的新向量。

## 和 LLM 应用的连接

- RAG 中，模型回答问题时要判断检索片段里的哪些 token 和问题相关。
- Agent 中，模型要在工具说明、用户目标、历史步骤之间建立关系。
- 长上下文成本高，是因为 token 之间的关系读取会随上下文长度变重。

## 常见误区

- Attention 不是让模型“理解一切”，它只是提供一种读取上下文的机制。
- Embedding 不是最终语义，经过 Attention 后的 hidden state 才吸收了当前上下文。
- 不是所有 token 都同等重要，Attention 权重表达的是相对读取比例。

## 自测

1. 为什么只看 embedding 不足以处理上下文含义？
2. Attention 想解决哪三个问题？
3. 为什么 RAG 回答需要上下文读取能力？

## 下一步

下一篇读 [04-self-attention-qkv.md](./04-self-attention-qkv.md)，把“想找什么、谁能提供、读取什么”具体变成 Q/K/V。
```

- [ ] **Step 3: Update `02-token-to-vector.md` next link**

Change its next-step link from `03-self-attention-qkv.md` to:

```markdown
下一篇读 [03-why-attention-needs-context.md](./03-why-attention-needs-context.md)，先理解为什么 token 需要读取上下文，再进入 Q/K/V。
```

- [ ] **Step 4: Revise `04-self-attention-qkv.md` opening**

Ensure it says the previous lesson introduced three questions and this lesson maps them:

```markdown
上一篇已经把 Attention 的动机拆成三个问题：当前 token 想找什么、其他 token 能提供什么、当前 token 应该读取什么。本篇把这三个问题具体落到 Q、K、V。
```

Ensure the title becomes:

```markdown
# 4.4 Self-Attention 与 Q/K/V
```

- [ ] **Step 5: Verify links**

Run:

```bash
rg -n "03-self-attention-qkv|03-why-attention-needs-context|04-self-attention-qkv" ai/ml-to-llm-roadmap/04-transformer-foundations
```

Expected: No references to `03-self-attention-qkv.md`. New links point to `03-why-attention-needs-context.md` and `04-self-attention-qkv.md`.

- [ ] **Step 6: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations
git commit -m "docs: add attention motivation lesson"
```

Expected: Commit succeeds.

## Task 3: Move and Reframe Transformer Block

**Files:**

- Move: `ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md` to `ai/ml-to-llm-roadmap/04-transformer-foundations/05-transformer-block.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/05-transformer-block.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/04-self-attention-qkv.md`

- [ ] **Step 1: Move the Transformer Block lesson**

Run:

```bash
git mv ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md ai/ml-to-llm-roadmap/04-transformer-foundations/05-transformer-block.md
```

Expected: The file is renamed and tracked by git.

- [ ] **Step 2: Update title and prerequisites**

In `05-transformer-block.md`, set the title to:

```markdown
# 4.5 Transformer Block：Attention、FFN、Residual、Norm 如何配合
```

Update the Self-Attention prerequisite link to:

```markdown
- Self-Attention 的 Q/K/V 流程；不熟先看 [04-self-attention-qkv.md](./04-self-attention-qkv.md)。
```

- [ ] **Step 3: Add a bridge to original Encoder/Decoder**

At the end of `05-transformer-block.md`, set the next step to:

```markdown
下一篇读 [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md)，看多个 Transformer Block 如何组成原始 Transformer 的 Encoder 和 Decoder。
```

- [ ] **Step 4: Update Q/K/V next link**

In `04-self-attention-qkv.md`, change the next link to:

```markdown
下一篇读 [05-transformer-block.md](./05-transformer-block.md)，把 Attention 放回完整 Transformer 层里。
```

- [ ] **Step 5: Verify no stale block path remains**

Run:

```bash
rg -n "04-transformer-block|05-transformer-block" ai/ml-to-llm-roadmap/04-transformer-foundations
```

Expected: References to `04-transformer-block.md` are gone or only appear in intentional historical text. Current learning links point to `05-transformer-block.md`.

- [ ] **Step 6: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations
git commit -m "docs: move transformer block in systematic path"
```

Expected: Commit succeeds.

## Task 4: Add Original Encoder/Decoder Lesson

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md`

- [ ] **Step 1: Create the lesson**

Write `06-original-transformer-encoder-decoder.md` with this structure:

```markdown
# 4.6 原始 Transformer：Encoder 和 Decoder 各自负责什么

## 你为什么要学这个

在比较 BERT、T5、GPT 之前，必须先知道原始 Transformer 为什么有 Encoder 和 Decoder。否则 Encoder-only、Encoder-Decoder、Decoder-only 只是三个需要硬背的名字。

## 学前检查

- 你知道 Transformer Block 是 Attention、FFN、Residual、Norm 的组合；不熟先看 [05-transformer-block.md](./05-transformer-block.md)。
- 你知道 causal mask 会限制 token 看未来；如果还不熟，本篇会先给最小解释。

## 一个真实问题

机器翻译里，输入是中文句子，输出是英文句子。模型需要先读懂完整中文，再逐步生成英文。这就是原始 Encoder-Decoder 架构的核心动机。

## 核心概念

### Source sequence 和 target sequence

Source sequence 是输入序列，例如用户给出的中文句子。Target sequence 是要生成的输出序列，例如英文翻译。

### Encoder 负责读懂输入

Encoder 读取完整 source sequence。因为输入已经完整给定，source token 之间通常可以双向互看。

### Decoder 负责逐步生成输出

Decoder 生成 target sequence。生成时不能偷看未来答案，所以 Decoder 的 self-attention 需要 causal mask。

### Cross-attention 负责读取 Encoder 结果

Decoder 生成每个输出 token 时，不只看已经生成的 target token，还要读取 Encoder 对 source sequence 的表示。这个“Decoder 读 Encoder 输出”的注意力就是 cross-attention。

## 最小心智模型

输入：source sequence，例如 `我 喜欢 苹果`。

Encoder 输出：每个 source token 的上下文表示。

Decoder 输入：已经生成的 target token，例如 `I like`。

Decoder 输出：下一个 target token 的概率，例如 `apples`。

## 和 LLM 应用的连接

- 翻译和摘要天然像“输入序列到输出序列”的任务。
- RAG 里的 reader/generator 可以类比为“先读材料，再生成答案”，但现代通用 LLM 通常把材料和问题拼进同一个 Decoder-only prompt。
- 理解 cross-attention 后，更容易理解为什么 Encoder-Decoder 和 Decoder-only 在处理输入信息时方式不同。

## 常见误区

- Encoder 不是“只编码不理解”，它会通过 self-attention 形成上下文表示。
- Decoder 不是只能看自己，它可以通过 cross-attention 读取 Encoder 输出。
- Causal mask 限制的是 Decoder 生成侧，避免它看见未来 target token。

## 自测

1. Source sequence 和 target sequence 分别是什么？
2. Encoder 为什么通常可以双向看输入？
3. Decoder 为什么需要 causal mask？
4. Cross-attention 连接了哪两部分？

## 下一步

下一篇读 [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md)，看 BERT、T5、GPT 如何从这套结构中选择不同部分。
```

- [ ] **Step 2: Verify the lesson names all required bridge terms**

Run:

```bash
rg -n "source sequence|target sequence|causal mask|cross-attention|Encoder|Decoder" ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
```

Expected: All required terms appear with local explanations.

- [ ] **Step 3: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
git commit -m "docs: explain original transformer encoder decoder"
```

Expected: Commit succeeds.

## Task 5: Add Architecture Variants Lesson

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md`

- [ ] **Step 1: Create the lesson**

Write `07-transformer-architecture-variants.md` with this structure:

```markdown
# 4.7 三种 Transformer 架构范式：BERT、T5、GPT 为什么不同

## 你为什么要学这个

面试经常问 BERT、T5、GPT 的区别。这个问题不能只背表格，因为它本质是在问：不同任务为什么需要不同的 Transformer 结构。

## 学前检查

- 你知道原始 Transformer 的 Encoder 和 Decoder 分工；不熟先看 [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md)。
- 你知道 self-attention 和 causal mask 的基本作用。

## 一个真实问题

同样是文本模型，为什么 embedding/rerank 常见 BERT 类模型，翻译/摘要可以用 T5，而 ChatGPT/LLaMA 主要是 GPT 类 Decoder-only？因为这些任务对“读输入”和“生成输出”的要求不同。

## 核心概念

### Encoder-only：保留理解侧

Encoder-only 只保留 Encoder。它适合把输入文本读成上下文表示。典型代表是 BERT。

适合任务：分类、NER、embedding、rerank、语义匹配。

### Encoder-Decoder：保留输入到输出转换链路

Encoder 读 source sequence，Decoder 生成 target sequence，并用 cross-attention 读取 Encoder 输出。典型代表是 T5。

适合任务：翻译、摘要、改写、结构化转换。

### Decoder-only：保留自回归生成侧

Decoder-only 把 prompt、历史对话、检索材料、工具 schema 都放进同一个序列，然后预测下一个 token。典型代表是 GPT、LLaMA。

适合任务：对话、通用生成、代码生成、工具调用。

## 最小心智模型

```text
Encoder-only:
  input text -> contextual representation

Encoder-Decoder:
  source text -> encoder representation -> decoder output text

Decoder-only:
  prompt + history + context -> next token -> next token -> ...
```

## 和 LLM 应用的连接

- RAG embedding 和 rerank 常常更接近 Encoder-only 用法，因为目标是理解和比较文本。
- 通用聊天模型多是 Decoder-only，因为 prompt、上下文和输出可以统一成一个 token 序列。
- Encoder-Decoder 仍然适合明确的输入到输出转换任务，但通用 LLM 应用里不一定是默认架构。

## 常见误区

- Encoder-only 不是“对生成完全没用”，而是不是天然自回归生成。
- Decoder-only 不是“没有 Encoder 所以不能理解输入”，它把输入放在同一个上下文序列里读取。
- Encoder-Decoder 不是过时架构，它在 seq2seq 任务里仍然有清晰优势。

## 自测

1. 为什么 BERT 适合 embedding/rerank？
2. T5 为什么需要 cross-attention？
3. GPT 为什么可以把检索文档和用户问题放进同一个 prompt？
4. 三种架构的输入输出形式分别是什么？

## 下一步

下一篇读 [08-decoder-only-generation.md](./08-decoder-only-generation.md)，在已经理解三种架构后，专门看 Decoder-only 如何逐 token 生成。
```

- [ ] **Step 2: Verify table is not the only explanation**

Run:

```bash
rg -n "Encoder-only|Encoder-Decoder|Decoder-only|RAG embedding|rerank|T5|GPT" ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
```

Expected: Each architecture appears in explanatory prose, not only in a table.

- [ ] **Step 3: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
git commit -m "docs: explain transformer architecture variants systematically"
```

Expected: Commit succeeds.

## Task 6: Split Decoder-Only Generation from KV Cache

**Files:**

- Move: `ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md` to `ai/ml-to-llm-roadmap/04-transformer-foundations/08-decoder-only-generation.md`
- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/09-kv-cache-context-cost.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/08-decoder-only-generation.md`

- [ ] **Step 1: Move old Decoder-only file**

Run:

```bash
git mv ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md ai/ml-to-llm-roadmap/04-transformer-foundations/08-decoder-only-generation.md
```

Expected: The file is renamed and tracked by git.

- [ ] **Step 2: Rewrite `08-decoder-only-generation.md` around generation only**

Ensure it has this title:

```markdown
# 4.8 Decoder-only 与逐 Token 生成
```

Remove the explanatory burden for Encoder-only and Encoder-Decoder. The opening should point back:

```markdown
前一篇已经解释了 Encoder-only、Encoder-Decoder 和 Decoder-only 的差异。本篇只回答一个问题：当架构选择 Decoder-only 后，模型如何基于已有上下文逐 token 生成。
```

Keep and expand these sections:

- Decoder-only 的训练目标。
- Causal Mask。
- Logits 到下一个 token。
- 解码策略的最小解释：greedy、temperature、top-p 各用一句话解释。

Move detailed KV Cache and long-context cost material out to Task 6 Step 3.

Set the next step to:

```markdown
下一篇读 [09-kv-cache-context-cost.md](./09-kv-cache-context-cost.md)，理解为什么 Decoder-only 生成可以缓存历史 K/V，以及长上下文为什么仍然贵。
```

- [ ] **Step 3: Create `09-kv-cache-context-cost.md`**

Write this lesson:

```markdown
# 4.9 KV Cache、上下文长度与推理成本

## 你为什么要学这个

学完逐 token 生成后，还需要理解为什么聊天越长越慢、显存为什么被上下文占用、为什么 KV Cache 能加速流式输出但不能让长 prompt 免费。

## 学前检查

- 你知道 Decoder-only 会逐 token 生成；不熟先看 [08-decoder-only-generation.md](./08-decoder-only-generation.md)。
- 你知道 Self-Attention 会计算 Q/K/V；不熟先看 [04-self-attention-qkv.md](./04-self-attention-qkv.md)。

## 一个真实问题

同一个模型，短 prompt 很快，长文档 RAG 或多轮对话会明显变慢、变贵。原因不只是输出 token 多，还包括输入上下文越长，prefill 和 KV Cache 成本越高。

## 核心概念

### Prefill

Prefill 是模型第一次处理完整 prompt 的阶段。所有输入 token 都要经过 Transformer 层，建立初始 hidden states 和 K/V Cache。

### Decode

Decode 是逐步生成新 token 的阶段。每生成一个 token，模型只新增这个 token 的 Q/K/V，并读取历史 K/V。

### KV Cache 缓存什么

KV Cache 缓存每一层历史 token 的 Key 和 Value。Query 来自当前新 token，历史 K/V 可以复用。

### KV Cache 加速什么

KV Cache 加速 decode 阶段，因为不用每一步重新计算所有历史 token 的 K/V。

### KV Cache 不解决什么

KV Cache 不消除长 prompt 的 prefill 成本，也不会让注意力读取历史上下文变成零成本。上下文越长，缓存占用和读取成本越高。

## 最小心智模型

```text
long prompt -> prefill all prompt tokens -> build KV Cache
new token 1 -> reuse old K/V -> append new K/V
new token 2 -> reuse old K/V -> append new K/V
```

## 和 LLM 应用的连接

- RAG 文档塞太多会增加 prefill 成本。
- 多轮对话历史太长会增加 KV Cache 显存占用。
- 流式输出快，是因为 decode 可以复用历史 K/V。
- 成本优化常常要减少无效上下文，而不是只调 temperature。

## 常见误区

- KV Cache 不是缓存最终答案，而是缓存每层历史 token 的 K/V。
- KV Cache 加速 decode，不消除 prefill。
- 长上下文贵，不只是因为输出长，也因为输入 token 多。

## 自测

1. Prefill 和 decode 分别发生在什么时候？
2. KV Cache 缓存的是 Q、K、V 里的哪几个？
3. 为什么长 RAG prompt 即使用 KV Cache 也不免费？
4. 多轮对话为什么会增加显存压力？

## 下一步

系统学习到这里先完成 Transformer 主线。面试前再读 [Transformer 面试阅读路径](../interview-paths/ai-engineer-transformer.md) 和 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。
```

- [ ] **Step 4: Verify old decoder filename is gone**

Run:

```bash
rg -n "05-decoder-only-and-generation|08-decoder-only-generation|09-kv-cache-context-cost" ai/ml-to-llm-roadmap/04-transformer-foundations
```

Expected: No references to `05-decoder-only-and-generation.md`. Current links point to `08-decoder-only-generation.md` or `09-kv-cache-context-cost.md`.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations
git commit -m "docs: split decoder generation and kv cache lessons"
```

Expected: Commit succeeds.

## Task 7: Update Cross-Links and Legacy Migration Notices

**Files:**

- Modify: `ai/ml-to-llm-roadmap.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-architecture/README.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`
- Modify: any file under `ai/ml-to-llm-roadmap/04-transformer-foundations/` that still links to old filenames.

- [ ] **Step 1: Find stale links**

Run:

```bash
rg -n "03-self-attention-qkv|04-transformer-block|05-decoder-only-and-generation" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/04-transformer-architecture
```

Expected: Any output identifies links to update.

- [ ] **Step 2: Update old Transformer core migration notice**

In `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`, ensure the migration notice points to all current systematic chapters:

```markdown
> - 为什么应用工程师需要懂 Transformer：[../04-transformer-foundations/01-why-ai-engineers-need-transformer.md](../04-transformer-foundations/01-why-ai-engineers-need-transformer.md)
> - 从 Token 到向量：[../04-transformer-foundations/02-token-to-vector.md](../04-transformer-foundations/02-token-to-vector.md)
> - 为什么 Attention 需要上下文：[../04-transformer-foundations/03-why-attention-needs-context.md](../04-transformer-foundations/03-why-attention-needs-context.md)
> - Self-Attention 与 Q/K/V：[../04-transformer-foundations/04-self-attention-qkv.md](../04-transformer-foundations/04-self-attention-qkv.md)
> - Transformer Block：[../04-transformer-foundations/05-transformer-block.md](../04-transformer-foundations/05-transformer-block.md)
> - 原始 Transformer Encoder/Decoder：[../04-transformer-foundations/06-original-transformer-encoder-decoder.md](../04-transformer-foundations/06-original-transformer-encoder-decoder.md)
> - 三种 Transformer 架构范式：[../04-transformer-foundations/07-transformer-architecture-variants.md](../04-transformer-foundations/07-transformer-architecture-variants.md)
> - Decoder-only 与逐 Token 生成：[../04-transformer-foundations/08-decoder-only-generation.md](../04-transformer-foundations/08-decoder-only-generation.md)
> - KV Cache 与上下文成本：[../04-transformer-foundations/09-kv-cache-context-cost.md](../04-transformer-foundations/09-kv-cache-context-cost.md)
```

- [ ] **Step 3: Update top-level roadmap wording**

In `ai/ml-to-llm-roadmap.md`, ensure the Transformer sample is described as:

```markdown
Transformer 系统学习样板
```

and ensure it does not imply review notes are the first learning entry.

- [ ] **Step 4: Verify stale filenames are gone**

Run:

```bash
rg -n "03-self-attention-qkv|04-transformer-block|05-decoder-only-and-generation" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/04-transformer-architecture
```

Expected: No output.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/04-transformer-architecture
git commit -m "docs: update transformer systematic links"
```

Expected: Commit succeeds.

## Task 8: Add Transformer Interview Reading Path

**Files:**

- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md`
- Modify: `ai/ml-to-llm-roadmap.md`

- [ ] **Step 1: Create interview path directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/interview-paths
```

Expected: Directory exists.

- [ ] **Step 2: Write the Transformer interview path**

Create `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md`:

```markdown
# AI Engineer Transformer 面试阅读路径

> **定位**：这不是第一次学习材料。先读完 [Transformer 系统学习主线](../04-transformer-foundations/)，再用这条路径按面试优先级复习。

## 适合谁

- 做过 RAG / Agent / LLM 应用，但底层 Transformer 不够稳。
- 需要准备 AI Engineer / LLM Application Engineer 面试。
- 想把系统学习内容压缩成可回答、可追问、可连接项目的材料。

## 2 周冲刺路径

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [04-transformer-foundations/README.md](../04-transformer-foundations/) | 按顺序过一遍系统主线 |
| 2 | [09-kv-cache-context-cost.md](../04-transformer-foundations/09-kv-cache-context-cost.md) | 重点复习成本、延迟、长上下文 |
| 3 | [07-transformer-architecture-variants.md](../04-transformer-foundations/07-transformer-architecture-variants.md) | 准备 BERT/T5/GPT 对比 |
| 4 | [03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md) | 压缩成面试答案 |

## 系统学习路径

1. 从 [04-transformer-foundations/README.md](../04-transformer-foundations/) 开始顺序读 1 到 9。
2. 每次卡住先回 foundation，不直接背 review note。
3. 学完后再读 [03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md)。
4. 用下面的问题做口头复述。

## 高频问题

- 为什么 Attention 需要上下文读取？
- Self-Attention 里的 Q/K/V 分别是什么？
- Transformer Block 里 FFN、Residual、Norm 分别解决什么问题？
- 原始 Transformer 为什么有 Encoder 和 Decoder？
- BERT、T5、GPT 架构有什么区别？
- 为什么现代通用 LLM 多数是 Decoder-only？
- KV Cache 为什么能加速生成，但不能让长 prompt 免费？

## 项目连接

- RAG embedding / rerank：连接 Encoder-only。
- RAG 长文档上下文：连接 prefill、context cost。
- Agent 工具调用：连接 Decoder-only 生成结构化 token。
- 流式输出：连接自回归 decode 和 KV Cache。

## 使用规则

如果这份路径里某个问题答不上来，不要先背答案，回到对应系统学习章节重读。
```

- [ ] **Step 3: Link from top-level roadmap**

In `ai/ml-to-llm-roadmap.md`, add the interview path link near the Transformer sample or interview sprint path:

```markdown
Transformer 面试阅读路径：[interview-paths/ai-engineer-transformer.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md)
```

- [ ] **Step 4: Verify path link exists**

Run:

```bash
test -f ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md
```

Expected: Exit code 0.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md
git commit -m "docs: add transformer interview reading path"
```

Expected: Commit succeeds.

## Task 9: Recalibrate Transformer Review Note

**Files:**

- Modify: `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md`

- [ ] **Step 1: Read the existing review note**

Run:

```bash
sed -n '1,160p' ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Expected: The note contains 30-second answer, 2-minute expansion, follow-up questions, easy-confuse points, and deeper reading.

- [ ] **Step 2: Update deeper reading links**

Ensure the deeper reading section links to all core systematic lessons:

```markdown
- [为什么 Attention 需要上下文](../04-transformer-foundations/03-why-attention-needs-context.md)
- [Self-Attention 与 Q/K/V](../04-transformer-foundations/04-self-attention-qkv.md)
- [Transformer Block](../04-transformer-foundations/05-transformer-block.md)
- [原始 Transformer Encoder/Decoder](../04-transformer-foundations/06-original-transformer-encoder-decoder.md)
- [三种 Transformer 架构范式](../04-transformer-foundations/07-transformer-architecture-variants.md)
- [Decoder-only 与逐 Token 生成](../04-transformer-foundations/08-decoder-only-generation.md)
- [KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md)
```

- [ ] **Step 3: Add architecture follow-up questions**

Add concise follow-up answers for:

```markdown
| 追问 | 回答 |
|------|------|
| BERT、T5、GPT 架构差异是什么？ | BERT 是 Encoder-only，适合理解和表示；T5 是 Encoder-Decoder，适合输入到输出转换；GPT 是 Decoder-only，适合把 prompt、上下文和输出统一成自回归生成。 |
| Cross-attention 解决什么问题？ | 在 Encoder-Decoder 中，Decoder 生成输出时通过 cross-attention 读取 Encoder 对输入序列的表示。 |
| KV Cache 为什么不消除长 prompt 成本？ | KV Cache 复用历史 K/V 加速 decode，但长 prompt 仍要先经过 prefill，且缓存占用和读取成本会随上下文增长。 |
```

- [ ] **Step 4: Add a clear first-time learning disclaimer**

Near the top, add:

```markdown
> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [Transformer 系统学习主线](../04-transformer-foundations/)。
```

- [ ] **Step 5: Verify review note does not link to stale filenames**

Run:

```bash
rg -n "03-self-attention-qkv|04-transformer-block|05-decoder-only-and-generation" ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Expected: No output.

- [ ] **Step 6: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
git commit -m "docs: recalibrate transformer review note"
```

Expected: Commit succeeds.

## Task 10: Final Verification

**Files:**

- Inspect all changed files in this plan.

- [ ] **Step 1: Check git status**

Run:

```bash
git status --short
```

Expected: No uncommitted changes before final verification starts. If there are changes, either commit them as part of their task or inspect why they exist.

- [ ] **Step 2: Run whitespace check**

Run:

```bash
BASE=$(git merge-base HEAD main)
git diff --check "$BASE"..HEAD
```

Expected: No output.

- [ ] **Step 3: Search for stale filenames and stale learning language**

Run:

```bash
rg -n "03-self-attention-qkv|04-transformer-block|05-decoder-only-and-generation|第一次学习入口.*review|review note.*第一次学习" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/09-review-notes ai/ml-to-llm-roadmap/interview-paths ai/ml-to-llm-roadmap/04-transformer-architecture
```

Expected: No stale filename output. Any output about review notes must say they are not first-time learning entry points.

- [ ] **Step 4: Run local Markdown link checker**

Run:

```bash
node -e 'const fs=require("fs"), path=require("path"); const roots=["ai/ml-to-llm-roadmap.md","ai/ml-to-llm-roadmap/04-transformer-foundations","ai/ml-to-llm-roadmap/interview-paths","ai/ml-to-llm-roadmap/09-review-notes","ai/ml-to-llm-roadmap/04-transformer-architecture/README.md","ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md"]; const files=[]; for (const p of roots) { const s=fs.statSync(p); if (s.isDirectory()) { for (const f of fs.readdirSync(p)) if (f.endsWith(".md")) files.push(path.join(p,f)); } else if (p.endsWith(".md")) files.push(p); } const bad=[]; const re=/\[[^\]]+\]\(([^)]+)\)/g; for (const file of files) { const text=fs.readFileSync(file,"utf8"); for (const m of text.matchAll(re)) { let href=m[1].trim(); if (!href || href.startsWith("#") || /^[a-z]+:/i.test(href)) continue; href=href.split("#")[0].split("?")[0]; if (!href) continue; const target=path.normalize(path.join(path.dirname(file),href)); if (!fs.existsSync(target)) bad.push(`${file}: ${href} -> ${target}`); } } if (bad.length) { console.error(bad.join("\n")); process.exit(1); } console.log(`checked ${files.length} files, links ok`);'
```

Expected: Command prints `links ok`.

- [ ] **Step 5: Manual learning-flow review**

Read these files in order:

```text
ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
ai/ml-to-llm-roadmap/04-transformer-foundations/03-why-attention-needs-context.md
ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
ai/ml-to-llm-roadmap/04-transformer-foundations/08-decoder-only-generation.md
ai/ml-to-llm-roadmap/04-transformer-foundations/09-kv-cache-context-cost.md
ai/ml-to-llm-roadmap/interview-paths/ai-engineer-transformer.md
ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Confirm:

- Encoder/Decoder is explained before architecture variants.
- Architecture variants are explained before Decoder-only generation.
- KV Cache is separated from first-time Decoder-only explanation.
- The interview path and review note both say they are for after learning.

- [ ] **Step 6: Commit final verification note if fixes were needed**

If Step 5 requires small link or wording fixes, commit them:

```bash
git add ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/interview-paths ai/ml-to-llm-roadmap/09-review-notes ai/ml-to-llm-roadmap/04-transformer-architecture
git commit -m "docs: verify transformer systematic learning flow"
```

Expected: Commit succeeds if fixes were made. If no fixes were made, no commit is needed.
