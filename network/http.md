# HTTP 协议系统学习与排障手册

更新时间：2026-04-17

**上下文**：
- **上游**（读本文前建议先懂）：[`basic.md`](./basic.md)（TCP 状态机、TIME_WAIT 根因）、[`socket-io.md`](./socket-io.md)（连接池实现基础）
- **下游**（读完可以接着看）：[`websocket.md`](./websocket.md)（HTTP 升级双向）、[`sse.md`](./sse.md)（HTTP 单向流）
- **索引**：[`README.md`](./README.md)

目标：读完你应该能——

- 在脑子里画出 `curl https://example.com/api` 从输入到返回的**完整生命周期**，并知道每一段会在哪一章讲透
- 看到任意一条报文（请求或响应），能说出**每个字段为什么在这**、**缺了会怎样**、**被中间盒改过会怎样**
- 看到状态码能**分诊**，而不是翻表查含义
- 线上出问题时，按"症状 → 嫌疑层 → 工具"的顺序定位，而不是瞎试

与其他实时协议对比见 [`实时通信协议选型.md`](./实时通信协议选型.md)、[`websocket.md`](./websocket.md)、[`sse.md`](./sse.md)。

---

## 0. 导读：怎么读这份文档

**两分钟速览**：HTTP 是一个**建立在 TCP（HTTP/3 是 UDP）之上的、基于请求-响应的文本协议**（HTTP/2、/3 已二进制化，但语义仍是文本模型）。它的核心抽象是：客户端用**方法 + URL + 头 + 体**问一个问题，服务端用**状态码 + 头 + 体**回答。其余所有复杂度——连接管理、缓存、认证、跨域、压缩、代理链路——都是**围绕这个基本模型的工程妥协**。把这个模型刻进脑子，排障时你就知道每一层可能在哪里动过手脚。

**两条阅读路线**：

### 路线 A：系统学习（从头读）

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

### 路线 B：我线上出事了（按症状跳）

| 症状 | 先看 | 再看 |
|---|---|---|
| 请求卡住不返回 | §15 慢请求分段 | §6 连接管理 / §13 代理 |
| 504 Gateway Timeout | §4 状态码 / §13 代理 | §6 连接池 / §15 |
| 502 Bad Gateway | §4 / §13 | §8 TLS 握手 |
| 偶发慢请求 | §15 | §6 / §9 缓存 |
| CORS 报错 | §11 | §5 头部家族 |
| 缓存不更新 | §9 | §5 / §13 CDN |
| 401/403 分不清 | §4 / §14 认证 | §5 |
| 请求体被截断 | §2 报文结构 | §12 压缩分块 |
| 证书错误 | §8 TLS | §13 谁终止 TLS |

每章末尾都有 **排障锚点** 小方框，标注"你会在什么场景下回到这一节"，章节之间靠这些锚点互相勾连。

---

## 1. 一个请求的完整生命周期

把这一章当**全文骨架**。其它所有章节都能挂到这张图上。

```
[1] 域名解析     DNS: example.com → 93.184.216.34
[2] 建立 TCP     SYN / SYN-ACK / ACK（三次握手）
[3] TLS 握手     ClientHello → ServerHello → ... → Finished
[4] 发送请求     GET /api HTTP/1.1\r\nHost: ...\r\n\r\n
[5] 服务器处理   应用读报文 → 业务逻辑 → 构造响应
[6] 返回响应     HTTP/1.1 200 OK\r\nContent-Length: ...\r\n\r\n<body>
[7] 实体传输     chunked 流式 or 一次性 body
[8] 连接去向     keep-alive 复用 or close
```

每一段都对应一类典型故障：

| 阶段 | 典型故障 | 讲透的章节 |
|---|---|---|
| [1] DNS | 解析失败、解析慢、解析到错 IP | §15.1 |
| [2] TCP | `connection refused`、`connection timeout` | §6 / §15.2 |
| [3] TLS | 证书不信任、握手超时、SNI 缺失 | §8 |
| [4] 请求 | Host 错、被代理改写、Content-Length 不一致 | §2 / §13 |
| [5] 服务器处理 | 上游超时、线程池满 → 504/503 | §4 / §15.4 |
| [6] 响应 | 状态码分诊、头部错配 | §4 / §5 |
| [7] 实体 | chunked 被中间层缓冲、压缩双叠 | §12 |
| [8] 连接 | TIME_WAIT 堆积、连接池耗尽 | §6 |

**直觉提示**：HTTP 本身只负责 [4] → [7]。但线上 99% 的"HTTP 问题"其实出在 [1][2][3][8]——连接层和基础设施层。这是为什么"懂 HTTP"在实战里等价于"懂 HTTP 上下这一整条链路"。

> **排障锚点**：任何时候遇到"这锅是谁的"之类的困惑，先回到这张 8 段图，按阶段排除。

---

## 2. 报文结构：你在 Wireshark 里看到的每个字节

### 2.1 报文总览

一个 HTTP/1.1 请求在字节层面长这样：

```
GET /api/users?id=1 HTTP/1.1\r\n        ← 请求行
Host: example.com\r\n                    ← 头部开始
User-Agent: curl/8.4.0\r\n
Accept: */*\r\n
Content-Length: 0\r\n
\r\n                                     ← 空行（必不可少）
<请求体，可有可无>
```

响应几乎对称：

```
HTTP/1.1 200 OK\r\n                      ← 状态行
Content-Type: application/json\r\n
Content-Length: 27\r\n
\r\n
{"id":1,"name":"alice"}\r\n
```

**三个必须刻在脑子里的事实**：

1. **文本协议，以 `\r\n` 分隔行**。少一个 `\r`、少一个 `\n`，整个报文就废了——这是手写 HTTP 最常见的翻车点。
2. **头与体之间的空行是强制的**。服务端用这个空行判断"头结束了，后面是体"。
3. **体的长度需要"明确"**——不是 `Content-Length` 告诉长度，就是 `Transfer-Encoding: chunked` 流式给长度，两者**互斥**。没有长度信息的 HTTP/1.1 响应只能靠 `Connection: close` 来宣告结束（老式做法，现在不应再出现）。

### 2.2 请求行 / 状态行

请求行：`方法 SP 请求目标 SP HTTP 版本`
状态行：`HTTP 版本 SP 状态码 SP 状态短语`

**"请求目标"有四种形式**，平时见最多的是第一种：

| 形式 | 例子 | 场景 |
|---|---|---|
| origin-form | `/api/users?id=1` | 直接对源站 |
| absolute-form | `http://example.com/api` | 发给正向代理时 |
| authority-form | `example.com:443` | `CONNECT` 用 |
| asterisk-form | `*` | `OPTIONS *`，极少见 |

### 2.3 头部的两个硬规则

- **大小写不敏感**（`Content-Type` 和 `content-type` 等价）
- **可以出现多个同名头**（如多个 `Set-Cookie`），行为取决于该头的语义——能合并的用逗号合并，不能合并的只能是重复行

### 2.4 Content-Length vs Transfer-Encoding

这是**最致命的一对头**。

- `Content-Length: 1234` — 告诉对方"体正好 1234 字节"。适合长度已知的场景。
- `Transfer-Encoding: chunked` — 流式传输。体被切成若干块，每块先给长度再给内容，最后用 `0\r\n\r\n` 收尾。适合长度未知（如实时生成的大文件）。

**两者不能共存**。如果报文里同时出现，接收方必须忽略 `Content-Length` 或直接拒绝。真实世界里同时出现往往意味着**中间代理改写错了**——这是 **HTTP 请求走私（request smuggling）** 漏洞的根源。

### 2.5 HTTP/2、/3 的报文怎么看

虽然 HTTP/2 把报文二进制化（分成"帧"），但**逻辑结构没变**：还是请求行/状态行 + 头部 + 体。只是：

- 请求行被拆成伪头：`:method`、`:path`、`:authority`、`:scheme`
- 头部用 HPACK（HTTP/2）或 QPACK（HTTP/3）压缩
- 多个请求/响应可以在同一连接上交错（多路复用，§7 讲）

你在 Chrome Network 里看到的依然是语义化的请求和响应——这是刻意的设计。

> **排障锚点**：
> - 请求体被截断 → 查 Content-Length 是否被代理改写
> - 响应 hang 住 → 查是不是 chunked 但上游没发 `0\r\n\r\n`
> - 奇怪的 400 Bad Request → 九成是头里有非法字符（中文、`\n`、控制符）或 CRLF 注入

---

## 3. 方法 & 幂等性 & 安全性

### 3.1 八个方法及其语义

| 方法 | 语义 | 安全 | 幂等 | 可缓存 |
|---|---|---|---|---|
| GET | 读资源 | ✓ | ✓ | ✓ |
| HEAD | 只要头 | ✓ | ✓ | ✓ |
| OPTIONS | 查能力 | ✓ | ✓ | ✗ |
| POST | 创建/非幂等写 | ✗ | ✗ | 特殊 |
| PUT | 整体替换（覆盖写） | ✗ | ✓ | ✗ |
| PATCH | 局部更新 | ✗ | ✗ | ✗ |
| DELETE | 删资源 | ✗ | ✓ | ✗ |
| CONNECT | 建隧道（HTTPS 代理用） | ✗ | ✗ | ✗ |

**三个概念要分清**：

