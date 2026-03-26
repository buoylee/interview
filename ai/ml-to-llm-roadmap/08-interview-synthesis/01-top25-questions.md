# Top 30 高频面试题 ⭐

> 按知识阶段排列，每题标注对应阶段和难度。答案控制在面试回答的适当长度。
> 🔥 = 2025-2026 新增热点

---

## 基础理论 (阶段 0-2)

### 1. 为什么 Transformer 要除以 √d_k？(⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/01-transformer-core.md)

Q·K 的方差和 d_k 成正比，d_k 大时点积值过大导致 softmax 趋向 one-hot → 梯度消失。除以 √d_k 归一化方差为 1，让 softmax 输出更平滑。

### 2. Batch Normalization 和 Layer Normalization 的区别？(⭐⭐⭐)
> 阶段 2 | [详细](../02-deep-learning/01-neural-network-basics.md)

BN 在 batch 维度归一化（同一特征跨样本），LN 在特征维度归一化（同一样本跨特征）。Transformer 用 LN 因为 (1) 序列长度不同 BN 不适用 (2) LN 不依赖 batch size。

### 3. 什么是 Residual Connection？为什么重要？(⭐⭐⭐)
> 阶段 2 | [详细](../02-deep-learning/04-cnn.md)

y = F(x) + x，输出 = 变换 + 原始输入。梯度至少是 1（不消失），信息可以直接传到底层。没有它，几十层的 Transformer 根本无法训练。

---

## NLP & Embedding (阶段 3-5)

### 4. Word2Vec 和 BERT Embedding 的区别？(⭐⭐⭐)
> 阶段 3 | [详细](../03-nlp-embedding-retrieval/01-text-representation.md)

Word2Vec 是静态向量（一词一向量），BERT 是上下文相关（同词不同义不同向量）。BERT 用 12 层 Transformer 编码，表示能力远超 Word2Vec。

### 5. BPE 分词的训练和推理过程？(⭐⭐⭐⭐)
> 阶段 3 | [详细](../03-nlp-embedding-retrieval/06-tokenization-deep-dive.md)

**训练**：从字符级词表开始，反复统计最高频的相邻 token 对并合并，直到达到目标词表大小。**推理**：按训练时的合并顺序依次对输入文本执行合并。GPT 系列用 Byte-level BPE（基本单元是字节而非字符），永远不会 OOV。WordPiece（BERT 用）区别在于合并标准——选使似然度提升最大的 pair 而非最高频。

**追问：词表大小怎么选？** 大词表→序列短但 Embedding 层重；小词表→参数少但序列长。趋势是越来越大（LLaMA-3 扩到 128K），因为推理时 token 效率比训练时参数成本更重要。

### 6. Embedding 模型怎么训练的？(⭐⭐⭐⭐)
> 阶段 3 | [详细](../03-nlp-embedding-retrieval/02-embedding-theory.md)

基于对比学习(InfoNCE)。正样本对（query 和相关文档）拉近，负样本推远。硬负样本挖掘是关键。架构是 Bi-Encoder（Sentence-BERT）。

### 7. 为什么 RAG 需要 Hybrid Search？(⭐⭐⭐)
> 阶段 3 | [详细](../03-nlp-embedding-retrieval/03-retrieval-theory.md)

BM25 擅长精确关键词匹配，Dense 擅长语义理解，两者互补。RRF 融合只用排名不用分数，不需要归一化。

---

## Transformer (阶段 4)

### 8. 从头讲一遍 Self-Attention (⭐⭐⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/01-transformer-core.md)

X → 生成 Q/K/V → Q·Kᵀ 计算注意力分数 → 除以 √d_k → softmax → 加权求和 V → 输出。多头：分成 h 个子空间并行计算再拼接。

### 9. RoPE 是什么？(⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/01-transformer-core.md)

