# 4.1 Transformer 核心组件（Day 1-3）⭐⭐⭐

> **迁移提示**：新版路线已将 Transformer 核心拆成更顺滑的学习链路：
>
> - 为什么应用工程师需要懂 Transformer：[../04-transformer-foundations/01-why-ai-engineers-need-transformer.md](../04-transformer-foundations/01-why-ai-engineers-need-transformer.md)
> - 从 Token 到向量：[../04-transformer-foundations/02-token-to-vector.md](../04-transformer-foundations/02-token-to-vector.md)
> - 为什么 Attention 需要上下文：[../04-transformer-foundations/03-why-attention-needs-context.md](../04-transformer-foundations/03-why-attention-needs-context.md)
> - Self-Attention 与 Q/K/V：[../04-transformer-foundations/04-self-attention-qkv.md](../04-transformer-foundations/04-self-attention-qkv.md)
> - Transformer Block：[../04-transformer-foundations/05-transformer-block.md](../04-transformer-foundations/05-transformer-block.md)
> - 原始 Transformer Encoder/Decoder：[../04-transformer-foundations/06-original-transformer-encoder-decoder.md](../04-transformer-foundations/06-original-transformer-encoder-decoder.md)
> - 三种 Transformer 架构范式：[../04-transformer-foundations/07-transformer-architecture-variants.md](../04-transformer-foundations/07-transformer-architecture-variants.md)
> - Decoder-only 与逐 Token 生成：[../04-transformer-foundations/08-decoder-only-generation.md](../04-transformer-foundations/08-decoder-only-generation.md)
> - KV Cache 与上下文成本：[../04-transformer-foundations/09-kv-cache-context-cost.md](../04-transformer-foundations/09-kv-cache-context-cost.md)
> - 面试速记：[../09-review-notes/03-transformer-core-cheatsheet.md](../09-review-notes/03-transformer-core-cheatsheet.md)
>
> 本旧文暂时保留作为综合参考，不再作为默认学习入口。

> **一句话定位**：面试 Top 1 高频题。必须能从头讲清楚 Self-Attention 的完整计算过程，解释每个设计决策的原因。

---

## 工程师导读

> **面试优先级：⭐⭐⭐⭐⭐** — 如果这一阶段只能学一个文件，学这个
>
> **为什么这是最重要的一节？**
> - "从头讲一遍 Self-Attention" — 几乎每场 LLM 面试都会问
> - "为什么除以 √d_k" — Top 3 高频面试题
> - "RoPE 是什么" — 现代 LLM 标配，面试常问
> - 你用的每个大模型（GPT-4、Claude、LLaMA）核心都是这里讲的东西
>
> **本节核心要点（面试必背）**：
> 1. Self-Attention = softmax(QK^T / √d_k) × V
> 2. Q = "我需要什么"，K = "我有什么"，V = "我的内容" → 动态路由
> 3. 除以 √d_k → 防止点积过大导致 softmax 饱和（梯度消失）
> 4. Multi-Head → 不同头学不同类型的关系（语法、语义、指代等）
> 5. RoPE → 旋转位置编码，编码相对位置，现代 LLM 标配
> 6. FFN = 每个 token 独自"思考消化"（Attention 是"讨论交流"）
> 7. Pre-Norm + RMSNorm + Residual = 现代 LLM 的标配组合
>
> **工程师类比**：把 Transformer 想象成一个团队会议
> - **Attention** = 大家讨论，每个人根据自己的需求从别人那里获取信息
> - **FFN** = 讨论完了各自回去思考消化
> - **Residual** = 保留讨论前的想法（不会因为讨论就忘了自己原来想什么）
> - **LayerNorm** = 确保每个人的音量差不多（数值稳定）
> - 重复 N 次 = N 轮会议，每轮讨论得更深入
>
> **先修**：[阶段 2 / 05-RNN→LSTM→Attention](../02-deep-learning/05-rnn-lstm-attention.md)（知道 Attention 的 Q/K/V 思想）

---

## 目录