- **安全**（safe）：**不改服务器状态**。GET/HEAD/OPTIONS 安全——但"安全"只是语义承诺，服务端写个 `GET /delete` 也没人拦你，只是**这违反协议**，所有中间盒（爬虫、预加载、预取）都会假设 GET 没副作用，你会吃亏。
- **幂等**（idempotent）：**同一请求发 N 次，等效于发 1 次的效果**。PUT 幂等（把资源设为某值，设一次和设 N 次最终态一样）；DELETE 幂等（删了就是删了）；POST 不幂等（创建 N 次会有 N 个资源）。
- **可缓存**：GET 默认可缓存；POST 需要显式 `Cache-Control` 才能缓存（极少这么干）。

### 3.2 最常见的语义误解

**误解 1：POST 是"写"、GET 是"读"**

错。正确版本是："POST 代表一个**不幂等**的操作"。RESTful 里常用 POST 创建资源，但 POST 也能用来"查询但参数太长塞不进 URL"——比如 `/search` 接口传复杂的过滤条件。

**误解 2：PUT 就是"更新"**

错。PUT 是**整体替换**。你 `PUT /users/1` 带上 `{name: "alice"}`，如果用户原来还有 `age` 字段，**按语义应该丢弃**（因为你没提交 age）。局部更新应该用 PATCH。真实世界很多后端把 PUT 当 PATCH 用，是妥协，不是规范。

**误解 3：DELETE 删完再删应该报错**

错。DELETE 是幂等的——**删除一个已经不存在的资源应该返回成功（或 404，按习惯）**，而不是 500。否则客户端重试一次就炸了。

### 3.3 幂等性在重试里的真实代价

假设你是一个网关，下游 502 了，你要不要自动重试？

- GET / HEAD / PUT / DELETE / OPTIONS：**可以重试**（幂等）
- POST：**不要自动重试**（可能重复创建订单）
- PATCH：**看场景**（`PATCH add $10 to balance` 不幂等；`PATCH set status=done` 幂等）

真实事故模板：网关对所有 5xx 无脑重试，POST 创建订单的请求下游先写成功再超时，网关重试 → 同一个用户同一秒创建了 3 个订单。**这类事故的根因永远是"网关不区分方法"**。

解决方案：
- 客户端生成 `Idempotency-Key`，服务端去重
- 网关只重试幂等方法
- 业务层幂等兜底（不要依赖协议保证）

> **排障锚点**：
> - 看到"重复订单/重复扣款" → 九成是 POST 被重试了，去查网关/SDK 的重试策略
> - 预加载把某资源触发了副作用 → GET 里不该有副作用，这是 URL 设计问题

---

## 4. 状态码：不是背码，是分诊

状态码分五类，**每类表达的不是"结果"，而是"接下来该往哪查"**。

### 4.1 五大家族

| 家族 | 含义 | 排障起点 |
|---|---|---|
| 1xx | 信息（协议级，很少见到） | 一般不需要管 |
| 2xx | 成功 | 没问题 |
| 3xx | 重定向 | 客户端跟随 or 缓存标记 |
| 4xx | **客户端错**（请求有问题） | 查请求本身 |
| 5xx | **服务端错**（请求没问题，处理挂了） | 查服务端 or 中间链路 |

**一个强记忆**：**4xx 是"你的锅"，5xx 是"我的锅"**。但中间夹着一个 **499**（见下），这是 nginx 独创的"客户端断了连接"码，归属比较暧昧。

### 4.2 3xx 里容易混的四个

| 码 | 方法是否保留 | 语义 |
|---|---|---|
| 301 Moved Permanently | 历史上可能被改写成 GET | **永久**重定向，浏览器/爬虫会记 |
| 302 Found | 历史上可能被改写成 GET | 临时重定向 |
| 307 Temporary Redirect | **保留原方法、原体** | 临时 |
| 308 Permanent Redirect | **保留原方法、原体** | 永久 |

**"历史上可能被改写成 GET"是个大坑**。POST 一个表单到 `/login`，服务端返回 301 跳到 `/home`——老浏览器会把 POST 改成 GET。**所以 API 接口重定向一律用 307/308，不要 301/302**。

### 4.3 4xx 的分诊表

| 码 | 含义 | 先查 |
|---|---|---|
| 400 Bad Request | 报文格式/参数有错 | JSON 解析？必填字段？头部非法字符？ |
| 401 Unauthorized | **没认证 / 凭证过期** | Authorization 头？token 是否过期？ |
| 403 Forbidden | **认证了但无权限** | 认证通过但策略拦了 |
| 404 Not Found | 资源不存在 | URL 拼错？路由没注册？ |
| 405 Method Not Allowed | 路由存在但方法错 | URL 对，方法错 |
| 408 Request Timeout | 客户端发得太慢 | 极少见，通常是网关吃的 |
| 409 Conflict | 状态冲突（如乐观锁失败） | 业务层并发 |
| 410 Gone | 永久删除（比 404 更明确） | |
| 413 Payload Too Large | 体太大 | nginx `client_max_body_size` |
| 414 URI Too Long | URL 太长 | GET 改 POST |
| 415 Unsupported Media Type | Content-Type 服务端不认 | 常见 `application/json` vs `text/plain` |
| 422 Unprocessable Entity | 格式对但业务校验不过 | 校验层 |
| 429 Too Many Requests | 限流 | 看 `Retry-After` 头 |
| 499（nginx）| 客户端提前断开 | 不是真的客户端错，是 nginx 记的账 |

**401 vs 403 的精确区分**：

- 401 = "我不知道你是谁" → 客户端应该**提供凭证或重新登录**
- 403 = "我知道你是谁，但你不配" → 客户端**不该重试**，除非身份变了

很多后端分不清，全返 403，前端就没法判断"要不要跳登录页"。

### 4.4 5xx 的分诊表

| 码 | 含义 | 先查 |
|---|---|---|
| 500 Internal Server Error | 兜底，没分类的错 | 看服务端日志/栈 |
| 501 Not Implemented | 方法/能力没实现 | 少见 |
| 502 Bad Gateway | **网关收到了一个坏响应** | 上游挂了？上游返回了非法报文？ |
| 503 Service Unavailable | **服务主动说我不行** | 限流、熔断、过载、维护 |
| 504 Gateway Timeout | **网关等上游等超时了** | 上游慢了，不一定挂 |

**502 vs 503 vs 504 的关键区分**：

- 502 = 上游**返回了东西，但不是合法 HTTP**（或者连接被重置）
- 503 = **服务自己喊的**："别来，我忙"
- 504 = 上游**没返回**，等到网关超时

**"谁超时了 504"是面试和排障常见问题**：

```
Client ─────────► nginx ─────────► upstream(app)
         [A]               [B]
```

- 如果 [B] 超过了 nginx 的 `proxy_read_timeout`，nginx 对 client 返回 504
- 如果 [A] 超过了 client 的请求超时，client 那边报 timeout（这不是 504，是客户端异常）

所以看到 504 别只骂 nginx——实际是**上游没在 nginx 等的时间内返回完整响应**，nginx 只是替上游挨骂。

> **排障锚点**：
> - 看到 401 → 去 §14 查认证
> - 看到 502/503/504 → 去 §13 查代理链路 + §6 查连接池 + §15 查慢请求分段
> - 看到 429 → 去查 `Retry-After` 并实现退避

---

## 5. 头部家族：按用途分六组

别按字母记，按**用途分组**：

### 5.1 内容协商（Content Negotiation）

客户端说"我想要什么"，服务端回"我给的是什么"。

| 客户端发 | 服务端回 | 管什么 |
|---|---|---|
| `Accept: application/json` | `Content-Type: application/json` | 媒体类型 |
| `Accept-Encoding: gzip, br` | `Content-Encoding: br` | 压缩 |
| `Accept-Language: zh-CN,en` | `Content-Language: zh-CN` | 语言 |
| `Accept-Charset`（弃用） | `Content-Type; charset=utf-8` | 字符集 |

**`Content-Type` 必须精确**。前端 `Accept: application/json` 但后端返 `Content-Type: text/html` 的 JSON——fetch 可能照样 parse，但 Chrome 会按 HTML 渲染，导致"本地 curl 能看到数据，浏览器空白"的诡异现象。

### 5.2 缓存

| 头 | 方向 | 作用 |
|---|---|---|
| `Cache-Control` | 双向 | 缓存策略主控 |
| `Expires` | 响应 | 老的过期时间（被 Cache-Control 取代） |
| `ETag` | 响应 | 资源指纹 |
| `Last-Modified` | 响应 | 资源最后修改时间 |
| `If-None-Match` | 请求 | 带上 ETag 问"还是这个吗" |
| `If-Modified-Since` | 请求 | 带上时间问"还是这个吗" |
| `Vary` | 响应 | "缓存区分 key" |

详细展开见 §9。

### 5.3 认证

| 头 | 方向 | 作用 |
|---|---|---|
| `Authorization: Bearer xxx` | 请求 | 带凭证 |
| `WWW-Authenticate: Bearer realm=...` | 401 响应 | 告诉客户端该怎么认证 |
| `Proxy-Authorization` | 请求 | 给代理的凭证 |
| `Proxy-Authenticate` | 407 响应 | 代理要求认证 |

详细展开见 §14。

### 5.4 连接控制

| 头 | 作用 |
|---|---|
| `Connection: keep-alive / close / upgrade` | 复用/关闭/升级连接 |
| `Keep-Alive: timeout=5, max=1000` | 保持时长 |
| `Upgrade: websocket / h2c` | 协议升级 |
| `Host` | 目标主机（HTTP/1.1 必填） |

