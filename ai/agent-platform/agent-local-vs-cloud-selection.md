# Agent 实现方案选型：本地、自建云上与托管云上

> 时间点：2026-04-24  
> 场景：企业知识库 + 工单/任务自动化 Agent 平台  
> 读者：架构评审 / 技术负责人  
> 目标：在生产级 MVP 到平台化演进之间，给出一套治理优先、云中立、可落地的选型结论。

## 1. 背景与目标

这份文档回答两个问题：

1. 企业级 Agent 平台应该优先选本地、自建云上，还是托管云上？
2. 在云中立、治理优先的前提下，Agent 主框架、RAG 路线、观测体系和工具接入标准应该怎么选？

本文不把 Agent 理解成一个简单的 LLM tool loop，而把它视为一套受控的分布式系统。对互联网公司来说，真正决定成败的通常不是模型本身，而是：

- 状态持久化与恢复
- 权限、审批、审计边界
- RAG 质量与 ACL 过滤
- 工具接入治理
- 观测与评测闭环
- 供应商锁定与长期可迁移性

## 2. 决策约束

本次选型按以下约束进行：

- **云中立**：不能把平台核心能力绑定在单一云厂商或单一模型厂商上。
- **治理优先**：Tool Gateway、Policy Engine、Approval、Audit 必须是平台统一能力，而不是散落在框架内部。
- **生产级 MVP 到平台化**：第一期要能安全落地，后续能扩展为多业务线共享平台。
- **主场景明确**：第一期围绕企业知识库问答和工单自动化，不做通用 Agent 平台。
- **RAG 是核心能力层**：知识获取、引用、权限边界不能被简化成“向量库 top-k”。
- **观测可替换**：不能把 LangSmith 或任何单一 LLMOps 产品作为唯一生产依赖。

## 3. 评估维度与加权标准

### 3.1 评估维度

| 维度 | 关注点 |
|---|---|
| 状态持久化 | checkpoint、thread state、长任务恢复、失败续跑 |
| 中断恢复 / Human-in-the-loop | 审批、人工接管、中断后继续执行 |
| 控制权 | 是否容易把 Tool Gateway、Policy Engine、Model Gateway 外置 |
| 平台化适配 | 是否适合作为多业务线共享 runtime |
| 供应商锁定风险 | 是否天然绑定某个模型厂商、云平台、LLMOps 平台 |
| 多模型 / 多云中立 | 是否容易接入自定义模型网关和跨云部署 |
| 可观测性可替换 | 是否能用 OTel / 自有审计替代框架官方 SaaS |

### 3.2 加权标准

正文使用“互联网公司偏治理”的加权评分：

| 维度 | 权重 |
|---|---:|
| 状态持久化 | 20% |
| 中断恢复 / Human-in-the-loop | 20% |
| 控制权 | 15% |
| 平台化适配 | 15% |
| 供应商锁定风险 | 15% |
| 多模型 / 多云中立 | 10% |
| 可观测性可替换 | 5% |

这组权重的含义是：我们优先选择一个适合做平台控制平面的 runtime，而不是只追求单框架的开箱即用体验。

## 4. 部署模式选型：本地 / 自建云上 / 托管云上 / 混合

### 4.1 结论

推荐采用：

> **云上生产 + 本地开发调试 + 私有工具网关** 的混合方案。

### 4.2 对比

| 维度 | 纯本地 / 内网自建 | 托管云上 | 混合方案 |
|---|---|---|---|
| 上线速度 | 慢 | 快 | 中 |
| 数据控制 | 最强 | 依赖云厂商配置 | 关键数据留私网 |
| 模型能力 | 受本地算力限制 | 最新模型可直连 | 可按任务路由 |
| 运维成本 | 高 | 低到中 | 中 |
| 伸缩性 | 自己做 | 平台承担 | 核心服务云上伸缩 |
| 观测与评测 | 需要自建 | 平台能力较强 | 可组合自建与托管 |
| 锁定风险 | 低 | 高 | 中低 |
| 适合阶段 | 研究 / 强监管 | 快速试点 | 生产落地 |

