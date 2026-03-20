# Part 1: RAG (检索增强生成) 学习路径

> RAG 是技术基建层，理解它是学习 Agent Memory 的前提。

---

## 一、RAG 是什么

**一句话**: 让 LLM 在生成回答前，先从外部知识源检索相关信息，注入上下文，减少幻觉。

```
用户提问
   ↓
┌──────────────────────────────────────────────┐
│                 RAG Pipeline                  │
│                                              │
│  ① Query → ② Retrieval → ③ Augmentation → ④ Generation │
│             (从知识库检索)   (拼入 Prompt)    (LLM 生成)   │
└──────────────────────────────────────────────┘
   ↓
回答（有据可查）
```

**核心价值**:
- 不用微调就能让 LLM 访问私有/最新知识
- 回答可溯源、可验证
- 比微调节省 60-80% 成本

---

## 二、RAG 核心流程详解

### 2.1 离线阶段：知识库构建 (Indexing)

```
原始文档 → 文档加载 → 分块(Chunking) → 向量化(Embedding) → 存入向量数据库
```

#### 文档加载
- PDF、Markdown、HTML、数据库、API 等
- 工具: LangChain Document Loaders, LlamaIndex Readers, Unstructured

#### 分块策略 (Chunking) — 核心难点之一

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| **固定长度分块** | 按 token/字符数切分 | 最简单，通用 |
| **递归字符分割** | 按段落→句子→字符层级递归切分 | **推荐起点** (400-512 tokens, 10-20% overlap) |
| **语义分块** | 按语义相似度边界切分 | 质量更高，成本更大 |
| **文档结构分块** | 按 Markdown 标题、HTML 标签等结构切分 | 结构化文档 |
| **Agentic Chunking** | 用 LLM 判断分块边界 | 最高质量，最高成本 |

> 研究发现: ~2500 tokens 存在"上下文悬崖"，超过后回答质量明显下降。句子级分块在 5000 tokens 以内效果接近语义分块，但成本低得多。

#### Embedding 模型

| 模型 | 来源 | 特点 |
|------|------|------|
| text-embedding-3-small/large | OpenAI | 最易上手，效果好 |
| bge-large-zh-v1.5 | BAAI (智源) | 中文效果好 |
| jina-embeddings-v3 | Jina AI | 多语言，长文本 |
| Cohere embed-v4 | Cohere | 多模态 embedding |
| GTE / E5 系列 | 阿里/微软 | 开源，可本地部署 |

#### 向量数据库

| 数据库 | 特点 | 适用场景 |
|--------|------|----------|
| **Chroma** | 轻量、嵌入式、Python 原生 | 原型开发、学习 |
| **FAISS** | Facebook 出品、纯库、极快 | 本地大规模检索 |
| **Qdrant** | Rust 实现、性能好、API 友好 | 生产部署 |
| **Milvus** | 分布式、可扩展 | 大规模生产 |
| **Pinecone** | 全托管、零运维 | 快速上线 |
| **pgvector** | PostgreSQL 扩展 | 已有 PG 基础设施 |
| **Weaviate** | 支持混合检索 | 需要关键词+语义混合 |

### 2.2 在线阶段：检索与生成

```
用户 Query → [查询处理] → 向量检索 → [重排序] → 上下文拼接 → LLM 生成
```

---

## 三、进阶 RAG 技术

### 3.1 Naive RAG → Advanced RAG → Modular RAG 演进

```
Naive RAG:     Query → Retrieve → Generate (最简管道)
                        ↓ 问题: 检索不准、上下文噪声

Advanced RAG:  Query Transform → Hybrid Retrieve → Rerank → Generate
                        ↓ 改进: 每个环节优化

Modular RAG:   可插拔模块，按需组合，Agent 调度
                        ↓ 趋势: RAG 成为 "Context Engine"
```

### 3.2 查询优化 (Pre-Retrieval)

