# 00-03 Unlock Route Design

## 背景

当前 `ml-to-llm-roadmap` 已经把默认学习入口从旧的学科式顺序：

```text
00 math -> 01 ML -> 02 DL -> 03 NLP -> 04 Transformer
```

调整为新版主线：

```text
04 Transformer foundations -> 按需 foundations 补课 -> 回到主线
```

这个方向解决了“学习者还没建立 LLM 主线，就被数学、ML、DL、NLP 的大块内容拖住”的问题。

但仍有一个缺口：当学习者从 `04-transformer-foundations` 跳到旧 `00-03` 查前置知识时，旧文档本身仍可能偏学科式，容易再次产生跳跃感。学习者的最终目标不是永远避开旧 `00-03`，而是在合适时机能读懂它们，把它们作为深入资料使用。

## 目标

建设一层 `foundations/` 解锁路线，让学习者：

1. 先顺畅读新版主线，尤其是 `04-transformer-foundations`。
2. 遇到数学、DL、NLP 前置卡点时，先进入更短、更贴近 Transformer 的 `foundations/` 桥接文档。
3. 补完桥接知识后回到主线。
4. 主线跑通后，再按导航回读旧 `00-03`，把旧资料作为深入解释，而不是第一次学习入口。

## 非目标

本阶段不做：

1. 不重写旧 `00-math-foundations/`、`01-ml-basics/`、`02-deep-learning/`、`03-nlp-embedding-retrieval/` 的全部正文。
2. 不把旧 `00-03` 恢复成默认学习路线。
3. 不新增面试速记类文档；本阶段是学习解锁层，不是复习层。
4. 不扩展到 RAG、Agent、训练对齐、推理部署等后续模块的全部前置知识。

## 设计原则

### 主线优先

`04-transformer-foundations` 仍是第一次系统理解 LLM 底层的入口。`foundations/` 不替代主线，只在主线卡住时提供补给。

### 小块解锁

每篇 foundation 文档只解决一个明确卡点，例如“为什么点积能表示相似度”或“softmax 为什么能把 logits 变成概率分布”。避免重新做大而全的数学或 NLP 课程。

### 旧资料延后解锁

旧 `00-03` 的定位改成“解锁后的深入资料”。README 要告诉学习者：

- 什么时候读。
- 读之前应该先懂什么。
- 读完能补强什么。
- 哪些内容第一次可以跳过。

### 回路清晰

每篇新 foundation 文档都要有清楚的返回路径：

```text
卡点 -> foundation 小文档 -> 回到 Transformer 原章节 -> 旧 00-03 深入资料
```

## 第一批范围

### 新增 `foundations/README.md`

作为总补课入口，回答：

- 为什么 foundations 不是默认主线。
- 按卡点应该读哪一组文档。
- 什么时候回读旧 `00-03`。

建议入口表：

| 你卡在哪里 | 先读 |
|------------|------|
| 向量、矩阵、点积、`QK^T` | `foundations/math-for-transformer/` |
| logits、softmax、概率分布 | `foundations/math-for-transformer/` |
| token、vocab、token id、embedding table | `foundations/nlp-tokenization-embedding/` |
| 神经元、线性层、MLP、激活 | `foundations/deep-learning/` |
| Residual、LayerNorm、FFN、GELU/SwiGLU | `foundations/deep-learning/` |

### 新增 `foundations/math-for-transformer/`

文件结构：

```text
foundations/math-for-transformer/
  README.md
  01-vector-matrix-dot-product.md
  02-logits-softmax-probability.md
  03-attention-math-minimal.md
```

定位：只讲 Transformer 主线需要的最小数学。

内容边界：

- `01-vector-matrix-dot-product.md`
  - 向量是什么。
  - 矩阵乘法可以理解成批量线性变换。
  - 点积为什么能表示方向相近或匹配程度。
  - 对应 Transformer 中的 embedding、linear projection、`QK^T`。

- `02-logits-softmax-probability.md`
  - logits 是未归一化分数。
  - softmax 把分数变成概率分布。
  - temperature 为什么会改变分布尖锐程度。
  - 对应 attention weights 和 next-token probability。

- `03-attention-math-minimal.md`
  - 把 `QK^T / sqrt(d_k)` 拆成逐步计算。
  - 每一行 attention scores 表示当前 token 看所有 token 的匹配分数。
  - softmax 后变成读取比例。
  - 乘以 `V` 表示按比例汇总信息。

旧资料连接：

- 读完后可回读 `00-math-foundations/01-linear-algebra.md`。
- 读完后可回读 `00-math-foundations/02-probability.md`。
- 微积分和信息论保留为后续训练/损失函数深入资料，不作为 Transformer 第一批前置。

### 新增 `foundations/nlp-tokenization-embedding/`

文件结构：

```text
foundations/nlp-tokenization-embedding/
  README.md
  01-token-vocab-token-id.md
  02-embedding-table-and-position.md
  03-from-text-representation-to-transformer.md
```

定位：只讲文本如何进入 Transformer，不重讲完整 NLP 历史。

内容边界：

- `01-token-vocab-token-id.md`
  - token、vocab、token id 的关系。
  - token 不等于词，token id 不含语义。
  - BPE/WordPiece 只讲直觉，不展开算法细节。