用旋转矩阵编码相对位置。Q·K 结果只取决于位置差（而非绝对位置）→ 可以插值扩展到更长序列。几乎所有现代开源 LLM 都用。

### 10. MHA、MQA、GQA 的区别？(⭐⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/03-attention-variants.md)

MHA 每头独立 KV（效果好但 Cache 大）；MQA 所有头共享 1 组 KV（Cache 最小但效果降）；GQA 分组共享（折中）。LLaMA 2/3 用 GQA。

### 11. Flash Attention 是什么？(⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/03-attention-variants.md)

分块计算 Attention + online softmax，不存储 n×n 注意力矩阵到 HBM。结果完全精确（不是近似），2-4x 加速。是所有现代 LLM 标配。

### 12. Transformer 有什么替代架构？(⭐⭐⭐)
> 阶段 4 | [详细](../04-transformer-architecture/04-non-transformer.md)

Mamba/SSM：线性复杂度 O(n)，选择性状态空间模型。推理时固定状态 O(1)/step。和 Transformer 的权衡：效率 vs 精确回忆。混合架构(Jamba)可能是最优解。

---

## LLM 核心 (阶段 6)

### 13. 大模型训练三个阶段？(⭐⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/01-training-pipeline.md)

(1) 预训练 PT：TB 级文本做下一词预测，学知识 (2) SFT：指令对上微调，学对话格式 (3) 对齐 RLHF/DPO：人类偏好训练，有帮助+安全。

### 14. RLHF 和 DPO 的区别？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/02-alignment.md)

RLHF 需要训 RM + PPO（4 模型，复杂不稳定）。DPO 跳过 RM 和 RL，直接从偏好数据优化（2 模型，简单稳定）。效果接近。

### 15. 什么是 Chinchilla Scaling Law？(⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/03-scaling-law.md)

最优策略：参数量 N 和训练 token 数 D 同比增长（D ≈ 20N）。但目前趋势是过度训练小模型（D >> 20N，如 LLaMA-3 用 15T tokens 训 70B），因为推理成本是持续的，训练成本是一次性的。

### 16. DP、TP、PP 的区别？(⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/04-distributed-training.md)

DP 同模型不同数据；TP 一层矩阵拆分到多卡；PP 不同层放不同卡。实际组合使用（3D 并行）。ZeRO 消除 DP 中的冗余存储。

### 17. KV-Cache 是什么？为什么需要？(⭐⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/05-inference-optimization.md)

缓存已计算的 K/V 向量避免重复计算。把总复杂度从 O(n³) 降到 O(n²)。但 KV-Cache 占大量显存，GQA/MLA 减少其大小。

### 18. 量化怎么做？(⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/05-inference-optimization.md)

FP16 → INT8/INT4 压缩权重。GPTQ/AWQ 通过校准数据保护重要权重。4-bit 效果损失很小但显存减少 4 倍。

### 19. LoRA 原理？为什么有效？(⭐⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/06-fine-tuning-distillation.md)

冻结 W，用低秩矩阵 A(d×r)×B(r×d) 近似 ΔW。有效因为微调时权重变化本身低秩。只训练 0.1-1% 参数，效果接近全参数微调。

### 20. MoE 怎么工作？(⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/07-moe.md)

多个 FFN 专家 + Router。每个 token 只激活 top-K 个专家。总参数大（学到更多）但每次计算量小（和小模型一样）。负载均衡是关键挑战。DeepSeek-V3 用共享专家 + 无辅助损失的负载均衡。

### 21. LLM 为什么幻觉？怎么解决？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/10-safety-hallucination.md)

数据有错+生成目标优化流畅性+RLHF 鼓励"有帮助"。解决：RAG 提供事实依据（最有效）+ 低温度 + 引用来源 + 事实验证。

### 🔥 22. o1/R1 这类推理模型怎么工作？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/12-test-time-compute.md)

