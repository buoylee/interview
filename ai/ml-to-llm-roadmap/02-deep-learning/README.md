# 阶段 2：深度学习基础（2 周）

> **目标**：理解神经网络的工作原理，掌握从 MLP → CNN → RNN → Attention 的演进脉络。这是通向 Transformer 和大模型的必经之路。
>
> **你的定位**：你已经在使用基于 Transformer 的模型（GPT、BERT），这里补齐「Transformer 之前发生了什么」以及「为什么需要 Transformer」。

---

## 📂 本阶段内容

| 文件 | 主题 | 预计时间 | 后续关联 |
|------|------|---------|---------|
| [01-neural-network-basics.md](./01-neural-network-basics.md) | 神经网络基础 | Day 1-4 | 所有深度学习的基石 |
| [02-optimizers-training.md](./02-optimizers-training.md) | 优化器 & 训练技巧 | Day 5-6 | LLM 训练配置 |
| [03-transfer-learning.md](./03-transfer-learning.md) | 迁移学习 & 灾难性遗忘 | Day 7 | 预训练+微调范式、LoRA 动机 |
| [04-cnn.md](./04-cnn.md) | CNN 卷积神经网络 | Day 8-9 | Residual Connection → Transformer |
| [05-rnn-lstm-attention.md](./05-rnn-lstm-attention.md) | RNN → LSTM → Attention | Day 10-12 | ⭐ **通向 Transformer 的关键过渡** |
| [06-other-architectures.md](./06-other-architectures.md) | 其他架构 | Day 13-14 | VAE、GAN、对比学习 → CLIP |
| [07-loss-functions.md](./07-loss-functions.md) | **损失函数（补充）** | 随时参考 | ⭐ Softmax→CE→NLL 完整链条 |

---

## 🎯 本阶段核心脉络

```
感知机 → MLP → CNN(空间) → RNN(时间) → Attention(万能) → Transformer

每一步都在解决上一步的问题：
MLP：能学非线性，但不能处理结构化数据
CNN：能捕捉空间局部特征，但不能处理序列
RNN：能处理序列，但记不住长距离
LSTM：能记住长距离，但不能并行
Attention：能并行 + 捕捉任意距离 → Transformer！
```

## 📖 推荐资源

| 资源 | 覆盖内容 | 特点 |
|------|---------|------|
| [3Blue1Brown《神经网络》](https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi) | 神经网络 + 反向传播 | 最佳可视化 |
| 李宏毅机器学习 (B站) | DL 全覆盖 | 中文、系统 |
| [d2l.ai](https://d2l.ai/) | CNN/RNN/Attention 代码 | 理论+实践 |

> ⬅️ [上一阶段：ML 基础](../01-ml-basics/) | ➡️ [下一阶段：NLP + Embedding & 检索理论](../03-nlp-embedding-retrieval/)
