# WebSocket 协议系统学习

更新时间：2026-04-17

目标：读完你应该能——

- 手写最小可用的 WebSocket 服务端 / 客户端
- 看懂一帧 WebSocket 字节在做什么
- 线上出问题时，按顺序定位是握手、代理、心跳、背压哪里出了事

与 SSE 对比见 [`sse.md §8`](./sse.md) 与 [`实时通信协议选型.md`](./实时通信协议选型.md)。

---

## 1. 起点：WebSocket 到底解决什么问题

HTTP 的天然缺陷：**请求—响应**，一来一回；想持续互相说话要么轮询要么黑魔法。WebSocket 要的是**一次握手之后，双方可以随时发消息，且每条消息不再带 HTTP 头**。

几种"推拉"技术的定位：

| 技术 | 方向 | 是否双向 | 是否基于 HTTP |
| --- | --- | --- | --- |
| 长轮询 | C → S → C | 伪 | 是（每次一个 HTTP）|
| SSE | S → C（单向推）| 否 | 是（一个长响应）|
| **WebSocket** | C ↔ S | 真双向 | **握手用 HTTP**，之后换成自己的帧协议 |

**直觉**：WebSocket 是把一根 TCP 连接"借"给你，握手阶段骗过 HTTP 代理/网关，之后在这根 TCP 上按规范收发一帧帧二进制或文本。因此它：

- 比 HTTP 省头（每帧最少 2 字节）
- 比裸 TCP 容易落地（穿透大多数 HTTP 基础设施）
- 比 SSE 复杂（要自己做心跳、重连、鉴权续期、消息重传）

**什么时候选 WebSocket**：聊天、协同编辑、实时游戏状态同步、交易撮合推送、客户端需要向服务端发命令。

**什么时候不选**：单向推（SSE 就够）、偶发通信（普通 HTTP 就好）、需要 NAT 穿透的音视频（上 WebRTC）。

---

## 2. 协议本体

### 2.1 握手：HTTP Upgrade 的魔术

客户端先发一个标准 HTTP GET，但带上升级头：

```
GET /chat HTTP/1.1
Host: example.com
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==
Sec-WebSocket-Version: 13
Sec-WebSocket-Protocol: chat, json.v1     (可选，子协议)
Sec-WebSocket-Extensions: permessage-deflate  (可选，压缩)
Origin: https://example.com
```

服务端同意后回 **101 Switching Protocols**：

```
HTTP/1.1 101 Switching Protocols
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
Sec-WebSocket-Protocol: chat
```

`Sec-WebSocket-Accept` 怎么来的：

```
base64(sha1( client_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11" ))
```

那串魔数是规范写死的常量，防止普通 HTTP 服务被"假装成 WebSocket"误触发。

**握手成功之后**，这条 TCP 连接上的字节流不再按 HTTP 解析，而是按下面的帧格式来回。

