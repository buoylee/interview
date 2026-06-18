# 高级检索策略：当 hybrid + rerank 还不够

## 这篇解决什么问题

03 篇讲的 hybrid + rerank 解决了两件事：两路信号互补（关键词 + 语义）、精排候选的可回答性。但还有一类失败它们碰不到——**检索的结构本身不对**：chunk 切的粒度不对、一个 query 其实包含好几个问题、或者这条 query 根本该去查另一个库。

这一篇讲一组「结构化检索策略」（small-to-big、auto-merging、recursive retrieval、query 分解、routing、metadata 过滤），每一个都对应一种 hybrid + rerank 治不好的检索失败。

先说清一件事，免得学偏：**这些是「检索层的思想」，不是某个框架的专利。** LlamaIndex 把它们命名、打包得最全（auto-merging、sentence-window 这些词就是它推广开的），所以本篇拿它当**教材**；但思想可移植——你在 LangChain、甚至裸向量库里都能实现同样的东西。**学的是策略，不是迁框架。**

## 学前检查

读这篇前，建议先理解：

- hybrid + rerank + 上下文组装：[Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md)
- chunk 怎么存、metadata 过滤在底层怎么走：[向量库内部](./02b-vector-store-internals.md)
- 「向量库 / 框架 / 模型」三层分工的背景（为什么框架只是胶水）：[旧版检索理论 §8](../03-nlp-embedding-retrieval/03-retrieval-theory.md#8-工程实现这条流水线谁帮你做了)

一句话锚点：**hybrid + rerank 优化的是「在固定 chunk 上怎么召回和排序」；本篇优化的是「chunk 粒度该多大、一个 query 该不该拆、该查哪个库」**——是检索的结构，不是检索的信号。

## 概念为什么出现

朴素 RAG（固定切块 → 单路向量召回 → 直塞 top-k）有三类失败，光加 hybrid + rerank 也解不掉：

```text
失败1 粒度错配：
  chunk 切小 → embedding 准、检得中，但片段太碎、上下文不全 → 答不完整
  chunk 切大 → 上下文全，但 embedding 糊、噪声多 → 检不准

失败2 单-query 假设：
  "对比 A 和 B 的退款政策" 其实是两个检索问题
  "既要支持 X 又要兼容 Y 的方案" 是多跳问题
  一个向量去捞 → 哪个都捞不全

失败3 单-库假设：
  所有 query 都打同一个 index
  但有的该查产品文档、有的该查表格、有的根本不用检索（闲聊/算术）
```

每个高级策略，就是上面某一类失败的解药。

## 最小心智模型

别背名词，先把策略挂到它治的「病」上：

| 检索失败 | 解药（策略） | LlamaIndex 里的名字 |
|---|---|---|
| 粒度错配 | 小块检索、大块喂给 LLM | sentence-window / auto-merging / parent-document |
| 一个 query 是多个问题 | 拆成子问题分别检索再合并 | sub-question query engine |
| query 与 doc 语义鸿沟 | 先生成假设答案再检索 | HyDE（检索理论已讲，此处不展开） |
| 不确定该查哪个源 | 让 LLM 选 index / 工具 | router query engine / selector |
| 需要精确过滤（时间/部门/类型） | 把硬条件转成 metadata 过滤器 | metadata filter / auto-retrieval |

一句话：**先确诊是哪类失败，再上对应策略。不是策略越多越好**——每加一个都加延迟、成本和复杂度。

## 最小例子

**small-to-big（小块检索、大块返回）**

```text
问题："这个 API 的限流是多少？"

朴素：chunk=200 字，检到一句 "限流默认 100 QPS"，但没带上下文（对谁、怎么配、能否调）
      → LLM 答得不全

small-to-big：
  用小 chunk（句子级）做检索 → 命中那句 "限流默认 100 QPS"（embedding 准）
  返回时换成它所在的父块 / 前后窗口（整段限流配置说明）
  → 检得准 + 上下文全，两头都要到
```

**sub-question（复合问题拆子问题）**

```text
问题："对比 Standard 和 Pro 套餐的退款政策"

单路检索：一个向量同时想捞 Standard 和 Pro → 往往偏一边
sub-question：
  LLM 先拆：Q1="Standard 退款政策"  Q2="Pro 退款政策"
  分别检索 → 各自命中 → 合并给 LLM 做对比
```

## 原理层

逐个讲：**治什么病 / LlamaIndex 怎么叫 / 等价实现 / 何时用**。

### small-to-big（sentence-window / auto-merging / parent-document）

- **治**：粒度错配。核心思想 = 用小单元检索（embedding 准），返回大单元（上下文全）。
- **变体**：sentence-window 按句检索、返回命中句 + 前后 N 句窗口；auto-merging 把文档切成层级块（大块下挂小块），若同一父块下足够多子块被命中就「上卷」返回整个父块。
- **LlamaIndex**：`SentenceWindowNodePostprocessor`、`AutoMergingRetriever`、层级 node parser。
- **等价**：LangChain 的 `ParentDocumentRetriever`（检子块、返父块）；裸库：存 chunk 时带 `parent_id`，命中后回查父块。
- **何时用**：文档有清晰层级（标题/段落/条款），且症状是「检得中但答不全」。
- **动手**：[09 small-to-big lab](../../rag-lab/09-small-to-big-lab/) —— 裸 Python vs LlamaIndex `AutoMergingRetriever` 两种实现 + 量化对比，全本地零 key 可跑。

### recursive retrieval（递归检索）

- **治**：粒度错配 + 长文档导航。先检索「摘要 / 索引节点」，再顺着引用下钻到具体块；或文档里引用了别的文档/表格，顺着引用继续检。
- **LlamaIndex**：recursive retriever、node references。
- **等价**：自建两层索引（摘要层 → 明细层），先检摘要定位文档，再在文档内检明细。
- **何时用**：文档很长、有目录/摘要结构，或文档之间有引用关系。

### query decomposition / sub-question（查询分解）

- **治**：单-query 假设。一个复合问题 → LLM 拆成多个子问题 → 各自检索 → 合并答。
- **LlamaIndex**：`SubQuestionQueryEngine`。
- **等价**：LangChain 的 multi-query，或自己写「LLM 拆问题 → 循环检索 → 合并」。
- **何时用**：对比类、多跳类、「既要…又要…」类问题。**代价**：多次检索 + 多次 LLM 调用，延迟和成本翻倍——简单问题别用。

### query routing（路由）

- **治**：单-库假设。让 LLM 看 query，决定走哪个 index / 工具，或要不要检索。
- **LlamaIndex**：router query engine、selector。
- **等价**：这其实就是你 LangGraph 里的**条件边 / supervisor 路由**——你已经在做了。
- **何时用**：有多个异构数据源，或有的 query 根本不需要 RAG（闲聊、算术、调工具）。

### metadata filtering / auto-retrieval（结构化过滤）

- **治**：需要精确结构化过滤。把 query 里的硬条件（时间、部门、文档类型）转成向量库的 metadata filter，先过滤再向量召回。
- **LlamaIndex**：metadata filters、auto-retrieval（LLM 从 query 里抽出 filter）。
- **等价**：LangChain 的 `SelfQueryRetriever`；裸库：Qdrant payload 过滤 / pgvector 字段 `WHERE`。
- **何时用**：文档有结构化字段，且 query 常带硬条件（"2023 年后的"、"财务部的"）。**注意**：过滤太狠会「过滤塌陷」（候选被砍光），见 [02b](./02b-vector-store-internals.md)。

## 和应用/面试的连接

面试问「怎么提升 RAG 检索质量」，**分层递进**地答，显得有判断力：

1. 先 hybrid + rerank（信号层，03 篇）
2. 再按失败类型上结构策略：答不全 → small-to-big；复合问题 → sub-question；多源 → routing；硬条件 → metadata filter
3. 始终配评估（04 篇）验证每个策略**真有提升**，而不是凭感觉堆

被追问「那为什么不直接全用 LlamaIndex」：因为这些是**可移植的检索思想**，不是必须迁的框架。骨架（尤其 agentic）仍可用 LangGraph；需要某个高级 retriever 时，把 LlamaIndex 的 retriever **当一个组件**接进节点即可，不用搬家。routing 这种，你 LangGraph 的条件边本来就在做（见 [§8 三层分工](../03-nlp-embedding-retrieval/03-retrieval-theory.md#8-工程实现这条流水线谁帮你做了)：重活在向量库和模型，框架只是胶水）。

## 常见误区

| 误区 | 更准确的理解 |
|---|---|
| 策略越多越好 | 每个策略治一类失败，先确诊再加；每加一个都加延迟和成本 |
| `index.as_query_engine()` 默认就够好 | 默认常不开 rerank、chunk 乱切，可能比认真调过的 hybrid+rerank 还差 |
| auto-merging 就是「切大块」 | 反了：小块检索（准）+ 命中后上卷返回父块（全） |
| 上了高级 retriever 就不用 rerank 了 | 互补不替代：结构策略管「取哪些」，rerank 管「怎么排」 |
| 学高级策略 = 学 LlamaIndex 框架 | 学的是思想；框架只是把它命名打包，可在任意栈实现 |
| sub-question 总是更好 | 多次检索 + 多次 LLM，延迟成本翻倍；简单问题反而更慢更贵 |

## 自测

1. small-to-big 为什么能同时拿到「检得准」和「上下文全」？它和「直接切大块」区别在哪？
2. 什么样的 query 适合 sub-question 分解？代价是什么？
3. query routing 和你在 LangGraph 里写的条件边 / supervisor 是不是一回事？
4. metadata filtering 解决了 hybrid + rerank 解不了的什么问题？它的风险是什么（联系 02b）？
5. 为什么说「学高级检索策略」不等于「必须迁到 LlamaIndex」？

## 回到主线

到这里，你手上有了一套「按失败类型选检索策略」的工具箱，而不是只会 hybrid + rerank。但加了策略不代表更好——下一步必须能**量化**：用评估集判断每个策略到底有没有提升，失败时定位是检索、排序、组装还是生成出了问题。

下一篇：[RAG 评估、幻觉与生产排查](./04-rag-evaluation-debugging.md)
