# SSE（Server-Sent Events）协议系统学习

更新时间：2026-04-17

目标读者：想彻底搞清楚 SSE 的开发者。读完你应该能：

- 手写最小可用的 SSE 服务端和客户端
- 一眼看懂 OpenAI / Claude 流式接口的报文
- 线上出问题时，能按顺序定位到是客户端、代理、服务端哪一环

本文不是规范翻译，规范入口放在文末。

---

## 1. 起点：SSE 到底解决什么问题

HTTP 是"请求—响应"模式：客户端不问，服务端不说。很多场景需要反过来——服务端随时把新数据推给客户端，比如：

- LLM 把 token 一个个吐出来
- 实时行情、实时日志、进度条
- 通知推送

历史上的几种做法：

| 做法 | 机制 | 问题 |
| --- | --- | --- |
| 短轮询 | 客户端循环发 HTTP 请求 | 延迟高、浪费请求 |
| 长轮询（Long Polling） | 服务端 hold 住请求直到有数据才响应 | 每条消息一次完整 HTTP，头开销大 |
| WebSocket | 升级协议后变成全双工 TCP | 双向、复杂、代理/鉴权要单独处理 |
| **SSE** | 一个长连接的 HTTP 响应，服务端持续写数据 | 单向（服务端 → 客户端）、基于 HTTP，天然走 CDN / 代理 / 鉴权 |

**SSE 的直觉**：它本质就是一个永远不结束的 HTTP 响应。服务端返回 `Content-Type: text/event-stream`，然后一直往响应体里写一段段小文本，每段是一条"事件"。客户端按行解析，遇到分隔符就拿到一条消息。

所以 SSE 不是新协议，它是 HTTP 上的一种**文本帧约定 + 浏览器内置的自动重连 API**。

**什么时候选 SSE，什么时候选 WebSocket**：

- 只需要服务端推给客户端（典型：LLM 输出、进度、通知）→ SSE，简单得多
- 双向、低延迟、二进制（游戏、协作编辑）→ WebSocket
- 不确定 → 先 SSE，它能覆盖 80% 的推送需求

---

## 2. 协议本体：最小可用的报文

### 2.1 HTTP 层约定

服务端响应必须带：

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

三件事要记死：

1. `Content-Type: text/event-stream` —— 浏览器识别 SSE 的唯一依据
2. `Cache-Control: no-cache` —— 别让代理/浏览器缓存流
3. 响应体是 **chunked transfer encoding**（HTTP/1.1 下自动），HTTP/2 下是 DATA 帧

不要设置 `Content-Length`（你根本不知道要发多少），让框架走 chunked。

### 2.2 事件的线缆格式

一条"事件"由若干行组成，以**空行**（`\n\n`）结尾。字段格式是 `字段名: 值`。核心字段只有 4 个：

| 字段 | 作用 |
| --- | --- |
| `data` | 事件数据。可以出现多次，多行会被客户端用 `\n` 拼起来 |
| `event` | 事件名。客户端据此分发到不同 listener；不写则默认 `message` |
| `id` | 事件 ID。客户端记住它，断线重连时通过 `Last-Event-ID` 头带回来 |
| `retry` | 建议的重连间隔（毫秒）。纯数字，客户端可采纳 |

另外：

- 以 `:` 开头的行是**注释/心跳**，客户端直接忽略。常用来保活，例如 `: keepalive\n\n`
- 字段名和冒号之间可有一个空格，解析时 trim
- 换行允许 `\n`、`\r\n`、`\r`，但实践里统一用 `\n` 最稳

### 2.3 一个最小完整例子

服务端往响应体一字不差地写：

```
: this is a comment, clients ignore it

data: hello

data: {"token":"你"}
data: {"token":"好"}

event: done
data: [DONE]

```

它表达了 4 件事：

1. 一行注释（心跳）
2. 一条默认 `message` 事件，数据是 `hello`
3. 一条 `message` 事件，数据是两行被拼成 `{"token":"你"}\n{"token":"好"}`（注意：是客户端拿到的 `event.data` 里有 `\n`，不是两条事件）
4. 一条 `done` 事件，数据是 `[DONE]`

