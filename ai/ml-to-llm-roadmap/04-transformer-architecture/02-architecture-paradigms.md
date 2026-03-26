# 4.2 三种架构范式（Day 4）

> **一句话定位**：Encoder-only (BERT)、Decoder-only (GPT)、Encoder-Decoder (T5) 三种范式各有所长，但 Decoder-only 最终胜出成为大模型的统一架构。

---

## 目录

- [1. 三种范式对比](#1-三种范式对比)
- [2. Encoder-only (BERT)](#2-encoder-only-bert)
- [3. Decoder-only (GPT)](#3-decoder-only-gpt)
- [4. Encoder-Decoder (T5)](#4-encoder-decoder-t5)
- [5. 为什么 Decoder-only 胜出](#5-为什么-decoder-only-胜出)
- [6. 面试常问](#6-面试常问)

---

## 1. 三种范式对比

| | Encoder-only | Decoder-only | Encoder-Decoder |
|--|-------------|-------------|----------------|
| **代表** | BERT, RoBERTa | GPT, LLaMA | T5, BART |
| **Attention** | 双向（全部可见）| 单向（因果掩码）| 编码双向 + 解码单向 |
| **训练任务** | MLM（完形填空）| CLM（下一词预测）| 多种任务 |
| **适合** | 理解任务 | **生成任务** ⭐ | 翻译、摘要 |
| **大模型趋势** | ❌ 非主流 | ⭐ **绝对主流** | ❌ 用得少 |
| **可扩展性** | 一般 | ⭐ 最好 | 一般 |

---

## 2. Encoder-only (BERT)

```
输入: "今天 [MASK] 真 好"
Attention: 每个 token 可以看到所有其他 token（双向）

     今天  [M]  真   好
今天  ✅   ✅   ✅   ✅
[M]   ✅   ✅   ✅   ✅    ← 全部可见
真    ✅   ✅   ✅   ✅
好    ✅   ✅   ✅   ✅

优点：理解能力强（双向上下文）
缺点：不能自回归生成
用途：Embedding 模型、分类、NER、Reranker
```

---

## 3. Decoder-only (GPT)

```
输入: "今天 天气 真"
目标: 预测 "好"
Attention: 每个 token 只能看到自己和之前的（因果掩码）

     今天  天气  真   好
今天  ✅   ❌   ❌   ❌
天气  ✅   ✅   ❌   ❌    ← 只能看左边
真    ✅   ✅   ✅   ❌
好    ✅   ✅   ✅   ✅

优点：天然适合生成，训练简单高效
缺点：单向（但大规模补偿了这个劣势）
用途：GPT、LLaMA、ChatGPT 等所有主流大模型
```

---

## 4. Encoder-Decoder (T5)

```
Encoder: 双向编码输入
Decoder: 单向生成输出 + Cross-Attention 看 Encoder

T5 的统一格式：text-to-text
  翻译: "translate English to Chinese: Hello" → "你好"
  摘要: "summarize: [文章]" → "摘要"
  分类: "classify: [文本]" → "positive"

所有任务都变成 text-to-text → 统一的训练框架
```

---

## 5. 为什么 Decoder-only 胜出

### 5.1 根本原因

```
1. 训练效率高
   - CLM 每个 token 都可以作为预测目标 → 数据利用率 100%
   - MLM 只有 15% 的 token 是预测目标 → 数据利用率低

2. 大规模 Scaling 效果最好
   - Decoder-only 的 Scaling Law 最清晰
   - 同样算力下，Decoder-only 达到最好的效果

3. 统一性
   - 理解和生成都可以做（大模型足够大后理解能力也很强）
   - 不需要区分编码器和解码器

4. 自回归范式自然
   - 语言本身就是从左到右产生的
   - 对话、写作都是自回归过程
```

### 5.2 BERT 类模型还有用吗？

```
✅ 仍然有用的场景：
  - Embedding 模型（Sentence-BERT, BGE）
  - 分类任务（情感分析）
  - Cross-Encoder（Reranking）
  - 小规模高效部署

❌ 被 Decoder-only 取代的场景：
  - 通用对话
  - 内容生成
  - 复杂推理
```

---

## 6. 面试常问

### Q1: BERT 和 GPT 的区别？

**答**：
- **架构**：BERT = Encoder-only（双向），GPT = Decoder-only（单向因果掩码）
- **训练**：BERT = MLM（完形填空），GPT = CLM（下一词预测）
- **适用**：BERT 适合理解（分类、Embedding），GPT 适合生成
- **趋势**：大模型时代 GPT 式的 Decoder-only 是绝对主流

### Q2: 为什么大模型都是 Decoder-only？

**答**：(1) CLM 训练数据利用率高 (2) Scaling 效果最好 (3) 统一了理解和生成 (4) 自回归范式更自然。

### Q3: T5 的 text-to-text 思想有什么影响？

**答**：T5 证明了所有 NLP 任务都可以统一为文本到文本的格式。虽然 T5 本身是 Encoder-Decoder，但这个「统一」思想被 GPT 继承——GPT 通过指令跟随（instruction following）实现了同样的统一性。

---

## 📖 推荐学习路径

1. 重点理解三种范式的 Attention 区别（Mask 不同）
2. 理解 Decoder-only 胜出的原因
3. 知道 BERT 在哪些场景仍然有价值

> ⬅️ [上一节：Transformer 核心](./01-transformer-core.md) | [返回概览](./README.md) | ➡️ [下一节：Attention 变体](./03-attention-variants.md)
