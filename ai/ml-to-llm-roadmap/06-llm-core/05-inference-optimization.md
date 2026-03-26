# 6.5 推理优化 & 长上下文（Day 10-11）⭐⭐⭐

> **一句话定位**：KV-Cache、量化、推测解码、vLLM 是降低推理成本的核心技术；上下文长度从 2K 到 200K 的技术路径。

---

## 1. KV-Cache ⭐⭐⭐ 面试必考

### 1.1 问题

```
自回归生成：每次生成 1 个 token，需要重新计算所有前面 token 的 Attention
  → token 1-100 的 K, V 在生成 token 101 时重新计算了
  → token 1-101 的 K, V 在生成 token 102 时又重新计算了
  → 大量重复计算！
```

### 1.2 KV-Cache 方案

```
把已经计算过的 K, V 缓存起来：

生成 token 101 时：
  K = [K₁, K₂, ..., K₁₀₀, K₁₀₁_new]  ← 前 100 个从 cache 取
  V = [V₁, V₂, ..., V₁₀₀, V₁₀₁_new]
  只需计算 Q₁₀₁, K₁₀₁, V₁₀₁ → 和所有 K 做 Attention

没有 KV-Cache: 每步 O(n²)   → 总共 O(n³)
有 KV-Cache:   每步 O(n)    → 总共 O(n²)
```

### 1.3 KV-Cache 占用

```
KV-Cache 大小 = 2 × n_layers × n_kv_heads × seq_len × d_head × 2bytes

LLaMA-70B (GQA 8组):
  2 × 80 × 8 × 4096 × 128 × 2 ≈ 1.3 GB

→ 这就是为什么 GQA/MLA 很重要（减少 KV heads = 减少 Cache）
→ 这就是为什么长上下文很贵（seq_len ↑ → Cache ↑）
```

## 2. 量化 (Quantization) ⭐⭐

### 2.1 原理

```
FP16: 每个参数 2 bytes → 70B 模型 = 140 GB
INT8: 每个参数 1 byte  → 70B 模型 = 70 GB
INT4: 每个参数 0.5 byte → 70B 模型 = 35 GB ← 单卡 A100 放得下！
```

### 2.2 方法

| 方法 | 类型 | 特点 |
|------|------|------|
| **GPTQ** | 训练后量化(PTQ) | 需要校准数据，4-bit 效果好 |
| **AWQ** | 训练后量化 | 保护重要权重通道 |
| **GGUF** (llama.cpp) | 训练后量化 | CPU/混合推理 |
| **QLoRA** | 量化+微调 | 4-bit 推理 + LoRA 微调 |
| **QAT** | 训练感知量化 | 训练时模拟量化 |

## 3. 推测解码 (Speculative Decoding)

```
问题：大模型每次只生成 1 个 token → 瓶颈是延迟而不是算力

方案：用小模型预测 K 个候选 → 大模型一次验证

小模型(快): "今天" → "天气" → "真" → "好" → "啊" (猜 5 个 token)
大模型(准): 验证 → "天气" ✅ "真" ✅ "好" ✅ "呢" ❌ (接受前 3 个)
                                                    ↑ 从这里重新生成

效果：一次验证接受多个 token → 吞吐提升 2-3x
保证：输出分布和原模型完全一致（数学证明精确）
```

## 4. 推理框架 vLLM ⭐

### 4.1 PagedAttention

```
传统 KV-Cache 问题：预分配连续内存 → 大量浪费

vLLM 的 PagedAttention：
  像操作系统的虚拟内存一样管理 KV-Cache
  - 分成固定大小的"页"
  - 按需分配和回收
  - 支持不同请求共享 KV block

效果：显存利用率从 ~50% → ~95% → 吞吐提升 2-4x
```

### 4.2 Continuous Batching

```
传统 Batching：等一批请求都完成再处理下一批 → 短请求等长请求
Continuous Batching：请求完成就立即替换新请求 → GPU 利用率最大化
```

## 5. 长上下文技术

### 5.1 关键技术路径