**最容易踩的格式坑**：事件之间必须是空行（`\n\n`）分隔。只写 `\n` 是"同一事件的下一行"，不是新事件。

### 2.4 UTF-8 必须

规范强制 UTF-8。别发 GBK、别发二进制（要传二进制就 Base64 一下塞进 `data`）。

---

## 3. 客户端：浏览器的 EventSource

浏览器原生提供 `EventSource`，它替你干了三件事：建连、按规范解析帧、断线自动重连。

```js
const es = new EventSource('/stream', { withCredentials: true });

es.onopen = () => console.log('connected');

// 默认事件（event 字段缺省时）
es.onmessage = (e) => {
  // e.data 是字符串，多行 data 会被拼起来
  // e.lastEventId 是最近一条带 id 事件的 id
  console.log('msg:', e.data);
};

// 命名事件
es.addEventListener('done', (e) => {
  console.log('done:', e.data);
  es.close(); // 显式关闭
});

es.onerror = (e) => {
  // 断线后浏览器会自动重连；这里收到的是"断线/准备重连"的通知
  // 只有 readyState === CLOSED 才是真的放弃了
};
```

浏览器会做：

- 断线后按 `retry` 建议的间隔自动重连（默认约 3 秒）
- 重连时自动带上 `Last-Event-ID: <上次收到的 id>` 请求头
- 若服务端响应不是 `text/event-stream`、或者返回 204 / 非 2xx，会终止连接

**CORS 坑**：跨域 + `withCredentials` 时，服务端除了返回 `Access-Control-Allow-Origin: <具体域名>`（不能是 `*`），还要 `Access-Control-Allow-Credentials: true`。

**手动实现**（Node、移动端、或浏览器遇 `EventSource` 不够用时）：按 2.2 的字段规则一边读一边行内解析就行。注意两点——用 streaming reader（不要等响应结束），按空行分帧。

---

## 4. 服务端：关键在"立刻冲刷"

SSE 服务端最核心的纪律：**写完一帧必须 flush，绝不能被任何层缓冲起来**。浏览器没拿到完整事件就不会触发回调。

### 4.1 Go

```go
func stream(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/event-stream")
    w.Header().Set("Cache-Control", "no-cache")
    w.Header().Set("Connection", "keep-alive")
    // 如果前面有 nginx，还要靠这行关掉 nginx 的缓冲
    w.Header().Set("X-Accel-Buffering", "no")

    flusher, ok := w.(http.Flusher)
    if !ok {
        http.Error(w, "streaming unsupported", 500)
        return
    }

    ctx := r.Context()
    ticker := time.NewTicker(15 * time.Second) // 心跳
    defer ticker.Stop()

    for i := 0; ; i++ {
        select {
        case <-ctx.Done(): // 客户端断开
            return
        case <-ticker.C:
            fmt.Fprint(w, ": ping\n\n")
            flusher.Flush()
        default:
            fmt.Fprintf(w, "id: %d\nevent: tick\ndata: %d\n\n", i, time.Now().Unix())
            flusher.Flush()
            time.Sleep(1 * time.Second)
        }
    }
}
```

要点：

- `http.Flusher` + `Flush()` 是关键，少了这一行客户端看不到任何数据
- 通过 `r.Context().Done()` 感知客户端断开，避免继续写爆
- `X-Accel-Buffering: no` 是给 nginx 看的后门，后文会讲

### 4.2 Python（FastAPI）

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio, json

app = FastAPI()

async def gen():
    try:
        for i in range(100):
            yield f"id: {i}\nevent: tick\ndata: {json.dumps({'i': i})}\n\n"
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # 客户端断开时触发，做清理
        raise

@app.get("/stream")
async def stream():
    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

FastAPI / Starlette 的 `StreamingResponse` 会自动走 chunked，不需要手动 flush，async generator yield 什么就发什么。

### 4.3 Node（Express）

```js
app.get('/stream', (req, res) => {
  res.set({
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders();

  const timer = setInterval(() => {
    res.write(`data: ${Date.now()}\n\n`);
  }, 1000);

  req.on('close', () => clearInterval(timer)); // 客户端断开
});
```

