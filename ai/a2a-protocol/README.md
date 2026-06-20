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

## 2. 底层四层模型:A2A 坐在 gRPC 之上(给 gRPC 工程师)

如果你跟我一样「学过 gRPC,以为它就是基于 HTTP/2 的一种编码」,先把这个误会拆掉——**任何 RPC 栈都能拆成四层,A2A 跟 gRPC 根本不在同一层。**

### 2.1 先把 gRPC 拆干净

gRPC 不是「一种编码」,是**四层捆成一个固定套餐**:

| 层 | gRPC 里是谁 | 说明 |
|---|---|---|
| **契约 / IDL** | `.proto` 文件 | 定义有哪些方法、消息长什么样(`service` / `message`) |
| **编码(序列化)** | **Protobuf** | 把消息变成二进制字节 —— **这层才是你说的「编码」** |
| **传输** | **HTTP/2** | 多路复用、流、头压缩、流控 |
| **RPC 约定** | gRPC 自己定的 | 方法名走 `:path = /pkg.Service/Method`、消息加 5 字节长度前缀、状态码放 `grpc-status` trailer、4 种流模式、deadline |

关键:**Protobuf(编码)和 HTTP/2(传输)本来是独立的**。你可以用 Protobuf 不走 HTTP/2,也可以用 HTTP/2 传 JSON。gRPC 只是把它们 + 一套 RPC 约定**绑成一个套餐**。所以正确的一句话是:**gRPC =(Protobuf 编码)+(HTTP/2 传输)+(一套 RPC 方法/状态/流约定),三件一起。** 你之前只抓到了「编码」这一件。

### 2.2 用同一把尺量 A2A

A2A **不替你选传输和编码**,它管的是更上面一层:**「agent 这种服务长什么样、有哪些标准方法、怎么被发现」**。

| 层 | gRPC | **A2A** |
|---|---|---|
| **契约 / 发现** | `.proto` + gRPC reflection | **Agent Card**(`/.well-known/agent-card.json`,一个 JSON)+ 固定的 `a2a.proto` |
| **编码** | Protobuf(二进制) | **JSON**(默认,人能读);走 gRPC 绑定时才是 Protobuf |
| **传输** | 只有 HTTP/2 | **三选一**:① JSON-RPC 2.0 over HTTP(默认)② gRPC ③ HTTP+JSON/REST |
| **方法约定** | 你自己在 `.proto` 里定方法 | **协议帮你定死一组方法**(`SendMessage` / `GetTask`…,见 §3、§5),你不能加方法,只能加 **skill** |

**这就是你之前看不懂的根源**:你拿 gRPC 的脑子去找「A2A 的 `.proto` 在哪、编码是什么」,但 A2A 故意把那两层**留作可选**——它甚至可以直接架在 gRPC 上(那时编码就是 Protobuf、传输就是 HTTP/2,跟你熟的一模一样)。

> 🎯 **核心 aha:「A2A vs gRPC」是个假对立。gRPC 是 A2A 可以选用的三种传输之一。** A2A 真正贡献的是上面那两层——**统一的数据模型 + 统一的方法集 + 统一的发现方式**。MCP 给 agent 接「手和眼」,A2A 让 agent 之间「对话分工」,而 gRPC/JSON-RPC/REST 只是 A2A 底下的「管子」。

### 2.3 一次调用的端到端流程

```
调用方                                          被调 agent
  │  ① GET /.well-known/agent-card.json
  ├──────────────────────────────────────────────►│
  │  ← 名片:我支持 JSONRPC,端点在 https://.../a2a │
  │                                                │
  │  ② 从名片挑一个传输(默认 JSON-RPC)           │
  │  ③ POST 一个 SendMessage 请求                  │
  ├──────────────────────────────────────────────►│  AgentExecutor.execute()
  │                                                │
  │  ← 短任务:直接回一条 Message                   │
  │  ← 长任务:开 Task,SSE 流式推 status/artifact  │
  │◄──────────────────────────────────────────────┤
```

---

## 3. 三种传输绑定(一个抽象操作的三种线上形态)

