# 2.7 损失函数 ⭐⭐⭐

> **一句话定位**：Softmax → Cross-Entropy → NLL Loss 是理解 LLM 训练目标的核心链条。搞懂这些就理解了"LLM 预训练到底在优化什么"。

---

## 工程师导读

> **面试优先级：⭐⭐⭐**
>
> **为什么 LLM 工程师要懂损失函数？**
> - 面试问"LLM 的训练目标是什么" → 答案就是交叉熵（最大化预测正确 token 的概率）
> - Temperature 怎么影响生成 → 本质是修改 Softmax 之前的 logits
> - Perplexity（模型评估指标） → 就是交叉熵的指数
> - RLHF 中的 KL 散度、DPO 的损失 → 都是交叉熵的变体
>
> **一句话总结 LLM 训练目标**：
> ```
> 给定 "今天天气"，模型输出 5 万个词的概率分布
> 正确答案是 "真" → 训练目标 = 让 P("真") 尽量大
> 损失函数 = -log P("真") → P("真") 越大，损失越小
> ```
>
> **先修**：[01-神经网络基础](./01-neural-network-basics.md)（知道 Softmax 把分数变概率）

---

## 目录

- [1. Softmax 函数](#1-softmax-函数)
- [2. 交叉熵损失](#2-交叉熵损失-cross-entropy-loss)
- [3. 负对数似然](#3-负对数似然-nll-loss)
- [4. 其他常见损失](#4-其他常见损失)
- [5. 损失函数在 LLM 中的完整链条](#5-损失函数在-llm-中的完整链条)
- [6. 面试常问](#6-面试常问)

---

## 1. Softmax 函数

### 1.1 定义

```
softmax(zᵢ) = exp(zᵢ) / Σⱼ exp(zⱼ)

输入：logits z = [z₁, z₂, ..., zₙ] (任意实数)
输出：概率分布 p = [p₁, p₂, ..., pₙ] (和为 1，每个 ≥ 0)
```

### 1.2 直觉

```
把"分数"变成"概率"

logits:  [2.0,  1.0, -1.0]
         ↓ exp
exp:     [7.39, 2.72, 0.37]  (都变正)
         ↓ 归一化
softmax: [0.71, 0.26, 0.03]  (和=1)

分数最高的获得最大概率，但不是 winner-take-all
```

### 1.3 Temperature 对 Softmax 的影响

```
softmax(zᵢ / T)

T=1.0:  [0.71, 0.26, 0.03]  ← 正常
T=0.5:  [0.91, 0.09, 0.00]  ← 更尖锐（高置信度）
T=2.0:  [0.54, 0.33, 0.13]  ← 更平坦（更随机）
T→0:    [1.0,  0.0,  0.0]   ← 等价于 argmax（贪婪）
T→∞:    [0.33, 0.33, 0.33]  ← 均匀分布（完全随机）
```

> 🔑 这就是 [阶段 3 解码策略](../03-nlp-embedding-retrieval/04-language-model-decoding.md) 中 Temperature 的底层原理。

### 1.4 Softmax 的数值稳定性

```
问题：exp(1000) = ∞ → 溢出
解决：减去最大值 → softmax(z) = softmax(z - max(z))

数学上等价（分子分母同乘常数不变），数值上稳定
所有深度学习框架都自动做这个处理
```

---

## 2. 交叉熵损失 (Cross-Entropy Loss)

### 2.1 回顾：信息论中的交叉熵

```
H(p, q) = -Σ p(x) × log q(x)

p = 真实分布（one-hot 标签）
q = 模型预测（softmax 输出）

回顾 阶段 0 信息论：
  H(p) = 自信息（真实分布的信息量）
  H(p, q) = 交叉熵 ≥ H(p)
  D_KL(p||q) = H(p,q) - H(p) = 两个分布的"距离"

最小化交叉熵 = 最小化 KL 散度（因为 H(p) 是常数）
= 让模型预测 q 尽量接近真实分布 p
```

### 2.2 分类场景中的交叉熵

```
真实标签: y = "猫" → one-hot = [1, 0, 0]  (猫, 狗, 鸟)
模型预测: q = softmax(logits) = [0.7, 0.2, 0.1]

交叉熵 = -(1×log(0.7) + 0×log(0.2) + 0×log(0.1))
       = -log(0.7)
       = 0.357

如果模型预测 q = [0.99, 0.005, 0.005]:
  交叉熵 = -log(0.99) = 0.01 ← 更低，更好

如果模型预测 q = [0.01, 0.01, 0.98]:
  交叉熵 = -log(0.01) = 4.6 ← 很高，很差
```

### 2.3 核心理解 ⭐

```
对于 one-hot 标签，交叉熵简化为：

CE = -log(q_正确类别)

即：正确类别的预测概率越高 → loss 越低
    正确类别的预测概率越低 → loss 越高

这就是负对数似然！
```

---

## 3. 负对数似然 (NLL Loss)

### 3.1 从交叉熵到 NLL

```
CE with one-hot labels = NLL = -log P(正确答案)

在 LLM 中：
  输入: "今天天气"
  正确下一词: "真"
  模型预测: P("真" | "今天天气") = 0.6

  Loss = -log(0.6) = 0.51

  如果 P("真") = 0.99 → Loss = 0.01 (好)
  如果 P("真") = 0.01 → Loss = 4.6  (差)
```

### 3.2 整个序列的损失

```
序列: "今天 天气 真 好"

L = -(1/T) × Σₜ log P(wₜ | w₁, ..., wₜ₋₁)

= -(1/3) × [log P("天气"|"今天") + log P("真"|"今天天气") + log P("好"|"今天天气真")]

每个 token 位置的负对数概率取平均 → 这就是 LLM 预训练的损失函数！
```

### 3.3 和 Perplexity 的关系

```
PPL = exp(Loss) = exp(Cross-Entropy)

Loss = 2.0 → PPL = exp(2.0) = 7.4（在 7 个词之间犹豫）
Loss = 1.0 → PPL = exp(1.0) = 2.7（在 3 个词之间犹豫）
Loss = 0.5 → PPL = exp(0.5) = 1.6（比较确定）
```

---

## 4. 其他常见损失

| 损失函数 | 公式 | 用在哪里 |
|---------|------|---------|
| **MSE** | (y - ŷ)² | 回归任务、VAE 重建 |
| **Binary CE** | -[y×log(q) + (1-y)×log(1-q)] | 二分类 |
| **InfoNCE** | -log[exp(sim⁺/τ) / Σexp(simₖ/τ)] | 对比学习（Embedding 训练）|
| **Bradley-Terry** | -log σ(r_w - r_l) | RLHF 奖励模型训练 |
| **DPO Loss** | -log σ(β×[log比率]) | DPO 对齐 |
| **Focal Loss** | -(1-p)^γ × log(p) | 不平衡分类 |

---

## 5. 损失函数在 LLM 中的完整链条

```
LLM 预训练时每一步：

1. 输入 tokens → Embedding Lookup → 向量序列

2. 前向传播 → Transformer Layers → 最后一层输出 (seq_len × d_model)

3. LM Head: 线性投影 → logits (seq_len × vocab_size)
   例: 50000 个词汇 → 每个位置一个 50000 维的 logits 向量

4. Softmax: logits → 概率分布
   P(next_token | context) for 每个位置

5. 交叉熵损失: 用真实的下一个 token 计算
   Loss = -log P(正确 token | context)

6. 反向传播: 用 Loss 计算梯度 → 更新参数

整链条: tokens → embeddings → Transformer → logits → softmax → CE Loss → 梯度 → 更新
```

---

## 6. 面试常问

### Q1: 为什么 LLM 用交叉熵损失？

**答**：LLM 预训练是分类问题——在词表 V 个类别中预测下一个 token。交叉熵等价于最大化 P(正确 token)（即最大似然估计 MLE）。对 one-hot 标签简化为 `-log P(正确token)`。

### Q2: 交叉熵和 KL 散度的关系？

**答**：H(p,q) = H(p) + D_KL(p||q)。最小化交叉熵等价于最小化 KL 散度（因为 H(p) 是常数）。这也是 RLHF 中 KL 约束的理论基础。

### Q3: Softmax 的 Temperature 怎么影响生成？

**答**：T 除以 logits 后再做 softmax。T<1 让分布更尖锐（更确定），T>1 让分布更平坦（更随机），T→0 等价于贪婪解码。

---

## 📖 推荐学习路径

本文串联了以下知识（按需回顾）：
- **旧版数学参考** [信息论](../00-math-foundations/04-information-theory.md)：熵、交叉熵、KL 散度的数学定义
- **旧版深度学习参考** [优化器](./02-optimizers-training.md)：梯度下降如何用 loss 更新参数
- **生成控制相关参考** [解码策略](../03-nlp-embedding-retrieval/04-language-model-decoding.md)：Temperature/Top-p 如何影响 softmax
- **训练主线参考** [训练流程](../06-llm-core/01-training-pipeline.md)：预训练的 CLM loss

## ⏭️ 回到新版路线

如果你是从 Deep Learning 补课来到这里，读到这里已经足够支撑理解 softmax、交叉熵和 KL 约束。下一步优先回到 Transformer 主线；如果要补 NLP、Embedding 或 RAG 背景，再按需读旧版 `03` 或新版 RAG 主线。

> ⬅️ [上一节：对比学习 & 其他范式](./06-other-architectures.md) | [返回旧版深度学习概览](./README.md) | 回到新版主线：[Transformer 必要基础](../04-transformer-foundations/) | 按需参考：[NLP + Embedding & 检索理论](../03-nlp-embedding-retrieval/)