| 技术 | 作用 |
|------|------|
| **RoPE 插值** | 位置编码扩展（NTK-aware, YaRN）|
| **Flash Attention** | 不存完整注意力矩阵 |
| **Sliding Window** | 局部注意力减少计算 |
| **Ring Attention** | 跨 GPU 分布式注意力 |
| **稀疏注意力** | 只计算部分位置的注意力 |

### 5.2 长上下文的代价

```
128K 上下文 vs 4K 上下文：
  注意力计算: 1024x (n² scaling)
  KV-Cache: 32x (线性 scaling)
  → 成本大幅增加
  → 使用时要思考是否真的需要这么长
```

## 6. LLM 端到端推理流程 ⭐⭐ 面试常问

> 面试官可能问：「描述一个 token 是怎么从用户输入到最终输出的」

### 6.1 Prefill 阶段（处理输入）

```
用户输入: "什么是 Transformer？"

Step 1: Tokenization
  "什么是 Transformer？" → [1234, 567, 89, 2345, 43]  (token IDs)

Step 2: Embedding Lookup
  token IDs → Embedding 矩阵查表 → (5 × d_model) 向量矩阵

Step 3: 前向传播（所有层，一次性并行处理所有输入 token）
  for layer in transformer_layers:
    x = x + Attention(RMSNorm(x))    # + RoPE, Causal Mask
    x = x + SwiGLU_FFN(RMSNorm(x))
  
Step 4: 取最后一个 token 的输出 → LM Head → logits (vocab_size 维)

Step 5: Logit Processing → softmax → 采样 → 第一个输出 token

★ 同时把所有输入 token 的 K, V 存入 KV-Cache
```

### 6.2 Decode 阶段（逐个生成）

```
Step 6: 循环生成（每次只处理 1 个新 token）
  
  新 token → Embedding → 1 个向量
    ↓
  for layer in transformer_layers:
    Q_new = 新 token 的 Query (1 × d_head)
    K_all = [KV-Cache中的K, K_new]  ← 拼接
    V_all = [KV-Cache中的V, V_new]
    Attention(Q_new, K_all, V_all)   ← Q 只有 1 个，但 K/V 有 n 个
    FFN(...)
    更新 KV-Cache（加入新的 K, V）
    ↓
  LM Head → logits → Temperature → Top-p → 采样 → 新 token
    ↓
  新 token != EOS → 继续循环
  新 token == EOS → 停止

Step 7: 所有生成的 token IDs → Detokenize → 输出文本
```

### 6.3 两阶段的性能特征

```
Prefill (预填充):
  - 处理所有输入 token（一次前向传播）
  - 计算密集型（Compute-bound）
  - 时间 ∝ 输入长度
  - 瓶颈：GPU 算力

Decode (解码):
  - 每步只处理 1 个 token
  - 内存带宽密集型（Memory-bound）← 需要读取整个 KV-Cache
  - 时间 ∝ 输出长度
  - 瓶颈：显存带宽（不是算力！）

这解释了推理优化的方向：
  - Prefill 优化：Flash Attention（减少显存读写）
  - Decode 优化：KV-Cache 压缩（GQA/MLA/量化）、推测解码（减少步数）
```

---

## 7. 面试常问

### Q1: KV-Cache 是什么？为什么需要？

**答**：缓存已计算的 K/V 向量，避免每步重新计算。没有 KV-Cache 每步 O(n²)总共 O(n³)；有了是每步 O(n)总共 O(n²)。但 KV-Cache 会占大量显存，GQA/MLA 等技术就是为了减少其大小。

### Q2: 量化怎么做？对效果影响大吗？

**答**：把 FP16(2字节) 权重压缩为 INT8(1字节) 或 INT4(0.5字节)。GPTQ/AWQ 等方法通过校准数据保护重要权重。4-bit 量化效果损失通常很小（<1% 在大多数任务上），但能把显存需求降低 4 倍。

### Q3: vLLM 的 PagedAttention 是什么？

**答**：借鉴操作系统虚拟内存管理 KV-Cache——按页分配而非预分配连续内存。消除了内存碎片和浪费，使显存利用率从约 50% 提升到 95%，吞吐量提升 2-4 倍。

---

> ⬅️ [上一节：分布式训练](./04-distributed-training.md) | [返回概览](./README.md) | ➡️ [下一节：微调技术](./06-fine-tuning-distillation.md)
