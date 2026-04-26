# RAG And Agent Systematization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematize the remaining RAG and Agent roadmap areas into first-time learning modules, interview paths, and review notes.

**Architecture:** Add two new default mainline directories, `01-rag-retrieval-systems/` and `02-agent-tool-use/`, while preserving old reference material. Then add interview paths and review notes, and update the root roadmap plus old-reference README navigation so RAG and Agent are no longer deferred.

**Tech Stack:** Markdown documentation, existing `ai/ml-to-llm-roadmap` structure, shell verification with `rg`, `git diff --check`, and a local Markdown link checker.

---

## Scope

Included:

1. RAG 与检索系统
2. Agent 与工具调用
3. Corresponding interview paths
4. Corresponding review notes
5. Root and legacy navigation updates

Not included:

1. Rewriting old deep-dive files wholesale.
2. Vendor SDK, framework, or live API documentation.
3. Turning RAG into a vector database product guide.
4. Turning Agent into a LangGraph/CrewAI/AutoGen tutorial.

## File Structure

Create:

- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/README.md`
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/01-rag-problem-boundary.md`
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/02-indexing-embedding-retrieval.md`
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md`
- `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md`

- `ai/ml-to-llm-roadmap/02-agent-tool-use/README.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/01-agent-boundary-and-loop.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/02-tool-use-and-recovery.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/03-state-memory-and-planning.md`
- `ai/ml-to-llm-roadmap/02-agent-tool-use/04-agent-evaluation-safety-production.md`

- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md`
- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md`

- `ai/ml-to-llm-roadmap/09-review-notes/01-rag-retrieval-systems-cheatsheet.md`
- `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md`

Modify:

- `ai/ml-to-llm-roadmap.md`
- `ai/ml-to-llm-roadmap/09-review-notes/README.md`
- `ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md`
- `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md`

## System Learning Page Standard

Every new system-learning page must use this exact heading order:

```markdown
## 这篇解决什么问题
## 学前检查
## 概念为什么出现
## 最小心智模型
## 最小例子
## 原理层
## 和应用/面试的连接
## 常见误区
## 自测
## 回到主线
```

Rules:

- Introduce every major concept through the problem it solves.
- Include a small concrete example on every page.
- Link back to foundation modules when relevant.
- Keep system pages as first-time learning material, not interview cheatsheets.
- Do not rely on a specific library, framework, SDK, or vector database product.

## Interview Path Standard

Every new interview path must include:

```markdown
# AI Engineer 面试路径：<模块名>

## 适用场景
## 90 分钟冲刺
## 半天复盘
## 必答问题
## 可跳过内容
## 复习笔记
```

Rules:

- Link to system-learning pages first.
- Link to the corresponding review note last.
- Include 5 to 8 must-answer questions.
- Keep explanations short; this is a route, not a tutorial.

## Review Note Standard

Every new review note must include:

```markdown
# <模块名> 面试速记

## 30 秒答案
## 2 分钟展开
## 高频追问
## 易混点
## 项目连接
## 反向链接
```

Rules:

- The 30-second answer must be concise enough to say aloud.
- Include at least 4 high-frequency follow-ups.
- Link back to system-learning pages.
- Do not introduce core concepts absent from the system-learning pages.

---

## Task 1: Build RAG Retrieval Systems Module

**Files:**

- Create: `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/README.md`
- Create: `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/01-rag-problem-boundary.md`
- Create: `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/02-indexing-embedding-retrieval.md`
- Create: `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md`
- Create: `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/04-rag-evaluation-debugging.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/01-rag-retrieval-systems
```

Expected:

- Directory exists.

- [ ] **Step 2: Create `README.md`**

Create `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/README.md` with:

```markdown
# 01 RAG 与检索系统

> **定位**：这个模块解释 RAG 为什么存在，以及如何把外部知识从“搜到一些文本”变成可评估、可追溯、可上线的上下文增强生成系统。

## 默认学习顺序

1. [RAG 解决什么问题：边界与基本链路](./01-rag-problem-boundary.md)
2. [索引、Embedding 与召回](./02-indexing-embedding-retrieval.md)
3. [Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md)
4. [RAG 评估、幻觉与生产排查](./04-rag-evaluation-debugging.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| 文本如何变成向量 | [旧版 Embedding 理论](../03-nlp-embedding-retrieval/02-embedding-theory.md) |
| 检索为什么有稀疏和稠密两类 | [旧版检索理论](../03-nlp-embedding-retrieval/03-retrieval-theory.md) |
| LLM 如何使用上下文生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| 长上下文为什么昂贵 | [长上下文、端侧部署与成本估算](../06-inference-deployment-cost/03-long-context-edge-cost.md) |

## 这个模块的主线

RAG 的核心不是“接一个向量库”，而是解决外部知识如何进入 LLM 输出的问题：

```text
知识源 -> 切分和索引 -> 查询理解 -> 召回和排序 -> 上下文组装 -> 生成 -> 评估和排查
```

学完本模块，你应该能解释 RAG 和长上下文、微调、搜索、Agent 工具调用的边界，并能排查“没检到、检错了、检到了但没用好、回答不忠实”等常见问题。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版 RAG 系统理论深度](../07-theory-practice-bridge/01-rag-deep-dive.md)
- [旧版 Embedding 理论](../03-nlp-embedding-retrieval/02-embedding-theory.md)
- [旧版检索理论](../03-nlp-embedding-retrieval/03-retrieval-theory.md)
```

- [ ] **Step 3: Create `01-rag-problem-boundary.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain why RAG exists: model weights are not a reliable place for changing private knowledge, and prompt-only answering lacks grounding.
- Compare RAG with:
  - long context
  - fine-tuning
  - search
  - tool use
- Establish the minimal RAG pipeline:

```text
User query -> query understanding -> retrieve -> assemble context -> generate -> check grounding/citation
```

- Use a concrete company policy QA example:
  - User asks whether unused annual leave can be cashed out.
  - Retrieved policy snippet says only terminated employees can cash it out.
  - Model must answer with the policy boundary instead of guessing.
- Explain that RAG is a knowledge-grounding pattern, not an Agent loop.
- Link to:
  - `../06-inference-deployment-cost/03-long-context-edge-cost.md`
  - `../05-training-alignment-finetuning/03-lora-qlora-distillation.md`
  - `./02-indexing-embedding-retrieval.md`
- Include self-check questions:
  1. RAG 解决的是模型能力问题还是外部知识接入问题？
  2. 为什么私有知识经常不适合直接微调进权重？
  3. RAG 和长上下文的边界是什么？
  4. 为什么 RAG 不等于 Agent？

- [ ] **Step 4: Create `02-indexing-embedding-retrieval.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain document ingestion, parsing, cleaning, chunking, metadata, embedding, index, query embedding, top-k recall.
- Introduce chunk size and overlap through the problem of semantic completeness vs noise.
- Explain metadata filtering with examples such as department, date, product, permission level.
- Define sparse retrieval, dense retrieval, vector index, approximate nearest neighbor, recall.
- Keep algorithm details practical; mention HNSW/IVF-PQ only as old-reference depth, not required first-pass understanding.
- Include a small example with three policy chunks and a query where chunking affects retrieval.
- Link to:
  - `../03-nlp-embedding-retrieval/02-embedding-theory.md`
  - `../03-nlp-embedding-retrieval/03-retrieval-theory.md`
  - `./03-hybrid-search-rerank-context.md`
- Include self-check questions:
  1. Chunk 太短和太长分别有什么问题？
  2. Metadata filter 解决什么检索问题？
  3. Dense retrieval 和 sparse retrieval 的匹配信号有什么不同？
  4. Recall 高不等于最终回答好，为什么？

- [ ] **Step 5: Create `03-hybrid-search-rerank-context.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain why first-stage retrieval is usually not enough.
- Define:
  - BM25
  - dense retrieval
  - hybrid search
  - RRF
  - reranker/cross-encoder
  - context assembly
  - deduplication
  - compression
  - ordering
- Explain context assembly as a separate design step, not “dump top-k into prompt”.
- Include a concrete example:
  - Query mentions `SOC2 data retention`.
  - BM25 finds exact `SOC2`.
  - Dense finds semantically related `audit log retention`.
  - Reranker promotes the most answerable chunk.
- Explain lost-in-the-middle and why ordering/summary matters.
- Link to:
  - `./02-indexing-embedding-retrieval.md`
  - `../06-inference-deployment-cost/03-long-context-edge-cost.md`
  - `./04-rag-evaluation-debugging.md`
- Include self-check questions:
  1. Hybrid search 为什么比单一 dense retrieval 更稳？
  2. Reranker 和 retriever 的职责区别是什么？
  3. Context assembly 为什么会影响幻觉？
  4. 为什么 top-k 越大不一定越好？

- [ ] **Step 6: Create `04-rag-evaluation-debugging.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain RAG-specific failure modes:
  - no hit
  - wrong hit
  - partial hit
  - stale document
  - unsupported answer
  - citation mismatch
  - context overload