### 2.2 帧结构（记住这张图就够了）

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
|     Extended payload length continued, if payload len == 127  |
+ - - - - - - - - - - - - - - - +-------------------------------+
|                               | Masking-key, if MASK set to 1 |
+-------------------------------+-------------------------------+
| Masking-key (continued)       |          Payload Data         |
+-------------------------------- - - - - - - - - - - - - - - - +
|                         Payload Data                          |
+---------------------------------------------------------------+
```

字段含义：

- **FIN**：这是消息的最后一帧吗？为 1 表示消息完整；为 0 表示后面还有"继续帧"
- **RSV1–3**：预留位，一般都是 0；开了 `permessage-deflate` 压缩时 RSV1=1
- **opcode**：
  - `0x0` 继续帧（分片的后续）
  - `0x1` 文本帧（UTF-8）
  - `0x2` 二进制帧
  - `0x8` Close
  - `0x9` Ping
  - `0xA` Pong
- **MASK**：客户端 → 服务端的帧 **必须** 掩码，服务端 → 客户端的帧 **必须不** 掩码。这是防止某些古董中间代理把 WebSocket 帧误认作 HTTP 注入攻击
- **Payload length**：7 位能表 0–125；126 表示真长度在后面 2 字节；127 表示真长度在后面 8 字节（支持 ≤ 2^63 的消息，现实里大多数库会限制几 MB）
- **Masking key**：4 字节；payload 每字节 XOR 掩码循环的对应字节
- **Payload**：真实数据

**最小帧**：2 字节帧头 + 4 字节掩码 + N 字节 payload（客户端方向）。服务端方向少 4 字节掩码。

### 2.3 消息可以分片

大消息可以拆成多帧：`[FIN=0 opcode=文本] ... [FIN=0 opcode=0] ... [FIN=1 opcode=0]`。应用层收到完整消息（所有分片）才看到一条。常规库自动处理。

**坑**：控制帧（Ping/Pong/Close）不能分片，且 payload ≤ 125 字节。

### 2.4 控制帧：Ping / Pong / Close

- **Ping**（0x9）/ **Pong**（0xA）：任何一方都能发。收到 Ping 必须尽快回 Pong，payload 原样返回。
  - 规范里 **Ping 是由协议库自动回 Pong 的**；应用代码通常只需要"定期主动发 Ping 检查对端是否活着"。
- **Close**（0x8）：payload 前 2 字节是 close code（大端），后面是可选的 UTF-8 reason。收到 Close 后应当回一个 Close 并关闭 TCP。

### 2.5 Close Code（排障必背）

| Code | 含义 | 什么时候见 |
| --- | --- | --- |
| 1000 | 正常关闭 | 业务主动 close |
| 1001 | 端点离开 | 浏览器关页面 / 服务重启 |
| 1002 | 协议错误 | 帧格式坏了 |
| 1003 | 不能接受的数据类型 | 比如只支持文本却收到二进制 |
| 1005 | 保留：没收到状态码 | 应用层看到时是"对端没带 code 就关了" |
| **1006** | **保留：异常关闭** | **TCP 断了、没收到 Close 帧。线上最常见** |
| 1007 | 数据内容不合法 | text 帧里不是合法 UTF-8 |
| 1008 | 违反策略 | 鉴权失败、业务拒绝 |
| 1009 | 消息过大 | 超过服务端限制 |
| 1010 | 客户端要求的扩展未提供 | 很少见 |
| 1011 | 服务端内部错误 | panic / uncaught |
| 1015 | 保留：TLS 握手失败 | wss 连接建不起来 |
| 4000–4999 | 应用自定义 | 业务约定，比如 4001 = token 过期 |

**经验**：线上 90% 的"异常断开"是 1006，它本身只告诉你"TCP 断了"，真正原因要去看日志/网关。

### 2.6 扩展：permessage-deflate

最常用的扩展，逐帧 / 逐消息做 deflate 压缩。开启靠握手时的 `Sec-WebSocket-Extensions`。

注意事项：

- CPU 和内存代价不低，大流量服务慎开
- 有历史 CVE（CRIME-like 攻击），现代库默认安全配置没问题
- 只压缩业务文本明显受益；压缩二进制（已经是压过的图片视频）是负优化

---

## 3. 客户端：浏览器的 WebSocket

```js
const ws = new WebSocket('wss://example.com/chat', ['chat.v1']); // 可带子协议
ws.binaryType = 'arraybuffer'; // 默认是 blob，流式处理二进制时设这个

ws.onopen = () => {
  ws.send('hello');                    // 文本
  ws.send(new Uint8Array([1, 2, 3]));  // 二进制
};

ws.onmessage = (e) => {
  // e.data 是 string 或 ArrayBuffer/Blob（根据 binaryType）
};

ws.onclose = (e) => {
  console.log('closed', e.code, e.reason, e.wasClean);
  // e.wasClean=false + code=1006 ⇒ TCP 异常断了，要在业务层重连
};

ws.onerror = (e) => {
  // 浏览器出于安全不给你错误细节，只给你一个"出错了"
  // 真要查原因，看 close 事件的 code 和服务端日志
};
```

**重连**：WebSocket 本身不帮你重连，得自己写（指数退避 + 心跳 + 消息重发队列）。业内最常见的封装：`reconnecting-websocket`、`socket.io` 等。

**心跳**：浏览器 WebSocket **不提供 API** 让你发 Ping 帧；要么库做，要么应用层用普通文本消息约定 `ping`/`pong`。服务端反之可以发 Ping，浏览器会自动回 Pong。

---

## 4. 服务端实现要点

### 4.1 Go（`nhooyr.io/websocket`）

```go
func chat(w http.ResponseWriter, r *http.Request) {
    c, err := websocket.Accept(w, r, &websocket.AcceptOptions{
        OriginPatterns: []string{"example.com"}, // 校验 Origin
        Subprotocols:   []string{"chat.v1"},
    })
    if err != nil {
        return
    }
    defer c.Close(websocket.StatusInternalError, "bye")

    ctx, cancel := context.WithCancel(r.Context())
    defer cancel()

    // 读 loop
    go func() {
        for {
            _, data, err := c.Read(ctx)
            if err != nil { cancel(); return }
            handleMessage(data)
        }
    }()

    // 定期心跳 + 业务推送
    tick := time.NewTicker(30 * time.Second)
    defer tick.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-tick.C:
            if err := c.Ping(ctx); err != nil { return }
        case msg := <-pushQueue:
            if err := c.Write(ctx, websocket.MessageText, msg); err != nil { return }
        }
    }
}
```

### 4.2 Python（FastAPI / Starlette）

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/chat")
async def chat(ws: WebSocket):
    await ws.accept(subprotocol="chat.v1")
    try:
        while True:
            msg = await ws.receive_text()
            await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect as e:
        print("closed", e.code)
```

