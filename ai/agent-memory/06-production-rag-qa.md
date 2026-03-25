# 生产级 RAG 系统 Q&A 答疑

> 基于 05-production-rag-tech-research.md 的 follow-up 讨论整理。

---

## Q1: Memory 是建立在 RAG 上的吗？用的是同一个技术栈吗？

**Memory 的底层存储和检索建立在 RAG 的技术栈上，但多了一整层"智能管理"逻辑。**

```
┌─────────────────────────────────────────────┐
│          Memory 独有的上层能力                │
│  • 自动提取（从对话中判断什么值得记）           │
│  • 去重/更新（覆盖旧记忆还是新增）             │
│  • 反思（从碎片记忆中提炼高阶认知）             │
│  • 遗忘（过期/低价值记忆清理）                  │
│  • 多维检索（recency + relevance + importance）│
├──────────────────────────────────────────────┤
│          共享的底层技术栈（= RAG 技术栈）       │
│  • Embedding 模型、向量数据库、相似度检索       │
│  • 可选：BM25、Reranking                      │
└──────────────────────────────────────────────┘
```

| 维度 | RAG | Memory |
|------|-----|--------|
| 数据来源 | 人工整理的文档 | 从对话中**自动提取** |
| 数据质量 | 高（人工把关） | 需要噪声过滤 |
| 更新方式 | 文档更新时重新索引 | **实时**从对话中提取和更新 |
| 检索维度 | 主要看语义相关性 | 相关性 + 时效性 + 重要性 三维 |
| 生命周期 | 文档在就在 | 创建 → 整合 → 反思 → 遗忘 |

**有专门的 Memory 库**，内部就是用 RAG 技术栈实现的：
- **Mem0** — 最流行，内部用向量 DB + 图 DB + KV 存储
- **Letta** (前 MemGPT) — Agent 自主内存管理，内部用向量 + SQL
- **LangChain/LlamaIndex Memory** — 各框架内置模块，功能较简单

> 结论：如果搭 RAG 系统，不需要单独引入 Memory 库。后续想加"跨会话记忆"能力时，在同一套技术栈上加一层 Mem0 或 Letta 即可。

---

## Q2: LanceDB 和记忆有什么关系？和谁是竞品？

**LanceDB 是一个嵌入式向量数据库**，和 Qdrant、Weaviate、pgvector 是同一层——都是存向量做相似度搜索的。

它出现在 Memory 文档中，是因为某些轻量级 Memory 系统选了它当存储后端。LanceDB 本身和 Memory 没有特殊关系。

**竞品：**
- 直接竞品（嵌入式）：**Chroma**、**sqlite-vec**
- 间接竞品（独立部署型）：**Qdrant**、**pgvector**、**Weaviate**

**LanceDB 独特优势：** 内置 FTS（BM25 全文搜索），一个数据库同时做向量搜索 + 关键词搜索。

> 结论：10 人团队生产级场景不推荐 LanceDB，国际社区采用率和生态成熟度比 Qdrant、Weaviate、pgvector 低一档。

---

## Q3: 混合检索中 BM25 由谁负责？

在推荐方案中：
- **向量搜索** → pgvector（PostgreSQL 扩展）
- **BM25 关键词搜索** → LlamaIndex 内置 `BM25Retriever`（基于 `rank_bm25` Python 库，纯内存）
- **结果合并** → LlamaIndex 的 `QueryFusionRetriever`（RRF 算法）

不需要额外部署 Elasticsearch 等服务。文档量大到 BM25 内存撑不住时，再考虑加 Elasticsearch 或换 Weaviate。

---

## Q4: pgvector vs Qdrant，已有 PostgreSQL 该怎么选？

**已有 PostgreSQL → 直接用 pgvector，不要换 Qdrant。**

| 维度 | pgvector | Qdrant |
|------|---------|--------|
| 搜索延迟 | 50-100ms (百万级) | <10ms |
| 运维成本 | ⭐ 零额外（PG 扩展） | 需要多维护一个 Docker 服务 |
| ACID 事务 | ✅ | ❌ |
| 团队学习成本 | 零 | 需要学新 API |
| 规模上限 | ~5000 万向量 | 更高 |

RAG 的延迟瓶颈在 LLM 生成（几秒），不在向量检索（几十毫秒 vs 几毫秒），**pgvector 的性能对 RAG 场景完全够用**。少引入一个组件，对小团队就是最大的胜利。

---

## Q5: 方案中哪些依赖外部 API？

| 组件 | 依赖外部 API？ | 说明 |
|------|:---:|------|
| LlamaIndex | ❌ | 本地 Python 库 |
| Docling | ❌ | 本地运行 |
| **Embedding (OpenAI)** | ✅ | 调 OpenAI API |
| pgvector | ❌ | 自有 PostgreSQL |
| BM25Retriever | ❌ | 内存计算 |
| **Reranker (Cohere)** | ✅ | 调 Cohere API |
| **LLM (GPT-4/Claude)** | ✅ | 调 OpenAI/Anthropic API |
| **RAGAS** | ✅ | 评估时调 LLM API |
| Langfuse | ❌ | 开源自部署 |

**核心外部 API 依赖 = OpenAI + Cohere（+ 可选 Anthropic）**

**本地替代方案：**

| 外部 API | 本地替代 | 代价 |
|----------|---------|------|
| OpenAI Embedding | BGE-M3（CPU 可跑） | 质量略低但够用 |
| Cohere Rerank | bge-reranker-v2-m3（CPU 可跑） | 质量几乎一样 |
| LLM | Ollama + Qwen2.5/Llama 3 | ⚠️ 需要 GPU，质量差距明显 |

---

## Q6: Reranker 和 RAGAS 是干嘛的？

### Reranker（精排器）— 在线运行，每次请求都走

把检索结果重新排序，让最相关的排到最前面。

```
向量检索从百万文档中粗筛 Top-20  ← HR 看简历，快但粗
Reranker 把 Top-20 精排出 Top-5   ← 面试官深度面试，慢但准
```

效果：检索质量提升 30%-48%。代价：多几百毫秒 + 一次 API 调用。

### RAGAS（评估框架）— 离线运行，开发调优时用

自动给 RAG 系统打分，告诉你效果好不好、哪里有问题。

| 指标 | 评估什么 | 诊断什么问题 |
|------|---------|------------|
| Context Precision | 检索到的文档是否相关 | 噪声太多 → 加 Reranker |
| Context Recall | 是否漏掉关键信息 | 检索不全 → 改分块/加混合检索 |
| Faithfulness | 回答是否忠于检索内容 | LLM 编造 → 改 Prompt |
| Answer Relevancy | 回答是否切题 | 答非所问 → 改 Prompt |

用 LLM 自动评判，不需要人工标注。类似于单元测试——每次改配置后跑一遍看分数变化。

---

## 最终确认的技术栈

```
编排框架:    LlamaIndex
文档解析:    Docling 或 LlamaParse
Embedding:  OpenAI text-embedding-3-small/large
向量数据库:  pgvector（公司已有 PostgreSQL ✅）
BM25 检索:   LlamaIndex 内置 BM25Retriever
Reranker:   Cohere Rerank v3
评估:       RAGAS
可观测性:    Langfuse（开源自部署）
```
