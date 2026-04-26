# 索引、Embedding 与召回

## 这篇解决什么问题

RAG 的第一步不是生成，而是把外部文档变成可检索的知识单元。原始 PDF、网页、Notion 页面或数据库记录不能直接高质量进入 prompt；它们需要解析、清洗、切分、打标签、向量化和建索引。

这一篇解决的问题是：文档如何从“文件”变成“可召回片段”，Embedding 和 index 在其中做什么，以及为什么 chunk 和 metadata 会直接影响最终回答。

## 学前检查

读这篇前，建议先理解：

- 文本如何变成向量：[旧版 Embedding 理论](../03-nlp-embedding-retrieval/02-embedding-theory.md)
- 稀疏检索和稠密检索的基本区别：[旧版检索理论](../03-nlp-embedding-retrieval/03-retrieval-theory.md)
- RAG 的基本边界：[RAG 解决什么问题](./01-rag-problem-boundary.md)

如果还不熟，可以先记住一句话：召回阶段的目标不是直接回答，而是尽量把可能有用的证据找出来。

## 概念为什么出现

原始文档通常有几个问题：

```text
格式混乱: PDF 页眉页脚、表格、目录和脚注会干扰语义
粒度不合适: 整篇文档太长，单句话又可能缺上下文
权限不同: 不同部门、产品和用户只能看到部分知识
查询表达不同: 用户问法和文档写法可能不完全一致
```

索引、Embedding 与召回出现，是为了把文档处理成适合匹配的片段，并在用户提问时快速找到候选证据。

## 最小心智模型

离线建库和在线查询可以分开看：

```text
离线: 文档 -> 解析 -> 清洗 -> chunk -> metadata -> embedding -> index
在线: query -> query embedding/filter -> top-k recall -> 候选 chunks
```

关键概念：

- ingestion：把文档从来源系统导入。
- parsing：提取正文、标题、表格和结构。
- cleaning：去掉噪声，例如页码、重复导航、乱码。
- chunking：把长文切成可检索片段。
- metadata：给片段加部门、日期、产品、权限等标签。
- embedding：把文本映射成向量。
- index：让向量或关键词可以被快速搜索。
- top-k recall：返回最相似的 k 个候选片段。

## 最小例子

有三段政策：

```text
chunk A: 在职员工未休年假不得直接折现。
chunk B: 员工离职结算时，未休年假可按当地政策折现。
chunk C: 销售部门季度奖金按业绩和回款计算。
```

用户问：

```text
离职的时候没休完年假能不能提现？
```

如果 chunk 太短，只保留“未休年假可折现”，模型可能误答成所有人都能折现。如果 chunk 太长，把年假、奖金、病假和报销都混在一起，检索可能被噪声干扰，也会浪费上下文。

更合适的 chunk 应该保留语义完整边界：

```text
离职结算规则：员工离职结算时，未休年假可按当地政策折现；仍在职员工不得直接折现。
```

这样检索命中后，回答既能覆盖“离职可折现”，也能保留“在职不行”的边界。

## 原理层

Chunk size 和 overlap 的核心矛盾是语义完整性与噪声。chunk 太短，可能丢掉条件、例外、定义和引用对象；chunk 太长，可能把多个主题混在一起，降低匹配精度并占用 prompt。overlap 可以减少切分处丢语义，但过大 overlap 会制造重复片段。

Metadata filter 解决的是“语义相似但不该返回”的问题。例如：

| metadata | 用途 |
|----------|------|
| department | 只检索 HR、Finance、Engineering 等部门文档 |
| date | 排除过期政策，或只看某日期后的版本 |
| product | 区分不同产品线的功能说明 |
| permission_level | 避免普通用户检索到管理层或敏感文档 |

检索方式可以先分成两类：

- sparse retrieval：基于关键词、词频和倒排索引，典型方法是 BM25。它擅长匹配精确术语、编号、人名和产品名。
- dense retrieval：基于 embedding 向量相似度，擅长匹配语义相近但措辞不同的问题。

Vector index 用来让向量相似度搜索更快。真实系统常用 approximate nearest neighbor 近似最近邻搜索，在速度和精度之间做权衡。HNSW、IVF-PQ 属于更深入的索引结构，第一遍学习只需要知道它们是加速向量检索的方法，不必先背参数。

Recall 指的是应该被找出的相关证据有没有进入候选集。召回高只是第一步：候选可能太多、排序可能不准、证据可能过期，最终回答仍然可能不好。

## 和应用/面试的连接

应用里，索引质量通常决定 RAG 上限。排查问题时要看：文档是否被正确解析，chunk 是否保留条件，metadata 是否完整，query filter 是否正确，top-k 是否覆盖答案证据。

面试里，不要把 RAG 说成“把文档 embedding 后放向量库”。更完整的说法是：先做 ingestion、parsing、cleaning 和 chunking，再加 metadata 和 embedding 建索引；查询时结合 filter 和 top-k recall 找候选，后面还要排序和上下文组装。

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| chunk 越小越精确 | 太小会丢条件和上下文 |
| chunk 越大越完整 | 太大会引入噪声并挤占 prompt |
| metadata 可有可无 | 它是权限、时效、产品线过滤的关键 |
| dense retrieval 能替代关键词检索 | 精确术语、编号和缩写常需要 sparse 信号 |
| recall 高就代表 RAG 好 | 后续排序、组装和生成仍会影响答案 |

## 自测

1. Chunk 太短和太长分别有什么问题？
2. Metadata filter 解决什么检索问题？
3. Dense retrieval 和 sparse retrieval 的匹配信号有什么不同？
4. Recall 高不等于最终回答好，为什么？

## 回到主线

到这里，你已经知道候选证据如何被召回。下一步要看：为什么第一阶段召回通常不够，系统还需要 Hybrid Search、Rerank 和上下文组装。

下一篇：[Hybrid Search、Rerank 与上下文组装](./03-hybrid-search-rerank-context.md)
