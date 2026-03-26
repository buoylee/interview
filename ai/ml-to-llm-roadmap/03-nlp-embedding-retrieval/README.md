# 阶段 3：NLP + Embedding & 检索理论（1.5 周）

> **目标**：理解文本如何变成向量，向量如何用来检索，以及语言模型的生成机制。这是你 RAG/Agent 实战经验的理论根基。
>
> **你的定位**：你已经在用 Embedding + 向量检索 + Reranking，这里搞懂「为什么这样做」和「底层原理是什么」。

> [!NOTE]
> **从阶段 2 过来的衔接说明**：阶段 2 讲的是通用深度学习（MLP→CNN→RNN→Attention），阶段 3 是 **NLP 领域特定知识**。两者是不同维度：阶段 2 是「架构演进」，阶段 3 是「文本怎么表示和处理」。所以这里从 One-Hot 开始讲不是"退步"，而是在 NLP 的维度把基础补齐。阶段 2 的 Attention 知识会在阶段 4 Transformer 中深度展开。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-text-representation.md](./01-text-representation.md) | 文本表示演进 | Day 1-2 | 从 One-Hot 到 BERT 的完整脉络 |
| [02-embedding-theory.md](./02-embedding-theory.md) | Embedding 深度理论 | Day 3-4 | ⭐ RAG 的 Embedding 底层原理 |
| [03-retrieval-theory.md](./03-retrieval-theory.md) | 检索理论 | Day 5-6 | ⭐ RAG 的检索底层原理 |
| [04-language-model-decoding.md](./04-language-model-decoding.md) | 语言模型 & 解码 | Day 7-8 | LLM 生成机制 |
| [05-controlled-generation.md](./05-controlled-generation.md) | 受控生成 & 结构化输出 | Day 9-10 | Function Calling、JSON Mode |
| [06-tokenization-deep-dive.md](./06-tokenization-deep-dive.md) | Tokenization 算法深度解析 | Day 11 | ⭐ BPE/WordPiece/Unigram 面试核心 |

---

## 🎯 本阶段核心脉络

```
文本如何表示？
  One-Hot → BoW/TF-IDF → Word2Vec → ELMo → BERT/GPT
    稀疏       统计        静态向量    上下文    预训练

Embedding 如何训练？
  Word2Vec(Skip-gram) → 对比学习(InfoNCE) → Sentence-BERT

如何用 Embedding 检索？
  BM25(稀疏) + Dense Retrieval(稠密) → Hybrid Search

如何生成文本？
  自回归 P(next|context) → Greedy/Beam/Top-k/Top-p/Temperature

如何控制输出？
  Prompt约束 → 解码约束(Constrained Decoding) → 微调约束(Function Calling)

Tokenization 算法？
  BPE(频率合并) / WordPiece(似然合并) / Unigram(删减) / Byte-level BPE(字节级)
```

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| Jay Alammar 博客 | Word2Vec, Transformer 等可视化 | 图解系列 |
| Lilian Weng Blog | Embedding, 检索, 生成 | 深度技术博客 |
| Sentence-BERT 论文 | Embedding 模型训练 | 必读 |

> ⬅️ [上一阶段：深度学习基础](../02-deep-learning/) | ➡️ [下一阶段：Transformer + 非 Transformer 架构](../04-transformer-architecture/)
