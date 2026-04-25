# 反向传播、梯度消失与梯度爆炸

## 这篇解决什么问题

这篇解释神经网络训练时最核心的一条链路：

```text
loss -> gradient -> optimizer update
```

模型先用当前参数做预测，loss 衡量预测和目标差多少；反向传播计算每个参数对应的 gradient；optimizer 再根据这些 gradient 更新参数，通常让后续预测朝更低 loss 的方向移动。

## 学前检查

读这篇前，你只需要确认三件事：

- 知道神经网络有很多可学习参数，也就是权重和偏置。
- 知道训练目标是让 loss 变小。
- 知道深层模型由很多层连续堆叠而成。

不需要会手推复杂偏导。这里关心的是训练方向和深层网络为什么难训练。

## 一个真实问题

假设模型在做文本分类，目标答案是“正向”，但模型预测成“负向”。这次预测会产生较高 loss。

训练要回答的问题不是“错了”这么简单，而是：

- 哪些参数让这个错误更容易发生？
- 每个参数该往哪个方向调？
- 每次调多少才不至于太慢或太猛？

这就是 gradient 和 optimizer 要解决的问题。

## 核心概念

前向传播负责得到预测和 loss：

```text
输入 -> 模型 -> 预测 -> loss
```

反向传播不是“把模型倒着运行一遍”，也不是从输出倒推出输入。它是在计算图上从 loss 出发，把 gradient 一层层传播回去，计算 loss 对每个参数的敏感度。

最基本的 optimizer update 可以写成：

```text
theta_new = theta_old - learning_rate * gradient
```

这是最简单的 gradient descent 形式。真实 LLM 训练常用 AdamW 或类似 optimizer，会用动量、自适应缩放、weight decay 等方式处理原始 gradient；但核心仍然是用 gradient 信息决定参数更新方向。

- `theta_old`：更新前的参数。
- `theta_new`：更新后的参数。
- `learning_rate`：每次更新的步长。
- `gradient`：loss 对参数的变化方向。

关键点是：gradient 指向让 loss 增大的方向，所以 gradient descent 要减去它。`learning_rate` 控制沿反方向走多远。

梯度消失和梯度爆炸来自同一个直觉：深层网络里，gradient 要穿过很多层。粗略地说，可以把它理解成 gradient 的尺度会被每层的局部变化影响；在真实网络里这是矩阵/Jacobian 的连乘，结果表现为 gradient norm 被持续缩小或放大。

- 如果这些数很多都小于 1，反复相乘后 gradient 会越来越接近 0，这就是梯度消失。
- 如果这些数很多都大于 1，反复相乘后 gradient 会急剧变大，这就是梯度爆炸。

## 最小心智模型

把训练想成三步：

```text
1. loss 告诉你当前预测错得多不多
2. gradient 告诉你参数往哪里动会让 loss 变化
3. optimizer 按规则更新参数
```

把反向传播想成：沿着计算图把“责任信号”从 loss 传回每一层。它传的不是 token，也不是反向生成结果，而是每个节点对 loss 的影响。

把深层训练问题想成：这个责任信号要过很多关。每一关都会缩小或放大它，层数越多，连乘效应越明显。

## 和 Transformer 的连接

Transformer 可以很深。层数越深，gradient 在层与层之间传播的路径越长，梯度消失和梯度爆炸的风险就越重要。

这也是为什么 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md) 里会反复看到 Residual 和 Norm：

- Residual 给 gradient 提供更直接的传播路径，降低深层堆叠时信号被层层削弱的风险。
- Norm 稳定每层输入输出的尺度，让训练过程更不容易出现数值失控。

没有这些结构，深层 Transformer 更难稳定训练；有了它们，模型才能把很多层堆起来，同时保持 optimizer update 有效。需要更多细节时，继续读 [Normalization、Residual 与初始化](./03-normalization-residual-initialization.md)。

## 常见误区

| 误区 | 修正 |
|------|------|
| 反向传播是在倒着运行模型 | 反向传播是在计算图上倒着传播 gradient，不是倒着生成输入 |
| gradient 指向降低 loss 的方向 | gradient 指向增加 loss 的方向，所以梯度下降要减去它 |
| learning_rate 越大训练越快 | 太大可能越过低 loss 区域，甚至让训练发散 |
| 梯度消失只和 sigmoid 有关 | 深度、初始化、激活函数、Residual、Norm 都会影响 |
| 梯度爆炸只要调小学习率就行 | 还可能需要梯度裁剪、初始化、Norm 等方法 |

## 自测

1. `loss -> gradient -> optimizer update` 这条链路里，每一步分别回答什么问题？
2. 为什么公式里是 `theta_old - learning_rate * gradient`，而不是加上 gradient？
3. 反向传播为什么不是“把模型倒着运行一遍”？
4. 梯度消失和梯度爆炸为什么都可以用“很多层里反复相乘”来理解？
5. Residual 和 Norm 为什么对深层 Transformer 特别重要？

## 回到主线

读完后回到 [Transformer Block](../../04-transformer-foundations/05-transformer-block.md)，重点观察一个 Block 里 Residual、Norm、Attention、MLP 如何共同让深层训练保持稳定。
