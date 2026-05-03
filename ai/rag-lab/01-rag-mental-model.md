# RAG 心智模型：从文件到可引用上下文

## 这篇解决什么问题

很多 RAG 疑问来自一个混淆：把“上传文件”“向量检索”“最终回答”看成一个黑盒。这样一来，看到 OpenAI `file_search` 返回 `file_id`、`vector_store_id` 或 citation 时，就很难判断系统到底保存了什么、检索了什么、为什么回答会错。

这篇建立一套底层心智模型：RAG 是从知识源到可引用上下文的链路，不是单独的向量库，也不是模型自动记住文件。

## 最小定义

RAG 是 Retrieval-Augmented Generation：

```text
先检索外部证据
再把证据组装进当前上下文
最后让模型基于证据生成答案
```

它解决的是外部知识接入和 grounding，不是让模型永久学习文件内容。

## 两条管线

RAG 至少有两条管线。

离线或异步 ingestion：

```text
file/source
-> parse
-> clean
-> chunk
-> attach metadata
-> embed
-> build index
```

在线 query：

```text
user question
-> decide resource scope
-> metadata/permission filter
-> retrieve candidates
-> rerank/deduplicate
-> assemble context
-> generate answer
-> record trace
```

一个系统是否成熟，往往不取决于“有没有向量库”，而取决于这两条管线是否可观察、可调试、可回归。

## 三层 ID

学习 RAG 时先把三个 ID 分清。

| ID | 所属系统 | 作用 |
|----|----------|------|
| `resource_id` | 自己的产品系统 | 表示业务文件、权限、scope、owner、生命周期 |
| `provider_file_id` | OpenAI、云厂商或外部服务 | 表示供应商侧文件句柄 |
| `chunk_id` | RAG 索引层 | 表示可检索、可注入、可引用的文本片段 |

例子：

```text
resource_id=res_123
filename=refund-policy.pdf
scope=project
provider_file_id=file-openai-abc

chunk_id=chk_009
resource_id=res_123
page=3
section=Refund SLA
text="退款处理时限为 7 个工作日..."
```

用户问“这个文件里的退款 SLA 是多少”时，runtime 先把“这个文件”解析成 `resource_id`，RAG 再在这个资源范围内找 `chunk_id`。

## Ingestion 层

Ingestion 的职责不是回答问题，而是把原始文件变成可检索证据。

最小字段：

```text
Resource:
  resource_id
  filename
  scope
  owner
  source_uri or provider_file_id
  status

Chunk:
  chunk_id
  resource_id
  text
  page/section
  token_count
  metadata
  embedding
```

生产系统还应保存：

```text
parser_version
chunking_strategy
embedding_model
created_at
document_version
checksum
```

这些字段会在重建索引、排查错误、回滚版本和审计引用时发挥作用。

## Metadata filter 不是检索后装饰

metadata filter 应该先于大规模检索执行。

错误做法：

```text
全库 vector search
-> 拿到 top-k
-> 再过滤 tenant/project/permission
```

更好的做法：

```text
Resource Resolver 决定候选资源
-> tenant/project/permission/status hard filter
-> 在被允许的 chunks 内检索
```

这样可以避免跨租户泄露，也能减少无关文件污染召回。

## BM25、Vector、Hybrid

Vector search 用 embedding 找语义相似内容，适合不同表达方式：

```text
"退款多久能到账" -> "退款处理时限为 7 个工作日"
```

BM25 用词项匹配和倒排索引找关键词，适合精确术语：

```text
SOC2
SKU-123
ERR_PAYMENT_402
API 字段名
合同条款编号
```

Hybrid search 通常不是“vector 后再 keyword filter”，而是两路召回并行：

```text
BM25 top-k
Vector top-k
-> fusion
-> candidates
```

这能同时覆盖精确词和语义改写。

## Rerank

第一阶段 retriever 通常快但粗。Reranker 面向少量候选，重新判断 query 和 chunk 是否真的匹配。

常见流程：

```text
retrieve top 50
-> rerank top 10
-> inject top 3-8
```

Rerank 解决的是“候选里谁最能回答问题”，不是替代权限过滤或文件选择。

## Context assembly

检索到 chunk 不等于 RAG 完成。还要决定：

- 放几个 chunk。
- 按什么顺序放。
- 是否去重。
- 是否压缩。
- 是否带标题、页码和引用信息。
- 如何告诉模型这些是资料，不是指令。

一个常见错误是直接把 rerank top-k 全塞进去。更稳的策略是：

```text
主证据
-> 必要定义
-> 约束/例外
-> 冲突或版本提示
```

## Trace 是学习 RAG 的放大镜

每次查询至少记录：

```text
question
candidate resources
filters
retrieved chunk ids
scores
reranked chunk ids
injected context
answer
citations
failure label if any
```

没有 trace，就只能说“RAG 不准”。有 trace，才能知道问题来自：

```text
文件没进候选池
解析错
chunk 切坏
embedding 召回错
BM25 没命中
rerank 排错
context assembly 混乱
模型没忠实使用证据
```

## 常见误区

| 误区 | 更准确的理解 |
|------|--------------|
| RAG 等于向量数据库 | 向量库只是索引/召回组件 |
| 上传文件后模型就知道文件 | 文件需要被解析、索引，并在当前轮被检索注入 |
| `file_id` 就够了 | 产品系统还要维护 `resource_id`、scope、权限和状态 |
| BM25 只是关键词过滤 | BM25 是独立召回通道 |
| top-k 越大越好 | 过多上下文会增加噪声和成本 |
| 有 citation 就一定正确 | citation 可能错配，答案仍需 grounding 检查 |

## 自测

1. 为什么 `provider_file_id` 不能替代业务系统里的 `resource_id`？
2. 为什么权限和 scope filter 应该在检索前执行？
3. BM25 和 vector search 各自最容易命中什么类型的问题？
4. Rerank 解决什么问题，不解决什么问题？
5. Context assembly 为什么会影响模型是否幻觉？