- [1. Transformer 全景架构](#1-transformer-全景架构)
- [2. Self-Attention 详解](#2-self-attention-详解)
- [3. Multi-Head Attention](#3-multi-head-attention)
- [4. 位置编码](#4-位置编码)
- [5. FFN 前馈网络](#5-ffn-前馈网络)
- [6. Residual + LayerNorm](#6-residual--layernorm)
- [7. Mask 机制](#7-mask-机制)
- [8. 完整前向传播](#8-完整前向传播)
- [9. 面试常问](#9-面试常问)

---

## 1. Transformer 全景架构

```
原始 Transformer (Attention is All You Need, 2017):

┌─────── Encoder ───────┐    ┌─────── Decoder ───────┐
│                       │    │                       │
│  Input Embedding      │    │  Output Embedding     │
│  + Positional Encoding│    │  + Positional Encoding│
│         ↓             │    │         ↓             │
│  ┌─────────────┐      │    │  ┌─────────────┐      │
│  │ Self-Attention│ ×N  │    │  │Masked Self-  │ ×N  │
│  │ + Add & Norm │      │    │  │Attention     │      │
│  │      ↓       │      │    │  │ + Add & Norm │      │
│  │   FFN        │      │    │  │      ↓       │      │
│  │ + Add & Norm │      │    │  │Cross-Attention│     │
│  └─────────────┘      │    │  │ + Add & Norm │      │
│                       │    │  │      ↓       │      │
└───────────────────────┘    │  │   FFN        │      │
                             │  │ + Add & Norm │      │
                             │  └─────────────┘      │
                             └───────────────────────┘

现代大模型（GPT）只用 Decoder 部分（去掉 Cross-Attention）
```

---

## 2. Self-Attention 详解

### 2.1 核心公式

```
Attention(Q, K, V) = softmax(QK^T / √d_k) × V
```

### 2.2 逐步拆解

#### Step 1: 生成 Q, K, V

```
输入 X: (seq_len × d_model)  如 (512 × 768)

Q = X × W_Q    W_Q: (d_model × d_k)
K = X × W_K    W_K: (d_model × d_k)
V = X × W_V    W_V: (d_model × d_v)

每个 token 都有自己的 Q, K, V 向量
  Q = "我在找什么？"（当前 token 的需求）
  K = "我有什么？"  （每个 token 的标签）
  V = "我的内容是什么？"（每个 token 的实际信息）
```

#### Step 2: 计算注意力分数

```
Scores = Q × K^T    形状: (seq_len × seq_len)

     K₁    K₂    K₃    K₄
Q₁ [0.8   0.1   0.3   0.2]     ← token 1 和每个 token 的相似度
Q₂ [0.2   0.9   0.1   0.4]     ← token 2 和每个 token 的相似度
Q₃ [0.1   0.3   0.7   0.5]
Q₄ [0.3   0.2   0.4   0.8]

直觉：每个 token 计算和所有其他 token 的相关性
```

#### Step 3: 归一化（除以 √d_k）⭐ 面试必问

```
Scores = Scores / √d_k

为什么除以 √d_k？

假设 Q 和 K 的每个元素独立，均值 0，方差 1
Q·K 的方差 = d_k（每个元素乘积的方差累加）

d_k = 64 → Q·K 的标准差 ≈ 8
→ 点积值可能到 ±24 (3σ)
→ softmax(24) ≈ 1.0, softmax(-24) ≈ 0.0
→ 输出接近 one-hot → 梯度消失！

除以 √64 = 8 后：
→ 值被缩回到合理范围
→ softmax 输出更平滑
→ 梯度正常
```

#### Step 4: Softmax → 注意力权重

```
Weights = softmax(Scores / √d_k)

每行和为 1（概率分布）

     K₁     K₂     K₃     K₄
Q₁ [0.45   0.10   0.25   0.20]  ← token 1 的注意力分配
Q₂ [0.10   0.55   0.05   0.30]  ← token 2 重点关注 K₂
...
```

#### Step 5: 加权求和 → 输出

```
Output = Weights × V    形状: (seq_len × d_v)

token 1 的输出 = 0.45×V₁ + 0.10×V₂ + 0.25×V₃ + 0.20×V₄

直觉：每个 token 的输出是所有 token 的 V 的加权组合
权重由 Q 和 K 的相似度决定
```

### 2.3 完整流程图

```
X ─→ [×W_Q] ─→ Q ─┐
                  ├─→ Q×K^T ─→ /√d_k ─→ softmax ─→ weights
X ─→ [×W_K] ─→ K ─┘                                    │
                                                       ├─→ output
X ─→ [×W_V] ─→ V ──────────────────────────────────────┘
```

### 2.4 复杂度分析

```
QK^T: (n × d) × (d × n) = O(n²d)
Attention × V: (n × n) × (n × d) = O(n²d)

总复杂度: O(n²d)

n = 序列长度 → 长序列是 Transformer 的瓶颈！
  n = 1K:   1M 运算
  n = 4K:   16M 运算
  n = 128K: 16B 运算（16 倍增长 → 256 倍计算）
```

---

## 3. Multi-Head Attention

### 3.1 为什么多头？

```
单头 Attention：只能关注一种类型的关系
多头 Attention：同时关注多种关系

例: "The cat sat on the mat because it was soft"
  Head 1: "it" → "mat"（语法指代）
  Head 2: "it" → "soft"（语义关联）
  Head 3: "cat" → "sat"（主谓关系）

每个头在不同的子空间学习不同类型的关联
```

### 3.2 实现

```
d_model = 768, num_heads = 12, d_k = d_model / num_heads = 64

把 Q, K, V 分成 12 份：
  Q₁(n×64), Q₂(n×64), ..., Q₁₂(n×64)
  K₁(n×64), K₂(n×64), ..., K₁₂(n×64)
  V₁(n×64), V₂(n×64), ..., V₁₂(n×64)

每个头独立做 Attention：
  head_i = Attention(Qᵢ, Kᵢ, Vᵢ)    形状: (n × 64)

拼接所有头 + 线性投影：
  MultiHead = Concat(head₁, ..., head₁₂) × W_O
  形状: (n × 768) × (768 × 768) = (n × 768)
```

### 3.3 参数量

```
W_Q: d_model × d_model = 768 × 768
W_K: d_model × d_model = 768 × 768
W_V: d_model × d_model = 768 × 768
W_O: d_model × d_model = 768 × 768

总参数: 4 × 768² ≈ 236 万（每层 Attention）
```

---

## 4. 位置编码

### 4.1 为什么需要位置编码？

```
Self-Attention 是置换不变的：
  Attention("猫 吃 鱼") = Attention("鱼 吃 猫")

→ 完全不知道词的顺序！
→ 必须手动注入位置信息
```

### 4.2 正弦余弦位置编码（原始 Transformer）

```
PE(pos, 2i)   = sin(pos / 10000^(2i/d))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d))

pos = 位置, i = 维度索引

特点：
  - 固定的（不需要学习）
  - 不同频率编码不同尺度的位置关系
  - 理论上可以泛化到任意长度
```

### 4.3 RoPE (Rotary Position Embedding) ⭐⭐ 现代 LLM 标配

```
核心思想：用旋转矩阵编码相对位置

不是把位置加到 Embedding 上，而是：
  - 在做 Q·K 之前，把 Q 和 K 按位置旋转
  - 旋转角度和位置成正比
  - Q_m · K_n 的结果只取决于 m-n（相对位置）

优势：
  ✅ 自然编码相对位置（而非绝对位置）
  ✅ 可以通过插值扩展到更长序列
  ✅ 不增加参数
  
用在：LLaMA, Qwen, DeepSeek, Mistral 等几乎所有现代开源 LLM
```

### 4.4 ALiBi (Attention with Linear Biases)

```
不加位置编码到 Embedding，而是在 Attention Score 上加一个偏置：

Score(i,j) = Q_i · K_j - m × |i - j|

m = 每个头不同的斜率
|i-j| = 距离越远，惩罚越大

直觉：距离远的 token 自然得到更低的 attention

用在：BLOOM, MPT
```

### 4.5 位置编码对比

| 方法 | 编码类型 | 长度泛化 | 使用 |
|------|---------|---------|------|
| 正弦余弦 | 绝对 | 一般 | 原始 Transformer |
| 学习式 | 绝对 | ❌（固定最大长度）| BERT, GPT-2 |
| **RoPE** ⭐ | 相对 | ✅（可插值扩展）| LLaMA, 大多数现代 LLM |
| ALiBi | 相对 | ✅ | BLOOM, MPT |

---

## 5. FFN 前馈网络

### 5.1 标准 FFN

```
FFN(x) = W₂ × ReLU(W₁ × x + b₁) + b₂

维度变化: d_model → 4×d_model → d_model
例: 768 → 3072 → 768

直觉：先扩展到更高维度（增加表达力），再压缩回来
```

### 5.2 SwiGLU FFN ⭐ 现代 LLM 标配

```
SwiGLU(x) = W₂ × (Swish(W₁x) ⊙ Vx)

Swish(x) = x × sigmoid(x)
⊙ = 逐元素乘法

维度: d → 4d/3×2 → d（因为有两个投影 W₁ 和 V，总参数量接近标准 FFN）

为什么 SwiGLU 更好：
  - GLU 门控机制：一条路算信息，一条路算门（要不要放行）
  - Swish 比 ReLU 更平滑
  - LLaMA 论文验证比标准 FFN 效果更好
```

### 5.3 FFN 的作用

```
Self-Attention: 捕捉 token 之间的关系
FFN: 对每个 token 独立做非线性变换

类比：
  Attention = 大家讨论交换信息
  FFN = 每个人独自思考消化信息

两者交替：讨论→思考→讨论→思考→...
```

---

## 6. Residual + LayerNorm

> 详见 [02-深度学习 / 01-神经网络基础](../02-deep-learning/01-neural-network-basics.md) 中的归一化章节。

### 6.1 Pre-Norm（现代 LLM 用法）

```
x → LayerNorm → Attention → + x → LayerNorm → FFN → + x

每个子层：output = x + SubLayer(LayerNorm(x))
```

### 6.2 RMSNorm（更快的变体）

```
RMSNorm(x) = x / √(mean(x²)) × γ

省掉了减均值步骤 → 更快
LLaMA, DeepSeek 等使用
```

---

## 7. Mask 机制

### 7.1 Padding Mask

```
Batch 中序列长度不同 → 短序列用 [PAD] 补齐
Padding Mask 让 [PAD] 位置不参与 Attention

句子1: "我 爱 AI [PAD] [PAD]"
句子2: "Transformer 很 强大 哦 ！"

Mask: [1, 1, 1, 0, 0] ← 0 的位置被屏蔽
```

### 7.2 Causal Mask（因果掩码）⭐

```
GPT 等自回归模型使用
每个 token 只能看到自己和之前的 token

Mask 矩阵（下三角）:
     t₁  t₂  t₃  t₄
t₁ [  0   -∞  -∞  -∞ ]
t₂ [  0    0   -∞  -∞ ]
t₃ [  0    0    0   -∞ ]
t₄ [  0    0    0    0  ]

加到 Attention Score 上 → softmax 后 -∞ 位置变成 0
```

---

## 8. 完整前向传播

```python
# 一层 Transformer Decoder Block (Pre-Norm 版)

def transformer_block(x):
    # Self-Attention
    residual = x
    x = rmsnorm(x)
    q, k, v = x @ W_Q, x @ W_K, x @ W_V
    # 分多头
    q, k = apply_rope(q, k, positions)  # RoPE 位置编码
    attn_scores = q @ k.T / sqrt(d_k)
    attn_scores = attn_scores + causal_mask  # 因果掩码
    attn_weights = softmax(attn_scores)
    attn_output = attn_weights @ v
    attn_output = concat_heads(attn_output) @ W_O
    x = residual + attn_output  # 残差连接
    
    # FFN (SwiGLU)
    residual = x
    x = rmsnorm(x)
    x = w2 @ (swish(w1 @ x) * (v_proj @ x))  # SwiGLU
    x = residual + x  # 残差连接
    
    return x
```

---

## 9. 面试常问

### Q1: 从头讲一遍 Self-Attention（面试最高频）

**答**：按 Step 1-5 讲：输入 X → 生成 Q/K/V → Q·K^T 计算注意力分数 → 除以 √d_k → softmax → 加权求和 V → 输出。关键解释为什么除以 √d_k（防止点积过大导致 softmax 饱和），为什么要多头（不同子空间学不同关系）。

### Q2: 为什么除以 √d_k？

**答**：Q·K 的方差和 d_k 成正比。d_k 大时点积值很大，softmax 趋向 one-hot（几乎只关注一个位置），梯度消失。除以 √d_k 将方差归一化为 1，让 softmax 输出更平滑。

### Q3: RoPE 是什么？为什么比学习式位置编码好？

**答**：
- RoPE 用旋转矩阵编码相对位置（Q·K 结果只取决于位置差）
- 比绝对位置编码好：(1) 泛化到训练未见的更长序列 (2) 可以通过 NTK-aware 插值扩展长度 (3) 不增加参数
- 几乎所有现代开源 LLM 都用 RoPE

### Q4: FFN 在 Transformer 中的作用是什么？

**答**：Self-Attention 捕捉 token 间关系，FFN 对每个 token 独立做非线性变换（"思考消化"）。现代 LLM 用 SwiGLU 替代 ReLU，通过门控机制增强表达力。FFN 的参数通常占模型总参数的 2/3。

### Q5: Transformer 的计算复杂度是多少？瓶颈在哪？

**答**：Self-Attention 是 O(n²d)，n 是序列长度。瓶颈在 n²：序列从 1K 到 128K 时计算量增大 16384 倍。这就是 Flash Attention、稀疏注意力等优化的动机。

---

## 📖 推荐学习路径

1. **必看 [Illustrated Transformer](https://jalammar.github.io/illustrated-transformer/)** — 最好的可视化讲解
2. 练习在纸上画出完整的 Attention 计算流程（Step 1-5），这是面试白板题
3. 确保能解释每个设计决策的原因（为什么 Q/K/V？为什么 √d_k？为什么多头？）

## ⏭️ 下一节预告

Transformer 有三种使用方式：Encoder-only（BERT）、Decoder-only（GPT）、Encoder-Decoder（T5）。为什么最终 **Decoder-only 成了绝对主流**？下一节给出答案。

> ⬅️ [返回阶段概览](./README.md) | ➡️ [下一节：三种架构范式](./02-architecture-paradigms.md)
