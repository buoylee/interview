# ML to LLM Transformer Sample Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first complete sample of the redesigned ML-to-LLM roadmap: a new AI Engineer entry route, a Transformer foundations module, supporting deep-learning foundations, one interview review note, and migration notices on legacy files.

**Architecture:** The implementation keeps legacy subject-based directories in place while adding the new capability-based route. New tutorial documents live under `ai/ml-to-llm-roadmap/04-transformer-foundations/`, prerequisite teaching material lives under `ai/ml-to-llm-roadmap/foundations/deep-learning/`, and interview recall material lives under `ai/ml-to-llm-roadmap/09-review-notes/`. The top-level `ai/ml-to-llm-roadmap.md` becomes the default learning console and points learners into the new sample without deleting old content.

**Tech Stack:** Markdown documentation, existing repository file layout, shell verification with `rg`, `find`, `git diff --check`, and manual reading passes.

---

## File Structure

Create:

- `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`
  Module landing page for the new Transformer sample.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md`
  Motivation-first bridge from RAG/Agent work to Transformer internals.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md`
  Systematic explanation of token IDs, embeddings, dimensionality, and why vectors are the input to Attention.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md`
  Dependency-ordered Self-Attention tutorial with Q/K/V, scaling, softmax, multi-head, and application implications.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md`
  Transformer block tutorial connecting Attention, FFN, Residual, LayerNorm/RMSNorm, and Pre-Norm.

- `ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md`
  Decoder-only generation tutorial connecting causal masking, next-token prediction, KV Cache, and why GPT-style models dominate.

- `ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md`
  Foundation file for neuron, linear layer, MLP, and activation functions.

- `ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md`
  Foundation file for forward pass, loss, backpropagation, gradient vanishing, gradient explosion, and gradient clipping.

- `ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md`
  Foundation file for residual connections, normalization, initialization, and why these stabilize deep networks.

- `ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md`
  Foundation file for Transformer FFN, GELU, GLU, SwiGLU, and why modern LLMs use gated FFNs.

- `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md`
  Interview recall note for Transformer core concepts.

Modify:

- `ai/ml-to-llm-roadmap.md`
  Reframe as the new AI Engineer interview-oriented entry point.

- `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md`
  Add a migration notice at the top, pointing to the new deep-learning foundations and Transformer sample.

- `ai/ml-to-llm-roadmap/04-transformer-architecture/README.md`
  Add a migration notice pointing to the new Transformer sample.

- `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`
  Add a migration notice pointing to the new Transformer sample and review note.

Do not modify:

- Other legacy roadmap files unless a verification step reveals a broken link caused by this migration.
- The approved spec at `docs/superpowers/specs/2026-04-24-ml-to-llm-roadmap-redesign.md`.

## Content Standards

Every new main-route tutorial must include these sections in this order:

```markdown
## 你为什么要学这个
## 学前检查
## 一个真实问题
## 核心概念
## 和 LLM 应用的连接
## 面试怎么问
## 自测
## 下一步
```

Every new foundation file must include these sections in this order:

```markdown
## 这篇只解决什么
## 你在主线哪里会用到
## 最小直觉
## 最小公式
## 逐步例子
## 常见误解
## 回到主线
```

The review note must include these sections in this order:

```markdown
## 30 秒答案
## 2 分钟展开
## 面试官追问
## 易混点
## 记忆钩子
## 项目连接
## 深入阅读
```

Content must follow these writing rules:

- Do not introduce an advanced term before either explaining it briefly or linking to a foundation file.
- Keep interview answers out of tutorial bodies except for short "面试怎么问" question lists.
- Use concrete RAG/Agent/LLM application hooks when explaining why a concept matters.
- Use formulas only when they unlock understanding, and define every symbol.
- Prefer small ASCII diagrams over long prose when explaining flow.

## Task 1: Update Main Entry Point

**Files:**

- Modify: `ai/ml-to-llm-roadmap.md`

- [ ] **Step 1: Read current entry point and confirm existing role**

Run:

```bash
sed -n '1,140p' ai/ml-to-llm-roadmap.md
```

Expected: The file starts with the old subject-sequence route and the quick two-week path.

- [ ] **Step 2: Replace the top-level structure with the new learning console**

Edit `ai/ml-to-llm-roadmap.md` so it starts with this structure:

```markdown
# AI Engineer 面试导向：ML → LLM 系统学习路线

> **定位**：你做过一些 RAG / Agent / LLM 应用开发，但对 LLM 底层只有基础理解。本路线从 AI Engineer 综合面试能力出发，反向补齐 Transformer、训练、推理、评估和系统设计知识。

## 如何使用这套路线路

| 你的目标 | 推荐路径 |
|---------|---------|
| 面试在 2 周内 | 先走「面试冲刺路径」，只看主线模块和 review notes |
| 想系统补底层 | 走「系统学习路径」，主线遇到不懂再回 foundations |
| 正在做 RAG / Agent 项目 | 从 RAG、Agent、生成控制三个模块开始，再补 Transformer |

## 新路线总览

```text
01 RAG 与检索系统
02 Agent 与工具调用
03 生成控制与结构化输出
04 Transformer 必要基础
05 训练、对齐与微调
06 推理优化、部署与成本
07 评估、安全与生产排查
08 系统设计与项目叙事
09 面试复习笔记
foundations 按需补课
```

## 第一批已迁移样板

| 模块 | 内容 | 入口 |
|------|------|------|
| Transformer 必要基础 | 从 AI Engineer 视角系统理解 Transformer | [04-transformer-foundations](./ml-to-llm-roadmap/04-transformer-foundations/) |
| Deep Learning 补课 | 支撑 Transformer 的神经网络基础 | [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/) |
| Transformer 面试复习 | 30 秒答案、追问、易混点和项目连接 | [03-transformer-core-cheatsheet](./ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md) |

## 面试冲刺路径

1. Transformer 必要基础：[04-transformer-foundations](./ml-to-llm-roadmap/04-transformer-foundations/)
2. Transformer 复习笔记：[09-review-notes/03-transformer-core-cheatsheet.md](./ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md)
3. 旧版 RAG 深度材料：[07/01-rag-deep-dive.md](./ml-to-llm-roadmap/07-theory-practice-bridge/01-rag-deep-dive.md)
4. 旧版 Agent 架构材料：[07/02-agent-architecture.md](./ml-to-llm-roadmap/07-theory-practice-bridge/02-agent-architecture.md)
5. 旧版系统设计材料：[08/02-system-design.md](./ml-to-llm-roadmap/08-interview-synthesis/02-system-design.md)

## 系统学习路径

1. 从主线模块开始，不从数学开始。
2. 每篇主线教程的「学前检查」会告诉你缺哪个基础。
3. 缺基础时进入 `foundations/`，补完再回主线。
4. 每个模块学完后，用 `09-review-notes/` 做面试复盘。

## 迁移说明

旧的 `00-08` 学科式目录暂时保留，避免丢失已有材料。新路线会逐步把有价值内容迁入能力模块、foundations 和 review notes。迁移完成前，旧目录可以作为参考资料，但不再作为默认学习入口。
```