详细展开见 §6。

### 5.5 代理链路

这一组在任何经过代理/CDN 的请求上都会被**中间节点加/改**，排障必看。

| 头 | 作用 |
|---|---|
| `Host` | 客户端原始目标主机 |
| `X-Forwarded-For` | 客户端真实 IP 链 |
| `X-Forwarded-Proto` | 原始协议（http/https） |
| `X-Forwarded-Host` | 原始 Host |
| `X-Real-IP` | nginx 常用，客户端 IP |
| `Forwarded`（RFC 7239） | 标准版的 X-Forwarded-*（用得少） |
| `Via` | 经过的代理链 |

**`X-Forwarded-For` 是攻击面**。任何人都能伪造这个头，所以**只能信任"从你自己的边缘代理加进来的那一段"**——通常是 XFF 列表的最右一项（离你最近的代理填的）。配置错了就能被伪造 IP 绕过限流。

### 5.6 安全

| 头 | 作用 |
|---|---|
| `Strict-Transport-Security` (HSTS) | 强制浏览器用 HTTPS |
| `Content-Security-Policy` (CSP) | 限制脚本来源 |
| `X-Content-Type-Options: nosniff` | 禁止 MIME sniff |
| `X-Frame-Options: DENY` | 防 clickjacking |
| `Referrer-Policy` | 控制 Referer 泄漏 |
| `Permissions-Policy` | 控制浏览器特性 |

这些和业务逻辑无关，但线上都应该有。

### 5.7 `Vary` 是个大地雷

`Vary: Accept-Encoding, Accept-Language` 告诉缓存："同一个 URL 的不同 Accept-Encoding/Accept-Language 值要分开缓存"。

问题是：

- 忘记写 `Vary` → 压缩和非压缩混在一起 → 不支持 gzip 的客户端拿到 gzip 内容乱码
- 写得太宽（`Vary: User-Agent`）→ 每个 UA 一份缓存 → CDN 命中率归零

`Vary` 是 §9 的重要伏笔。

> **排障锚点**：
> - "本地能跑线上挂" → 查 `Host` 头在 CDN/nginx 被改过没
> - 用户 IP 显示不对 → 查 XFF 的信任链
> - 某些浏览器下内容错了 → 查 `Vary`

---

## 6. 连接管理：keep-alive / 连接池 / TIME_WAIT

**这一章是"服务慢" / "连接打爆"类事故的根据地**。

### 6.1 从短连接到长连接的演进

- **HTTP/0.9、1.0 默认**：一个请求一个 TCP 连接，用完就断。建一次 TCP 要三次握手（至少 1 个 RTT），TLS 再加 1–2 RTT。高频请求下，连接建立的开销比业务处理还大。
- **HTTP/1.1 默认 keep-alive**：一个 TCP 连接跑完请求 1 后，不断开，接着跑请求 2、3、……直到超时或被主动关闭。
- **HTTP/2 多路复用**：一个连接上**并发**多个请求（不是串行）。
- **HTTP/3（QUIC）**：连接变成逻辑概念，底层是 UDP，能跨网络切换（Wi-Fi → 4G 不断流）。

### 6.2 keep-alive 的三个参数

- **`Connection: keep-alive / close`**：客户端/服务端的意愿
- **`Keep-Alive: timeout=N, max=M`**：空闲多久关、最多跑多少请求
- **服务端的实际超时**：nginx `keepalive_timeout`、Node.js `server.keepAliveTimeout`、Go `http.Server.IdleTimeout`——**这个才是真生效的**

**一个经典坑**：客户端连接池的 idle timeout 设得比服务端大。服务端已经关了连接，客户端拿这个连接发请求，**被 RST**，报 `connection reset`。常见于 Go 客户端连 nginx：Go 的 `IdleConnTimeout` 默认 90s，nginx 默认 75s，调过来就行。

### 6.3 连接池：每个 HTTP 客户端都在做的事

不管你用什么语言，HTTP 客户端内部都有一个连接池（或者叫 `Transport`、`HttpClient`、`Session`）。**最关键的两个参数**：

| 概念 | Go `http.Transport` | Java `HttpClient` | Python `requests.Session` |
|---|---|---|---|
| 总池大小 | `MaxIdleConns` | `maxConnections` | 底层 `HTTPAdapter(pool_maxsize=...)` |
| 每 host 池大小 | `MaxIdleConnsPerHost` / `MaxConnsPerHost` | 同 | 同 `pool_maxsize` |
| 空闲超时 | `IdleConnTimeout` | `PoolingHttpClientConnectionManager` | — |

**典型事故**：Go 默认 `MaxIdleConnsPerHost = 2`。服务每秒打 1000 个请求到下游，连接池只有 2 个空闲复用位，剩下 998 次全是新建连接 + 建完随即关闭 → TIME_WAIT 堆满。

解决：把 `MaxIdleConnsPerHost` 调到 100–1000，匹配实际并发。

### 6.4 TIME_WAIT：为什么它总是堆积

TCP 连接关闭的四次挥手里，**主动关闭的一方**会进入 TIME_WAIT，停留 **2MSL**（Linux 上通常是 60s）。TIME_WAIT 占用一个 `<本地IP, 本地端口, 对端IP, 对端端口>` 四元组。

本地端口范围只有约 28000 个（`/proc/sys/net/ipv4/ip_local_port_range`）。如果你每秒主动关闭 500 个连接，60 秒后堆积 30000 个 TIME_WAIT——**本地端口用光**，新连接报 `EADDRNOTAVAIL`。

**三种解决思路**：

1. **减少连接建立频率**（根因）：用连接池、用 HTTP/2 多路复用
2. **让服务端主动关**：客户端大量短连接打服务端，让服务端承担 TIME_WAIT（服务端单机资源多、可复用四元组）
3. **内核参数**：`net.ipv4.tcp_tw_reuse=1`（客户端场景可开），`tcp_tw_recycle`（已废弃，不要开，会在 NAT 后炸）

### 6.5 HTTP/2 的连接模型不一样

HTTP/2 下，**一个 TCP 连接可以同时跑多个请求**（通过"流"的概念，每个流是独立的双向字节流）。所以：

- 连接池几乎不需要（一条连接就够了）
- TIME_WAIT 问题基本消失
- 但是：**同连接上的请求共享底层 TCP**，一个丢包拖累所有流（HOL 阻塞，§7 讲）

### 6.6 Connection: close 什么时候该用

- 你明确知道这是**一次性请求**（批处理脚本、探活）
- 服务端已经关了（你返回 close 告诉客户端别复用）
- 负载均衡做优雅重启时（告诉客户端"别再用这条连接了，下次去别处"）

平时业务调用**永远不要手动加 `Connection: close`**，会毁掉连接池。

> **排障锚点**：
> - `connection reset by peer` 偶发 → 查客户端 idle timeout > 服务端 idle timeout
> - `EADDRNOTAVAIL` → 查连接池大小和 TIME_WAIT
> - 下游 QPS 一高就超时 → 查连接池耗尽
> - HTTPS 建连巨慢 → 查是不是没有连接复用，每次都在重跑 TLS 握手（§8）

---

## 7. HTTP/1.1 vs 2 vs 3：演进的动机

**不要把这三版本当独立协议记。它们是同一个协议对"TCP/IP 的瓶颈"的三次工程回应**。

### 7.1 HTTP/1.1 的瓶颈

- **请求串行**：一条连接上请求 2 必须等请求 1 的响应完整到达才能发
- **头部冗余**：每个请求都带完整 Cookie、UA、Accept、Authorization……一个请求头可能 1–2 KB，100 个请求就 100–200 KB 的纯头重复
- **服务端无法主动推**：只能客户端问一句答一句

历史上的缓解方案：
- **管道化（pipelining）**：同一连接上连续发多个请求，不等响应——但响应必须按请求顺序返回，如果请求 1 的响应慢，后面全卡（**队头阻塞 HOL**）。所以几乎没被真正部署。
- **多连接**：浏览器对同一域名开 6 条连接。但仍是串行 × 6。
- **域名分片（domain sharding）**：把静态资源分到 `static1.foo.com`、`static2.foo.com`，绕过每域名 6 条限制。CDN 时代这么做过，HTTP/2 后反而成反模式。

### 7.2 HTTP/2 的四板斧

| 能力 | 解决的 1.1 问题 |
|---|---|
| **二进制分帧** | 文本解析开销、歧义性 |
| **多路复用** | 请求串行 |
| **头部压缩（HPACK）** | 头部冗余 |
| **服务端推送（已废弃）** | 客户端被动 |

**多路复用的直觉**：一条 TCP 上跑多个独立的"流"。每个流是双向字节流，互不阻塞。帧层标记每个帧属于哪个流，接收端按流重组。

```
Stream 1: [H] [D] [D]       ← 请求 A
Stream 3:     [H] [D]       ← 请求 B
Stream 5:       [H] [D] [D] ← 请求 C
TCP:      [1][3][1][5][1][3][5][5]  ← 帧交错发
```

**头部压缩 HPACK**：客户端和服务端各维护一张"索引表"，重复出现的头（如 `Cookie`、`User-Agent`）只发索引号，不发全文。第一次 1 KB，第二次可能只要 1 字节。

**服务端推送已被废弃**（Chrome 106 起）。原因：预测不准，推错的资源占用带宽反而更慢。**面试如果被问"HTTP/2 特性"，推送可以提但要说"已废弃"**。

