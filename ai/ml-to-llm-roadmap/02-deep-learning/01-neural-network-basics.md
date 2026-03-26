# 2.1 神经网络基础（Day 1-4）

> **一句话定位**：神经网络 = 一堆矩阵乘法 + 非线性激活函数的堆叠。理解这一点，后面的 CNN、RNN、Transformer 只是「怎么堆叠」的不同设计。

---

## 目录

- [1. 神经元](#1-神经元)
- [2. 多层感知机 MLP](#2-多层感知机-mlp)
- [3. 激活函数](#3-激活函数)
- [4. 反向传播](#4-反向传播)
- [5. 梯度消失与梯度爆炸](#5-梯度消失与梯度爆炸)
- [6. 归一化 BN vs LN](#6-归一化-bn-vs-ln)
- [7. Dropout](#7-dropout)
- [8. 权重初始化](#8-权重初始化)
- [9. 面试常问](#9-面试常问)

---

## 1. 神经元

### 1.1 单个神经元

```
输入: x₁, x₂, ..., xₙ
      ↓
z = w₁x₁ + w₂x₂ + ... + wₙxₙ + b  (线性变换)
      ↓
y = f(z)                             (非线性激活)
```

**直觉**：
- 线性部分 = 加权求和（和逻辑回归完全一样！）
- 激活函数 = 引入非线性（没有它，多层网络等于单层）

> 🔑 逻辑回归 = 一个使用 sigmoid 激活的神经元。这就是为什么逻辑回归是神经网络的起点。

### 1.2 为什么需要非线性？

```
没有激活函数：
  y = W₂(W₁x + b₁) + b₂ = (W₂W₁)x + (W₂b₁ + b₂) = W'x + b'
  → 多层线性 = 一层线性，加层毫无意义！

有激活函数：
  y = f₂(W₂ × f₁(W₁x + b₁) + b₂)
  → 能拟合任意复杂的函数
```

---

## 2. 多层感知机 MLP

### 2.1 结构

```
输入层 → 隐藏层₁ → 隐藏层₂ → ... → 输出层
  x    →  h₁=f(W₁x+b₁) → h₂=f(W₂h₁+b₂) → ... → ŷ
```

### 2.2 万能近似定理 (Universal Approximation Theorem)

**一个有足够多神经元的单隐藏层 MLP 可以近似任何连续函数。**

```
但「足够多」可能是天文数字！所以实践中用深层网络（每层少量神经元）而非浅层宽网络。

深 > 宽 的直觉：
  - 深层网络可以学习层次化特征（底层学简单特征，高层学复杂组合）
  - 类比：先学笔画 → 学部首 → 学汉字 → 学词语 → 学句子
```

### 2.3 前向传播

```python
# 伪代码
h = x
for layer in layers:
    h = activation(layer.weight @ h + layer.bias)
output = h
```

> 🔑 **ML 关联**：Transformer 中的 FFN（前馈网络）就是一个两层 MLP：
> ```
> FFN(x) = W₂ · activation(W₁ · x + b₁) + b₂
> 维度变化: d → 4d → d
> ```

---

## 3. 激活函数

### 3.1 常见激活函数对比 ⭐

| 激活函数 | 公式 | 值域 | 优点 | 缺点 | 用在 |
|---------|------|------|------|------|------|
| **sigmoid** | 1/(1+e⁻ˣ) | (0,1) | 输出是概率 | 梯度消失、不零中心 | 二分类输出 |
| **tanh** | (eˣ-e⁻ˣ)/(eˣ+e⁻ˣ) | (-1,1) | 零中心 | 梯度消失 | 早期 RNN |
| **ReLU** ⭐ | max(0, x) | [0,∞) | 简单快速、缓解梯度消失 | 死神经元(Dead ReLU) | CNN, MLP |
| **Leaky ReLU** | max(0.01x, x) | (-∞,∞) | 解决死神经元 | 多一个超参数 | 替代 ReLU |
| **GELU** ⭐ | x·Φ(x) | ≈(-0.17,∞) | 平滑、概率解释 | 计算稍复杂 | **Transformer/BERT** |
| **SiLU/Swish** ⭐ | x·σ(x) | ≈(-0.28,∞) | 平滑、自门控 | 计算稍复杂 | **现代 LLM** |
| **SwiGLU** ⭐ | Swish(xW₁) ⊙ (xV) | - | GLU 门控机制 | 多一个矩阵 | **LLaMA/GPT-4** |

### 3.2 ReLU 为什么好？

```
sigmoid 导数: σ'(z) = σ(z)(1-σ(z)) → 最大值 0.25
  → 多层连乘: 0.25 × 0.25 × 0.25... → 梯度消失！

ReLU 导数:
  x > 0 → 导数 = 1（梯度直通！）
  x < 0 → 导数 = 0（神经元"死了"）
```

### 3.3 GELU 为什么在 Transformer 中用？

```
GELU(x) = x × Φ(x)  (Φ 是标准正态分布的 CDF)
≈ x × sigmoid(1.702x)

直觉：不是硬性截断（ReLU: 负数直接变 0），而是"概率性"地丢弃
  → 平滑、可微、在负值区域有小梯度
```

### 3.4 SwiGLU 为什么是现代 LLM 标配？

```
标准 FFN:  W₂ · ReLU(W₁x)
SwiGLU FFN: W₂ · (Swish(W₁x) ⊙ Vx)     (⊙ = 逐元素乘法)

GLU 门控的直觉：一条路算"信息"，另一条路算"要不要放行" → 更强的表达能力
```

---

## 4. 反向传播

> 详细的数学原理已在 [03-微积分](../00-math-foundations/03-calculus.md) 中介绍。这里聚焦实践层面。

### 4.1 计算图 (Computational Graph)

```
x ──→ [Linear] ──→ [ReLU] ──→ [Linear] ──→ [Softmax] ──→ [CrossEntropy] ──→ Loss
         W₁              W₂

前向传播: 从左到右计算 Loss
反向传播: 从右到左计算 ∂Loss/∂W₁, ∂Loss/∂W₂
```

### 4.2 自动微分 (Autograd)

```python
# PyTorch 自动帮你做反向传播
loss = model(x)          # 前向传播，同时构建计算图
loss.backward()          # 反向传播，自动计算所有梯度
optimizer.step()         # 用梯度更新参数
optimizer.zero_grad()    # 清零梯度，准备下一次
```

> 🔑 你不需要手动计算梯度！框架的 Autograd 引擎全自动完成。但理解反向传播原理有助于 debug 梯度问题。

---

## 5. 梯度消失与梯度爆炸

### 5.1 梯度消失 (Vanishing Gradient)

```
∂L/∂W₁ = ∂L/∂hₙ × ∂hₙ/∂hₙ₋₁ × ... × ∂h₂/∂h₁ × ∂h₁/∂W₁

如果每个 ∂hᵢ/∂hᵢ₋₁ < 1（sigmoid 最大 0.25）:
  10 层: 0.25¹⁰ ≈ 0.000001 → 梯度几乎为 0！
  底层参数"学不到东西"
```

### 5.2 梯度爆炸 (Exploding Gradient)

```
如果每个 ∂hᵢ/∂hᵢ₋₁ > 1:
  10 层: 2¹⁰ = 1024 → 梯度爆炸！
  参数更新过大，训练发散（NaN）
```

### 5.3 解决方案 ⭐

| 问题 | 解决方案 | 原理 |
|------|---------|------|
| 梯度消失 | **ReLU 激活** | 正区域导数=1 |
| 梯度消失 | **Residual Connection** ⭐ | 梯度可以跳过层直接传回 |
| 梯度消失 | **Layer Normalization** | 稳定中间层分布 |
| 梯度消失 | **合理初始化 (Xavier/He)** | 控制每层输出的方差 |
| 梯度爆炸 | **梯度裁剪 (Gradient Clipping)** | 限制梯度最大值 |
| 梯度爆炸 | **Layer Normalization** | 同样能稳定梯度 |

> 🔑 **Transformer 的关键设计**：Residual Connection + Layer Normalization + GELU → 让几十甚至上百层的网络都能稳定训练。

---

## 6. 归一化 BN vs LN

### 6.1 Batch Normalization (BN)

```
对每个特征维度，在 batch 内做归一化：
  μ = mean(x, dim=batch)
  σ = std(x, dim=batch)
  x̂ = (x - μ) / σ
  y = γ × x̂ + β      (可学习的缩放和偏移)

归一化方向: [batch_size, features]
  ↕ 沿 batch 维度统计
```

**优点**：加速训练，允许更大学习率
**缺点**：
- 依赖 batch size（太小统计不准）
- 序列长度不同时不好用
- 推理时需要用训练时的 running mean/var

### 6.2 Layer Normalization (LN) ⭐

```
对每个样本，在特征维度内做归一化：
  μ = mean(x, dim=features)
  σ = std(x, dim=features)
  x̂ = (x - μ) / σ
  y = γ × x̂ + β

归一化方向: [batch_size, features]
  ←→ 沿 features 维度统计
```

### 6.3 为什么 Transformer 用 LN 而不是 BN？⭐⭐ 面试常问

| | BN | LN |
|--|----|----|
| 归一化维度 | batch 维度 | feature 维度 |
| 依赖 batch size | ✅ 依赖 | ❌ 不依赖 |
| 序列数据 | ❌ 不适合（序列长度不同） | ✅ 适合 |
| 推理一致性 | 需要 running stats | ✅ 推理和训练一致 |
| Transformer 选择 | ❌ | ✅ |

**核心原因**：
1. NLP 数据序列长度不同，BN 不好统计
2. 自回归生成时是逐 token 的（batch=1），BN 完全失效
3. LN 对每个 token 独立归一化，不受 batch 和序列长度影响

### 6.4 Pre-Norm vs Post-Norm

```
Post-Norm (原始 Transformer):
  x → Attention → Add(x) → LayerNorm → FFN → Add → LayerNorm

Pre-Norm (现代 LLM 标配):
  x → LayerNorm → Attention → Add(x) → LayerNorm → FFN → Add
```

**Pre-Norm 优势**：训练更稳定，梯度流更好。**现代 LLM (GPT-3, LLaMA, etc.) 都用 Pre-Norm。**

### 6.5 RMSNorm

```
RMSNorm(x) = x / √(mean(x²)) × γ

比 LayerNorm 省了减均值的步骤 → 更快
LLaMA、DeepSeek 等使用 RMSNorm
```

---

## 7. Dropout

### 7.1 原理

```
训练时：随机把每个神经元以概率 p 置为 0
推理时：不 Dropout，所有神经元参与

常见 p = 0.1 ~ 0.5
```

### 7.2 直觉

| 视角 | 解释 |
|------|------|
| 正则化 | 不让模型过度依赖任何一个特征/神经元 |
| 集成学习 | 每次相当于训练不同的子网络 → 隐式集成 |
| 噪声注入 | 给训练加点噪声 → 更鲁棒 |

### 7.3 在 LLM 中

```
预训练：通常不用 Dropout（数据量大，不容易过拟合）
微调：可能加 Dropout（数据少，防过拟合）
LoRA：在 A/B 矩阵之间可以加 Dropout
```

---

## 8. 权重初始化

### 8.1 为什么不能全零初始化？

```
如果所有权重都是 0：
  所有神经元的输出都一样 → 梯度都一样 → 更新都一样
  → 永远都一样！（对称性打不破）
```

### 8.2 Xavier 初始化

```
W ~ N(0, 1/n_in)  或  U(-√(6/(n_in+n_out)), √(6/(n_in+n_out)))

适用：sigmoid / tanh 激活函数
目标：让每层输出的方差保持一致
```

### 8.3 He 初始化 (Kaiming)

```
W ~ N(0, 2/n_in)

适用：ReLU 激活函数
原因：ReLU 砍掉了一半（负值），所以方差要乘 2 来补偿
```

### 8.4 现代实践

```
大模型通常使用：
  - 截断正态分布（防止极端值）
  - 初始化标准差和层数有关（越深层越小）
  - 特殊层可能有特殊初始化（如 Residual Block 的最后一层初始化为 0）
```

---

## 9. 面试常问

### Q1: 为什么要用激活函数？不用会怎样？

**答**：没有激活函数，多层线性变换等价于单层线性变换（矩阵乘法的结合律），网络无法学习非线性关系。激活函数引入非线性，让网络能近似任意复杂函数。

### Q2: ReLU 有什么问题？怎么解决？

**答**：
- **Dead ReLU**：如果输入 < 0，导数为 0，神经元永远不会更新（"死了"）
- 解决：Leaky ReLU（负值区域给小斜率 0.01）、GELU（平滑近似）
- 现代 LLM 用 GELU/SwiGLU 替代 ReLU

### Q3: BN 和 LN 的区别？为什么 Transformer 用 LN？

**答**：
- BN 沿 batch 维度归一化，LN 沿 feature 维度
- Transformer 用 LN 因为：(1) NLP 序列长度不同 (2) 自回归生成时 batch=1 (3) LN 对每个 token 独立归一化
- 现代 LLM 进一步用 RMSNorm（更快，省掉减均值）

### Q4: Residual Connection 为什么有效？

**答**：
```
y = F(x) + x   (输出 = 变换 + 原始输入)

梯度流：∂y/∂x = ∂F/∂x + 1

关键：即使 ∂F/∂x ≈ 0（梯度消失），梯度仍然至少是 1（通过恒等路径）
→ 梯度可以直通到底层，不会消失
```
- ResNet 首先提出，Transformer 中每个子层都用
- 也叫 skip connection / shortcut connection

### Q5: Pre-Norm 和 Post-Norm 的区别？

**答**：
- **Post-Norm**（原始 Transformer）：先算 Attention/FFN，再加残差后归一化
- **Pre-Norm**（现代 LLM）：先归一化，再算 Attention/FFN，最后加残差
- Pre-Norm 训练更稳定（梯度更好），现代 LLM 全部使用 Pre-Norm
- 代价：Pre-Norm 的最终表示可能需要额外的 final LayerNorm

---

## 📖 推荐学习路径

1. **3Blue1Brown《神经网络》**（4 集，约 1 小时）→ 直觉理解
2. 重点掌握：激活函数（ReLU vs GELU）、梯度消失解决方案、BN vs LN
3. 理解 Residual Connection → 这是 Transformer 最重要的组件之一

> ⬅️ [返回阶段概览](./README.md) | ➡️ [下一节：优化器 & 训练技巧](./02-optimizers-training.md)