A2A 规范先定义**抽象操作**(binding-independent),再规定每种传输怎么把它落到线上。同一个 `SendMessage`,三种绑定三张脸:

| 绑定 | 编码 | 方法/路径形态 | 端点形态 | 流式机制 |
|---|---|---|---|---|
| **JSON-RPC 2.0 over HTTP**(默认) | JSON | `"method": "SendMessage"`(PascalCase) | **单端点**,方法在 body 的 `method` 字段 | **SSE**(`text/event-stream`) |
| **gRPC** | Protobuf | `A2AService.SendMessage` | gRPC service 方法 | HTTP/2 原生 server-streaming |
| **HTTP+JSON / REST** | JSON | `POST /message:send` | **多路径**(RESTful) | **SSE** |

> 三种绑定**功能必须等价**,因为它们都从同一个 **canonical `a2a.proto`** 派生(规范原话:all bindings must maintain functional equivalence with `a2a.proto`)。

### 3.1 canonical proto:`A2AService`(你会一眼认出这就是 gRPC service)

`a2a.proto`(包名 `lf.a2a.v1`,LF = Linux Foundation)节选——**这跟你以前写的 gRPC service 几乎重合**,REST 路径是靠 `google.api.http` 注解自动派生出来的:

```proto
syntax = "proto3";
package lf.a2a.v1;

service A2AService {
  // 发消息(短任务):返回 Task 或 Message
  rpc SendMessage(SendMessageRequest) returns (SendMessageResponse) {
    option (google.api.http) = { post: "/message:send" body: "*" };
  }
  // 发消息(流式):返回 SSE / server-stream
  rpc SendStreamingMessage(SendMessageRequest) returns (stream StreamResponse) {
    option (google.api.http) = { post: "/message:stream" body: "*" };
  }
  // 查任务状态
  rpc GetTask(GetTaskRequest) returns (Task) {
    option (google.api.http) = { get: "/tasks/{id=*}" };
  }
  // 取消任务
  rpc CancelTask(CancelTaskRequest) returns (Task) {
    option (google.api.http) = { post: "/tasks/{id=*}:cancel" body: "*" };
  }
  // 重新订阅一个已存在的任务(断线重连)
  rpc SubscribeToTask(SubscribeToTaskRequest) returns (stream StreamResponse) {
    option (google.api.http) = { get: "/tasks/{id=*}:subscribe" };
  }
  // push 回调配置 CRUD(见 §7)
  rpc CreateTaskPushNotificationConfig(TaskPushNotificationConfig) returns (TaskPushNotificationConfig);
  rpc GetTaskPushNotificationConfig(GetTaskPushNotificationConfigRequest) returns (TaskPushNotificationConfig);
  rpc ListTaskPushNotificationConfigs(ListTaskPushNotificationConfigsRequest) returns (ListTaskPushNotificationConfigsResponse);
  rpc DeleteTaskPushNotificationConfig(DeleteTaskPushNotificationConfigRequest) returns (google.protobuf.Empty);
  // 鉴权后才给的「扩展名片」(见 §8)
  rpc GetExtendedAgentCard(GetExtendedAgentCardRequest) returns (AgentCard);
}
```

### 3.2 REST 绑定的 URL 表(从 proto 注解派生)

| 抽象操作 | REST |
|---|---|
| SendMessage | `POST /message:send` |
| SendStreamingMessage | `POST /message:stream`(SSE) |
| GetTask | `GET /tasks/{id}` |
| ListTasks | `GET /tasks` |
| CancelTask | `POST /tasks/{id}:cancel` |
| SubscribeToTask | `GET /tasks/{id}:subscribe`(SSE) |
| Create/Get/List/Delete PushConfig | `…/tasks/{taskId}/pushNotificationConfigs[/{id}]` |
| GetExtendedAgentCard | `GET /extendedAgentCard` |

> `:cancel` / `:subscribe` 这种「路径 + 冒号 + 动词」是 Google AIP 的自定义方法风格,不是打错。

---

## 4. 线上真实字节(不是 SDK 代码,是报文)

### 4.1 `SendMessage`(JSON-RPC,短任务一问一答)

