# 阶段 6：大模型 LLM 核心知识（3 周）

> **目标**：这是整个路线图的核心阶段，覆盖 LLM 的训练、对齐、推理优化、微调、MoE、多模态等全部关键知识。面试 Top 25 中超过一半的题目在这里。
>
> **你的定位**：你已有应用经验，这里补齐大模型「怎么训出来的」和「怎么优化部署的」底层知识。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 面试频率 |
|------|------|---------|---------|
| [01-training-pipeline.md](./01-training-pipeline.md) | 训练三阶段 + RL 基础 | Day 1-4 | ⭐⭐⭐⭐⭐ |
| [02-alignment.md](./02-alignment.md) | 对齐技术 RLHF→DPO→GRPO | Day 5-6 | ⭐⭐⭐⭐⭐ |
| [03-scaling-law.md](./03-scaling-law.md) | Scaling Law & 涌现能力 | Day 7 | ⭐⭐⭐⭐ |
| [04-distributed-training.md](./04-distributed-training.md) | 分布式训练 DP/TP/PP/ZeRO | Day 8-9 | ⭐⭐⭐⭐ |
| [05-inference-optimization.md](./05-inference-optimization.md) | 推理优化 & 长上下文 | Day 10-11 | ⭐⭐⭐⭐⭐ |
| [06-fine-tuning-distillation.md](./06-fine-tuning-distillation.md) | 微调(LoRA) + 知识蒸馏 + 模型合并 | Day 12-13 | ⭐⭐⭐⭐⭐ |
| [07-moe.md](./07-moe.md) | MoE 混合专家 | Day 14 | ⭐⭐⭐⭐ |
| [08-advanced-topics.md](./08-advanced-topics.md) | 推理模型 + 多模态 + Code LLM | Day 15-17 | ⭐⭐⭐⭐ |
| [09-data-evaluation.md](./09-data-evaluation.md) | 数据工程 + LLM 评估 | Day 18-19 | ⭐⭐⭐ |
| [10-safety-hallucination.md](./10-safety-hallucination.md) | AI 安全 + 幻觉 | Day 20 | ⭐⭐⭐ |
| [11-model-families.md](./11-model-families.md) | 关键模型族总览 | Day 21 | ⭐⭐⭐ |
| [12-test-time-compute.md](./12-test-time-compute.md) | Test-time Compute Scaling | Day 22 | ⭐⭐⭐⭐ |
| [13-long-context.md](./13-long-context.md) | 长上下文技术 | Day 23 | ⭐⭐⭐⭐ |
| [14-llm-as-judge.md](./14-llm-as-judge.md) | LLM-as-Judge 评估 | Day 24 | ⭐⭐⭐ |
| [15-edge-deployment.md](./15-edge-deployment.md) | 端侧/小模型部署 | Day 25 | ⭐⭐⭐ |

---

## 🎯 本阶段核心主线

```
怎么训出来的？
  预训练(PT) → 监督微调(SFT) → 人类对齐(RLHF/DPO)

怎么变快/变小？
  量化 / KV-Cache / Flash Attention / 推测解码 / vLLM

怎么适配我的任务？
  LoRA / QLoRA / 知识蒸馏 / 模型合并

前沿方向？
  MoE / 推理模型(o1) / 多模态 / 长上下文

推理时怎么更好？
  Test-time Compute Scaling / Long CoT / Best-of-N / Tree Search

怎么评估？
  传统 Benchmark + LLM-as-Judge + Chatbot Arena

怎么在端侧跑？
  量化(INT4) + 剪枝 + 蒸馏 → llama.cpp / GGUF
```

## 📖 推荐资源

| 资源 | 特点 |
|------|------|
| Lilian Weng Blog | LLM 训练、对齐、推理优化 |
| 李宏毅 B 站 | 中文系统讲解 |
| Hugging Face Blog | 实践向 |

> ⬅️ [上一阶段：预训练语言模型](../05-pretrained-models/) | ➡️ [下一阶段：理论-应用桥接](../07-theory-practice-bridge/)