Node 里要记得 `res.flushHeaders()` 把响应头提前送出去，否则某些中间件会等首次 write 才发头。

### 4.4 服务端侧必做清单

- ✅ 头部三件套：`Content-Type`、`Cache-Control: no-cache`、`Connection: keep-alive`
- ✅ 每条事件写完调用 flush（语言有封装就确认它是 chunked 模式）
- ✅ 每 15–30 秒发一次 `: ping\n\n` 心跳，防止代理 / LB 因空闲断连
- ✅ 感知客户端断开（Go: `ctx.Done()`；Node: `req.on('close')`；Python: `CancelledError`），否则上游推送会继续烧资源
- ✅ 关闭 gzip（gzip 会缓冲直到缓冲满才输出，事件会"卡住")；或至少对 `text/event-stream` 跳过
- ✅ 幂等/可续传：带 `id`，并在接到 `Last-Event-ID` 时从该点之后开始

---

## 5. 重连与续传：`id` / `retry` / `Last-Event-ID`

这是 SSE 与"裸 chunked"的主要区别，也是线上生产的必看一节。

### 5.1 流程

1. 服务端给事件带上 `id: <offset>`
2. 浏览器收到后记住最新 id
3. 断线 → 浏览器等 `retry` 毫秒（默认 ~3s，可被服务端覆盖）→ 重发同一个 URL
4. 重连请求自动带上 `Last-Event-ID: <上次 id>`
5. 服务端从该 id **之后** 继续发

### 5.2 最小实现

服务端：

```
retry: 5000

id: 42
event: message
data: hello

```

重连请求里：

```
GET /stream HTTP/1.1
Last-Event-ID: 42
```

服务端读 `Last-Event-ID` header，从 43 开始发。

### 5.3 重要细节

- `id` 是字符串，不必是整数。用 Kafka 偏移量、Redis stream ID、数据库自增都行
- 服务端**必须**有能力从某个 id 往后重放，才真的叫"可续传"。否则 id 只是当个已读水位，重放不了——这时要明确告诉客户端无法续传（比如返回错误事件，让客户端决定丢弃还是重刷界面）
- `retry` 可以按业务调整：对话流设短点（2s），监控大屏设长点（30s），避免风暴
- 服务端主动结束时，规范做法是**正常关闭响应体**（HTTP/1.1 的 chunked 终止帧）。浏览器会把它当作断线并尝试重连——如果你不希望它重连，返回 HTTP 204 就是标准的"终止重连"信号

---

## 6. 真实世界：LLM 流式响应就是 SSE

你当前看的 `ai/openai-claude-chat-completion-接口整理.md` 里这几类接口的流式输出**全部是 SSE**：

- OpenAI `chat/completions` / `responses`（`stream: true`）
- Anthropic `messages`（`stream: true`）

区别在"用了哪些 SSE 字段"和"data 里放什么 JSON"。

### 6.1 OpenAI：只用 data + 特殊终止符

只使用 `data:`，不用 `event:` 字段。每条是一个 JSON chunk，最后用一条特殊的 `data: [DONE]` 告诉客户端流结束。

```
data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":"你"}}]}

data: {"id":"chatcmpl-abc","choices":[{"delta":{"content":"好"}}]}

data: [DONE]

```

客户端逻辑：收到 `[DONE]` 就停，否则把 `data` JSON parse 出来累积 delta。

### 6.2 Anthropic：完整使用 event + data

Anthropic 用 `event:` 字段区分不同阶段，更贴近 SSE 规范本意：

```
event: message_start
data: {"type":"message_start","message":{...}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"你"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"好"}}

event: message_stop
data: {"type":"message_stop"}

```

客户端用 `addEventListener('content_block_delta', ...)` 和 `addEventListener('message_stop', ...)` 分派。

### 6.3 两者对照

| 维度 | OpenAI | Anthropic |
| --- | --- | --- |
| 用 `event:` 字段 | ❌ 不用 | ✅ 阶段化事件 |
| 结束标志 | `data: [DONE]` | `event: message_stop` |
| id 字段 | 一般不带 | 一般不带（另有 message id 在 JSON 里） |
| 是否支持 `Last-Event-ID` 续传 | ❌ | ❌（断流要重新发请求） |

