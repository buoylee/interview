# Advanced RAG 理论篇：从能用到好用

> 前置知识：你已了解向量数据库、Embedding、分块、重叠。
> 本篇目标：搞懂 Naive RAG 的问题在哪，以及 4 个关键改进技术的原理。

---

## 一、先看清 Naive RAG 的问题

你现在掌握的 Naive RAG 流程：

```
用户问题 → Embedding → 向量数据库 Top-K → 塞进 Prompt → LLM 回答
```

这个流程能跑通，但在实际使用中会碰到几类典型问题：

| 问题 | 举例 | 根因 |
|------|------|------|
| **精确匹配失败** | 搜 "pgvector 配置" 返回 "Milvus 配置" | 向量检索只看语义相似，不看关键词精确匹配 |
| **排序不够好** | 最相关的文档排在第 4 位而不是第 1 位 | Embedding 的相似度是粗排，精度有限 |
| **Query 和文档形式不匹配** | 用户问"为什么报错"，但文档里写的是"错误原因及解决方案" | 问题和答案的表达方式不同，embedding 距离远 |
| **无法量化好坏** | 改了分块策略，不知道效果是变好还是变差 | 缺乏评估体系 |

Advanced RAG 就是针对这些问题，在检索管道的不同环节加上改进：

```
用户问题
   ↓
┌─────────────────── Advanced RAG ───────────────────┐
│                                                    │
│  ① Query 改写 ←── 解决 "query 和文档形式不匹配"      │
│       ↓                                            │
│  ② 混合检索   ←── 解决 "精确匹配失败"                │
│       ↓                                            │
│  ③ 重排序     ←── 解决 "排序不够好"                  │
│       ↓                                            │
│  ④ 评估       ←── 解决 "无法量化好坏"                │
│       ↓                                            │
│  Top-K → Prompt → LLM 回答                         │
└────────────────────────────────────────────────────┘
```

下面逐一讲清楚。

---

## 二、混合检索 (Hybrid Search)

### 2.1 为什么需要？

先理解两种检索方式的本质差异：

**稠密检索 (Dense Retrieval)** — 你已经会的向量检索
```
"如何配置 PostgreSQL" → [0.12, -0.34, 0.78, ...] → 余弦相似度

优点: 理解语义 — "如何设置数据库" 也能匹配到
缺点: 可能忽略精确词 — "PostgreSQL" 和 "MySQL" 的向量可能很近
```

**稀疏检索 (Sparse Retrieval)** — 传统关键词检索（BM25）
```
"如何配置 PostgreSQL" → 看文档里有没有 "配置" 和 "PostgreSQL" 这些词

优点: 精确匹配 — 有 "PostgreSQL" 就是有，没有就是没有
缺点: 不理解语义 — "数据库设置" 匹配不到 "PostgreSQL 配置"
```

**混合检索: 两者互补**
```
              ┌→ 稠密检索: "配置数据库" 也能找到 (语义理解) ───┐
"如何配置       │                                              ├→ 合并
 PostgreSQL" ──┤                                              │
              └→ 稀疏检索: 精确命中 "PostgreSQL" 关键词 ────────┘
```

### 2.2 BM25 是什么？一句话搞懂

BM25 是稀疏检索最常用的算法。它的核心思想非常直觉：

> **一个词越稀有、在文档中出现越多次、文档越短 → 这个文档越相关**

三个要素：

| 要素 | 直觉 | 例子 |
|------|------|------|
| **词的稀有度 (IDF)** | 越少见的词越有区分度 | "PostgreSQL" 比 "如何" 有价值得多 |
| **词频 (TF) + 饱和** | 出现越多越相关，但有上限 | 出现 3 次 vs 1 次有区别，30 次 vs 28 次几乎没区别 |
| **文档长度归一化** | 短文档中出现 1 次 > 长文档中出现 1 次 | 一条推文提到 1 次 > 300 页文档提到 1 次 |

公式你可以不记，记住这个直觉就够了。

### 2.3 RRF：怎么把两路结果合并？

问题来了：稠密检索返回一个排序列表，稀疏检索也返回一个排序列表，怎么合成一个？

**Reciprocal Rank Fusion (RRF)** — 一种简单有效的合并方法：

> **核心思想: 不看分数，只看排名。排名靠前的文档得分高，在多个列表中都靠前的文档得分更高。**

```
稠密检索结果:              稀疏检索结果:
1. 文档A (相似度 0.92)     1. 文档C (BM25: 8.5)
2. 文档B (相似度 0.87)     2. 文档A (BM25: 7.2)
3. 文档C (相似度 0.85)     3. 文档D (BM25: 6.1)
4. 文档D (相似度 0.80)     4. 文档B (BM25: 5.8)
```

