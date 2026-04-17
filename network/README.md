# 网络文档索引

更新时间：2026-04-17

这个目录里的文档按**协议分层**组织，不是按话题堆砌。每篇讲自己层的事，不越界——需要联动时靠交叉引用。

---

## 分层地图

```
┌─────────────────────────────────────────────────────────────┐
│ 应用层（具体协议）                                             │
│                                                              │
│  http.md ────── websocket.md ────── sse.md    webrtc.md      │
│                                                   │          │
│  └──────── 都建立在 TCP 之上 ────────┘           │          │
│                      │                          UDP+ICE+DTLS │
└──────────────────────┼───────────────────────────┼───────────┘
                       │                           │
                       ▼                           │
┌──────────────────────────────────────┐          │
│ Socket 编程 / IO 模型                 │          │
│                                       │          │
│   socket-io.md                        │          │
│   （socket API / 粘包 / epoll / Reactor）         │
└───────────────────┬──────────────────┘          │
                    │                              │
                    ▼                              │
┌─────────────────────────────────────────────────┐│
│ 传输层 + 网络层                                  ││
│                                                  ▼│
│   basic.md                                         │
│   （TCP/UDP 协议、状态机、流控/拥控、URI/URL）       │
└────────────────────────────────────────────────────┘

              实时通信协议选型.md
              （websocket / sse / webrtc 的选型索引）
```

---

## 三种读法

### 🎓 系统学习（从底到顶）

第一次看，按顺序读：

1. [`basic.md`](./basic.md) — TCP/UDP 本体、三握四挥、状态机、URI/URL
2. [`socket-io.md`](./socket-io.md) — socket API、粘包、epoll、Reactor 模式
3. [`http.md`](./http.md) — HTTP 协议全景与排障手册
4. [`sse.md`](./sse.md) — 在 HTTP 上做服务端推
5. [`websocket.md`](./websocket.md) — 在 HTTP 握手后切全双工
6. [`webrtc.md`](./webrtc.md) — 跳出 HTTP，走 UDP + NAT 穿透
7. [`实时通信协议选型.md`](./实时通信协议选型.md) — 把 4/5/6 的选型与排障串起来

### 🎯 面试冲刺

时间紧的话只啃核心：

- [`basic.md`](./basic.md) §4–§11（三握四挥 + TIME_WAIT + 可靠性 + 拥塞控制）
- [`socket-io.md`](./socket-io.md) §4–§9（粘包 + 分帧 + select/poll/epoll）
- [`http.md`](./http.md) §3–§9（方法 + 状态码 + 头 + 连接 + 版本 + TLS + 缓存）
- [`实时通信协议选型.md`](./实时通信协议选型.md) —— 横向对比

### 🚑 线上排障

凌晨三点照着跑：

- [`http.md §17`](./http.md) Playbook — 按症状查表
- [`basic.md §13`](./basic.md) — `refused / reset / timeout` 的本质区别
- [`socket-io.md §14`](./socket-io.md) — `too many open files` / `EAGAIN` / `Address already in use`
- [`实时通信协议选型.md`](./实时通信协议选型.md) §排障 — 推流协议的定位顺序

---

## 每篇一句话

| 文档 | 讲什么 | 不讲什么 |
|---|---|---|
| [basic.md](./basic.md) | TCP/UDP 协议、三握四挥、状态机、TIME_WAIT 根因、拥塞控制、URI/URL | 怎么用 API，具体应用协议 |
| [socket-io.md](./socket-io.md) | socket 系统调用、listen backlog、粘包分帧、5 种 IO 模型、epoll 演进、Reactor | 具体应用协议的帧格式 |
| [http.md](./http.md) | HTTP 报文 / 方法 / 状态码 / 头 / 连接管理 / 版本演进 / TLS / 缓存 / Cookie / CORS / 代理 / 性能排障 | TCP 本身、IO 模型 |
| [websocket.md](./websocket.md) | WebSocket 握手、帧格式、心跳、断线重连 | epoll 原理、TCP 保活机制 |
| [sse.md](./sse.md) | SSE 事件流格式、自动重连、LLM token 流场景 | HTTP chunked 底层机制（→ http.md） |
| [webrtc.md](./webrtc.md) | ICE / STUN / TURN / DTLS-SRTP / 媒体协商 | TCP（WebRTC 不用 TCP） |
| [实时通信协议选型.md](./实时通信协议选型.md) | WebSocket / SSE / WebRTC 选型决策树与排障定位 | 协议内部细节（去各自文档） |

---

## 文档之间的引用约定

- 每篇头部有 **"上下文"** 块，列出上游（建议先读）和下游（读完可看）
- 协议细节**只在各自主文档讲一次**，其它文档引用不重复
- 章节编号稳定，引用格式 `文档.md §N.M`，改编号要同步改引用

---

## 约定贡献

- 新增协议 / 话题：**先判断属于哪一层**。L4 以下进 `basic.md`；用户态 API / 并发模型进 `socket-io.md`；具体应用协议单独一篇
- 避免在多处重复同一个话题，有冲突就抽到更底层文档再反向引用
- 每个新文档也加 **上下文 / 目标 / 排障锚点** 三件套，风格保持一致

---

祝排障顺利，别凌晨三点找我。
