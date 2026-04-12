# 5.3 里程碑 & 范式转换（Day 6-7）

> **一句话定位**：T5 统一了任务格式，CLIP 开启了多模态，自监督学习方法的演进构成了预训练的理论基础。

---

## 工程师导读

> **面试优先级：⭐⭐**
>
> **为什么 LLM 工程师要懂这些？**
> - "NLP 经历了哪些范式转换？" — 展示你对整个领域发展的系统性理解
> - CLIP 是多模态的基石 → LLaVA、GPT-4V、Stable Diffusion 都建立在它之上
> - T5 的 text-to-text 思想直接启发了后来 ChatGPT 的指令跟随
>
> **本节核心要点**：
> 1. T5 = 所有任务统一为 "文本→文本" → ChatGPT 指令跟随的思想先祖
> 2. CLIP = 图文对比学习 → 多模态的起点（了解 zero-shot 分类原理即可）
> 3. CLM 为什么赢了 MLM → 数据利用率 100% vs 15%（这是 Decoder-only 胜出的根本原因之一）
> 4. 四次范式转换 → 特征工程 → 预训练+微调 → Prompt → SFT+RLHF → 面试高频
>
> **先修**：[01-BERT 家族](./01-bert-family.md) + [02-GPT 演进](./02-gpt-evolution.md)

---

## 目录