Test-time Compute Scaling：不增大模型，而是推理时多花计算。模型通过 RL 学会生成长思维链，自主决定推理深度——复杂问题自动思考更多步骤。DeepSeek-R1 用 GRPO 纯 RL 训练，模型自发涌现了自我反思和回溯行为。配合 Process Reward Model（每步打分）比 Outcome Reward（只看结果）信号更密集。

### 🔥 23. 怎么让模型处理 128K 甚至更长的上下文？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/13-long-context.md)

三个层面：(1) **位置编码**——RoPE 插值/YaRN 修改旋转角度，使位置编码能表示更长距离 (2) **注意力优化**——Flash Attention 减少显存，Sliding Window 降低复杂度 (3) **KV-Cache 管理**——PagedAttention 按需分配，量化减小体积。主要挑战是"Lost in the Middle"——长上下文中模型对中间位置的信息关注度下降，需要将重要信息放在开头/结尾。

### 🔥 24. 怎么评估 LLM 的输出质量？(⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/14-llm-as-judge.md)

传统指标（BLEU/ROUGE）不够，人工评估太贵。主流方案是 **LLM-as-Judge**——用 GPT-4 等强模型评估弱模型输出。方式：成对比较（A vs B）比绝对打分更稳定。已知偏差：位置偏差（交换 AB 位置缓解）、长度偏差（Rubric 中加简洁性）、自我偏好（多模型交叉评估）。Chatbot Arena 用匿名投票 + Elo rating 是目前最公认的排名方式。

---

## 应用 (阶段 7)

### 25. 描述你的 RAG 系统，解释每个设计决策。(⭐⭐⭐⭐⭐)
> 阶段 7 | [详细](../07-theory-practice-bridge/01-rag-deep-dive.md)

分块(语义完整) → Embedding(对比学习) → Hybrid Search(BM25+Dense互补) → Reranking(Cross-Encoder交叉注意力) → LLM 生成(低温减幻觉)。

### 26. HNSW 怎么工作？(⭐⭐⭐)
> 阶段 3 | [详细](../03-nlp-embedding-retrieval/03-retrieval-theory.md)

多层图：顶层稀疏（快速导航）→ 底层密集（精确搜索）。从顶层贪婪搜索逐层下降。复杂度 O(log N) vs 暴力 O(N)。

### 27. Function Calling 怎么训练的？(⭐⭐⭐)
> 阶段 7 | [详细](../07-theory-practice-bridge/02-agent-architecture.md)

SFT 数据包含 (用户输入, 工具定义, 工具调用, 工具结果, 最终回答) 格式。模型学会判断是否需要工具、选择正确工具、输出结构化参数。配合 Constrained Decoding 保证输出格式（JSON Schema 约束 token 选择）。

### 28. DeepSeek 有什么技术创新？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/11-model-families.md)

(1) MLA 多头潜在注意力（低秩压缩 KV-Cache）(2) 超大 MoE(256 专家 + 共享专家) (3) GRPO 对齐 (4) R1 纯 RL 推理模型 (5) 训练成本极低($5.6M)。

### 🔥 29. 怎么设计一个生产级 LLM 应用系统？(⭐⭐⭐⭐⭐)
> 阶段 7 | [详细](../07-theory-practice-bridge/05-compound-ai-systems.md)

Compound AI System 思想——不是单个 LLM，而是多组件协作：(1) **Router** 判断请求类型和复杂度（简单请求→小模型/缓存，复杂请求→大模型）(2) **Retriever** 检索知识（RAG）(3) **Generator** LLM 生成 (4) **Verifier** 验证输出正确性 (5) **Guardrails** 安全过滤。配套 Observability：链路追踪、LLM-as-Judge 质量抽检、成本追踪。关键决策：RAG vs 微调取决于知识更新频率——频繁更新用 RAG，改变行为风格用微调，实际常组合使用。

### 🔥 30. Prompt Injection 是什么？怎么防御？(⭐⭐⭐⭐)
> 阶段 6 | [详细](../06-llm-core/10-safety-hallucination.md)

