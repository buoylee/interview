# 5.2 GPT 演进（Day 4-5）

> **一句话定位**：GPT-1 → GPT-2 → GPT-3 的演进展示了「规模即能力」的核心规律，GPT-3 的 In-Context Learning 彻底改变了 NLP 的使用范式。

---

## 工程师导读

> **面试优先级：⭐⭐⭐**
>
> **为什么 LLM 工程师要懂 GPT 演进？**
> - 面试常问："GPT-1/2/3 每代的关键突破是什么？"
> - "什么是 In-Context Learning？" — 理解这个概念是理解 Prompt Engineering 的基础
> - 展现你对 LLM 发展历史的系统性理解
>
> **一句话记忆 GPT 演进**：
> ```
> GPT-1 (117M)  → "预训练+微调"有效！但需要每个任务单独微调
> GPT-2 (1.5B)  → 不微调也能做任务了！(Zero-shot) → 规模带来涌现
> GPT-3 (175B)  → 给几个例子就能学会新任务 (In-Context Learning) → 改变范式
> ```
>
> **先修**：[01-BERT 家族](./01-bert-family.md) + [阶段 4 / 02-三种范式](../04-transformer-architecture/02-architecture-paradigms.md)

---

## 目录

- [1. GPT-1：预训练+微调](#1-gpt-1预训练微调)
- [2. GPT-2：Zero-shot 能力](#2-gpt-2zero-shot-能力)
- [3. GPT-3：In-Context Learning](#3-gpt-3in-context-learning)
- [4. GPT 演进的关键洞察](#4-gpt-演进的关键洞察)
- [5. 面试常问](#5-面试常问)

---

## 1. GPT-1：预训练+微调

### 1.1 基本信息

```
GPT-1 (2018, OpenAI)
参数：117M（和 BERT-Base 差不多）
架构：12 层 Transformer Decoder
训练数据：BooksCorpus (~5GB)
```

### 1.2 核心贡献

```
训练范式：
  阶段 1: 无监督预训练（在大量文本上做下一词预测）
  阶段 2: 有监督微调（在标注数据上微调）

和 BERT 同年（2018），但方向不同：
  BERT: 双向理解 → 面向理解任务
  GPT:  单向生成 → 面向生成任务
  
当时 BERT 效果更好 → GPT 路线一度被认为不如 BERT
```

### 1.3 和 BERT 的对比

| | GPT-1 | BERT |
|--|-------|------|
| 方向 | 单向（左→右）| 双向 |
| 预训练 | CLM（下一词预测）| MLM + NSP |
| 微调 | 需要 | 需要 |
| 效果 | 略差 | 略好 |

---

## 2. GPT-2：Zero-shot 能力

### 2.1 基本信息

```
GPT-2 (2019, OpenAI)
参数：1.5B（比 GPT-1 大 13 倍）
训练数据：WebText (~40GB, 来源于 Reddit 高赞链接)
```

### 2.2 核心发现 ⭐

```
惊人发现：不用微调，GPT-2 也能做任务！

Zero-shot（零样本）：
  输入："Translate English to French: cheese =>"
  输出："fromage"
  
  没有专门训练翻译！只是在预训练时见过类似格式的文本

论文标题："Language Models are Unsupervised Multitask Learners"
→ 语言模型在预训练时隐式地学会了多种任务
```

### 2.3 关键启示

```
1. 更大的模型 → 涌现出新能力（Zero-shot）
2. 不需要为每个任务微调 → 一个模型做多件事
3. 任务可以用自然语言描述 → "翻译成法语: xxx"

这预示了 GPT-3 的 prompt 范式和后来的 ChatGPT
```

### 2.4 争议

```
OpenAI 一度不公开 1.5B 模型，担心被滥用生成虚假内容
→ 首次引发 AI 安全的公众讨论
→ 后来全部开源
```

---

## 3. GPT-3：In-Context Learning

### 3.1 基本信息

```
GPT-3 (2020, OpenAI)
参数：175B（比 GPT-2 大 117 倍！）
训练数据：~570GB（Common Crawl + 书籍 + 维基百科）
训练成本：约 460 万美元（当时）
```

### 3.2 核心突破：In-Context Learning ⭐⭐

```
不修改模型参数，只通过输入示例让模型学会新任务：

Zero-shot（0 个示例）：
  "将以下文本翻译成中文: Hello world"

One-shot（1 个示例）：
  "Hello → 你好
   Good morning →"

Few-shot（几个示例）：
  "Happy → 高兴
   Sad → 悲伤
   Beautiful →"

模型通过「看示例」学会了模式 → 不需要梯度更新！
```

### 3.3 In-Context Learning 的理论争议

```
为什么 ICL 有效？目前有几种假说：

1. 隐式梯度下降假说：
   - 看示例 ≈ 在 Attention 中隐式地做了一步梯度下降
   - Transformer 的前向传播 ≈ 一种优化过程

2. 贝叶斯推断假说：
   - 模型在预训练时见过各种"格式"
   - Few-shot 示例帮助模型识别出是哪种"格式"
   - 然后按这个格式输出

3. 任务识别假说：
   - 预训练数据中有各种任务的数据
   - 示例帮模型识别当前是什么任务
   - 然后调用预训练时学到的能力

没有定论，仍在研究中
```

### 3.4 GPT-3 的局限

```
1. 不能对话（没人教它怎么对话）→ 后来 InstructGPT/ChatGPT 解决
2. 容易生成有害内容 → 需要对齐(Alignment)
3. 不能遵循复杂指令 → 需要 SFT
4. 175B 参数太大 → 推理成本高
5. 闭源 → 研究受限
```

---

## 4. GPT 演进的关键洞察

### 4.1 规模驱动

```
GPT-1:   117M  → 需要微调才能做任务
GPT-2:   1.5B  → Zero-shot 涌现
GPT-3:   175B  → Few-shot 接近微调效果

参数量增大 ~1500 倍 → 新能力涌现
这就是后来 Scaling Law 的实践验证
```

### 4.2 范式转换

```
GPT-1 时代：预训练 → 微调 → 做任务
  每个任务都需要标注数据和微调
  
GPT-3 时代：预训练 → 写 Prompt → 做任务
  不需要标注数据，不需要微调
  用自然语言"告诉"模型要做什么

ChatGPT 时代（阶段6）：预训练 → SFT → RLHF → 做任务
  真正能对话、遵循指令、安全对齐
```

### 4.3 时间线

```
2018.06  GPT-1   (117M)   → 预训练+微调
2018.10  BERT    (340M)   → MLM, 双向
2019.02  GPT-2   (1.5B)   → Zero-shot
2019.07  RoBERTa (355M)   → 更好的 BERT
2020.05  GPT-3   (175B)   → In-Context Learning
2022.01  InstructGPT       → SFT + RLHF
2022.11  ChatGPT           → 改变世界
```

---

## 5. 面试常问

### Q1: GPT-1/2/3 每一代的关键突破是什么？

**答**：
- **GPT-1**：证明了「预训练+微调」范式的有效性
- **GPT-2**：Zero-shot 能力涌现，不需要微调也能做任务
- **GPT-3**：In-Context Learning，通过 few-shot 示例在输入中学习，效果接近微调

### Q2: 什么是 In-Context Learning？为什么有效？

**答**：不修改模型参数，只在输入中提供几个示例，让模型从示例中学会任务模式。有效原因仍有争议，主要假说包括：隐式梯度下降、贝叶斯推断（识别任务类型）、从预训练数据中回忆相关模式。

### Q3: GPT 和 BERT 选谁？

**答**：
- 需要**生成**（对话、写作）→ GPT（Decoder-only）
- 需要**理解**（分类、Embedding、Reranking）→ BERT（Encoder-only）
- 大模型时代：GPT 式 Decoder-only 是绝对主流（足够大时理解能力也很强）
- BERT 在 Embedding 和分类的小规模高效场景仍有价值

### Q4: 从 GPT-1 到 GPT-3，参数量增大了多少？带来了什么变化？

**答**：从 117M 到 175B，增大约 1500 倍。最大变化是能力的质变：GPT-1 需要微调，GPT-2 出现 Zero-shot，GPT-3 出现 In-Context Learning。这就是后来 Scaling Law 和涌现能力的早期证据。

---

## ⏭️ 下一节预告

最后一节讲几个改变游戏规则的 **里程碑模型**：T5 统一了任务格式、CLIP 开启了多模态、以及 NLP 四次范式转换的完整故事。学完这一节，你就有了从特征工程到 ChatGPT 的完整时间线。

> ⬅️ [上一节：BERT 家族](./01-bert-family.md) | [返回概览](./README.md) | ➡️ [下一节：里程碑 & 范式转换](./03-milestones.md)