请求 —— POST 到 Agent Card 里声明的那个 JSON-RPC 端点:

```jsonc
POST /a2a/jsonrpc          Content-Type: application/json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "SendMessage",
  "params": {
    "message": {
      "messageId": "msg-001",
      "role": "ROLE_USER",
      "parts": [{ "text": "帮我生成一份报告" }]
    }
  }
}
```

响应 —— `SendMessageResponse` 是个 oneOf,回 `task` 或 `message`:

```jsonc
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "task": {
      "id": "task-123",
      "contextId": "ctx-456",
      "status": { "state": "TASK_STATE_COMPLETED", "timestamp": "2026-06-20T10:00:00Z" },
      "artifacts": [
        { "id": "art-1", "parts": [{ "text": "报告正文…" }] }
      ]
    }
  }
}
```

### 4.2 `SendStreamingMessage`(JSON-RPC,长任务流式)

换方法 `SendStreamingMessage`,响应不再是一个 JSON,而是 **SSE 流**(`Content-Type: text/event-stream`),每个 `data:` 一个 `StreamResponse`(也是 oneOf:`task` / `statusUpdate` / `artifactUpdate` / `message`):

```
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: {"jsonrpc":"2.0","id":1,"result":{"task":{"id":"task-123","status":{"state":"TASK_STATE_SUBMITTED"}}}}

data: {"jsonrpc":"2.0","id":1,"result":{"statusUpdate":{"taskId":"task-123","status":{"state":"TASK_STATE_WORKING"}}}}

data: {"jsonrpc":"2.0","id":1,"result":{"artifactUpdate":{"taskId":"task-123","artifact":{"id":"art-1","parts":[{"text":"部分结果…"}]}}}}

data: {"jsonrpc":"2.0","id":1,"result":{"statusUpdate":{"taskId":"task-123","status":{"state":"TASK_STATE_COMPLETED"},"final":true}}}
```

> 对照你熟的:**gRPC 的 server-streaming 是 HTTP/2 原生流;A2A 在 JSON-RPC/REST 绑定下没有 HTTP/2 流,就用 SSE 来补这个能力。** 选 gRPC 绑定时,流式就直接用回 gRPC 原生 streaming。

**客户端侧其实就这么点事**:GET 名片 → POST 上面那个 JSON-RPC 信封 → 读单个 JSON 或读 SSE 流。本目录的 [`hello_client.py`](./hello_client.py) 干的就是这个。

> ⚠️ **【命名换代,极重要的踩坑点】** 网上 90% 的教程/老 SDK 用的是 **v0.x** 写法,跟 v1.0 不一样,别照抄:
>
> | 维度 | v0.x(满天飞的旧教程) | **v1.0(本文 / 现行 spec)** |
> |---|---|---|
> | JSON-RPC 方法名 | `"message/send"`(slash + 小写) | `"SendMessage"`(**PascalCase**) |
> | Part 结构 | `{"kind":"text","text":...}` 带 `kind` 判别字段 | `{"text": ...}`(**oneOf,无 `kind`**) |
> | Task 状态 | `working` / `completed`(小写) | `TASK_STATE_WORKING` / `TASK_STATE_COMPLETED` |
> | 角色 | `"user"` / `"agent"` | `"ROLE_USER"` / `"ROLE_AGENT"` |
>
> 真要写代码时,**以你装的那版 `a2a-sdk` 官方 sample 为准**(`a2a-samples` 里的 `test_client.py`),别逐字抄上面的报文——v1.0 client API 仍在演进。

---

## 5. 协议核心组件

### 5.1 协议数据模型全清单

这就是「A2A 包含了什么」——一组定死的数据对象(≈ gRPC 的 `message`,只是默认用 JSON):