### 4.3 Node（`ws`）

```js
import { WebSocketServer } from 'ws';
const wss = new WebSocketServer({ port: 8080 });

wss.on('connection', (ws, req) => {
  ws.isAlive = true;
  ws.on('pong', () => (ws.isAlive = true));

  ws.on('message', (data, isBinary) => ws.send(data, { binary: isBinary }));
});

// 心跳监测
setInterval(() => {
  wss.clients.forEach((ws) => {
    if (!ws.isAlive) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);
```

### 4.4 服务端侧必做清单

- ✅ **Origin 校验**：WebSocket 没有浏览器的 CORS 机制，Origin 是你唯一的防御。不校验就可能被 CSWSH（Cross-Site WebSocket Hijacking）
- ✅ **鉴权**：放在握手阶段。可以用 Cookie、URL query 里的 token、`Sec-WebSocket-Protocol` 夹带 token（后者业内常见但稍 hack）
- ✅ **心跳**：每 20–60s 发一次 Ping，N 次没收到 Pong 强制关连接
- ✅ **消息大小限制** + **频率限制**：避免被滥用
- ✅ **背压**：写队列设上限，超过就断开这个慢客户端而不是把进程内存打爆
- ✅ **水平扩展**：多实例时用 Redis pub/sub / Kafka 做广播；Load Balancer 开 sticky session（一条连接必须一直落到同一个进程）

---

## 5. 生命周期与状态机

浏览器 `WebSocket.readyState`：

- 0 `CONNECTING` 握手中
- 1 `OPEN` 可以发消息了
- 2 `CLOSING` 发了 Close，等对端回
- 3 `CLOSED` 断了

应用层面的 well-behaved 流程：

```
建 TCP → TLS 握手（wss）→ HTTP Upgrade 101
        ↓
      OPEN
        ↓ 业务消息 + 定期 Ping
        ↓
业务主动 close 或 对端 close
        ↓
互相回 Close 帧 → 关 TCP
```

**异常路径**：任一中间环节 TCP 断 → 客户端拿到 code=1006，服务端日志可能只能看到"write broken pipe"。

---

## 6. 与代理 / 网关配合

### 6.1 Nginx

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;

        proxy_read_timeout 86400;   # 长连接，读超时要拉到小时级
        proxy_send_timeout 86400;
    }
}
```

必须 HTTP/1.1；`Upgrade` 头必须透传。

### 6.2 云厂商 LB

- **AWS ALB**：支持 WebSocket，idle timeout 默认 60s，要调大；或者靠心跳续命
- **AWS NLB**：4 层直通，WebSocket 天然支持
- **GCP HTTP(S) LB**：默认支持，同样要改 backend timeout（默认 30s）
- **Cloudflare**：免费版默认就支持 WebSocket；但不会转发 Ping 帧到源站（自己在应用层 ping）

### 6.3 sticky session

应用通常把"这个连接所属的房间/频道"存在进程内存。多实例时：

- 要么加 sticky（按客户端 IP / cookie 路由同一实例）
- 要么把状态外移到 Redis / 数据库，连接可以落到任一实例

---

## 7. 排障手册（按顺序）

### 7.1 症状：握手失败，连不上

1. **HTTP status 不是 101**：
   - 401/403：鉴权问题
   - 404：路由没注册
   - 200：后端根本没识别 Upgrade 头（经典 Spring MVC 漏配）
2. **响应里没有 `Upgrade: websocket`**：代理把 Upgrade 头吃了（常见：nginx 没配 `Connection $connection_upgrade`）
3. **HTTPS 下用 `ws://`**：浏览器强制要求同源/同协议，要用 `wss://`
4. **Origin 校验失败**：服务端日志看 403

**工具**：
```bash
wscat -c wss://example.com/chat
websocat wss://example.com/chat
curl -v --include \
  --http1.1 \
  --no-buffer \
  --header "Connection: Upgrade" \
  --header "Upgrade: websocket" \
  --header "Sec-WebSocket-Version: 13" \
  --header "Sec-WebSocket-Key: test" \
  https://example.com/chat
```

