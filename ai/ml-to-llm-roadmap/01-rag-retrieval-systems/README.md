# 01 RAG 与检索系统

> **定位**：这个模块解释 RAG 为什么存在，以及如何把外部知识从“搜到一些文本”变成可评估、可追溯、可上线的上下文增强生成系统。

## 默认学习顺序

1. [RAG 解决什么问题：边界与基本链路](./01-rag-problem-boundary.md)
2. [索引、Embedding 与召回](./02-indexing-embedding-retrieval.md)
3. [Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md)
4. [RAG 评估、幻觉与生产排查](./04-rag-evaluation-debugging.md)

## 学前检查

| 如果你不懂 | 先补 |
|------------|------|
| 文本如何变成向量 | [旧版 Embedding 理论](../03-nlp-embedding-retrieval/02-embedding-theory.md) |
| 检索为什么有稀疏和稠密两类 | [旧版检索理论](../03-nlp-embedding-retrieval/03-retrieval-theory.md) |
| LLM 如何使用上下文生成 | [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md) |
| 长上下文为什么昂贵 | [长上下文、端侧部署与成本估算](../06-inference-deployment-cost/03-long-context-edge-cost.md) |

## 这个模块的主线

RAG 的核心不是“接一个向量库”，而是解决外部知识如何进入 LLM 输出的问题：

```text
知识源 -> 切分和索引 -> 查询理解 -> 召回和排序 -> 上下文组装 -> 生成 -> 评估和排查
```

学完本模块，你应该能解释 RAG 和长上下文、微调、搜索、Agent 工具调用的边界，并能排查“没检到、检错了、检到了但没用好、回答不忠实”等常见问题。

## 深入参考

旧版材料仍可作为扩展阅读：

- [旧版 RAG 系统理论深度](../07-theory-practice-bridge/01-rag-deep-dive.md)
- [旧版 Embedding 理论](../03-nlp-embedding-retrieval/02-embedding-theory.md)
- [旧版检索理论](../03-nlp-embedding-retrieval/03-retrieval-theory.md)