Keep a short "旧版目录索引" section after the new intro so users can still find legacy files. Do not keep the old long stage-by-stage body as the primary content if it makes the entry point hard to scan.

- [ ] **Step 3: Verify key links exist**

Run:

```bash
find ai/ml-to-llm-roadmap -maxdepth 2 -type d -print
```

Expected: Legacy directories still exist. New directories may not exist yet if this task is executed before Task 2; missing new directories are acceptable until Task 2 completes.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap.md
git commit -m "docs: add ai engineer roadmap entry"
```

Expected: Commit succeeds.

## Task 2: Create Transformer Module Landing Page and Motivation Lesson

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md`
- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/04-transformer-foundations
```

Expected: Directory exists.

- [ ] **Step 2: Write `README.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/README.md` with this structure and content:

```markdown
# 04 Transformer 必要基础

> **定位**：这不是算法岗训练手册，而是 AI Engineer 面试需要掌握的 Transformer 底层模型。目标是让你能解释 RAG、Agent、结构化输出、上下文长度、推理成本背后的模型机制。

## 你会学到什么

- Token 如何变成向量
- Self-Attention 如何让 token 彼此读取信息
- Q/K/V、softmax、缩放、多头注意力分别解决什么问题
- Transformer Block 里的 Attention、FFN、Residual、LayerNorm/RMSNorm 如何配合
- 为什么现代 LLM 大多是 Decoder-only
- Transformer 知识如何连接 KV Cache、长上下文、工具调用和幻觉排查

## 学习路径

| 顺序 | 文件 | 解决的问题 |
|------|------|------------|
| 1 | [01-why-ai-engineers-need-transformer.md](./01-why-ai-engineers-need-transformer.md) | 为什么应用工程师也要懂 Transformer |
| 2 | [02-token-to-vector.md](./02-token-to-vector.md) | 文本如何进入模型 |
| 3 | [03-self-attention-qkv.md](./03-self-attention-qkv.md) | Self-Attention 到底怎么算 |
| 4 | [04-transformer-block.md](./04-transformer-block.md) | 一个 Transformer 层由哪些零件组成 |
| 5 | [05-decoder-only-and-generation.md](./05-decoder-only-and-generation.md) | 为什么 GPT 类模型能逐 token 生成 |

## 学前检查

如果下面概念不熟，先按需补课：

| 概念 | 补课材料 |
|------|----------|
| 神经元、线性层、激活函数 | [foundations/deep-learning/01-neuron-mlp-activation.md](../foundations/deep-learning/01-neuron-mlp-activation.md) |
| 反向传播、梯度消失/爆炸 | [foundations/deep-learning/02-backprop-gradient-problems.md](../foundations/deep-learning/02-backprop-gradient-problems.md) |
| Residual、LayerNorm、初始化 | [foundations/deep-learning/03-normalization-residual-initialization.md](../foundations/deep-learning/03-normalization-residual-initialization.md) |
| FFN、GELU、SwiGLU | [foundations/deep-learning/04-ffn-gating-for-transformer.md](../foundations/deep-learning/04-ffn-gating-for-transformer.md) |

## 学完后你应该能回答

- 从头讲 Self-Attention 的计算流程。
- 为什么 Attention 要除以 `sqrt(d_k)`。
- Multi-Head Attention 为什么不是简单重复。
- Residual、LayerNorm、FFN 在 Transformer Block 中分别负责什么。
- 为什么 Decoder-only 成为主流 LLM 架构。
- Transformer 的哪些机制会影响上下文长度、延迟和推理成本。

## 复习入口

学完后用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 做面试复盘。

> ⬅️ [返回总路线](../../ml-to-llm-roadmap.md)
```

- [ ] **Step 3: Write `01-why-ai-engineers-need-transformer.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md` with these sections:

```markdown
# 4.1 为什么 AI Engineer 需要懂 Transformer

## 你为什么要学这个

你不一定要训练一个大模型，但你需要解释大模型为什么会这样工作。RAG 召回了正确文档但回答仍然错、Agent 工具调用参数不稳定、长上下文成本暴涨、结构化输出偶尔坏掉，这些问题都和 Transformer 的输入表示、注意力、解码和上下文机制有关。

## 学前检查

你需要知道：

- Token 是模型处理文本的最小单位之一；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- 神经网络是一组线性变换和非线性函数的组合；不熟先看 [神经元、MLP 与激活函数](../foundations/deep-learning/01-neuron-mlp-activation.md)。

## 一个真实问题

你的 RAG 系统检索到了包含答案的文档，但模型仍然回答错。可能原因不只在检索层，也可能是：

