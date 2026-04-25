# Transformer Principle Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the Transformer systematic learning path so `06` and `07` explain the principle layer directly, without requiring learners to jump into dense legacy references.

**Architecture:** Keep the current 9-lesson Transformer module intact. Add mechanism-level sections inside the existing `06` and `07` lessons, then update the module README to point learners to the new principle-layer coverage. Legacy docs remain as optional deep references at the end of the relevant lessons.

**Tech Stack:** Markdown documentation, existing `ai/ml-to-llm-roadmap` file structure, shell verification with `rg`, `git diff --check`, and a local Markdown link checker.

---

## File Structure

- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md`
  - Responsibility: Explain the original Encoder-Decoder Transformer, now including the concrete data flow through encoder self-attention, decoder masked self-attention, cross-attention, and train/inference differences.

- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md`
  - Responsibility: Explain Encoder-only, Encoder-Decoder, and Decoder-only as architecture variants, now including their training objectives and output shapes.

- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`
  - Responsibility: Keep the module navigation accurate and tell learners where the principle-layer explanations live.

## Task 1: Add Encoder-Decoder Data-Flow Principle Layer

**Files:**
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md`

- [ ] **Step 1: Read the target lesson and source references**

Run:

```bash
sed -n '1,260p' ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
sed -n '1,220p' ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md
```

Expected:
- The target lesson currently explains the mental model but does not spell out where Q/K/V come from in encoder self-attention, decoder masked self-attention, and cross-attention.
- The legacy reference contains useful attention details, but it is too dense to use as the main learner path.

- [ ] **Step 2: Insert the principle-layer section after `## 最小心智模型`**

Add this section after the existing minimal mental model and before `## 和 LLM 应用的连接`:

````markdown
## 原理层：Encoder 和 Decoder 的数据流

先把一个 Transformer block 里的 self-attention 回忆一下：当前 token 会产生一个 Query，用它去和一组 Key 做匹配，再按匹配权重读取对应的 Value。区别在于，不同位置的 Q/K/V 来自哪里，以及哪些位置允许被看见。

### Encoder self-attention：source token 之间互相读

Encoder 处理的是已经完整给定的 source sequence。以 `我 喜欢 苹果` 为例，Encoder 的每一层都会让每个 source token 产生自己的 Q/K/V：

```text
source tokens: 我 | 喜欢 | 苹果

每个 token 都产生:
  Q: 我现在想找什么信息
  K: 我能被别人用什么特征匹配到
  V: 如果别人关注我，我能提供什么内容
```

因为 source sequence 已经完整给定，`我` 可以看 `喜欢` 和 `苹果`，`苹果` 也可以反过来看 `我` 和 `喜欢`。所以 Encoder self-attention 通常是双向的。

这一步的输出不是一个单独向量，而是一组上下文表示：每个 source token 都变成了“结合整句上下文之后的 token 表示”。

### Decoder masked self-attention：target token 只能读已经出现的部分

Decoder 处理的是 target sequence，也就是正在生成的输出。生成英文翻译时，如果当前已经有 `I like`，模型要预测下一个 token，不能提前看到标准答案里的 `apples`。

所以 Decoder self-attention 也会从 target token 产生 Q/K/V，但会加 causal mask：

```text
target prefix: I | like | ?

位置 I:
  只能看 I

位置 like:
  可以看 I, like

下一个位置:
  可以看 I, like
  不能看未来答案 apples
```

这就是 masked self-attention。它不是让 Decoder “少理解一点”，而是强制模型遵守生成任务的时间顺序：只能根据已经出现的 target prefix 预测下一个 token。

### Cross-attention：Decoder 用当前生成需求去读 Encoder 结果

Decoder block 比 Encoder block 多一个 cross-attention。它连接的是两条序列：

```text
Encoder 输出:
  source 表示: 我' | 喜欢' | 苹果'

Decoder 当前状态:
  target prefix 表示: I' | like'

Cross-attention:
  Q 来自 Decoder 当前状态
  K/V 来自 Encoder 的 source 表示
```

这句话很关键：cross-attention 里的 Query 来自 Decoder，Key 和 Value 来自 Encoder。

直觉上，它在问：

> 我现在正在生成 target 里的这个位置，为了决定下一个词，应该回看 source sequence 的哪些部分？

