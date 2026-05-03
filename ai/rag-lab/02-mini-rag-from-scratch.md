# 从零设计 mini RAG：看清文件、chunk、检索和 prompt

## 这篇解决什么问题

这篇不是框架教程，也不写具体代码。它设计一个最小实验，让你亲手看清 RAG 的数据流。

目标不是做强，而是让每一步可打印、可解释、可替换：

```text
file -> resource -> chunks -> embeddings -> retrieval -> prompt context -> answer -> trace
```

## 实验边界

第一版只支持：

- `.txt`
- `.md`
- 本地小文件
- 单用户
- 单进程
- read-only 查询

暂时不做：

- PDF
- 表格
- OCR
- 多租户权限
- 流式输出
- 复杂 Agent loop
- 长期 memory

这些都不是 RAG 第一性问题。先把主链路跑透明。

## 数据集

准备 8 到 10 个小文档，每个文档 300 到 1500 字。建议覆盖：

```text
refund-policy.md
refund-policy-old.md
security-audit.md
soc2-checklist.md
api-errors.md
product-pricing.md
vacation-policy.md
malicious-instructions.md
```

文档里刻意放：

- 同义表达。
- 专有名词。
- 旧版本政策。
- 条件和例外。
- 跨文件对比信息。
- 类似 prompt injection 的文本。

## 数据模型

最小模型：

```text
Resource:
  resource_id
  filename
  source_path
  scope
  created_at
  status

Chunk:
  chunk_id
  resource_id
  chunk_index
  text
  start_offset
  end_offset
  token_count
  metadata
  embedding

QueryTrace:
  query
  candidate_resource_ids
  retrieved_chunk_ids
  retrieval_scores
  injected_chunk_ids
  final_prompt
  answer
```

这里的 `resource_id` 是自己的业务文件 ID，不是 OpenAI `file_id`。即使第一版不接外部 provider，也要保留这个概念。

## Ingestion 实验

### Step 1: 注册文件

每个文件生成一个 `resource_id`：

```text
refund-policy.md -> res_refund_current
refund-policy-old.md -> res_refund_old
```

打印：

```text
resource_id
filename
source_path
status
```

### Step 2: 解析文本

第一版直接读取纯文本。重点是保留文件名和路径，不要把文本丢进匿名字符串。

打印：

```text
resource_id
text_length
first_200_chars
```

### Step 3: 切 chunk

先用固定大小策略，例如：

```text
chunk_size: 500-800 tokens or approximate characters
overlap: 50-100 tokens or approximate characters
```

每个 chunk 保存：

```text
chunk_id
resource_id
chunk_index
start_offset
end_offset
text
```

打印所有 chunk，人工检查：

- 条件是否被切断。
- 标题是否跟正文分离。
- overlap 是否制造太多重复。
- chunk 是否包含多个不相关主题。

### Step 4: embedding

给每个 chunk 生成 embedding。学习阶段可以使用任一 embedding 模型，甚至先用简单替代实现观察流程。

关键是保存：

```text
chunk_id -> embedding
embedding_model
embedding_dimension
```

不要只保存向量而丢掉 chunk text 和 metadata。

## Query 实验

### Step 1: query embedding

用户问题也转成 embedding：

```text
query="退款多久能到账？"
query_embedding=[...]
```

### Step 2: metadata/resource filter

第一版可以先全局搜索，但要保留接口：

```text
candidate_resource_ids=[res_refund_current]
```

这样后续能接 Agent Runtime 的 Resource Resolver。

### Step 3: vector search

在候选 chunks 中做相似度搜索，返回 top-k：

```text
top_k=5
chunk_id
resource_id
score
text_preview
```

### Step 4: prompt assembly

把 top chunks 组装成 prompt context：

```text
Context:
[source: refund-policy.md, chunk: chk_003]
...

Question:
退款多久能到账？
```

注意：context 是资料，不是 system instruction。

### Step 5: answer

让 LLM 基于 context 回答，并要求无法从 context 得出时说不知道。

### Step 6: trace

保存并打印：

```text
query
selected resources
retrieved chunks
scores
final context
answer
```

如果没有 trace，这个实验价值会大幅下降。

## 第一批测试问题

用这些问题检查主链路：

```text
1. 退款 SLA 是多久？
2. 在职员工未休年假能提现吗？
3. SOC2 审计日志保留多久？
4. ERR_PAYMENT_402 是什么意思？
5. 新旧退款政策有什么差异？
6. 文件里有没有要求忽略系统指令？
```

每个问题记录：

```text
expected source
expected answer
retrieved chunks
actual answer
failure type
```

## 完成标准

完成本实验后，你应该能做到：

- 指出每个答案使用了哪些 chunk。
- 根据 score 判断为什么某个 chunk 被召回。
- 解释为什么有些问题 vector search 命中差。
- 看到 chunk 切分如何影响答案。
- 明确知道最终 prompt 里到底塞了什么。

## 下一步

mini RAG 跑通后，不要急着接框架。先制造失败，再加 BM25、hybrid、rerank 和调试模板。

下一篇：[Hybrid、Rerank 与调试](./03-hybrid-rerank-debugging.md)