- 文档片段太长，关键信息在上下文中被稀释。
- Prompt 中多个信息互相竞争，模型注意力分配不理想。
- 模型按生成概率续写，而不是做数据库式精确查询。
- 解码过程在格式、事实和流畅性之间做了取舍。

理解 Transformer 能帮助你把问题拆到更具体的层：输入表示、注意力分配、上下文位置、解码行为和推理缓存。

## 核心概念

### Transformer 解决的核心问题

传统序列模型按顺序读文本，长距离信息要一步步传递。Transformer 让每个 token 可以直接查看其他 token，并根据相关性聚合信息。

```text
RNN/LSTM: token 1 -> token 2 -> token 3 -> token 4
Transformer: 每个 token 同时查看所有 token
```

### AI Engineer 需要掌握的最小模型

```text
文本 -> token IDs -> embedding 向量 -> Transformer Blocks -> logits -> 下一个 token
```

其中：

- `embedding` 决定文本如何进入模型。
- `attention` 决定 token 之间如何读取信息。
- `FFN` 决定每个 token 如何独立加工信息。
- `residual + normalization` 决定深层模型能否稳定运行。
- `decoder-only + causal mask` 决定 GPT 类模型如何逐 token 生成。

## 和 LLM 应用的连接

| 应用问题 | Transformer 相关机制 |
|----------|----------------------|
| RAG 命中文档但回答错 | 上下文组织、注意力竞争、位置影响 |
| Agent 工具调用参数不稳 | 解码、结构化输出、上下文约束 |
| 长上下文慢且贵 | Attention 复杂度、KV Cache |
| 模型幻觉 | 训练目标、生成概率、上下文证据不足 |
| 小模型和大模型能力差异 | 层数、宽度、上下文建模和训练规模 |

## 面试怎么问

- 你做应用为什么还需要懂 Transformer？
- RAG 系统里，Transformer 知识能帮你排查什么问题？
- 为什么长上下文会带来成本和效果问题？
- Agent 的工具调用为什么不是简单 JSON 拼接问题？

完整答法见 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。

## 自测

1. Transformer 相比 RNN/LSTM，最关键的结构差异是什么？
2. 为什么 RAG 答错不一定是向量检索的问题？
3. 为什么结构化输出失败可能和解码有关？
4. 长上下文为什么既影响成本，也影响质量？

## 下一步

下一篇读 [02-token-to-vector.md](./02-token-to-vector.md)，先搞清楚文本如何变成模型能处理的向量。
```

- [ ] **Step 4: Verify section order**

Run:

```bash
rg -n "^(#|##) " ai/ml-to-llm-roadmap/04-transformer-foundations/README.md ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md
```

Expected: The README has clear module sections. The lesson has the exact main-route template sections.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/README.md ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md
git commit -m "docs: add transformer foundations entry"
```

Expected: Commit succeeds.

## Task 3: Create Token-to-Vector and Self-Attention Lessons

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md`
- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md`

- [ ] **Step 1: Write `02-token-to-vector.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md` with these content requirements:

```markdown
# 4.2 从 Token 到向量

## 你为什么要学这个

LLM 不能直接处理字符串。它先把文本切成 token，再把 token ID 映射成向量。RAG 分块、上下文长度、价格、截断、工具调用格式，都会受 tokenization 和 embedding 表示影响。

## 学前检查

你需要知道：

- 向量是数字列表，可以表示一个对象的特征。
- 矩阵乘法可以把一批向量一起变换；不熟时回看旧版 [线性代数基础](../00-math-foundations/01-linear-algebra.md)。

## 一个真实问题

同一段文档按字符看不长，但放进模型后超出上下文窗口。原因是模型限制的是 token 数，不是字数。英文、中文、代码、JSON 的 token 切分效率不同，所以 RAG 分块不能只按字符数估算。

## 核心概念

### 文本进入模型的路径

```text
"用户输入" -> tokenizer -> token IDs -> embedding table -> token vectors
```

### Token ID 不是语义

Token ID 只是词表中的编号。模型真正计算的是 embedding 向量。

### Embedding Table 是一个查表矩阵

```text
词表大小 = V
向量维度 = d_model
Embedding Table 形状 = V x d_model
```

如果 token ID 是 `314`，模型取出 embedding table 第 `314` 行作为这个 token 的向量。

### 位置还没有进入

只查 embedding 时，同一个 token 在不同位置拿到的是同一类词向量。Transformer 还需要位置编码或位置机制告诉模型顺序信息。

## 和 LLM 应用的连接

| 应用现象 | 底层原因 |
|----------|----------|
| 同样字数的中文、英文、代码价格不同 | token 数不同 |
| JSON 输出容易变长 | 标点、引号、字段名也会占 token |
| RAG chunk 需要控制长度 | 模型上下文按 token 限制 |
| 长 prompt 会变慢 | 后续 Attention 计算和 KV Cache 都随 token 增长 |

## 面试怎么问

- Token、token ID、embedding 向量是什么关系？
- 为什么上下文窗口按 token 计数？
- Embedding table 的形状是什么？
- 为什么只靠 token embedding 还不知道词序？

## 自测

1. Token ID 和 embedding 向量有什么区别？
2. 为什么 RAG 分块不应该只按字符数？
3. Embedding table 的行数和列数分别代表什么？
4. 位置编码解决的是什么问题？

## 下一步

下一篇读 [03-self-attention-qkv.md](./03-self-attention-qkv.md)，看这些 token 向量如何互相读取信息。
```

- [ ] **Step 2: Write `03-self-attention-qkv.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md` with these content requirements:

