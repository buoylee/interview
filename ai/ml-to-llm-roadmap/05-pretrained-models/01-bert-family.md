# 5.1 BERT 家族（Day 1-3）

> **一句话定位**：BERT 开启了预训练语言模型时代，其后续改进版至今仍是 Embedding 模型和分类任务的基础架构。

---

## 工程师导读

> **面试优先级：⭐⭐**
>
> **BERT 在 2024+ 还有用吗？**
> BERT 不能聊天，但在以下场景仍然是最佳选择：
> - Embedding 模型（BGE、E5 都基于 BERT 架构）
> - 分类/NER 任务
> - Cross-Encoder Reranker
> - 小规模高效部署
>
> **本节核心要点**：
> 1. BERT 的 MLM 训练：15% token 被遮掩（80% [MASK] + 10% 随机 + 10% 不变）
> 2. RoBERTa 的核心发现："BERT 没训练够" → Scaling 的早期信号
> 3. DeBERTa = 效果最好的 BERT 变体（解耦注意力）
> 4. 知识蒸馏（DistilBERT）= 大模型教小模型 → 理解蒸馏思想
>
> **先修**：[阶段 4 / 02-三种架构范式](../04-transformer-architecture/02-architecture-paradigms.md)

---

## 目录

- [1. BERT 原版](#1-bert-原版)
- [2. RoBERTa](#2-roberta)
- [3. ALBERT](#3-albert)
- [4. DeBERTa](#4-deberta)
- [5. DistilBERT](#5-distilbert)
- [6. BERT 家族总结](#6-bert-家族总结)
- [7. 面试常问](#7-面试常问)

---

## 1. BERT 原版

### 1.1 核心信息

```
BERT = Bidirectional Encoder Representations from Transformers (2018, Google)

架构：Transformer Encoder-only
参数：Base = 110M, Large = 340M
层数：Base = 12 层, Large = 24 层
隐藏维度：Base = 768, Large = 1024
```

### 1.2 预训练任务

#### MLM (Masked Language Model) ⭐

```
输入：  "今天 [MASK] 真 好"
目标：  预测 [MASK] = "天气"

15% 的 token 被选中：
  80% → [MASK]         "今天 [MASK] 真 好"
  10% → 随机 token     "今天 苹果 真 好"
  10% → 保持不变       "今天 天气 真 好"

为什么不全用 [MASK]？
  → 推理时没有 [MASK] token → 训练推理不一致
  → 随机替换和保持不变让模型学会对所有 token 的表示都保持准确
```

#### NSP (Next Sentence Prediction)

```
输入：[CLS] 句子A [SEP] 句子B
目标：判断 B 是否是 A 的下一句

正样本：真正连续的两句话
负样本：随机配对的两句话

后来发现：NSP 对效果帮助不大（RoBERTa 去掉了）
```

### 1.3 BERT 的微调

```
预训练的 BERT → 加一个任务特定的输出层 → 在标注数据上微调

分类：[CLS] 向量 → 线性层 → softmax
NER：每个 token → 线性层 → 标签
问答：找 start/end 位置

关键：预训练学到了通用语言理解 → 少量标注数据就能适应特定任务
```

### 1.4 BERT 的局限

```
1. 不能生成（Encoder-only，没有自回归能力）
2. [MASK] token 训练推理不一致
3. MLM 只利用 15% 的 token 作为训练信号（低效）
4. 最大长度 512 token
5. NSP 任务后来证明没用
```

---

## 2. RoBERTa

### 2.1 关键改进

```
RoBERTa = Robustly Optimized BERT (2019, Meta/Facebook)

改进        BERT                RoBERTa
NSP任务     有                  去掉 ← 没用
Mask方式    静态（固定mask位置） 动态（每个epoch重新mask）
训练数据    16GB                160GB (10x)
训练步数    较少                更多
Batch Size  256                 8K
```

### 2.2 核心发现

```
BERT 根本没有训练充分！

只要：更多数据 + 更久训练 + 动态 mask + 去掉 NSP
→ 效果显著提升
→ 说明预训练的核心是数据量和训练量，而不是复杂的任务设计
```

> 🔑 这个发现预示了 Scaling Law：更多数据 + 更多计算 = 更好效果。

---

## 3. ALBERT

### 3.1 关键改进

```
ALBERT = A Lite BERT (2019, Google)

目标：减少参数量但保持效果

两个技巧：
1. 嵌入因式分解：V×H → V×E + E×H（E << H）
   词表 30000, H=768: 23M 参数 → V×128 + 128×768 = 3.9M + 0.1M ≈ 4M
   
2. 跨层参数共享：所有 Transformer 层共享同一组参数
   12 层 × 每层参数 → 1 层参数（重复使用 12 次）
   → 参数量大幅减少
```

### 3.2 效果

```
参数量减少 18x（89M → 12M for Base）
效果略降但差距不大
推理速度没有提升（计算量一样，只是参数少）
```

---

## 4. DeBERTa

### 4.1 关键改进 ⭐

```
DeBERTa = Decoupled attention for BERT (2020, Microsoft)

核心：解耦注意力（Disentangled Attention）

标准 BERT：Embedding = Token Embedding + Position Embedding
  → Attention 计算的是混合后的向量

DeBERTa：把内容和位置分开计算 Attention
  Attention = Content-Content + Content-Position + Position-Content

直觉：
  "猫" 和 "狗" 的关系（内容-内容）
  "第一个词" 和 "第三个词" 的关系（位置-位置）
  两种关系分开建模，更精确
```

### 4.2 为什么重要？

```
DeBERTa 在多个 benchmark 上超过了人类水平
是 BERT 家族中效果最好的
Microsoft 的 Embedding 模型 E5 就基于 DeBERTa
```

---

## 5. DistilBERT

### 5.1 知识蒸馏

```
DistilBERT = Distilled BERT (2019, Hugging Face)

教师：BERT-Base (12层, 110M)
学生：DistilBERT (6层, 66M)

蒸馏过程：
  学生模型同时学习：
  1. 硬标签（真实答案）
  2. 软标签（教师模型的 softmax 输出）← 包含更多信息！

温度参数 T：
  高 T → 教师输出更"软"→ 暴露更多类间关系
  例：教师对"猫"预测 0.9，"老虎"0.08，"桌子"0.001
  → 学生学到"猫"和"老虎"相近，和"桌子"无关
```

### 5.2 效果

```
参数量减少 40%（110M → 66M）
速度提升 60%
保留 BERT 97% 的效果
```

> 🔑 知识蒸馏在阶段 6 会详细展开，这里先理解基本思想。

---

## 6. BERT 家族总结

| 模型 | 改进点 | 参数 | 核心价值 |
|------|--------|------|---------|
| **BERT** | MLM + NSP | 110M/340M | 开创者 |
| **RoBERTa** | 更多数据+去NSP+动态mask | 125M/355M | 训练方法优化 |
| **ALBERT** | 参数共享+因式分解 | 12M/18M | 参数效率 |
| **DeBERTa** | 解耦注意力 | 134M/390M | ⭐ 效果最好 |
| **DistilBERT** | 知识蒸馏压缩 | 66M | 轻量部署 |

### 在 LLM 时代的角色

```
BERT 家族不做大模型对话 → 但在以下场景仍然是最佳选择：
  ✅ Embedding 模型（BGE, E5 基于 BERT/DeBERTa）
  ✅ 分类任务（情感分析、意图识别）
  ✅ NER 命名实体识别
  ✅ Cross-Encoder Reranker
  ✅ 小规模高效部署
```

---

## 7. 面试常问

### Q1: BERT 的 MLM 训练具体怎么做的？

**答**：随机选 15% 的 token，其中 80% 替换为 [MASK]、10% 随机替换、10% 不变。模型预测被选中位置的原始 token。不全用 [MASK] 是为了缓解训练和推理的不一致。

### Q2: RoBERTa 对 BERT 做了哪些改进？

**答**：(1) 去掉 NSP (2) 动态 mask (3) 更多数据(10x) (4) 更大 batch (5) 训练更久。核心发现：BERT 没有训练充分，更多数据和计算就能显著提升效果。

### Q3: DeBERTa 的解耦注意力是什么？

**答**：把 token 的内容和位置信息分开计算 Attention。标准 BERT 把两者加在一起再算，DeBERTa 分别算 content-content、content-position、position-content 三种注意力再组合，更精细。

### Q4: 什么是知识蒸馏？DistilBERT 怎么做的？

**答**：用大模型（教师）的 soft label 指导小模型（学生）学习。高温 softmax 的输出包含类间关系信息（比 one-hot 更丰富）。DistilBERT 用 BERT(12层) 蒸馏为 6 层，保留 97% 效果。

---

## ⏭️ 下一节预告

BERT 是"理解"这条路的代表。下一节讲"生成"这条路的代表 — **GPT 的演进**。从 GPT-1（需要微调）到 GPT-3（只要写 prompt），参数量增大 1500 倍带来了质的飞跃。这个故事是理解 Scaling Law 和 ChatGPT 的基础。

> ⬅️ [返回阶段概览](./README.md) | ➡️ [下一节：GPT 演进](./02-gpt-evolution.md)