### 4.3 决策理由

- **不选纯本地**：对于互联网公司，第一期纯本地往往把团队拖进模型推理、沙箱、观测和 GPU 运维，成本过高。
- **不选纯托管云 Agent 平台**：速度快，但锁定风险大，且治理能力容易散落到供应商平台里。
- **选择混合方案**：本地负责开发与回放调试，云上负责生产运行，企业工具通过私有 Tool Gateway 接入。

## 5. Agent 框架选型

候选聚焦在四类“可作为核心 runtime 的框架”：

- LangGraph
- OpenAI Agents SDK
- Pydantic AI
- Microsoft Agent Framework

其他工具的定位：

- **LlamaIndex / Haystack**：偏 RAG 与数据层，不作为主编排框架
- **CrewAI**：适合任务型多角色自动化，不建议做平台主 runtime
- **Dify / Flowise / n8n**：适合 PoC 和运营配置层，不适合作为治理中心

### 5.1 加权评分表

评分标准：1-5 分，5 分最好。

| 框架 | 状态持久化 | 中断恢复 | 控制权 | 平台化适配 | 锁定风险 | 多模型 / 多云中立 | 可观测性可替换 | 加权总分 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LangGraph | 5 | 5 | 5 | 5 | 4 | 5 | 4 | **4.80 / 5** |
| Pydantic AI | 3 | 3 | 5 | 2 | 5 | 5 | 4 | **3.70 / 5** |
| Microsoft Agent Framework | 4 | 4 | 4 | 4 | 2 | 3 | 4 | **3.60 / 5** |
| OpenAI Agents SDK | 4 | 4 | 4 | 3 | 2 | 2 | 3 | **3.30 / 5** |

### 5.2 结论

> **主框架选择 LangGraph。**  
> Pydantic AI 保留为 specialist agent / typed service 备选。  
> Microsoft Agent Framework 作为 Azure/.NET 路线映射保留。  
> OpenAI Agents SDK 不做主框架，只作为 OpenAI 专项能力适配器。

## 6. 为什么主框架选 LangGraph

### 6.1 状态与恢复能力最匹配生产 Agent

LangGraph 的核心价值不在“会不会 tool calling”，而在于它把以下能力放在核心心智模型里：

- graph/state
- checkpoint
- interrupt / resume
- thread state
- human-in-the-loop
- fault tolerance

这正好对应企业 Agent 平台最真实的问题：长任务、审批恢复、失败重试、断点续跑、状态审计。

### 6.2 最适合把治理能力外置到平台层

我们明确要求以下能力由平台统一掌控：

- Tool Gateway
- Policy Engine
- Approval Flow
- Audit Log
- Model Gateway
- OTel-first observability

LangGraph 更像一个低层 workflow runtime，天然适合被这些平台能力包住。它不会强迫平台把治理中心放回框架内部。

### 6.3 云中立和模型中立更符合长期演进

LangGraph 本身并不天然绑定某个云平台或某个模型厂商。它可以：

- 接自定义 Model Gateway
- 接自定义 Tool Gateway
- 用 LangSmith 增强调试，但不强依赖 LangSmith
- 跑在任意云、容器、Kubernetes 或自建控制平面上

这对互联网公司更重要，因为平台需要保留后续迁移和多供应商路由空间。

## 7. 为什么不选其他框架做主框架

### 7.1 OpenAI Agents SDK：适合专项能力，不适合主控制平面

OpenAI Agents SDK 官方能力很完整，尤其强在：

- tools
- handoffs
- guardrails
- human review
- tracing
- MCP
- sandbox

但它的最佳体验明显偏向 OpenAI 生态。对于云中立、治理优先的平台：

- 模型与工具链绑定更强
- tracing / hosted tools / sandbox 更偏向 OpenAI 平台
- 容易让平台治理能力回流到供应商 SDK

