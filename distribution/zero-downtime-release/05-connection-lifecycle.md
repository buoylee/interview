# 05 — 连接生命周期:为什么"摘流量"常常没用

> 核心问题:前四章你都做对了——readiness 准、preStop 配了、grace 够、滚动旋钮也对。可上了 WebSocket / gRPC / HTTP keep-alive,**滚动发布时长连接的用户还是被断、或者一直打在正在退场的老实例上**。为什么?
>
> 一句话点破:**"摘流量"摘的是「新连接的分发」,对「已经建立的连接」毫无作用。** 前四章的 endpoint 摘除、LB 不再转发,管的都是"新连接别再来";而长连接早就建好了,它会**继续在老连接上发请求**,直到这条连接被**主动关闭**。这一章把"连接"这个一直被忽略的主角拎出来收口。

---

## A · 问题根源:摘流量 vs 连接复用

回顾 ch03 的链路 A:Endpoints 摘除 → kube-proxy/LB 不再把**新连接**路由到这个 Pod。但看这两种连接:

```
  短连接(每请求一条 TCP,用完即关):
     摘流量后,下一个请求 = 新连接 → 被路由到别的 Pod ✅  摘流量有效

  长连接 / keep-alive(一条 TCP 复用发很多请求):
     连接 t0 就建好了,一直复用 →
     摘流量后,客户端/LB 继续在【这条老连接】上发请求 → 还是打到正在退场的 Pod ❌
     直到这条连接被【主动关闭】,客户端才会去建新连接(才会被重新路由)
```

谁是长连接?**比你以为的多**:

- **HTTP/1.1 keep-alive**:浏览器、LB→后端、HTTP 客户端默认复用连接。
- **HTTP/2 / gRPC**:一条连接多路复用海量请求,**天生长连接**,且复用更彻底。
- **WebSocket / SSE**:本质就是不关的长连接。
- **数据库 / Redis 连接池**:也是长连接(不过这是你 app 作为客户端去连下游,方向相反)。

> 所以 ch03 那句"app 关 socket 前先 preStop 等摘流量"对**新连接**成立;对**已建立的长连接**,还得额外做"**主动通知对端:这条连接要关了,去重连**"。这就是本章的活儿。

---

## B · L4 vs L7:谁能在哪个粒度上排空

| | L4(TCP)LB,如 NLB/LVS | L7(HTTP)LB,如 ALB/nginx/Envoy |
|---|---|---|
| 看到的粒度 | **连接** | **请求** |
| draining 能做的 | 停止新连接,**已建立的 TCP 连接继续**到自然关闭/超时 | 能在**请求**粒度控制:可注入 `Connection: close`、可在老连接上拒新请求 |
| 长连接处理 | 无能为力(看不懂 HTTP),只能等连接结束或超时强断 | 能主动让连接优雅收尾(发关闭信号) |

> 要点:**L4 摘后端 = 连接级排空**(等连接自然结束,deregistration delay 就是这个等待窗口);**L7 才能在请求级优雅收尾**。长连接 + 只有 L4 LB = 你几乎只能靠"应用层主动关连接 + 超时强断",LB 帮不上细活。

---

## C · 长连接怎么优雅断:发"连接级关闭信号" ⭐

核心手法:**服务端主动告诉对端"这条连接别再用了,把手头的收个尾,然后去重连"**。不同协议有不同的"那句话":

| 协议 | 关闭信号 | 语义 |
|---|---|---|
| **HTTP/1.1** | 响应头 `Connection: close` | "这条连接处理完当前请求就关,你下个请求去建新连接" |
| **HTTP/2 / gRPC** | **GOAWAY** 帧 | "别在这条连接上开新 stream 了;已开的我处理完;我要走了" |
| **WebSocket** | Close 帧(opcode 0x8) | 主动关,客户端收到后**重连**(到新实例) |
| **SSE** | 服务端结束响应流 | 客户端按 SSE 规范**自动重连** |

