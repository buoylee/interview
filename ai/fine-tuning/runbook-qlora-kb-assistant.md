# QLoRA 微调实操 Runbook：知识库助手（月4 实操）

> **目标版本**：月4 · 2026-06 · branch `agent-loop-lab`
> **状态**：数据已构造完毕，GPU 相关数字待实测后回填（标注 〔待实测〕）

---

## 1. 目标与产出

### 做什么

跑通一次完整的 QLoRA 微调循环：先用原始 notebook 验证环境和流程，再替换为自构的企业知识库 SFT 数据，最后用 eval 思路做前后对比。

### 产出清单

| 产出 | 文件 | 状态 |
|------|------|------|
| SFT 数据集 | `data/kb_sft.jsonl` | 已生成（45 条） |
| 数据构造脚本 | `prepare_kb_data.py` | 可立即运行 |
| 微调 Notebook | `Qwen3_(14B)_Reasoning_Conversational.ipynb` | 需 GPU 运行 |
| eval 结果表 | 本文第 4 节 | 〔待实测〕 |

### 面试达标线

能说清楚以下三点即达标：
1. **数据怎么构造**：从 heading 结构化语料，模板化生成 What/How/Compare 三种问答 + 拒答样本；
2. **参数为什么这么配**：r=32 / lora_alpha=32 / 4-bit 量化的选型逻辑；
3. **效果怎么验证**：微调前后对同一组问题评四维（正确率/groundedness/拒答正确率/平均分）。

---

## 2. 第一遍：原样跑通

> 目的：验证 Colab 环境可以跑起来，记录基线 loss 和训练时长，不换数据。
> 细节参考：[notebook-explained.md](./notebook-explained.md)（760 行逐行解读）

### Checklist

- [ ] 打开 Google Colab → 运行时 → 更改运行时类型 → **T4**（免费）或 **A100**（需订阅）
- [ ] 挂载 Google Drive（用于断连时保存 checkpoint）：
  ```python
  from google.colab import drive
  drive.mount('/content/drive')
  ```
- [ ] 运行 `Qwen3_(14B)_Reasoning_Conversational.ipynb` 所有 Cell
- [ ] 确认 LoRA adapter 可训练参数比例约为 **0.86%**（见 notebook-explained.md 阶段 3）
- [ ] 训练结束后记录以下数字（回填到下表）：

| 指标 | 值 |
|------|----|
| 训练时长（分钟） | 〔待实测〕 |
| 显存峰值（GB） | 〔待实测〕 |
| 初始 loss | 〔待实测〕 |
| 最终 loss（最后 10 步均值） | 〔待实测〕 |
| Loss 趋势 | 〔待实测，预期：持续下降后收敛〕 |

### 常见坑

**坑 1：Colab 断连导致训练中止**

Colab 免费版约 1-2 小时无操作会断连。解法：

```python
# 训练时加 checkpoint 保存，每 N 步保存到 Drive
args = SFTConfig(
    ...
    save_steps = 50,
    output_dir = "/content/drive/MyDrive/qwen3-qlora-checkpoints",
)
```

**坑 2：xformers 版本不匹配**

Notebook 开头根据 PyTorch 版本自动选择 xformers 版本（见 notebook-explained.md 阶段 1）。如果报错 `xformers is not compatible`，确认 PyTorch 版本在 2.8–2.10 之间：

```python
import torch; print(torch.__version__)
```

**坑 3：T4 显存不足（16GB）**

T4 装 Qwen3-14B 4-bit 需约 8GB，加上 LoRA 和 batch 约 12-14GB，接近上限。如出现 OOM：
- 将 `per_device_train_batch_size` 从 2 降到 1
- 将 `max_seq_length` 从 2048 降到 1024
- 或改用 A100（40GB）

---

## 3. 第二遍：换自构数据

### 3.1 生成 SFT 数据集

数据已生成，可直接跳到 3.2。如需重新生成：

```bash
# 在本地运行（无需 GPU，无需额外依赖）
cd ai/fine-tuning
python3 prepare_kb_data.py
```

**实际输出（已运行）**：

```
Found 4 source docs: ['docker.md', 'kubernetes.md', 'postgres.md', 'redis.md']
  docker.md:     5 sections → 10 samples（含 1 个 Compare 样本）
  kubernetes.md: 4 sections → 9 samples（含 1 个 Compare 样本）
  postgres.md:   4 sections → 10 samples（含 2 个 Compare 样本）
  redis.md:      5 sections → 10 samples（含 2 个 Compare 样本）

Total samples:    45
  KB samples:     39
  Refusal samples: 6
```

数据文件：[data/kb_sft.jsonl](./data/kb_sft.jsonl)

**数据构造策略说明**（面试可答）：
- 每个 `## heading` 章节生成 2-3 条样本：
  - **What 模板**：`什么是 <heading>？` → 答案取章节前 3 句
  - **How 模板**：`<heading> 是如何工作的？` → 答案取含动词关键词的句子 + 正文前 400 字
  - **Compare 模板**（仅在章节含对比关键词时触发）：`<heading> 中有哪些取舍？` → 答案取含对比关键词的段落
