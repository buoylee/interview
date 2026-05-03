# RAG Lab: 从 file_search 黑盒到可调试 RAG

> 定位：这是一组理论 + 实践路线，用来把 RAG 从“上传文件后系统会搜索”拆成可观察、可调试、可替换的工程链路。

## 为什么需要这个 Lab

主线 RAG 文档已经解释了 RAG 的边界、索引、召回、Hybrid Search、Rerank、上下文组装和评估。这个 Lab 解决另一个问题：当你面对 OpenAI `file_search`、LlamaIndex 或自建 RAG 时，能不能知道每个黑盒背后发生了什么。

目标不是一开始替代 `file_search`，而是通过亲手设计一个 mini RAG，看清：

- 文件上传后应该保存哪些业务元信息。
- `resource_id`、provider `file_id`、`chunk_id` 分别解决什么问题。
- chunking、embedding、BM25、rerank、context assembly 分别影响什么。
- 一个回答错了，应该定位到哪一层。
- `file_search` 包含了 RAG 的哪些部分，哪些仍然要由 Agent Runtime 自己维护。

## 适用人群

适合已经知道以下关键词，但还不能稳定解释底层链路的人：

```text
file_id
vector_store_id
chunk
embedding
BM25
hybrid search
rerank
context assembly
citation
trace
```

如果你还没读过 RAG 主线，先看：

- [RAG 与检索系统](../ml-to-llm-roadmap/01-rag-retrieval-systems/)
- [索引、Embedding 与召回](../ml-to-llm-roadmap/01-rag-retrieval-systems/02-indexing-embedding-retrieval.md)
- [Hybrid Search、Rerank 与上下文组装](../ml-to-llm-roadmap/01-rag-retrieval-systems/03-hybrid-search-rerank-context.md)

## 学习顺序

1. [RAG 心智模型：从文件到可引用上下文](./01-rag-mental-model.md)
2. [从零设计 mini RAG：看清文件、chunk、检索和 prompt](./02-mini-rag-from-scratch.md)
3. [Hybrid、Rerank 与调试：从能跑到能排查](./03-hybrid-rerank-debugging.md)
4. [file_search vs 自建 RAG：托管能力和自管边界](./04-file-search-vs-self-managed-rag.md)
5. [类 ChatGPT 文件 Agent：文件范围、选择、检索与注入](./05-chatgpt-like-file-agent.md)

## 阶段产出

| 阶段 | 产出 | 判断标准 |
|------|------|----------|
| 心智模型 | 一张 RAG 数据流图和 ID 关系表 | 能说清 `resource_id`、`file_id`、`chunk_id` 的区别 |
| mini RAG | 一个只支持 txt/md 的实验设计 | 能打印每个 chunk、score、最终 prompt |
| 调试实验 | 一组故意失败用例 | 能判断失败来自解析、切块、召回、排序、组装还是生成 |
| file_search 对照 | 一张能力边界表 | 能解释哪些交给 `file_search`，哪些必须自建 |
| 文件 Agent 教程 | 一条完整 ChatGPT-like 文件会话链路 | 能解释文件范围如何确定、何时检索、何时注入、如何更新 active files |

## 和 file_search 的关系

`file_search` 可以被看作托管 RAG 后端。它能处理文件索引、语义/关键词检索、部分排序和 citation，但它不负责你的产品状态：

```text
session/project/library scope
active_files
Resource Resolver
权限过滤
业务 metadata
trace/eval
```

所以这个 Lab 的核心结论会是：

```text
file_search 可以做 RetrievalProvider
但 Resource Registry、Resolver、Context Policy 和 Trace 必须由 Agent Runtime 自己掌握
```

## 和 LlamaIndex 的关系

建议先手写 mini RAG，再用 LlamaIndex 复刻同一条链路。这样你看到 `Document`、`Node`、`Index`、`Retriever`、`QueryEngine` 时，会知道它们对应 mini RAG 的哪一层，而不是被框架术语带着走。

## 完成标准

完成这个 Lab 后，你应该能回答：

1. 上传文件后系统应该保存什么，为什么不能只保存 provider `file_id`。
2. chunk size 和 overlap 错了会怎样定位。
3. BM25 为什么不是简单 keyword filter，而是独立召回通道。
4. metadata filter 为什么应该在检索前执行。
5. rerank 和 retrieval ranking 有什么区别。
6. context assembly 为什么不是简单取 top-k。
7. `file_search` 托管了哪些 RAG 步骤，哪些没托管。
8. Agent Runtime 里文件选择和 RAG 检索是什么关系。
9. 类 ChatGPT 文件 Agent 如何从当前附件、active files、project/library 里选择资源。
10. 为什么“选择文件”和“检索 chunks”必须拆成两个阶段。

## 连接 Agent Runtime

本 Lab 的结果会反哺 Agent Runtime 文件上下文设计：

- [Agent Runtime File Context Design](../../docs/superpowers/specs/2026-05-03-agent-runtime-file-context-design.md)

RAG 解决“选定资源后如何找证据”。Agent Runtime 还要解决“这一轮到底应该选哪些资源”。这两个问题要分开设计。
