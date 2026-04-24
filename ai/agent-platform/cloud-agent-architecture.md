# 云上 Agent 最终落地方案

> 时间点：2026-04-24  
> 场景：企业知识库 + 工单/任务自动化 Agent 平台  
> 读者：架构评审 / 技术负责人  
> 目标：给出一套可进入研发排期的云上 Agent 架构方案，支撑生产级 MVP 并能演进到平台化。

## 1. 方案概述

最终方案采用：

> **LangGraph 作为主控制平面 + 私有 Tool Gateway + ACL-aware RAG + OTel-first 可观测 + 审批/审计闭环**

这不是一个单纯的聊天机器人方案，而是一套受控的企业 Agent 系统。它要完成四件事：

- 回答企业知识库问题，并给出来源引用。
- 查询工单、摘要工单、生成分类和处理建议。
- 在人工审批后执行有限写操作。
- 保留权限、审批、审计、评测、成本和观测边界。

## 2. MVP 业务范围

### 2.1 MVP 做什么

第一期只做一个可上线的最小业务闭环：

- 企业知识库问答
- 工单查询
- 工单摘要
- 工单分类 / 处理建议
- 审批后更新工单状态或备注
- 少量平台预注册工具接入

### 2.2 MVP 明确不做什么

- 不做通用 Agent 平台
- 不做任意 MCP / 任意工具接入
- 不做高风险跨系统自动写操作
- 不做 voice / realtime / browser / computer use
- 不做复杂多 Agent 自由协作
- 不做通用 SQL / 数据分析 Agent
- 不做完整平台化运营后台

### 2.3 为什么先收敛到这个边界

第一期目标不是“大而全”，而是先证明以下闭环成立：

- 业务闭环
- 权限闭环
- 审批闭环
- 审计闭环
- 观测闭环

只有这些闭环成立，平台化才有基础。

## 3. 架构原则

### 3.1 主控制平面只选一个 runtime

- **LangGraph 是唯一主 runtime**
- OpenAI Agents SDK 不作为第二主框架
- OpenAI Agents SDK 仅在专项能力场景作为 capability adapter

### 3.2 Tool Gateway + Policy Engine 是统一入口

无论底层工具来自：

- function tools
- OpenAPI tools
- MCP tools
- OpenAI hosted tools
- sandbox capability

都必须经过统一 Tool Gateway 与 Policy Engine。

### 3.3 OTel-first，可观测与审计分离

- trace 用于排障、性能和质量分析
- audit 用于权限、审批和责任追踪
- LangSmith / Langfuse / Phoenix 是可选增强层，不是唯一生产依赖

### 3.4 RAG 是核心能力层

在“企业知识库 + 工单自动化”场景里，RAG 与 Agent Runtime、Tool Gateway 是并列核心能力：

- Agent Runtime 决定流程和状态
- RAG 决定知识获取、权限过滤和引用
- Tool Gateway 决定动作执行边界

### 3.5 云中立与可迁移

- 模型由 Model Gateway 统一封装
- 检索底座可替换
- 可观测出口可替换
- 云厂商只承载基础设施与托管能力，不承载平台控制平面

## 4. 总体架构图

