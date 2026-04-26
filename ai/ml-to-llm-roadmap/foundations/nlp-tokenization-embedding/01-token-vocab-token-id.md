# Token、Vocab 与 Token ID

## 这篇解决什么卡点

读到 Transformer 的“文本先变成 token id，再查表变成向量”时，最常见的卡点是：为什么一句话不能直接按字或词送进去，为什么还要多出 token、vocab、token id 这几层。

这里先解决这个卡点：Transformer 看到的不是原始文字，而是一串模型可识别的文本单位编号。

## 先记住一句话

token 是模型侧的文本单位，vocab 是模型允许使用的 token 清单，token id 是 token 在这个清单里的整数编号。

token 不一定等于一个词。它可能是一个词、一个词片段、一个标点、一个空格相关片段，或者代码里的某段字符。

## 最小例子

```text
"unhappy" 可能被切成 ["un", "happy"]
"user_id" 在代码或 JSON 里也会被拆成多个 token
```

如果 vocab 里有：

| token | token id |
|-------|----------|
| `un` | 501 |
| `happy` | 902 |
| `_` | 17 |
| `id` | 314 |

那么 token id 只是编号标签。`314` 本身不表示“身份”或“变量名”，它只表示“去 vocab 里找第 314 个 token”。

## 这个概念在 Transformer 哪里出现

主线的 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md) 里，第一步就是把文本切成 token，再把 token 映射成 token id。

Transformer 后面的 attention、MLP、layer norm 都不直接处理文字。它们处理的是由 token id 查表得到的向量。

## 和旧资料的连接

这里不展开 tokenizer 的算法细节，也不比较 BPE、WordPiece、SentencePiece。只要先记住：token 是模型输入单位，token id 是查表用的整数索引。

需要深入时再读 [旧版 Tokenization 深入](../../03-nlp-embedding-retrieval/06-tokenization-deep-dive.md)。

## 自测

1. token 为什么不一定等于词？
2. vocab 和 token id 的关系是什么？
3. 为什么 token id 本身没有语义？

## 回到主线

回到 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)，继续看 token id 如何进入 embedding table。