### 7.3 HTTP/2 的新瓶颈：TCP 层的 HOL

多路复用解决了**HTTP 层**的队头阻塞，但**TCP 层的队头阻塞依然存在**：

```
TCP 视角：[1][3][1][5][1][3][5][5]
                 ↑ 这一个包丢了
→ 后面所有包（包括属于其它流的）都得等重传
```

一条连接上所有流共享一条 TCP 管道，**一个 IP 包丢，所有流都卡**。在丢包率高的网络（移动网络、弱 Wi-Fi）上，HTTP/2 可能比 HTTP/1.1 多连接还慢。

### 7.4 HTTP/3：把传输层换成 QUIC

HTTP/3 做了一件激进的事：**不在 TCP 上跑了，改跑 UDP 之上的 QUIC**。

QUIC 在 UDP 上重新实现了：连接、可靠传输、拥塞控制、加密。**关键点**：**流是 QUIC 协议原生概念**，一个流丢包不影响其它流——彻底解决 HOL。

额外好处：

- **0-RTT 建连**：二次连接可以在第一个数据包就带上应用数据
- **连接迁移**：Wi-Fi 切 4G，连接 ID 不变，TCP 四元组换了也能续传
- **TLS 1.3 内置**：握手和 QUIC 握手合并

代价：

- **中间盒不认识 UDP 上跑 QUIC**，部分企业防火墙直接丢 UDP 443 → 回退 HTTP/2
- 运维工具链不成熟（抓包工具对 QUIC 支持晚于 TCP）

### 7.5 "我该不该升 HTTP/2/3"

**用 HTTP/2**：几乎无脑开。CDN、nginx、反代都支持。唯一要注意：**别再做域名分片**（反模式，会打碎 HTTP/2 连接的优势）。

**用 HTTP/3**：

- 浏览器访问：有 CDN 就开，浏览器自动协商
- 服务端之间 RPC：目前 HTTP/2 + gRPC 更稳，HTTP/3 收益有限
- 移动网络场景（App 直连 API）：HTTP/3 收益明显（连接迁移 + 抗弱网）

### 7.6 ALPN：版本怎么协商的

TLS 握手时，客户端在 `ClientHello` 里的 ALPN 扩展列出支持的协议（`h2`, `http/1.1`），服务端选一个回来。**所以版本协商发生在 TLS 层，还没进入 HTTP**。

> **排障锚点**：
> - HTTP/2 下某些请求偶发慢 → 怀疑 TCP 丢包触发 HOL，试试开 HTTP/3
> - 移动端连不上 HTTP/3 → 可能 UDP 443 被运营商/防火墙丢，回退 HTTP/2
> - HTTP/2 比 HTTP/1.1 慢 → 查是不是做了域名分片（反模式）

---

## 8. HTTPS / TLS 握手（从 HTTP 视角）

这一章**只讲对排障有用的部分**：握手时序、SNI、证书链、ALPN、0-RTT、会话复用。密码学数学（ECDHE 怎么算、AES 模式）不展开——不影响排障。

### 8.1 TLS 1.2 握手时序

```
Client                                     Server
  │── ClientHello ─────────────────────────►│   [1]
  │  (支持的密码套件、SNI、ALPN、随机数)         │
  │                                         │
  │◄─ ServerHello ──────────────────────────│   [2]
  │   Certificate                          │   (证书链)
  │   ServerKeyExchange                    │   (ECDHE 参数)
  │   ServerHelloDone                      │
  │                                         │
  │── ClientKeyExchange ────────────────────►│   [3]
  │   ChangeCipherSpec                     │
  │   Finished (加密)                       │
  │                                         │
  │◄─ ChangeCipherSpec ─────────────────────│   [4]
  │   Finished (加密)                       │
  │                                         │
  │━━ 应用数据（双方已有对称密钥）━━━━━━━━━━━━━━━│
```

**总共 2 个 RTT**才能发出第一个 HTTP 请求。

### 8.2 TLS 1.3 把它压到 1 RTT

```
Client                                     Server
  │── ClientHello ─────────────────────────►│
  │   (直接带上密钥交换材料)                   │
  │                                         │
  │◄─ ServerHello, Certificate,            │
  │   Finished (加密)                       │
  │                                         │
  │── Finished (加密) ──────────────────────►│
  │━━ 应用数据 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
```

再加上 0-RTT（会话复用时），**第二次连接的第一个包就可以带 HTTP 请求**。代价：0-RTT 数据不防重放，GET 安全，POST 谨慎。

### 8.3 SNI：一个 IP 多个证书

早期 HTTPS 一个 IP 只能服务一个证书——因为客户端要看证书才知道在和谁说话，而这时候 `Host` 头还没发。SNI（Server Name Indication）是**`ClientHello` 里带上我要访问的域名**，让服务端能根据这个挑对应的证书。

现实：**所有现代客户端都支持 SNI**。但有些老代理、老库可能不发 SNI → 服务端挑了默认证书 → 域名不匹配 → 握手失败。

### 8.4 证书链

```
叶子证书（你的域名）
   └─ 中间 CA 证书
         └─ 根 CA 证书（浏览器/操作系统内置信任）
```

服务端返回的**必须是完整的叶子 + 中间**。根 CA 客户端自己有。**常见事故：证书部署时只配了叶子，没配中间 CA** → 客户端信任链断了 → `unable to verify the first certificate`。

工具：
```
openssl s_client -connect example.com:443 -servername example.com -showcerts
```
看返回了几张证书。

### 8.5 ALPN 和 HTTP 版本选择

见 §7.6。ALPN 是 `ClientHello` 的扩展，列出 `h2`、`http/1.1`、`h3`。服务端挑一个。

### 8.6 会话复用

完整握手开销大，TLS 提供两种复用：

- **Session ID**（1.2）：服务端记一张表
- **Session Ticket**（1.2）：服务端发给客户端一个加密票据，自己不记
- **PSK**（1.3）：合并了上面两者

**复用后握手退化到 1 RTT（或 0-RTT）**。对延迟敏感的业务，会话复用 = 性能。

### 8.7 "谁终止 TLS"——排障第一问

```
Client ──HTTPS──► CDN ──HTTPS──► LB ──HTTP──► App
                  ↑                    ↑
               谁在这里解密        谁在这里再加密（或不加密）
```

排障先问：**链路上每个节点，TLS 终止在哪**。

- 证书错 → 找终止那一层
- 慢 → 找每段重新握手的层
- 日志里看不到客户端 IP → TLS 被 CDN 终止后，客户端 IP 要靠 `X-Forwarded-For` 转（§5.5、§13）

### 8.8 常见抓包现象

| 现象 | 解读 |
|---|---|
| `bad_certificate` / `certificate_unknown` | 证书链不完整、或根 CA 不信任 |
| `handshake_failure` | 密码套件协商不上（老客户端 + 新服务端或相反） |
| `unrecognized_name` | SNI 不匹配服务端证书 |
| `certificate_expired` | 证书过期（注意客户端时钟） |
| 握手卡在 ServerHello | 服务端证书太大（带了太多中间 CA） |

> **排障锚点**：
> - `unable to verify the first certificate` → 服务端没配中间 CA
> - 老客户端（Android < 7）连不上 → 证书链包含已退役的 CA，或密码套件不兼容
> - HTTPS 延迟高 → 没复用会话，每次都完整握手（§6.3 连接池）

---

## 9. 缓存：强缓存 / 协商缓存 / CDN

缓存是**用空间换时间**，也是**排障最容易中枪的领域**——你以为请求到了服务器，实际上 CDN 返了一个三天前的副本。

### 9.1 两种缓存模型

- **强缓存**：客户端看自己的存货，**不发请求**。表现为浏览器 Network 里的 `(memory cache)` / `(disk cache)` / 200。
- **协商缓存**：客户端**发请求**，但带上"我有这个版本"；服务端说"还是这个"就回 304（不带体），"变了"就回 200（带新体）。

### 9.2 强缓存头：Cache-Control

`Cache-Control` 是**主控**，`Expires`（HTTP/1.0）已被淘汰但仍然常见。

| 指令 | 方向 | 作用 |
|---|---|---|
| `max-age=N` | 响应 | N 秒内强缓存 |
| `s-maxage=N` | 响应 | 共享缓存（CDN）用，覆盖 max-age |
| `no-cache` | 响应 | **每次都走协商缓存**（不是"不缓存"） |
| `no-store` | 响应 | **真的不要存**（敏感数据） |
| `private` | 响应 | 只能浏览器缓存，CDN 不许缓 |
| `public` | 响应 | 都可以缓 |
| `must-revalidate` | 响应 | 过期后必须重新校验 |
| `immutable` | 响应 | 过期前绝不重新校验（指纹化文件） |
| `max-age=0` | 请求 | 客户端要求不用强缓存 |

**最容易混的一组：`no-cache` 不是"不缓存"，是"缓存但每次都问一下"；`no-store` 才是真的不存**。

### 9.3 协商缓存头：ETag / Last-Modified

客户端第一次请求得到响应：

```
HTTP/1.1 200 OK
ETag: "abc123"
Last-Modified: Wed, 15 Apr 2026 08:00:00 GMT
Cache-Control: no-cache
<body>
```

第二次请求：

```
GET /file HTTP/1.1
If-None-Match: "abc123"
If-Modified-Since: Wed, 15 Apr 2026 08:00:00 GMT
```

服务端两种回复：

- 资源没变 → `304 Not Modified`（**无响应体**，客户端复用自己的副本）
- 资源变了 → `200 OK` + 新体 + 新 ETag

