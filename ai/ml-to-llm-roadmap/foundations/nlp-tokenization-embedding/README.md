# Tokenization 与 Embedding 补课

> **定位**：这里只解决文本进入 Transformer 前的最小前置：token、vocab、token id、embedding table 和 position。完整 NLP 表示史留给旧 `03-nlp-embedding-retrieval` 深入阅读。

## 默认学习顺序

1. [Token、Vocab 与 Token ID](./01-token-vocab-token-id.md)
2. [Embedding Table 与位置信息](./02-embedding-table-and-position.md)
3. [从文本表示演进到 Transformer 输入](./03-from-text-representation-to-transformer.md)

## 什么时候读

| 你在主线哪里卡住 | 先读 |
|------------------|------|
| 不理解 token 为什么不是字或词 | [Token、Vocab 与 Token ID](./01-token-vocab-token-id.md) |
| 不理解 token id 为什么没有语义 | [Token、Vocab 与 Token ID](./01-token-vocab-token-id.md) |
| 不理解 embedding table | [Embedding Table 与位置信息](./02-embedding-table-and-position.md) |
| 不理解为什么还要 position | [Embedding Table 与位置信息](./02-embedding-table-and-position.md) |
| 想知道旧 NLP 文本表示和 Transformer 的关系 | [从文本表示演进到 Transformer 输入](./03-from-text-representation-to-transformer.md) |

## 和旧 NLP 资料的关系

读完这里后，如果想补完整背景，再回到：

- [旧版文本表示演进](../../03-nlp-embedding-retrieval/01-text-representation.md)
- [旧版 Embedding 理论](../../03-nlp-embedding-retrieval/02-embedding-theory.md)
- [旧版 Tokenization 深入](../../03-nlp-embedding-retrieval/06-tokenization-deep-dive.md)

> 回到主线：[从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)