| 对象 | 关键字段 | 作用 |
|---|---|---|
| **AgentCard** | `name` `description` `provider` `capabilities` `skills[]` `interfaces[]` `securitySchemes` `security` `signature?` | 服务名片 / 发现描述符 |
| **AgentInterface** | `type`(`JSON_RPC_2.0`/`GRPC`/`HTTP_JSON_REST`)`url` `version` | 声明一种传输端点(一张卡可挂多个) |
| **AgentSkill** | `id` `name` `description` `tags` `examples` `inputSchema?` `outputSchema?` | 一个能力(你的业务从这里暴露) |
| **Message** | `messageId` `role`(ROLE_USER/ROLE_AGENT)`parts[]` `contextId?` `taskId?` `referenceTaskIds?` | 一轮对话 |
| **Part** | **oneOf**:`text` / `raw`(字节,base64) / `url` / `data`(JSON);+ `mediaType?` `filename?` | 多模态最小单位 |
| **Task** | `id` `contextId?` `status` `artifacts[]?` `history[]?` | 有状态的长任务 |
| **TaskStatus** | `state`(TaskState)`message?` `timestamp` | 任务当前状态 |
| **TaskState** | 见 §6 的 9 个枚举 | 生命周期状态 |
| **Artifact** | `id` `parts[]` `metadata?` | 任务产出物 |
| **TaskStatusUpdateEvent** | `taskId` `status` `final?` | 流式推的「状态变了」 |
| **TaskArtifactUpdateEvent** | `taskId` `artifact` | 流式推的「出了个产物」 |
| **PushNotificationConfig** | `url`(必填)`token?` `authentication?`(见 §7) | webhook 回调配置 |
| **SecurityScheme** | APIKey / HTTP / OAuth2 / OIDC / mTLS(见 §8) | 鉴权声明 |

> ⚠️ 字段名在 spec 与各家 SDK 之间有小出入。例:spec 叫 `interfaces[]` / `type="JSON_RPC_2.0"`;a2a-sdk(python)叫 `supported_interfaces[]` / `AgentInterface(protocol_binding="JSONRPC")`(见本目录 `hello_server.py`)。概念一样,落地前对一下你那版。

### 5.2 标准方法集(11 个,协议定死,你不能新增)

| 抽象操作 | JSON-RPC `method` | gRPC | 用途 |
|---|---|---|---|
| SendMessage | `SendMessage` | `A2AService.SendMessage` | 发消息(短) |
| SendStreamingMessage | `SendStreamingMessage` | 同名(stream) | 发消息(SSE 流) |
| GetTask | `GetTask` | 同名 | 查任务状态(轮询) |
| ListTasks | `ListTasks` | 同名 | 列任务 |
| CancelTask | `CancelTask` | 同名 | 取消 |
| SubscribeToTask | `SubscribeToTask` | 同名(stream) | 重新订阅已存在任务(断线重连) |
| Create/Get/List/Delete­PushNotificationConfig | 同名 | 同名 | webhook 回调 CRUD(§7) |
| GetExtendedAgentCard | `GetExtendedAgentCard` | 同名 | 鉴权后取扩展名片(§8) |

> 你的「业务」不是靠加方法暴露,而是靠在 Agent Card 里声明 **skills**;所有 skill 都通过上面这几个标准方法进来。

### 5.3 Agent Card —— 一切的起点
挂在 `http://<host>/.well-known/agent-card.json`,字段大致:
- `name` / `description` / `version` / `provider`
- `capabilities`:`streaming`、`push_notifications` 等开关
- `default_input_modes` / `default_output_modes`:默认收发模态(text / 图片 / task-status…)
- `skills[]`:每个 skill 有 `id` / `name` / `description` / `tags` / `examples`
- `supported_interfaces[]`:**v1.0 新结构**,声明每种传输的 `protocol_binding` + `protocol_version` + `url`

### 5.4 两种应答模式(v1.0 强约束,别混用)
- **模式 A:消息直返** —— `execute()` 里 enqueue 一条 `Message` 就结束。适合一问一答。
- **模式 B:Task 生命周期** —— **先 enqueue 一个 `Task`(必须第一个)**,再发 `status_update` / `artifact_update`。适合长任务、流式。
> v1.0 明确:混用 message 和 task 事件、或在初始 Task 之前发 task 更新,**运行时会报错**。

