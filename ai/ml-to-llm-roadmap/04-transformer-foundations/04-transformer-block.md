# 4.4 Transformer Block：Attention、FFN、Residual、Norm 如何配合

## 你为什么要学这个

Self-Attention 只是 Transformer 的一个零件。现代 LLM 能堆几十层甚至上百层，是因为 Attention、FFN、Residual、LayerNorm/RMSNorm 和初始化方式共同保证表达能力和训练稳定性。

## 学前检查

你需要知道：

- Self-Attention 的 Q/K/V 流程；不熟先看 [03-self-attention-qkv.md](./03-self-attention-qkv.md)。
- Residual、LayerNorm、初始化的作用；不熟先看 [normalization/residual foundation](../foundations/deep-learning/03-normalization-residual-initialization.md)。
- FFN 和门控激活；不熟先看 [FFN/gating foundation](../foundations/deep-learning/04-ffn-gating-for-transformer.md)。

## 一个真实问题

面试官问："Transformer 一层里除了 Attention 还有什么？" 如果只会 Q/K/V，回答是不完整的。一个可训练、可堆叠的 Transformer block 还必须解释 FFN、Residual 和 Norm。

## 核心概念

### Pre-Norm Decoder Block

```text
x
-> RMSNorm / LayerNorm
-> Self-Attention
-> Add residual
-> RMSNorm / LayerNorm
-> FFN / SwiGLU FFN
-> Add residual
```

更精确地写，Pre-Norm block 的两步是：

```text
x = x + Attention(Norm(x))
x = x + FFN(Norm(x))
```

Pre-Norm 指先对输入做 Norm，再进入 Attention 或 FFN，最后加 residual。Post-Norm 指先做子层计算并加 residual，再对结果做 Norm。深层 LLM 常用 Pre-Norm，因为 residual 路径更直接，梯度更容易穿过很多层。

### Attention 负责 token 间通信

Attention 让每个 token 从上下文里的其他 token 读取信息。

### FFN 负责 token 内加工

FFN 对每个 token 独立执行非线性变换。可以把它理解为每个 token 读完上下文后进行内部消化。

### Residual 保留原信息并改善梯度流

```text
y = x + F(x)
```

即使 `F(x)` 学得不好，原始 `x` 仍能传下去；反向传播时梯度也有更短路径。

### LayerNorm / RMSNorm 稳定数值尺度

Norm 让每层输入保持稳定，减少训练发散风险。现代 LLM 常用 Pre-Norm 和 RMSNorm。

LayerNorm 会在每个 token 的 hidden dimension 上减去均值并除以标准差，再乘上可学习缩放参数。RMSNorm 不减均值，只按 root mean square 做尺度归一化，形式更简单，计算也更省。两者的共同目标都是控制激活尺度，让深层堆叠更稳定。

## 和 LLM 应用的连接

| 应用现象 | Block 视角 |
|----------|------------|
| 大模型更强 | 更多 block 叠加带来更深的上下文加工 |
| 训练深层网络困难 | Residual 和 Norm 是稳定训练的关键 |
| 推理成本高 | 每层都要做 Attention 和 FFN |
| LoRA 常挂在 Attention/FFN | 这些线性层承载主要可调能力 |

## 面试怎么问

- Transformer Block 由哪些部分组成？
- FFN 在 Transformer 里有什么作用？
- Residual Connection 为什么重要？
- Pre-Norm 和 Post-Norm 有什么区别？
- RMSNorm 和 LayerNorm 的区别是什么？

## 自测

1. Attention 和 FFN 的职责差异是什么？
2. Residual 为什么能帮助深层模型训练？
3. Pre-Norm 为什么比 Post-Norm 更稳定？
4. 为什么 LoRA 常作用在 Attention 和 FFN 的线性层？

## 下一步

下一篇读 [05-decoder-only-and-generation.md](./05-decoder-only-and-generation.md)，看 Transformer Block 如何组成 GPT 类生成模型。
