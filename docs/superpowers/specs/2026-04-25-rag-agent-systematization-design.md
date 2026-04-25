# RAG And Agent Systematization Design

## Context

The ML to LLM roadmap has been reshaped around three layers:

1. System-learning modules for first-time understanding.
2. Interview paths for targeted preparation.
3. Review notes for fast recall.

The remaining deferred areas are RAG and Agent. Both currently exist only as older reference material under `ai/ml-to-llm-roadmap/07-theory-practice-bridge/`, and the root roadmap marks them as `待迁移`. The user has approved systematizing both in one batch, while preserving the old files as reference sources.

## Goals

- Turn RAG and Agent from old reference topics into default system-learning modules.
- Keep the learner experience smooth for someone who has used RAG/Agent partially but lacks a systematic mental model.
- Match the style of the existing new modules: problem-first, concrete examples, principle layer, common pitfalls, self-check, and return-to-mainline navigation.
- Add interview routes and review notes after the system-learning layer, not as substitutes for it.
- Update navigation so RAG and Agent are no longer marked as deferred.

## Non-Goals

- Do not delete the old RAG or Agent reference files.
- Do not turn the first-time learning pages into cheatsheets.
- Do not make the RAG module depend on Agent.
- Do not make the Agent module a framework tutorial for LangGraph, CrewAI, AutoGen, or any vendor SDK.
- Do not add current library/API usage instructions; this is conceptual documentation, not live SDK documentation.

## Recommended Approach

Use the same three-layer pattern as the completed modules:

1. Create a new `01-rag-retrieval-systems/` mainline module.
2. Create a new `02-agent-tool-use/` mainline module.
3. Add one interview path for each module.
4. Add one review-note cheatsheet for each module.
5. Update root and old-reference navigation.

This keeps the roadmap coherent and avoids the earlier problem where learners saw dense theory or interview notes before they had enough mental model.

## RAG Module Design

Create `ai/ml-to-llm-roadmap/01-rag-retrieval-systems/`.

Default learning order:

1. `01-rag-problem-boundary.md`
2. `02-indexing-embedding-retrieval.md`
3. `03-hybrid-search-rerank-context.md`
4. `04-rag-evaluation-debugging.md`

The module should answer one main question: when a model lacks or should not memorize knowledge, how do we retrieve the right external context and make the final answer grounded, useful, and debuggable?

Page responsibilities:

- `01-rag-problem-boundary.md`
  - Explain why RAG exists.
  - Compare RAG with long context, fine-tuning, search, and tool use.
  - Establish the minimal pipeline: user query, retrieval, context assembly, generation, citation or grounding check.
  - Use a concrete example such as company policy QA.

- `02-indexing-embedding-retrieval.md`
  - Explain documents, chunking, metadata, embedding, vector index, sparse retrieval, and recall.
  - Introduce chunk size and overlap through the problem they solve.
  - Link to existing NLP/embedding old references as deeper background, not required first reading.

- `03-hybrid-search-rerank-context.md`
  - Explain why first-stage retrieval is not enough.
  - Introduce BM25 plus dense retrieval, hybrid search, RRF, reranking, context ordering, deduplication, compression, and prompt assembly.
  - Keep focus on retrieval quality and context quality, not Agent planning.

- `04-rag-evaluation-debugging.md`
  - Explain RAG-specific failure modes: no hit, wrong hit, partial hit, stale doc, answer unsupported by retrieved context, citation mismatch, and context overload.
  - Connect to existing evaluation/safety module.
  - Introduce retrieval metrics, answer metrics, grounding/faithfulness checks, golden sets, regression sets, and production debugging.

## Agent Module Design

Create `ai/ml-to-llm-roadmap/02-agent-tool-use/`.

Default learning order:

1. `01-agent-boundary-and-loop.md`
2. `02-tool-use-and-recovery.md`
3. `03-state-memory-and-planning.md`
4. `04-agent-evaluation-safety-production.md`

The module should answer one main question: when a task requires multiple steps, external actions, observations, and recovery from failures, how do we design an LLM-controlled loop without pretending the model magically executes tools?

Page responsibilities:

- `01-agent-boundary-and-loop.md`
  - Distinguish normal LLM calls, structured output, function calling, workflow orchestration, and Agent loops.
  - Explain the minimal loop: goal, state, plan or next action, tool call, observation, stop condition.
  - Link back to generation control for Function Calling boundaries.

- `02-tool-use-and-recovery.md`
  - Explain tool schema, permissions, argument validation, tool result validation, timeout, retries, fallback, idempotency, and human escalation.
  - Keep framework names as optional references only.
  - Use a concrete example like refund-status lookup or calendar scheduling.

