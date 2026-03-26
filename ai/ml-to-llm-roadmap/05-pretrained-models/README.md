# 阶段 5：预训练语言模型时代（1 周）

> **目标**：了解从 BERT 到 GPT-3 的关键模型演进，理解「预训练+微调」到「预训练+提示」的范式转换。这是连接 Transformer 架构和大模型时代的桥梁。
>
> **你的定位**：你已经在用这些模型的后代（GPT-4、Claude），这里了解它们的「家谱」。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-bert-family.md](./01-bert-family.md) | BERT 家族 | Day 1-3 | Embedding 模型、分类任务 |
| [02-gpt-evolution.md](./02-gpt-evolution.md) | GPT 演进 | Day 4-5 | GPT-1→2→3，大模型基础 |
| [03-milestones.md](./03-milestones.md) | 里程碑 & 范式转换 | Day 6-7 | T5、CLIP、自监督学习 |

---

## 🎯 本阶段核心脉络

```
2018: BERT + GPT-1 → 预训练+微调范式诞生
2019: GPT-2 → Zero-shot，不用微调也能做任务
2020: GPT-3 → In-Context Learning，Few-shot 能力涌现
2021: T5 → 统一 text-to-text
      CLIP → 图文对齐，多模态开端

范式转换:
  Pre-train → Fine-tune (BERT时代)
       ↓
  Pre-train → Prompt (GPT-3时代)
       ↓
  Pre-train → SFT → RLHF (ChatGPT时代，阶段6展开)
```

## 📖 推荐资源

| 资源 | 特点 |
|------|------|
| Jay Alammar: Illustrated BERT/GPT | 图解系列 |
| Lilian Weng Blog | 深度模型演进梳理 |

> ⬅️ [上一阶段：Transformer 架构](../04-transformer-architecture/) | ➡️ [下一阶段：大模型 LLM 核心知识](../06-llm-core/)