- Define retrieval metrics:
  - recall@k
  - precision@k
  - MRR/NDCG as optional ranking metrics
- Define answer metrics:
  - answer correctness
  - faithfulness/grounding
  - citation accuracy
  - answer relevancy
- Explain golden set, regression set, and production trace.
- Include a concrete debugging trace:

```text
Question -> retrieved chunks -> reranked chunks -> final prompt context -> answer -> judge/human label -> failure type
```

- Connect to:
  - `../07-evaluation-safety-production/01-llm-evaluation-judge.md`
  - `../07-evaluation-safety-production/02-hallucination-safety-guardrails.md`
  - `../07-evaluation-safety-production/03-production-debugging-monitoring.md`
- Include self-check questions:
  1. 如何区分检索失败和生成失败？
  2. Faithfulness 和 answer correctness 有什么区别？
  3. Citation mismatch 可能来自哪些环节？
  4. RAG 线上回归应该记录哪些 trace 字段？

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "默认学习顺序|RAG 解决什么问题|Hybrid Search|RAG 评估|学前检查|回到主线" ai/ml-to-llm-roadmap/01-rag-retrieval-systems
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/01-rag-retrieval-systems
git commit -m "docs: systematize rag retrieval module"
```

---

## Task 2: Build Agent Tool Use Module

**Files:**

- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/README.md`
- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/01-agent-boundary-and-loop.md`
- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/02-tool-use-and-recovery.md`
- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/03-state-memory-and-planning.md`
- Create: `ai/ml-to-llm-roadmap/02-agent-tool-use/04-agent-evaluation-safety-production.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/02-agent-tool-use
```

Expected:

- Directory exists.

- [ ] **Step 2: Create `README.md`**

Create `ai/ml-to-llm-roadmap/02-agent-tool-use/README.md` with:

```markdown
# 02 Agent 与工具调用

> **定位**：这个模块解释什么时候需要 Agent，以及如何把 LLM 的结构化输出、工具执行、状态、记忆、恢复和安全控制组成可上线的多步执行系统。

## 默认学习顺序

1. [Agent 边界与执行循环](./01-agent-boundary-and-loop.md)
2. [工具调用、权限与失败恢复](./02-tool-use-and-recovery.md)
3. [状态、记忆与任务规划](./03-state-memory-and-planning.md)
4. [Agent 评估、安全与生产排查](./04-agent-evaluation-safety-production.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Function Calling 只是输出形态 | [Function Calling 的输出形态](../03-generation-control/03-function-calling-output-shape.md) |
| 结构化输出为什么需要校验 | [结构化输出与约束解码](../03-generation-control/02-structured-output-constrained-decoding.md) |
| RAG 和记忆检索的关系 | [RAG 与检索系统](../01-rag-retrieval-systems/) |
| 生产排查和监控为什么重要 | [生产排查、监控与回归定位](../07-evaluation-safety-production/03-production-debugging-monitoring.md) |

## 这个模块的主线

Agent 不是“模型会自动执行工具”，而是一个受控循环：

```text
目标 -> 状态 -> 选择下一步 -> 生成 tool call -> 应用执行工具 -> 观察结果 -> 更新状态 -> 停止或继续
```

学完本模块，你应该能区分普通 LLM 调用、Function Calling、workflow 和 Agent，并能设计工具权限、失败恢复、状态管理、评估、安全和生产排查。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版 Agent 架构理论](../07-theory-practice-bridge/02-agent-architecture.md)
- [旧版 Compound AI Systems](../07-theory-practice-bridge/05-compound-ai-systems.md)
```

- [ ] **Step 3: Create `01-agent-boundary-and-loop.md`**

Create the page using the System Learning Page Standard. Required content:

- Distinguish:
  - one-shot LLM call
  - structured output
  - Function Calling
  - workflow orchestration
  - Agent loop
- Explain why Agent exists: multi-step tasks need observations, state updates, decisions, and recovery.
- Define the minimal loop:

```text
goal -> state -> decide next action -> tool call -> observation -> update state -> stop or continue
```

- Include a concrete refund-status assistant example.
- Explain that Function Calling produces a call shape; the application executes tools.
- Link to:
  - `../03-generation-control/03-function-calling-output-shape.md`
  - `../08-system-design-project-narrative/01-ai-system-design-method.md`
  - `./02-tool-use-and-recovery.md`
- Include self-check questions:
  1. Agent 和 Function Calling 的边界是什么？
  2. Agent 和 workflow 的区别是什么？
  3. 为什么 Agent 需要状态？
  4. 什么场景不该用 Agent？

- [ ] **Step 4: Create `02-tool-use-and-recovery.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain tool schema, permissions, argument validation, tool result validation, timeouts, retries, fallback, idempotency, and human escalation.
- Explain least privilege for tools.
- Explain tool result as untrusted input, especially for prompt injection.
- Include concrete example:
  - `get_refund_status(order_id)`
  - `create_refund_ticket(order_id, reason)`
  - show a safe path and a failure path.