**启示**：SSE 规范定义了"线缆格式"，至于 data 里塞什么、事件怎么分阶段，完全是 API 的产品决策。读对方文档时先看"流结束靠什么"和"一条 data 代表什么单位"。

### 6.4 用 curl 直接看 LLM 的 SSE

最实用的调试手段之一：

```bash
curl -N https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o","stream":true,"messages":[{"role":"user","content":"hi"}]}'
```

`-N` 关掉 curl 的输出缓冲，否则你看到的是一坨整体输出而不是流。后面排障也会反复用到。

---

## 7. 排障手册（按顺序定位）

线上 SSE 出问题，按从客户端往服务端的路径一层层切：

### 7.1 症状：浏览器一直转圈，`onmessage` 不触发

**最常见原因：代理/网关在缓冲。** 事件被攒在 nginx 的 buffer 里，客户端当然收不到。

核查顺序：

1. **用 curl 验证服务端本身有没有问题**：
   ```bash
   curl -N -H "Accept: text/event-stream" http://your-server/stream
   ```
   看是否"一行一行吐"。如果 curl 直连能流式看到，就是中间链路的问题。
2. **nginx 这样配**：
   ```nginx
   location /stream {
       proxy_pass http://backend;
       proxy_http_version 1.1;         # 必须 1.1，chunked 才生效
       proxy_set_header Connection ""; # 不要传 "close"
       proxy_buffering off;            # 关键：关掉缓冲
       proxy_cache off;
       proxy_read_timeout 24h;         # 长连接，别让读超时踢人
       chunked_transfer_encoding on;
   }
   ```
   或者在响应头上加 `X-Accel-Buffering: no`，nginx 看到这个头就只对这个响应关缓冲。
3. **CDN**：CloudFront、Cloudflare 这些默认缓冲/缓存，配置里找到 "disable buffering for text/event-stream" 或直接跳过这个路径的 CDN。
4. **AWS ALB / GCP LB**：ALB 对 HTTP/1.1 chunked 是透传的，但**超时默认 60 秒**，长连接要调到几分钟以上。

### 7.2 症状：前几条能收到，之后就断了

- **空闲超时被踢**：LB、nginx、Cloudflare 都有"多久没数据就杀连接"。解法是**服务端每 15–30 秒发一次 `: ping\n\n` 心跳**。
- **服务端 keep-alive 超时**比业务推送间隔短。
- **浏览器在省电/后台 tab**：Chrome 会节流。无解，业务上自己兜底。

### 7.3 症状：数据到了但内容是乱的 / event 分不出来

- **忘了空行分隔**：两条事件之间必须 `\n\n`。只写 `\n` 会被并进上一条。
- **换行用了 `\r` 不统一**：尽量全 `\n`。
- **编码不是 UTF-8**：比如 Python 默认 locale、Windows 文件写 GBK。
- **开了 gzip/brotli 压缩**：压缩层会攒一段才输出，看起来就是"一批一批到"。关掉 event-stream 的压缩。

### 7.4 症状：断线后客户端拼命重连

- **retry 没设置或设太短**。用 `retry: 5000` 先压一压。
- **服务端报 500 后立刻关连接**：浏览器会按 retry 再连，再 500，形成风暴。正确做法：返回错误事件后主动 **204** 让客户端停；或服务端做指数退避写到 `retry` 字段里。
- **鉴权过期**：每次重连都 401 → 浏览器还是会再试。SSE 本身没有 401 停重连的明确规则，业务层要么让客户端显式 close，要么服务端用 204。

### 7.5 症状：客户端断了，服务端还在算 / 还在烧 token

- 没监听"客户端已断"事件。参考第 4 节各语言做法。**LLM 场景这条尤其贵**——用户关掉页面，你还在烧 OpenAI 的 token。

### 7.6 症状：续传失败 / 重连后消息丢了

- 服务端根本没实现 `Last-Event-ID` 的回放，却又发了 `id`。要么老老实实实现回放，要么就别发 `id`（减少用户期待）。
- `id` 存储位置太靠前（如内存），进程重启就丢。依赖真正的持久化来源（Kafka offset、DB 自增）。

