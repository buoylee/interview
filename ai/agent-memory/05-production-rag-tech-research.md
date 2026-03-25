# 生产级 RAG 系统技术调研（国际主流方案）

> 调研时间：2026-03-23 | 面向 10 人团队

---

## 一、编排框架（Orchestration Framework）

RAG 系统的核心骨架，负责串联分块、检索、生成等各环节。

| 框架 | GitHub Stars | 核心定位 | 优势 | 劣势 | 适合场景 |
|------|-------------|---------|------|------|---------|
| **LlamaIndex** | 39k+ | 数据优先的 RAG 引擎 | 专注检索质量优化；300+ 数据连接器（LlamaHub）；多种索引类型（vector/tree/graph）；2025 年检索准确率提升 35% | Agent 框架不如 LangChain 成熟；API 变动较频繁 | **文档密集型问答、检索质量优先** |
| **LangChain** | 100k+ | 通用 LLM 应用编排 | 生态最大，700+ 集成；LangGraph 支持复杂 Agent 工作流；开发速度快 3x；LangChain 1.0 (2025.10) 解决了稳定性问题 | 抽象层过厚，简单场景 overkill；调试复杂链路困难 | **需要灵活编排、Agent 工作流** |
| **Haystack** (deepset) | 18k+ | 生产优先的管道框架 | 专为生产设计，管道清晰可审计；企业特性（RBAC、语义版本、REST API）；内置 HyDE/Query Expansion；Haystack 2.5 索引速度提升 2x | 快速原型不如 LangChain 快；学习曲线稍陡 | **企业级/受监管行业、可审计管道** |

### 🎯 10 人团队推荐

**LlamaIndex** 是最务实的选择：
- 专注做 RAG 做得最深，而不是试图覆盖所有 LLM 应用场景
- 内置了从解析到评估的端到端工具
- 社区活跃度仅次于 LangChain，文档质量高

如果后续需要 Agent 能力，可以组合 **LlamaIndex（检索层）+ LangGraph（编排层）**。

---

## 二、向量数据库（Vector Database）

存储 embedding 并执行相似度搜索的核心基础设施。

| 数据库 | 语言 | 核心优势 | P95 延迟 (10M 向量) | 规模上限 | 混合搜索 | 部署复杂度 |
|--------|------|---------|-------------------|---------|---------|-----------|
| **Qdrant** | Rust | 极快，过滤能力强，payload 分片 | <10ms | 千万级 | 支持（BM42） | ⭐低（单 Docker 容器） |
| **Weaviate** | Go | **原生混合搜索最强**（BM25 + 向量 + metadata 一次查询） | 20-40ms | 5000 万级  | ⭐⭐⭐原生最强 | ⭐⭐中（Docker/K8s） |
| **Milvus** | Go/C++ | 分布式，十亿级规模 | 15-30ms@100M+ | 十亿级 | 支持 | ⭐⭐⭐高（需 DevOps） |
| **pgvector** | C | 零额外运维（PostgreSQL 扩展） | 视情况 | 5000 万级 | SQL 过滤 + 向量 | ⭐最低 |

### 🎯 10 人团队推荐

**两个方向：**

1. **已有 PostgreSQL** → 用 **pgvector**，零额外运维成本，SQL 直接查
2. **没有 PG / 需要更好的混合搜索** → 用 **Qdrant**（性能最强、部署最轻）或 **Weaviate**（混合搜索最好）

> [!IMPORTANT]
> **不推荐 Milvus**，它是为十亿级规模设计的分布式系统，10 人团队维护成本过高。

---

## 三、Embedding 模型

将文本转为向量的核心模型，直接决定检索质量。