```text
┌─────────────────────────────────────────────────────────┐
│                         Channels                         │
│ Web / API / Slack / Teams / Ticket System / Admin UI    │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│                    API Gateway / BFF                     │
│ AuthN, tenant, request_id, rate limit, user context      │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│                      Control Plane                       │
│                                                         │
│  LangGraph Runtime                                      │
│  Workflow Versioning                                    │
│  Session / Thread State                                 │
│  Policy Engine                                          │
│  Approval Engine                                        │
│  Audit Log                                              │
│  Eval Runner                                            │
│  OTel Trace Contract                                    │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│                      Execution Plane                     │
│                                                         │
│  Specialist Nodes                                       │
│  Retrieval Nodes                                        │
│  Tool Nodes                                             │
│  OpenAI Capability Node                                 │
│  Sandbox / Hosted Tool Adapter (phase 2+)               │
└───────────────┬───────────────────────────────┬─────────┘
                │                               │
┌───────────────▼──────────────┐   ┌────────────▼──────────┐
│         Tool Gateway          │   │      RAG Platform      │
│ schema, authz, audit, policy  │   │ parse, chunk, index,   │
│ allowlist, timeout, rate      │   │ retrieve, rerank, ACL  │
└───────────────┬──────────────┘   └────────────┬──────────┘
                │                               │
┌───────────────▼──────────────┐   ┌────────────▼──────────┐
│      Enterprise Systems       │   │  Search / Vector Base  │
│ ticket, CRM, KB, ITSM, email  │   │ OpenSearch / pgvector  │
│ etc.                          │   │ / Milvus / managed svc │
└───────────────────────────────┘   └───────────────────────┘
```

## 5. 控制平面设计

控制平面由平台自己掌控，不交给单一 Agent 框架或单一厂商产品。

### 5.1 控制平面包含什么

- workflow definition / versioning
- LangGraph runtime
- session / thread state
- Policy Engine
- Approval Engine
- Audit Log
- Eval Runner
- OTel trace export
- Release Gate

### 5.2 为什么控制平面必须平台自有

如果控制平面散落到各个框架内部，长期会出现：

- 工具权限边界失控
- 审批和审计模型不统一
- 观测数据无法关联
- OpenAI SDK / LangSmith 逐渐膨胀成第二控制平面

因此平台必须拥有控制权，框架负责执行。

## 6. 执行平面设计

执行平面负责真正“干活”的节点。

### 6.1 执行平面包含什么

- 普通 tool nodes
- retrieval nodes
- specialist agents
- OpenAI capability node
- 后续阶段的 sandbox / browser / realtime adapters

### 6.2 为什么拆控制平面与执行平面

因为：

- 控制平面解决治理问题
- 执行平面解决能力问题

这样做的结果是：

- LangGraph 始终是 orchestrator
- OpenAI Agents SDK 只做某些节点的内部实现
- Tool Gateway / Policy Engine 永远在平台侧收口

## 7. Agent Runtime 设计

### 7.1 主 runtime：LangGraph

选择 LangGraph 的原因：

- graph / state 更适合表达多步骤 workflow
- checkpoint / interrupt / resume 贴合审批与长任务
- 更容易把治理能力放在框架外面
- 云中立和模型中立更好

### 7.2 OpenAI Agents SDK 的边界

它不做主 runtime，只在这些场景作为 capability adapter：

- OpenAI hosted tools
- sandbox
- voice / realtime
- computer use
- 特定 OpenAI-only specialist

调用原则：

1. LangGraph 调度 capability node
2. capability node 再调用 OpenAI Agents SDK
3. tool / policy / audit 结果回写平台体系

### 7.3 推荐 Agent 分工

MVP 不做复杂多 Agent 自由协作，只做少量职责清晰的 specialist：

| Agent / Node | 职责 |
|---|---|
| Router Node | 路由到知识问答或工单流程 |
| Knowledge Node | 检索知识、组织引用、回答问题 |
| Ticket Node | 查询工单、摘要、分类、生成处理建议 |
| Approval Node | 在高风险操作前中断并等待人工审批 |
| Summary Node | 输出最终摘要与执行结果 |

## 8. Model Gateway 设计

Model Gateway 是平台自有能力。

### 8.1 职责

- provider abstraction
- per-workflow model routing
- fallback
- token / latency / cost 统计
- 模型准入和版本控制
- 预算限制

### 8.2 推荐路由

| 任务 | 模型策略 |
|---|---|
| 分类 / 风险判定 | 小模型 |
| RAG 答案生成 | 中高能力模型 |
| 复杂规划 | 高能力模型 |
| 摘要 / 压缩 | 低成本模型 |