RRF 计算（忽略原始分数，只用排名）：

```
RRF(文档) = Σ  1 / (k + rank_i)     (k 通常取 60)

文档A: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325  ← 两边都靠前，最高
文档C: 1/(60+3) + 1/(60+1) = 0.0159 + 0.0164 = 0.0323
文档B: 1/(60+2) + 1/(60+4) = 0.0161 + 0.0156 = 0.0317
文档D: 1/(60+4) + 1/(60+3) = 0.0156 + 0.0159 = 0.0315

最终排序: A > C > B > D
```

**为什么不直接合并分数？** 因为两路检索的分数量级完全不同（余弦相似度是 0~1，BM25 可能是 0~20），没法直接比。RRF 只看排名，巧妙回避了这个问题。

### 2.4 小结

```
混合检索 = BM25 (关键词精确匹配) + Dense Retrieval (语义理解) + RRF (合并排序)
```

解决了: 纯向量检索的精确匹配失败问题。

---

## 三、重排序 (Reranking)

### 3.1 为什么需要？

混合检索返回了 Top-20 候选文档，但排序仍然不够精确。原因是：

**Bi-Encoder（你用的 Embedding 模型）的工作方式：**

```
Query:    "如何配置 PostgreSQL"  →  [向量Q]  ─┐
                                              ├→ 余弦相似度 = 0.87
Document: "PostgreSQL 配置指南"  →  [向量D]  ─┘

问题: Query 和 Document 是分别编码的！
      编码 Document 时，模型不知道 Query 是什么。
      所有语义信息被压缩到一个固定长度的向量里，信息损失大。
```

**Cross-Encoder（重排序模型）的工作方式：**

```
["如何配置 PostgreSQL", "PostgreSQL 配置指南"]
                    ↓
        一起输入 Transformer
     Query 和 Document 的每个 token 互相注意
                    ↓
              相关性分数 = 0.95
```

### 3.2 Bi-Encoder vs Cross-Encoder 对比

把这两个角色想象成**招聘流程**：

```
Bi-Encoder = HR 初筛
  - 看简历关键词匹配度，快速筛掉明显不合适的
  - 速度快，但可能误判
  - 可以同时处理 100 万份简历

Cross-Encoder = 面试官深度面试
  - 把候选人和岗位需求放一起仔细对比
  - 准确度高，但很慢
  - 一次只能面一个人
```

| 维度 | Bi-Encoder (初筛) | Cross-Encoder (精排) |
|------|-------------------|---------------------|
| 输入 | Query 和 Doc **分别**编码 | Query 和 Doc **一起**编码 |
| 速度 | 快（编码一次，检索用近似最近邻） | 慢（每对 query-doc 都要过一次模型） |
| 精度 | 较好 | 更好 |
| 适用 | 从百万文档中召回 Top-100 | 从 Top-100 中精排出 Top-5 |

### 3.3 两阶段检索架构

这就是生产环境的标准做法：

```
百万文档
   ↓
第一阶段: Bi-Encoder 粗召回 Top-100 (毫秒级)
   ↓
第二阶段: Cross-Encoder 精排 → Top-5 (百毫秒级)
   ↓
送入 LLM 生成回答
```

为什么不直接用 Cross-Encoder？因为对 100 万文档逐一做 Cross-Encoder 可能要跑几个小时。所以先用快的 Bi-Encoder 粗筛，再用慢但准的 Cross-Encoder 精排。

### 3.4 常见重排序模型

| 模型 | 说明 |
|------|------|
| `bge-reranker-v2-m3` | BAAI 出品，多语言，开源，可本地跑 |
| `ms-marco-MiniLM-L-12-v2` | 经典轻量 Cross-Encoder |
| Cohere Rerank v3 | API 服务，开箱即用，效果好 |
| Jina Reranker | API 服务，支持多语言 |

### 3.5 小结

```
重排序 = 用 Cross-Encoder 对粗召回结果做精排
效果: 检索质量提升最高 48%（Databricks 研究数据）
代价: 增加几百毫秒延迟
```

---

## 四、Query 改写 (Query Transformation)

### 4.1 为什么需要？

用户的提问方式和文档的表达方式之间存在"鸿沟"：

```
用户问:     "为什么我的服务挂了"        ← 口语化、模糊
文档里写:   "服务异常的常见原因及排查步骤" ← 规范化、具体

这两句话在向量空间里可能距离不近！
```

### 4.2 三种主要技术

#### 技术一: Query Rewriting（最实用）

