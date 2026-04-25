# 阶段 3：NLP + Embedding & 检索理论（1.5 周）

> **新版路线说明**：这个目录仍保留 NLP、Embedding、检索和旧版生成控制材料。默认学习路径中，生成控制已经迁入 [03-generation-control](../03-generation-control/)；RAG 与检索系统会在后续单独系统化。

> **目标**：理解文本如何变成向量，向量如何用来检索，以及语言模型的生成机制。这是你 RAG/Agent 实战经验的理论根基。
>
> **你的定位**：你已经在用 Embedding + 向量检索 + Reranking，这里搞懂「为什么这样做」和「底层原理是什么」。

> [!NOTE]
> **从阶段 2 过来的衔接说明**：阶段 2 讲的是通用深度学习（MLP→CNN→RNN→Attention），阶段 3 是 **NLP 领域特定知识**。两者是不同维度：阶段 2 是「架构演进」，阶段 3 是「文本怎么表示和处理」。所以这里从 One-Hot 开始讲不是"退步"，而是在 NLP 的维度把基础补齐。阶段 2 的 Attention 知识会在阶段 4 Transformer 中深度展开。

---

## 🗺️ 学习路径指南

```
快速路径（4-5 天）：
  01 文本表示     → 理解演进脉络即可，不需要记公式
  02 Embedding   → ⭐ 重点！RAG 面试必考
  03 检索理论     → ⭐ 重点！BM25 vs Dense + HNSW
  04 语言模型     → 理解 AR vs AE + 解码策略
  06 Tokenization → BPE 面试常问，要会讲流程

深入路径（1.5 周完整）：
  按顺序全部学完，05 受控生成是加分项
```

---

## 📂 本阶段内容

| 文件 | 主题 | 面试优先级 | 核心收获 |
|------|------|-----------|---------|
| [01-text-representation.md](./01-text-representation.md) | 文本表示演进 | ⭐⭐ | One-Hot → Word2Vec → BERT 的脉络 |
| [02-embedding-theory.md](./02-embedding-theory.md) | Embedding 深度理论 | ⭐⭐⭐ | RAG 的 Embedding 底层原理 |
| [03-retrieval-theory.md](./03-retrieval-theory.md) | 检索理论 | ⭐⭐⭐ | BM25、HNSW、Hybrid Search |
| [04-language-model-decoding.md](./04-language-model-decoding.md) | 语言模型 & 解码 | ⭐⭐⭐ | AR vs AE、Top-p/Temperature |
| [05-controlled-generation.md](./05-controlled-generation.md) | 受控生成 & 结构化输出 | ⭐⭐ | JSON Mode、Function Calling |
| [06-tokenization-deep-dive.md](./06-tokenization-deep-dive.md) | Tokenization 算法 | ⭐⭐⭐ | BPE 面试核心，常要求讲流程 |

---

## 🎯 本阶段核心脉络

```
文本如何表示？
  One-Hot → BoW/TF-IDF → Word2Vec → ELMo → BERT/GPT
    稀疏       统计        静态向量    上下文    预训练

Embedding 如何训练？
  Word2Vec(Skip-gram) → 对比学习(InfoNCE) → Sentence-BERT

如何用 Embedding 检索？
  BM25(稀疏) + Dense Retrieval(稠密) → Hybrid Search → Reranking

如何生成文本？
  自回归 P(next|context) → Greedy/Beam/Top-k/Top-p/Temperature

如何控制输出？
  Prompt约束 → 解码约束(Constrained Decoding) → 微调约束(Function Calling)
```

> **工程师视角**：这一阶段是离你日常工作最近的理论。你调 Embedding 模型、选向量数据库、调 Temperature 参数、用 Function Calling — 这里讲的就是这些东西背后的原理。面试官最爱问的也是这些。

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| Jay Alammar 博客 | Word2Vec, Transformer 等可视化 | 图解系列 |
| Lilian Weng Blog | Embedding, 检索, 生成 | 深度技术博客 |
| Sentence-BERT 论文 | Embedding 模型训练 | 必读 |

> ⬅️ [上一阶段：深度学习基础](../02-deep-learning/) | ➡️ [下一阶段：Transformer + 非 Transformer 架构](../04-transformer-architecture/)