| 技术 | 原理 | 效果 |
|------|------|------|
| **Query Rewriting** | LLM 改写用户查询，使其更匹配文档表达 | 提升召回率 |
| **HyDE** | LLM 先生成假设性回答，用回答的 embedding 去检索 | 弥合 query-doc 语义鸿沟 |
| **Sub-question Decomposition** | 将复杂问题拆解为子问题，分别检索 | 处理多跳问题 |
| **Step-back Prompting** | 生成更抽象的问题辅助检索 | 提升泛化能力 |
| **RAG-Fusion** | 生成多个查询变体，合并检索结果 | 提升召回多样性 |

### 3.3 混合检索 (Hybrid Search)

```
              ┌→ 稠密检索 (Dense): Embedding 余弦相似度 → 语义匹配
用户 Query →  │
              └→ 稀疏检索 (Sparse): BM25 / SPLADE      → 关键词匹配
                              ↓
                     RRF (Reciprocal Rank Fusion) 合并排序
```

- **为什么需要混合**: 纯语义检索会漏掉精确术语匹配；纯关键词检索无法理解语义
- 大多数生产系统在 2025 年都采用混合检索

### 3.4 重排序 (Reranking) — 提升精度的关键

| 方法 | 说明 | 代表模型 |
|------|------|----------|
| **Cross-Encoder** | 将 query-doc 对一起输入模型打分，精度最高 | ms-marco-MiniLM, bge-reranker |
| **ColBERT** | 延迟交互，兼顾速度和精度 | ColBERTv2, JaColBERT |
| **LLM Reranking** | 用 LLM 对候选文档排序 | GPT-4、Claude |
| **Cohere Rerank** | API 服务，开箱即用 | Cohere Rerank v3 |

> Databricks 研究: 重排序可提升检索质量最高 48%

### 3.5 上下文增强 (Post-Retrieval)

- **Context Compression**: 压缩检索到的文档，去除无关内容
- **Contextual Retrieval** (Anthropic): 为每个 chunk 添加上下文前缀
- **Parent Document Retrieval**: 检索小块，返回其所在的大块

### 3.6 GraphRAG

```
文档 → 实体/关系抽取 → 知识图谱构建 → 图检索 + 向量检索混合
```

