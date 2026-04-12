# 4.4 非 Transformer 架构（Day 7-10）⭐

> **一句话定位**：面试区分度话题——「Transformer 有什么问题？有替代方案吗？」Mamba/SSM 是最重要的替代架构。

---

## 工程师导读

> **面试优先级：⭐** — 加分项，不是必考
>
> **为什么 LLM 工程师要了解这些？**
> - 面试区分度：大部分候选人只知道 Transformer，能讲 Mamba 的设计思路是加分项
> - 帮你理解行业趋势 — 混合架构（Mamba + Attention）可能是未来方向
> - DeepSeek 等中国大模型在这方面有创新（MLA、混合架构）
>
> **速读要点**（不需要深入，知道这些就够面试用了）：
> 1. Transformer 的核心问题 = O(n^2) 复杂度 + KV-Cache 线性增长
> 2. Mamba/SSM = 用固定大小的状态替代 KV-Cache → O(1) per step 推理
> 3. Mamba 的关键创新 = 选择性扫描（根据输入决定记住什么、忘记什么）
> 4. 混合架构（Jamba）= Mamba 负责高效处理 + 少量 Attention 负责精确回忆
>
> **先修**：[01-Transformer 核心](./01-transformer-core.md)

---

## 目录

- [1. Transformer 的核心问题](#1-transformer-的核心问题)
- [2. SSM 状态空间模型](#2-ssm-状态空间模型)
- [3. Mamba](#3-mamba)
- [4. RWKV](#4-rwkv)
- [5. 混合架构](#5-混合架构)
- [6. 其他替代架构](#6-其他替代架构)
- [7. 对比总结](#7-对比总结)
- [8. 面试常问](#8-面试常问)

---

## 1. Transformer 的核心问题

```
Attention 是 O(n²)：
  序列长度翻倍 → 计算量翻 4 倍
  
  n = 2K:    4M  计算单元
  n = 8K:    64M 计算单元 (16x)
  n = 128K:  16G 计算单元 (4096x)

KV-Cache 线性增长：
  每生成一个 token → KV-Cache 增大一行
  长对话/长文档 → 显存不断增加

这限制了：
  1. 最大上下文长度（虽然现在已经做到 128K+）
  2. 推理成本（越长越贵）
  3. 实时性（长序列首 token 延迟高）
```

---

## 2. SSM 状态空间模型

### 2.1 基本思想

```
从连续动力系统出发：
  ẋ(t) = Ax(t) + Bu(t)    (状态更新)
  y(t) = Cx(t) + Du(t)    (输出)

离散化后：
  x_t = Ā x_{t-1} + B̄ u_t
  y_t = C x_t + D u_t

直觉：
  x_t = 隐藏状态（"记忆"）
  u_t = 输入
  y_t = 输出
  A = 状态转移矩阵（怎么更新记忆）
  B = 输入矩阵（怎么写入新信息）
  C = 输出矩阵（怎么读出信息）
```

### 2.2 和 RNN 的关系

```
SSM 的递推形式：x_t = Ā x_{t-1} + B̄ u_t
RNN 的递推形式：h_t = f(W_h h_{t-1} + W_x x_t)

非常像！但 SSM 有两个关键区别：
  1. 线性递推（没有激活函数）→ 可以高效并行化
  2. A 矩阵有特殊结构（如对角矩阵、HiPPO 初始化）→ 长期记忆

训练时：展开为卷积 → 并行！O(n log n)
推理时：递推 → O(1) per step！（比 Transformer 的 O(n) 好）
```

### 2.3 S4 模型（Mamba 前身）

```
S4 (Structured State Spaces for Sequence Modeling):
  - Albert Gu 提出
  - HiPPO 初始化：A 矩阵记住历史信息的最优方式
  - 在长序列任务上超过 Transformer

但 S4 的 A, B, C 是固定的 → 不能根据输入动态调整
```

---

## 3. Mamba ⭐⭐

### 3.1 核心创新：选择性扫描

```
S4 问题：A, B, C 对所有输入相同 → 不能选择性地记住或遗忘
Mamba 创新：让 B, C, Δ 依赖于输入 → 选择性状态空间模型

B_t = f_B(x_t)    ← 输入相关！
C_t = f_C(x_t)    ← 输入相关！
Δ_t = f_Δ(x_t)    ← 输入相关！（控制时间步长）

直觉：
  遇到重要信息 → Δ 大 → 写入更多到状态
  遇到无关信息 → Δ 小 → 忽略

类似 LSTM 的门控，但用连续动力系统实现
```

### 3.2 复杂度优势

```
             训练并行性    推理(每步)    推理(总)
Transformer   ✅ O(n²)    O(n)          O(n²)     ← 需要看所有KV
Mamba         ✅ O(n)     O(1)          O(n)      ← 只需要固定大小的状态
```

### 3.3 硬件感知的并行算法

```
问题：选择性让 B, C 依赖输入 → 不能用 FFT 并行 → 退化为 O(n) 递推？
解决：Mamba 提出硬件感知的扫描算法
  - 利用 GPU 内存层次（类似 Flash Attention 思想）
  - 在 SRAM 中做递推，减少 HBM 访问
  - 虽然不是完全并行，但实际速度和 Transformer 相当甚至更快
```

### 3.4 Mamba 架构

```
标准 Transformer Block:
  LayerNorm → Attention → Add → LayerNorm → FFN → Add

Mamba Block:
  Linear → Conv1D → SiLU → SSM → Linear
       ↘ SiLU → 乘 ↗

没有 Attention！整个块替换为 SSM
```

### 3.5 Mamba-2

```
关键发现：结构化 SSM 和 Attention 有数学统一性

线性 Attention ≈ SSM（在特定参数化下）

Mamba-2 利用这个统一性：
  - 使用矩阵运算代替扫描 → 更好地利用 GPU
  - 训练速度比 Mamba-1 快 2-8x
```

---

## 4. RWKV

### 4.1 核心思想

```
RWKV = Receptance Weighted Key Value
  → RNN 的现代化改造

核心：线性注意力变体
  - 训练时可以并行（展开为矩阵运算）
  - 推理时递推 → O(1) per step

和传统 RNN 的区别：
  - 没有非线性激活 → 可以并行
  - 没有梯度消失问题
  - 有类似 Attention 的 token mixing 能力
```

### 4.2 RWKV 的特色

```
✅ 完全开源
✅ 支持超长上下文（推理时状态固定大小）
✅ 在多种benchmark上接近同规模 Transformer
❌ 在某些需要精确回忆的任务上不如 Transformer
```

---

## 5. 混合架构

### 5.1 为什么混合？

```
纯 Mamba 问题：需要精确回忆特定信息时不如 Attention
纯 Transformer 问题：长序列效率低

解决：混合使用

Jamba (AI21):
  - 大部分层用 Mamba → 高效
  - 少数层用 Attention → 精确回忆
  - + MoE → 进一步提效

直觉：
  Mamba 做"日常阅读"（高效处理大量信息）
  Attention 做"精确查找"（需要准确引用时）
```

### 5.2 混合比例

```
不同模型的策略：
  Jamba: 7:1（7 层 Mamba : 1 层 Attention）
  某些研究: 交替使用
  
目前没有统一最优比例，仍在研究中
```

---

## 6. 其他替代架构

| 架构 | 核心思想 | 特点 |
|------|---------|------|
| **RetNet** | 保留网络 | 训练并行、推理递推 O(1)、和 Transformer 可转换 |
| **xLSTM** | LSTM 现代化 | sLSTM（新门控）+ mLSTM（记忆矩阵），经典复兴 |
| **Linear Attention** | 去掉 softmax | Attention 变线性 O(n)，但效果通常不如标准 |
| **Hyena** | 长卷积 | 用可学习的长卷积替代 Attention |

---

## 7. 对比总结

```
              训练并行   推理复杂度   长序列能力   回忆精度
Transformer     ✅       O(n²)→O(n)*   受限窗口    ⭐⭐⭐
Mamba/SSM       ✅       O(1)          理论无限    ⭐⭐
RWKV            ✅       O(1)          理论无限    ⭐⭐
混合(Jamba)     ✅       O(n)*         理论无限    ⭐⭐⭐

* 有 KV-Cache/Flash Attention 优化后
```

### 当前共识

```
1. Transformer 仍然是主流（效果最好、生态最成熟）
2. Mamba 是最有前途的替代者（但还没完全证明大规模 scaling）
3. 混合架构可能是最优解（结合两者优点）
4. 长序列场景 Mamba 有明显优势
```

---

## 8. 面试常问

### Q1: Transformer 有什么问题？有替代方案吗？

**答**：
- **核心问题**：Self-Attention 是 O(n²)，长序列计算和内存都是瓶颈
- **替代方案**：
  - Mamba/SSM：线性复杂度，选择性状态空间模型
  - RWKV：线性注意力 + RNN 式递推
  - 混合架构（Jamba）：Mamba + 少量 Attention
- 目前 Transformer 仍是主流，但 Mamba 在长序列场景有优势

### Q2: Mamba 和 Transformer 的核心区别？

**答**：
- Transformer 用 Attention（O(n²)，显式存储所有 token 的 KV）
- Mamba 用 SSM（O(n)，固定大小的隐藏状态压缩所有历史信息）
- Mamba 的关键创新：选择性扫描，让状态更新依赖输入内容
- Transformer 更擅长精确回忆，Mamba 更擅长长距离依赖

### Q3: 为什么 SSM 能替代 Attention？

**答**：Mamba-2 发现了结构化 SSM 和线性 Attention 的数学等价性。SSM 的递推本质上在做和 Attention 类似的信息混合，但用固定大小的状态向量压缩了历史信息，在精度上有所牺牲但效率大幅提升。

### Q4: 混合架构为什么可能是最优解？

**答**：
- SSM 高效处理长序列（压缩历史），但不擅长精确回忆特定信息
- Attention 擅长精确回忆（显式存储 KV），但长序列效率低
- 混合：大部分层用 SSM（高效），关键层用 Attention（精确回忆）
- 类似人类：大部分时间快速阅读，偶尔仔细回忆特定内容

---

## 📖 推荐学习路径

1. **重点理解** Mamba 的选择性扫描思想和复杂度优势
2. 知道 Transformer vs SSM 的核心权衡（精确回忆 vs 效率）
3. 了解混合架构的趋势
4. 推荐资源：Mamba 论文 + Albert Gu 的讲座视频

## ⏭️ 下一阶段预告

恭喜你完成阶段 4！你现在已经深入理解了 Transformer 和它的替代方案。下一阶段进入 **预训练语言模型时代** — BERT 家族、GPT 演进、CLIP 和 T5。这是了解大模型"家谱"的阶段，帮你理解从 BERT 到 ChatGPT 之间发生了什么。

> ⬅️ [上一节：Attention 变体](./03-attention-variants.md) | [返回概览](./README.md) | ➡️ [下一阶段：预训练语言模型](../05-pretrained-models/)
