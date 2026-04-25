# 阶段 4：Transformer + 非 Transformer 架构（1.5 周）

> **迁移提示**：新版路线已将 Transformer 的首次学习入口迁到系统学习模块：[04-transformer-foundations](../04-transformer-foundations/)。
>
> 旧版阶段 4 暂时保留作为更宽的参考材料；如果你是第一次系统学习 Transformer，请从 [04-transformer-foundations](../04-transformer-foundations/) 开始，再用 [Transformer 核心面试速记](../09-review-notes/03-transformer-core-cheatsheet.md) 复盘。

> **目标**：深入理解 Transformer 的每个组件，掌握 Attention 变体（MHA→GQA→MLA→Flash Attention），以及 Mamba/SSM 等替代架构。这是面试的核心战场。
>
> **你的定位**：你天天在用 Transformer 模型，这里搞透「它到底怎么工作」以及「有没有替代品」。

---

## 🗺️ 学习路径指南

> **这一阶段是面试重中之重。** Self-Attention 的计算流程几乎是每场 LLM 面试都会问到的。

```
快速路径（4-5 天）：
  01 Transformer 核心 → ⭐⭐⭐ 最重要！必须能白板讲清 Self-Attention
  02 三种范式        → 理解 BERT vs GPT vs T5 的区别
  03 Attention 变体  → GQA 和 Flash Attention 是面试高频

深入路径（1.5 周完整）：
  按顺序全部学完，04 非 Transformer 是面试区分度话题
```

---

## 📂 本阶段内容

| 文件 | 主题 | 面试优先级 | 核心收获 |
|------|------|-----------|---------|
| [01-transformer-core.md](./01-transformer-core.md) | Transformer 核心组件 | ⭐⭐⭐ | Self-Attention 完整流程、Q/K/V、RoPE |
| [02-architecture-paradigms.md](./02-architecture-paradigms.md) | 三种架构范式 | ⭐⭐⭐ | BERT vs GPT vs T5、为什么 Decoder-only 胜出 |
| [03-attention-variants.md](./03-attention-variants.md) | Attention 变体 | ⭐⭐ | MHA→GQA→MLA→Flash Attention |
| [04-non-transformer.md](./04-non-transformer.md) | 非 Transformer 架构 | ⭐ | Mamba/SSM — 面试区分度加分项 |

---

## 🎯 本阶段核心公式

```
Attention(Q, K, V) = softmax(QK^T / √d_k) V

这一行公式是整个大模型时代的基石。用工程师的话说：

  Q (Query):  "我需要什么信息？"（当前 token 的需求）
  K (Key):    "我能提供什么？"  （每个 token 的标签）
  V (Value):  "我的实际内容"    （每个 token 的数据）
  QK^T:       计算需求和供给的匹配度（相似度矩阵）
  √d_k:       防止数值太大导致 softmax 饱和
  softmax:    把匹配度变成权重（和为 1）
  × V:        按权重提取信息
```

> **工程师视角**：把 Attention 想象成一个动态路由器 — 每个 token 根据自己的需求（Q），查看所有 token 的标签（K），然后按匹配度从它们的内容（V）中提取信息。这就是为什么 Transformer 能捕捉任意距离的依赖关系。

## 📖 推荐资源

| 资源 | 特点 |
|------|------|
| [The Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/) | 最佳图解，必看 |
| [3Blue1Brown Transformer 视频](https://www.youtube.com/watch?v=wjZofJX0v4M) | 动画可视化 |
| [Attention is All You Need 原论文](https://arxiv.org/abs/1706.03762) | 经典必读 |
| Mamba 论文 + Albert Gu 讲座 | SSM 深入 |

> ⬅️ [上一阶段：NLP + Embedding & 检索](../03-nlp-embedding-retrieval/) | ➡️ [下一阶段：预训练语言模型](../05-pretrained-models/)