### 5.5 v0.3 → v1.0 破坏性改动(踩坑预警)
| 维度 | v0.3 | v1.0 |
|---|---|---|
| 方法命名 | `message/send`(slash + 小写) | `SendMessage`(PascalCase,见 §4 提示框) |
| 状态/角色枚举 | `submitted` / `user`(小写) | `TASK_STATE_SUBMITTED` / `ROLE_USER`(SCREAMING_SNAKE_CASE) |
| Part 结构 | `Part(TextPart(text=...))` 包一层 / 带 `kind` | `Part(text=...)` 直接挂,字节不用 base64 包壳 |
| AgentCard URL | 顶层 `url=` | 去掉,改 `supported_interfaces=[AgentInterface(...)]` |
| Server 启动 | `A2AStarletteApplication(...)` 包装类 | 去掉,用 `create_*_routes()` 工厂函数拼 Starlette/FastAPI |
| Client 创建 | `ClientFactory().create_client(url)` | `await create_client(url)` |
| 发消息返回 | `AsyncIterator[ClientEvent|Message]` | `AsyncIterator[StreamResponse]`,每个 chunk 只含一种字段(`HasField`) |
| Handler | 可不传 card | `DefaultRequestHandler(agent_card=...)` **必传** |
| helpers | 散落 | 统一到 `a2a.helpers`(`new_text_message`、`get_message_text`…) |

---

## 6. Task 状态机(长任务怎么活)

短任务一问一答用不到 Task。**只要任务可能跑很久、要流式、或要人介入,就走 Task**,它有 9 个状态:

| 状态 | 类别 | 含义 |
|---|---|---|
| `TASK_STATE_UNSPECIFIED` | — | 未知/占位(别用) |
| `TASK_STATE_SUBMITTED` | 活跃 | 已收下,还没开跑 |
| `TASK_STATE_WORKING` | 活跃 | 正在处理 |
| `TASK_STATE_INPUT_REQUIRED` | **中断** | 卡住了,要调用方补输入(human-in-the-loop) |
| `TASK_STATE_AUTH_REQUIRED` | **中断** | 卡住了,要补鉴权 |
| `TASK_STATE_COMPLETED` | 终态 ✓ | 成功 |
| `TASK_STATE_FAILED` | 终态 ✗ | 出错 |
| `TASK_STATE_CANCELED` | 终态 | 被 `CancelTask` 取消 |
| `TASK_STATE_REJECTED` | 终态 | agent 直接拒收 |

```
                         ┌─────────── 再次 SendMessage(同 taskId,补输入/补鉴权)──────────┐
                         ▼                                                                │
 SUBMITTED ──► WORKING ──┼──► INPUT_REQUIRED ───────────────────────────────────────────┘
                         │    AUTH_REQUIRED  ──────────────────────────────────────────(同上)
                         │
                         ├──► COMPLETED   (终态 ✓)
                         ├──► FAILED      (终态 ✗)
                         ├──► CANCELED    (终态,被 CancelTask)
                         └──► REJECTED    (终态,agent 拒收)
```

**多轮(input-required)那条路**才是 Task 的精髓:agent 干到一半发现缺信息 → 把 Task 推到 `INPUT_REQUIRED` 并附一条「我还需要 X」的 Message → 调用方**用同一个 `taskId` 再发一次 `SendMessage` 补上** → Task 回到 `WORKING` 继续。`AUTH_REQUIRED` 同理,只是补的是凭证。这就是 A2A 对「带状态、可中断、可恢复」的长任务的标准建模。

**长任务拿结果有三条路**(按场景选):
1. **SSE 流**:`SendStreamingMessage` / `SubscribeToTask` —— 全程挂着连接,实时推。
2. **轮询**:`GetTask` —— 自己定时查状态,简单但有延迟。
3. **Push webhook**:见 §7 —— 不挂连接,干完回调你。

---

## 7. Push notification webhook(超长任务/断连场景)

任务要跑几分钟到几小时、或客户端根本没法一直挂着 SSE(手机、Serverless、跨网络)时,用 push:**让 agent 干完主动 POST 回来。**

`PushNotificationConfig` 字段:
- `url`(必填)—— 你的 webhook 端点
- `token?` —— 简单共享密钥(回调时带上,供你校验来源)
- `authentication?` —— 更正式的鉴权方案(同 §8 那套 scheme)
- `taskId` / `id` —— 关联哪个任务、哪条配置