Direct 是用户直接注入恶意指令（"忽略之前的指令"）；Indirect 更危险——恶意内容嵌入在外部数据中（如 RAG 检索到的网页含有恶意指令）。防御需要多层：(1) 输入过滤——分类模型检测恶意意图 (2) 输出过滤——检测有害内容和 PII (3) 系统级 Guardrails——声明式规则限制行为边界 (4) 持续 Red Teaming——安全测试不是一次性的。不能依赖单一防线。

---

## 🎯 面试技巧

```
1. 先说结论/一句话概括 → 再展开细节
2. 不确定就说"据我了解" → 不要编
3. 结合自己的项目经验 → 理论+实践
4. 面试官追问说"好问题" → 承认不确定的边界
5. 准备 2-3 个自己的技术亮点 → 主动引导话题
```

---

## 📊 题目速查索引

| # | 题目 | 阶段 | 难度 | 热度 |
|---|------|------|------|------|
| 1 | √d_k 缩放 | 4 | ⭐⭐⭐ | 经典 |
| 2 | BN vs LN | 2 | ⭐⭐⭐ | 经典 |
| 3 | Residual Connection | 2 | ⭐⭐⭐ | 经典 |
| 4 | Word2Vec vs BERT | 3 | ⭐⭐⭐ | 经典 |
| 5 | BPE / Tokenization | 3 | ⭐⭐⭐⭐ | 高频 |
| 6 | Embedding 训练 | 3 | ⭐⭐⭐⭐ | 高频 |
| 7 | Hybrid Search | 3 | ⭐⭐⭐ | 高频 |
| 8 | Self-Attention | 4 | ⭐⭐⭐⭐⭐ | **必考** |
| 9 | RoPE | 4 | ⭐⭐⭐ | 高频 |
| 10 | MHA/MQA/GQA | 4 | ⭐⭐⭐⭐ | 高频 |
| 11 | Flash Attention | 4 | ⭐⭐⭐ | 高频 |
| 12 | Mamba/SSM | 4 | ⭐⭐⭐ | 区分度 |
| 13 | 训练三阶段 | 6 | ⭐⭐⭐⭐⭐ | **必考** |
| 14 | RLHF vs DPO | 6 | ⭐⭐⭐⭐ | 高频 |
| 15 | Chinchilla Scaling | 6 | ⭐⭐⭐ | 高频 |
| 16 | DP/TP/PP | 6 | ⭐⭐⭐ | 工程岗 |
| 17 | KV-Cache | 6 | ⭐⭐⭐⭐⭐ | **必考** |
| 18 | 量化 | 6 | ⭐⭐⭐ | 高频 |
| 19 | LoRA | 6 | ⭐⭐⭐⭐⭐ | **必考** |
| 20 | MoE | 6 | ⭐⭐⭐ | 高频 |
| 21 | 幻觉 | 6 | ⭐⭐⭐⭐ | 高频 |
| 22 | 🔥 o1/R1 推理模型 | 6 | ⭐⭐⭐⭐ | **新热点** |
| 23 | 🔥 长上下文 | 6 | ⭐⭐⭐⭐ | **新热点** |
| 24 | 🔥 LLM-as-Judge | 6 | ⭐⭐⭐ | **新热点** |
| 25 | RAG 系统设计 | 7 | ⭐⭐⭐⭐⭐ | **必考** |
| 26 | HNSW | 3 | ⭐⭐⭐ | 高频 |
| 27 | Function Calling | 7 | ⭐⭐⭐ | 高频 |
| 28 | DeepSeek 创新 | 6 | ⭐⭐⭐⭐ | **新热点** |
| 29 | 🔥 Compound AI 系统设计 | 7 | ⭐⭐⭐⭐⭐ | **新热点** |
| 30 | 🔥 Prompt Injection | 6 | ⭐⭐⭐⭐ | **新热点** |