```
用户原始问题: "为什么我的服务挂了"
       ↓ LLM 改写
改写后:       "服务崩溃 故障排查 常见错误原因 异常处理"
       ↓
用改写后的 query 去检索
```

原理简单直接: 让 LLM 把用户的口语化表达改写成更匹配文档风格的 query。

#### 技术二: HyDE（Hypothetical Document Embeddings）

这个方法更巧妙:

```
用户问题: "为什么我的服务挂了"
       ↓
LLM 先生成一个"假设性回答"（不需要准确）:
"服务崩溃的常见原因包括: 1. 内存溢出 OOM  2. 数据库连接池耗尽
 3. 网络超时  4. 配置错误导致的启动失败..."
       ↓
对这个"假回答"做 Embedding
       ↓
用"假回答"的向量去检索真文档
```

**为什么有效？**

核心洞察: **数据库里存的是"答案"，不是"问题"**。

```
问题 vs 文档 = 不同形式，向量可能不近
假回答 vs 文档 = 相同形式（都是答案），向量更近！
```

假回答哪怕不准确也没关系，因为它在 embedding 空间里和真正的文档更"像"。

#### 技术三: Sub-question Decomposition（子问题分解）

处理复杂的多跳问题:

```
原始问题: "比较 PostgreSQL 和 MySQL 在高并发场景下的性能差异"
       ↓ LLM 分解
子问题1: "PostgreSQL 高并发性能特点"  → 分别检索
子问题2: "MySQL 高并发性能特点"       → 分别检索
子问题3: "PostgreSQL vs MySQL 基准测试" → 分别检索
       ↓
合并所有检索结果 → LLM 综合回答
```

### 4.3 三种技术对比

| 技术 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| Query Rewriting | LLM 改写 query | 简单，通用 | 依赖 LLM 改写质量 | 通用场景 |
| HyDE | 用假设性回答的向量检索 | 弥合问答形式鸿沟 | 多一次 LLM 调用 | 问答形式差距大 |
| Sub-question | 拆解复杂问题分别检索 | 解决多跳问题 | 延迟高，多次检索 | 复杂/对比类问题 |

### 4.4 小结

```
Query 改写 = 让检索 query 更"像"文档的表达方式
不改文档，不改检索器，只改 query —— 投入产出比最高的优化之一
```

---

## 五、RAG 评估 (Evaluation)

### 5.1 为什么需要？

没有评估，一切优化都是"凭感觉"：
- 改了分块大小，效果变好还是变差？
- 加了 Reranker，到底提升了多少？
- 换了 Embedding 模型，值得吗？

### 5.2 评估什么？两个层面

```
┌──────────────────────────────────────────────────────┐
│                    RAG 评估                           │
│                                                      │
│   检索质量 (Retrieval)         生成质量 (Generation)   │
│   "找到的对不对？全不全？"      "回答得好不好？"         │
│                                                      │
│   ┌─────────────────────┐    ┌─────────────────────┐ │
│   │ Context Precision   │    │ Faithfulness         │ │
│   │ Context Recall      │    │ Answer Relevancy     │ │
│   └─────────────────────┘    └─────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 5.3 四个核心指标详解

#### 指标 1: Context Precision（上下文精度）

> 检索到的文档中，有多少是真正相关的？

```
检索到 5 个文档: [相关, 不相关, 相关, 不相关, 不相关]

Precision = 相关文档数 / 检索总数 = 2/5 = 0.4

问题诊断: 检索到了太多无关文档，噪声大
```

但 Context Precision 不只看比例，还看**排序** — 相关文档排在前面比排在后面得分更高。

#### 指标 2: Context Recall（上下文召回率）

> 所有应该被检索到的信息，实际找到了多少？

```
正确答案需要 3 个要点: [A, B, C]
检索到的文档覆盖了:    [A, B]    缺少 C

Recall = 2/3 = 0.67

问题诊断: 有关键信息没被检索到
```

注意: 这是唯一一个需要标注数据（ground truth）的指标。

#### 指标 3: Faithfulness（忠实度）

> LLM 的回答是否忠于检索到的内容？有没有编造？

```
检索到的上下文: "PostgreSQL 默认端口是 5432"
LLM 回答:       "PostgreSQL 默认端口是 5432，且支持最多 100 个并发连接"
                                                 ↑ 这条信息不在上下文里！

评估方式:
1. 将回答拆解为独立的声明 (claims)
2. 逐条检查每个声明是否有上下文支持

Faithfulness = 有支持的声明数 / 总声明数 = 1/2 = 0.5

问题诊断: LLM 产生了幻觉
```

#### 指标 4: Answer Relevancy（回答相关度）

> 回答是否切题？有没有答非所问？

```
问题: "PostgreSQL 的默认端口是多少？"

