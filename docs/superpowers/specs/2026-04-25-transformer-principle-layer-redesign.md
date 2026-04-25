# Transformer 原理层补强设计

## 背景

当前 `ai/ml-to-llm-roadmap/04-transformer-foundations/06-original-transformer-encoder-decoder.md` 和 `07-transformer-architecture-variants.md` 已经建立了心智模型：Encoder 负责读输入，Decoder 负责生成，Encoder-only / Encoder-Decoder / Decoder-only 对应不同任务形状。

用户反馈是：这种写法能说明“是什么”和“为什么先这样理解”，但还不足以让学习者心里有底。学习者会继续追问：

- Encoder 和 Decoder 里面的数据到底怎么流？
- self-attention、masked self-attention、cross-attention 分别在看谁？
- Encoder-only、Encoder-Decoder、Decoder-only 不只是任务选择不同，它们的训练目标到底有什么差异？
- 为什么 GPT 类 Decoder-only 能成为现代通用 LLM 的主流？

因此需要在现有心智模型层下面补一层“机制层 / 原理层”，让主线文档自身可读，而不是把关键理解交给旧文档链接。

## 设计原则

1. 主线文档必须独立可读
   - 学习者读完 `06/07` 后，应能理解 Encoder / Decoder / Encoder-only / Encoder-Decoder / Decoder-only 的核心机制。
   - 旧文档只能作为深入参考，不能承担主线解释责任。

2. 复用旧文档作为素材库
   - 旧版 `04-transformer-architecture/01-transformer-core.md`、`02-architecture-paradigms.md` 和 `05-pretrained-models/*` 中已有不少有价值内容。
   - 这些内容应被拆解、改写、降密度后放入新主线，而不是原样链接给学习者。

3. 原理层优先解释机制，不追求数学推导完整性
   - 本轮目标是“知道数据怎么走、attention 在看谁、训练目标是什么、为什么结构适合任务”。
   - 公式可以少量出现，但只作为辅助，不把课程变成推导课。

4. 面试笔记继续后置
   - 先让系统学习路径讲顺，再把面试路径和复习笔记建立在主线之上。
   - 不在原理层里过早塞面试问答，避免再次打断学习流。

## 推荐方案

采用“重新编排主线 + 复用旧内容”的方案。

不采用“心智模型层只加旧文档链接”的方案，因为旧文档密度高、范围宽，会重新制造跳跃感。

不采用“完全从零重写”的方案，因为旧文档已经包含 Q/K/V、cross-attention、BERT/GPT/T5 范式、MLM/CLM/T5 text-to-text 等素材，可以作为可靠来源。

## 目标改造范围

### 1. 补强 `06-original-transformer-encoder-decoder.md`

在现有心智模型后增加“原理层：Encoder 和 Decoder 的数据流”。

应讲清：

- Encoder self-attention：
  - 每个 source token 都从 source sequence 中产生 Q/K/V。
  - 因为输入已经完整给定，source token 通常可以双向互看。
  - 输出是每个 source token 的上下文表示。

- Decoder masked self-attention：
  - 每个 target token 从已知 target prefix 中产生 Q/K/V。
  - causal mask 阻止当前位置看到未来 target token。
  - 这解释了为什么 Decoder 能用于逐 token 生成。

- Cross-attention：
  - Query 来自 Decoder 当前生成侧表示。
  - Key/Value 来自 Encoder 的 source 表示。
  - 它回答的是：“我正在生成这个 target token 时，应该回看 source 的哪些部分？”

- 训练和推理差异：
  - 训练时用右移后的 target token，让模型学习预测下一个 token。
  - 推理时没有完整 target，只能把已经生成的 token 继续喂回 Decoder。

### 2. 补强 `07-transformer-architecture-variants.md`

在现有三种范式后增加“原理层：结构选择和训练目标”。

应讲清：

- Encoder-only：
  - 结构上保留双向读取能力。
  - 典型训练目标是 MLM 或其他理解型目标。
  - 输出常用于 token 表示、句向量、分类、匹配、rerank。

- Encoder-Decoder：
  - 结构上保留 source reader 和 target generator。
  - 训练时让 Decoder 根据 source 和已知 target prefix 预测下一个 target token。
  - 适合翻译、摘要、改写、结构化转换等 source-to-target 任务。

- Decoder-only：
  - 结构上把 prompt、上下文、历史、输出统一成一个序列。
  - 典型训练目标是 CLM / next-token prediction。
  - 适合通用生成，因为所有条件都可以放进同一个上下文窗口。

- 为什么现代通用 LLM 多采用 Decoder-only：
  - 训练目标统一。
  - 数据形态简单，海量文本天然适配 next-token prediction。
  - 推理接口统一：给 prefix，继续生成。
  - RAG、工具调用、多轮对话都可以表达成上下文续写问题。

### 3. 旧文档链接降级为深入参考

在 `06/07` 末尾增加“深入参考”，但不要把核心解释外包给它们。

候选引用：

- `../04-transformer-architecture/01-transformer-core.md`
- `../04-transformer-architecture/02-architecture-paradigms.md`
- `../05-pretrained-models/01-bert-family.md`
- `../05-pretrained-models/02-gpt-evolution.md`
- `../05-pretrained-models/03-milestones.md`

链接文案应明确这是“看完主线后再读”，不是主线前置依赖。

## 非目标

- 不重写整个 Transformer 模块。
- 不把 `06/07` 改成公式密集型论文笔记。
- 不在本轮新增完整面试问答文档。
- 不删除旧文档；旧文档暂时保留为参考资料。

## 验收标准

完成后，学习者不点旧文档链接，也应该能回答：

1. Encoder self-attention 和 Decoder masked self-attention 的区别是什么？
2. Cross-attention 中 Q、K、V 分别来自哪里？
3. 为什么训练 Decoder 时要用右移后的 target？
4. Encoder-only、Encoder-Decoder、Decoder-only 的训练目标分别倾向什么？
5. 为什么 Decoder-only 可以把 RAG 文档、用户问题、历史对话放在同一个 prompt 里？
6. 为什么 BERT 适合 embedding/rerank，而 GPT 适合通用生成？

## 风险与控制

- 风险：补充原理后篇幅变长。
  - 控制：每篇只补机制层，公式和历史细节放到旧文档参考中。

- 风险：又变成面试压缩表格。
  - 控制：原理层按数据流和训练目标组织，面试总结后置。

- 风险：旧文档和新主线术语不一致。
  - 控制：新主线统一使用 source sequence、target sequence、self-attention、masked self-attention、cross-attention、MLM、CLM 等术语；旧文档只作为参考。

