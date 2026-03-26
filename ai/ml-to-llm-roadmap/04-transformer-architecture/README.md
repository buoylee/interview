# 阶段 4：Transformer + 非 Transformer 架构（1.5 周）

> **目标**：深入理解 Transformer 的每个组件，掌握 Attention 变体（MHA→GQA→MLA→Flash Attention），以及 Mamba/SSM 等替代架构。这是面试的核心战场。
>
> **你的定位**：你天天在用 Transformer 模型，这里搞透「它到底怎么工作」以及「有没有替代品」。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-transformer-core.md](./01-transformer-core.md) | Transformer 核心组件 | Day 1-3 | ⭐ 面试必考，整个 LLM 的基础 |
| [02-architecture-paradigms.md](./02-architecture-paradigms.md) | 三种架构范式 | Day 4 | Encoder-only/Decoder-only/Enc-Dec |
| [03-attention-variants.md](./03-attention-variants.md) | Attention 变体 | Day 5-6 | MHA→MQA→GQA→MLA→Flash Attention |
| [04-non-transformer.md](./04-non-transformer.md) | 非 Transformer 架构 | Day 7-10 | Mamba/SSM/RWKV → 面试区分度 |

---

## 🎯 本阶段核心公式

```
Attention(Q, K, V) = softmax(QK^T / √d_k) V

这一行公式是整个大模型时代的基石。理解它的每个部分：
  Q (Query):  我在找什么？
  K (Key):    每个位置有什么？
  V (Value):  每个位置的实际内容
  QK^T:       相似度矩阵
  √d_k:       归一化（防止值太大）
  softmax:    变成概率（权重和=1）
  × V:        加权求和
```

## 📖 推荐资源

| 资源 | 特点 |
|------|------|
| [The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/) | 最佳图解 |
| [3Blue1Brown Transformer 视频](https://www.youtube.com/watch?v=wjZofJX0v4M) | 动画可视化 |
| [Attention is All You Need 原论文](https://arxiv.org/abs/1706.03762) | 经典必读 |
| Mamba 论文 + Albert Gu 讲座 | SSM 深入 |

> ⬅️ [上一阶段：NLP + Embedding & 检索](../03-nlp-embedding-retrieval/) | ➡️ [下一阶段：预训练语言模型](../05-pretrained-models/)
