# 模型演进：BERT、GPT、T5 给今天留下了什么

## 这篇解决什么问题

学习 BERT、GPT、T5 不是为了背模型年表，而是为了理解三类架构和训练目标如何影响今天的模型选择：encoder-only 擅长理解，decoder-only 擅长生成，encoder-decoder 擅长输入到输出的转换。这一篇解决的问题是：模型历史如何帮助你解释现代 LLM 为什么多采用 decoder-only，并理解旧模型在今天的位置。

## 学前检查

读这篇前，建议先补：

- [Transformer 架构变体](../04-transformer-foundations/07-transformer-architecture-variants.md)
- [Decoder-only 与生成](../04-transformer-foundations/08-decoder-only-generation.md)
- 如果你想看更完整历史，再读 [旧版预训练模型历史](../05-pretrained-models/)

## 概念为什么出现

Transformer 不是只能做聊天模型。早期预训练模型面对的问题不同：

- 搜索、分类、抽取需要强理解能力。
- 文本续写和开放生成需要从左到右生成。
- 翻译、摘要、问答等任务需要把输入序列转换成输出序列。

BERT、GPT、T5 分别代表了这些问题下的典型答案。理解它们，是为了把“模型家谱”压缩成架构和训练目标的判断。

## 最小心智模型

三类模型可以这样记：

```text
BERT: 看完整输入，做理解和表示
GPT: 只看左侧上下文，逐 token 生成
T5: 编码输入，再解码输出，把任务统一成 text-to-text
```

历史主线则是：

```text
pretrain + finetune
-> pretrain + prompt / in-context learning
-> pretrain + SFT + preference alignment
```

## 最小例子

同一个任务“判断影评情绪”，三类模型的输入输出形态不同：

```text
BERT:
输入: [CLS] This movie is surprisingly good. [SEP]
输出: [CLS] 表示接分类头 -> positive

GPT:
输入: Review: This movie is surprisingly good. Sentiment:
输出: positive

T5:
输入: sentiment: This movie is surprisingly good.
输出: positive
```

BERT 更像把文本编码成可用于分类的表示；GPT 更像继续生成答案；T5 更像把所有任务都改写成“输入文本 -> 输出文本”。

## 原理层

| 模型 | 架构 | 训练目标 | 输入/输出形态 | 现代角色 |
|------|------|----------|---------------|----------|
| BERT | Encoder-only | MLM，预测被 mask 的 token | 输入完整文本，输出 token/句子表示 | 理解、分类、抽取、embedding 历史基础 |
| GPT | Decoder-only | CLM，预测下一个 token | 输入左侧上下文，逐 token 输出 | 现代生成式 LLM 的主线架构 |
| T5 | Encoder-decoder | Text-to-text span corruption | 输入文本，解码输出文本 | 翻译、摘要、统一任务格式的重要范式 |

BERT 的 encoder 可以双向看完整输入，所以适合理解任务。但 MLM 训练目标和自回归生成不完全一致，它不是天然的开放式生成模型。

GPT 的 decoder-only 只看左侧上下文，训练目标和推理生成一致。规模扩大后，GPT 系列展示了 prompt 和 in-context learning：不一定每个任务都要更新权重，可以把任务说明和示例放进上下文，让模型临时适应。

T5 的贡献是把很多 NLP 任务统一成 text-to-text：输入是文本，输出也是文本。这个思想影响了后来的指令数据构造和多任务训练，即使今天很多 chat model 不直接采用 T5 架构。

ChatGPT 之后的主线不是简单的“更大 GPT”，而是 pretraining 之后加入 SFT 和偏好对齐，让模型从续写器变成更符合人类交互预期的助手。

## 和应用/面试的连接

面试问“BERT 和 GPT 有什么区别”时，不要只答“一个双向一个单向”。更完整的回答应覆盖：架构、注意力可见性、训练目标、输出形态和适用任务。

工程上，历史也能帮你避免错配：

- 做 embedding、分类或 rerank，不一定需要 decoder-only chat model。
- 做开放生成、对话和工具参数生成，decoder-only LLM 更自然。
- 做翻译、摘要或结构化转换时，encoder-decoder 思想仍然有参考价值。

## 常见误区

| 误区 | 更准确的说法 |
|------|--------------|
| BERT 已经过时，没必要懂 | BERT 代表 encoder-only + MLM，对理解类任务和 embedding 思路仍有解释价值 |
| GPT 只是更大的 BERT | GPT 的架构、训练目标和生成方式都不同 |
| T5 只是翻译模型 | T5 的核心是 text-to-text 统一任务范式 |
| 历史越细越重要 | 对 AI Engineer 来说，重点是架构和训练目标如何影响现代选择 |

## 自测

1. BERT 为什么适合理解任务，但不是天然的开放生成模型？
2. GPT 的 CLM 训练目标为什么和生成过程一致？
3. T5 的 text-to-text 思想解决了什么任务接口问题？
4. 从 pretrain+finetune 到 chat alignment，范式变化在哪里？

## 回到主线

完成本模块后，你应该能串起：预训练提供底座，SFT 塑造指令行为，RLHF/DPO 调整偏好，LoRA/QLoRA/蒸馏负责适配和压缩，BERT/GPT/T5 提供架构历史坐标。后续 Task 3 会把推理、部署和成本拆成新的主线模块；现在如果需要深入旧材料，可参考 [旧版 LLM 核心知识](../06-llm-core/)。
