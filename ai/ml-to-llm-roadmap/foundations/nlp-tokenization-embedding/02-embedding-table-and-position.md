# Embedding Table 与位置信息

## 这篇解决什么卡点

读到“token id 查 embedding table 得到向量”时，容易误以为 token id 自己就带语义，或者以为查出来的向量已经包含了完整句子信息。

这里先解决这个卡点：token embedding 只把“是哪一个 token”变成可计算的向量，还不能单独表达顺序。

## 先记住一句话

embedding table 是一个形状为 `vocab_size x d_model` 的参数表：每一行对应一个 token，每一列对应向量的一个维度。

查表得到的是模型能计算的向量，不是把 token 翻译回文字。

## 最小例子

```text
token id = 314
embedding table[314] -> 这个 token 的向量
```

如果 `vocab_size = 50000`，`d_model = 768`，embedding table 的形状就是：

```text
50000 x 768
```

第 314 行可能是一个 768 维向量。这个向量一开始是可训练参数，训练后会变成模型使用的内容表示。

## 这个概念在 Transformer 哪里出现

主线的 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md) 里，token id 会先查 token embedding table。

但 token embedding 只告诉模型“当前位置是什么 token”，不告诉模型“这个 token 在第几个位置”。如果输入是 `A B` 和 `B A`，只看两个 token 的身份，不足以稳定地区分谁在前、谁在后。

所以 Transformer 还需要位置信息。position embedding、RoPE 或其他位置机制，解决的都是同一个问题：让模型知道 token 的顺序关系。

## 和旧资料的连接

这里不展开 embedding 训练目标，也不推导相似度空间。只要先记住：embedding table 把离散 token id 变成连续向量，position 机制补上顺序信息。

需要深入时再读 [旧版 Embedding 理论](../../03-nlp-embedding-retrieval/02-embedding-theory.md)。

## 自测

1. embedding table 的行数和列数分别代表什么？
2. 为什么查表后得到的是向量而不是文字？
3. 为什么只靠 token embedding 不知道顺序？

## 回到主线

回到 [从 Token 到向量](../../04-transformer-foundations/02-token-to-vector.md)，继续看 token embedding 和 position 信息如何组成 Transformer 的输入。