**ETag vs Last-Modified 的关系**：ETag 更精确（指纹），Last-Modified 精度只到秒（一秒内多次修改检测不到）。两者都带时客户端/服务端一般优先 ETag。

### 9.4 指纹化：最实用的缓存策略

静态资源打包时给文件加哈希：`app.a3f4c2.js`。

```
Cache-Control: public, max-age=31536000, immutable
```

设一年强缓存 + immutable。更新时文件名变了（哈希变），HTML 引用的 URL 也变了，浏览器自然重新下载。**这是前端构建工具默认的方案**。

相比之下 `index.html` 本身永远设 `no-cache`——每次都校验最新的文件列表。

### 9.5 Vary：缓存的分桶 key

缓存 key 默认是 URL。但如果你对同一个 URL 的响应会因请求头不同而不同（比如 gzip vs 不 gzip），必须用 `Vary` 告诉缓存："把这些头也纳入 key"。

```
Vary: Accept-Encoding
```

**忘写 `Vary: Accept-Encoding` 的经典事故**：
- 客户端 A 发 `Accept-Encoding: gzip` → CDN 缓存了 gzip 响应
- 客户端 B 发 `Accept-Encoding:`（不支持） → CDN 返回了 gzip 响应 → B 收到乱码

**写得太宽的经典事故**：
- `Vary: User-Agent` → 每个 UA 一份缓存 → 命中率接近 0

### 9.6 CDN 的分层缓存

```
浏览器 → CDN 边缘节点 → CDN 中心节点 → 源站
```

每一层都有缓存，每一层都可能因 `Cache-Control` / `Vary` / 查询串的处理不同而给出不同结果。

**常见排障**：

1. **用户看到老版本**：清 CDN，别清自己的浏览器缓存
2. **某些用户看到老版本，某些不**：查 CDN 节点分布和 TTL 梯度
3. **发了新版本但流量没切**：CDN 还在老文件的 TTL 窗口内，需要主动 purge

### 9.7 HTTP 方法和缓存

- **GET/HEAD**：默认可缓存
- **POST**：按规范**可以**缓存（但需要显式 Cache-Control），实际几乎没人这么做
- **PUT/DELETE/PATCH**：不缓存

### 9.8 一次完整的缓存决策流

```
请求到来
  │
  ├── 强缓存在有效期内？
  │     ├── 是 → 直接用本地副本（200 from cache）
  │     └── 否 ↓
  │
  ├── 有 ETag/Last-Modified？
  │     ├── 是 → 带上 If-None-Match 发请求
  │     │       └── 304 → 复用本地体 + 刷新过期时间
  │     │       └── 200 → 用新内容 + 新头
  │     └── 否 → 直接发完整请求
```

> **排障锚点**：
> - 用户说"发新版了但看到旧的" → 按"浏览器 → CDN → 源"逐层 purge，看 `Cache-Control` 和 `Age` 响应头
> - 某个浏览器正确某个错 → 查 `Vary`
> - 304 响应体为空但客户端还是重新下载 → 客户端没保留本地副本（常见于 fetch/axios 默认不缓存响应体）

---

## 10. Cookie / Session / SameSite

### 10.1 Cookie 是什么，不是什么

Cookie 是服务端用 `Set-Cookie` 头下发的小片键值对，浏览器存起来，**之后对匹配的域发请求自动带上**。它**只是一个"请求自动带状态"的机制**，Session 是在其上建立的一层逻辑。

### 10.2 Set-Cookie 的属性矩阵

```
Set-Cookie: sid=abc123; Domain=example.com; Path=/; Max-Age=3600;
            Secure; HttpOnly; SameSite=Lax
```

| 属性 | 作用 | 不写的后果 |
|---|---|---|
| `Domain` | 匹配哪些域 | 默认只给当前域（不含子域） |
| `Path` | 匹配哪些路径 | 默认 `/`，全路径 |
| `Max-Age` / `Expires` | 过期 | 不写 = Session Cookie（关浏览器就没） |
| `Secure` | 只 HTTPS 带 | HTTP 也带 → 易泄漏 |
| `HttpOnly` | JS 读不到 | JS 能读 → XSS 可盗 |
| `SameSite` | 跨站策略 | 见下 |
| `Partitioned`（新） | 分区存储 | 新隐私模型用 |

**默认值**：`Domain` = 当前域（不含子域）、`Path=/`、无 `Expires`（Session）、无 `Secure`、无 `HttpOnly`、`SameSite=Lax`（Chrome 默认）。

### 10.3 SameSite 的三种值

| 值 | 跨站请求会带 Cookie 吗 |
|---|---|
| `Strict` | 永远不带 |
| `Lax`（默认） | **顶层导航的 GET 会带**，其余不带 |
| `None` | 都带，但**必须 `Secure`** |

**"跨站"定义**：eTLD+1 不同就是跨站。`a.example.com` 和 `b.example.com` 不跨站；`example.com` 和 `other.com` 跨站。

**Lax 的具体边界**：你从 `a.com` 点链接跳到 `b.com`（顶层导航 GET）→ 带。你在 `a.com` 页面上 fetch `b.com/api` → 不带。你提交表单（POST）到 `b.com` → 不带。

**第三方 Cookie 的消亡**：跨站 iframe、跨站图片跟踪像素都不能带 Cookie（除非 SameSite=None; Secure + 用户允许第三方 Cookie）。Chrome 本来要在 2024 杀掉第三方 Cookie，后来推迟；Partitioned Cookie（CHIPS）是新的妥协方案。

### 10.4 Session 是什么

**Session** = 服务端用一张表（或 Redis）记录"这个 Cookie ID 对应哪个用户"。Cookie 里存 Session ID，服务端拿 ID 查表。

相比之下 **JWT/Token 方案** 把用户信息直接签在 token 里，服务端无状态——但代价是**无法主动失效某个 token**（要搞黑名单）。

### 10.5 常见排障场景

**场景 1：用户登录后跨域请求丢 Cookie**

前端 `api.b.com`，页面 `www.a.com`。SameSite=Lax → 跨站 fetch 不带 Cookie。

解决：
- `Set-Cookie: sid=...; SameSite=None; Secure`
- 前端 `fetch(url, { credentials: 'include' })`
- 后端 `Access-Control-Allow-Credentials: true` + `Access-Control-Allow-Origin: https://www.a.com`（不能是 `*`）

**场景 2：子域共享 Cookie**

想让 `a.example.com` 和 `b.example.com` 共享：

```
Set-Cookie: sid=...; Domain=example.com
```

注意 `Domain=example.com` 会让 `example.com` **和所有子域**都能读到。

**场景 3：登出后 Cookie 还在**

清理不彻底。正确做法：`Set-Cookie: sid=; Max-Age=0; Path=/; Domain=...`——**属性要和下发时一致**，否则清不到。

> **排障锚点**：
> - "跨域丢 Cookie" → 先查 SameSite，再查 CORS 的 credentials 链（§11）
> - "清不掉的 Cookie" → 属性不匹配

---

## 11. CORS：预检 / 凭证 / 通配

### 11.1 从同源策略说起

浏览器的**同源策略**：一个源（协议 + 域名 + 端口）的脚本不能读另一个源的响应——防的是"恶意页面偷你银行的数据"。

"读不到"但不"发不了"——请求其实**发出去了**，只是 JS 拿不到响应。这是和后端"拒绝请求"完全不同的模型。

### 11.2 CORS 是给浏览器的例外许可

CORS（跨源资源共享）让服务端用响应头**主动允许某些跨源请求**。核心头：

```
Access-Control-Allow-Origin: https://a.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 86400
Access-Control-Expose-Headers: X-Custom-Id
```

### 11.3 简单请求 vs 预检请求

**简单请求**（不触发预检）必须满足：

- 方法是 GET / POST / HEAD
- 只有这些头：`Accept`、`Accept-Language`、`Content-Language`、`Content-Type`（限 `application/x-www-form-urlencoded`、`multipart/form-data`、`text/plain`）、`Range`
- 不能自定义头

**只要违反任何一条，触发预检**：浏览器先发一个 `OPTIONS` 请求问"我能不能……"，服务端回允许的策略，浏览器再发真请求。

```
OPTIONS /api/update HTTP/1.1
Origin: https://a.com
Access-Control-Request-Method: PUT
Access-Control-Request-Headers: Content-Type, Authorization

──────

HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://a.com
Access-Control-Allow-Methods: PUT
Access-Control-Allow-Headers: Content-Type, Authorization
Access-Control-Max-Age: 86400
```

**预检结果可以缓存**：`Access-Control-Max-Age: 86400` 说 24 小时不用再预检。没写或写 0 → **每次请求前都预检**，性能灾难。

### 11.4 凭证（credentials）与通配的互斥

**带凭证（Cookie、Authorization）的跨源请求**：

- 前端必须 `fetch(url, { credentials: 'include' })`
- 服务端必须 `Access-Control-Allow-Credentials: true`
- `Access-Control-Allow-Origin` **不能是 `*`**，必须是具体 origin
- `Access-Control-Allow-Headers` / `Access-Control-Allow-Methods` **不能是 `*`**，必须具体列

**这条规则是 CORS 最折磨人的地方**。想支持多 origin？服务端根据请求的 `Origin` 头动态回写 `Access-Control-Allow-Origin`（并记得加 `Vary: Origin` 防止缓存污染）。

### 11.5 典型排障

