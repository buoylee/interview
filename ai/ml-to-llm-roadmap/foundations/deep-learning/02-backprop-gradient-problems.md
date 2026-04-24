# 反向传播、梯度消失与梯度爆炸

## 这篇只解决什么

这篇解释神经网络如何用 loss 更新参数，以及深层网络为什么会遇到梯度消失和梯度爆炸。它不要求你手推复杂偏导。

## 你在主线哪里会用到

- [Self-Attention 与 Q/K/V](../../04-transformer-foundations/03-self-attention-qkv.md)
- [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)

## 最小直觉

训练神经网络就是让 loss 变小。反向传播从 loss 出发，计算每个参数应该往哪个方向调。

```text
前向: 输入 -> 模型 -> 预测 -> loss
反向: loss -> 梯度 -> 更新参数
```

## 最小公式

```text
theta_new = theta_old - learning_rate * gradient
```

- `theta`：模型参数。
- `learning_rate`：每次更新的步长。
- `gradient`：loss 对参数的变化方向。严格说，梯度指向让 loss 增大的方向；梯度下降会减去 `learning_rate * gradient`，沿相反方向更新参数。

## 逐步例子

```text
预测太大 -> loss 变大
梯度下降根据梯度: 让相关权重沿降低 loss 的方向变小
优化器更新权重
下一次预测更接近目标
```

深层网络中，梯度要穿过很多层。如果每层都让梯度变小，就会梯度消失；如果每层都放大梯度，就会梯度爆炸。

## 常见误解

| 误解 | 修正 |
|------|------|
| 反向传播是倒着运行模型 | 它是倒着传播梯度，不是倒着生成输入 |
| 梯度消失只和 sigmoid 有关 | 深度、初始化、归一化、残差设计都会影响 |
| 梯度爆炸只能靠调小学习率 | 梯度裁剪、初始化和归一化也很重要 |

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/04-transformer-block.md)，理解 Residual 和 Norm 为什么是深层 Transformer 的关键。
