# 6.13 长上下文技术

> **一句话定位**：如何让 LLM 处理 128K 甚至 1M+ token 的超长文本，涉及位置编码外推、注意力优化和工程挑战。

---

## 1. 为什么长上下文很难？

```
核心瓶颈：

1. 注意力复杂度
   Self-Attention = O(n²) 计算 + O(n²) 内存
   4K context → 16M 个注意力值
   128K context → 16.4B 个注意力值（增长 1024 倍！）

2. KV-Cache 内存
   每个 token 需要存储 K 和 V 向量
   128K context × 80 layers × 128 heads × 128 dim × 2(K+V) × 2 bytes(FP16)
   ≈ 40+ GB 仅 KV-Cache

3. 位置编码外推
   如果训练时只见过 4K 长度 → 推理时位置编码在 4K 之后可能失效
   → "分布偏移"：模型没学过这些位置

4. 注意力稀释 ("Lost in the Middle")
   上下文太长时，模型倾向于关注开头和结尾
   中间的信息容易被忽略
```

## 2. 位置编码扩展方法 ⭐

### 2.1 RoPE (Rotary Position Embedding) 回顾

```
RoPE 基本思想：
  将位置信息编码为旋转角度
  q_m · k_n 只取决于相对位置 (m-n)

  R(θ, m) × q  →  旋转 query 向量
  R(θ, n) × k  →  旋转 key 向量
  内积结果只依赖于 m-n（相对位置）

θ_i = 10000^(-2i/d)  → 不同维度用不同的旋转频率
  低维 → 高频旋转（捕获局部位置关系）
  高维 → 低频旋转（捕获远距离位置关系）
```

### 2.2 Position Interpolation（位置插值）

```
问题：模型在 4K 训练 → 推理 32K 时位置 5000-32000 从未见过

思路：把 [0, 32K] 的位置压缩到 [0, 4K] 范围
  position' = position × (L_train / L_target)
  例：position 32000 → 32000 × (4096/32768) = 4000

  相当于"缩小刻度"：原来 1 格 = 1 位置，现在 1 格 = 8 位置

优点：简单有效，Meta 用此方法将 LLaMA 扩展到 32K
缺点：分辨率降低 → 近距离的位置区分度变差

实操：需要少量长文本数据微调（约 1000 步）
```

### 2.3 NTK-aware Interpolation

```
Position Interpolation 的问题：对所有频率维度统一缩放
  → 高频维度（管近距离关系）也被缩了 → 近距离的精度丢失

NTK-aware 改进：
  - 高频维度（管近距离）→ 少缩或不缩（保持局部精度）
  - 低频维度（管远距离）→ 多缩（适应长序列）

  通过修改 RoPE 的 base 值实现：
  base' = base × α^(d/(d-2))

  α = L_target / L_train

优点：
  - 不需要微调就有一定效果（"免训练"外推）
  - 保持近距离位置精度
```

### 2.4 YaRN (Yet another RoPE extensioN)

```
综合方法：分维度处理

将 RoPE 的不同频率维度分为三组：
  高频维度 → 不做任何修改（已经能在训练长度内完成完整周期）
  低频维度 → 线性插值（类似 Position Interpolation）
  中间维度 → NTK-aware 插值（平滑过渡）

+ 注意力分布修正（temperature 调整）

效果：目前 RoPE 外推的最优综合方案
```

### 2.5 ALiBi (Attention with Linear Biases)

```
不用 RoPE，直接在注意力分数上加位置偏置：

Attention = softmax(QK^T/√d + bias)

bias[i][j] = -m × |i - j|
  m 是每个头不同的斜率
  距离越远 → 偏置越负 → 注意力越弱

优点：
  - 天然支持任意长度（只是线性衰减）
  - 不修改 Q/K 向量本身

缺点：
  - 训练长度外的外推能力有限（虽然好于绝对位置编码）
  - 长距离信息被强制压低（有些场景不合适）
```

## 3. 注意力优化方法

### 3.1 Sliding Window Attention

```
每个 token 只关注附近 W 个 token（如 W=4096）

  Token:     1    2    3    4    5    6    7    8
  关注范围: [1-4] [1-4] [1-4] [1-4] [2-5] [3-6] [4-7] [5-8]

  层叠效应：多层 Sliding Window 叠加后，信息可以传播更远
    Layer 1: 每个 token 看 W=4K 范围
    Layer 2: 通过 Layer 1 传递，等效看 8K 范围
    Layer N: 等效感受野 = N × W

代表：Mistral (W=4096)
```

### 3.2 Ring Attention