**症状 1：预检过了但真请求还被 CORS 拦**

预检的 `Allow-Methods / Allow-Headers` 和真请求不匹配。比如预检允许 `PUT`，但真请求是 `PATCH`。

**症状 2：CORS 在本地没事、上线就挂**

本地 `localhost:3000` 直连后端，没跨源。上线走了 CDN/域名变了，跨源了。

**症状 3：登录态丢失**

没带 credentials，或 Allow-Origin 是 `*`，或没设 Allow-Credentials。

**症状 4：OPTIONS 反复打爆后端**

没设 `Access-Control-Max-Age`。

**症状 5："No 'Access-Control-Allow-Origin' header"**

CORS 错误**浏览器报给 JS**，但请求实际发到了服务端。去服务端看日志，可能请求其实成功了——只是浏览器不让 JS 读响应。

### 11.6 CORS 不是安全机制（对服务端而言）

**关键认知**：CORS 保护的是**浏览器用户**，不是你的 API。不走浏览器的客户端（curl、爬虫、任何后端服务）完全不受 CORS 约束——它只是"对浏览器说我允许谁读我"。

**你的 API 的真正鉴权永远在服务端**（token、Cookie、IP 白名单）。CORS 只是浏览器多加了一道闸。

> **排障锚点**：
> - Chrome 控制台红字 CORS → F12 Network 看是哪个请求、是预检还是真请求
> - "明明配了 CORS 还是挂" → `Allow-Origin` 是不是 `*` 但带了 credentials
> - 预检反复 → `Max-Age`

---

## 12. 压缩与分块传输

### 12.1 Content-Encoding vs Transfer-Encoding

两个名字像，含义完全不同。

- **`Content-Encoding`**：**体自身**的编码（gzip/br/zstd）。端到端语义，代理不能擅自解压再压。
- **`Transfer-Encoding`**：**传输层**的编码（主要是 chunked）。逐跳语义，每个代理都可以重编码。

### 12.2 压缩

```
Content-Encoding: gzip
Content-Encoding: br
Content-Encoding: zstd  (新兴，Chrome 123+)
```

哪个好？

- **gzip**：最古老，兼容性最好。压缩率一般。
- **brotli (br)**：Google 2015 推，专为 Web 设计，比 gzip 压 15-25%。现代浏览器都支持。
- **zstd**：Facebook 推的，压缩速度 + 比更好。普及中。

**服务端实践**：一般 nginx / Caddy / CDN 会根据 `Accept-Encoding` 自动选。**静态资源预压缩**（启动时压好 `.br` / `.gz` 文件）比运行时压省 CPU。

### 12.3 压缩和缓存的交互

一定要 `Vary: Accept-Encoding`（见 §9.5 地雷）。

### 12.4 chunked 分块传输

长度未知时用：

```
HTTP/1.1 200 OK
Transfer-Encoding: chunked

7\r\n
Mozilla\r\n
9\r\n
Developer\r\n
7\r\n
Network\r\n
0\r\n
\r\n
```

每块：`长度（16进制）\r\n + 数据 \r\n`，以 `0\r\n\r\n` 收尾。

用途：
- SSE / 长轮询
- 服务端流式生成内容（LLM 输出、ZIP 流式打包）
- 代理不想缓冲大响应

### 12.5 流式响应被"缓冲杀死"的场景

你写了一个 SSE / chunked 流式接口，本地 curl 能看到一块一块来，部署到线上 nginx 后变成一次性全给——**nginx `proxy_buffering` 默认 on**。

解决：

```
proxy_buffering off;
proxy_cache off;
```

或在响应头里加 `X-Accel-Buffering: no`（nginx 专用）。

类似地：Apache 的 `mod_deflate` 可能把 chunked 响应先 gzip 再一次性送出，也会破坏流式。

### 12.6 双重压缩事故

应用层返回了 gzip 内容，nginx 又 gzip 一次。客户端看到 `Content-Encoding: gzip`，但实际是 gzip(gzip(原文))，解压一层后是一堆二进制。

防止：应用返回压缩内容时，设 `Content-Encoding` 并告诉反代**别再压**（nginx `gzip_proxied off` 或条件化）。

> **排障锚点**：
> - SSE / 流式响应"本地好、线上断" → nginx `proxy_buffering`
> - 响应乱码 → 双重压缩或 Content-Encoding 没设 + 客户端按明文解
> - "大响应下载很慢但带宽还在" → 没开压缩

---

## 13. 代理 / CDN / 反向代理语义

### 13.1 正向 vs 反向代理

- **正向代理**：**替客户端**出面。客户端配置"所有流量走代理"。常见：企业内网出网、翻墙工具。目标服务器看不到客户端真实 IP。
- **反向代理**：**替服务端**出面。客户端以为在和服务端说话，其实先到反代。常见：nginx、CDN。客户端看不到后端真实结构。

从 HTTP 字节流上，两者**报文几乎没区别**（区别在请求目标形式见 §2.2）。你关心的差异在"谁看得到什么"。

### 13.2 一个请求可能经过的层

```
Client
  │
  ├── 正向代理（如企业出网代理、mitmproxy）
  │
  ├── CDN 边缘节点
  │
  ├── CDN 中心节点
  │
  ├── WAF（Web 应用防火墙）
  │
  ├── 四层负载均衡（LVS / AWS NLB）
  │
  ├── 七层负载均衡（nginx / HAProxy / AWS ALB）
  │
  ├── 服务网格 Sidecar（Envoy）
  │
  └── 应用进程
```

**每一层都可能：重写头 / 缓存 / 终止 TLS / 限流 / 改变连接模型**。排障第一步永远是：**画出这张链路图，标注每一层做了什么**。

### 13.3 四层 vs 七层的可观测差异

- **L4 LB**（基于 TCP 端口）：不解析 HTTP，只转发字节。好处：快、支持任何 TCP 协议。坏处：**不能按 URL / 方法分流，看不到应用指标**。
- **L7 LB**（理解 HTTP）：能按 path/header 路由，能看请求数/状态码分布。代价：必须终止 TLS（才能看明文）。

这决定了**TLS 终止在哪**——反过来也决定了**客户端真实 IP 从哪获取**。

### 13.4 客户端真实 IP 的获取链

经过代理后，服务端看到的"源 IP"是代理的 IP。真实客户端 IP 靠头传递：

```
原始客户端 203.0.113.5
   │
   ├─► CDN 边缘 (node-1)
   │     加: X-Forwarded-For: 203.0.113.5
   │
   ├─► 内部 LB (lb-1)
   │     追加: X-Forwarded-For: 203.0.113.5, 198.51.100.10
   │
   └─► App
         XFF 头值: "203.0.113.5, 198.51.100.10, 172.16.0.5"
```

**解析规则**：

- 最左 = 客户端声称的 IP
- 最右 = 离你最近的代理填的

**安全**：**不能信任整条 XFF**。攻击者可以在自己的请求里伪造 `X-Forwarded-For: 1.1.1.1, 2.2.2.2`，所有中间代理看到这个头会**追加**而不是清空。所以：

- 如果你的链路上 nginx 是边缘 → nginx 应该**覆写**（不是 append）XFF 只写真实 remote addr
- 应用层只信任"从你信任的代理那一跳开始的部分"

Go 的 `httputil.ReverseProxy`、Caddy、Traefik、nginx 都有不同的 XFF 处理策略，**部署前要明确**。

### 13.5 Host 重写与路由错乱

`Host` 头在 HTTP/1.1 是必填，用于虚拟主机路由。

**陷阱**：反代转发时如果改写了 Host，应用可能走错路由。

```
客户端: Host: a.com
   ↓
nginx: proxy_set_header Host b.com;
   ↓
应用: 看到 Host: b.com，按 b.com 路由
```

这有时是故意的（多租户），有时是事故。**排障线索**："本地能跑线上挂 + 应用 404" → 九成是 Host 被改了。

### 13.6 WebSocket / gRPC / 长连接的代理坑

- WebSocket 通过 Upgrade 升级，反代必须显式配置才会转发（nginx 需要 `Connection: upgrade` + `Upgrade: $http_upgrade`）
- gRPC 要求 HTTP/2 贯通。CDN 终止 HTTP/2 回源 HTTP/1.1 会断掉
- 长轮询 / SSE：反代的 `proxy_read_timeout` 要设大（默认 60s 会超时）

### 13.7 谁终止 TLS，谁终止 HTTP 版本

```
Client ──h2/TLS──► CDN ──h2/TLS──► LB ──http/1.1──► App
```

上面是常见模式。**CDN 到 LB 用 HTTP/2**，**LB 到 App 用 HTTP/1.1**（内部网络）。从客户端视角是 HTTP/2，从应用视角是 HTTP/1.1。

这导致：

- App 看到的 `Host` 可能被 LB 改过（不是客户端原始 Host，要看 `X-Forwarded-Host`）
- App 看到的协议是 http，但客户端实际用的是 https，要看 `X-Forwarded-Proto`
- App 看到的 IP 是 LB 的，要看 `X-Forwarded-For`

**框架如 Spring / Django / Express 都有"信任代理"设置**，开启后会从 XFF 头读真实 IP/proto/host。**不开就会把代理 IP 当客户端 IP** → 限流失效、审计错乱。

> **排障锚点**：
> - "本地能跑线上 404" → 查 Host 重写
> - 真实 IP 拿不到 → 查是不是 L4 LB 直接转（看不到 XFF），或 L7 但没信任代理
> - WebSocket / SSE 线上卡 → 反代 buffering / read_timeout
> - 502 → 回源连接断（§6）、TLS 握手失败（§8）、上游返回非法报文