### 7.7 症状：跨域下浏览器直接不建连

- 预检 `OPTIONS` 被服务端处理成 405。EventSource 只发 GET，不会触发预检；但如果你**带自定义头**，需要上层用 fetch + ReadableStream 自己实现（EventSource 不支持自定义头），这时才会有预检。
- `withCredentials: true` 时，CORS 响应头要是**具体域名**而非 `*`。

### 7.8 症状：HTTP/2 下行为不一样

- HTTP/2 下没有 chunked 概念，换成 DATA 帧。效果等价，但 **`X-Accel-Buffering` 在某些网关下失效**，要改用配置层面关缓冲。
- HTTP/2 / HTTP/3 允许多路复用，多条 SSE 共用一条 TCP，不占连接数（HTTP/1.1 时代浏览器一个域名最多 6 条并发，SSE 会吃掉一条）。

### 7.9 调试工具箱

| 目的 | 工具 |
| --- | --- |
| 直连服务端看原始帧 | `curl -N -v` |
| 看浏览器收到的事件 | Chrome DevTools → Network → 选中请求 → `EventStream` 面板 |
| 看 HTTP/2 帧 | `curl --http2 -v` 或 Wireshark + SSLKEYLOGFILE |
| 看代理是否缓冲 | 本地启 nginx/dumb proxy，对照直连效果 |

---

## 8. 与其他推送技术的对比（面试常考）

| 维度 | SSE | WebSocket | HTTP/2 Server Push | WebTransport |
| --- | --- | --- | --- | --- |
| 方向 | 服务端 → 客户端 | 双向 | 服务端 → 客户端 | 双向 |
| 传输 | HTTP 响应体 | 升级后 TCP 帧 | HTTP/2 PUSH_PROMISE | HTTP/3 (QUIC) |
| 是否走 HTTP 鉴权/代理 | ✅ 原生 | 部分支持 | ✅ | ✅ |
| 自动重连 | ✅ 浏览器内置 | ❌ 需自己做 | ❌ 已被多数浏览器废弃 | ❌ |
| 消息续传 | ✅ `Last-Event-ID` | ❌ | ❌ | ❌ |
| 文本/二进制 | 只文本（UTF-8） | 都行 | 都行 | 都行 |
| 复杂度 | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

**一句话结论**：只推不收，优先 SSE；需要双向就上 WebSocket；音视频或极低延迟 P2P 才轮到 WebRTC。

和 WebSocket / WebRTC 完整对比和选型决策树，见 [`实时通信协议选型.md`](./实时通信协议选型.md)。

---

## 9. 规范与参考

- HTML Living Standard - Server-sent events：https://html.spec.whatwg.org/multipage/server-sent-events.html
- MDN - EventSource：https://developer.mozilla.org/en-US/docs/Web/API/EventSource
- MDN - Using server-sent events：https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- OpenAI streaming：https://platform.openai.com/docs/api-reference/streaming
- Anthropic streaming：https://docs.anthropic.com/en/api/messages-streaming
- nginx `proxy_buffering` 与 `X-Accel-Buffering`：https://nginx.org/en/docs/http/ngx_http_proxy_module.html

## 10. 一页速查

最后把全文压成一张能贴墙上的速查：

**格式**

- 事件之间用空行 `\n\n` 分隔；`data:` / `event:` / `id:` / `retry:` / `:comment`
- `data:` 可多次，多行被客户端拼成一个带 `\n` 的字符串
- UTF-8 only

**头**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**服务端必做**

1. 每帧 flush
2. 每 15–30s 心跳 `: ping\n\n`
3. 监听客户端断开，及时停止上游（LLM 省 token！）
4. 关闭 `text/event-stream` 的 gzip

**代理必做**

- nginx：`proxy_buffering off`、`proxy_http_version 1.1`、`proxy_read_timeout` 拉长
- LB：空闲超时调大到分钟级

**排障顺序**

1. `curl -N` 直连服务端 → 能不能流？
2. 能 → 查代理/CDN/LB 的缓冲与超时
3. 不能 → 查服务端是否 flush、gzip 是否开了
4. 再不行 → DevTools EventStream 面板看实际收到的帧