回答A: "PostgreSQL 的默认端口是 5432。"               → 高相关度
回答B: "PostgreSQL 是一个强大的开源数据库系统，        → 低相关度
        它支持 SQL 标准...默认端口是 5432。"             (虽然包含答案，但废话太多)
```

### 5.4 四个指标的关系和用途

```
你发现 RAG 效果不好，怎么定位问题？

Faithfulness 低   → LLM 在编造，需要改 Prompt 或换模型
Relevancy 低     → LLM 答非所问，需要改 Prompt
Precision 低     → 检索到太多噪声，需要改检索策略（加 Reranker）
Recall 低        → 漏掉了关键信息，需要改分块/改 Embedding/加混合检索
```

### 5.5 RAGAS 评估框架

[RAGAS](https://docs.ragas.io/) 是最流行的 RAG 评估框架，核心特点：

- **无需人工标注**（大部分指标）: 用 LLM 自动评估，和人类评判一致性达 70-95%
- **开箱即用**: `pip install ragas`，几行代码就能跑评估
- **可集成**: 可以嵌入 CI/CD，每次改动自动跑评估

### 5.6 小结

```
评估 = 让你用数据说话，而不是凭感觉调参
四个指标分两层: 检索层 (Precision + Recall) + 生成层 (Faithfulness + Relevancy)
工具: RAGAS 框架
```

---

## 六、技术全景图

```
                        Advanced RAG 全景
                        ================

                    ┌─── Pre-Retrieval ───┐
                    │  Query Rewriting     │
                    │  HyDE                │
                    │  Sub-question        │
                    └─────────┬───────────┘
                              ↓
              ┌────────── Retrieval ──────────┐
              │                               │
              │  ┌─ Dense (Embedding向量) ──┐ │
              │  │                          │ │
              │  └──── RRF 合并 ────────────┘ │
              │  ┌─ Sparse (BM25关键词)  ──┐ │
              │  │                          │ │
              │  └──────────────────────────┘ │
              └───────────┬───────────────────┘
                          ↓
                 ┌─ Post-Retrieval ──┐
                 │  Reranking        │
                 │  (Cross-Encoder)  │
                 └────────┬──────────┘
                          ↓
                 ┌── Generation ───┐
                 │  LLM 生成回答    │
                 └────────┬────────┘
                          ↓
                 ┌── Evaluation ───┐
                 │  RAGAS 评估      │
                 │  Precision       │
                 │  Recall          │
                 │  Faithfulness    │
                 │  Relevancy       │
                 └─────────────────┘
```

---

## 七、推荐阅读顺序

按照本文的理解基础，继续深入的阅读顺序：

### 第一步：巩固混合检索 + 重排序
1. [Hybrid Search Explained (Weaviate)](https://weaviate.io/blog/hybrid-search-explained) — 图文并茂，讲得最清楚
2. [Rerankers and Two-Stage Retrieval (Pinecone)](https://www.pinecone.io/learn/series/rag/rerankers/) — Bi-Encoder vs Cross-Encoder 的最佳科普
3. [Optimizing RAG with Hybrid Search & Reranking (VectorHub)](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking) — 完整实践指南

### 第二步：理解 Query 改写
4. [HyDE 论文](https://arxiv.org/abs/2212.10496) — 原始论文，不长
5. [Advanced RAG — HyDE (AI Planet)](https://medium.aiplanet.com/advanced-rag-improving-retrieval-using-hypothetical-document-embeddings-hyde-1421a8ec075a) — HyDE 通俗讲解
6. [Better RAG with HyDE (Zilliz)](https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings) — 带代码的教程

### 第三步：搞懂评估
7. [Evaluating RAG Applications with RAGAS (Leonie Monigatti)](https://medium.com/data-science/evaluating-rag-applications-with-ragas-81d67b0ee31a) — 最好的 RAGAS 入门文章
8. [RAG Evaluation Metrics (Confident AI)](https://www.confident-ai.com/blog/rag-evaluation-metrics-answer-relevancy-faithfulness-and-more) — 指标详解
9. [RAGAS 官方文档](https://docs.ragas.io/) — 指标定义和用法

### 第四步：综合提升
10. [RAG 2025 Definitive Guide](https://www.chitika.com/retrieval-augmented-generation-rag-the-definitive-guide-2025/) — 全景综述
11. [From RAG to Context — 2025 年终回顾](https://ragflow.io/blog/rag-review-2025-from-rag-to-context) — RAG 最新演进方向
12. [Search Reranking with Cross-Encoders (OpenAI Cookbook)](https://cookbook.openai.com/examples/search_reranking_with_cross-encoders) — OpenAI 官方教程