| 模型 | 提供方 | 维度 | 最大 tokens | 多语言 | 开源/API | 特点 |
|------|--------|------|------------|--------|---------|------|
| **text-embedding-3-large** | OpenAI | 3072 (可裁剪) | 8192 | ✓ | API | 通用最强默认选，Matryoshka 维度裁剪省存储 |
| **text-embedding-3-small** | OpenAI | 1536 | 8192 | ✓ | API | 性价比高，速度快 |
| **voyage-3.5** | Voyage AI | 可选 | **32000** | ✓ | API | 超长上下文，有领域专用模型（法律/代码） |
| **Cohere embed-v4** | Cohere | 1024 | 512 | ⭐⭐⭐ | API | 多语言检索 benchmark 最强 |
| **Jina Embeddings v3** | Jina AI | 1024 | 8192 | ✓ | API/本地 | 多语言、长文本、开源可本地部署 |
| **BGE-M3** | BAAI (智源) | 1024 | 8192 | ✓ | 开源本地 | **Dense + Sparse + ColBERT 三合一**，免费，可控 |

### 🎯 10 人团队推荐

- **最快上手**：**OpenAI text-embedding-3-small**（便宜好用，API 调用）
- **最高质量**：**OpenAI text-embedding-3-large** 或 **Voyage AI voyage-3.5**
- **需要本地部署 / 数据安全敏感**：**BGE-M3**（开源，CPU 可跑，且自带稀疏向量做混合检索）
- **长文档多**：**Voyage AI voyage-3.5**（32K 上下文）

---

## 四、Reranker 模型

对粗召回结果精排，通常提升检索质量 **30%-48%**（Databricks 研究数据）。

| 模型 | 提供方 | 类型 | 特点 |
|------|--------|------|------|
| **Cohere Rerank v3** | Cohere | API | 开箱即用，效果好，多语言 |
| **Jina Reranker** | Jina AI | API | 多语言，价格合理 |
| **bge-reranker-v2-m3** | BAAI | 开源/本地 | 多语言 Cross-Encoder，可本地跑 |
| **ms-marco-MiniLM-L-12-v2** | 微软 | 开源/本地 | 经典轻量级，英文 |

### 🎯 10 人团队推荐

- **质量优先**：**Cohere Rerank v3**（API 调用，零维护）
- **成本/隐私优先**：**bge-reranker-v2-m3**（开源，CPU 可跑）

---

## 五、文档解析（Document Parsing）

"Garbage in, garbage out" — 解析质量直接决定 RAG 效果。

| 工具 | 来源 | 核心优势 | 速度 | 开源 | 特点 |
|------|------|---------|------|------|------|
| **Docling** | IBM | layout 分析 + 表格识别（97.9% 准确率）+ 内置 OCR | 快 | ✓ 完全开源 | 集成 LangChain/LlamaIndex，本地运行 |
| **LlamaParse** | LlamaIndex | 专为 RAG 设计，复杂 PDF 处理出色 | ~6s/doc | 有免费额度 | 表格 → Markdown 保持结构，支持自定义解析指令 |
| **Unstructured** | Unstructured.io | 25+ 文件类型，content-aware 分块 | 51-141s/doc | ✓（核心）| ETL 管道，JSON 标准化输出 |
| **Marker** | VikParuchuri | PDF → Markdown 专精 | 快 | ✓ | 轻量，专注做一件事做到极致 |

### 🎯 10 人团队推荐

- **通用推荐**：**Docling**（IBM 出品，完全开源，准确率高，本地运行）
- **PDF 为主 + 用 LlamaIndex**：**LlamaParse**（深度集成，免费额度够小团队用）
- **需要快速轻量**：**Marker**（PDF → Markdown，一步到位）

---

## 六、评估框架（Evaluation）

没有评估 = 盲目调参。

| 工具 | 类型 | 核心功能 | 是否需要标注数据 | 特点 |
|------|------|---------|----------------|------|
| **RAGAS** | 开源框架 | Context Precision/Recall, Faithfulness, Answer Relevancy | 大部分不需要 | **最流行**，LLM 自动评估，与人类判断一致性 70-95% |
| **DeepEval** | 开源框架 | 单元测试风格的 LLM 评估 | 不需要 | 集成 CI/CD，适合自动化测试 |
| **TruLens** | 开源库 | 管道每阶段的 feedback functions 评分 | 不需要 | 与 LangChain/LlamaIndex 深度集成 |