- `03-state-memory-and-planning.md`
  - Explain working state, conversation history, summarized memory, retrieved memory, task decomposition, plan-and-execute, and when multi-agent decomposition is useful.
  - Make clear that memory often reuses RAG-like retrieval, but Agent is not identical to RAG.
  - Avoid turning Tree-of-Thought, Graph-of-Thought, or MCTS into required first-pass material.

- `04-agent-evaluation-safety-production.md`
  - Explain Agent-specific evaluation and safety: task success, trajectory quality, tool success, permission violations, cost/latency blowups, loop limits, and audit logs.
  - Connect to production debugging and system design modules.
  - Explain common failures: infinite loops, tool hallucination, stale observations, prompt injection through tool results, unsafe actions, and hidden state drift.

## Interview Paths

Create:

- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-rag.md`
- `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-agent.md`

Each path must follow the existing interview path standard:

```markdown
# AI Engineer 面试路径：<模块名>

## 适用场景
## 90 分钟冲刺
## 半天复盘
## 必答问题
## 可跳过内容
## 复习笔记
```

RAG must-answer themes:

- RAG 解决什么问题，和长上下文、微调、搜索有什么边界？
- Chunk size 和 overlap 怎么选？
- Dense、BM25、Hybrid Search、Rerank 分别解决什么问题？
- Context assembly 如何影响最终回答？
- 如何评估和排查 RAG 失败？
- 如何降低幻觉和 citation mismatch？

Agent must-answer themes:

- Agent 和普通 LLM 调用、Function Calling、workflow 的区别？
- ReAct 或 observe-act loop 的核心是什么？
- Tool schema、权限、参数校验和错误恢复怎么设计？
- State、memory、planning 分别解决什么问题？
- Agent 系统怎么评估、限流、审计和防止失控？
- 什么时候不该用 Agent？

## Review Notes

Create:

- `ai/ml-to-llm-roadmap/09-review-notes/01-rag-retrieval-systems-cheatsheet.md`
- `ai/ml-to-llm-roadmap/09-review-notes/02-agent-tool-use-cheatsheet.md`

Update:

- `ai/ml-to-llm-roadmap/09-review-notes/README.md`

Each cheatsheet must follow the existing review note standard:

```markdown
# <模块名> 面试速记

## 30 秒答案
## 2 分钟展开
## 高频追问
## 易混点
## 项目连接
## 反向链接
```

The review notes must summarize system-learning content only. If an idea is not introduced in the RAG/Agent system pages, it should not become a new core concept in the cheatsheet.

## Navigation Updates

Update `ai/ml-to-llm-roadmap.md`:

- Mark RAG 与检索系统 as `已系统化`, linking to `01-rag-retrieval-systems/`.
- Mark Agent 与工具调用 as `已系统化`, linking to `02-agent-tool-use/`.
- Update the target structure explanation to say all mainline modules are now systematized.
- Add RAG and Agent interview paths to the interview sprint path before generation control.
- Update system learning path to include RAG and Agent as first-class target modules.

Update old references:

- `ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md`
  - Keep it reference-only.
  - Point RAG and Agent readers to the new modules.

- `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md`
  - Keep NLP/embedding/retrieval material as background.
  - Point default RAG learning to `01-rag-retrieval-systems/`.

Do not rewrite the old deep-dive RAG and Agent files unless navigation wording inside them is clearly misleading.

## Verification Strategy

Run checks equivalent to the previous batch:

- `git diff --check`
- Local Markdown link checker over:
  - `ai/ml-to-llm-roadmap.md`
  - `01-rag-retrieval-systems/`
  - `02-agent-tool-use/`
  - `interview-paths/`
  - `09-review-notes/`
  - updated old README files
- Structure check:
  - Each new system page has the standard learning headings.
  - Each new interview path has the interview path headings.
  - Each new review note has the review note headings.
- Targeted `rg` checks:
  - RAG and Agent no longer show as `待迁移`.
  - New module links appear in root roadmap.
  - Old reference directories point to new modules.

## Risks And Mitigations

- Risk: RAG pages become a vector database tutorial.
  - Mitigation: Keep pages centered on retrieval quality, context quality, and grounded answering.

- Risk: Agent pages become a framework tutorial.
  - Mitigation: Explain loop, state, tools, permissions, recovery, and evaluation without depending on a specific framework.

- Risk: RAG and Agent concepts blur together.
  - Mitigation: RAG explains knowledge retrieval; Agent explains action loops. Cross-link only where one genuinely depends on the other.

- Risk: Interview notes reintroduce jumpiness.
  - Mitigation: Review notes must only compress concepts already covered in system pages.

## Approval Status

The user approved the recommended approach: RAG and Agent are systematized together, using the same three-layer pattern as prior modules.