**流程:**
```
① 客户端:CreateTaskPushNotificationConfig(taskId, url=https://me/cb, token=...)
② agent 后台慢慢跑……(客户端可以断开,不用挂着)
③ 每次状态/产物变化 & 到终态:agent HTTP POST 到你的 url,body = StreamResponse(同 SSE 那个对象)
④ 到终态(completed/failed/…)后停止;或你 DeleteTaskPushNotificationConfig 主动撤
```

**安全要点**(这是 push 的主要风险面):
- 你的 webhook 是公网入口,**必须验证回调真来自那个 agent**(校验 `token` / 签名 / mTLS),否则任何人都能伪造「任务完成」打你。
- 反过来 agent 侧也该防 SSRF(别被诱导往内网地址 POST)。
- 收到回调通常只当「去 `GetTask` 拉权威状态」的触发信号,别完全信 body。

> SSE vs Push 怎么选:**要实时、连接扛得住 → SSE;任务超长、客户端会断、要可靠送达 → Push。** 两者可并存。

---

## 8. 鉴权 / 安全模型

A2A 让**互不信任、跨组织**的 agent 互通,鉴权是头等大事。模型直接**借用 OpenAPI 那套 SecurityScheme**,声明在 Agent Card 里:

| SecurityScheme | 说明 |
|---|---|
| **APIKeySecurityScheme** | API key,放 header / query(`apiKeyName` + `in`) |
| **HTTPAuthSecurityScheme** | HTTP 标准鉴权:`Basic` / `Bearer` 等 |
| **OAuth2SecurityScheme** | OAuth2 各种 flow(authorizationCode / clientCredentials / deviceCode) |
| **OpenIdConnectSecurityScheme** | OIDC(`openIdConnectUrl`) |
| **MutualTlsSecurityScheme** | 双向 TLS(mTLS) |

**机制:**
- Agent Card 的 `securitySchemes` 声明「我支持哪些鉴权」,`security` 声明「调我必须满足哪些」。
- 客户端按声明带上凭证;agent 对未鉴权请求直接回 `UNAUTHENTICATED` 错误。
- **扩展名片**:公开的 `/.well-known/agent-card.json` 可以只暴露基本信息;`GetExtendedAgentCard` 让**已鉴权**的调用方拿到更全的 skill/能力(权限分层)。

**跨组织的真实风险(别被新闻稿带过去)**:让「不透明(opaque)agent」跨厂商互通,**身份认证、agent 身份、数据暴露**的信任模型尚未充分验证。学术界(arXiv 2505.12490)、Palo Alto、Cloud Security Alliance(MAESTRO 威胁建模)都点过问题。把鉴权/边界当**生产前必须自己设计**的部分,协议给的是机制,不是现成的安全方案。详见 §12。

---

## 9. 最小 demo

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

## 10. A2A vs MCP —— 全场最被反复证实的一点

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

## 11. 主流框架怎么接

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

> 注意区分「框架内多 agent」和「A2A 跨 agent」:OpenAI Agents SDK 的 handoff、LangGraph 的 supervisor 都是**同进程内**的函数调用/状态流转;A2A 是**跨进程、跨网络、跨厂商**的 RPC。前者不需要 A2A,后者才需要。

---

## 12. 生产落地注意(别被新闻稿带节奏)

1. **"production-ready" ≠ 实战验证**。规范刚稳定不久,公开的、有名有姓的大规模部署基本还查不到;早期采用者基本是 beta 测试者。
2. **安全/信任模型是重点风险**。让「不透明 agent」跨组织互通,身份认证、agent 身份、数据暴露的信任模型,学术界(arXiv 2505.12490)、Palo Alto、Cloud Security Alliance(MAESTRO 威胁建模)都点过问题,生产级安全流程尚未充分验证。
3. **架构上限**有人质疑(HiveMQ 等)在大规模 agent 网格下的扩展性。
4. **变化极快**。本文时间线到 2026 年中;半年后数字和格局会过时,落地前重新核版本和 API。