- Explain retry categories:
  - parse/schema failure
  - transient tool failure
  - permission failure
  - unsafe action
- Link to:
  - `../03-generation-control/02-structured-output-constrained-decoding.md`
  - `../07-evaluation-safety-production/02-hallucination-safety-guardrails.md`
  - `./03-state-memory-and-planning.md`
- Include self-check questions:
  1. Tool schema 为什么不能替代权限控制？
  2. 参数校验和结果校验分别防什么？
  3. 哪些失败适合重试，哪些应该停止或转人工？
  4. 为什么工具结果也可能触发 prompt injection？

- [ ] **Step 5: Create `03-state-memory-and-planning.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain working state, conversation history, scratchpad/trajectory, summarized memory, retrieved memory, and task state.
- Explain planning patterns:
  - direct next-action
  - plan-and-execute
  - task decomposition
  - multi-agent as optional decomposition
- Explain memory often reuses RAG-like retrieval, but Agent is not RAG.
- Include concrete example:
  - travel planning or support escalation where state tracks user constraints, completed steps, pending tool calls, and stopping condition.
- Mention Tree-of-Thought, Graph-of-Thought, and MCTS only as advanced references, not required first-pass material.
- Link to:
  - `../01-rag-retrieval-systems/01-rag-problem-boundary.md`
  - `../06-inference-deployment-cost/01-prefill-decode-kv-cache.md`
  - `./04-agent-evaluation-safety-production.md`
- Include self-check questions:
  1. Working state 和长期记忆有什么区别？
  2. 为什么不能把所有历史都塞进上下文？
  3. Plan-and-execute 解决什么问题？
  4. Multi-agent 什么时候是必要拆分，什么时候是过度设计？

- [ ] **Step 6: Create `04-agent-evaluation-safety-production.md`**

Create the page using the System Learning Page Standard. Required content:

- Explain Agent-specific eval dimensions:
  - task success
  - trajectory quality
  - tool call validity
  - tool success rate
  - permission safety
  - cost/latency
  - loop termination
  - human escalation correctness
- Explain safety controls:
  - tool allowlist
  - permission boundary
  - policy checks
  - loop limits
  - audit logs
  - sandboxing dangerous actions
- Explain production failures:
  - infinite loop
  - tool hallucination
  - stale observation
  - unsafe action
  - hidden state drift
  - prompt injection through tool output
- Include a concrete trace example:

```text
goal -> step 1 tool call -> observation -> step 2 tool call -> failure -> fallback/escalation -> final answer
```

- Link to:
  - `../07-evaluation-safety-production/03-production-debugging-monitoring.md`
  - `../08-system-design-project-narrative/02-llm-platform-routing-cost.md`
  - `../07-evaluation-safety-production/02-hallucination-safety-guardrails.md`
- Include self-check questions:
  1. Agent eval 为什么不能只看最终答案？
  2. 怎么发现 tool hallucination？
  3. Loop limit 防什么，可能带来什么副作用？
  4. Agent 生产日志需要记录哪些字段？

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "默认学习顺序|Agent 边界|工具调用|状态、记忆|Agent 评估|学前检查|回到主线" ai/ml-to-llm-roadmap/02-agent-tool-use
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/02-agent-tool-use
git commit -m "docs: systematize agent tool use module"
```

---

## Task 3: Add RAG And Agent Interview Paths

**Files:**

- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md`

- [ ] **Step 1: Create RAG interview path**

Create `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md` using the Interview Path Standard.

Must link:

- `../01-rag-retrieval-systems/01-rag-problem-boundary.md`
- `../01-rag-retrieval-systems/02-indexing-embedding-retrieval.md`
- `../01-rag-retrieval-systems/03-hybrid-search-rerank-context.md`
- `../01-rag-retrieval-systems/04-rag-evaluation-debugging.md`
- `../09-review-notes/01-rag-retrieval-systems-cheatsheet.md`

Must-answer questions:

1. RAG 解决什么问题，和长上下文、微调、搜索有什么边界？
2. Chunk size 和 overlap 怎么选？
3. Dense、BM25、Hybrid Search、Rerank 分别解决什么问题？
4. Context assembly 如何影响最终回答？
5. 如何评估和排查 RAG 失败？
6. 如何降低幻觉和 citation mismatch？
7. 什么时候不该用 RAG？

Rules:

- Make clear this is not the first-time learning entrance.
- Do not require Agent pages for RAG interview prep.

- [ ] **Step 2: Create Agent interview path**

Create `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md` using the Interview Path Standard.

Must link:

- `../02-agent-tool-use/01-agent-boundary-and-loop.md`
- `../02-agent-tool-use/02-tool-use-and-recovery.md`
- `../02-agent-tool-use/03-state-memory-and-planning.md`
- `../02-agent-tool-use/04-agent-evaluation-safety-production.md`
- `../09-review-notes/02-agent-tool-use-cheatsheet.md`

Must-answer questions:

1. Agent 和普通 LLM 调用、Function Calling、workflow 的区别？
2. ReAct 或 observe-act loop 的核心是什么？
3. Tool schema、权限、参数校验和错误恢复怎么设计？
4. State、memory、planning 分别解决什么问题？
5. Agent 系统怎么评估、限流、审计和防止失控？
6. 什么时候不该用 Agent？
7. Agent 失败时怎么定位是模型、工具、状态还是权限问题？

Rules:

- Link to generation control or RAG only as prerequisites or boundaries, not as default interview steps.
- Do not make this a framework comparison page.

- [ ] **Step 3: Verify and commit**

Run:

```bash
rg -n "90 分钟冲刺|半天复盘|必答问题|复习笔记|ai-engineer-rag|ai-engineer-agent" ai/ml-to-llm-roadmap/interview-paths
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md
git commit -m "docs: add rag agent interview paths"
```

---

## Task 4: Add RAG And Agent Review Notes

**Files:**

- Create: `ai/ml-to-llm-roadmap/09-review-notes/01-rag-retrieval-systems-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md`
- Modify: `ai/ml-to-llm-roadmap/09-review-notes/README.md`

- [ ] **Step 1: Create RAG review note**

Create `ai/ml-to-llm-roadmap/09-review-notes/01-rag-retrieval-systems-cheatsheet.md` using the Review Note Standard.

Include 30-second answer coverage for:

- RAG problem and boundary
- chunking, metadata, embedding, retrieval
- dense vs sparse vs hybrid search
- rerank and context assembly
- RAG evaluation and debugging
- hallucination, grounding, and citation mismatch

High-frequency follow-ups must include at least:

1. RAG、长上下文、微调怎么取舍？
2. Chunk size 怎么选？
3. 为什么需要 hybrid search 和 rerank？
4. 如何区分 retrieval failure 和 generation failure？
5. Faithfulness 和 correctness 有什么区别？

Reverse links must include all four RAG system pages.

- [ ] **Step 2: Create Agent review note**

Create `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md` using the Review Note Standard.

Include 30-second answer coverage for:

- Agent boundary
- observe-act loop
- tool schema and permissions
- validation and recovery
- state, memory, planning
- Agent evaluation, safety, and production debugging

High-frequency follow-ups must include at least:

1. Agent 和 Function Calling 的区别？
2. Tool schema 为什么不能替代权限控制？
3. Agent 为什么需要状态？
4. Agent eval 为什么不能只看最终答案？
5. 什么时候不该用 Agent？

Reverse links must include all four Agent system pages plus generation-control Function Calling page.

- [ ] **Step 3: Update review notes README**

Modify `ai/ml-to-llm-roadmap/09-review-notes/README.md` so the table includes:

```markdown
| [RAG 与检索系统速记](./01-rag-retrieval-systems-cheatsheet.md) | [RAG 与检索系统](../01-rag-retrieval-systems/) |
| [Agent 与工具调用速记](./02-agent-tool-use-cheatsheet.md) | [Agent 与工具调用](../02-agent-tool-use/) |
```

Place these rows before Transformer so the numbering matches the mainline modules.

- [ ] **Step 4: Verify and commit**

Run:

```bash
rg -n "30 秒答案|2 分钟展开|高频追问|易混点|项目连接|反向链接|RAG 与检索系统速记|Agent 与工具调用速记" ai/ml-to-llm-roadmap/09-review-notes
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/09-review-notes
git commit -m "docs: add rag agent review notes"
```

---

## Task 5: Update Roadmap And Legacy Navigation

**Files:**

- Modify: `ai/ml-to-llm-roadmap.md`
- Modify: `ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md`
- Modify: `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md`

- [ ] **Step 1: Update root roadmap migration table**

Modify `ai/ml-to-llm-roadmap.md`.

In `## 迁移成果`, update:

