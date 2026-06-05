# A2A(Agent2Agent)协议 实战自学

> 一句话:**A2A 已经是「agent 跟 agent 互通」这一层的事实标准**。Google 2025/04 发起 → 2025/06 捐给 Linux Foundation → 竞品 IBM 的 ACP 在 2025/08 并入 A2A → 2026/03 出第一个稳定版 v1.0.0。它跟 Anthropic 的 **MCP 是互补**(A2A 管 agent↔agent,MCP 管 agent↔工具),不是竞争。

本目录是给**后端工程师**的上手笔记:用 Java/Go 的概念对照协议骨架,跑一个最小 demo,再讲 MCP 关系、框架怎么接、生产注意、面试怎么答。

---

## 0. 现状速览(2026 年中)

| 时间 | 事件 |
|---|---|
| 2025/04/09 | Google Cloud Next 发起 A2A,50+ 合作伙伴 |
| 2025/06/23 | Google 把规范 + SDK + 工具捐给 **Linux Foundation**,Apache 2.0,厂商中立 |
| 2025/08 | **IBM 的 ACP 并入 A2A**,ACP 停止开发(出了 ACP→A2A 迁移指南) |
| 2025/12/09 | LF 成立 **Agentic AI Foundation(AAIF)**,**MCP 也由 Anthropic 捐进来** |
| 2026/03 | **v1.0.0** 首个稳定版;2026/05 补到 v1.0.1 |
| 2026/04 | 宣称支持组织从 ~50 涨到 150+ |

- 七个创始成员:**AWS、Cisco、Google、Microsoft、Salesforce、SAP、ServiceNow**;TSC 再加 **IBM**。
- 官方 6 语言 SDK:Python / Go / JS-TS / Java / .NET / Rust。
- 三大云都接了:AWS Bedrock AgentCore、Azure AI Foundry + Copilot Studio、Google Vertex AI。

> ⚠️ **批判性提醒**:「150+ 组织」「企业生产部署」这类数字几乎都来自 LF/Google 新闻稿(利益相关方自报)。结构性事实(Google 发起、LF 治理、创始成员、云整合)独立可证;但「生产采用广度」目前**没有点名的、有名有姓的大规模案例**。把 "production-ready" 当成「成熟度姿态」,不是「已大规模实战验证」。

---

## 1. 心智模型:用后端概念对照 A2A

A2A 本质就是**给 agent 之间定了一套标准的「服务发现 + RPC」契约**。你熟的东西基本都能对上:

| A2A 概念 | 你已经会的对照物 | 说明 |
|---|---|---|
| **Agent Card**(`/.well-known/agent-card.json`) | 服务描述文件 / OpenAPI spec / gRPC reflection | agent 的「能力名片」:叫什么、会哪些 skill、走哪些传输、要不要鉴权 |
| `/.well-known/` 固定路径 | 服务注册中心约定端点 | 调用方只要知道域名,就能拉到名片做发现 |
| **Transport**(JSONRPC / HTTP+JSON / gRPC) | 你在 Go 里写的 gRPC / REST | 同一个 agent 可同时挂多种传输,调用方挑一个 |
| **Message / Part** | 请求/响应 body(多模态) | v1.0 里 `Part` 统一了:`text` / `raw` 字节 / `url` / `data` 直接挂在 Part 上 |
| **Task**(submitted→working→completed) | 异步任务 / Future / 带状态的 Job | 长任务不是一问一答,而是发个 Task 然后流式推状态 |
| **Artifact** | 任务的最终产出物 | agent 干完活吐出来的结果(可多个、可分块流式) |
| **AgentExecutor** | 你的 Servlet / gRPC service impl | 真正跑业务逻辑的地方,实现 `execute()` / `cancel()` |
| **Streaming(SSE)** | server-streaming gRPC | 边算边推 token / 状态 |

一句话串起来:**调用方拉对方 Agent Card → 挑个传输 → 发 Message → 对方 AgentExecutor 处理 → 要么直接回一条 Message,要么开个 Task 流式推状态 + 吐 Artifact。**

---

## 2. 协议核心组件

### 2.1 Agent Card —— 一切的起点
挂在 `http://<host>/.well-known/agent-card.json`,字段大致:
- `name` / `description` / `version` / `provider`
- `capabilities`:`streaming`、`push_notifications` 等开关
- `default_input_modes` / `default_output_modes`:默认收发模态(text / 图片 / task-status…)
- `skills[]`:每个 skill 有 `id` / `name` / `description` / `tags` / `examples`
- `supported_interfaces[]`:**v1.0 新结构**,声明每种传输的 `protocol_binding` + `protocol_version` + `url`

### 2.2 两种应答模式(v1.0 强约束,别混用)
- **模式 A:消息直返** —— `execute()` 里 enqueue 一条 `Message` 就结束。适合一问一答。
- **模式 B:Task 生命周期** —— **先 enqueue 一个 `Task`(必须第一个)**,再发 `status_update` / `artifact_update`。适合长任务、流式。
> v1.0 明确:混用 message 和 task 事件、或在初始 Task 之前发 task 更新,**运行时会报错**。