```
分布式长上下文方案：

将长序列分成多个块，分配到不同 GPU：
  GPU 0: tokens [0, L/4]
  GPU 1: tokens [L/4, L/2]
  GPU 2: tokens [L/2, 3L/4]
  GPU 3: tokens [3L/4, L]

每个 GPU 计算自己的 Q，但 K/V 在 GPU 间"环形"传递：
  Round 1: GPU_i 用自己的 KV
  Round 2: GPU_i 收到 GPU_(i-1) 的 KV → 计算交叉注意力
  Round 3: 继续传递...

优点：
  - 内存随 GPU 数线性 scale → 理论上支持无限长度
  - 计算和通信可以重叠

使用：Gemini 1.5 (1M context) 可能使用类似方案
```

### 3.3 Context Compression（上下文压缩）

```
不是让模型处理更长的序列，而是压缩输入：

1. 摘要压缩：
   将长文档先用 LLM 摘要 → 把摘要放入上下文

2. Token 压缩：
   [10000 tokens 的文档] → 压缩成 [500 个"超级 token"]
   代表：ICAE, AutoCompressor

3. Retrieval + 压缩：
   长文档存入向量数据库 → 检索相关部分 → 只把相关部分放入上下文
   本质就是 RAG！

4. 分层处理：
   第一遍：快速浏览全文，标记重要段落
   第二遍：精读重要段落
```

## 4. 工程挑战

### 4.1 KV-Cache 管理

```
问题：128K context 的 KV-Cache 可能占 40+ GB

解决方案：
  1. PagedAttention (vLLM)
     像操作系统的虚拟内存，按需分配 KV-Cache 的物理内存

  2. KV-Cache 量化
     将 KV-Cache 从 FP16 量化到 INT8/INT4 → 内存减半/四分之一

  3. KV-Cache 驱逐
     保留"重要"的 KV，驱逐不重要的
     H2O (Heavy Hitter Oracle): 保留注意力分数高的 token 的 KV

  4. 跨请求 KV-Cache 复用
     多个请求共享相同的 system prompt → 共享对应的 KV-Cache
     Prefix Caching: 缓存公共前缀的 KV-Cache
```

### 4.2 "Lost in the Middle" 问题

```
现象：
  当上下文很长时，模型对中间位置的信息关注度明显下降
  开头和结尾的信息被更好地利用

实验：
  在长文档中不同位置插入关键信息
  → 放在开头/结尾时准确率高
  → 放在中间时准确率显著下降

原因：
  - 注意力模式偏向开头（初始 token 的 KV 被频繁关注）
  - 位置编码在中间区域区分度不够

缓解：
  - 将重要信息放在上下文的开头或结尾
  - RAG 时对检索结果重排序
  - 训练时增加长文本中间位置的监督
```

## 5. 主流模型的长上下文能力

| 模型 | 最大上下文 | 位置编码 | 关键技术 |
|------|-----------|---------|---------|
| GPT-4 Turbo | 128K | 未公开 | - |
| Claude 3.5 | 200K | 未公开 | 近乎完美的 Needle-in-Haystack |
| Gemini 1.5 Pro | 1M-2M | 未公开 | 可能用 Ring Attention |
| LLaMA-3.1 | 128K | RoPE + 插值 | 渐进式训练扩展 |
| DeepSeek-V3 | 128K | YaRN | MLA 压缩 KV |
| Mistral | 32K | RoPE + Sliding Window | 4K 窗口 × 多层叠加 |
| Qwen-2.5 | 128K | YaRN | 动态 NTK |

## 6. 面试常问

### Q1: 如何将一个 4K 上下文的模型扩展到 128K？

**答**：(1) 位置编码：用 Position Interpolation 或 YaRN 修改 RoPE，使位置编码能表示更长距离；(2) 注意力优化：用 Flash Attention 减少内存，Sliding Window 降低复杂度；(3) KV-Cache：用 PagedAttention 管理内存，量化减小体积；(4) 训练：用渐进式方法——先在中等长度微调，再扩展到全长度。

### Q2: "Lost in the Middle" 是什么？怎么缓解？

**答**：长上下文中，模型对中间位置的信息关注度下降，更偏向开头和结尾。缓解方法：(1) 将重要信息放在上下文开头/结尾 (2) RAG 检索结果重排序 (3) 训练时增加中间位置的监督信号 (4) 修改注意力机制（如增加中间位置的 bias）。

### Q3: RoPE 外推和插值的区别？

**答**：外推是直接用训练时的 RoPE 公式处理更长位置（通常效果差，因为训练时没见过这些位置的角度值）。插值是将长位置线性压缩到训练范围内（如 32K 压缩到 4K 范围），保证位置值在训练见过的分布内。YaRN 进一步改进：对不同频率的维度采用不同策略。

---

> ⬅️ [上一节：Test-time Compute](./12-test-time-compute.md) | [返回概览](./README.md) | ➡️ [下一节：LLM-as-Judge](./14-llm-as-judge.md)