机制串起来(优雅下线一个有长连接的实例):

```
  收到下线信号(SIGTERM / preStop 触发)
     → 停止接受【新连接】(ch03)
     → 对【已建立的长连接】逐个发关闭信号:
          HTTP/2/gRPC: GOAWAY  ·  HTTP/1.1: Connection: close  ·  WS/SSE: 主动 close
     → 等这些连接上手头的请求/stream 收尾(排空)
     → grace 内没收完的,超时强断
     → 退出
```

**gRPC 的标准做法**:`server.GracefulStop()`(Go)/ `server.stop(grace)`(其它语言)——它就是发 GOAWAY + 等existing RPC 完成 + 超时强停。**这是 gRPC 服务优雅下线的命门**,光配 k8s preStop、不调 GracefulStop,长连接照样被硬断。

### C1 别忘了"重连风暴"(架构师追问)

主动断长连接 → 一大批客户端**同时重连** → 打到剩下的实例上 = **thundering herd**。尤其 WebSocket(成千上万长连接)滚动发布时,每替换一个实例就甩出一批重连。对策:

- 客户端**重连退避 + 抖动**(exponential backoff + jitter),别所有人同一刻重连。
- 服务端**分批**断(别一次性全断),或滚动节奏放慢、给重连留缓冲。
- 重连走的入口要扛得住瞬时连接洪峰(连接建立成本 = TCP+TLS,比想象贵)。

> 这是 ch02 冷启动雪崩的近亲:**断连风暴打到的新实例如果还冷,双杀。** 所以长连接服务的发布,要同时考虑"优雅断"和"重连别压垮"。

---

## D · Service Mesh(Envoy)里的连接排空 + 一个经典坑 ⭐

如果你在 mesh 里(Istio/Linkerd),连接排空有 sidecar 帮忙、但也多一个**时序坑**:

- **Envoy 的排空**:支持 connection draining、`drain_time`、对 HTTP/2 发 GOAWAY;sidecar 收到下线信号会优雅排空它代理的连接。
- **经典坑:sidecar 与 app 的关闭时序**。Pod 里 app 容器 + envoy sidecar 一起被终止。如果 **envoy 先停**,app 还在排空的在途请求(要经 envoy 出去/进来)就**没了代理 → 失败**。这正是 Istio 早期"滚动发布偶发 503"的著名根因。
- **对策**:给 sidecar 也配 preStop(让 envoy 晚于 app 退)、`EXIT_ON_ZERO_ACTIVE_CONNECTIONS`(envoy 等连接清零再退)、`holdApplicationUntilProxyStarts`(启动时反过来:app 等 envoy 就绪——这是 ch02 入场侧的对称坑)。

> 架构师点:**有了 sidecar,优雅下线从"app 一个进程"变成"app + 代理两个进程的协同退出",时序错了照样掉请求。** 这是 mesh 增加的复杂度,能讲出来就到位了。详见 [`cloud-native-landscape/04`](../../cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md)。

---

## E · 把整条连接模型收口

回看整个 track,"连接"这个主角其实贯穿始终,这里收口:

| 章节 | 连接视角下在干什么 |
|---|---|
| ch01 readiness | 决定 LB 要不要**建新连接**到这个实例 |
| ch02 优雅上线 | 预建到下游的连接池(别让首请求现场握手);slow-start 让**新连接**逐步来 |
| ch03 优雅下线 | preStop 等"**新连接**别再来",再关监听 socket |
| **ch05 本章** | 已建立的**老连接/长连接**怎么主动收尾,不被硬断 |

> 一句话总纲:**"摘流量"治新连接,"连接级关闭信号(Connection: close / GOAWAY / WS close)"治老连接。两手都做,长连接服务才能真零停机。** 只做前者,是大多数人优雅下线"做了还是断"的最后一块拼图。

---

## 踩坑框 ⚠️

> **配了 preStop/readiness,WebSocket 用户还是被硬断** → 摘流量只管新连接;长连接要**主动发 close 帧**让客户端重连,并配重连退避(C)。

