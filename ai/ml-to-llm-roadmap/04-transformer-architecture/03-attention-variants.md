# 4.3 Attention 变体（Day 5-6）⭐

> **一句话定位**：从原始 MHA 到 GQA、MLA、Flash Attention，每个变体都在解决 Attention 的效率问题。这些是现代 LLM 的核心工程创新。

---

## 目录

- [1. MHA 原始多头注意力](#1-mha-原始多头注意力)
- [2. MQA 多查询注意力](#2-mqa-多查询注意力)
- [3. GQA 分组查询注意力](#3-gqa-分组查询注意力)
- [4. MLA 多头潜在注意力](#4-mla-多头潜在注意力)
- [5. Flash Attention](#5-flash-attention)
- [6. 长序列注意力](#6-长序列注意力)
- [7. 对比总结](#7-对比总结)
- [8. 面试常问](#8-面试常问)

---

## 1. MHA 原始多头注意力

```
每个头有独立的 Q, K, V 投影矩阵：

Head i: Q_i = XW_Q_i,  K_i = XW_K_i,  V_i = XW_V_i

例: 32 头 × 每头 128 维 = 4096 维模型
  Q: 32 个 (n × 128) 矩阵
  K: 32 个 (n × 128) 矩阵  → 推理时需要缓存所有 32 个头的 K
  V: 32 个 (n × 128) 矩阵  → 推理时需要缓存所有 32 个头的 V
```

**问题：KV-Cache 太大！**

```
KV-Cache 大小 = 2 × n_layers × n_heads × seq_len × d_head × 2bytes(FP16)

LLaMA-70B (80层, 64头, 128维, 4K 上下文):
  KV = 2 × 80 × 64 × 4096 × 128 × 2 = ~10 GB（单个请求！）
```

---

## 2. MQA 多查询注意力

### 2.1 核心思想

```
所有头共享同一组 K 和 V，只有 Q 不同：

MHA: Q₁K₁V₁, Q₂K₂V₂, ..., Q₃₂K₃₂V₃₂   (32 组 KV)
MQA: Q₁K V,  Q₂K V,  ..., Q₃₂K V         (1 组 KV！)

KV-Cache 减少 32× ！
```

### 2.2 效果

```
优点：推理时 KV-Cache 大幅减少 → 更快、能服务更多并发
缺点：效果可能略降（所有头看同一个 KV → 多样性下降）

使用：PaLM (Google)
```

---

## 3. GQA 分组查询注意力 ⭐

### 3.1 核心思想

```
MHA 和 MQA 的折中：将头分成 G 组，每组共享 K/V

MHA:  32 组 KV（每头独立）
GQA:  8 组 KV（每 4 个头共享一组 KV）← LLaMA 2/3 使用
MQA:  1 组 KV（所有头共享）

                MHA        GQA(8组)      MQA
Q 头数:          32          32           32
KV 组数:         32           8            1
KV-Cache:       32×         8×           1×
效果:           最好        接近MHA       略降
```

### 3.2 直觉

```
MHA = 32 个人各有各的笔记本
MQA = 32 个人共用 1 本笔记本 → 灵活性不够
GQA = 32 个人分 8 组，每组共用 1 本 → 平衡效率和灵活性
```

### 3.3 使用情况

```
LLaMA 2 (70B): 8 组 GQA
LLaMA 3:       GQA
Mistral:        GQA
Qwen:          GQA
→ GQA 已经是行业标准
```

---

## 4. MLA 多头潜在注意力

### 4.1 DeepSeek 的创新 ⭐

```
问题：即使 GQA 也需要缓存多组 KV
MLA 思路：用低秩压缩来进一步减少 KV-Cache

传统：缓存 K (n × d), V (n × d)
MLA：缓存 C (n × d_c)，d_c << d（压缩后的潜在表示）

推理时从 C 恢复出 K 和 V：
  K = C × W_K↑    (上投影恢复)
  V = C × W_V↑

效果：KV-Cache 比 GQA 更小，但注意力表达力接近 MHA
```

### 4.2 本质

```
MLA = 低秩分解应用在 KV-Cache 上

回顾 SVD/LoRA 的思想：
  高维矩阵 ≈ 低秩矩阵
  完整 KV (128维) → 压缩为 C (如 16维) → 恢复为 KV

使用：DeepSeek-V2, DeepSeek-V3
```

---

## 5. Flash Attention ⭐⭐

### 5.1 问题

```
标准 Attention 的内存瓶颈：

Q×K^T → 产生 (n × n) 矩阵 → 存到 GPU 显存 → 再做 softmax × V

n = 4096 时：注意力矩阵 = 4096² × 4bytes = 64 MB（每层每头）
n = 128K 时：注意力矩阵 = 128K² × 4bytes = 64 GB → 爆了！

关键：GPU 计算很快，但和显存之间的数据搬运（IO）是瓶颈
```

### 5.2 Flash Attention 的解决方案

```
核心思想：不存储完整的 n×n 注意力矩阵

方法：分块计算（Tiling）
  1. 把 Q, K, V 分成小块
  2. 在 GPU 的快速内存（SRAM）中计算每块的 attention
  3. 用 online softmax 算法增量更新结果
  4. 不需要把完整 n×n 矩阵写回显存

关键技术：Online Softmax
  - 通常 softmax 需要看到所有值（找最大值、求和）
  - Online Softmax 可以分块计算、增量更新
  - 数学上保证结果和标准 softmax 完全一致 → 精确，不是近似！
```

### 5.3 效果

```
Flash Attention 1 (2022):  2-4x 加速，无精度损失
Flash Attention 2 (2023):  进一步优化，~2x faster
Flash Attention 3 (2024):  对新硬件优化

所有现代 LLM 训练和推理都使用 Flash Attention
→ 不是可选优化，而是必备组件
```

### 5.4 IO 感知（IO-Aware）

```
GPU 内存层次：
  SRAM (快, 小): ~20MB, ~19TB/s
  HBM  (慢, 大): ~40GB, ~2TB/s    ← 标准注意力读写这里

标准 Attention: 反复读写 HBM → IO 瓶颈
Flash Attention: 尽量在 SRAM 中完成计算 → 减少 IO → 更快

这就是为什么叫 "IO-aware"
```

---

## 6. 长序列注意力

### 6.1 Sliding Window Attention

```
不让每个 token attend 所有 token，只看固定窗口内的：

窗口大小 W = 4:
     t₁  t₂  t₃  t₄  t₅  t₆  t₇  t₈
t₅ [  ❌  ❌  ✅  ✅  ✅  ✅  ❌  ❌ ]  ← 只看窗口 [t₃-t₆]

复杂度: O(n × W) 而不是 O(n²)

问题：看不到窗口外的信息
解决：多层堆叠 → 间接看到更远的信息（类似 CNN 的感受野）

使用：Mistral
```

### 6.2 Sparse Attention

```
固定模式的稀疏注意力：
  - 局部窗口（近邻）
  - 全局 token（每隔 k 个 token 做全局 attention）
  - 带状模式（对角线附近）

Longformer: 窗口 + 全局 attention
BigBird: 窗口 + 全局 + 随机

适用：需要超长上下文但不需要密集注意力的场景
```

---

## 7. 对比总结

| 变体 | KV-Cache | 计算量 | 精度 | 代表模型 |
|------|---------|--------|------|---------|
| **MHA** | 最大 | O(n²d) | 最好 | 原始 Transformer |
| **MQA** | 最小 (1/h) | O(n²d) | 略降 | PaLM |
| **GQA** ⭐ | 较小 (G/h) | O(n²d) | 接近MHA | LLaMA 2/3, Mistral |
| **MLA** | 更小 | O(n²d) | 接近MHA | DeepSeek-V2/V3 |
| **Flash Attn** ⭐ | 不存n×n矩阵 | 同 | 精确 | 所有现代 LLM |
| **Sliding Window** | 减少 | O(nW) | 局部 | Mistral |
| **Sparse** | 减少 | O(n√n) | 近似 | Longformer |

---

## 8. 面试常问

### Q1: MHA、MQA、GQA 的区别？

**答**：
- MHA：每个头独立 KV → 效果最好但 KV-Cache 最大
- MQA：所有头共享 1 组 KV → Cache 最小但效果可能降
- GQA：折中，分组共享 KV → 接近 MHA 效果 + 较小 Cache
- 现代 LLM 标配 GQA（如 LLaMA 2/3）

### Q2: Flash Attention 是什么？为什么重要？

**答**：
- 不是近似算法，结果完全精确
- 核心：分块在 GPU SRAM 中计算，避免存储 n×n 注意力矩阵到 HBM
- 使用 online softmax 技术实现分块计算
- 效果：2-4x 加速，显存大幅节省
- 是所有现代 LLM 的标配

### Q3: DeepSeek 的 MLA 是什么？

**答**：用低秩压缩 KV-Cache。不直接缓存 K 和 V（维度高），而是缓存压缩后的潜在向量 C（维度低），推理时从 C 恢复出 K/V。本质是 SVD/低秩分解在 KV-Cache 上的应用。

---

> ⬅️ [上一节：三种架构范式](./02-architecture-paradigms.md) | [返回概览](./README.md) | ➡️ [下一节：非 Transformer 架构](./04-non-transformer.md)