落地前自查三件事:① 你用的框架的 A2A 整合是 **GA 还是 preview**;② 跨组织的**认证/身份**方案怎么做;③ 有没有可参考的**真实案例**。

---

## 13. 面试卡片

**Q:A2A 是什么?解决什么问题?**
> 一套开放标准,让**独立、彼此不透明(opaque)的 AI agent** 能跨平台/厂商/框架互通。核心是 Agent Card(能力发现)+ 标准化消息/任务协议(JSON-RPC 2.0 over HTTP/SSE,v1.0 起还有 gRPC、REST binding)。Google 2025 发起、现在 Linux Foundation 治理,是 agent 互通层的事实标准。

**Q:A2A 和 gRPC 是什么关系?(高频陷阱题)**
> 不是一个层级,不是竞品。**gRPC 是 A2A 三种传输绑定之一**。A2A 定的是上层契约——数据模型(Agent Card / Message / Task / Artifact)+ 标准方法集(SendMessage / GetTask…)+ 发现方式(/.well-known);底下的传输+编码可以选 JSON-RPC(默认,JSON+SSE)、gRPC(Protobuf+HTTP/2)、或 REST。三种绑定都从同一个 `a2a.proto` 派生,功能等价。

**Q:A2A 和 MCP 什么关系?**
> 互补两层。MCP(Anthropic)管 agent 接**工具和上下文**;A2A(Google→LF)管 **agent 之间**协作。常一起用:内部 MCP 接工具,对外 A2A 暴露服务。2025/12 起两者同在 LF 的 AAIF 基金会下。

**Q:A2A 一次调用的流程?**
> 调用方拉对方 `/.well-known/agent-card.json` → 选传输 → 发 `SendMessage` → 对方 AgentExecutor 处理 → 要么直接回一条 Message(短),要么开 Task 流式推 status_update + artifact_update(长任务)。

**Q:Task 有哪些状态?哪些是中断态?长任务怎么拿结果?**
> 9 个 `TASK_STATE_*`:活跃(SUBMITTED/WORKING)、**中断(INPUT_REQUIRED/AUTH_REQUIRED,要调用方用同一 taskId 补输入/补鉴权后继续)**、终态(COMPLETED/FAILED/CANCELED/REJECTED)。拿结果三条路:SSE 流、轮询 GetTask、push webhook。

**Q:Agent Card 里有什么?**
> name/version/provider、capabilities(streaming 等开关)、skills(每个有 id/name/examples/tags)、supported_interfaces(v1.0:每种传输的 binding+version+url)、securitySchemes/security(鉴权)。

**Q:为什么需要 A2A 而不是直接 REST 互调?**
> 标准化了**发现**(Agent Card)、**长任务的状态/产出流**(Task/Artifact 生命周期)、**多模态**和**多传输**,且厂商中立 —— 不同团队/公司的异构 agent 不用两两约定私有契约就能协作。本质是给 agent 生态做了「OpenAPI + gRPC + 服务注册」三合一的统一约定。

**Q:竞品和现状?**
> ACP(IBM)已并入 A2A 并停更;ANP/AGNTCY 等仍小众。agent↔agent 这层基本收敛到 A2A 单一标准。MCP 不是竞品,是互补的另一层。

---

## 14. 引用来源

**一手:**
- A2A 规范:https://a2a-protocol.org/latest/specification/
- A2A 数据定义 / `a2a.proto`:https://a2a-protocol.org/latest/definitions/
- A2A ❤️ MCP:https://a2a-protocol.org/latest/topics/a2a-and-mcp/
- GitHub:https://github.com/a2aproject/A2A · Python SDK:https://github.com/a2aproject/a2a-python · JS SDK:https://github.com/a2aproject/a2a-js · 示例:https://github.com/a2aproject/a2a-samples
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

> 本笔记由一次 deep-research(6 角度 / 25 来源 / 122 论点 → 对抗式核查 25 条,0 被推翻)整理;§2–§8 的协议细节(方法名、`a2a.proto`、TaskState 枚举、传输绑定、鉴权 scheme)另查了 a2a-protocol.org 现行 spec + definitions(2026-06 核对)+ a2a-python v1.0 官方 sample。