如果 Decoder 正在生成 `apples`，它的 Query 可能会更关注 Encoder 输出里和 `苹果` 对应的 Key，然后读取那个位置的 Value。

### 训练时和推理时为什么不一样

训练时，标准答案已经存在。例如目标句子是 `I like apples`。模型通常会看到右移后的 target prefix：

```text
Decoder 输入: <BOS> | I | like
预测目标:       I | like | apples
```

这叫 teacher forcing。模型不是一次性复制答案，而是在每个位置学习“看到前面的 token 后，下一个 token 应该是什么”。

推理时没有标准答案，只有模型自己已经生成的内容：

```text
第 1 步: <BOS> -> I
第 2 步: <BOS> I -> like
第 3 步: <BOS> I like -> apples
```

所以推理必须逐 token 进行。这个区别会在后面的 Decoder-only 和 KV Cache 中继续出现。
````

- [ ] **Step 3: Update common mistakes and self-check questions**

In `## 常见误区`, keep the existing bullets and add these bullets:

```markdown
- Cross-attention 不是 Encoder 自己内部的 attention，而是 Decoder 用自己的 Query 去读取 Encoder 输出的 Key/Value。
- 训练时 Decoder 可以拿到右移后的标准答案前缀；推理时只能拿到模型已经生成的前缀。
```

In `## 自测`, replace the current list with:

```markdown
1. Source sequence 和 target sequence 分别是什么？
2. Encoder self-attention 的 Q/K/V 都来自哪里？
3. Decoder masked self-attention 为什么不能看未来 target token？
4. Cross-attention 中 Q、K、V 分别来自哪里？
5. 训练时右移后的 target prefix 和推理时已生成 prefix 有什么区别？
```

- [ ] **Step 4: Add deep-reference links before `## 下一步`**

Insert this section immediately before `## 下一步`:

```markdown
## 深入参考

本篇已经覆盖主线需要的 Encoder/Decoder 数据流。读完后，如果你想看更公式化的 attention 计算，可以再读旧版参考：

- [Transformer 核心架构](../04-transformer-architecture/01-transformer-core.md)
```

- [ ] **Step 5: Verify the lesson contains all required mechanism terms**

Run:

```bash
rg -n "原理层|Encoder self-attention|Decoder masked self-attention|Cross-attention|Q 来自 Decoder|Key 和 Value 来自 Encoder|右移后的 target prefix|teacher forcing" ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
git diff --check
```

Expected:
- `rg` prints matches for every mechanism term.
- `git diff --check` prints no output and exits successfully.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md
git commit -m "docs: explain encoder decoder mechanics"
```

Expected:
- Commit succeeds.

## Task 2: Add Architecture Variant Training-Objective Principle Layer

**Files:**
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md`

- [ ] **Step 1: Read the target lesson and source references**

Run:

```bash
sed -n '1,320p' ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
sed -n '1,260p' ai/ml-to-llm-roadmap/04-transformer-architecture/02-architecture-paradigms.md
sed -n '1,220p' ai/ml-to-llm-roadmap/05-pretrained-models/01-bert-family.md
sed -n '1,220p' ai/ml-to-llm-roadmap/05-pretrained-models/02-gpt-evolution.md
sed -n '1,220p' ai/ml-to-llm-roadmap/05-pretrained-models/03-milestones.md
```

Expected:
- The target lesson explains task shape and mental model.
- The references provide reusable material for MLM, CLM, BERT/GPT/T5, and text-to-text framing.

- [ ] **Step 2: Insert the principle-layer section after `## 最小心智模型`**

Add this section after the existing minimal mental model and before `## 和 LLM 应用的连接`:

````markdown
## 原理层：结构选择和训练目标

三种架构不只是“长得不一样”，它们通常也对应不同的训练目标和输出形态。理解这一层后，BERT、T5、GPT 的差异就不再只是背表格。

### Encoder-only：更适合理解型目标

Encoder-only 保留的是双向读取输入的能力。每个 token 都可以结合左右上下文形成表示，所以它天然适合“读完输入后做判断或产出表示”。

典型预训练目标是 MLM，也就是 Masked Language Modeling：

```text
输入: 我 喜欢 [MASK]
目标: 苹果
```