---

## 14. 认证：Basic / Bearer / JWT（HTTP 层视角）

**这一章只讲凭证在 HTTP 上怎么跑**。OAuth 2 / OIDC 的全流程不展开——那属于应用层协议。

### 14.1 Basic Auth

```
Authorization: Basic base64(username:password)
```

Base64 不是加密，是编码。Basic 在 HTTPS 下勉强能用，在 HTTP 下等于明文。

401 响应附：

```
WWW-Authenticate: Basic realm="Access to internal tools"
```

浏览器看到会弹原生登录框。

今天主要用途：内部工具、API 保护（更常见的是 Digest 或干脆换成 Token）。

### 14.2 Bearer Token（含 JWT）

```
Authorization: Bearer <token>
```

`<token>` 可以是：

- **不透明 token**（随机字符串）：服务端维护一张表，查表验证
- **JWT（JSON Web Token）**：自包含，`header.payload.signature` 三段 base64url 拼接

JWT 的三段：

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1MSIsImV4cCI6MTc...
↑ Header        ↑ Payload（用户 ID、过期）    ↑ Signature
```

服务端只需验签（用密钥或公钥）即可确定 payload 未被篡改 → 无需查库。

### 14.3 JWT 的三种排障现象

| 现象 | 原因 |
|---|---|
| `signature verification failed` | 密钥/公钥不对，或 payload 被改过 |
| `token expired` | `exp` 字段过期（注意时钟偏差） |
| `invalid audience/issuer` | `aud` / `iss` 字段不匹配 |

**区分签名失败和过期很关键**——过期可以让客户端刷新，签名失败通常是配置错或攻击。

### 14.4 401 的正确用法

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="api", error="invalid_token", error_description="token expired"
```

客户端根据 `error` 字段决定：
- `invalid_token` → 刷新 token
- 其他 → 跳登录

### 14.5 典型事故

**事故 1：Bearer token 泄漏**

- 打印在日志里（注意脱敏）
- 带在 URL 查询串里（见浏览器历史、Referer 泄漏）
- 存在 localStorage 被 XSS 偷走

最佳实践：
- 短生命期 access token + 长生命期 refresh token
- access token 存内存 or HttpOnly Cookie
- 绝不放 URL

**事故 2：JWT 算法降级**

早期 JWT 库允许 `alg: none`（不签名）。恶意客户端把 header 改成 `none`，服务端盲信——完全绕过。现代库都拒绝，但老代码要查。

**事故 3：无法失效**

JWT 是自包含的，只要签名有效、未过期，服务端就认。想"登出让 token 立即失效"要做黑名单或短 TTL——这是 JWT 的固有代价。

> **排障锚点**：
> - 401 但不知道该刷新还是登出 → 看 `WWW-Authenticate` 的 error
> - JWT 间歇性签名失败 → 多实例密钥不一致，或密钥轮换没同步
> - "用户登出后还能用" → JWT 本身没失效机制，要么黑名单要么短 TTL

---

## 15. 性能排障：把一个慢请求切成 6 段

**这是全文的核心章节**。线上 90% 的"HTTP 问题"是"慢"。慢的根因可以出在任何一段——你的工作是按顺序排除。

### 15.1 6 段模型

```
[1] DNS 解析     [2] TCP 握手    [3] TLS 握手
    │                │               │
    └── "建连阶段"，一次性开销 ────────┘
                                      │
                                  [4] 请求发送
                                      │
                                  [5] 服务端处理（TTFB 最大头）
                                      │
                                  [6] 响应接收（下载）
                                      │
                                  [7] 客户端解析/渲染（不严格属于 HTTP）
```

Chrome DevTools → Network → 点某个请求 → Timing 标签，能看到每一段多少 ms。

### 15.2 每一段的典型病因和工具

#### 段 [1] DNS（通常 <50ms）

**慢**：递归 DNS 服务器抽风 / 域名 TTL 太短 / 解析 IPv6 失败后 fallback 到 IPv4

**工具**：
- `dig example.com +trace` — 看递归链
- `time dig example.com` — 量时间

#### 段 [2] TCP（通常 1 RTT ≈ 几十 ms）

**慢**：SYN 包丢、目标 IP 不可达、端口被防火墙丢

**工具**：
- `telnet host 443` / `nc -zv host 443` — 测端口可达
- `traceroute -T -p 443 host` — 看哪一跳卡

#### 段 [3] TLS（通常 1–2 RTT）

**慢**：没复用会话（每次全握手）、证书链太长、OCSP 在线查询慢

**工具**：
- `curl -w "%{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total}\n" -o /dev/null -s https://example.com` — 一次得到每段耗时
- `openssl s_client` 加 `-sess_out / -sess_in` 看会话复用

#### 段 [4] 请求发送（通常 <10ms）

**慢**：大 body（上传）、客户端带宽瓶颈、网卡问题

**工具**：浏览器 Network → Request Sent 时长

#### 段 [5] 服务端处理（TTFB，常是大头）

**慢**：数据库慢、上游超时、GC / 锁、线程池满、外部依赖挂

**工具**：
- 服务端 APM（Datadog / NewRelic / 自研 trace）
- 日志里请求的 trace id，找到对应的 span 树
- 加埋点

**这一段是最复杂的**，因为它包含了你的**整个后端**。排障顺序：
1. 先看服务端自身 p99 延迟是否飙升 → 是，查服务端
2. 否，查上游依赖（DB、缓存、外部 API）
3. 看是否个别请求慢（热点 key、大 user）

#### 段 [6] 响应下载

**慢**：响应体太大、没压缩、带宽不够、CDN 没命中

**工具**：
- Content-Length 看大小
- `curl -w "%{size_download}\n"` 看实际下载量
- 浏览器 Network → Size 列

#### 段 [7] 客户端解析/渲染

不严格属于 HTTP，但用户体验里看不出区别。比如 100KB JSON 在前端 `JSON.parse` 要 10ms，大列表 React 渲染要 500ms。Chrome Performance 面板看。

### 15.3 一次真实的 case study

**症状**：某个 API p99 从 200ms 涨到 2000ms，持续 30 分钟。

**排障步骤**：

1. 先看 APM：服务端 p99 正常 → 问题不在服务端自身 → 问题在建连 / 下载
2. 看客户端分布：只有某区域用户受影响 → 怀疑 CDN / DNS
3. `dig +trace` 域名：CDN 节点 IP 响应正常
4. 抓几个慢请求的 curl timing：`time_connect` 正常，`time_appconnect` 异常大（2s）
5. `openssl s_client` 连 CDN 节点：握手时 OCSP 查询卡了 1.5s
6. **根因**：CDN 节点的 OCSP Stapling 配置出错，每次要在线查 CA 的 OCSP 响应

**修复**：开启 OCSP Stapling，服务端预取吊销状态一起返回。

**教训**：p99 涨不一定是服务端问题，**建连阶段也会吃掉 1-2s**。

### 15.4 排障的优先级

同样是慢，不同业务的**忍耐度不同**：

- 用户交互接口（p99 500ms 就难受）
- 后台任务（p99 10s 都能忍）
- 长轮询 / SSE（定义上就长，不能用 p99 衡量）

**先分清"你在量什么指标"，再说"它是不是变慢了"**。

### 15.5 慢请求的监控怎么建

最小集合：

- **客户端 RUM（Real User Monitoring）**：用 `PerformanceNavigationTiming` API 上报 6 段耗时
- **服务端接入层**：nginx 日志记 `$request_time`（总）、`$upstream_response_time`（上游）、`$upstream_connect_time`（连上游）
- **应用层**：trace id 贯穿，每个外部依赖 span 化

这三层交叉后，几乎任何慢请求都能定位到具体段。

> **排障锚点**：
> - 整体慢 → 先分段再细化
> - p99 飙升 → 先看服务端 APM 再看客户端 RUM，区分"是处理慢还是建连慢"
> - 移动端慢但 PC 端好 → 怀疑弱网下的 TCP HOL（§7）或 TLS 全握手（§8）

---

## 16. 工具链：哪个工具擅长看什么

| 想看 | 工具 | 关键命令 |
|---|---|---|
| 单次请求、调参 | **curl** | `curl -v` / `curl -w "%{...}"` |
| 浏览器全景 | **Chrome Network** | F12 → Network 面板 |
| TCP / TLS 字节 | **tcpdump** / **Wireshark** | `tcpdump -i any port 443 -w out.pcap` |
| 应用层抓包（HTTPS 明文） | **mitmproxy** | 配置证书，走代理 |
| DNS | **dig** | `dig example.com +trace` |
| TLS 握手 | **openssl s_client** | `openssl s_client -connect h:443 -servername h` |
| HTTP/2 / 3 专项 | **nghttp / curl --http3** | `nghttp -v https://h/path` |
| 反代侧日志 | **nginx access log** | `$request_time` / `$upstream_*` |

### 16.1 curl 的排障三件套

```bash
# 1. 看一次请求的全部耗时
curl -w "@curl-timing.txt" -o /dev/null -s https://example.com/

# curl-timing.txt:
time_namelookup:     %{time_namelookup}\n
time_connect:        %{time_connect}\n
time_appconnect:     %{time_appconnect}\n
time_pretransfer:    %{time_pretransfer}\n
time_starttransfer:  %{time_starttransfer}\n
time_total:          %{time_total}\n
size_download:       %{size_download}\n

# 2. 看完整握手过程
curl -v --trace-time https://example.com/

# 3. 强制 HTTP/2 或 /3，看协商结果
curl --http2 -v https://example.com/
curl --http3 -v https://example.com/
```

