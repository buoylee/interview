# Hybrid Search、Rerank 与上下文组装

## 这篇解决什么问题

第一阶段检索通常只负责“找一批可能相关的候选”。但候选里常有重复、过旧、只匹配关键词但不回答问题、语义相关但缺关键条件的片段。如果直接把 top-k 全塞进 prompt，模型会被噪声干扰，甚至引用错误证据。

这一篇解决的问题是：为什么 RAG 需要 Hybrid Search、Rerank 和单独的 context assembly，以及上下文顺序、压缩和去重为什么会影响幻觉。

## 学前检查

读这篇前，建议先理解：

- 文档如何被切分、向量化和召回：[索引、Embedding 与召回](./02-indexing-embedding-retrieval.md)
- 长上下文为什么不是免费答案：[长上下文、端侧部署与成本估算](../06-inference-deployment-cost/03-long-context-edge-cost.md)

如果还不熟，可以先记住一句话：retriever 找候选，reranker 重新判断候选可回答性，context assembly 决定模型最终看到什么。

## 概念为什么出现

单一检索信号不稳定：

```text
关键词检索: 能抓住 SOC2、SKU-123、P0 这类精确词，但不懂同义改写
稠密检索: 能抓住语义相近内容，但可能错过缩写、编号和专有名词
top-k 直塞: 候选顺序和噪声会影响模型注意力与引用
```

Hybrid Search、Rerank 和上下文组装出现，是为了从“找得到一些相关片段”进一步走到“把最能回答问题的证据交给模型”。

## 最小心智模型

一个更完整的检索后半段是：

```text
query -> BM25 results + dense results -> hybrid merge/RRF -> rerank -> dedup/compress/order -> prompt context
```

关键概念：

- BM25：常见稀疏检索算法，基于词项匹配、词频和文档长度等信号。
- dense retrieval：用 embedding 相似度召回语义相关片段。
- hybrid search：同时使用关键词和向量信号。
- RRF：Reciprocal Rank Fusion，把多个检索结果按排名融合，不强依赖原始分数尺度。
- reranker/cross-encoder：把 query 和候选 chunk 一起输入模型，重新判断相关性或可回答性。
- context assembly：选择、去重、压缩、排序并组织最终 prompt 上下文。

## 最小例子

用户问：

```text
SOC2 审计要求下，审计日志要保留多久？
```

第一阶段可能得到：

```text
BM25: 命中包含 "SOC2" 和 "audit" 的合规检查清单。
Dense: 命中 "security event log retention" 和 "audit trail retention" 相关片段。
```

BM25 找到了精确的 SOC2 术语，但片段可能只是说明“需要审计日志”。Dense 找到了语义相关的日志保留政策，但没有出现 SOC2。Reranker 会把 query 和候选一起看，优先提升最能回答“保留多久”的片段，例如：

```text
安全审计日志需至少保留 365 天；SOC2 审计材料引用该保留周期作为证据。
```

最后 context assembly 应该把这条主证据、必要定义和引用来源放进 prompt，而不是把所有 SOC2 页面和日志页面都塞进去。

## 原理层

Hybrid Search 的价值在于信号互补。BM25 对精确词强，dense retrieval 对语义改写强。RRF 常用于融合两路结果：如果一个片段在多个结果列表中都排得靠前，它会得到更高融合排名；如果只在一路结果中靠前，也仍有机会进入候选。

Reranker 和 retriever 的职责不同。Retriever 面向大规模候选库，需要快，所以通常用便宜的关键词或向量匹配。Reranker 面向少量候选，可以更慢更精细，判断候选是否真正回答 query。Cross-encoder reranker 会同时读取 query 和 chunk，因此比单独向量相似度更能理解条件、否定和可回答性。

Context assembly 是独立设计步骤，不是“取 rerank top-k”。它至少要处理：

- deduplication：去掉重复、近重复或同一段落多版本。
- compression：保留回答所需句子，压掉无关背景。
- ordering：把最关键证据放在模型更容易使用的位置。
- source tracking：保留文档标题、时间、段落和权限信息，便于引用。

Lost-in-the-middle 指长上下文中间位置的信息可能更容易被模型忽略。上下文越长，越需要考虑顺序、摘要和分组：把主证据放前面或靠近问题，把补充证据合并摘要，把冲突证据显式标注。

## 和应用/面试的连接

应用里，Hybrid Search 和 Rerank 常用于提高稳健性，尤其是企业文档里有缩写、编号、产品名和同义表达时。上下文组装则决定模型最终是否能忠实回答：即使检索命中了，如果 prompt 里证据太多、顺序混乱或引用丢失，仍然会幻觉。

面试里，可以把 RAG 质量拆成三层：召回层保证候选覆盖，排序层保证最可回答证据靠前，组装层保证模型看到清晰、少噪声、可引用的上下文。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| dense retrieval 总比 BM25 高级 | 两者信号不同，专有名词和编号常需要 BM25 |
| reranker 只是更贵的 retriever | reranker 处理少量候选，判断更细的相关性和可回答性 |
| top-k 越大越保险 | 过多片段会增加噪声、成本和 lost-in-the-middle 风险 |
| context assembly 不重要 | 它决定证据如何进入模型视野 |
| 有引用就不会幻觉 | 引用可能错配，答案仍需 grounding 检查 |

## 自测

1. Hybrid search 为什么比单一 dense retrieval 更稳？
2. Reranker 和 retriever 的职责区别是什么？
3. Context assembly 为什么会影响幻觉？
4. 为什么 top-k 越大不一定越好？

## 回到主线

到这里，你已经知道如何从候选证据走到可用上下文。下一步要看：当 RAG 回答失败时，如何判断是检索、排序、组装还是生成出了问题。

下一篇：[RAG 评估、幻觉与生产排查](./04-rag-evaluation-debugging.md)
