# 阶段 5：预训练语言模型时代（1 周）

> **新版路线说明**：这个目录保留 BERT、GPT、T5 等历史材料。默认学习路径中，模型演进已经压缩进 [训练、对齐与微调](../05-training-alignment-finetuning/)，这里只作为深入参考。

> **目标**：了解从 BERT 到 GPT-3 的关键模型演进，理解「预训练+微调」到「预训练+提示」的范式转换。这是连接 Transformer 架构和大模型时代的桥梁。
>
> **你的定位**：你已经在用这些模型的后代（GPT-4、Claude），这里了解它们的「家谱」以及每一代解决了什么问题。

---

## 🗺️ 学习路径指南

```
快速路径（3 天）：
  01 BERT 家族 → 重点理解 MLM 训练、DeBERTa、知识蒸馏
  02 GPT 演进  → ⭐ 重点！GPT-1→2→3 的范式转换
  03 里程碑    → T5 text-to-text 思想 + CLIP 多模态

深入路径（1 周完整）：
  按顺序全部学完，重点理解每个模型"解决了什么新问题"
```

---

## 📂 本阶段内容

| 文件 | 主题 | 面试优先级 | 核心收获 |
|------|------|-----------|---------|
| [01-bert-family.md](./01-bert-family.md) | BERT 家族 | ⭐⭐ | MLM 训练、BERT 家族改进、知识蒸馏 |
| [02-gpt-evolution.md](./02-gpt-evolution.md) | GPT 演进 | ⭐⭐⭐ | GPT-1→2→3、In-Context Learning |
| [03-milestones.md](./03-milestones.md) | 里程碑 & 范式转换 | ⭐⭐ | T5、CLIP、四次范式转换 |

---

## 🎯 本阶段核心脉络

```
2018: BERT + GPT-1 → 预训练+微调范式诞生
2019: GPT-2 → Zero-shot，不用微调也能做任务
      RoBERTa → "BERT 没训练够" → Scaling 的早期信号
2020: GPT-3 (175B) → In-Context Learning，Few-shot 能力涌现
2021: T5 → 统一 text-to-text
      CLIP → 图文对齐，多模态开端

范式转换:
  特征工程+浅层模型 → 预训练+微调(BERT) → 预训练+Prompt(GPT-3) → 预训练+SFT+RLHF(ChatGPT)
```

> **工程师视角**：这一阶段是 LLM 的"家谱"。面试中经常被问到"GPT 和 BERT 有什么区别"、"为什么大模型都是 Decoder-only"、"什么是 In-Context Learning"。这些问题的答案都在这里。理解这段历史能帮你在面试中展现系统性思维。

## 📖 推荐资源

| 资源 | 特点 |
|------|------|
| Jay Alammar: Illustrated BERT/GPT | 图解系列 |
| Lilian Weng Blog | 深度模型演进梳理 |

> ⬅️ [上一阶段：Transformer 架构](../04-transformer-architecture/) | ➡️ [下一阶段：大模型 LLM 核心知识](../06-llm-core/)