- 微软开源的 [GraphRAG](https://github.com/microsoft/graphrag)
- 适合需要多跳推理、实体关系密集的场景
- 2025 年的重要趋势之一

### 3.7 Agentic RAG

```
用户 Query → Agent 判断 → 是否需要检索？
                            → 检索哪个知识源？
                            → 检索结果够不够？需要再检索吗？
                            → 最终生成回答
```

- Agent 动态决定检索策略，而非固定管道
- 代表: LangGraph ReAct Agent + RAG Tools

---

## 四、RAG 评估

### 4.1 核心指标

| 指标 | 评估什么 | 说明 |
|------|----------|------|
| **Context Precision** | 检索到的文档是否相关 | 检索的准确性 |
| **Context Recall** | 是否检索到了所有需要的信息 | 检索的完整性 |
| **Faithfulness** | 回答是否忠于检索到的上下文 | 是否产生幻觉 |
| **Answer Relevancy** | 回答是否切题 | 生成质量 |
| **MRR / NDCG** | 排序质量 | 好的结果是否排在前面 |

### 4.2 评估工具

| 工具 | 说明 | 链接 |
|------|------|------|
| **RAGAS** | 最流行的 RAG 评估框架，无需标注数据 | [GitHub](https://github.com/explodinggradients/ragas) / [Docs](https://docs.ragas.io/) |
| **LangSmith** | LangChain 配套的可观测性+评估平台 | [langsmith.com](https://smith.langchain.com/) |
| **Langfuse** | 开源 LLM 可观测性平台 | [langfuse.com](https://langfuse.com/) |
| **DeepEval** | 开源 LLM 评估框架 | [GitHub](https://github.com/confident-ai/deepeval) |

---

## 五、动手实践路线

### Level 1: 最简 RAG (1-2天)

```python
# 用 Chroma + OpenAI 实现最简 RAG
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# 1. 分块
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = splitter.split_documents(raw_docs)

# 2. 索引
vectorstore = Chroma.from_documents(docs, OpenAIEmbeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# 3. 生成
prompt = ChatPromptTemplate.from_template(
    "基于以下上下文回答问题:\n{context}\n\n问题: {question}"
)
chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt
    | ChatOpenAI()
)
answer = chain.invoke("什么是 RAG？")
```

### Level 2: Advanced RAG (3-5天)

- 加入 Hybrid Search (BM25 + Dense)
- 加入 Reranker (Cohere 或 bge-reranker)
- 实现 Query Rewriting
- 用 RAGAS 评估效果对比

### Level 3: Production RAG (1-2周)

- 对接生产级向量数据库 (Qdrant/Milvus)
- 实现 Agentic RAG (Agent 动态决定检索策略)
- 可观测性 (Langfuse/LangSmith)
- 评估与持续优化管道

### Level 4: 前沿探索

- GraphRAG 实践
- 多模态 RAG (图片/表格检索)
- 长文本 RAG (128K+ context)

---

## 六、推荐学习资源

### 教程 & 指南
- [RAG 2025 Definitive Guide](https://www.chitika.com/retrieval-augmented-generation-rag-the-definitive-guide-2025/)
- [Advanced RAG: Hybrid Search and Re-ranking (Google Codelabs)](https://codelabs.developers.google.com/codelabs/production-ready-ai-with-gc/8-advanced-rag-methods/advanced-rag-methods)
- [Optimizing RAG with Hybrid Search & Reranking (VectorHub)](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)
- [RAGAS Evaluation with Langfuse](https://langfuse.com/guides/cookbook/evaluation_of_rag_with_ragas)
- [Best Chunking Strategies for RAG 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)

### 论文
- [RAG 原始论文 (Lewis et al., 2020)](https://arxiv.org/abs/2005.11401)
- [RAG 综合综述 2025](https://arxiv.org/html/2506.00054v1)
- [RAGAS 评估框架论文](https://arxiv.org/abs/2309.15217)
- [From RAG to Context — 2025 年终回顾](https://ragflow.io/blog/rag-review-2025-from-rag-to-context)

### 框架 & 工具
- [LangChain](https://github.com/langchain-ai/langchain) — 最全的 RAG 编排框架
- [LlamaIndex](https://github.com/run-llama/llama_index) — 专注检索和索引优化
- [RAGFlow](https://github.com/infiniflow/ragflow) — 开箱即用的 RAG 引擎
- [Microsoft GraphRAG](https://github.com/microsoft/graphrag) — 图增强 RAG

---

## 七、关键概念速查

| 概念 | 一句话解释 |
|------|-----------|
| Embedding | 将文本转为高维向量，语义相似的文本向量距离近 |
| 向量数据库 | 专门存储和检索高维向量的数据库，支持近似最近邻搜索 |
| Chunking | 将长文档切分为适合检索的小块 |
| BM25 | 经典的基于词频的检索算法（稀疏检索） |
| Dense Retrieval | 基于 embedding 相似度的语义检索（稠密检索） |
| Hybrid Search | 结合稀疏+稠密检索 |
| Reranking | 对初次检索结果用更精确的模型重新排序 |
| Cross-Encoder | 将 query 和 doc 一起输入模型计算相关性分数 |
| HyDE | 先让 LLM 生成假设回答，用回答的 embedding 检索 |
| RRF | 合并多路检索结果排序的算法 |
| Faithfulness | 回答是否忠于检索到的证据 |
| GraphRAG | 用知识图谱增强检索，支持多跳推理 |

---

> **学完 Part 1 (RAG)，你掌握了"怎么存、怎么检索、怎么注入上下文"的技术基建。**
> **接下来 Part 2 (Memory) 会在此基础上，讨论"记什么、何时记、怎么组织、何时遗忘"的上层能力。**