```markdown
| RAG 与检索系统 | 外部知识接入、检索、上下文组装、评估排查 | [01-rag-retrieval-systems](./ml-to-llm-roadmap/01-rag-retrieval-systems/) | 已系统化 |
| Agent 与工具调用 | 工具调用循环、状态记忆、失败恢复、安全评估 | [02-agent-tool-use](./ml-to-llm-roadmap/02-agent-tool-use/) | 已系统化 |
```

Update the paragraph above the target structure so it no longer says RAG and Agent are deferred. It should say all current mainline modules have a system-learning entry, while old directories remain as references.

Update `面试复习笔记` status from `部分完成` to `已系统化` if the table now covers all modules with review notes.

- [ ] **Step 2: Update interview sprint path**

In `## 面试冲刺路径`, keep Transformer first if the existing order says so, but add RAG and Agent as first-class paths immediately after Transformer review notes and before generation control:

```markdown
4. RAG 面试路径：[interview-paths/ai-engineer-rag.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md)
5. Agent 面试路径：[interview-paths/ai-engineer-agent.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md)
```

Renumber following items.

Remove wording that says old RAG/Agent materials are the only available path. Keep old materials only in optional reference.

- [ ] **Step 3: Update system learning path**

Update `## 系统学习路径` so it says:

```markdown
1. 从 [Transformer 必要基础](./ml-to-llm-roadmap/04-transformer-foundations/) 开始。
2. 缺 Deep Learning 前置知识时进入 [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/)。
3. 如果目标是应用系统，按需进入：RAG、Agent、生成控制、推理部署、评估安全、系统设计。
4. 如果目标是模型理解，按需进入：训练对齐、推理部署、评估安全。
5. 每个模块学完后，用对应 `09-review-notes/` 做面试复盘。
```

- [ ] **Step 4: Update `07-theory-practice-bridge/README.md`**

Keep it reference-only, but update wording:

- It should say RAG now defaults to `../01-rag-retrieval-systems/`.
- It should say Agent now defaults to `../02-agent-tool-use/`.
- The table rows for `01-rag-deep-dive.md` and `02-agent-architecture.md` should say old reference and point to the new default modules.
- Remove wording that says RAG/Agent will be systematized later.

- [ ] **Step 5: Update `03-nlp-embedding-retrieval/README.md`**

Update the `新版路线说明` so it says:

- RAG default learning has moved to `../01-rag-retrieval-systems/`.
- NLP/Embedding/Retrieval theory remains as background reference.
- Generation control remains in `../03-generation-control/`.

Update any table row descriptions that still imply this old directory is the default RAG route.

- [ ] **Step 6: Verify and commit**

Run:

```bash
rg -n "01-rag-retrieval-systems|02-agent-tool-use|RAG 与检索系统|Agent 与工具调用|已系统化|待迁移|旧版参考" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md
git diff --check
```

Expected:

- `01-rag-retrieval-systems` appears in root roadmap and old-reference README files.
- `02-agent-tool-use` appears in root roadmap and old-reference README files.
- `待迁移` should not describe RAG or Agent in root roadmap.

Commit:

```bash
git add ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md
git commit -m "docs: update roadmap for rag agent modules"
```

---

## Task 6: Final Validation

**Files:**

- Validate all files changed in this branch.

- [ ] **Step 1: Run whitespace check**

Run:

```bash
git diff --check main..HEAD
```