```markdown
# 4.3 Self-Attention 与 Q/K/V

## 你为什么要学这个

Self-Attention 是 LLM 理解上下文的核心机制。面试里的 Q/K/V、`sqrt(d_k)`、Multi-Head、长上下文复杂度，都是从这一节展开。

## 学前检查

你需要知道：

- token 已经被表示成向量；不熟先看 [02-token-to-vector.md](./02-token-to-vector.md)。
- softmax 会把一组分数变成和为 1 的权重；不熟时回看旧版 [概率基础](../00-math-foundations/02-probability.md)。

## 一个真实问题

在 RAG prompt 里，答案证据、系统指令、用户问题、历史对话同时出现。模型不是平均阅读所有文本，而是每个 token 根据注意力权重从上下文里取信息。上下文组织不好时，关键信息可能被其他内容竞争掉。

## 核心概念

### 一句话公式

```text
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

符号含义：

- `Q`：Query，当前 token 想找什么信息。
- `K`：Key，每个 token 提供什么匹配标签。
- `V`：Value，每个 token 真正提供的内容。
- `QK^T`：计算每个 token 对其他 token 的匹配分数。
- `sqrt(d_k)`：把点积分数缩放到 softmax 更稳定的范围。
- `softmax`：把分数变成注意力权重。

### 逐步流程

```text
X -> W_Q -> Q
X -> W_K -> K
X -> W_V -> V
QK^T -> scale -> softmax -> weights
weights V -> output
```

### 为什么除以 `sqrt(d_k)`

如果 Q 和 K 的维度很高，点积数值会变大。过大的分数会让 softmax 接近 one-hot，梯度变小，训练不稳定。除以 `sqrt(d_k)` 可以把分数拉回更合理的范围。

### Multi-Head Attention

单头注意力只能在一个表示空间里计算关系。多头把表示拆到多个子空间，让不同头可以关注不同关系，例如指代、语义相似、格式边界和局部邻近。

### 复杂度

Self-Attention 要计算 token 两两关系，所以序列长度为 `n` 时，注意力分数矩阵是 `n x n`。这就是长上下文成本高的根源之一。

## 和 LLM 应用的连接

| 应用问题 | Attention 视角 |
|----------|----------------|
| RAG 证据被忽略 | 证据 token 没有被关键生成 token 高权重关注 |
| Prompt 太长效果下降 | 无关 token 增加注意力竞争 |
| 长上下文成本高 | 注意力矩阵随 token 数平方增长 |
| KV Cache 占显存 | 每层都要缓存历史 token 的 K/V |

## 面试怎么问

- 从头讲 Self-Attention 的计算过程。
- Q、K、V 分别是什么？
- 为什么要除以 `sqrt(d_k)`？
- Multi-Head Attention 为什么有用？
- Attention 的复杂度瓶颈在哪里？

## 自测

1. `QK^T` 的结果矩阵每一行代表什么？
2. `softmax` 在 Attention 中起什么作用？
3. 为什么长上下文会显著增加计算成本？
4. Multi-Head 和单头 Attention 的核心区别是什么？

## 下一步

下一篇读 [04-transformer-block.md](./04-transformer-block.md)，把 Attention 放回完整 Transformer 层里。
```

- [ ] **Step 3: Verify formulas and section headings**

Run:

```bash
rg -n "sqrt\\(d_k\\)|QK\\^T|Multi-Head|KV Cache|^(#|##) " ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md
```

Expected: Self-Attention file contains Q/K/V, scaling, Multi-Head, complexity, and application links.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md
git commit -m "docs: add token and attention lessons"
```

Expected: Commit succeeds.

## Task 4: Create Transformer Block and Decoder-Only Lessons

**Files:**

- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md`
- Create: `ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md`

- [ ] **Step 1: Write `04-transformer-block.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md` with these content requirements:

```markdown
# 4.4 Transformer Block：Attention、FFN、Residual、Norm 如何配合

## 你为什么要学这个

Self-Attention 只是 Transformer 的一个零件。现代 LLM 能堆几十层甚至上百层，是因为 Attention、FFN、Residual、LayerNorm/RMSNorm 和初始化方式共同保证表达能力和训练稳定性。

## 学前检查

你需要知道：

- Self-Attention 的 Q/K/V 流程；不熟先看 [03-self-attention-qkv.md](./03-self-attention-qkv.md)。
- Residual、LayerNorm、初始化的作用；不熟先看 [normalization/residual foundation](../foundations/deep-learning/03-normalization-residual-initialization.md)。
- FFN 和门控激活；不熟先看 [FFN/gating foundation](../foundations/deep-learning/04-ffn-gating-for-transformer.md)。

## 一个真实问题

面试官问："Transformer 一层里除了 Attention 还有什么？" 如果只会 Q/K/V，回答是不完整的。一个可训练、可堆叠的 Transformer block 还必须解释 FFN、Residual 和 Norm。

## 核心概念

### Pre-Norm Decoder Block

```text
x
-> RMSNorm / LayerNorm
-> Self-Attention
-> Add residual
-> RMSNorm / LayerNorm
-> FFN / SwiGLU FFN
-> Add residual
```

### Attention 负责 token 间通信

Attention 让每个 token 从上下文里的其他 token 读取信息。

### FFN 负责 token 内加工

FFN 对每个 token 独立执行非线性变换。可以把它理解为每个 token 读完上下文后进行内部消化。

### Residual 保留原信息并改善梯度流

```text
y = x + F(x)
```

即使 `F(x)` 学得不好，原始 `x` 仍能传下去；反向传播时梯度也有更短路径。

### LayerNorm / RMSNorm 稳定数值尺度

Norm 让每层输入保持稳定，减少训练发散风险。现代 LLM 常用 Pre-Norm 和 RMSNorm。

## 和 LLM 应用的连接

| 应用现象 | Block 视角 |
|----------|------------|
| 大模型更强 | 更多 block 叠加带来更深的上下文加工 |
| 训练深层网络困难 | Residual 和 Norm 是稳定训练的关键 |
| 推理成本高 | 每层都要做 Attention 和 FFN |
| LoRA 常挂在 Attention/FFN | 这些线性层承载主要可调能力 |

## 面试怎么问

