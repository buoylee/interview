# 阶段 2：深度学习基础（旧版参考）

> **定位**：这个目录保留旧版深度学习材料，供查漏补缺和扩展阅读使用。新版系统学习默认不从这里顺序读，而是从 [Transformer 必要基础](../04-transformer-foundations/) 出发，按需回到 [Deep Learning 补课](../foundations/deep-learning/)。
>
> **为什么这样改**：原来的深度学习阶段把太多前置概念塞进同一条学习线，容易让只想补 LLM 底层的学习者感觉跳跃。新版把“第一次讲懂 Transformer”放在主线，把神经网络基础拆成小的 foundation。

---

## 新版默认路径

```text
先读 Transformer 主线
  -> 卡在神经网络基础
  -> 回到 foundations/deep-learning 对应小节补课
  -> 补完回到原 Transformer 章节
```

默认入口：

- [Transformer 必要基础](../04-transformer-foundations/)
- [Deep Learning 补课](../foundations/deep-learning/)
- [新版神经网络基础入口](./01-neural-network-basics.md)

---

## 入口与旧版材料索引

| 文件 | 主题 | 面试优先级 | 核心收获 | 说明 |
|------|------|-----------|---------|------|
| [01-neural-network-basics.md](./01-neural-network-basics.md) | 神经网络基础 | ⭐⭐⭐ | 激活函数、BN vs LN、Residual Connection | 新版入口，指向拆分后的 foundation |
| [legacy/01-neural-network-basics-reference.md](./legacy/01-neural-network-basics-reference.md) | 神经网络基础旧版长文 | ⭐⭐⭐ | 激活函数、BN vs LN、Residual Connection | 旧版参考，不建议作为第一次学习入口 |
| [02-optimizers-training.md](./02-optimizers-training.md) | 优化器 & 训练技巧 | ⭐⭐ | AdamW、混合精度、梯度累积 | 旧版参考 |
| [03-transfer-learning.md](./03-transfer-learning.md) | 迁移学习 & 灾难性遗忘 | ⭐⭐ | 预训练+微调范式、LoRA 的动机 | 旧版参考 |
| [04-cnn.md](./04-cnn.md) | CNN & Residual Connection | ⭐ | **只需掌握 Residual Connection** | 旧版参考 |
| [05-rnn-lstm-attention.md](./05-rnn-lstm-attention.md) | RNN → LSTM → Attention | ⭐⭐⭐ | 通向 Transformer 的关键过渡 | 旧版参考 |
| [06-other-architectures.md](./06-other-architectures.md) | 对比学习 & 其他范式 | ⭐⭐ | 对比学习 → CLIP、Embedding 的理论根基 | 旧版参考 |
| [07-loss-functions.md](./07-loss-functions.md) | 损失函数 | ⭐⭐⭐ | Softmax → CE → NLL，LLM 训练目标 | 旧版参考 |

---

## 🎯 旧版阶段脉络（参考）

```
感知机 → MLP → CNN(空间) → RNN(时间) → Attention(万能) → Transformer

每一步都在解决上一步的问题：
MLP：能学非线性，但不能处理结构化数据
CNN：能捕捉空间局部特征，但不能处理序列
RNN：能处理序列，但记不住长距离
LSTM：能记住长距离，但不能并行
Attention：能并行 + 捕捉任意距离 → Transformer！
```

> **工程师视角**：你不需要能从头实现 CNN 或 LSTM。你需要理解的是：**为什么 Transformer 会取代它们**，以及 Transformer 从它们继承了什么（Residual Connection、门控机制、Attention 思想）。

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| [3Blue1Brown《神经网络》](https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi) | 神经网络 + 反向传播 | 最佳可视化，先看这个建立直觉 |
| 李宏毅机器学习 (B站) | DL 全覆盖 | 中文、系统 |
| [d2l.ai](https://d2l.ai/) | CNN/RNN/Attention 代码 | 理论+实践 |

> ⬅️ [上一阶段：ML 基础](../01-ml-basics/) | ➡️ [下一阶段：NLP + Embedding & 检索理论](../03-nlp-embedding-retrieval/)
