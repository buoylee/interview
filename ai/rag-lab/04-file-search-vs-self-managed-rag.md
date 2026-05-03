# file_search vs 自建 RAG：托管能力和自管边界

## 这篇解决什么问题

OpenAI `file_search` 很容易让人误解：既然上传文件、建 vector store、调用工具就能问答，是不是它已经等于完整 RAG 系统？

更准确的答案是：

```text
file_search 可以作为托管 RAG 后端
但不是完整 Agent/RAG 产品系统
```

这篇把它和自建 RAG 拆开比较。

## file_search 的基本工作流

典型流程：

```text
1. Upload file
   -> 得到 provider file_id

2. Create vector store
   -> 得到 vector_store_id

3. Add file to vector store
   -> OpenAI 处理并索引文件

4. Responses API 中启用 tool
   tools=[{ type: "file_search", vector_store_ids: [...] }]

5. 模型需要时调用 file_search
   -> 返回 file_search_call
   -> 生成带 citation 的答案
```

它是 hosted tool。你不需要自己写检索执行代码，但仍要决定何时、在哪个资源范围内使用它。

## file_search 托管了哪些 RAG 能力

| 能力 | 是否托管 |
|------|----------|
| 文件上传句柄 | 是，Files API 返回 `file_id` |
| 知识库容器 | 是，Vector Store |
| 文件加入索引 | 是，把 `file_id` attach 到 `vector_store_id` |
| 文件处理和索引 | 是，异步 processing/indexing |
| chunking | 部分托管，部分场景可配置 chunking strategy |
| embedding | 是 |
| 语义检索 | 是 |
| 关键词检索 | 是，文档说明支持 semantic + keyword search |
| filters | 是，支持 metadata/attribute filter |
| ranking options | 部分支持 |
| citation | 是 |
| 工具执行 | 是，模型决定调用时执行 |

所以在简单文档问答场景，`file_search` 已经能完成 RAG 主链路。

## 它没有托管什么

这些仍然属于你的 Agent Runtime 或产品系统：

| 能力 | 为什么不能交给 file_search |
|------|----------------------------|
| `session/project/library` scope | 这是产品资源边界 |
| `Resource Registry` | 需要记录 owner、tenant、scope、状态、生命周期 |
| 用户权限 | 必须由业务系统硬过滤 |
| “这些文件”的解析 | 需要 Resource Resolver 和 active file focus |
| active_files | 是 session 状态，不是检索索引 |
| 是否应该使用文件 | 需要 intent detection 和 context policy |
| 追问策略 | 候选不清时不能让检索猜 |
| 原文件归档 | 影响审计、迁移、重解析和合规 |
| 自定义 parsing | PDF、表格、代码、图片可能需要业务专用处理 |
| 自定义 context assembly | 决定注入哪些 chunk、顺序、压缩、引用格式 |
| eval/trace | 需要排查和复现生产问题 |
| 供应商迁移 | 避免把产品状态绑定到单一 hosted tool |

## 两种架构心智模型

### 只靠 file_search 的 demo 架构

```text
upload file
-> vector store
-> responses with file_search
-> answer
```

适合：

- 单知识库。
- 权限简单。
- 文档格式普通。
- 快速验证文件问答。

不适合：

- 多租户。
- session/project/library 作用域。
- 强审计。
- 复杂文件解析。
- 可替换检索后端。

### 平台型 Agent Runtime 架构

```text
User message
-> FileIntentClassifier
-> ResourceResolver
-> permission/scope filter
-> RetrievalProvider(file_search or self-managed RAG)
-> ContextAssembler
-> Model
-> TraceWriter
```

这里 `file_search` 只是 `RetrievalProvider` 的一种实现。

## 什么时候直接用 file_search

可以优先用：

- MVP。
- 内部低风险知识库。
- 单租户或权限简单。
- 不需要自定义 chunk/rerank。
- 不需要把索引迁移到其他供应商。
- 重点是快速验证产品价值。

推荐搭配：

```text
自己维护 Resource Registry
自己维护 Resolver/Trace
底层先用 file_search
```

## 什么时候自建 RAG

应该考虑自建或至少保留可替换后端：

- 多租户强权限。
- 数据不能出特定环境。
- 需要自定义 PDF、表格、OCR、代码解析。
- 需要精确控制 chunking、BM25、rerank、context order。
- 需要离线评估召回质量。
- 需要完整 trace 和复现能力。
- 需要混合多个模型供应商。
- 需要把 RAG 和业务数据库、搜索引擎深度集成。

## 推荐接口边界

即使第一版用 `file_search`，也建议抽象：

```text
RetrievalProvider.search(request) -> RetrievalResult
```

请求：

```text
query
candidate_resource_ids
provider_vector_store_ids
filters
top_k
ranking_options
trace_id
```

结果：

```text
retrieved_items:
  resource_id
  provider_file_id
  chunk_or_citation_id
  text
  score
  source
  metadata
```

这样未来可以替换成：

```text
OpenAI file_search
LlamaIndex + pgvector
Qdrant + BM25 + reranker
Elasticsearch/OpenSearch hybrid
```

## 和 Agent Runtime 文件上下文设计的连接

Agent Runtime 先解决：

```text
这一轮应该用哪些文件？
```

RAG/file_search 再解决：

```text
在这些文件中，哪些内容最能回答问题？
```

这两个问题不能混在一起。`file_search` 不应该负责解释用户说的“这些文件”到底指 session 附件、project 文档还是 library 文件。

相关设计：

- [Agent Runtime File Context Design](../../docs/superpowers/specs/2026-05-03-agent-runtime-file-context-design.md)

## 最终判断

`file_search` 不是低级方案，也不是不专业。它是一个托管 retrieval backend。

成熟团队的问题不是“用不用 file_search”，而是：

```text
是否把产品状态、权限边界、文件选择、上下文策略和 trace 掌握在自己手里？
```

如果答案是 yes，底层先用 `file_search` 是务实选择。如果答案是 no，把所有文件丢进 vector store 让工具自己决定，就是生产风险。