因此它更适合做：

- hosted tools
- sandbox
- voice / realtime
- computer use

这些专项能力的适配器，而不是整个平台的主控制平面。

### 7.2 Pydantic AI：适合 specialist agent，不是主 workflow runtime

Pydantic AI 的优势非常明确：

- 强类型输入输出
- 结构化输出校验
- dependency injection
- Python/FastAPI 风格体验
- model-agnostic

它很适合：

- 风险分类 Agent
- 结构化提取 Agent
- typed tool proxy
- 规则较强的专家 Agent

但它不是最适合作为平台级 workflow runtime。它更像“生产级 Python Agent 框架”，而不是“平台级控制平面”。

### 7.3 Microsoft Agent Framework：适合 Azure/.NET 路线，不是中立主线

Microsoft Agent Framework 在以下场景有竞争力：

- Azure AI Foundry
- Entra ID
- Microsoft 365 / Teams / SharePoint
- .NET 企业应用

它的 workflow、checkpointing、telemetry 都不错，但它的优势主要来自 Microsoft 企业生态整合。对“云中立”的主方案，它更适合作为 Azure/.NET 映射路线，而不是默认底座。

## 8. 可观测与 LLMOps 选型

### 8.1 结论

> **可观测层采用 OTel-first。LangSmith 作为开发调试与评测加速器，可选但非硬依赖。**

### 8.2 LangSmith 的价值

LangSmith 对 LangGraph 的价值主要在于：

- trace 可视化调试体验非常好
- 可看 prompt、tool call、异常、中间状态
- 方便做 dataset / eval / annotation
- LangGraph Studio 与 LangSmith 的联动体验最好

### 8.3 LangSmith 的边界

对于互联网公司，LangSmith 不能被当成唯一生产观测依赖，原因包括：

- trace 里可能包含 prompt、检索片段、工具参数和工具结果
- SaaS 成本与留存策略需要单独评估
- 高敏数据场景可能面临数据出域要求
- trace 不等于 audit
- 一旦 prompt、dataset、eval、review 全部沉进去，迁移成本会上升

因此更稳的表达是：

> LangSmith 是推荐的开发调试和评测工具，但生产体系必须同时保留 OTel、结构化 audit log 和可替换的 LLMOps 出口。

### 8.4 备选方案

| 方案 | 定位 | 适合什么 |
|---|---|---|
| LangSmith | LangGraph 原生 LLMOps | 开发调试、trace、eval、prompt 迭代 |
| Langfuse | 开源 / self-host LLM observability | 数据控制要求高、希望可自托管 |
| Phoenix | 开源 tracing / eval | 适合 OTel/OpenInference 友好的团队 |
| OTel + Tempo/Jaeger/Grafana | 标准观测底座 | 需要最大程度复用公司现有监控栈 |

## 9. RAG 方案选型

### 9.1 结论

> **RAG 采用“开源框架 + 托管检索底座”的路线。**  
> 主推 LlamaIndex，Haystack 作为备选。  
> 检索策略采用 Hybrid Search + Rerank。  
> 权限策略采用 ACL-aware retrieval。

### 9.2 为什么企业场景不能只靠长上下文

在企业知识库场景下，只靠更长上下文通常会遇到：

- 权限边界难控制
- 成本和延迟变差
- 引用与来源难以严格控制
- 文档更新后难以保证 freshness
- 工单号、错误码、配置项这类精确召回不稳定

因此必须把 RAG 当成独立能力层，而不是长上下文的附庸。

### 9.3 为什么不是 vector-only

vector-only 在企业知识库场景里有明显问题：

- 对错误码、工单号、术语、产品名的精确召回不稳
- FAQ、SOP 标题类文档容易被语义相近但不精确的片段挤占
- 在 ACL 和 citation 要求强的场景里，误召回成本更高

因此默认推荐：