### 8.3 为什么 Model Gateway 必须平台掌控

否则会出现：

- 业务代码直接依赖多个模型 SDK
- 成本无法统一统计
- fallback 策略无法收敛
- 云中立失真

## 9. Tool Gateway 设计

Tool Gateway 是所有 side effect 的唯一入口。

### 9.1 MVP 必须具备的能力

- 工具注册
- schema 校验
- 用户身份透传
- Agent-to-tool allowlist
- 参数审计
- timeout / rate limit
- 工具调用日志
- 高风险工具分级

### 9.2 支持的工具类型

- function tools
- OpenAPI tools
- MCP tools

但第一期仅支持平台白名单工具，不开放任意动态注册。

### 9.3 工具风险分级

| 等级 | 类型 | 策略 |
|---|---|---|
| L0 | 公开只读 | 可自动执行 |
| L1 | 企业内部只读 | 需要用户身份和 ACL |
| L2 | 低风险写操作 | 可配置执行，完整审计 |
| L3 | 高风险写操作 | 必须审批 |
| L4 | 金钱 / 权限 / 删除 / 外发 | 默认禁止或双人审批 |

### 9.4 为什么 MVP 不开放任意 MCP / 任意工具接入

因为“工具接入”本身就是最大的风险面之一。第一期先控制工具范围，后续再做：

- Tool Registry
- MCP allowlist
- 工具审核
- 版本治理
- 权限模板

## 10. Policy Engine / Approval 设计

### 10.1 Policy Engine 职责

- 哪个 Agent 能调用哪些工具
- 哪个用户 / 租户能触发哪些操作
- 哪些参数需要审批
- 哪些输出需要阻断或脱敏
- 哪些场景可以进入 OpenAI hosted capability

### 10.2 MVP 形态

第一期不需要复杂策略 DSL，采用规则化实现即可：

- allowlist
- risk level
- per-tool parameter rules
- tenant / role based restrictions

### 10.3 Approval 设计

审批不是 trace 的附属能力，而是业务闭环的一部分。

审批卡片至少要包含：

- 原始请求
- Agent 计划执行的动作
- 工具名称与参数摘要
- 风险等级
- 影响对象
- 回滚方式

审批结果需要关联：

- run_id
- tool_call_id
- approver
- approved_at
- approval_reason

## 11. Audit Log 设计

### 11.1 为什么 trace 不能替代 audit

trace 用于排障，audit 用于责任追踪。两者字段和留存要求不同。

### 11.2 Audit Log 最小字段

- run_id
- workflow_name / version
- user_id / tenant_id
- tool_call_id
- tool_name
- args_summary
- result_summary
- approval_id
- before / after diff
- created_at

### 11.3 审计原则

- 高风险写操作必须有 before / after diff
- 审计日志不可被普通开发者随意删除
- trace 与 audit 通过 run_id 关联，但分开存储

## 12. RAG Platform 设计

RAG 是第一期核心能力层之一，而不是附属模块。

### 12.1 技术路线

采用：

> **开源框架 + 托管检索底座**

推荐：

- LlamaIndex 作为主 RAG 编排框架
- Haystack 作为备选
- 底层使用可替换的搜索 / 向量服务

### 12.2 数据流

```text
Source
 -> Connector
 -> Parser / OCR
 -> Chunker
 -> Metadata / ACL Extractor
 -> Embedding
 -> Keyword / Vector Index
 -> Retrieval API
 -> Reranker
 -> Citation Builder
 -> Agent Context
```

### 12.3 Chunking 设计

默认采用：

> **结构感知 chunking + 长度约束**

而不是固定 token 机械切块。

优先按文档结构切：

- 标题 / 小节
- FAQ 问答对
- SOP 步骤块
- 列表 / 表格块
- 工单对话片段

再通过长度约束控制 chunk 大小。初始可从 300-800 tokens 的目标区间起步，再用评测调优。

