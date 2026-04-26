# 从文本表示演进到 Transformer 输入

## 这篇解决什么卡点

读到 attention 之前，容易把 one-hot、Word2Vec、embedding、hidden state 混在一起，以为它们只是同一个东西的不同名字。

这里先解决这个卡点：这些方法都在回答“怎么表示文本”，但它们解决的问题层次不同。Transformer 的输入向量只是起点，后面的 hidden state 会逐层吸收上下文。

## 先记住一句话

从旧文本表示到 Transformer，可以粗略看成：从能编号，到能表达相似性，再到能随上下文改变。

## 最小例子

```text
One-hot/BoW: 能编号和统计，但语义弱
Word2Vec: 静态词向量，能表达相似性
Contextual embedding: 同一个词在不同上下文里表示不同
Transformer hidden state: token 向量逐层吸收上下文
```

比如 `bank` 在 “river bank” 和 “bank account” 里含义不同。静态 embedding 通常给它一个固定向量；contextual embedding 会根据上下文给出不同表示。

## 这个概念在 Transformer 哪里出现

主线的 [为什么 Attention 需要上下文](../../04-transformer-foundations/03-why-attention-needs-context.md) 里，关键问题是：一个 token 的表示不能只停留在自己是谁，还要知道它和上下文里其他 token 的关系。

Transformer 最开始的 token embedding 只是输入层表示。经过多层 self-attention 和 MLP 后，每一层的 hidden state 都会吸收更多上下文信息，所以最终 hidden state 不是最初的 token embedding。

## 和旧资料的连接

这篇只是桥接，不替代完整 NLP 表示史。你只需要先分清：one-hot/BoW 主要解决编号和统计，Word2Vec 解决静态语义相似，contextual embedding 和 Transformer hidden state 解决上下文相关表示。

想补完整背景时，再读 [旧版文本表示演进](../../03-nlp-embedding-retrieval/01-text-representation.md) 和 [旧版 Embedding 理论](../../03-nlp-embedding-retrieval/02-embedding-theory.md)。

## 自测

1. One-hot 为什么不能表达语义相近？
2. 静态 embedding 和 contextual embedding 的区别是什么？
3. Transformer hidden state 为什么不是最初的 token embedding？

## 回到主线

回到 [为什么 Attention 需要上下文](../../04-transformer-foundations/03-why-attention-needs-context.md)，继续看 self-attention 如何让 token 表示吸收上下文。