- `02-embedding-table-and-position.md`
  - embedding table 是 `vocab_size x d_model` 的查表矩阵。
  - token id 查出向量。
  - position 信息为什么必须加入。
  - token embedding 和 position embedding 如何连接 Transformer 输入。

- `03-from-text-representation-to-transformer.md`
  - One-hot、词袋、Word2Vec、上下文 embedding 的演进只讲问题脉络。
  - 目标是让学习者读旧 NLP 文档时不觉得概念凭空出现。
  - 明确 Transformer 主线只需要先理解 token 到向量，不需要先掌握完整 NLP 表示史。

旧资料连接：

- 读完后可回读 `03-nlp-embedding-retrieval/01-text-representation.md`。
- 读完后可回读 `03-nlp-embedding-retrieval/02-embedding-theory.md`。
- BPE 细节可在需要时回读 `03-nlp-embedding-retrieval/06-tokenization-deep-dive.md`。

### 优化现有 `foundations/deep-learning/`

现有结构保留：

```text
foundations/deep-learning/
  README.md
  01-neuron-mlp-activation.md
  02-backprop-gradient-problems.md
  03-normalization-residual-initialization.md
  04-ffn-gating-for-transformer.md
```

第一批只做小幅优化：

- 在 README 中接入新的 `foundations/README.md` 总入口。
- 检查每篇是否明确返回 `04-transformer-foundations` 对应章节。
- 对旧 `02-deep-learning/README.md` 保持“旧版参考”定位，并指向新的 foundations 总入口。

## 导航更新

### 根路线图

更新 `ai/ml-to-llm-roadmap.md`：

- 把 `foundations` 从“Deep Learning 补课”升级为“00-03 解锁层”。
- 在系统学习路径中说明：
  - Transformer 主线优先。
  - 数学、NLP、DL 前置都先进 `foundations/`。
  - 旧 `00-03` 是解锁后的深入资料。

### Transformer 主线

更新 `04-transformer-foundations/README.md`：

- 学前检查优先指向新的 foundations：
  - 向量/矩阵/点积 -> `foundations/math-for-transformer/01`
  - logits/softmax -> `foundations/math-for-transformer/02`
  - token/vocab/embedding -> `foundations/nlp-tokenization-embedding/`
  - Residual/Norm/FFN -> `foundations/deep-learning/`

更新 `04-transformer-foundations/02-05`：

- 把直接跳旧 `00` 或旧 `03` 的前置链接，尽量改到新 foundations。
- 保留旧资料作为“深入参考”，不作为第一次补课入口。

### 旧 `00-03` README

更新：

- `00-math-foundations/README.md`
- `01-ml-basics/README.md`
- `02-deep-learning/README.md`
- `03-nlp-embedding-retrieval/README.md`

统一加上新版路线说明：

```text
这个目录是解锁后的深入资料，不是默认主线。
如果你是从 Transformer 主线卡住过来的，先读 foundations 对应短文。
读完 foundations 后，再回到本目录补完整理论。
```

每个旧目录要标注：

- 什么时候读。
- 先懂什么。
- 哪些章节可暂时跳过。

## 新 foundation 页面标准

每个新 foundation 页面使用统一结构：

```markdown
## 这篇解决什么卡点
## 先记住一句话
## 最小例子
## 这个概念在 Transformer 哪里出现
## 和旧资料的连接
## 自测
## 回到主线
```

写作规则：

- 先解决卡点，再给术语。
- 每篇必须有一个最小数字或文本例子。
- 不追求公式完整推导，只追求能继续读 Transformer 主线。
- 不引入当前卡点之外的大量新概念。
- 必须链接回对应 Transformer 章节。
- 必须标出旧 `00-03` 深入资料入口。

## 成功标准

完成后，学习者应能：

1. 从 `04-transformer-foundations` 开始，不再默认顺读旧 `00-03`。
2. 卡在数学、token/embedding、DL 基础时，能从 `foundations/README.md` 找到对应补课页。
3. 读完补课页后，知道回到 Transformer 哪一篇。
4. 读完 Transformer 主线后，知道什么时候回读旧 `00-03`。
5. 不再把旧 `00-03` 误解成第一默认路线。

验证方式：

- Markdown 链接检查通过。
- 新 foundation 页面结构检查通过。
- 根路线图和旧 `00-03` README 不再暗示旧 `00-03` 是默认顺序入口。
- `04-transformer-foundations/README.md` 的学前检查优先指向 foundations，而不是直接要求读旧目录。

## 风险与处理

### 风险：foundation 也变成大课程

处理：每篇只解决一个卡点，旧资料继续承担深入展开。

### 风险：旧 `00-03` 被边缘化

处理：每篇 foundation 都必须有“和旧资料的连接”，旧资料是深入资料，不是废弃资料。

### 风险：链接过多导致学习者再次分心

处理：Transformer 主线只给必要补课链接；深入参考放在 foundation 页末尾，不放在正文开头。

## 第一批完成后的后续

第一批完成后，学习者实际阅读 `04-transformer-foundations/02-05`。如果仍然卡住，再根据真实卡点追加第二批：

- loss / cross entropy / perplexity 解锁。
- gradient descent / optimizer 解锁。
- tokenization 算法细节解锁。
- 旧 ML 基础中“训练-评估-泛化”对 LLM eval 的连接。