- 所有答案以 `（来源：<filename>，章节：<heading>）` 结尾 → 强化 groundedness 行为
- 6 条拒答样本对应 MVP 的 `REFUSAL_MARKERS "依据不足"` 格式

### 3.2 修改 Notebook 的数据加载段

对照 [notebook-explained.md](./notebook-explained.md) 的「阶段 4：数据准备」节，将原始数据加载替换为如下代码（找到 `from datasets import load_dataset` 块，替换整段）：

```python
# ========== 替换原有数据加载段（阶段 4.1-4.4）==========
from datasets import load_dataset, Dataset
import json, pathlib

# 从 kb_sft.jsonl 加载（上传到 Colab 或从 Drive 读取）
KB_JSONL = "/content/drive/MyDrive/kb_sft.jsonl"  # 先把 data/kb_sft.jsonl 上传到 Drive

# 用 HuggingFace datasets 加载
raw = load_dataset("json", data_files=KB_JSONL, split="train")

# 应用 Qwen3 的 chat template（把 messages 转成模型格式的文本）
def apply_template(example):
    text = tokenizer.apply_chat_template(
        example["messages"],  # list of {"role": ..., "content": ...}
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}

combined_dataset = raw.map(apply_template, remove_columns=raw.column_names)
combined_dataset = combined_dataset.shuffle(seed=3407)
# ========== 替换结束 ==========
```

> 注意：`tokenizer` 在阶段 2 加载模型时已初始化，直接复用即可。
> `messages` 字段格式与 notebook 原来的格式完全一致（`[{"role":"user",...}, ...]`）。
> 其余训练 Cell（阶段 5 SFTTrainer）无需改动，`dataset_text_field = "text"` 保持不变。

### 3.3 上传数据文件到 Colab

```bash
# 方式一：直接上传（小文件，推荐）
from google.colab import files
files.upload()  # 选择 kb_sft.jsonl

# 方式二：从 Drive 读取（如已挂载）
# 先把 kb_sft.jsonl 复制到 Drive，然后用上面 KB_JSONL 路径
```

### 3.4 训练超参起点

沿用 notebook 默认值，下表说明哪些参数值得根据数据量调整：

| 参数 | Notebook 默认 | 知识库数据建议 | 理由 |
|------|-------------|-------------|------|
| `num_train_epochs` | 注释掉（用 max_steps） | **1-2 epochs** | 数据只有 45 条，2 epoch ≈ 90 步；过多会过拟合 |
| `max_steps` | 60 | 改为 **-1**（跑完整 epoch） | 45 条数据，60 步约等于 1.5 epoch，直接跑 epoch 更直观 |
| `learning_rate` | 2e-4 | **1e-4 ～ 2e-4** | 数据少时略降 lr 更稳 |
| `max_seq_length` | 2048 | **1024** | 知识库 Q&A 一般 300-600 token，缩短可省显存 |
| `per_device_train_batch_size` | 2 | 2（T4 够用） | 45 条小数据集，batch=2 足够 |
| `gradient_accumulation_steps` | 4 | 4（等效 batch=8） | 保持不变 |
| `r` (LoRA rank) | 32 | 32（保持） | 见下方「参数为什么这么配」 |

**参数为什么这么配**（面试可答）：
- `r=32`：rank 越大表达力越强，但参数量增加。对 14B 基座而言，r=32 约占 0.86% 参数，是效果与成本的平衡点；小任务用 r=8 也可以。
- `lora_alpha=32`：实际缩放因子 = alpha/r = 1，不放大 LoRA 影响，让训练更稳定。
- `4-bit 量化`（load_in_4bit=True）：14B 模型全精度需 28GB，4-bit 只需 ~8GB，让 T4（16GB）能装下。

---

## 4. 前后对比 Eval

### 4.1 测试集来源

从 MVP golden set 取问题：[../langchain/mvp-agentic-rag/eval/golden/cases.jsonl](../langchain/mvp-agentic-rag/eval/golden/cases.jsonl)

**选取策略**（共 13 条）：
- **10 条 KB 问题**（`should_refuse=false` + `expected_route="kb_rag"`）：覆盖 docker/k8s/postgres/redis 四个文档
- **3 条应拒答问题**（`should_refuse=true`）：`refuse-unknown` / `refuse-salary` / `refuse-fabricate`

完整 ID 列表：
```
KB:     kb-autoscaling, kb-pgvector, kb-k8s-probes, kb-k8s-rolling,
        kb-pg-ivfflat, kb-pg-fulltext, kb-docker-multistage,
        kb-docker-healthcheck, kb-redis-persistence, kb-redis-cache-aside
拒答:   refuse-unknown, refuse-salary, refuse-fabricate
```

### 4.2 评估方式

使用 [../ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md](../ml-to-llm-roadmap/07-evaluation-safety-production/01-llm-evaluation-judge.md) 中的 judge prompt，对每条回答评四维（1-5 分）：

