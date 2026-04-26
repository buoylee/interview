# AI Engineer 面试路径：RAG 检索增强生成

## 适用场景

- 已理解 LLM 基础调用，需要在面试中解释“模型不知道最新或私有知识”时的工程方案。
- 需要说清 RAG、长上下文、微调和搜索的边界，而不是把所有问题都塞进向量库。
- 这不是零基础学习入口；先有 LLM API、embedding 和检索基本概念，再用本路径冲刺面试。
- 准备 RAG 面试不要求先读 Agent 路径。

## 90 分钟冲刺

| 顺序 | 阅读 | 目标 |
|------|------|------|
| 1 | [RAG Problem Boundary](../01-rag-retrieval-systems/01-rag-problem-boundary.md) | 说清 RAG 解决什么问题，以及不用 RAG 的场景 |
| 2 | [Indexing, Embedding and Retrieval](../01-rag-retrieval-systems/02-indexing-embedding-retrieval.md) | 掌握 chunk、embedding、索引和召回的关键取舍 |
| 3 | [Hybrid Search, Rerank and Context](../01-rag-retrieval-systems/03-hybrid-search-rerank-context.md) | 区分 dense、BM25、hybrid search、rerank 和上下文组装 |
| 4 | [RAG Evaluation and Debugging](../01-rag-retrieval-systems/04-rag-evaluation-debugging.md) | 建立失败定位、评估和防幻觉口径 |
| 5 | [RAG Retrieval Systems Cheatsheet](../09-review-notes/01-rag-retrieval-systems-cheatsheet.md) | 压缩成面试答案 |

## 半天复盘

1. 先读系统学习页，按“问题边界 -> 索引召回 -> 重排组装 -> 评估调试”串起来。
2. 准备一个端到端案例：文档进入索引、查询改写、召回、重排、上下文组装、生成和引用。
3. 给每个环节准备失败模式：切块丢语义、召回缺失、重排错排、上下文冲突、引用不匹配。
4. 最后读 [RAG Retrieval Systems Cheatsheet](../09-review-notes/01-rag-retrieval-systems-cheatsheet.md)，只补口径，不替代系统学习。

## 必答问题

- RAG 解决什么问题，和长上下文、微调、搜索有什么边界？
- Chunk size 和 overlap 怎么选？
- Dense、BM25、Hybrid Search、Rerank 分别解决什么问题？
- Context assembly 如何影响最终回答？
- 如何评估和排查 RAG 失败？
- 如何降低幻觉和 citation mismatch？
- 什么时候不该用 RAG？

## 可跳过内容

- 不深入向量数据库厂商参数、索引底层实现和分布式存储细节。
- 不默认引入 Agent 多步规划；RAG 面试重点是知识接入、检索质量和可验证回答。
- 不背具体 embedding 模型排行榜，重点讲清数据、召回、重排和评估链路。

## 复习笔记

从系统学习页开始，最后用 [RAG Retrieval Systems Cheatsheet](../09-review-notes/01-rag-retrieval-systems-cheatsheet.md) 收口。
