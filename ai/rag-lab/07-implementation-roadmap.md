# RAG 文件 Agent 实现路线

## 这篇解决什么问题

前面的文档已经完成理论、实验、调试、`file_search` 边界和类 ChatGPT 文件 Agent 教程。这篇把它收敛成实现路线：第一版先做什么，哪些先用规则，哪些以后再升级，如何避免一开始就做成大而散的平台。

目标是构建 read-only 文件 Agent MVP：

```text
用户上传/选择文件
-> runtime 判断是否需要文件
-> resolver 选中文件
-> retrieval provider 检索内容
-> context assembler 注入
-> model 回答
-> trace 记录
-> active files 更新
```

## 非目标

第一版不做：

- 写工具。
- 审批和回滚。
- 多 agent 协作。
- 长期 memory。
- 复杂 workflow。
- 完整 PDF/OCR/表格生产解析。
- 大规模权限管理后台。

这些可以后续扩展，但不应阻塞文件选择和注入主链路。

## Phase 1: Resource Registry

目标：系统知道文件是谁、在哪、属于哪个 scope。

实现内容：

```text
Resource:
  resource_id
  provider
  provider_file_id
  filename
  mime_type
  size_bytes
  tenant_id
  owner_user_id
  scope
  session_id?
  project_id?
  status
  created_at
  expires_at?
```

同时记录：

```text
ResourceBinding:
  resource_id
  bound_to_type
  bound_to_id
  role
```

验收：

- 上传文件后能创建 `resource_id`。
- 能查询某个 session 的 attachments。
- 能区分 session、project、library。
- 不依赖 provider `file_id` 作为业务主键。

## Phase 2: Message Attachments

目标：把用户消息和文件绑定起来。

实现内容：

```text
Message:
  message_id
  session_id
  user_id
  text

MessageAttachment:
  message_id
  resource_id
  order_index
```

验收：

- 当前消息附件可按顺序读取。
- “第二个文件”有稳定顺序来源。
- trace 可以知道某个文件是当前附件还是历史文件。

## Phase 3: FileIntentClassifier

目标：先判断当前轮要不要进入文件选择流程。

第一版用规则：

```text
explicit_file_intent:
  总结/对比/提取/附件/文件/PDF/文档/合同/里面有没有

deictic_file_intent:
  这个/那个/第二个/刚才/继续/里面

project_library_intent:
  项目文档/知识库/公司文档/团队资料

file_use_forbidden:
  不要参考附件/不要查知识库/只根据常识

no_file_intent:
  默认
```

验收：

- 普通概念问题不会选文件。
- 明确附件问题会选文件。
- 禁用文件指令优先级最高。

## Phase 4: ActiveFileManager

目标：保存当前 session 的文件焦点。

状态：

```text
active_files:
  session_id
  resource_ids
  order
  source_turn_id
  updated_at
  confidence
```

规则：

```text
高置信度文件任务后设置 active files
用户上传新文件并提问时替换
用户明确切换文件时替换
用户纠正时修正
普通问题可衰减但不必立刻清空
```

验收：

- “第二个文件”能解析上一轮 active order。
- “不是这个文件”能修正 active state。
- active files 不会导致普通问题自动查文件。

## Phase 5: ResourceResolver

目标：把用户表达解析成 `selected_resource_ids`。

第一版规则顺序：

```text
1. 当前消息附件 + file intent
2. 显式文件名
3. active files / ordinal reference
4. project scope explicit
5. library scope explicit
6. ambiguity -> clarification
```

输出：

```text
selected_resource_ids
selection_reasons
confidence
excluded_resource_ids
exclusion_reasons
clarification_required
```

验收：

- 当前附件优先。
- 同名文件追问。
- 候选过多追问。
- project/library 不默认打开。

## Phase 6: RetrievalProvider

目标：把检索后端抽象出来。

统一接口：

```text
search(request):
  query
  selected_resource_ids
  filters
  top_k
  mode

returns:
  items:
    resource_id
    chunk_or_citation_id
    text
    score
    source
    metadata
```

第一版可选两条路线：