### 12.4 Metadata 设计

metadata 是 retrieval contract 的核心，不是附属字段。

建议至少包含：

- `doc_id`
- `chunk_id`
- `doc_version`
- `source_uri`
- `title`
- `section_path`
- `tenant_id`
- `acl`
- `owner` / `team`
- `doc_type`
- `updated_at`
- `tags`

### 12.5 检索策略

默认采用：

> **Hybrid Search + Rerank**

理由：

- keyword / BM25 负责精确召回
- vector 负责语义召回
- metadata filter 负责租户、文档类型、权限等过滤
- rerank 提升 top-k 质量，减少无关上下文

### 12.6 ACL-aware retrieval

权限尽量前置到检索阶段，而不是“先全量召回再粗暴过滤”。

推荐链路：

```text
query
 -> user / tenant context
 -> metadata ACL filter
 -> hybrid retrieval
 -> rerank
 -> top-k context
 -> citation permission re-check
```

### 12.7 Citation 设计

MVP 要求：

- 最终答案必须带来源
- citation 与用户可见内容权限一致
- 引用必须能回溯到 doc / chunk / section

## 13. RAG 评测与更新机制

### 13.1 评测必须拆成两层

#### 层 1：检索质量

- Recall@K
- rerank 后正确 chunk 排名
- ACL leakage rate
- 精确词召回能力

#### 层 2：答案质量

- citation accuracy
- groundedness
- 检索不足时是否保守降级
- 是否过度推断

### 13.2 更新机制

MVP 必须具备：

- 文档新增触发索引
- 文档更新触发重建相关 chunk
- 文档删除 / 失效触发索引清理
- `doc_version` 管理
- reindex 任务可追踪

### 13.3 闭环

```text
新文档接入
 -> 解析 / chunk / metadata
 -> 建索引
 -> retrieval eval
 -> 上线
 -> bad case 回流
 -> 更新评测集与索引策略
```

## 14. 可观测设计

### 14.1 OTel-first

所有核心事件统一映射到 OTel / 结构化事件模型：

- run
- node execution
- model call
- retrieval call
- tool call
- approval interruption
- final output

### 14.2 需要能看到什么

- 每个 run 的唯一 run_id
- workflow 各节点执行情况
- model / retrieval / tool / approval 的基础 trace
- latency、tokens、errors
- 关键操作与审计日志关联

### 14.3 LangSmith / Langfuse / Phoenix 的位置

- LangSmith：开发调试、trace、eval 加速器
- Langfuse / Phoenix：开源或自托管 LLMOps 备选
- OTel + 公司现有监控：生产基础底座

生产原则：

> 不把任意单一 LLMOps 平台作为唯一观测系统。

## 15. 安全设计

### 15.1 Prompt injection 防御

- 明确区分 system / user / retrieved data / tool output
- 检索和工具结果默认不可信
- 高风险动作前再做 policy check

### 15.2 Secret 与网络边界

- secrets 存在 secret manager
- Tool Gateway 使用短期凭证或代理身份
- Agent runtime 默认不拥有企业系统长期高权限凭证
- 企业系统通过 private network / VPC / VPN / private link 接入

### 15.3 Hosted capability 的安全边界

后续如果引入 OpenAI sandbox、hosted tools、browser/computer use：

- 仍然走 capability adapter
- 不允许直接绕过平台 policy
- 结果和 side effect 必须纳入审计

## 16. 成本与性能设计

### 16.1 延迟目标

建议目标：

- 知识库问答 P95 < 8s
- 工单建议流程 P95 < 15s
- 长任务改为异步，不阻塞在线交互

### 16.2 成本控制

- 小模型做分类、风险判定、压缩
- 强模型只处理关键规划与最终答案
- 限制 top-k、context length、tool calls
- 对 workflow 建立 cost dashboard
- 超预算时降级为只读建议模式

## 17. MVP 验收标准

### 17.1 功能闭环