- Transformer Block 由哪些部分组成？
- FFN 在 Transformer 里有什么作用？
- Residual Connection 为什么重要？
- Pre-Norm 和 Post-Norm 有什么区别？
- RMSNorm 和 LayerNorm 的区别是什么？

## 自测

1. Attention 和 FFN 的职责差异是什么？
2. Residual 为什么能帮助深层模型训练？
3. Pre-Norm 为什么比 Post-Norm 更稳定？
4. 为什么 LoRA 常作用在 Attention 和 FFN 的线性层？

## 下一步

下一篇读 [05-decoder-only-and-generation.md](./05-decoder-only-and-generation.md)，看 Transformer Block 如何组成 GPT 类生成模型。
```

- [ ] **Step 2: Write `05-decoder-only-and-generation.md`**

Create `ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md` with these content requirements:

```markdown
# 4.5 Decoder-only 与逐 Token 生成

## 你为什么要学这个

GPT、LLaMA、Claude 这类主流 LLM 都以 Decoder-only 自回归生成为核心。理解 Decoder-only 可以解释 next-token prediction、causal mask、KV Cache、上下文窗口、流式输出和 Function Calling 的底层行为。

## 学前检查

你需要知道：

- Transformer Block 的组成；不熟先看 [04-transformer-block.md](./04-transformer-block.md)。
- Self-Attention 会让 token 读取上下文；不熟先看 [03-self-attention-qkv.md](./03-self-attention-qkv.md)。

## 一个真实问题

为什么模型生成 JSON 时会一个 token 一个 token 地输出？为什么已经生成过的上下文不需要每步完全重算？这些问题都来自自回归生成和 KV Cache。

## 核心概念

### 三种 Transformer 范式

| 范式 | 代表 | 典型用途 |
|------|------|----------|
| Encoder-only | BERT | 理解、分类、向量表示 |
| Encoder-Decoder | T5 | 输入到输出转换 |
| Decoder-only | GPT、LLaMA | 通用生成、对话、工具调用 |

### Decoder-only 的训练目标

```text
给定前面的 token，预测下一个 token
P(token_t | token_1, token_2, token_3, token_{t-1})
```

这就是自回归语言模型。

### Causal Mask

生成第 `t` 个 token 时，模型不能偷看未来 token。Causal Mask 会遮住当前位置之后的信息。

```text
token 1 can see: token 1
token 2 can see: token 1, token 2
token 3 can see: token 1, token 2, token 3
```

### Logits 到下一个 token

最后一层输出会变成词表上每个 token 的分数，也就是 logits。解码策略再从这些分数中选择下一个 token。

### KV Cache

生成新 token 时，历史 token 的 K/V 不变，可以缓存。这样每一步只需要为新 token 计算新的 K/V，并读取历史缓存。

## 和 LLM 应用的连接

| 应用现象 | Decoder-only 视角 |
|----------|-------------------|
| 流式输出 | 自回归逐 token 生成 |
| Function Calling 是生成结构化 token | 工具名和参数也是 token 序列 |
| KV Cache 占显存 | 每层缓存历史 token 的 K/V |
| 长对话越来越贵 | 上下文 token 越多，缓存和注意力读取越重 |
| 低温度更稳定 | 解码策略减少随机性 |

## 面试怎么问

- BERT、T5、GPT 架构有什么区别？
- 为什么现代 LLM 多数是 Decoder-only？
- 什么是 causal mask？
- KV Cache 为什么能加速推理？
- Function Calling 和普通文本生成在底层有什么共同点？

## 自测

1. Decoder-only 为什么不能看未来 token？
2. 自回归生成和流式输出是什么关系？
3. KV Cache 缓存的是什么？
4. Function Calling 为什么仍然可以理解成生成任务？

## 下一步

用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 做复习。如果 Residual、Norm 或 FFN 仍不清楚，回到 [deep-learning foundations](../foundations/deep-learning/) 补课。
```

- [ ] **Step 3: Verify section headings and Decoder-only concepts**

Run:

```bash
rg -n "Decoder-only|Causal Mask|KV Cache|Residual|RMSNorm|SwiGLU|^(#|##) " ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md
```

Expected: Both files include required topics and main-route sections.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md
git commit -m "docs: add transformer block and generation lessons"
```

Expected: Commit succeeds.

## Task 5: Create Deep-Learning Foundation Files

**Files:**

- Create: `ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md`
- Create: `ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md`
- Create: `ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md`
- Create: `ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md`

- [ ] **Step 1: Create foundation directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/foundations/deep-learning
```

Expected: Directory exists.

- [ ] **Step 2: Write neuron, MLP, and activation foundation**

Create `ai/ml-to-llm-roadmap/foundations/deep-learning/01-neuron-mlp-activation.md` with:

```markdown
# 神经元、MLP 与激活函数

## 这篇只解决什么

这篇只解释神经网络最小组件：线性层、偏置、激活函数、MLP。它不讲 Transformer Block、Pre-Norm、RMSNorm 或 SwiGLU，这些在后续 foundations 中单独讲。

## 你在主线哪里会用到

- [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)
- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)
- [FFN 与门控](./04-ffn-gating-for-transformer.md)

## 最小直觉

神经元先做加权求和，再用激活函数引入非线性。

```text
输入 x -> 线性变换 Wx + b -> 激活函数 -> 输出
```

没有激活函数，多层线性变换仍然等价于一层线性变换，网络无法表达复杂关系。

## 最小公式

```text
z = Wx + b
h = f(z)
```

- `x`：输入向量。
- `W`：权重矩阵。
- `b`：偏置。
- `f`：激活函数。
- `h`：输出向量。

## 逐步例子

```text
输入: [价格, 评分]
线性层: 0.8 * 价格 + 1.2 * 评分 - 0.5
激活: ReLU 只保留正值
输出: 一个新的特征
```

MLP 把多个这样的层堆起来，让模型从简单特征组合出复杂特征。

## 常见误解