### 🎯 10 人团队推荐

**RAGAS** — 业界标准，`pip install ragas`，几行代码就能跑评估。先把这个搞起来，后续有需要再加 DeepEval 做 CI/CD 集成。

---

## 七、可观测性（Observability）

生产系统必备，debug 和持续优化的基础。

| 平台 | 类型 | 核心功能 | 特点 |
|------|------|---------|------|
| **Langfuse** | 开源/可自部署 | 全链路 Trace、指标、评估、A/B 测试 | **开源首选**，RAG 专用 trace，与 RAGAS 集成 |
| **LangSmith** | SaaS 商业 | 监控、告警、版本对比、调试 | LangChain 生态，功能全但要付费 |
| **Arize Phoenix** | 开源 | LLM 可观测性、评估 | 功能丰富，与各框架集成 |

### 🎯 10 人团队推荐

**Langfuse** — 开源可自部署（Docker），与 RAGAS 天然集成，一个平台搞定 trace + 评估。

---

## 八、推荐技术栈组合

综合以上调研，为 10 人团队推荐的 **国际主流** 技术栈：

```
┌────────────────────────────────────────────────────────┐
│              推荐技术栈（10 人团队）                      │
│                                                        │
│  编排框架:    LlamaIndex                                │
│  文档解析:    Docling (开源) 或 LlamaParse               │
│  Embedding:  OpenAI text-embedding-3-small/large       │
│              或 BGE-M3 (需本地部署时)                    │
│  向量数据库:  Qdrant (推荐) 或 pgvector (已有 PG)        │
│  Reranker:   Cohere Rerank v3 (API)                    │
│              或 bge-reranker-v2-m3 (本地)               │
│  评估:       RAGAS                                     │
│  可观测性:    Langfuse (开源自部署)                       │
└────────────────────────────────────────────────────────┘
```

### 必备基础功能清单

| 优先级 | 功能 | 说明 |
|--------|------|------|
| **P0** | 多格式文档加载 | PDF/Word/Markdown/HTML |
| **P0** | 智能分块 | 递归字符分割，chunk_size 400-512 tokens，10-20% overlap |
| **P0** | 混合检索 | Dense (向量) + Sparse (BM25) + RRF 融合 |
| **P0** | 重排序 | Cross-Encoder 精排 Top-K |
| **P0** | 流式响应 | SSE 流式输出 |
| **P0** | 引用溯源 | 回答标注来源文档和段落 |
| **P1** | Query 改写 | LLM 改写用户 query 提升检索质量 |
| **P1** | 评估管线 | RAGAS 四指标 (Faithfulness, Relevancy, Precision, Recall) |
| **P1** | 可观测性 | Langfuse 追踪全链路 |
| **P1** | 知识库管理 | 上传/删除/更新文档，增量索引 |
| **P1** | 权限隔离 | 多租户数据隔离 |
| **P2** | GraphRAG | 知识图谱增强（复杂场景迭代加入） |
| **P2** | Agentic RAG | Agent 动态选择检索策略 |
| **P2** | 多模态 RAG | 图片/表格检索 |

---

## 九、参考链接

- [LlamaIndex](https://github.com/run-llama/llama_index) — 数据优先的 RAG 引擎
- [LangChain](https://github.com/langchain-ai/langchain) — 通用 LLM 编排
- [Haystack](https://github.com/deepset-ai/haystack) — 生产级管道框架
- [Qdrant](https://github.com/qdrant/qdrant) — Rust 向量数据库
- [Weaviate](https://github.com/weaviate/weaviate) — AI-native 向量数据库
- [Docling](https://github.com/DS4SD/docling) — IBM 文档解析工具
- [RAGAS](https://github.com/explodinggradients/ragas) — RAG 评估框架
- [Langfuse](https://github.com/langfuse/langfuse) — 开源 LLM 可观测性
- [BGE-M3](https://huggingface.co/BAAI/bge-m3) — 多功能开源 Embedding
