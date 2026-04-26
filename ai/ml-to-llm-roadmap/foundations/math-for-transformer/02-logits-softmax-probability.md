# Logits、Softmax 与概率分布

## 这篇解决什么卡点

读 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md) 时，模型会先算出一排分数，再把分数变成“读取比例”。卡点通常不是公式，而是不清楚原始分数和概率分布有什么区别。

读 [Decoder-only 生成过程](../../04-transformer-foundations/08-decoder-only-generation.md) 时，也会看到模型先给候选 token 打分，再从分布里选下一个 token。

## 先记住一句话

logits 是归一化前的原始分数，softmax 把这些分数变成非负、总和为 1 的权重。

## 最小例子

```text
logits = [2, 1, 0]
softmax 后大致变成 [0.67, 0.24, 0.09]
```

分数越大，softmax 后的概率越大；但其他候选不会直接变成 0，它们仍然保留一些权重。

temperature 只改变分布形状：更低的 temperature 让分布更尖锐、更保守；更高的 temperature 让分布更平、更容易多样化。它改变的不是模型学到的知识，而是怎么使用这些分数。

## 这个概念在 Transformer 哪里出现

在 attention 里，softmax 把 token 之间的匹配分数变成读取权重，表示当前 token 应该从上下文中各读多少。

在 decoder-only 生成里，softmax 把词表上每个候选 token 的 logits 变成概率分布，之后模型才能按策略选择下一个 token。

## 和旧资料的连接

这篇只解释 softmax 为什么适合把分数变成权重。如果想补概率分布、随机变量等背景，再读 [旧版概率基础](../../00-math-foundations/02-probability.md)。

## 自测

1. logits 和 probability 的区别是什么？
2. softmax 为什么适合表示“读取比例”？
3. temperature 改变的是知识还是分布形状？

## 回到主线

回到 [Self-Attention 里的 Q/K/V](../../04-transformer-foundations/04-self-attention-qkv.md)，再继续读 [Decoder-only 生成过程](../../04-transformer-foundations/08-decoder-only-generation.md)。