| 误解 | 修正 |
|------|------|
| 神经元像生物大脑一样工作 | 工程上可以先理解为可学习的数学函数 |
| 层数越多一定越好 | 更深需要 Residual、Norm 和足够数据支撑 |
| 激活函数只是装饰 | 没有非线性，多层网络会退化成一层线性模型 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 FFN 为什么本质上是 MLP。
```

- [ ] **Step 3: Write backprop and gradient foundation**

Create `ai/ml-to-llm-roadmap/foundations/deep-learning/02-backprop-gradient-problems.md` with:

```markdown
# 反向传播、梯度消失与梯度爆炸

## 这篇只解决什么

这篇解释神经网络如何用 loss 更新参数，以及深层网络为什么会遇到梯度消失和梯度爆炸。它不要求你手推复杂偏导。

## 你在主线哪里会用到

- [Self-Attention 与 Q/K/V](../../04-transformer-foundations/03-self-attention-qkv.md)
- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)

## 最小直觉

训练神经网络就是让 loss 变小。反向传播从 loss 出发，计算每个参数应该往哪个方向调。

```text
前向: 输入 -> 模型 -> 预测 -> loss
反向: loss -> 梯度 -> 更新参数
```

## 最小公式

```text
theta_new = theta_old - learning_rate * gradient
```

- `theta`：模型参数。
- `learning_rate`：每次更新的步长。
- `gradient`：loss 对参数的变化方向。

## 逐步例子

```text
预测太大 -> loss 变大
梯度告诉模型: 让相关权重变小
优化器更新权重
下一次预测更接近目标
```

深层网络中，梯度要穿过很多层。如果每层都让梯度变小，就会梯度消失；如果每层都放大梯度，就会梯度爆炸。

## 常见误解

| 误解 | 修正 |
|------|------|
| 反向传播是倒着运行模型 | 它是倒着传播梯度，不是倒着生成输入 |
| 梯度消失只和 sigmoid 有关 | 深度、初始化、归一化、残差设计都会影响 |
| 梯度爆炸只能靠调小学习率 | 梯度裁剪、初始化和归一化也很重要 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 Residual 和 Norm 为什么是深层 Transformer 的关键。
```

- [ ] **Step 4: Write normalization, residual, and initialization foundation**

Create `ai/ml-to-llm-roadmap/foundations/deep-learning/03-normalization-residual-initialization.md` with:

```markdown
# Normalization、Residual 与初始化

## 这篇只解决什么

这篇解释深层网络稳定训练的三个基础零件：Residual Connection、Normalization、权重初始化。目标是为 Transformer Block 做铺垫。

## 你在主线哪里会用到

- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)
- [Decoder-only 与逐 Token 生成](../../04-transformer-foundations/05-decoder-only-and-generation.md)

## 最小直觉

深层网络难训练，是因为信号和梯度穿过很多层后容易变形。Residual 保留原信息，Normalization 稳定数值尺度，初始化让训练从合理状态开始。

## 最小公式

Residual:

```text
y = x + F(x)
```

LayerNorm:

```text
normalized_x = (x - mean(x)) / std(x)
```

RMSNorm:

```text
normalized_x = x / rms(x)
```

## 逐步例子

```text
没有 Residual:
x -> F1 -> F2 -> F3 -> 输出
每层都可能丢失原信息

有 Residual:
x -> x + F1(x) -> 继续
原信息始终有直达路径
```

Pre-Norm 把 Norm 放在 Attention/FFN 前面，通常比 Post-Norm 更容易训练深层模型。

## 常见误解

| 误解 | 修正 |
|------|------|
| Residual 只是把输入加回来 | 它同时改善信息流和梯度流 |
| BN 和 LN 可以随便替换 | Transformer 更适合 LN/RMSNorm，因为它不依赖 batch 统计 |
| RMSNorm 是完全不同的机制 | 它是更轻量的归一化方式，省掉均值中心化 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 Pre-Norm、Residual 和 RMSNorm 如何组成现代 LLM block。
```

- [ ] **Step 5: Write FFN and gating foundation**

Create `ai/ml-to-llm-roadmap/foundations/deep-learning/04-ffn-gating-for-transformer.md` with:

```markdown
# Transformer FFN、GELU 与 SwiGLU

## 这篇只解决什么

这篇解释 Transformer 里的 FFN 为什么存在，以及 GELU、GLU、SwiGLU 这类激活和门控为什么常见。它不重新讲 Self-Attention。

## 你在主线哪里会用到

- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)

## 最小直觉

Attention 让 token 之间交换信息，FFN 让每个 token 独立加工刚读到的信息。

```text
Attention = token 之间交流
FFN = 每个 token 自己消化
```

## 最小公式

标准 FFN:

```text
FFN(x) = W2 * activation(W1 * x + b1) + b2
```

SwiGLU 风格:

```text
FFN(x) = W2 * (SiLU(W1 * x) elementwise_multiply (V * x))
```

## 逐步例子

```text
输入 token 表示
-> 扩维到更大的隐藏维度
-> 非线性激活或门控
-> 投回原维度
```

扩维给模型更多加工空间，投回原维度保证可以继续和 residual 相加。

## 常见误解