> **gRPC 服务优雅下线无效** → 光靠 k8s preStop 不够,要调 `GracefulStop()` 发 GOAWAY + 排空 existing RPC(C)。

> **HTTP keep-alive 让请求继续打老实例** → L7 注入 `Connection: close` 让连接收尾;L4 只能等连接结束/超时(B)。

> **断长连接引发重连风暴** → 客户端 backoff+jitter、服务端分批断、入口扛连接洪峰;否则打到冷新实例双杀(C1)。

> **mesh 里滚动偶发 503** → app 与 envoy sidecar 关闭时序:envoy 先停 → app 在途没代理。给 sidecar 配 preStop / `EXIT_ON_ZERO_ACTIVE_CONNECTIONS`(D)。

> **只有 L4 LB 还想请求级优雅** → L4 看不懂 HTTP,做不到;要请求级排空得上 L7 / mesh(B)。

---

## 面试速记卡(只做复习自检)

**人人会的**
- WebSocket 怎么优雅断?→ 服务端发 close 帧,客户端重连到别的实例。

**资深分水岭** ⭐
- 为什么 readiness 摘了流量,长连接还打在老实例上?→ 摘流量只阻止**新连接**;已建立的长连接会继续复用,直到被**主动关闭**。
- 各协议的"关闭信号"是什么?→ HTTP/1.1 `Connection: close`;HTTP/2 & gRPC **GOAWAY**;WebSocket close 帧;SSE 结束流让客户端重连。
- gRPC 优雅下线关键?→ `GracefulStop()`:发 GOAWAY、不收新 stream、排空 existing RPC、超时强停;光配 preStop 不调它没用。
- L4 和 L7 LB 在排空上的差别?→ L4 看连接,只能停新连接、等老连接自然结束;L7 看请求,能注入 `Connection: close`、在请求粒度优雅收尾。

**架构师**
- 主动断长连接有什么副作用,怎么治?→ 重连风暴(thundering herd);客户端 backoff+jitter、服务端分批断、入口扛连接洪峰,还要防打到冷新实例(接 ch02 雪崩)。
- mesh 里优雅下线多了什么坑?→ app 与 envoy sidecar 的关闭时序:envoy 先退则 app 在途请求没代理 → 503;对策 sidecar preStop / `EXIT_ON_ZERO_ACTIVE_CONNECTIONS` / `holdApplicationUntilProxyStarts`。

---

## 小结 + 桥接

> **连接生命周期是优雅发布的最后一块拼图**:"摘流量"只治新连接的分发,**已建立的长连接(keep-alive / HTTP2 / gRPC / WS / SSE)要靠服务端主动发关闭信号(`Connection: close` / GOAWAY / close 帧)让对端收尾并重连**;断连要防重连风暴;mesh 里还要管 app↔sidecar 的关闭时序。两手都做,长连接服务才真零停机。

- 这章治的"摘流量为何没用",起点在 → [`ch03 优雅下线 G 节`](./03-graceful-shutdown.md)
- 重连风暴打到冷新实例的双杀 → [`ch02 冷启动雪崩`](./02-graceful-startup.md)
- L7/L4 与连接处理的更多细节 → [`gateway/03`](../../gateway/03-routing-and-load-balancing.md)、[`gateway/08`](../../gateway/08-gateway-as-distributed-system.md)
- service mesh sidecar 模型 → [`cloud-native-landscape/04`](../../cloud-native-landscape/04-service-mesh-sidecar-to-ambient.md)

---

**🎉 track 收尾。** 回到不变式:**流量只打到「已就绪 AND 不在退场」的实例。** 五章分别守它的一个面——ch01 谁判定就绪/退场、ch02 别在没热时算就绪、ch03 退场时别掉请求、ch04 放大到 fleet 不塌容量、ch05 别让长连接绕过这一切。配 [`lab/`](./lab/) 把 ch03 的核心亲手跑一遍。