### 2.3 v0.3 → v1.0 破坏性改动(踩坑预警)
| 维度 | v0.3 | v1.0 |
|---|---|---|
| Part 结构 | `Part(TextPart(text=...))` 包一层 | `Part(text=...)` 直接挂,字节不用 base64 |
| AgentCard URL | 顶层 `url=` | 去掉,改 `supported_interfaces=[AgentInterface(...)]` |
| 枚举 | `submitted` / `user` | `TASK_STATE_SUBMITTED` / `ROLE_USER`(SCREAMING_SNAKE_CASE) |
| Server 启动 | `A2AStarletteApplication(...)` 包装类 | 去掉,用 `create_*_routes()` 工厂函数拼 Starlette/FastAPI |
| Client 创建 | `ClientFactory().create_client(url)` | `await create_client(url)` |
| 发消息返回 | `AsyncIterator[ClientEvent|Message]` | `AsyncIterator[StreamResponse]`,每个 chunk 只含一种字段(`HasField`) |
| Handler | 可不传 card | `DefaultRequestHandler(agent_card=...)` **必传** |
| helpers | 散落 | 统一到 `a2a.helpers`(`new_text_message`、`get_message_text`…) |

---

## 3. 最小 demo

> **保证能跑的路径(推荐先跑这个)**:官方 helloworld sample,2 分钟起来:
> ```bash
> git clone https://github.com/a2aproject/a2a-samples.git
> cd a2a-samples/samples/python/agents/helloworld
> uv run .                      # 起服务端
> # 另开一个终端:
> uv run test_client.py         # 跑客户端
> ```
> 然后浏览器开 `http://127.0.0.1:41241/.well-known/agent-card.json` 看名片长啥样。

本目录的 [`hello_server.py`](./hello_server.py) / [`hello_client.py`](./hello_client.py) 是**精简骨架**,只留 JSON-RPC + Agent Card,去掉官方 sample 里的 gRPC/REST/v0.3 兼容噪音,用来**对着读、理解每个零件**。

⚠️ 这两个文件按 v1.0 官方 sample + 迁移指南整理,**未在本机实跑**;v1.0 client API 还在演进,若 import / 签名对不上,**以官方 sample 的 `test_client.py` 为准**。

骨架长这样(完整见 .py 文件):

```python
# 服务端核心四步
agent_card = AgentCard(name=..., skills=[AgentSkill(...)],
                       supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", ...)])
handler = DefaultRequestHandler(agent_executor=HelloExecutor(),
                                task_store=InMemoryTaskStore(),
                                agent_card=agent_card)   # v1.0 必传 card
routes = [*create_agent_card_routes(agent_card),
          *create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc")]
app = Starlette(routes=routes)                            # uvicorn.run(app, ...)

# 你的逻辑只在这
class HelloExecutor(AgentExecutor):
    async def execute(self, context, event_queue):
        q = context.get_user_input()
        await event_queue.enqueue_event(new_text_message(f"Hello! 你说: {q}", role=Role.ROLE_AGENT))
```

安装:`uv add a2a-sdk`(或 `pip install a2a-sdk`);要 FastAPI 就 `a2a-sdk[fastapi]`。

---

## 4. A2A vs MCP —— 全场最被反复证实的一点

**不是二选一,是两层,经常一起用:**

```
你的 Agent
  ├─ 对「工具 / 数据 / 上下文」  → 用 MCP   (Anthropic,2024/11)
  └─ 对「别的 Agent」协作/委派    → 用 A2A   (Google → LF,2025/04)
```

- 规范里专门有 **Appendix B「Relationship to MCP」**,官方还有一页叫 **"A2A ❤️ MCP"**。
- Google 原话:*"A2A complements Anthropic's Model Context Protocol (MCP), which provides tools and context to agents."*
- 现在两者**同在 AAIF 基金会**下,更坐实互补定位。
- 唯一灰色地带:当一个 agent 既协调子 agent、又自己控制工具时,边界**可能**模糊 —— 但没有来源否认互补框架。

记忆口诀:**MCP 给 agent 接「手和眼」(工具/数据),A2A 让 agent 之间「对话和分工」。**

---

## 5. 主流框架怎么接

A2A 是**框架中立**的协议层,主流 agent 框架基本都有桥接(成熟度 GA/preview 不一,落地前自己核一下版本):

| 框架 / 平台 | 接入方式 |
|---|---|
| **Google ADK**(Agent Development Kit) | 原生,A2A 的「亲儿子」,`to_a2a()` 直接把 ADK agent 暴露成 A2A 服务 |
| **LangGraph / LangChain** | 官方/社区桥接,把 graph 包成 A2A server,或作为 A2A client 调远端 agent |
| **Microsoft Semantic Kernel / Agent Framework** | 微软博客有 multi-agent + A2A 示例;Azure AI Foundry / Copilot Studio 平台级支持 |
| **CrewAI / AutoGen** | 社区集成,把 crew/团队暴露为可被 A2A 调用的 agent |
| **三大云** | AWS Bedrock AgentCore、Azure AI Foundry、Google Vertex AI Agent Engine |

