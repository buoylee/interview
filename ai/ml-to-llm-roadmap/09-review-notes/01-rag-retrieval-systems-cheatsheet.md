# RAG 与检索系统 面试速记

> 这份笔记用于复习，不适合作为第一次学习入口。第一次学习先读 [RAG 与检索系统](../01-rag-retrieval-systems/)。

## 30 秒答案

RAG 解决的是外部知识接入和 grounding：把动态、私有、需要引用的知识先检索出来，再放进上下文让模型基于证据回答。链路上先做文档解析、chunk、metadata、embedding 和索引，查询时用 dense、sparse 或 hybrid search 召回候选，再 rerank、去重、压缩和组装上下文。上线时要分开评估 retrieval 和 answer，排查 no hit、wrong hit、partial hit、stale document、unsupported answer 和 citation mismatch；有引用不等于可靠，答案主张必须被上下文支持。

## 2 分钟展开

RAG 的边界不是“让模型记住更多”，而是在回答前把可验证的外部证据放进上下文。长上下文适合单次阅读大量已知材料，微调适合改变输出风格、格式和任务习惯；动态事实、权限知识和需要引用的企业文档更适合 RAG。RAG 也不是 Agent，它不要求模型自主规划多步行动，只要求检索证据、组装上下文并基于证据回答。

索引阶段决定检索上限。Chunk 太短会丢条件、例外和定义，太长会混入噪声并浪费 prompt；metadata 用来表达部门、日期、产品和权限，避免语义相似但不该返回的片段进入候选。Dense retrieval 擅长语义改写，sparse retrieval/BM25 擅长专有名词、编号和精确术语；hybrid search 用两类信号互补，reranker 再在少量候选里判断哪个片段真正能回答问题。

Context assembly 不是简单取 top-k。它要去重、压缩、排序、保留 source tracking，并控制上下文长度和证据位置，降低噪声、lost-in-the-middle 和引用错配。评估时先看正确证据是否进入候选和靠前位置，再看最终答案是否正确、忠实、相关、引用准确。Correctness 看真实业务事实，faithfulness 看答案是否被当前上下文支持，两者都要看。

## 高频追问

| 追问 | 回答 |
|------|------|
| RAG、长上下文、微调怎么取舍？ | RAG 接入动态、私有、需引用的外部知识；长上下文处理单次已知材料；微调改变风格、格式和任务适配，不适合频繁更新事实。 |
| Chunk size 怎么选？ | 目标是保留语义完整边界。太短会丢条件和例外，太长会引入噪声并挤占 prompt；用代表性问题和失败样本调 chunk、overlap 和 metadata。 |
| 为什么需要 hybrid search 和 rerank？ | BM25 抓精确词和编号，dense 抓语义改写；hybrid 提高召回稳健性，rerank 在少量候选里重新判断相关性和可回答性。 |
| 如何区分 retrieval failure 和 generation failure？ | 看 trace：正确证据没进候选是 no hit，进了但排低或漏条件是排序/组装问题；证据在 final context 里但答案没用或编造，才更像 generation/grounding 问题。 |
| Faithfulness 和 correctness 有什么区别？ | Faithfulness 是答案主张是否被给定上下文支持；correctness 是答案是否符合真实事实或业务规则。忠实复述过期文档也可能不正确。 |
| Citation mismatch 怎么排查？ | 检查引用片段是否真的支持对应主张，再看 source tracking、context assembly、引用生成和文档版本是否丢失或错位。 |
| Top-k 越大越好吗？ | 不一定。更大的 top-k 可能提高召回，但也会增加噪声、成本和 lost-in-the-middle 风险，需要配合 rerank、压缩和去重。 |

## 易混点

| 概念 | 容易混的点 | 正确理解 |
|------|------------|----------|
| RAG vs 向量库 | 以为接向量库就是 RAG | 向量库只是检索实现之一，还需要 chunk、metadata、排序、上下文组装和评估 |
| RAG vs 长上下文 | 以为上下文够长就不需要检索 | 全库塞上下文成本高、噪声大，RAG 先缩小候选材料 |
| RAG vs 微调 | 以为微调能解决私有知识更新 | 微调适合行为和格式，高频变化事实仍应从外部证据来 |
| Dense vs Sparse | 以为 dense 总是更高级 | Dense 擅长语义相似，sparse 擅长精确术语、缩写和编号 |
| Rerank vs Retrieve | 以为 reranker 只是更贵的 retriever | Retriever 快速召回大候选，reranker 精细判断少量候选可回答性 |
| Faithfulness vs Correctness | 以为忠实就等于正确 | 忠实相对上下文，正确还要看真实事实、文档时效和业务规则 |
| Citation vs Grounding | 以为有引用就被证据支持 | 引用可能错配，答案主张仍需逐条被引用片段支持 |

## 项目连接

- 企业知识库问答：先说明知识更新频率、权限边界和引用要求，再讲 ingestion、chunk、metadata、hybrid search、rerank 和 context assembly。
- 合同或政策问答：重点保护条件、例外和版本日期，避免只召回片面证据后生成过度泛化答案。
- RAG 质量排查：固定记录 Question、retrieved chunks、reranked chunks、final prompt context、answer、label 和 failure type。
- 评估集建设：golden set 标注期望证据和参考答案，regression set 覆盖历史 no hit、partial hit、citation mismatch 和 stale document。
- 面试表达：把质量拆成召回层、排序层、组装层和生成层，不要只说“用 LLM-as-Judge 评估”。

## 反向链接

- [RAG 解决什么问题：边界与基本链路](../01-rag-retrieval-systems/01-rag-problem-boundary.md)
- [索引、Embedding 与召回](../01-rag-retrieval-systems/02-indexing-embedding-retrieval.md)
- [Hybrid Search、Rerank 与上下文组装](../01-rag-retrieval-systems/03-hybrid-search-rerank-context.md)
- [RAG 评估、幻觉与生产排查](../01-rag-retrieval-systems/04-rag-evaluation-debugging.md)
