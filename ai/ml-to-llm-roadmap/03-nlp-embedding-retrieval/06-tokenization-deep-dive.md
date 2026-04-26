# 3.6 Tokenization 算法深度解析

> **一句话定位**：Tokenization 决定了 LLM "看到"什么，是文本进入模型的第一步，面试中经常要求解释 BPE 算法流程甚至手写伪代码。

---

## 工程师导读

> **面试优先级：⭐⭐⭐** — BPE 算法经常被要求现场讲解
>
> **为什么 LLM 工程师要懂 Tokenization？**
> - 面试常见题："解释 BPE 算法的训练和推理过程" — 甚至可能要求写伪代码
> - 理解为什么中文调 API 比英文贵（同样的文本中文需要更多 token）
> - 理解为什么 LLM 数学能力差（数字被拆成了碎片）
> - 选模型时需要考虑词表大小和语言覆盖度
>
> **本节核心要点**：
> 1. BPE = 从字符开始，反复合并最高频的相邻对 → 面试能讲清这一句就够了
> 2. Byte-level BPE（GPT 用的）= 以字节为基本单元 → 永远不会 OOV
> 3. 词表大 → 序列短（省钱）但 Embedding 层参数多 → 权衡
> 4. Tokenization 直接影响多语言效率和 API 成本
>
> **先修**：[01-文本表示](./01-text-representation.md)

---

## 1. 为什么 Tokenization 重要？

```
输入文本 → Tokenizer → Token IDs → Embedding → Model

Tokenizer 决定了：
  - 模型的"词汇表"是什么
  - 同样的文本被拆成多少个 token（影响上下文长度利用率）
  - 未知词 (OOV) 怎么处理
  - 多语言能力（中文是按字还是按词？）
  - 推理成本（token 越多 → 推理越慢越贵）
```

## 2. 演进路线

```
Word-level → Character-level → Subword (主流)
  "猫在吃鱼"     "猫","在","吃","鱼"     "猫在", "吃鱼"

Word-level 问题：
  - 词表巨大（英文 50 万+词）
  - OOV 无法处理（新词、拼写错误）

Character-level 问题：
  - 序列太长（一个词变成多个字符 → 浪费上下文窗口）
  - 单个字符缺乏语义

Subword 方案（BPE/WordPiece/Unigram）：
  - 高频词保持完整
  - 低频词拆成子词
  - 兼顾词表大小和序列长度
```

## 3. BPE (Byte Pair Encoding) ⭐⭐ 面试核心

### 3.1 训练过程（构建词表）

```
输入语料: "hug", "hug", "pug", "pun", "bun", "hugs"

Step 0: 初始化为字符级
  词表: {h, u, g, p, n, b, s, </w>}
  语料表示: h u g</w>, h u g</w>, p u g</w>, p u n</w>, b u n</w>, h u g s</w>

Step 1: 统计所有相邻对 (bigram) 的频率
  (h, u): 3   (u, g): 5   (g, </w>): 3   (p, u): 2
  (u, n): 2   (b, u): 1   (g, s): 1     (s, </w>): 1

  最高频: (u, g) = 5 → 合并为 "ug"

Step 2: 更新语料
  h ug</w>, h ug</w>, p ug</w>, p u n</w>, b u n</w>, h ug s</w>

  统计: (h, ug): 3   (ug, </w>): 3   (p, ug): 1   ...
  最高频: (h, ug) = 3 → 合并为 "hug"

Step 3: 更新语料
  hug</w>, hug</w>, p ug</w>, p u n</w>, b u n</w>, hug s</w>

  统计: (hug, </w>): 2   (u, n): 2   ...
  选 (hug, </w>) → 合并为 "hug</w>"

... 重复直到词表达到目标大小（如 32000、50000）

最终词表: {h, u, g, p, n, b, s, </w>, ug, hug, hug</w>, un, ...}
```

### 3.2 推理过程（编码文本）

```
输入: "hugging"

1. 将文本拆成字符: h u g g i n g
2. 按照训练时的合并顺序，依次应用合并规则:
   h u g g i n g
   → h ug g i n g    (规则1: u+g→ug)
   → hug g i n g     (规则2: h+ug→hug)
   → hug g i ng      (假设 n+g→ng 在规则中)
   → hug g ing       (假设 i+ng→ing)
   → hugg ing        (假设 hug+g→hugg)
   ...
3. 最终得到 token 序列: ["hugg", "ing"]
4. 查词表得到 ID: [12345, 6789]
```