> **keyword / BM25 + vector + metadata filter + rerank**

### 9.4 为什么选“开源框架 + 托管检索底座”

- 比纯自建更现实：不必从零重写 parser、chunking、embedding、retrieval pipeline
- 比纯云厂商 Knowledge Base 更稳：保留 retrieval contract、ACL、citation、eval 的控制权
- 最适合 MVP 到平台化演进：开源框架负责能力封装，底座服务负责弹性和运维

### 9.5 RAG 组件建议

| 层 | 推荐 |
|---|---|
| 接入与检索编排 | LlamaIndex 主推，Haystack 备选 |
| 搜索 / 向量底座 | Elasticsearch / OpenSearch / pgvector / Milvus / 托管向量库 |
| OCR / 解析 | 可托管或外购 |
| Rerank | 独立 reranker，可托管或模型服务化 |

### 9.6 RAG 的关键治理要求

- 结构感知 chunking，而不是简单固定长度切分
- metadata 作为 retrieval contract 核心资产
- ACL 前置到检索阶段
- citation 输出前再次校验权限
- bad case 回流为检索评测样本
- 文档版本、增量更新、reindex 成为平台能力

## 10. 工具接入标准选型

### 10.1 结论

平台工具接入标准按三类支持：

- function tools
- OpenAPI tools
- MCP tools

但这不意味着第一期支持任意工具自由接入。

### 10.2 MVP 阶段

只支持：

- 平台审核并登记的白名单工具
- 少量场景化 MCP / OpenAPI / function tools
- 统一通过 Tool Gateway 注册和路由

明确不支持：

- 用户自行添加任意 MCP server
- 任意 OpenAPI 动态注册
- 任意数据库 / 任意 SaaS 自由接入

### 10.3 平台化阶段

后续可以建设：

- Tool Registry
- MCP allowlist
- 工具审核与版本治理
- 权限模板
- 工具健康状态与下线机制

因此文档表述应为：

> 平台化阶段支持标准化的可扩展工具接入体系，而不是无约束的任意工具接入。

## 11. 最终推荐方案

### 11.1 主结论

| 层级 | 推荐 |
|---|---|
| 主 runtime | LangGraph |
| OpenAI 专项能力 | OpenAI Agents SDK capability adapter |
| RAG 框架 | LlamaIndex 主推，Haystack 备选 |
| 检索策略 | Hybrid Search + Rerank |
| 权限策略 | ACL-aware retrieval |
| 工具接入 | Tool Gateway + Policy Engine 统一入口 |
| 可观测 | OTel-first，LangSmith 可选，Langfuse/Phoenix 可替换 |
| 部署模式 | 云上生产 + 本地调试 + 私有工具网关 |

### 11.2 一句话版本

> 主框架选 LangGraph，不是因为它某个单点能力最花哨，而是因为它在状态恢复、治理外置、云中立这三个维度上最适合作为企业 Agent 平台的控制平面。

## 12. 风险与取舍

### 12.1 工具越权

风险：

- Agent 直接越权访问企业系统
- 工具参数被模型构造成危险操作

取舍与缓解：

- 所有工具必须过 Tool Gateway
- 高风险写操作必须审批
- Tool Gateway 记录 before/after diff

### 12.2 Prompt injection / 数据污染

风险：

- 文档内容伪装成系统指令
- 工具结果诱导危险操作

取舍与缓解：

- system、user、retrieved data、tool output 明确分层
- 高风险工具前做 policy check
- 检索和工具输出默认不可信

### 12.3 成本失控

风险：

- tool loop 过长
- 上下文膨胀
- tracing / eval 成本被低估

取舍与缓解：

- Model Gateway 做路由与预算控制
- 限制 max steps / max tool calls / top-k
- trace 做采样和分级留存

### 12.4 效果漂移

风险：

- prompt、模型、工具变化后质量悄悄退化

取舍与缓解：

- 离线 eval dataset
- bad case 回流
- regression suite