DevTools → Network → 选中请求 → "Messages" 面板能看到所有帧。

### 7.2 症状：连上了，但过一会就自己断（1006）

按概率从高到低排：

1. **代理 / LB 空闲超时**：没有流量 60 秒就被踢。**加心跳**
2. **服务端写了没 flush / 崩了**：看服务端日志
3. **NAT 设备 / 家用路由器回收空闲连接**：移动网络尤其明显。心跳
4. **浏览器 tab 后台**：某些浏览器会暂停定时器，心跳没按时发就被代理踢

### 7.3 症状：消息丢了 / 乱了

WebSocket 基于 TCP，**单条连接内** 消息是可靠 + 有序的，不会丢也不会乱。如果你看到乱：

- 你有 **多条** 连接（断连重连期间）：旧连接还没死、新连接已经发了；消费端没用 sequence number
- 广播架构里消息从多个来源汇集：这是业务层问题
- 用了 permessage-deflate + 自己手搓解码：检查压缩上下文

### 7.4 症状：服务端内存涨

- **连接没被 GC**：有长住引用（map 里没删、goroutine 没退出）
- **写队列无上限**：慢客户端把服务端内存攒爆
- **每连接带上大对象**：比如整个用户资料；只存必要字段
- **Close 没清理业务状态**：onClose 里要从 room / subscription 移除

### 7.5 症状：高并发下 CPU 爆炸

- **permessage-deflate 开在了大流量节点**：考虑关掉或只对大消息压缩
- **TLS 终止在应用层**：前面加一层 nginx/ALB 做 TLS 卸载
- **广播全量遍历**：用 channel / pub-sub 分片

### 7.6 症状：从 Nginx 升级之后全挂了

经典：新版 nginx 默认某些头会带下划线过滤、或者没配 `proxy_http_version 1.1`。对照 §6.1。

### 7.7 症状：跨域建连失败

WebSocket **没有 CORS 预检**，但浏览器会自动发 `Origin` 头。服务端自己决定要不要接。"跨域连不上" 基本就是服务端 `Origin` 校验拒了。

### 7.8 调试工具箱

| 目的 | 工具 |
| --- | --- |
| 命令行客户端 | `wscat`（Node 写的）、`websocat`（Rust 写的，更强） |
| 看浏览器收发的帧 | DevTools → Network → 选择 WS 连接 → Messages |
| 抓包看真实字节 | Wireshark（直接识别 WebSocket）|
| 负载/压测 | k6、tsung、artillery |
| 广播系统压测 | 写脚本模拟万级连接（Go + goroutine 最省事）|

---

## 8. 与 HTTP/3、WebTransport 的关系

- **HTTP/2 下的 WebSocket**（RFC 8441）：握手从 CONNECT 伪方法开始，帧封在 HTTP/2 流里。浏览器支持参差，服务器支持也分库。一般不用主动开。
- **WebTransport**：HTTP/3 之上的双向消息 + 数据报，可视为 WebSocket 的"继任者"，但还在普及中。
- 结论：2026 年，生产环境仍然 `wss://` 优先。

---

## 9. 速查（贴墙版）

**握手三件套**：`Upgrade: websocket` / `Connection: Upgrade` / `Sec-WebSocket-Key` → 服务端 101 + `Sec-WebSocket-Accept`

**帧结构**：`FIN|RSV|opcode|MASK|len|[extlen]|[mask key]|payload`

**常见 opcode**：0x1 文本 / 0x2 二进制 / 0x8 Close / 0x9 Ping / 0xA Pong

**记这几个 close code**：1000 正常 / 1001 离开 / 1006 异常断 / 1008 策略拒 / 1011 服务端错

**服务端五件套**：Origin 校验 · 鉴权 · 心跳 · 消息限额 · 背压

**Nginx**：`proxy_http_version 1.1` + `Upgrade/Connection` 透传 + 长超时

**排障顺序**：

1. 握手 status 是不是 101？→ 不是 → 看鉴权 / 路由 / 代理 Upgrade 头
2. 是 101 但频繁 1006？→ 心跳加上，LB 超时拉长
3. 消息乱？→ 多连接问题；sequence number
4. 内存涨？→ 找连接关闭后的泄漏路径

**规范**：
- RFC 6455（协议本身）: https://datatracker.ietf.org/doc/html/rfc6455
- RFC 7692（permessage-deflate）: https://datatracker.ietf.org/doc/html/rfc7692
- MDN: https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API
