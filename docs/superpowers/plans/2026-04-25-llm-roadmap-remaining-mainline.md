# Remaining LLM Roadmap Mainline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Systematize the five remaining non-RAG, non-Agent roadmap modules so learners can continue smoothly after Transformer and Deep Learning foundations, then add interview paths and review notes for those modules.

**Architecture:** Add new default mainline directories for generation control, training/alignment/fine-tuning, inference/deployment/cost, evaluation/safety/production, and system design/project narrative. Preserve the existing `03`, `05`, `06`, `07`, and `08` legacy directories as reference sources; do not delete or rewrite them wholesale. Update the root roadmap so the new directories become the default route while RAG and Agent stay explicitly deferred.

**Tech Stack:** Markdown documentation, existing `ai/ml-to-llm-roadmap` layout, shell verification with `rg`, `git diff --check`, and a local Markdown link checker.

---

## Scope

Included now:

1. `03 生成控制与结构化输出`
2. `05 训练、对齐与微调`
3. `06 推理优化、部署与成本`
4. `07 评估、安全与生产排查`
5. `08 系统设计与项目叙事`

Deferred:

1. `01 RAG 与检索系统`
2. `02 Agent 与工具调用`

The deferred modules may still appear as old-reference links when unavoidable, but they must not become default reading steps in this batch.

## File Structure

Create these new system-learning directories:

- Create: `ai/ml-to-llm-roadmap/03-generation-control/`
  - Responsibility: Explain decoding parameters, constrained decoding, structured output, and function/tool-call shaped output as a generation-control module, not as Agent architecture.

- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/`
  - Responsibility: Explain how base models are created and adapted: pretraining, SFT, preference alignment, LoRA/QLoRA, distillation, and model-history context.

- Create: `ai/ml-to-llm-roadmap/06-inference-deployment-cost/`
  - Responsibility: Explain prefill/decode, KV cache, batching, vLLM/PagedAttention, quantization, long context, edge deployment, and cost reasoning.

- Create: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/`
  - Responsibility: Explain evals, LLM-as-Judge, hallucination, safety, guardrails, monitoring, and production debugging.

- Create: `ai/ml-to-llm-roadmap/08-system-design-project-narrative/`
  - Responsibility: Explain AI Engineer system design and project narrative without making RAG/Agent the default examples.

Create these interview-path files:

- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-generation-control.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-training-alignment.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-inference-deployment.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-evaluation-safety.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-system-design.md`

Create these review notes:

- Create: `ai/ml-to-llm-roadmap/09-review-notes/04-generation-control-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/05-training-alignment-finetuning-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/06-inference-deployment-cost-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/07-evaluation-safety-production-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/08-system-design-project-narrative-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/README.md` if it does not already exist.

Modify navigation:

- Modify: `ai/ml-to-llm-roadmap.md`
  - Responsibility: Mark these five modules as systematized, keep RAG/Agent deferred, and point interview sprint users to the new paths and notes.

- Modify: `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md`
  - Responsibility: Mark this old directory as legacy/reference for NLP, retrieval, and old generation-control material.

- Modify: `ai/ml-to-llm-roadmap/05-pretrained-models/README.md`
  - Responsibility: Mark this old directory as legacy/reference for model-history material now summarized in the new training module.

- Modify: `ai/ml-to-llm-roadmap/06-llm-core/README.md`
  - Responsibility: Mark this old dense directory as legacy/reference and point learners to the new split modules.

- Modify: `ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md`
  - Responsibility: Keep RAG/Agent entries as old references; route prompt/fine-tuning/debugging material into the new default modules.

- Modify: `ai/ml-to-llm-roadmap/08-interview-synthesis/README.md`
  - Responsibility: Mark old interview synthesis as reference and route default interview prep to `interview-paths/` and `09-review-notes/`.

## System Learning Page Standard

Each new system-learning page must use this heading order:

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

- Do not turn system-learning pages into interview cheatsheets.
- Every new concept must be introduced through the problem it solves.
- Every page must have a small concrete example.
- Every page must link back to related Transformer or Deep Learning foundation content when relevant.
- Old files may be linked as `深入参考`, but not required before first-time understanding.

## Interview Path Standard

Each interview path must include:

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

- Do not repeat long explanations.
- Link to the new system-learning pages first.
- Link to the corresponding review note last.
- Include 5 to 8 must-answer questions.

## Review Note Standard

Each review note must include:

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

- Every 30-second answer must be concise enough to say aloud.
- Every note must include at least 4 high-frequency follow-ups.
- Every note must link back to the system-learning pages that explain the concepts.
- Review notes must not introduce core concepts that do not appear in the system-learning pages.

## Task 1: Build Generation Control System Module

**Files:**
- Create: `ai/ml-to-llm-roadmap/03-generation-control/README.md`
- Create: `ai/ml-to-llm-roadmap/03-generation-control/01-decoding-parameters.md`
- Create: `ai/ml-to-llm-roadmap/03-generation-control/02-structured-output-constrained-decoding.md`
- Create: `ai/ml-to-llm-roadmap/03-generation-control/03-function-calling-output-shape.md`
- Modify: `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/03-generation-control
```

Expected:
- Directory exists.

- [ ] **Step 2: Create `README.md`**

Create `ai/ml-to-llm-roadmap/03-generation-control/README.md` with:

```markdown
# 03 生成控制与结构化输出