| 维度 | 含义 |
|------|------|
| 正确率 (Correctness) | 答案内容是否准确 |
| Groundedness | 是否基于知识库内容，不凭空编造 |
| 拒答正确率 (Refusal) | 应拒答时是否明确说明依据不足 |
| 平均分 (Avg) | 前三维均值 |

**方式**：人工评（小数据量时推荐）或 LLM-judge（Claude/GPT-4o 调 judge prompt）。

### 4.3 结果记录表（〔待实测〕）

对相同的 13 条问题，分别用微调前模型（base Qwen3-14B）和微调后模型生成回答，填入下表：

| 指标 | 微调前（Base） | 微调后（SFT） | 变化 |
|------|------------|------------|------|
| KB 问题正确率（/5） | 〔待实测〕 | 〔待实测〕 | — |
| KB 问题 Groundedness（/5） | 〔待实测〕 | 〔待实测〕 | — |
| 拒答正确率（3 条中几条正确） | 〔待实测〕 | 〔待实测〕 | — |
| 平均分（10 条 KB + 3 条拒答） | 〔待实测〕 | 〔待实测〕 | — |
| 来源引用率（答案含"来源:"比例） | 〔待实测〕 | 〔待实测〕 | — |

### 4.4 生成回答（Notebook Cell 参考）

```python
# 微调后推理：在训练完成后的 Cell 中执行
test_questions = [
    "How does Kubernetes autoscaling work?",
    "What index should I use for vector search in Postgres?",
    "What is the difference between liveness and readiness probes in Kubernetes?",
    # ... 补全 13 条
]

from unsloth.chat_templates import get_chat_template
FastLanguageModel.for_inference(model)  # 切换到推理模式

for q in test_questions:
    inputs = tokenizer.apply_chat_template(
        [{"role": "user", "content": q}],
        tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to("cuda")
    output = model.generate(inputs, max_new_tokens=512, temperature=0.1)
    print(tokenizer.decode(output[0], skip_special_tokens=True))
    print("---")
```

---

## 5. 记录与回填

跑完实测后，回填以下两个位置：

### 5.1 本文件

将第 2 节训练指标表、第 4.3 节 eval 结果表的 `〔待实测〕` 替换为实际数字。

### 5.2 05 模块锚点

回填位置：[../ml-to-llm-roadmap/05-training-alignment-finetuning/](../ml-to-llm-roadmap/05-training-alignment-finetuning/)

具体文件和位置：

- **`03-lora-qlora-distillation.md`**：在「实战案例」或文末补充一个锚点段落，格式：
  ```markdown
  ### 月4 实操锚点（知识库助手 QLoRA）
  - 数据：45 条（39 KB + 6 拒答），来源 4 个 heading 结构化文档
  - 配置：Qwen3-14B / r=32 / 4-bit / T4 GPU
  - 训练时长：〔待实测〕分钟 / 显存峰值：〔待实测〕GB
  - eval：正确率 〔待实测〕 → 〔待实测〕 / groundedness 〔待实测〕 → 〔待实测〕
  ```
- **`01-pretraining-sft-overview.md`**：如有「SFT 数据构造」节，补充数据构造方法的实测备注。

---

## 6. 面试 30 秒

> 基于即将完成的实操（数字填入后替换 〔待实测〕 部分）：

**中文版**：

> 我做了一次 QLoRA 微调实验：基座用 Qwen3-14B，4-bit 量化跑在 T4 GPU 上，LoRA rank=32，覆盖 Attention + FFN 全部目标层，可训练参数约 0.86%。
>
> 数据方面，从 4 个企业知识库文档（Docker/K8s/Postgres/Redis）按 heading 结构模板化构造了 45 条 SFT 样本：What/How/Compare 三种问答模板 + 6 条依据不足拒答样本，答案全部锚定原文并注明来源文件。
>
> 效果验证用了 13 条 golden eval 问题（10 条知识库问答 + 3 条应拒答），评四维：正确率、groundedness、拒答准确率、平均分。微调前后对比结果：〔待实测〕。

**英文版（可用于外企面试）**：

> I ran a QLoRA fine-tuning experiment on Qwen3-14B: 4-bit quantized on a T4 GPU, LoRA rank=32 targeting all Attention + FFN layers, ~0.86% trainable parameters.
>
> For data, I built 45 SFT samples from 4 KB documents (Docker/K8s/Postgres/Redis) using deterministic templates — What/How/Compare patterns per heading, plus 6 refusal samples aligned to the system-level "依据不足" marker. All answers are grounded in source text with explicit citations.
>
> Evaluation: 13 test questions from the golden set (10 KB Q&A + 3 refusals), scored on correctness, groundedness, refusal accuracy, and average. Before vs. after: 〔待实测〕.

---

*回填提醒：实测完成后更新第 2 节训练表、第 4.3 节 eval 表、第 5.2 节 05 模块锚点，并更新第 6 节的 〔待实测〕 数字。*
