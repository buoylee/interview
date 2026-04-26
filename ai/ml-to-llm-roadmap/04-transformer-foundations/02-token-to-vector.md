# 4.2 从 Token 到向量

## 你为什么要学这个

LLM 不能直接处理字符串。它先把文本切成 token，再把 token ID 映射成向量。RAG 分块、上下文长度、价格、截断、工具调用格式，都会受 tokenization 和 embedding 表示影响。

## 学前检查

你需要知道：

- token、vocab、token id 的关系；不熟先看 [Token、Vocab 与 Token ID](../foundations/nlp-tokenization-embedding/01-token-vocab-token-id.md)。
- embedding table 和位置信息；不熟先看 [Embedding Table 与位置信息](../foundations/nlp-tokenization-embedding/02-embedding-table-and-position.md)。
- 向量是数字列表，矩阵乘法可以把一批向量一起变换；不熟先看 [向量、矩阵和点积](../foundations/math-for-transformer/01-vector-matrix-dot-product.md)。

## 一个真实问题

同一段文档按字符看不长，但放进模型后超出上下文窗口。原因是模型限制的是 token 数，不是字数。英文、中文、代码、JSON 的 token 切分效率不同，所以 RAG 分块不能只按字符数估算。

## 核心概念

### 文本进入模型的路径

```text
"用户输入" -> tokenizer -> token IDs -> embedding table -> token vectors
```

### Token ID 不是语义

Token ID 只是词表中的编号。模型真正计算的是 embedding 向量。

### Embedding Table 是一个查表矩阵

```text
词表大小 = V
向量维度 = d_model
Embedding Table 形状 = V x d_model
```

如果 token ID 是 `314`，模型取出 embedding table 中 ID 为 `314` 对应的那一行作为这个 token 的向量。

### 位置还没有进入

只查 embedding 时，同一个 token 在不同位置拿到的是同一类词向量。Transformer 还需要位置编码或位置机制告诉模型顺序信息。

## 和 LLM 应用的连接

| 应用现象 | 底层原因 |
|----------|----------|
| 同样字数的中文、英文、代码价格不同 | token 数不同 |
| JSON 输出容易变长 | 标点、引号、字段名也会占 token |
| RAG chunk 需要控制长度 | 模型上下文按 token 限制 |
| 长 prompt 会变慢 | 后续 Attention 计算和 KV Cache 都随 token 增长 |

## 面试怎么问

- Token、token ID、embedding 向量是什么关系？
- 为什么上下文窗口按 token 计数？
- Embedding table 的形状是什么？
- 为什么只靠 token embedding 还不知道词序？

## 自测

1. Token ID 和 embedding 向量有什么区别？
2. 为什么 RAG 分块不应该只按字符数？
3. Embedding table 的行数和列数分别代表什么？
4. 位置编码解决的是什么问题？

## 下一步

下一篇读 [03-why-attention-needs-context.md](./03-why-attention-needs-context.md)，先理解为什么 token 需要读取上下文，再进入 Q/K/V。