> **定位**：这个模块解释 LLM 为什么不是“直接吐答案”，而是在每一步从 token 分布中选择下一个 token；也解释 JSON、Schema、Function Calling 这类结构化输出为什么需要额外控制。

## 默认学习顺序

1. [解码参数：Temperature、Top-k、Top-p](./01-decoding-parameters.md)
2. [结构化输出与约束解码](./02-structured-output-constrained-decoding.md)
3. [Function Calling 的输出形态](./03-function-calling-output-shape.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 为什么逐 token 生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| KV Cache 为什么影响生成成本 | [KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md) |
| Softmax 后得到概率分布是什么意思 | [Attention 中的 softmax 直觉](../04-transformer-foundations/04-self-attention-qkv.md) |

## 这个模块要解决的主线问题

LLM 应用里很多问题不是“模型会不会”，而是“如何让模型稳定地按你需要的形式输出”。你需要同时理解三层控制：

```text
Prompt 约束: 告诉模型想要什么
解码约束: 改变 token 选择过程
输出协议: 把自由文本变成系统可消费的结构
```

## 深入参考

旧版材料仍可作为扩展阅读：

- [语言模型与解码](../03-nlp-embedding-retrieval/04-language-model-decoding.md)
- [受控生成与结构化输出](../03-nlp-embedding-retrieval/05-controlled-generation.md)
```

- [ ] **Step 3: Create `01-decoding-parameters.md`**

Create the page using the system learning standard. Required content:

- Explain why generation starts from a probability distribution over next tokens.
- Define greedy, temperature, top-k, top-p, repetition penalty.
- Include a small example with next-token candidates like `Paris`, `London`, `Berlin`.
- Explain that temperature changes distribution sharpness, top-k/top-p truncate candidate sets, and greedy is deterministic.
- Link to `../04-transformer-foundations/08-decoder-only-generation.md`.
- Include self-check questions:
  1. Temperature changes what part of decoding?
  2. Top-k and Top-p both remove candidates, but their cutoff rules differ how?
  3. Why can low temperature improve stability but reduce diversity?
  4. Why is greedy decoding often bad for open-ended generation?

- [ ] **Step 4: Create `02-structured-output-constrained-decoding.md`**

Create the page using the system learning standard. Required content:

- Explain why prompt-only JSON instructions fail in production.
- Define JSON mode, schema-constrained decoding, grammar-constrained decoding, and validation-retry.
- Include a small JSON example for:

```json
{"answer": "yes", "confidence": 0.82}
```

- Explain constrained decoding as masking invalid next tokens.
- Explain validation-retry as a fallback, not a guarantee.
- Link to `./01-decoding-parameters.md`.
- Include self-check questions:
  1. Prompt 约束和 constrained decoding 的根本区别是什么？
  2. Schema 约束为什么能减少格式错误？
  3. 为什么 validation-retry 不能替代真正的约束解码？
  4. 结构化输出为什么会影响延迟和失败处理？

- [ ] **Step 5: Create `03-function-calling-output-shape.md`**

Create the page using the system learning standard. Required content:

- Explain Function Calling as model outputting a structured call shape, not magically executing tools.
- Keep Agent planning/tool-loop architecture out of scope and explicitly defer it to the future Agent module.
- Explain arguments, schema, tool choice, parallel call shape, and final natural-language answer.
- Include a minimal example:

```json
{
  "name": "get_weather",
  "arguments": {"city": "Shanghai"}
}
```

- Explain failure modes: wrong tool, missing argument, invalid enum, hallucinated tool name.
- Link to `./02-structured-output-constrained-decoding.md`.
- Include self-check questions:
  1. Function Calling 和 Agent 有什么边界？
  2. 模型输出 tool call 后，谁负责真正执行工具？
  3. Schema 为什么不能保证语义正确？
  4. 并行 tool call 的输出形态需要额外处理什么？

- [ ] **Step 6: Mark old NLP/Generation directory as reference**

Modify the top of `ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md` to add:

```markdown
> **新版路线说明**：这个目录仍保留 NLP、Embedding、检索和旧版生成控制材料。默认学习路径中，生成控制已经迁入 [03-generation-control](../03-generation-control/)；RAG 与检索系统会在后续单独系统化。
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "03 生成控制|Temperature|Top-k|Top-p|约束解码|Function Calling|Agent 有什么边界|新版路线说明" ai/ml-to-llm-roadmap/03-generation-control ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md
git diff --check
```

Expected:
- `rg` returns matches in new files and the old README.
- `git diff --check` prints no output.

Commit:

```bash
git add ai/ml-to-llm-roadmap/03-generation-control ai/ml-to-llm-roadmap/03-nlp-embedding-retrieval/README.md
git commit -m "docs: systematize generation control module"
```

## Task 2: Build Training, Alignment, And Fine-Tuning Module

**Files:**
- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/README.md`
- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/01-pretraining-sft-overview.md`
- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/02-preference-alignment-rlhf-dpo.md`
- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/03-lora-qlora-distillation.md`
- Create: `ai/ml-to-llm-roadmap/05-training-alignment-finetuning/04-model-evolution-bert-gpt-t5.md`
- Modify: `ai/ml-to-llm-roadmap/05-pretrained-models/README.md`
- Modify: `ai/ml-to-llm-roadmap/06-llm-core/README.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/05-training-alignment-finetuning
```

- [ ] **Step 2: Create `README.md`**

Create `README.md` with:

```markdown
# 05 训练、对齐与微调

> **定位**：这个模块解释一个 LLM 从 base model 到 chat model，再到你的业务适配模型，中间经历了什么。它不要求你会训练大模型，但要让你能在面试和工程决策中说清训练阶段、对齐方法和微调边界。

## 默认学习顺序

1. [预训练与 SFT：从 base model 到 instruction model](./01-pretraining-sft-overview.md)
2. [偏好对齐：RLHF、DPO 与 KL 约束](./02-preference-alignment-rlhf-dpo.md)
3. [LoRA、QLoRA、蒸馏与模型合并](./03-lora-qlora-distillation.md)
4. [模型演进：BERT、GPT、T5 给今天留下了什么](./04-model-evolution-bert-gpt-t5.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 为什么适合生成 | [架构变体](../04-transformer-foundations/07-transformer-architecture-variants.md) |
| CLM/MLM 的差异 | [架构变体的训练目标](../04-transformer-foundations/07-transformer-architecture-variants.md) |
| loss 和反向传播 | [反向传播与梯度问题](../foundations/deep-learning/02-backprop-gradient-problems.md) |

## 这个模块的主线

```text
预训练: 学语言和世界知识
SFT: 学会按指令回答
偏好对齐: 学会更符合人类偏好
微调/蒸馏: 适配任务、压缩模型或迁移能力
```

## 深入参考

- [旧版 LLM 训练三阶段](../06-llm-core/01-training-pipeline.md)
- [旧版对齐技术](../06-llm-core/02-alignment.md)
- [旧版微调与蒸馏](../06-llm-core/06-fine-tuning-distillation.md)
- [旧版预训练模型历史](../05-pretrained-models/)
```

- [ ] **Step 3: Create `01-pretraining-sft-overview.md`**

Required content:

- Use the system learning standard.
- Explain why pretraining comes before SFT.
- Define token prediction, data mix, base model, instruction data, chat template, and SFT.
- Include a minimal example of turning raw text learning into instruction-response learning.
- Explain why SFT improves instruction following but does not fully solve preference/safety.
- Link to `../04-transformer-foundations/08-decoder-only-generation.md`.

- [ ] **Step 4: Create `02-preference-alignment-rlhf-dpo.md`**

Required content:

- Explain why SFT is not enough: multiple valid answers have different human preference quality.
- Define reward model, PPO/RLHF, KL constraint, DPO, chosen/rejected pair.
- Include a tiny pairwise preference example.
- Explain DPO as directly optimizing preference pairs without training a separate reward model in the same way as RLHF.
- Include a common-mistakes table covering “RLHF = only RL”, “DPO does not need preferences”, and “alignment makes the model factual”.
- Link to `./01-pretraining-sft-overview.md`.

- [ ] **Step 5: Create `03-lora-qlora-distillation.md`**

Required content:

- Explain the problem: full fine-tuning is expensive and risky.
- Define LoRA as low-rank adapter update, QLoRA as quantized base + LoRA training, distillation as teacher-to-student transfer, and model merge as combining weights/adapters.
- Include a minimal shape explanation:

```text
原权重 W 不动
只训练一个低秩增量 ΔW = A @ B
推理时使用 W + ΔW
```

- Explain when to use LoRA vs prompt/RAG vs full fine-tuning.
- Link to `../foundations/deep-learning/01-neuron-mlp-activation.md` for linear layers.

- [ ] **Step 6: Create `04-model-evolution-bert-gpt-t5.md`**

Required content:

- Explain why history matters only as architecture/training-objective context.
- Cover BERT as encoder-only + MLM, GPT as decoder-only + CLM, T5 as encoder-decoder + text-to-text.
- Explain the shift from pretrain+finetune to pretrain+prompt/in-context learning to chat alignment.
- Include a table comparing BERT/GPT/T5 by architecture, training objective, input/output shape, and modern role.
- Link to `../04-transformer-foundations/07-transformer-architecture-variants.md`.

- [ ] **Step 7: Mark old training/history directories as reference**

Modify `05-pretrained-models/README.md` opening with:

```markdown
> **新版路线说明**：这个目录保留 BERT、GPT、T5 等历史材料。默认学习路径中，模型演进已经压缩进 [训练、对齐与微调](../05-training-alignment-finetuning/)，这里只作为深入参考。
```

Modify `06-llm-core/README.md` opening with:

```markdown
> **新版路线说明**：这个旧目录覆盖很多 LLM 核心主题，但第一次学习不再建议顺序读完。训练/对齐/微调、推理部署、评估安全已经拆入新的主线模块。
```

- [ ] **Step 8: Verify and commit**

Run:

```bash
rg -n "05 训练|预训练|SFT|RLHF|DPO|LoRA|QLoRA|BERT|GPT|T5|新版路线说明" ai/ml-to-llm-roadmap/05-training-alignment-finetuning ai/ml-to-llm-roadmap/05-pretrained-models/README.md ai/ml-to-llm-roadmap/06-llm-core/README.md
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/05-training-alignment-finetuning ai/ml-to-llm-roadmap/05-pretrained-models/README.md ai/ml-to-llm-roadmap/06-llm-core/README.md
git commit -m "docs: systematize training alignment finetuning module"
```

## Task 3: Build Inference, Deployment, And Cost Module

**Files:**
- Create: `ai/ml-to-llm-roadmap/06-inference-deployment-cost/README.md`
- Create: `ai/ml-to-llm-roadmap/06-inference-deployment-cost/01-prefill-decode-kv-cache.md`
- Create: `ai/ml-to-llm-roadmap/06-inference-deployment-cost/02-batching-vllm-quantization.md`
- Create: `ai/ml-to-llm-roadmap/06-inference-deployment-cost/03-long-context-edge-cost.md`
- Modify: `ai/ml-to-llm-roadmap/06-llm-core/README.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/06-inference-deployment-cost
```

- [ ] **Step 2: Create `README.md`**

Create a README with:

```markdown
# 06 推理优化、部署与成本

> **定位**：这个模块解释为什么 LLM 推理慢、贵、吃显存，以及工程上如何通过 KV Cache、batching、量化、长上下文策略和端侧部署降低成本。

## 默认学习顺序

1. [Prefill、Decode 与 KV Cache](./01-prefill-decode-kv-cache.md)
2. [Batching、vLLM/PagedAttention 与量化](./02-batching-vllm-quantization.md)
3. [长上下文、端侧部署与成本估算](./03-long-context-edge-cost.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| Decoder-only 的逐 token 生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| KV Cache 的基本直觉 | [KV Cache 与上下文成本](../04-transformer-foundations/09-kv-cache-context-cost.md) |
| Attention 为什么随序列变贵 | [Self-Attention QKV](../04-transformer-foundations/04-self-attention-qkv.md) |
```

- [ ] **Step 3: Create `01-prefill-decode-kv-cache.md`**

Required content:

- Explain prefill and decode as two phases with different bottlenecks.
- Explain KV cache as reusing past K/V, not caching final answers.
- Include a small step-by-step token generation example.
- Explain TTFT, tokens/sec, context length, batch size.
- Link to `../04-transformer-foundations/09-kv-cache-context-cost.md`.

- [ ] **Step 4: Create `02-batching-vllm-quantization.md`**

Required content:

- Explain serving problem: many users, variable lengths, GPU memory fragmentation.
- Define static batching, dynamic/continuous batching, PagedAttention, quantization.
- Explain quantization tradeoff: less memory and bandwidth, possible quality loss.
- Include a minimal table comparing FP16, INT8, INT4.
- Link to `./01-prefill-decode-kv-cache.md`.

- [ ] **Step 5: Create `03-long-context-edge-cost.md`**

Required content:

- Explain long context as cost and quality problem, not just max token number.
- Define RoPE scaling, sliding window, chunking, retrieval-assisted context, summarization, and prompt compression.
- Explain edge deployment through quantization, smaller models, GGUF/llama.cpp style local inference at a conceptual level.
- Include a cost formula:

```text
总成本 ≈ 输入 token 成本 + 输出 token 成本 + 检索/重排/工具调用成本 + 失败重试成本
```

- Include self-check questions around long-context tradeoffs and cost debugging.

- [ ] **Step 6: Add inference-routing note to old LLM core README**

Ensure `06-llm-core/README.md` links to `../06-inference-deployment-cost/` in the new-route explanation.

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "06 推理|Prefill|Decode|KV Cache|PagedAttention|量化|长上下文|端侧|总成本" ai/ml-to-llm-roadmap/06-inference-deployment-cost ai/ml-to-llm-roadmap/06-llm-core/README.md
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/06-inference-deployment-cost ai/ml-to-llm-roadmap/06-llm-core/README.md
git commit -m "docs: systematize inference deployment cost module"
```

## Task 4: Build Evaluation, Safety, And Production Module

**Files:**
- Create: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/README.md`
- Create: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md`
- Create: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/02-hallucination-safety-guardrails.md`
- Create: `ai/ml-to-llm-roadmap/07-evaluation-safety-production/03-production-debugging-monitoring.md`
- Modify: `ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/07-evaluation-safety-production
```

- [ ] **Step 2: Create `README.md`**

Create a README with:

```markdown
# 07 评估、安全与生产排查

> **定位**：这个模块解释 LLM 应用上线后如何判断“好不好、安不安全、哪里坏了”。它把评估、安全和生产排查放在一起，因为真实系统里这三件事经常互相影响。

## 默认学习顺序

1. [LLM 评估与 LLM-as-Judge](./01-llm-evaluation-judge.md)
2. [幻觉、安全与 Guardrails](./02-hallucination-safety-guardrails.md)
3. [生产排查、监控与回归定位](./03-production-debugging-monitoring.md)
```

- [ ] **Step 3: Create `01-llm-evaluation-judge.md`**

Required content:

- Explain why traditional exact-match metrics are insufficient for open-ended LLM outputs.
- Define offline eval, online eval, human eval, LLM-as-Judge, rubric, golden set, regression set.
- Include a minimal judge rubric example with correctness, helpfulness, citation/grounding, safety.
- Explain judge bias and calibration.
- Link to `../09-review-notes/03-transformer-core-cheatsheet.md` only if needed for model background; otherwise keep focused.

- [ ] **Step 4: Create `02-hallucination-safety-guardrails.md`**

Required content:

- Explain hallucination as model producing plausible unsupported content.
- Separate factuality, grounding, instruction-following, and policy safety.
- Explain mitigations: better context, refusal, citations, verification, constrained output, red teaming, input/output filters.
- Include prompt injection direct vs indirect and why RAG/Agent-specific details are deferred.
- Link to `../03-generation-control/02-structured-output-constrained-decoding.md` for structured-output guardrails.

- [ ] **Step 5: Create `03-production-debugging-monitoring.md`**

Required content:

- Explain debugging from symptom to component: input, retrieval/context if applicable, prompt, model, decoding, tool/output parser, evaluator, infra.
- Since RAG and Agent modules are deferred, present retrieval/tool rows as optional components, not the main path.
- Include monitoring dimensions: quality, latency, cost, safety, refusal rate, schema failure, drift, user feedback.
- Include a small incident example: output quality drops after model/version/prompt change.
- Link to `../06-inference-deployment-cost/README.md` for latency/cost and `./01-llm-evaluation-judge.md` for eval.

- [ ] **Step 6: Mark old theory-practice bridge as reference**

Modify the top of `07-theory-practice-bridge/README.md` with:

```markdown
> **新版路线说明**：这个目录保留 RAG、Agent、Prompt、生产排查和微调实操的旧版桥接材料。RAG 与 Agent 会后续单独系统化；生产排查默认迁入 [评估、安全与生产排查](../07-evaluation-safety-production/)。
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "07 评估|LLM-as-Judge|rubric|幻觉|Guardrails|生产排查|监控|新版路线说明" ai/ml-to-llm-roadmap/07-evaluation-safety-production ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/07-evaluation-safety-production ai/ml-to-llm-roadmap/07-theory-practice-bridge/README.md
git commit -m "docs: systematize evaluation safety production module"
```

## Task 5: Build System Design And Project Narrative Module

**Files:**
- Create: `ai/ml-to-llm-roadmap/08-system-design-project-narrative/README.md`
- Create: `ai/ml-to-llm-roadmap/08-system-design-project-narrative/01-ai-system-design-method.md`
- Create: `ai/ml-to-llm-roadmap/08-system-design-project-narrative/02-llm-platform-routing-cost.md`
- Create: `ai/ml-to-llm-roadmap/08-system-design-project-narrative/03-project-narrative.md`
- Modify: `ai/ml-to-llm-roadmap/08-interview-synthesis/README.md`

- [ ] **Step 1: Create module directory**

Run:

```bash
mkdir -p ai/ml-to-llm-roadmap/08-system-design-project-narrative
```

- [ ] **Step 2: Create `README.md`**

Create a README with:

```markdown
# 08 系统设计与项目叙事

> **定位**：这个模块把前面学到的生成控制、训练适配、推理成本、评估安全串成面试中的系统设计和项目表达。RAG/Agent 题型会后续单独补，本模块先建立通用 AI Engineer 设计框架。

## 默认学习顺序

1. [AI 系统设计方法论](./01-ai-system-design-method.md)
2. [LLM 平台、模型路由与成本治理](./02-llm-platform-routing-cost.md)
3. [项目叙事：把经历讲成可追问的技术故事](./03-project-narrative.md)
```

- [ ] **Step 3: Create `01-ai-system-design-method.md`**

Required content:

- Explain why AI system design differs from normal backend design: uncertainty, eval, latency/cost, safety, model behavior changes.
- Provide a 6-step method:
  1. clarify user/task/success metric
  2. define input/output contract
  3. choose model and control strategy
  4. design evaluation and guardrails
  5. design serving/cost path
  6. plan monitoring and iteration
- Include a non-RAG, non-Agent example: structured support-ticket classification and response drafting.
- Link to generation control, inference, and evaluation modules.

- [ ] **Step 4: Create `02-llm-platform-routing-cost.md`**

Required content:

- Explain platform-level concerns: model gateway, routing, fallback, rate limiting, caching, prompt/version management, logging, eval hooks, budget controls.
- Include a model-routing table with cheap model, strong model, long-context model, local/edge model.
- Explain cost governance using input tokens, output tokens, retries, latency, and eval failures.
- Link to `../06-inference-deployment-cost/03-long-context-edge-cost.md`.

- [ ] **Step 5: Create `03-project-narrative.md`**

Required content:

- Explain project narrative as “problem -> constraints -> design decisions -> eval -> production result -> lessons”.
- Include STAR + technical-depth hybrid template.
- Include a generic LLM output-quality improvement story, not RAG/Agent-specific.
- Include a追问清单 covering eval, latency, cost, safety, tradeoffs, failure case, and next iteration.
- Link to `../07-evaluation-safety-production/03-production-debugging-monitoring.md`.

- [ ] **Step 6: Mark old interview synthesis as reference**

Modify `08-interview-synthesis/README.md` opening with:

```markdown
> **新版路线说明**：这个目录保留旧版 Top 题、系统设计和项目叙事材料。默认面试准备会逐步迁入 [interview-paths](../interview-paths/) 和 [review notes](../09-review-notes/)。
```

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "08 系统设计|AI 系统设计|模型路由|成本治理|项目叙事|新版路线说明" ai/ml-to-llm-roadmap/08-system-design-project-narrative ai/ml-to-llm-roadmap/08-interview-synthesis/README.md
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/08-system-design-project-narrative ai/ml-to-llm-roadmap/08-interview-synthesis/README.md
git commit -m "docs: systematize system design narrative module"
```

## Task 6: Add Interview Paths For The Five Modules

**Files:**
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-generation-control.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-training-alignment.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-inference-deployment.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-evaluation-safety.md`
- Create: `ai/ml-to-llm-roadmap/interview-paths/ai-engineer-system-design.md`

- [ ] **Step 1: Create generation-control interview path**

Use the Interview Path Standard. Must link:

- `../03-generation-control/01-decoding-parameters.md`
- `../03-generation-control/02-structured-output-constrained-decoding.md`
- `../03-generation-control/03-function-calling-output-shape.md`
- `../09-review-notes/04-generation-control-cheatsheet.md`

Must-answer questions:

1. Temperature、Top-k、Top-p 分别控制什么？
2. JSON Mode 和 schema constrained decoding 的区别？
3. Function Calling 是模型执行工具吗？
4. Prompt 约束为什么不等于结构化输出保证？
5. 结构化输出失败时怎么设计 fallback？

- [ ] **Step 2: Create training/alignment interview path**

Must link:

- `../05-training-alignment-finetuning/01-pretraining-sft-overview.md`
- `../05-training-alignment-finetuning/02-preference-alignment-rlhf-dpo.md`
- `../05-training-alignment-finetuning/03-lora-qlora-distillation.md`
- `../05-training-alignment-finetuning/04-model-evolution-bert-gpt-t5.md`
- `../09-review-notes/05-training-alignment-finetuning-cheatsheet.md`

Must-answer questions:

1. Pretraining、SFT、RLHF/DPO 各解决什么问题？
2. 为什么 SFT 不等于对齐？
3. RLHF 和 DPO 的核心差异？
4. LoRA/QLoRA 为什么省显存？
5. BERT、GPT、T5 的架构和训练目标差异？

- [ ] **Step 3: Create inference/deployment interview path**

Must link:

- `../06-inference-deployment-cost/01-prefill-decode-kv-cache.md`
- `../06-inference-deployment-cost/02-batching-vllm-quantization.md`
- `../06-inference-deployment-cost/03-long-context-edge-cost.md`
- `../09-review-notes/06-inference-deployment-cost-cheatsheet.md`

Must-answer questions:

1. Prefill 和 Decode 的瓶颈分别是什么？
2. KV Cache 缓存的是什么？
3. vLLM/PagedAttention 解决什么问题？
4. 量化如何影响速度、显存和质量？
5. 长上下文为什么贵，怎么优化？

- [ ] **Step 4: Create evaluation/safety interview path**

Must link:

- `../07-evaluation-safety-production/01-llm-evaluation-judge.md`
- `../07-evaluation-safety-production/02-hallucination-safety-guardrails.md`
- `../07-evaluation-safety-production/03-production-debugging-monitoring.md`
- `../09-review-notes/07-evaluation-safety-production-cheatsheet.md`

Must-answer questions:

1. 怎么设计 LLM eval？
2. LLM-as-Judge 有什么风险？
3. 幻觉有哪些类型，怎么缓解？
4. Prompt Injection 怎么分类和防御？
5. 线上质量回退怎么定位？

- [ ] **Step 5: Create system-design interview path**

Must link:

- `../08-system-design-project-narrative/01-ai-system-design-method.md`
- `../08-system-design-project-narrative/02-llm-platform-routing-cost.md`
- `../08-system-design-project-narrative/03-project-narrative.md`
- `../09-review-notes/08-system-design-project-narrative-cheatsheet.md`

Must-answer questions:

1. AI 系统设计和普通后端系统设计有什么不同？
2. 如何设计模型路由和 fallback？
3. 如何把成本、延迟、质量一起权衡？
4. 如何设计 eval 和监控？
5. 怎么讲一个项目让面试官能继续深挖？

- [ ] **Step 6: Verify and commit**

Run:

```bash
rg -n "90 分钟冲刺|半天复盘|必答问题|复习笔记" ai/ml-to-llm-roadmap/interview-paths
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/interview-paths
git commit -m "docs: add interview paths for remaining modules"
```

## Task 7: Add Review Notes For The Five Modules

**Files:**
- Create: `ai/ml-to-llm-roadmap/09-review-notes/README.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/04-generation-control-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/05-training-alignment-finetuning-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/06-inference-deployment-cost-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/07-evaluation-safety-production-cheatsheet.md`
- Create: `ai/ml-to-llm-roadmap/09-review-notes/08-system-design-project-narrative-cheatsheet.md`

- [ ] **Step 1: Create or update review notes README**

Create `09-review-notes/README.md` with:

```markdown
# 09 面试复习笔记

> **定位**：这里是学完系统主线后的压缩复习材料，不是第一次学习入口。

## 已有笔记

| 笔记 | 对应系统主线 |
|------|--------------|
| [Transformer 核心速记](./03-transformer-core-cheatsheet.md) | [Transformer 必要基础](../04-transformer-foundations/) |
| [生成控制速记](./04-generation-control-cheatsheet.md) | [生成控制与结构化输出](../03-generation-control/) |
| [训练对齐微调速记](./05-training-alignment-finetuning-cheatsheet.md) | [训练、对齐与微调](../05-training-alignment-finetuning/) |
| [推理部署成本速记](./06-inference-deployment-cost-cheatsheet.md) | [推理优化、部署与成本](../06-inference-deployment-cost/) |
| [评估安全生产速记](./07-evaluation-safety-production-cheatsheet.md) | [评估、安全与生产排查](../07-evaluation-safety-production/) |
| [系统设计项目叙事速记](./08-system-design-project-narrative-cheatsheet.md) | [系统设计与项目叙事](../08-system-design-project-narrative/) |
```

- [ ] **Step 2: Create generation-control cheatsheet**

Use Review Note Standard. Include 30-second answers for:

- Temperature / Top-k / Top-p
- Constrained decoding
- JSON mode vs schema
- Function Calling boundary
- Structured-output fallback

- [ ] **Step 3: Create training/alignment cheatsheet**

Use Review Note Standard. Include 30-second answers for:

- Pretraining vs SFT vs alignment
- RLHF vs DPO
- KL constraint
- LoRA/QLoRA
- BERT/GPT/T5 differences

- [ ] **Step 4: Create inference/deployment cheatsheet**

Use Review Note Standard. Include 30-second answers for:

- Prefill vs Decode
- KV Cache
- vLLM/PagedAttention
- Quantization
- Long-context cost

- [ ] **Step 5: Create evaluation/safety cheatsheet**

Use Review Note Standard. Include 30-second answers for:

- LLM eval design
- LLM-as-Judge
- Hallucination
- Prompt injection
- Production quality regression

- [ ] **Step 6: Create system-design cheatsheet**

Use Review Note Standard. Include 30-second answers for:

- AI system design method
- Model routing
- Fallback/caching/cost governance
- Eval/monitoring in system design
- Project narrative structure

- [ ] **Step 7: Verify and commit**

Run:

```bash
rg -n "30 秒答案|2 分钟展开|高频追问|易混点|项目连接|反向链接" ai/ml-to-llm-roadmap/09-review-notes
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap/09-review-notes
git commit -m "docs: add review notes for remaining modules"
```

## Task 8: Update Root Roadmap Navigation

**Files:**
- Modify: `ai/ml-to-llm-roadmap.md`

- [ ] **Step 1: Update target-structure status table**

Modify `## 第一批迁移成果` into a broader migration table named:

```markdown
## 迁移成果
```

The table must include these rows:

```markdown
| RAG 与检索系统 | 旧版资料保留，后续单独系统化 | [旧版 RAG 参考](./ml-to-llm-roadmap/07-theory-practice-bridge/01-rag-deep-dive.md) | 待迁移 |
| Agent 与工具调用 | 旧版资料保留，后续单独系统化 | [旧版 Agent 参考](./ml-to-llm-roadmap/07-theory-practice-bridge/02-agent-architecture.md) | 待迁移 |
| 生成控制与结构化输出 | 解码参数、结构化输出、Function Calling 输出形态 | [03-generation-control](./ml-to-llm-roadmap/03-generation-control/) | 已系统化 |
| Transformer 必要基础 | 从 AI Engineer 视角系统理解 Transformer | [04-transformer-foundations](./ml-to-llm-roadmap/04-transformer-foundations/) | 已创建 |
| 训练、对齐与微调 | 预训练、SFT、偏好对齐、LoRA/QLoRA | [05-training-alignment-finetuning](./ml-to-llm-roadmap/05-training-alignment-finetuning/) | 已系统化 |
| 推理优化、部署与成本 | Prefill/Decode、KV Cache、batching、量化、长上下文 | [06-inference-deployment-cost](./ml-to-llm-roadmap/06-inference-deployment-cost/) | 已系统化 |
| 评估、安全与生产排查 | Eval、LLM-as-Judge、幻觉、安全、监控排查 | [07-evaluation-safety-production](./ml-to-llm-roadmap/07-evaluation-safety-production/) | 已系统化 |
| 系统设计与项目叙事 | 通用 AI 系统设计、模型路由、项目表达 | [08-system-design-project-narrative](./ml-to-llm-roadmap/08-system-design-project-narrative/) | 已系统化 |
| 面试复习笔记 | 30 秒答案、追问、易混点和项目连接 | [09-review-notes](./ml-to-llm-roadmap/09-review-notes/) | 部分完成 |
| Deep Learning 补课 | 支撑 Transformer 的神经网络基础 | [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/) | 已系统化 |
```

- [ ] **Step 2: Update sprint path**

In `## 面试冲刺路径`, keep Transformer first, then add:

```markdown
4. 生成控制面试路径：[interview-paths/ai-engineer-generation-control.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-generation-control.md)
5. 训练对齐面试路径：[interview-paths/ai-engineer-training-alignment.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-training-alignment.md)
6. 推理部署面试路径：[interview-paths/ai-engineer-inference-deployment.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-inference-deployment.md)
7. 评估安全面试路径：[interview-paths/ai-engineer-evaluation-safety.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-evaluation-safety.md)
8. 系统设计面试路径：[interview-paths/ai-engineer-system-design.md](./ml-to-llm-roadmap/interview-paths/ai-engineer-system-design.md)
```

Leave RAG/Agent as optional old references.

- [ ] **Step 3: Update system-learning path**

Ensure `## 系统学习路径` says:

```markdown
1. 从 [Transformer 必要基础](./ml-to-llm-roadmap/04-transformer-foundations/) 开始。
2. 缺 Deep Learning 前置知识时进入 [foundations/deep-learning](./ml-to-llm-roadmap/foundations/deep-learning/)。
3. 然后按目标选择：生成控制、训练对齐、推理部署、评估安全、系统设计。
4. RAG 与 Agent 暂时使用旧版参考，后续单独系统化。
5. 每个模块学完后，用对应 `09-review-notes/` 做面试复盘。
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
rg -n "迁移成果|03-generation-control|05-training-alignment-finetuning|06-inference-deployment-cost|07-evaluation-safety-production|08-system-design-project-narrative|RAG 与检索系统|Agent 与工具调用|待迁移|已系统化" ai/ml-to-llm-roadmap.md
git diff --check
```

Commit:

```bash
git add ai/ml-to-llm-roadmap.md
git commit -m "docs: update roadmap for remaining mainline modules"
```

## Task 9: Final Validation

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

Run this from repo root:

```bash
python3 - <<'PY'
from pathlib import Path
import re

roots = [
    Path('ai/ml-to-llm-roadmap.md'),
    Path('ai/ml-to-llm-roadmap/03-generation-control'),
    Path('ai/ml-to-llm-roadmap/05-training-alignment-finetuning'),
    Path('ai/ml-to-llm-roadmap/06-inference-deployment-cost'),
    Path('ai/ml-to-llm-roadmap/07-evaluation-safety-production'),
    Path('ai/ml-to-llm-roadmap/08-system-design-project-narrative'),
    Path('ai/ml-to-llm-roadmap/interview-paths'),
    Path('ai/ml-to-llm-roadmap/09-review-notes'),
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
    text = file.read_text()
    for line_no, line in enumerate(text.splitlines(), 1):
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

- [ ] **Step 3: Verify route status terms**

Run:

```bash
rg -n "已系统化|待迁移|默认学习顺序|学前检查|30 秒答案|90 分钟冲刺|RAG 与 Agent 暂时使用旧版参考" ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap/03-generation-control ai/ml-to-llm-roadmap/05-training-alignment-finetuning ai/ml-to-llm-roadmap/06-inference-deployment-cost ai/ml-to-llm-roadmap/07-evaluation-safety-production ai/ml-to-llm-roadmap/08-system-design-project-narrative ai/ml-to-llm-roadmap/interview-paths ai/ml-to-llm-roadmap/09-review-notes
```

Expected:
- `rg` finds all status and structure terms.

- [ ] **Step 4: Final review**

Perform a final read-through focused on these questions:

- Does every new mainline module have a smooth first-time learning path?
- Are RAG and Agent clearly deferred rather than silently mixed into default routes?
- Do review notes only summarize concepts already explained in system pages?
- Are old directories clearly marked as references?
- Does the root roadmap tell the learner what to read next?

- [ ] **Step 5: Commit any final fixes**

If final review requires fixes, commit them:

```bash
git add ai/ml-to-llm-roadmap.md ai/ml-to-llm-roadmap
git commit -m "docs: polish remaining roadmap mainline"
```

If no fixes are needed, do not create an empty commit.
