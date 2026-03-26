# 7.1 RAG 系统的理论深度（Day 1-4）⭐⭐⭐

> **一句话定位**：你已经做过 RAG，这里用理论知识为每个组件提供「为什么这样做」的深度解释，让面试回答从「我会用」升级到「我懂原理」。

---

## 1. RAG 全链路理论解析

```
Query → Embedding → ANN 检索 → Reranking → Context Augmentation → LLM 生成

每一步对应的理论基础：
1. Embedding:  对比学习 + Bi-Encoder  (阶段 3)
2. ANN 检索:   HNSW / IVF-PQ         (阶段 3)
3. Reranking:  Cross-Encoder          (阶段 3)
4. 上下文拼接: In-Context Learning    (阶段 5)
5. 生成:       自回归 + 解码策略       (阶段 3/4)
```

## 2. 关键设计决策的理论依据 ⭐

### 2.1 Chunk Size 怎么选？

```
理论依据:
  - Embedding 模型有最大输入长度（512/8192 tokens）
  - 太短: 语义不完整 → Embedding 质量差
  - 太长: 噪声太多 → 稀释关键信息

推荐: 256-512 tokens (有 overlap)
overlap: 防止关键信息被截断在边界
```

### 2.2 Embedding 模型怎么选？

```
理论依据:
  - 领域匹配: 通用 vs 领域微调（对比学习 + 硬负样本）
  - 维度权衡: 768 足够大多数场景（Matryoshka 可截断）
  - 语言匹配: BGE-zh 中文好，E5 多语言好

实际: 先用 BGE/E5，不够再微调
```

### 2.3 为什么需要 Hybrid Search？

```
理论: BM25(稀疏,词匹配) + Dense(稠密,语义匹配) 互补
  - 精确术语: BM25 强（"Python 3.12"）
  - 语义理解: Dense 强（"最新版 Python"）
  - RRF 融合: 只用排名不用分数 → 不需要归一化
```

### 2.4 为什么需要 Reranker？

```
理论: Bi-Encoder(独立编码,快) + Cross-Encoder(交叉编码,准)
  - Bi-Encoder 初筛 top-100: O(1) per doc（已预计算）
  - Cross-Encoder 精排 top-10: O(n²) 注意力但只有 100 个候选
  - 精度提升来自交叉注意力（能看到 query 和 doc 的交互）
```

## 3. RAG 高级优化的理论

### 3.1 Query Transformation

| 技术 | 理论依据 |
|------|---------|
| **HyDE** | 用 LLM 生成假设文档 → 和真实文档在同一分布（减少 query-doc 语义差距）|
| **Query Rewriting** | 多角度改写覆盖更多语义 |
| **Sub-question** | 分解复杂问题 → 每个子问题独立检索 |

### 3.2 Context 优化

```
问题: 检索回来太多文档 → 上下文太长、有噪声
解决:
  - Lost in the Middle: LLM 更关注首尾 → 把最相关的放开头
  - Compression: 用另一个 LLM 压缩检索结果
  - Relevance Filter: 过滤相关性低于阈值的文档
```

### 3.3 Evaluation 理论

```
RAG 特有评估指标:
  - Context Relevancy: 检索结果和问题的相关度
  - Faithfulness: 回答是否忠实于检索内容（不幻觉）
  - Answer Relevancy: 回答和问题的相关度

RAGAS 框架: 自动化 RAG 评估（用 LLM 评估上述指标）
```

## 4. 面试模拟

### Q: 描述你做的 RAG 系统，解释每个设计决策的原因。

**答（示例框架）**：

```
我的 RAG 系统使用:
1. 分块: 512 tokens + 50 overlap → 语义完整性 + 边界信息保留
2. Embedding: BGE-large → 对比学习训练，中文优化
3. 检索: Hybrid (BM25 + Dense) + RRF 融合 → 词匹配和语义理解互补
4. Reranking: Cross-Encoder → 交叉注意力比 Bi-Encoder 准确
5. 生成: GPT-4 + 低温度 → 减少幻觉，忠实于检索内容

底层原理:
- Embedding 基于对比学习(InfoNCE)，正负样本训练
- HNSW 索引实现 O(log N) 近似最近邻检索
- Cross-Encoder 通过交叉注意力看到 query-doc 交互
- Hybrid Search 中 RRF 只用排名不用分数 → 异构结果可融合
```

---

> ⬅️ [返回概览](./README.md) | ➡️ [下一节：Agent 架构](./02-agent-architecture.md)