### 3.3 BPE 伪代码 ⭐

```python
def train_bpe(corpus, vocab_size):
    # 初始化：每个字符是一个 token
    vocab = set(all characters in corpus)
    merges = []  # 记录合并顺序

    # 将语料转为字符序列
    words = [list(word) + ['</w>'] for word in corpus]

    while len(vocab) < vocab_size:
        # 1. 统计所有相邻 pair 的频率
        pairs = count_pairs(words)

        # 2. 找到最高频的 pair
        best_pair = max(pairs, key=pairs.get)

        # 3. 在语料中执行合并
        words = merge_pair(words, best_pair)

        # 4. 更新词表和合并规则
        new_token = best_pair[0] + best_pair[1]
        vocab.add(new_token)
        merges.append(best_pair)

    return vocab, merges

def encode(text, merges):
    tokens = list(text)
    for (a, b) in merges:  # 按训练时的顺序应用
        i = 0
        while i < len(tokens) - 1:
            if tokens[i] == a and tokens[i+1] == b:
                tokens[i] = a + b
                del tokens[i+1]
            else:
                i += 1
    return tokens
```

## 4. Byte-level BPE (GPT-2/3/4, LLaMA)

```
改进：不用字符作为基本单元，而用字节 (byte)

优势：
  - 基本词表只有 256 个 (0x00-0xFF)
  - 任何 UTF-8 文本都能表示 → 永远没有 OOV
  - 天然支持多语言（中文、日文、emoji 都是字节序列）

GPT-2 词表：50257 tokens
  = 256 bytes + 50000 merges + 1 special token

LLaMA 词表：32000 tokens
  = 256 bytes + ~31744 merges

例："你好" (UTF-8: \xe4\xbd\xa0\xe5\xa5\xbd)
  → 6 个字节 → 通过合并规则 → 可能 2-3 个 tokens
```

## 5. WordPiece (BERT)

```
和 BPE 的区别：选择合并 pair 的标准不同

BPE:       选频率最高的 pair
WordPiece: 选使语言模型似然度提升最大的 pair

评分公式:
  score(a, b) = freq(ab) / (freq(a) × freq(b))

  → 不只看共现频率，还考虑各自的独立频率
  → "th" 虽然频率高，但 t 和 h 各自也频率高，所以分数不一定最高
  → 倾向于合并"在一起比单独出现更有意义"的 pair

特殊标记：
  子词前缀用 "##" 表示
  "playing" → ["play", "##ing"]
  "unbelievable" → ["un", "##believ", "##able"]
```

## 6. Unigram (SentencePiece, T5)

```
和 BPE/WordPiece 相反的思路：

BPE:     从小词表开始，不断合并（自底向上）
Unigram: 从大词表开始，不断删减（自顶向下）

过程：
  1. 初始化一个很大的候选词表（所有可能的子串）
  2. 为每个 token 赋予概率（基于 EM 算法）
  3. 计算删除每个 token 对语料似然度的影响
  4. 删除影响最小的 token（保留重要的）
  5. 重复直到词表达到目标大小

优势：
  - 同一文本可能有多种分词方式 → 训练时随机采样 → 正则化效果
  - 概率模型 → 可以计算分词的概率
```

## 7. SentencePiece

```
不是新的分词算法，而是一个框架/工具：

核心特点：
  1. 将空格视为普通字符（用 ▁ 替代空格）
     "Hello World" → "▁Hello", "▁World"
     → 不依赖预分词 → 语言无关

  2. 支持 BPE 和 Unigram 两种算法

  3. 可逆性：tokens → 原始文本 无损还原

使用模型：
  T5, LLaMA, Mistral 等都用 SentencePiece

为什么重要：
  - 语言无关设计 → 多语言模型的基础
  - 不需要预分词工具（中文不需要先分词再 tokenize）
```

## 8. 对比总结

| 特性 | BPE | WordPiece | Unigram | Byte-level BPE |
|------|-----|-----------|---------|----------------|
| **方向** | 自底向上 | 自底向上 | 自顶向下 | 自底向上 |
| **合并标准** | 最高频 pair | 最大似然提升 | 删除最小影响 | 最高频 pair |
| **基本单元** | 字符 | 字符 | 候选子串 | 字节 (256) |
| **OOV** | 可能 | 可能 | 不可能 | 不可能 |
| **多语言** | 需要大词表 | 需要大词表 | 较好 | 天然支持 |
| **代表模型** | GPT-2 (原版) | BERT | T5 | GPT-3/4, LLaMA |