> ⚠️ 这次调研确认了**云平台级**整合;**框架级**整合的深度(GA 还是 preview)**没逐一深挖**,是待验证项。

**典型组合架构**:用某个框架(ADK/LangGraph)写 agent 内部逻辑 → 内部用 **MCP** 接工具/数据库 → 对外用 **A2A** 暴露成可被别的 agent 发现和调用的服务。

---

## 6. 生产落地注意(别被新闻稿带节奏)

1. **"production-ready" ≠ 实战验证**。规范刚稳定不久,公开的、有名有姓的大规模部署基本还查不到;早期采用者基本是 beta 测试者。
2. **安全/信任模型是重点风险**。让「不透明 agent」跨组织互通,身份认证、agent 身份、数据暴露的信任模型,学术界(arXiv 2505.12490)、Palo Alto、Cloud Security Alliance(MAESTRO 威胁建模)都点过问题,生产级安全流程尚未充分验证。
3. **架构上限**有人质疑(HiveMQ 等)在大规模 agent 网格下的扩展性。
4. **变化极快**。本文时间线到 2026 年中;半年后数字和格局会过时,落地前重新核版本和 API。

落地前自查三件事:① 你用的框架的 A2A 整合是 **GA 还是 preview**;② 跨组织的**认证/身份**方案怎么做;③ 有没有可参考的**真实案例**。

---

## 7. 面试卡片

**Q:A2A 是什么?解决什么问题?**
> 一套开放标准,让**独立、彼此不透明(opaque)的 AI agent** 能跨平台/厂商/框架互通。核心是 Agent Card(能力发现)+ 标准化消息/任务协议(JSON-RPC 2.0 over HTTP/SSE,v1.0 起还有 gRPC、REST binding)。Google 2025 发起、现在 Linux Foundation 治理,是 agent 互通层的事实标准。

**Q:A2A 和 MCP 什么关系?**
> 互补两层。MCP(Anthropic)管 agent 接**工具和上下文**;A2A(Google→LF)管 **agent 之间**协作。常一起用:内部 MCP 接工具,对外 A2A 暴露服务。2025/12 起两者同在 LF 的 AAIF 基金会下。

**Q:A2A 一次调用的流程?**
> 调用方拉对方 `/.well-known/agent-card.json` → 选传输 → 发 Message → 对方 AgentExecutor 处理 → 要么直接回一条 Message(短),要么开 Task 流式推 status_update + artifact_update(长任务)。

**Q:Agent Card 里有什么?**
> name/version/provider、capabilities(streaming 等开关)、skills(每个有 id/name/examples/tags)、supported_interfaces(v1.0:每种传输的 binding+version+url)、鉴权要求。

**Q:为什么需要 A2A 而不是直接 REST 互调?**
> 标准化了**发现**(Agent Card)、**长任务的状态/产出流**(Task/Artifact 生命周期)、**多模态**和**多传输**,且厂商中立 —— 不同团队/公司的异构 agent 不用两两约定私有契约就能协作。本质是给 agent 生态做了「OpenAPI + gRPC + 服务注册」三合一的统一约定。

**Q:竞品和现状?**
> ACP(IBM)已并入 A2A 并停更;ANP/AGNTCY 等仍小众。agent↔agent 这层基本收敛到 A2A 单一标准。MCP 不是竞品,是互补的另一层。

---

## 8. 引用来源

**一手:**
- A2A 规范:https://a2a-protocol.org/latest/specification/
- A2A ❤️ MCP:https://a2a-protocol.org/latest/topics/a2a-and-mcp/
- GitHub:https://github.com/a2aproject/A2A · Python SDK:https://github.com/a2aproject/a2a-python · 示例:https://github.com/a2aproject/a2a-samples
- v1.0 公告:https://a2a-protocol.org/latest/announcing-1.0/
- Google 发起:https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- Google 捐 LF:https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/
- LF 立项:https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents
- LF 一周年(150+ 组织 / 云落地):https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year
- ACP 并入 A2A:https://lfaidata.foundation/communityblog/2025/08/29/acp-joins-forces-with-a2a-under-the-linux-foundations-lf-ai-data/
- AAIF 成立 + MCP 捐赠:https://www.linuxfoundation.org/press/agentic-ai-foundation

**批判/安全视角:**
- A2A 安全分析:https://arxiv.org/html/2505.12490v3
- 协议综述:https://arxiv.org/abs/2505.02279 · https://arxiv.org/abs/2505.03864
- CSA MAESTRO 威胁建模:https://cloudsecurityalliance.org/blog/2025/04/30/threat-modeling-google-s-a2a-protocol-with-the-maestro-framework
- Palo Alto A2A 风险:https://live.paloaltonetworks.com/t5/community-blogs/safeguarding-ai-agents-an-in-depth-look-at-a2a-protocol-risks/ba-p/1235996

> 本笔记由一次 deep-research(6 角度 / 25 来源 / 122 论点 → 对抗式核查 25 条,0 被推翻)整理;代码部分另查了 a2a-python v1.0 官方 sample + 迁移指南。