- [1. T5：统一 Text-to-Text](#1-t5统一-text-to-text)
- [2. CLIP：图文对齐](#2-clip图文对齐)
- [3. 自监督学习方法](#3-自监督学习方法)
- [4. 范式转换总结](#4-范式转换总结)
- [5. 面试常问](#5-面试常问)

---

## 1. T5：统一 Text-to-Text

### 1.1 核心思想

```
T5 = Text-to-Text Transfer Transformer (2019, Google)

所有 NLP 任务都转化为"文本到文本"格式：

翻译：  "translate English to German: That is good" → "Das ist gut"
摘要：  "summarize: [长文本]" → "短摘要"
分类：  "sentiment: This movie is great" → "positive"
问答：  "question: What color? context: The sky is blue" → "blue"
NER:    "ner: John lives in NYC" → "person: John, location: NYC"
```

### 1.2 为什么重要？

```
1. 统一框架：不需要为每个任务设计不同的输出头
2. 多任务学习：同一个模型同时训练多种任务
3. 思想传承：GPT 的指令跟随（Instruction Following）继承了这个思想
   - T5: "summarize: [文本]" → 摘要
   - ChatGPT: "请帮我总结这段文字: [文本]" → 摘要
   本质相同，只是 T5 用固定前缀，ChatGPT 用自然语言指令
```

### 1.3 架构

```
Encoder-Decoder 架构
参数：770M（Base）到 11B（XXL）
训练：C4 数据集（Colossal Clean Crawled Corpus）
```

---

## 2. CLIP：图文对齐

### 2.1 核心思想

```
CLIP = Contrastive Language-Image Pre-training (2021, OpenAI)

用 4 亿图文对做对比学习：
  匹配的图-文对 → 拉近
  不匹配的图-文对 → 推远

  "一只橙色的猫" ──── 🖼️ 猫的照片    → 拉近 ✅
  "一只橙色的猫" ──── 🖼️ 汽车的照片  → 推远 ❌
```

### 2.2 架构

```
图像 → [Vision Encoder (ViT/ResNet)] → 图像 Embedding ↘
                                                        → 对比损失
文本 → [Text Encoder (Transformer)]  → 文本 Embedding ↗

两个 Encoder 共享同一个嵌入空间
```

### 2.3 Zero-shot 图像分类

```
不用训练分类器！用文本描述类别：

类别候选:
  "a photo of a cat"   → 文本 Embedding₁
  "a photo of a dog"   → 文本 Embedding₂
  "a photo of a bird"  → 文本 Embedding₃

测试图像 → 图像 Embedding → 和哪个文本 Embedding 最相似？
→ 分类完成！

新增类别只需要写新的文本描述 → 极其灵活
```

### 2.4 为什么 CLIP 是里程碑？

```
1. 多模态的开端
   → 图像和文本在同一空间对齐
   → 后续做多模态大模型的基础

2. 影响了后续模型
   → LLaVA = CLIP Vision Encoder + LLM
   → GPT-4V = 原生多模态
   → Stable Diffusion 用 CLIP 做文本理解

3. Zero-shot 能力
   → 不用标注就能做图像分类
   → 对比学习的强大证明
```

> 🔑 回顾 [02-深度学习 / 06-其他架构](../02-deep-learning/06-other-architectures.md) 中对比学习的理论基础。

---

## 3. 自监督学习方法

### 3.1 方法总结

| 方法 | 任务 | 代表 | 特点 |
|------|------|------|------|
| **MLM** (Masked LM) | 完形填空 | BERT | 双向理解 |
| **CLM** (Causal LM) | 下一个词预测 | GPT | ⭐ 大模型标准 |
| **Denoising** | 还原被破坏的文本 | T5, BART | 灵活 |
| **Contrastive** | 拉近/推远相似/不同对 | CLIP, SimCLR | 表示学习 |

### 3.2 MLM vs CLM

```
MLM ("完形填空")：
  输入: "今天 [MASK] 真 好"
  预测: "天气"
  特点: 双向，但只有 15% token 作为目标 → 数据利用率低

CLM ("下一个词预测")：
  输入: "今天"         → 预测 "天气"
  输入: "今天 天气"     → 预测 "真"
  输入: "今天 天气 真"   → 预测 "好"
  特点: 单向，但每个 token 都是目标 → 数据利用率 100%

为什么 CLM 赢了：
  1. 数据利用率高（每个 token 都是训练信号）
  2. Scaling 效果更好
  3. 天然适合生成
```

### 3.3 Denoising（去噪）

```
T5 的 Span Corruption：
  原文: "今天天气真好，适合出去玩"
  输入: "今天 <X> 好，<Y> 玩"
  目标: "<X> 天气真 <Y> 适合出去"

BART 的各种破坏方式：
  - Token 遮罩
  - Token 删除
  - 句子打乱
  - 文档旋转

模型学会从各种"破坏"中恢复原文 → 建立强大的文本理解和生成能力
```

---

## 4. 范式转换总结

### 4.1 三次范式转换

```
范式 1: 特征工程 + 浅层模型 (2010s前)
  人工提取特征 → SVM / 随机森林
  
范式 2: 预训练 + 微调 (2018-2020)
  BERT/GPT-1 预训练 → 每个任务微调
  ✅ 减少了特征工程
  ❌ 每个任务需要标注数据和微调

范式 3: 预训练 + Prompt (2020-2022)
  GPT-3 预训练 → 写提示词做任务
  ✅ 不需要微调
  ❌ 不能对话，不够安全

范式 4: 预训练 + SFT + RLHF (2022-)
  GPT预训练 → 指令微调 → 人类对齐
  ✅ 能对话，能遵循指令，更安全
  → 阶段 6 详细展开
```

### 4.2 预训练范式的核心原则

```
1. 自监督 → 利用无标签数据
2. 大规模 → 更大的数据 + 更大的模型 = 更好
3. 通用性 → 一个模型适应多种任务
4. 涌现性 → 量变产生质变（Scaling Law）
```

---

## 5. 面试常问

### Q1: T5 的 text-to-text 思想有什么影响？

**答**：T5 证明所有 NLP 任务都可以统一为文本到文本格式，不需要为每个任务设计不同的输出头。这个思想被 ChatGPT 继承——用自然语言指令代替固定前缀，实现任务统一。

### Q2: CLIP 是怎么实现 zero-shot 图像分类的？

**答**：CLIP 用对比学习让图像和文本共享同一嵌入空间。分类时把类别名写成文本（如 "a photo of a cat"），计算图像 Embedding 和每个类别文本 Embedding 的余弦相似度，最相似的就是预测类别。不需要训练分类器。

### Q3: MLM 和 CLM 的区别？为什么大模型用 CLM？

**答**：MLM 双向但只用 15% token 作为目标；CLM 单向但每个 token 都是目标（数据利用率高）。大模型用 CLM 因为：(1) 高数据利用率 (2) Scaling 效果好 (3) 天然适合生成。

### Q4: NLP 经历了哪些范式转换？

**答**：(1) 特征工程+浅层模型 → (2) 预训练+微调(BERT) → (3) 预训练+提示(GPT-3) → (4) 预训练+SFT+RLHF(ChatGPT)。每次转换都减少了人工干预，增加了模型的自主能力。

---

## ⏭️ 下一阶段预告

恭喜你完成阶段 5！到这里你已经有了从特征工程到 ChatGPT 的完整发展时间线。下一阶段进入 **大模型 LLM 核心知识** — SFT（指令微调）、RLHF（人类对齐）、Scaling Law、LoRA 等。这些是 LLM 工程师面试的最核心内容，也是你日常工作中最直接使用的知识。

> ⬅️ [上一节：GPT 演进](./02-gpt-evolution.md) | [返回概览](./README.md) | ➡️ [下一阶段：大模型 LLM 核心知识](../06-llm-core/)
