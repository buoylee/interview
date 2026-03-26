# 6.7 MoE 混合专家（Day 14）⭐

> **一句话定位**：MoE 让模型参数量很大但每次推理只激活一小部分，实现「大模型的效果，小模型的成本」。

---

## 1. 核心思想

```
Dense 模型：所有参数每次推理都用
MoE 模型：每个 token 只激活部分"专家"

例：8 个 FFN 专家，每次只用 2 个
  总参数 = 8 × FFN_params → 很大
  每次计算 = 2 × FFN_params → 和小模型一样！
```

## 2. 架构

```
标准 Transformer 层:
  Self-Attention → FFN

MoE Transformer 层:
  Self-Attention → Router → [Expert₁, Expert₂, ..., Expert₈] → 加权求和

Router (门控网络):
  输入 token → 线性层 → softmax → top-K 分数
  选择分数最高的 K 个专家

  例：token "猫" → Router 选择 Expert₃ (权重 0.7) + Expert₆ (权重 0.3)
  输出 = 0.7 × Expert₃(x) + 0.3 × Expert₆(x)
```

## 3. 关键挑战

### 3.1 负载均衡 ⭐

```
问题：所有 token 都涌向某个"明星"专家 → 其他专家闲置
  → 训练不充分，效果差

解决：辅助损失 (Auxiliary Load Balancing Loss)
  L_aux = α × Σ (fraction_i × routing_probability_i)
  惩罚不均匀的专家分配
  
DeepSeek-V3 改进：无辅助损失的负载均衡策略
```

### 3.2 Expert Parallelism（专家并行）⭐

```
不同专家放不同 GPU → 需要 All-to-All 通信
  token 根据路由结果发送到对应 GPU → expert 计算 → 结果返回

通信开销是 MoE 的主要工程挑战

All-to-All 通信流程：
  1. Dispatch: 每个 GPU 把自己的 token 发给目标专家所在 GPU
     GPU0 有 token A (需要 Expert₃ 在 GPU1) → 发送到 GPU1
     GPU1 有 token B (需要 Expert₁ 在 GPU0) → 发送到 GPU0

  2. Compute: 每个 GPU 计算收到的 token

  3. Combine: 结果发回原来的 GPU

  → 两次 All-to-All = 巨大的通信开销
  → 这就是为什么 MoE 训练比 Dense 模型更依赖高带宽互联（NVLink/InfiniBand）
```

### 3.3 辅助损失设计细节

```
标准 Auxiliary Loss：
  L_aux = α × N × Σᵢ (fᵢ × Pᵢ)

  fᵢ = 分配给专家 i 的 token 比例
  Pᵢ = 路由到专家 i 的平均概率
  N = 专家数
  α = 损失权重（通常 0.01）

  目标：让 fᵢ 和 Pᵢ 尽量均匀

DeepSeek-V3 的创新（无辅助损失）：
  使用 bias term 替代 auxiliary loss
  给每个专家一个可学习的 bias → 调节路由偏好
  → 不会干扰主损失的梯度 → 训练更稳定

Mixtral 的 Capacity Factor：
  限制每个专家最多处理 C × (N_tokens / N_experts) 个 token
  超出的 token 被"丢弃"（用残差连接兜底）
```

### 3.4 Shared Expert（共享专家）

```
DeepSeek-V2/V3 的设计：

标准 MoE: 所有专家都是可选的（top-K 选择）
共享专家 MoE: 有几个专家始终被激活

例（DeepSeek-V3）：
  256 个路由专家 → top-8 选择
  + 1 个共享专家 → 始终激活

共享专家的作用：
  - 学习通用知识（所有 token 都需要的能力）
  - 路由专家专注于特定领域知识
  - 减少专家间的知识冗余
```

## 4. 代表模型

| 模型 | 专家数 | 激活 | 总参/激活参 |
|------|--------|------|-----------|
| **Mixtral 8x7B** | 8 | top-2 | 47B / 13B |
| **DeepSeek-V2** | 160 | top-6 | 236B / 21B |
| **DeepSeek-V3** | 256 | top-8 | 671B / 37B |
| GPT-4 (传闻) | 16 | top-2 | ~1.8T / ~220B |

## 5. 面试常问

### Q1: MoE 的核心优势？

**答**：参数量大（学到更多知识）但每次推理只激活一小部分专家（计算量相当于小模型）。DeepSeek-V3 总参 671B 但每次只用 37B 的计算量。

### Q2: Router 怎么决定用哪个专家？负载均衡怎么做？

**答**：Router 是一个简单的线性层+softmax，选 top-K 个分数最高的专家。负载均衡通常加辅助损失（L_aux），惩罚专家使用不均匀。DeepSeek-V3 改用 bias term 替代辅助损失，不干扰主损失的梯度，训练更稳定。

### Q3: MoE 的 Expert Parallelism 有什么工程挑战？

**答**：核心是 All-to-All 通信开销。每个 token 需要发送到对应专家所在的 GPU，计算后再发回，两次 All-to-All。需要高带宽互联（NVLink/InfiniBand），是 MoE 训练成本的主要来源之一。

### Q4: DeepSeek-V3 的 MoE 有什么创新？

**答**：三个关键创新：(1) 无辅助损失的负载均衡——用可学习的 bias 替代 auxiliary loss (2) 共享专家——1 个专家始终激活，学通用知识 (3) 256 个路由专家 top-8 激活——总参 671B 但每次只用 37B 计算量。

---

> ⬅️ [上一节：微调技术](./06-fine-tuning-distillation.md) | [返回概览](./README.md) | ➡️ [下一节：高级话题](./08-advanced-topics.md)