模型不是从左到右生成整句话，而是利用左右上下文预测被遮住的位置。这会推动模型学习上下文理解能力。

在应用里，Encoder-only 的输出常见有三种用法：

```text
token 表示 -> NER / token classification
句向量 -> embedding / semantic search
query-document 表示 -> rerank / matching
```

所以 BERT 类模型适合 embedding/rerank，不是因为它“不会生成所以只能检索”，而是因为它的结构和训练目标更偏向完整读取输入、形成可比较的表示。

### Encoder-Decoder：适合 source-to-target 学习

Encoder-Decoder 保留了两段式结构：Encoder 读 source，Decoder 根据 source 和已知 target prefix 预测下一个 target token。

训练时可以写成：

```text
source: 中文句子
decoder input: <BOS> I like
prediction target: I like apples
```

Decoder 的每一步预测都同时依赖两类信息：

- 通过 masked self-attention 读取已经出现的 target prefix。
- 通过 cross-attention 读取 Encoder 产出的 source 表示。

这让 Encoder-Decoder 很适合 source 和 target 明确不同的任务，例如翻译、摘要、改写、问答到结构化输出。T5 的 text-to-text 思路就是把多种 NLP 任务都改写成“输入文本 -> 输出文本”。

### Decoder-only：把所有条件都变成 prefix

Decoder-only 保留的是自回归生成能力。它通常使用 CLM，也就是 Causal Language Modeling / next-token prediction：

```text
输入前缀: The capital of France is
预测下一个 token: Paris
```

它不单独区分 source 和 target，而是把所有信息排成一个连续上下文：

```text
system instruction
user question
retrieved documents
tool schema
assistant answer prefix
```

模型要做的是在这个 prefix 后继续预测下一个 token。RAG 文档、历史对话、工具说明并不是通过 cross-attention 接进来，而是作为同一段上下文的一部分被 masked self-attention 读取。

### 为什么现代通用 LLM 多采用 Decoder-only

Decoder-only 对通用 LLM 友好，核心原因不是“Encoder 没用”，而是它把训练和推理都统一成同一种形式：

```text
给定 prefix -> 预测下一个 token -> 把新 token 接回 prefix -> 继续预测
```

这个形式有几个工程和规模化优势：

- 数据形态简单：网页、书籍、代码、对话都可以变成 next-token prediction。
- 训练目标统一：不需要为每类任务单独设计输入输出结构。
- 推理接口统一：prompt、上下文、工具 schema、示例、历史消息都可以拼成 prefix。
- 应用组合方便：RAG、Agent、function calling 都可以表达成“给模型更多上下文，再让它继续生成”。

因此 Decoder-only 成为现代通用 LLM 的主流，不代表 Encoder-only 或 Encoder-Decoder 过时；它只是最适合大规模通用生成这个目标。
````

- [ ] **Step 3: Update common mistakes and self-check questions**

In `## 常见误区`, keep the existing bullets and add these bullets:

```markdown
- BERT、T5、GPT 的差异不只是模型名字不同，还包括结构、训练目标和输出形态的差异。
- Decoder-only 能读 prompt 里的材料，不是因为它有单独的 Encoder，而是因为材料已经被放进同一个 prefix。
```

In `## 自测`, replace the current list with:

```markdown
1. 为什么 BERT 适合 embedding/rerank？
2. MLM 和 CLM 的核心区别是什么？
3. T5 为什么适合 source-to-target 任务？
4. GPT 为什么可以把检索文档和用户问题放进同一个 prompt？
5. 三种架构的输入输出形式分别是什么？
6. 为什么现代通用 LLM 多采用 Decoder-only？
```

- [ ] **Step 4: Add deep-reference links before `## 下一步`**

Insert this section immediately before `## 下一步`:

```markdown
## 深入参考

本篇已经覆盖主线需要的三种架构范式。读完后，如果你想看更压缩的模型对比和预训练目标，可以再读旧版参考：

- [三大架构范式](../04-transformer-architecture/02-architecture-paradigms.md)
- [BERT 系列：理解型模型](../05-pretrained-models/01-bert-family.md)
- [GPT 演进：生成式模型](../05-pretrained-models/02-gpt-evolution.md)
- [预训练模型里程碑](../05-pretrained-models/03-milestones.md)
```