### 12.5 平台复杂度失控

风险：

- 第一阶段同时引入太多框架、能力和开放接入

取舍与缓解：

- 主 runtime 只选 LangGraph
- OpenAI Agents SDK 只做专项能力适配器
- MVP 严格限制业务边界和工具范围

## 13. 云厂商映射

### 13.1 Azure

适合：

- Entra ID / Teams / SharePoint / Azure OpenAI / Azure AI Search
- .NET / Microsoft 企业应用为主

映射建议：

- LangGraph 仍做主 runtime
- Azure 提供模型、搜索、身份、存储与监控底座
- Microsoft Agent Framework 作为 Azure/.NET 分支可选

### 13.2 AWS

适合：

- Bedrock、IAM、Lambda、API Gateway、S3、OpenSearch 生态

映射建议：

- LangGraph 主 runtime
- Bedrock / AgentCore 作为模型与专项能力来源
- Tool Gateway 与审计体系保持自有

### 13.3 GCP

适合：

- Gemini、Vertex AI、BigQuery、Vertex AI Search

映射建议：

- LangGraph 主 runtime
- Vertex AI / Gemini 提供模型和搜索底座
- 控制平面保持云中立

### 13.4 OpenAI

适合：

- 需要 hosted tools、sandbox、realtime、computer use

映射建议：

- OpenAI Agents SDK 不做主框架
- 只作为 OpenAI 能力节点被 LangGraph workflow 调度

## 14. 结论摘要

如果只保留评审会上的三句结论：

1. **部署模式**：选择云上生产 + 本地调试 + 私有工具网关的混合方案。  
2. **主 runtime**：选择 LangGraph，统一控制平面；OpenAI Agents SDK 仅作专项能力适配器。  
3. **核心治理**：Tool Gateway、Policy Engine、Approval、Audit、OTel-first observability 必须由平台掌控，RAG 采用开源框架 + 托管检索底座，默认 Hybrid Search + Rerank + ACL-aware retrieval。

## 15. 附录：等权重评分表

供读者参考的中立视角对比：

| 框架 | 状态持久化 | 中断恢复 | 控制权 | 平台化适配 | 锁定风险 | 多模型 / 多云中立 | 可观测性可替换 | 总分 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LangGraph | 5 | 5 | 5 | 5 | 4 | 5 | 4 | **33** |
| Pydantic AI | 3 | 3 | 5 | 2 | 5 | 5 | 4 | **27** |
| Microsoft Agent Framework | 4 | 4 | 4 | 4 | 2 | 3 | 4 | **25** |
| OpenAI Agents SDK | 4 | 4 | 4 | 3 | 2 | 2 | 3 | **22** |

## 16. 参考资料

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph deploy: https://docs.langchain.com/oss/python/langgraph/deploy
- LangGraph Studio: https://docs.langchain.com/oss/javascript/langgraph/studio
- OpenAI Agents SDK overview: https://developers.openai.com/api/docs/guides/agents
- OpenAI orchestration and handoffs: https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI guardrails and approvals: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- OpenAI MCP integration: https://developers.openai.com/api/docs/guides/agents/integrations-observability#mcp
- OpenAI sandbox agents: https://developers.openai.com/api/docs/guides/agents/sandboxes
- Microsoft Agent Framework overview: https://learn.microsoft.com/en-us/agent-framework/overview/
- LlamaIndex framework docs: https://developers.llamaindex.ai/python/framework/
- LlamaIndex multi-agent / AgentWorkflow: https://developers.llamaindex.ai/python/framework/understanding/agent/multi_agent/
- Pydantic AI overview: https://pydantic.dev/docs/ai/overview/
- LangSmith pricing: https://www.langchain.com/pricing
- Langfuse docs: https://langfuse.com/docs
- Phoenix docs: https://arize.com/docs/phoenix
- Anthropic MCP docs: https://docs.anthropic.com/en/docs/mcp