- 能完成知识库问答并给出引用
- 能查询工单并生成摘要
- 能生成处理建议
- 能在审批后更新工单状态或备注

### 17.2 安全治理

- 所有工具调用都经过 Tool Gateway
- 高风险写操作必须审批
- 无权限用户无法检索无权限内容
- 无权限用户无法触发未授权工具

### 17.3 质量正确性

- QA 样本集正确率达到最低目标
- citation 有效率达标
- 工具参数正确率达标
- 信息不足时保守降级

### 17.4 可观测性

- trace 与 audit 能关联
- 失败 case 可定位到模型、检索、工具或策略层

### 17.5 成本性能

- run 有 token / cost 记录
- latency 在目标范围内

### 17.6 运行稳定性

- 工具失败有明确状态
- 审批后可恢复执行
- workflow 失败后状态可追踪

## 18. 路线图

### 18.1 Phase 1：生产级 MVP

目标：

- 知识库问答
- 工单查询 / 摘要 / 建议
- 审批后有限写操作

交付：

- LangGraph 主 runtime
- Tool Gateway / Policy Engine / Approval / Audit 最小闭环
- ACL-aware RAG
- OTel-first trace
- 少量白名单工具

### 18.2 Phase 2：生产增强与可扩展

目标：

- 更稳定的恢复与降级
- 更多白名单工具
- 更细粒度策略
- 更完整评测和成本治理
- 必要时引入 OpenAI capability node

### 18.3 Phase 3：平台化

目标：

- Tool Registry / MCP allowlist
- Prompt / workflow versioning
- Eval 平台
- 多业务线复用
- 更丰富的 specialist agent 与 capability adapters

## 19. 云厂商落地映射

### 19.1 Azure

- Azure OpenAI / Azure AI Search / Entra ID / Azure Monitor
- 适合 Microsoft 生态企业
- Microsoft Agent Framework 作为 Azure/.NET 路线可选

### 19.2 AWS

- Bedrock / IAM / API Gateway / Lambda / OpenSearch / CloudWatch
- 适合已有 AWS 基础设施的企业

### 19.3 GCP

- Vertex AI / Gemini / Vertex AI Search / Cloud Logging
- 适合 BigQuery / GCP 数据生态

### 19.4 OpenAI 专项能力接入

- hosted tools
- sandbox
- realtime / voice
- computer use

这些能力通过 capability adapter 接入，不改变主控制平面。

## 20. 结论

如果把方案压缩成一页：

1. **控制平面**：LangGraph + Tool Gateway + Policy Engine + Approval + Audit + OTel-first。  
2. **执行平面**：specialist nodes + retrieval nodes + tool nodes + 可选 OpenAI capability node。  
3. **RAG**：LlamaIndex 主推，采用结构感知 chunking、Hybrid Search + Rerank、ACL-aware retrieval。  
4. **MVP 边界**：只做知识库 + 工单自动化最小闭环，只开放白名单工具，不开放任意 MCP。  
5. **演进路线**：先建立治理闭环，再增强稳定性，最后平台化。

## 21. 参考资料

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph deploy: https://docs.langchain.com/oss/python/langgraph/deploy
- OpenAI Agents SDK overview: https://developers.openai.com/api/docs/guides/agents
- OpenAI sandbox agents: https://developers.openai.com/api/docs/guides/agents/sandboxes
- OpenAI guardrails and approvals: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- Microsoft Agent Framework overview: https://learn.microsoft.com/en-us/agent-framework/overview/
- LlamaIndex framework docs: https://developers.llamaindex.ai/python/framework/
- Haystack docs: https://docs.haystack.deepset.ai/docs/intro
- Pydantic AI overview: https://pydantic.dev/docs/ai/overview/
- LangSmith pricing: https://www.langchain.com/pricing
- Langfuse docs: https://langfuse.com/docs
- Phoenix docs: https://arize.com/docs/phoenix