## 9. 词表大小的权衡 ⭐

```
词表小（如 8K）：
  ✅ Embedding 层参数少
  ❌ 序列变长（同样文本需要更多 token）
  ❌ 语义粒度粗

词表大（如 128K）：
  ✅ 序列更短 → 更高效利用上下文窗口
  ✅ 更好的语义粒度
  ❌ Embedding 层参数多（vocab_size × hidden_dim）
  ❌ softmax 计算更重（输出层 = vocab_size 个类别）

主流选择：
  BERT: 30522
  GPT-2: 50257
  LLaMA: 32000
  LLaMA-3: 128256（大幅扩展，提升多语言和代码效率）
  Qwen-2: 151643

趋势：词表越来越大
  → 提高 token 效率（同样文本更少 token → 省成本 + 更长上下文）
  → 尤其对非英语和代码更友好
```

## 10. Tokenization 对 LLM 的实际影响 ⭐

```
1. 多语言效率差异
   "Hello World" → 2 tokens (英文友好)
   "你好世界"     → 4-6 tokens (中文不友好 → 中文用户消耗更多 token)

   这就是为什么 LLaMA-3 扩大词表的原因之一

2. 数学和代码
   "123456" 可能被拆成 "123" + "456" → 模型"看不到"完整数字
   → 影响数学推理能力（数字被拆开后失去位置信息）

3. Token 边界影响
   "Unfortunately" → ["Un", "fortunately"] 或 ["Unfor", "tunately"]
   不同的拆法影响模型对词义的理解

4. 计费和限制
   API 按 token 计费 → Tokenizer 效率直接影响成本
   上下文窗口是 token 数限制 → 同样 128K 窗口，高效 tokenizer 能放更多文本
```

## 11. 面试常问

### Q1: 解释 BPE 算法的训练和推理过程

**答**：训练时从字符级开始，反复统计所有相邻 pair 的频率，合并最高频的 pair 形成新 token，直到词表达到目标大小。推理时按训练得到的合并顺序，依次对输入文本执行合并。时间复杂度训练 O(V × N)，推理 O(M × L)，V 是词表大小，N 是语料大小，M 是合并规则数，L 是序列长度。

### Q2: BPE 和 WordPiece 的区别？

**答**：核心区别在合并标准。BPE 选频率最高的 pair；WordPiece 选使整体似然度提升最大的 pair（freq(ab) / freq(a)×freq(b)）。WordPiece 更倾向合并"在一起比各自独立更有意义"的组合，而非仅看共现次数。

### Q3: 为什么 GPT 系列用 Byte-level BPE？

**答**：基本单元是字节（256 个），任何 UTF-8 文本都能表示，永远不会 OOV。天然支持多语言和特殊字符，不需要针对特定语言做预处理。代价是非 ASCII 文本（如中文）的 token 效率较低。

### Q4: 词表大小怎么选？有什么权衡？

**答**：词表大 → 序列短、语义粒度好，但 Embedding 层和输出 softmax 更重；词表小 → 参数少，但序列长、效率低。趋势是词表越来越大（LLaMA-3 扩到 128K），因为推理时 token 效率比训练时参数成本更重要。

### Q5: Tokenization 对 LLM 多语言能力有什么影响？

**答**：如果训练语料以英文为主，BPE 学到的合并规则偏向英文子词。同样语义的中文文本可能需要 2-3 倍的 token 数，导致：(1) 中文用户 API 成本更高 (2) 同等上下文窗口能放的中文内容更少 (3) 需要更大词表和更多中文数据来改善。

---

## ⏭️ 回到新版路线

如果你是为了补 tokenization 细节读到这里，下一步优先回到 [Transformer 必要基础](../04-transformer-foundations/)；如果目标是应用系统，再进入 [RAG 与检索系统](../01-rag-retrieval-systems/) 或 [生成控制](../03-generation-control/)。

> ⬅️ [上一节：受控生成](./05-controlled-generation.md) | [返回旧版 NLP/Embedding 概览](./README.md) | 回到新版主线：[Transformer 必要基础](../04-transformer-foundations/)