### 16.2 Chrome Network 的常见误区

- **Time 列不是服务端处理时间**，是从发出到收完的总时长
- **Size 列的第一个数字是"传输大小"**（可能压缩），第二个是"解压后大小"
- **`(disk cache)` / `(memory cache)` 不是从网络来的**，但 status 依然显示 200
- **右键 "Copy as cURL"** 复现问题最快

### 16.3 Wireshark / tcpdump：什么时候需要

HTTPS 下你看不到明文 body——要用 mitmproxy 或在客户端导出 `SSLKEYLOGFILE` 给 Wireshark 解密。

典型场景：
- 怀疑是 TCP 层的问题（重传、乱序、RST）
- 排查中间盒改写（WAF / 代理是否改了头）
- 协议级问题（HTTP/2 帧错）

**90% 的 HTTP 排障用 curl + 浏览器 + 服务端日志够了**，Wireshark 是最后兵器。

---

## 17. 排障 Playbook（按症状查）

**凌晨 3 点照着跑版。每条 3–5 步。**

### 17.1 请求卡住不返回

1. **`curl -v --max-time 60`** 直连试，看卡在哪一段
   - 卡在建连 → DNS / TCP / 防火墙（§15.1–15.2）
   - 卡在 `ServerHello` 前 → TLS 握手（§8）
   - 卡在响应前 → 服务端处理或上游超时（§15.5）
2. **绕过客户端**：直接 curl 源站 IP（加 `--resolve host:port:ip`），排除 DNS / CDN
3. **服务端日志**：请求有没有到？到了卡在哪个 span？
4. **网关层**：nginx `$upstream_response_time` 看上游多久返回

### 17.2 大量 502 / 504

1. **分清 502 还是 504**：
   - 502 = 上游连不上 or 返回非法报文
   - 504 = 上游没在超时内返回
2. **502 优先查**：
   - 上游进程挂了？（health check）
   - 连接池耗尽？（§6.3）
   - TLS 握手失败（如回源证书过期）？（§8）
3. **504 优先查**：
   - 上游慢（看上游 APM）
   - nginx `proxy_read_timeout` 合不合理（一般 30–60s）
4. **突发还是持续**：
   - 突发 → 发布 / 流量尖峰
   - 持续 → 容量 / 依赖挂

### 17.3 偶发慢请求（p99 抖动）

1. **RUM 还是服务端 APM 显示的抖动**？
   - 仅 RUM 抖 → 客户端侧（网络、DNS、TLS）
   - 服务端 APM 也抖 → 服务端 / 依赖
2. **慢请求的共性**：
   - 某用户？→ 热点数据、权限膨胀
   - 某路径？→ 该路径代码问题
   - 某时段？→ 依赖 GC、备份任务
3. **服务端 GC / 锁**：看 JVM GC 日志、Go pprof
4. **HTTP/2 丢包 HOL**：移动端专属 → 考虑 HTTP/3

### 17.4 CORS 报错

1. **F12 看是预检还是真请求被拦**
2. **看响应头**：`Access-Control-Allow-Origin`、`Allow-Methods`、`Allow-Headers` 是不是匹配
3. **有没有带 credentials**：
   - 是 → Allow-Origin 不能是 `*`，必须具体
   - 是 → Allow-Credentials 必须是 true
4. **本地 vs 线上差异**：本地 dev proxy 可能自动转发，线上真跨源了

### 17.5 用户说缓存不更新

1. **先确认用户看到的到底是什么**：让他 F12 → Disable Cache → 刷新
2. **分层 purge**：
   - 浏览器强缓存（`max-age` 未过期）
   - CDN 缓存（响应头看 `Age` / `X-Cache`）
   - 源站是不是真的已经是新的
3. **看响应头**：
   - `Cache-Control` / `Expires` / `Age` / `Vary`
   - `Vary` 写错了可能导致某些 UA 永远拿老版本
4. **指纹化文件名**：根治方案是 URL 里带哈希（§9.4）

### 17.6 证书错误 / TLS 握手失败

1. **`openssl s_client -connect host:443 -servername host -showcerts`**：
   - 返回了几张证书？（应该是叶子 + 中间）
   - 验证链能不能对到根？
2. **老客户端专属**（Android 7 以下、老 curl）：
   - 根 CA 是不是太新（Let's Encrypt 旧链 vs 新链）
   - 密码套件太现代
3. **SNI 不匹配**：
   - 用 IP 直连 → SNI 没设 → 握手报 `unrecognized_name`
4. **时钟偏差**：客户端时间错了也会报"证书过期"

### 17.7 跨域丢 Cookie

1. **Network 看请求有没有带 Cookie**（没带 → 前端或浏览器没发）
2. **没带的原因（按概率）**：
   - SameSite 限制了（默认 Lax，非顶层 GET 不带）
   - 前端没 `credentials: 'include'`
   - 路径/域不匹配
3. **带了但后端收不到**：
   - 代理吃掉了（少见）
   - 后端解析 Cookie 的库版本问题
4. **对应 CORS 配置**：Allow-Origin 具体、Allow-Credentials true

### 17.8 请求体被截断

1. **`Content-Length` 和实际体长度是否一致**
2. **链路上有没有 body 大小限制**：
   - nginx `client_max_body_size`
   - 网关限流
   - 应用框架的限制
3. **chunked 被中间代理改成定长**（少见但存在）
4. **压缩问题**（§12）

---

## 附录

### A. 状态码速查表

| 码 | 名称 | 典型场景 |
|---|---|---|
| 100 | Continue | 客户端可继续发 body |
| 101 | Switching Protocols | WebSocket / h2c 升级 |
| 200 | OK | 请求成功 |
| 201 | Created | POST/PUT 创建成功 |
| 202 | Accepted | 异步接受 |
| 204 | No Content | 成功无体（PUT/DELETE 常用） |
| 206 | Partial Content | Range 请求返回 |
| 301 | Moved Permanently | 永久重定向（可能改方法） |
| 302 | Found | 临时重定向（可能改方法） |
| 304 | Not Modified | 协商缓存命中 |
| 307 | Temporary Redirect | 临时重定向（保留方法） |
| 308 | Permanent Redirect | 永久重定向（保留方法） |
| 400 | Bad Request | 请求格式错 |
| 401 | Unauthorized | 未认证 |
| 403 | Forbidden | 无权限 |
| 404 | Not Found | 资源不存在 |
| 405 | Method Not Allowed | 方法错 |
| 408 | Request Timeout | 请求发送超时 |
| 409 | Conflict | 并发冲突 |
| 410 | Gone | 永久删除 |
| 413 | Payload Too Large | 体太大 |
| 414 | URI Too Long | URL 太长 |
| 415 | Unsupported Media Type | Content-Type 不认 |
| 416 | Range Not Satisfiable | Range 超出范围 |
| 422 | Unprocessable Entity | 格式对但业务校验失败 |
| 429 | Too Many Requests | 限流 |
| 499 | (nginx) Client Closed Request | 客户端主动断开 |
| 500 | Internal Server Error | 服务端兜底错 |
| 501 | Not Implemented | 功能未实现 |
| 502 | Bad Gateway | 上游坏响应 |
| 503 | Service Unavailable | 服务主动拒绝 |
| 504 | Gateway Timeout | 上游超时 |

### B. 常用头字段速查

**请求头**：
- `Host` / `User-Agent` / `Accept` / `Accept-Encoding` / `Accept-Language`
- `Authorization` / `Cookie` / `Referer` / `Origin`
- `If-None-Match` / `If-Modified-Since` / `Range`
- `Content-Type` / `Content-Length` / `Transfer-Encoding`
- `Connection` / `Upgrade`
- `X-Forwarded-For` / `X-Forwarded-Proto` / `X-Forwarded-Host`

**响应头**：
- `Content-Type` / `Content-Length` / `Content-Encoding` / `Content-Disposition`
- `Cache-Control` / `Expires` / `ETag` / `Last-Modified` / `Vary` / `Age`
- `Set-Cookie` / `WWW-Authenticate`
- `Location`（重定向）
- `Access-Control-*`（CORS）
- `Strict-Transport-Security` / `Content-Security-Policy` / `X-Frame-Options`

### C. 延伸阅读

- **RFC 9110** — HTTP Semantics（语义总纲，2022）
- **RFC 9111** — HTTP Caching
- **RFC 9112** — HTTP/1.1
- **RFC 9113** — HTTP/2
- **RFC 9114** — HTTP/3
- **High Performance Browser Networking**（Ilya Grigorik，在线免费）— 全栈网络性能经典
- **MDN HTTP** — 参考性最好的中英文文档（中文质量也不错）
- **HTTP 的 30 年演进**（[Sean Allen 博客] / [Cloudflare 博客]）— 版本演进动机
- **TLS 1.3 in Pictures**（Michael Driscoll 可视化）— TLS 握手动画

---

**本文档的使用建议**：

- 第一次读：按路线 A 线性读，不懂的先跳过，建立骨架
- 后续复习：盯第 1 章生命周期图和第 17 章 Playbook
- 线上出事：直接跳第 17 章对应症状，再按"排障锚点"上溯到协议章节

祝你排障顺利。