```text
Route A: OpenAI file_search
  快速验证
  需要维护 provider_file_id/vector_store_id/filter 映射

Route B: mini RAG
  更适合学习和调试
  只支持 txt/md
```

建议：

```text
学习环境先用 mini RAG
产品 MVP 可先用 file_search
接口保持一致，避免锁死
```

验收：

- 能在 selected resources 内检索。
- 不会跨 scope 检索。
- 返回结果能进入 trace。

## Phase 7: RetrievalPlanner

目标：决定注入策略。

规则：

```text
metadata only:
  文件身份、状态、消歧

full text:
  小文件 + broad task

summary:
  中等文件整体理解

retrieved chunks:
  精确问答、查字段、查风险

map-reduce:
  大文件完整总结

multi-document:
  对比、综合、冲突检查
```

验收：

- 小文件总结不会无意义走 RAG。
- 大文件不会全文塞 prompt。
- 精确问答只注入相关 chunks。

## Phase 8: ContextAssembler

目标：把材料组成模型输入。

输入：

```text
system/developer instructions
current message
short conversation history
selected file metadata
retrieved chunks/summaries
tool observations
```

策略：

```text
文件内容标注为 untrusted context
保留 source metadata
控制 file context budget
去重、压缩、排序
```

验收：

- 文件内容不会进入 system/developer prompt。
- prompt 能追溯每个 chunk 来源。
- 超预算时有明确裁剪规则。

## Phase 9: TraceWriter

目标：每一轮可复现和可排查。

字段：

```text
turn_id
file_intent
candidate_resource_ids
selected_resource_ids
selection_reasons
selection_confidence
excluded_resource_ids
exclusion_reasons
retrieval_provider
retrieval_query
filters
injection_mode
injected_chunk_ids
citations
token_usage_by_context_type
active_files_before
active_files_after
clarification_required
```

验收：

- 能解释为什么选了某个文件。
- 能解释为什么没有用 project/library。
- 能定位回答用了哪些 chunks。
- 用户纠错时能关联上一轮选择。

## Phase 10: Regression Cases

目标：用固定用例防止回归。

直接使用：

- [RAG 文件 Agent 测试用例集](./06-rag-file-agent-test-cases.md)

最低通过集：

```text
当前附件总结
第二个文件指代
同名文件歧义
project 显式开启
普通问题不使用文件
禁用文件
prompt injection 文档
旧版本污染
partial hit
用户纠正
候选过多追问
```

验收：

- 每个 case 都有 expected selected resources。
- 每个 case 都有 expected injection mode。
- 每个失败都能归类 failure type。

## 推荐迭代顺序

```text
Iteration 1:
  Resource Registry
  Message Attachments
  Current attachment selection
  Trace skeleton

Iteration 2:
  FileIntentClassifier
  ActiveFileManager
  Deictic reference
  Clarification gate

Iteration 3:
  RetrievalProvider mini RAG or file_search
  RetrievalPlanner
  ContextAssembler

Iteration 4:
  Project/library explicit scope
  Metadata filters
  Regression cases

Iteration 5:
  Hybrid/rerank
  Better summaries
  Evaluation dashboard
```

## 最小可演示场景

第一版 demo 只需要支持：

```text
Turn 1:
  上传 A/B，问“总结这些文件”

Turn 2:
  问“第二个文件有什么风险”

Turn 3:
  问“RAG 和微调有什么区别”

Turn 4:
  问“根据项目文档查 ERR_PAYMENT_402”
```

如果这四轮的 selected resources、injection mode、answer 和 trace 都正确，说明核心链路已经成立。

## 成功标准

实现路线完成后，你应该拥有：

- 一个可查询的 Resource Registry。
- 一个能处理当前附件和 active files 的 Resolver。
- 一个可替换的 RetrievalProvider。
- 一个能控制全文、summary、chunks 的 ContextAssembler。
- 一个能排查错误文件选择的 Trace。
- 一组固定 regression cases。

这时再考虑 LlamaIndex、复杂 PDF、长期 memory 或多 agent，才不会把基础边界搞乱。