| 误解 | 修正 |
|------|------|
| Transformer 只有 Attention 重要 | FFN 通常占大量参数和计算 |
| GELU/SwiGLU 是面试背诵细节 | 它们影响模型表达能力和训练效果 |
| 门控就是 if/else | 门控是连续的逐元素调节，不是硬规则 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 FFN 在 block 中的位置和作用。
```

- [ ] **Step 6: Verify foundation template compliance**

Run:

```bash
rg -n "^(#|##) " ai/ml-to-llm-roadmap/foundations/deep-learning/*.md
```

Expected: All four foundation files use the required foundation section template.

- [ ] **Step 7: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/foundations/deep-learning/*.md
git commit -m "docs: add deep learning foundations"
```

Expected: Commit succeeds.

## Task 6: Create Transformer Review Note

**Files:**

- Create: `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md`

- [ ] **Step 1: Create review notes directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/09-review-notes
```

Expected: Directory exists.

- [ ] **Step 2: Write Transformer review note**

Create `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md` with:

```markdown
# Transformer 核心面试速记

## 30 秒答案

Transformer 的核心是 Self-Attention。每个 token 通过 Q/K/V 计算自己应该关注上下文中的哪些 token，再把相关 token 的 V 加权汇总。现代 LLM 在 Attention 外还依赖 FFN、Residual、LayerNorm/RMSNorm 和 Decoder-only 自回归生成。应用工程师理解这些，才能解释 RAG 上下文组织、长上下文成本、KV Cache、工具调用和生成稳定性问题。

## 2 分钟展开

Self-Attention 的公式是：

```text
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
```

Q 表示当前 token 想找什么，K 表示每个 token 能被如何匹配，V 是实际内容。`QK^T` 得到 token 两两相关性，除以 `sqrt(d_k)` 防止 softmax 饱和，softmax 产生权重，再加权求和 V。Multi-Head 让不同头在不同子空间捕捉不同关系。

完整 Transformer Block 不是只有 Attention。Attention 负责 token 间通信，FFN 负责 token 内加工，Residual 保留原信息并改善梯度流，LayerNorm/RMSNorm 稳定数值。Decoder-only 模型通过 causal mask 只能看历史 token，用 next-token prediction 训练，并在推理时用 KV Cache 复用历史 K/V。

## 面试官追问

| 追问 | 回答 |
|------|------|
| 为什么除以 `sqrt(d_k)`？ | QK 点积的方差随维度增大，数值过大会让 softmax 接近 one-hot，梯度变小；缩放后分布更平滑。 |
| Multi-Head 有什么用？ | 多个头在不同子空间学习不同关系，比单头只能表达一种关系更灵活。 |
| FFN 的作用是什么？ | Attention 做跨 token 信息聚合，FFN 对每个 token 独立做非线性加工。 |
| 为什么要 Residual？ | 保留原始信息，提供更短的梯度路径，让深层网络更容易训练。 |
| 为什么现代 LLM 多是 Decoder-only？ | 自回归目标简单统一，适合通用生成、对话、工具调用和规模化训练。 |
| KV Cache 缓存什么？ | 缓存历史 token 在各层 Attention 中的 K/V，避免生成每个新 token 时重复计算历史上下文。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| Token ID vs Embedding | 以为 ID 本身有语义 | ID 是词表编号，embedding 向量才参与计算 |
| Attention vs FFN | 以为 Transformer 只有 Attention | Attention 负责交流，FFN 负责加工 |
| LayerNorm vs BatchNorm | 以为归一化都一样 | LN/RMSNorm 不依赖 batch，更适合序列和生成 |
| Encoder-only vs Decoder-only | 以为 BERT 和 GPT 只是训练数据不同 | 架构和注意力 mask 不同，任务定位也不同 |
| KV Cache vs Attention weights | 以为缓存的是注意力分数 | 缓存的是 K/V，不是 softmax 后的权重 |

## 记忆钩子

```text
Embedding 让文本变数字。
Attention 让 token 互相读。
FFN 让 token 自己想。
Residual 让信息别丢。
Norm 让数值别炸。
Decoder-only 让模型一步步写。
KV Cache 让历史别重算。
```

## 项目连接

讲 RAG 项目时可以这样连接：

- 检索命中文档但回答错：从上下文组织、注意力竞争和位置影响分析，不只怪向量库。
- 长文档问答成本高：解释 token 数、Attention 复杂度和 KV Cache。
- 工具调用不稳定：说明工具调用本质上也是 Decoder-only 模型生成结构化 token，需要约束解码或 schema 校验。
- 多轮 Agent 变慢：历史对话进入上下文，导致 token 增长和 KV Cache 增长。

## 深入阅读

- [为什么 AI Engineer 需要懂 Transformer](../04-transformer-foundations/01-why-ai-engineers-need-transformer.md)
- [从 Token 到向量](../04-transformer-foundations/02-token-to-vector.md)
- [Self-Attention 与 Q/K/V](../04-transformer-foundations/03-self-attention-qkv.md)
- [Transformer Block](../04-transformer-foundations/04-transformer-block.md)
- [Decoder-only 与逐 Token 生成](../04-transformer-foundations/05-decoder-only-and-generation.md)
```

- [ ] **Step 3: Verify review note template compliance**

Run:

```bash
rg -n "30 秒答案|2 分钟展开|面试官追问|易混点|记忆钩子|项目连接|深入阅读" ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Expected: All review note sections are present.

- [ ] **Step 4: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
git commit -m "docs: add transformer interview notes"
```

Expected: Commit succeeds.

## Task 7: Add Legacy Migration Notices

**Files:**

- Modify: `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-architecture/README.md`
- Modify: `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`

- [ ] **Step 1: Add notice to neural network basics**

Insert this block immediately after the H1 in `ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md`:

```markdown
> **迁移提示**：新版路线已将本篇拆成更小的基础补课材料，避免神经元、反向传播、归一化、Residual、RMSNorm、SwiGLU 在同一篇里混讲。
>
> - 神经元 / MLP / 激活函数：[foundations/deep-learning/01-neuron-mlp-activation.md](../foundations/deep-learning/01-neuron-mlp-activation.md)
> - 反向传播 / 梯度问题：[foundations/deep-learning/02-backprop-gradient-problems.md](../foundations/deep-learning/02-backprop-gradient-problems.md)
> - Normalization / Residual / 初始化：[foundations/deep-learning/03-normalization-residual-initialization.md](../foundations/deep-learning/03-normalization-residual-initialization.md)
> - FFN / GELU / SwiGLU：[foundations/deep-learning/04-ffn-gating-for-transformer.md](../foundations/deep-learning/04-ffn-gating-for-transformer.md)
>
> 本旧文暂时保留作为参考，不再作为默认学习入口。
```

Because this file is in `02-deep-learning/`, the correct relative links to `foundations/` start with `../foundations/`.

- [ ] **Step 2: Add notice to old Transformer README**

Insert this block immediately after the H1 in `ai/ml-to-llm-roadmap/04-transformer-architecture/README.md`:

```markdown
> **迁移提示**：新版路线已新增 AI Engineer 视角的 Transformer 样板模块：[04-transformer-foundations](../04-transformer-foundations/)。
>
> 旧版阶段 4 暂时保留作为更宽的参考材料；如果你是为了 LLM 应用工程师面试学习，优先看新版模块和 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md)。
```

- [ ] **Step 3: Add notice to old Transformer core**

Insert this block immediately after the H1 in `ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md`:

```markdown
> **迁移提示**：新版路线已将 Transformer 核心拆成更顺滑的学习链路：
>
> - 为什么应用工程师需要懂 Transformer：[../04-transformer-foundations/01-why-ai-engineers-need-transformer.md](../04-transformer-foundations/01-why-ai-engineers-need-transformer.md)
> - 从 Token 到向量：[../04-transformer-foundations/02-token-to-vector.md](../04-transformer-foundations/02-token-to-vector.md)
> - Self-Attention 与 Q/K/V：[../04-transformer-foundations/03-self-attention-qkv.md](../04-transformer-foundations/03-self-attention-qkv.md)
> - Transformer Block：[../04-transformer-foundations/04-transformer-block.md](../04-transformer-foundations/04-transformer-block.md)
> - Decoder-only 与逐 Token 生成：[../04-transformer-foundations/05-decoder-only-and-generation.md](../04-transformer-foundations/05-decoder-only-and-generation.md)
> - 面试速记：[../09-review-notes/03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md)
>
> 本旧文暂时保留作为综合参考，不再作为默认学习入口。
```

- [ ] **Step 4: Verify notices are present**

Run:

```bash
rg -n "迁移提示|04-transformer-foundations|03-transformer-core-cheatsheet" ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/04-transformer-architecture/README.md ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md
```

Expected: All three files contain migration notices and links to new materials.

- [ ] **Step 5: Commit**

Run:

```bash
git add ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/04-transformer-architecture/README.md ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md
git commit -m "docs: add legacy roadmap migration notices"
```

Expected: Commit succeeds.

## Task 8: Final Verification Pass

**Files:**

- Verify: `ai/ml-to-llm-roadmap.md`
- Verify: `ai/ml-to-llm-roadmap/04-transformer-foundations/*.md`
- Verify: `ai/ml-to-llm-roadmap/foundations/deep-learning/*.md`
- Verify: `ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md`
- Verify: legacy files modified in Task 7

- [ ] **Step 1: Check changed files**

Run:

```bash
git status --short
```

Expected: No uncommitted changes if every prior task committed. If there are uncommitted changes, inspect them before proceeding.

- [ ] **Step 2: Check markdown whitespace**

Run:

```bash
git diff --check HEAD~7..HEAD
```

Expected: No whitespace errors.

- [ ] **Step 3: Check for incomplete markers**

Run:

```bash
rg -n -e "T""BD" -e "T""ODO" -e "placeh""older" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/foundations/deep-learning ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Expected: No matches. If the command exits with code 1 and no output, that is acceptable.

- [ ] **Step 4: Check required sections**

Run:

```bash
rg -n "你为什么要学这个|学前检查|一个真实问题|核心概念|和 LLM 应用的连接|面试怎么问|自测|下一步" ai/ml-to-llm-roadmap/04-transformer-foundations/*.md
```

Expected: Each main-route lesson has all required main-route sections.

Run:

```bash
rg -n "这篇只解决什么|你在主线哪里会用到|最小直觉|最小公式|逐步例子|常见误解|回到主线" ai/ml-to-llm-roadmap/foundations/deep-learning/*.md
```

Expected: Each foundation file has all required foundation sections.

- [ ] **Step 5: Check links by inspection**

Run:

```bash
rg -n "\\[[^]]+\\]\\([^)]+" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/04-transformer-foundations ai/ml-to-llm-roadmap/foundations/deep-learning ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md ai/ml-to-llm-roadmap/02-deep-learning/01-neural-network-basics.md ai/ml-to-llm-roadmap/04-transformer-architecture/README.md ai/ml-to-llm-roadmap/04-transformer-architecture/01-transformer-core.md
```

Expected: Review output and confirm every relative path points to an existing file.

- [ ] **Step 6: Read the new learner path end to end**

Read in this order:

```bash
sed -n '1,220p' ai/ml-to-llm-roadmap.md
sed -n '1,220p' ai/ml-to-llm-roadmap/04-transformer-foundations/README.md
sed -n '1,220p' ai/ml-to-llm-roadmap/04-transformer-foundations/01-why-ai-engineers-need-transformer.md
sed -n '1,240p' ai/ml-to-llm-roadmap/04-transformer-foundations/02-token-to-vector.md
sed -n '1,280p' ai/ml-to-llm-roadmap/04-transformer-foundations/03-self-attention-qkv.md
sed -n '1,260p' ai/ml-to-llm-roadmap/04-transformer-foundations/04-transformer-block.md
sed -n '1,260p' ai/ml-to-llm-roadmap/04-transformer-foundations/05-decoder-only-and-generation.md
sed -n '1,260p' ai/ml-to-llm-roadmap/09-review-notes/03-transformer-core-cheatsheet.md
```

Expected: The path reads smoothly from AI Engineer motivation to tokenization, Attention, block structure, generation, and review. If an advanced term appears before explanation or link, edit the relevant file and commit a fix.

- [ ] **Step 7: Final status**

Run:

```bash
git status --short
```

Expected: Working tree is clean.