Expected:

- No output.

- [ ] **Step 2: Run local Markdown link checker**

Run from repo root:

```bash
python3 - <<'PY'
from pathlib import Path
import re

roots = [
    Path('ai/ml-to-llm-roadmap.md'),
    Path('ai/ml-to-llm-roadmap/01-rag-retrieval-systems'),
    Path('ai/ml-to-llm-roadmap/02-agent-tool-use'),
    Path('ai/ml-to-llm-roadmap/interview-paths'),
    Path('ai/ml-to-llm-roadmap/09-review-notes'),
    Path('ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md'),
    Path('ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md'),
]

files = []
for root in roots:
    if root.is_file():
        files.append(root)
    elif root.exists():
        files.extend(sorted(root.glob('*.md')))

link_re = re.compile(r'(?<!!)(?:\[[^\]]*\]|\[\[[^\]]*\]\])\(([^)]+)\)')
errors = []
for file in files:
    in_code = False
    for line_no, line in enumerate(file.read_text().splitlines(), 1):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        for raw in link_re.findall(line):
            target = raw.split()[0].strip('<>')
            if not target or target.startswith(('#', 'http://', 'https://', 'mailto:')):
                continue
            path_part = target.split('#', 1)[0]
            if not path_part:
                continue
            dest = (file.parent / path_part).resolve()
            if not dest.exists():
                errors.append(f'{file}:{line_no}: missing link target {raw}')
if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print(f'checked {len(files)} files: all local markdown links resolve')
PY
```

Expected:

- Link checker prints `all local markdown links resolve`.

- [ ] **Step 3: Run structure checks**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

system_dirs = [
    Path('ai/ml-to-llm-roadmap/01-rag-retrieval-systems'),
    Path('ai/ml-to-llm-roadmap/02-agent-tool-use'),
]
system_required = [
    '## 这篇解决什么问题',
    '## 学前检查',
    '## 概念为什么出现',
    '## 最小心智模型',
    '## 最小例子',
    '## 原理层',
    '## 和应用/面试的连接',
    '## 常见误区',
    '## 自测',
    '## 回到主线',
]
errors = []
for directory in system_dirs:
    for file in sorted(directory.glob('*.md')):
        if file.name == 'README.md':
            continue
        text = file.read_text()
        for heading in system_required:
            if heading not in text:
                errors.append(f'{file}: missing {heading}')

interview_required = [
    '## 适用场景',
    '## 90 分钟冲刺',
    '## 半天复盘',
    '## 必答问题',
    '## 可跳过内容',
    '## 复习笔记',
]
for file in [
    Path('ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md'),
    Path('ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md'),
]:
    text = file.read_text()
    for heading in interview_required:
        if heading not in text:
            errors.append(f'{file}: missing {heading}')

review_required = [
    '## 30 秒答案',
    '## 2 分钟展开',
    '## 高频追问',
    '## 易混点',
    '## 项目连接',
    '## 反向链接',
]
for file in [
    Path('ai/ml-to-llm-roadmap/09-review-notes/01-rag-retrieval-systems-cheatsheet.md'),
    Path('ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md'),
]:
    text = file.read_text()
    for heading in review_required:
        if heading not in text:
            errors.append(f'{file}: missing {heading}')

if errors:
    print('\n'.join(errors))
    raise SystemExit(1)
print('new RAG/Agent system pages, interview paths, and review notes have required headings')
PY
```

Expected:

- Structure checker prints required heading success.

- [ ] **Step 4: Verify navigation status terms**

Run:

```bash
rg -n "01-rag-retrieval-systems|02-agent-tool-use|RAG 与检索系统|Agent 与工具调用|已系统化|待迁移|面试路径|30 秒答案" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/01-rag-retrieval-systems ai/ml-to-llm-roadmap/02-agent-tool-use ai/ml-to-llm-roadmap/interview-paths ai/ml-to-llm-roadmap/09-review-notes ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md
```

Expected:

- New module links and `已系统化` are present.
- `待迁移` does not describe RAG or Agent in the root roadmap.

- [ ] **Step 5: Final read-through**

Check:

- RAG pages explain knowledge retrieval and grounding, not Agent loops.
- Agent pages explain action loops, tools, state, recovery, and safety, not a specific framework.
- Interview paths link system pages before review notes.
- Review notes compress only concepts covered in system pages.
- Old reference README files clearly direct default learners to the new modules.