- [ ] **Step 5: Verify the lesson contains all required principle terms**

Run:

```bash
rg -n "原理层|MLM|Masked Language Modeling|CLM|Causal Language Modeling|source-to-target|text-to-text|prefix|next-token prediction|Decoder-only 成为现代通用 LLM 的主流" ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
git diff --check
```

Expected:
- `rg` prints matches for every principle term.
- `git diff --check` prints no output and exits successfully.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
git commit -m "docs: explain transformer variant objectives"
```

Expected:
- Commit succeeds.

## Task 3: Update Transformer Module Navigation

**Files:**
- Modify: `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`

- [ ] **Step 1: Update the learning-path table descriptions**

In the `## 学习路径` table, replace the row descriptions for lessons 6 and 7 with:

```markdown
| 6 | [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md) | 原始 Transformer 的 Encoder/Decoder 分工、数据流和 cross-attention |
| 7 | [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md) | Encoder-only、Encoder-Decoder、Decoder-only 的结构选择和训练目标 |
```

- [ ] **Step 2: Update the key concept location section**

In `## 关键概念定位`, replace the two bullets for `06` and `07` with:

```markdown
- [06-original-transformer-encoder-decoder.md](./06-original-transformer-encoder-decoder.md)：解释原始 Transformer 为什么分 Encoder 和 Decoder，并进一步讲清 Encoder self-attention、Decoder masked self-attention、cross-attention 的数据流，以及训练/推理时 Decoder 输入的区别。
- [07-transformer-architecture-variants.md](./07-transformer-architecture-variants.md)：解释 Encoder-only、Encoder-Decoder、Decoder-only 如何从 Encoder / Decoder 结构里演化出来，并进一步讲清 MLM、CLM、source-to-target、prefix 续写这些训练目标和输出形态差异。
```

- [ ] **Step 3: Update the completion checklist**

In `## 学完后你应该能回答`, ensure these bullets are present:

```markdown
- Cross-attention 中 Q、K、V 分别来自哪里。
- Encoder-only、Encoder-Decoder、Decoder-only 的训练目标分别倾向什么。
```

If the existing list already contains nearby bullets, replace them rather than duplicating similar wording.

- [ ] **Step 4: Verify navigation mentions the principle-layer concepts**

Run:

```bash
rg -n "数据流|cross-attention|训练目标|MLM|CLM|prefix|Q、K、V" ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
git diff --check
```

Expected:
- `rg` prints matches in the learning-path table, key concept section, and completion checklist.
- `git diff --check` prints no output and exits successfully.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
git commit -m "docs: update transformer principle navigation"
```

Expected:
- Commit succeeds.

## Task 4: Final Validation

**Files:**
- Verify: `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md`
- Verify: `ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md`
- Verify: `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`

- [ ] **Step 1: Run whitespace validation over the implementation commits**

Run:

```bash
git diff --check HEAD~3..HEAD
```

Expected:
- No output.
- Exit code `0`.

- [ ] **Step 2: Run local Markdown link validation for changed files**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import re
import sys

files = [
    Path("ai/ml-to-llm-roadmap/04-transformer-foundations/README.md"),
    Path("ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md"),
    Path("ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md"),
]

errors = []
pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

for file in files:
    text = file.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (file.parent / path_part).resolve()
        if not resolved.exists():
            errors.append(f"{file}: missing link target {target}")

if errors:
    print("\n".join(errors))
    sys.exit(1)

print(f"checked {len(files)} files, links ok")
PY
```

Expected:
- Output: `checked 3 files, links ok`
- Exit code `0`.

- [ ] **Step 3: Verify spec acceptance questions are answerable from the main docs**

Run:

```bash
rg -n "Q 来自 Decoder|Key 和 Value 来自 Encoder|右移后的 target prefix|MLM|CLM|prefix|BERT 类模型适合 embedding/rerank|Decoder-only 成为现代通用 LLM 的主流" ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md ai/ml-to-llm-roadmap/04-transformer-foundations/07-transformer-architecture-variants.md
```

Expected:
- Each acceptance concept from the spec appears in `06` or `07`.

- [ ] **Step 4: Confirm working tree cleanliness**

Run:

```bash
git status --short
```

Expected:
- No output.
