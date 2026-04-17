# WebRTC 协议系统学习

更新时间：2026-04-17

目标：读完你应该能——

- 清楚 WebRTC 为什么比 WebSocket 复杂这么多，它复杂在哪
- 手写一个最小的 P2P 音视频 / DataChannel Demo
- 看懂 `chrome://webrtc-internals` 和 `getStats` 的关键数据
- 线上通话质量出问题时，按顺序定位是信令、NAT、TURN、媒体传输、客户端哪一环

与 SSE / WebSocket 的选型见 [`实时通信协议选型.md`](./实时通信协议选型.md)。

---

## 1. 起点：WebRTC 解决什么问题

SSE、WebSocket 都是"通过服务器"中转消息。当你要做的是**实时音视频通话、桌面共享、游戏状态同步**时，中转服务器会带来两个致命问题：

- **延迟**：每条数据绕一圈服务端，大陆两端通话百毫秒以上
- **成本**：服务器带宽烧钱，音视频上行带宽尤其贵

**WebRTC 的核心承诺**：让两个浏览器（或浏览器 ↔ 客户端 ↔ 原生 App）之间**直接建立加密的点对点连接**，数据不经服务端。做到这件事需要解决：

1. 怎么在两个防火墙/NAT 后的设备之间建立直连（**NAT 穿透**）
2. 怎么让两端互相知道"我支持 H.264、你支持 VP8，大家共同用 VP8"（**能力协商 / SDP**）
3. 怎么加密（DTLS / SRTP）
4. 怎么在直连不成时降级为经服务器中继（**TURN**）

WebRTC 规范把这四件事全包了；但它**不管信令**——你要自己用 WS / SSE / HTTP 把"我找到了一条候选通路、这是我的 SDP"这些消息送到对端。

**直觉模型**：WebRTC 像打电话。信令是"交换号码"（告诉对方你的 IP:port 和能力），真正的语音流是"电话线"（RTP 包）。信令通道必须先通，不然电话拨不出去；电话线通了之后，信令断了也不影响通话。

**什么时候选 WebRTC**：浏览器里要做低延迟（< 500ms）、双向、音视频或大带宽数据。

**什么时候不选**：单向直播、消息类 IM、你只有几十个用户、你不想运营 TURN 服务器——其中任何一条都值得再想想。

---

## 2. 核心概念：六个词搞清楚

### 2.1 MediaStream / getUserMedia

拿到麦克风和摄像头的数据：

```js
const stream = await navigator.mediaDevices.getUserMedia({
  audio: true,
  video: { width: 1280, height: 720 },
});
```

- 只有 HTTPS（或 localhost）下才能调
- 用户必须授权
- 一个 `MediaStream` 里可以有多个 `MediaStreamTrack`（一条音轨、一条视轨）

### 2.2 RTCPeerConnection

WebRTC 的主角。**一个 PeerConnection 代表"本机和某个对端之间"的一条通道**。它负责：

- 承载多条轨（音、视、屏）
- 承载 DataChannel
- 跑 ICE、DTLS、SRTP

```js
const pc = new RTCPeerConnection({
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'turn:turn.example.com:3478', username: 'u', credential: 'p' },
  ],
});
```

### 2.3 信令（Signaling）——**规范不定义的部分**

信令就是一条带外消息通道，用来交换两类东西：

1. **SDP**（offer / answer）
2. **ICE candidate**（"我可能在这个 IP:port 接收你")

实现信令几乎永远是 WebSocket。"为什么 WebRTC 要配 WebSocket 一起学" 这个疑问现在应该解开了。

### 2.4 SDP（Session Description Protocol）

一段文本，描述"我这边准备发 / 收什么媒体"。真实 SDP 长这样（节选）：

```
v=0
o=- 4611732511636540840 2 IN IP4 127.0.0.1
s=-
t=0 0
a=group:BUNDLE 0 1
m=audio 9 UDP/TLS/RTP/SAVPF 111 103 104
c=IN IP4 0.0.0.0
a=rtcp-mux
a=ice-ufrag:F7gI
a=ice-pwd:x9cml/YzichV2+XlhiMu8g
a=fingerprint:sha-256 ...
a=setup:actpass
a=mid:0
a=sendrecv
a=rtpmap:111 opus/48000/2
m=video 9 UDP/TLS/RTP/SAVPF 96 97
...
```

平常你基本不需要读/写 SDP 原文——浏览器帮你生成。但看懂几个字段能救命（§7 排障用得上）：

- `m=` 行：一条媒体流的声明，audio / video / application（data channel）
- `a=sendrecv / sendonly / recvonly / inactive`：方向
- `a=ice-ufrag / ice-pwd`：ICE 认证
- `a=fingerprint`：DTLS 证书指纹，保证"连上的就是发 SDP 的那个人"
- `a=rtpmap`：编码 payload type 和对应编解码器
- `a=candidate`：ICE candidate（也可以分开用 `onicecandidate` 事件单独送）

### 2.5 ICE：把 NAT 穿透的复杂度塞进一个黑盒

**问题**：你在家里，对方在办公室，两边都在 NAT 后面，谁也不知道对方的公网 IP 和端口。怎么直连？

**ICE 的打法**：收集所有可能的"我的地址"，也叫 candidate，包括：

- **host**：本机网卡 IP（局域网内有效）
- **srflx**（server reflexive）：通过 STUN 服务器观察到的"我的公网 IP:port"
- **prflx**（peer reflexive）：连接过程中对方看到的我的地址
- **relay**：TURN 中继服务器分配的地址（万不得已走这条）

两端把各自的 candidate 列表丢给对方，然后**两两配对尝试**（connectivity check）。哪对先通就用哪对，优先级是 host > srflx > relay。

**STUN**：一个"公网镜子"。你发一个 UDP 包给它，它告诉你它看到的你的源 IP:port。免费的公用 STUN 到处都是（`stun:stun.l.google.com:19302`）。

**TURN**：当两端都在对称 NAT 后面（比如很多 4G/5G 移动网络）时，STUN 告诉你的公网端口每次给不同对端发包都变，对面打不进来。这时只能让**流量中转**：我发给 TURN 服务器，它转给你。TURN 烧带宽、必须自己部署（或买托管服务）。

**经验数字**：互联网上 **20–30% 的用户** 需要 TURN 才能通话。没 TURN 的 WebRTC 产品就是残废。

### 2.6 DTLS / SRTP

- **DTLS**：UDP 版的 TLS。ICE 通了之后两端跑一次 DTLS 握手，建立加密。`a=fingerprint` 就是用于校验对端证书的。
- **SRTP**：DTLS 之后，音视频走 SRTP（加密 RTP）。DataChannel 走 **SCTP over DTLS**。

你基本不需要管这层——但要知道"**ICE 建好了，但握手失败 / 连通后马上断**" 这种症状，多半是 DTLS 出了问题（比如证书过期、时钟错乱）。

---

## 3. 建立连接的完整流程

这一节很重要，建议跟着走一遍。

```
    Caller (A)                Signal Server           Callee (B)
        |                            |                    |
        | 1. new RTCPeerConnection   |                    |
        | 2. addTrack(local media)   |                    |
        | 3. createOffer() → SDP_A   |                    |
        | 4. setLocalDescription     |                    |
        | 5. offer --------------->  |-----> offer ------>|
        |                            |                    | 6. new RTCPeerConnection
        |                            |                    | 7. setRemoteDescription(SDP_A)
        |                            |                    | 8. addTrack(local media)
        |                            |                    | 9. createAnswer() → SDP_B
        |                            |                    |10. setLocalDescription
        |<------ answer ------------ |<---- answer -------|
        |11. setRemoteDescription    |                    |
        |                            |                    |
        | ice candidates 双向 trickle 互发                |
        |                            |                    |
        | ICE 连通性检查（直接 UDP，不经信令）             |
        |-------- UDP 打洞 ------------------------------>|
        |<------- DTLS 握手 ----------------------------->|
        |                                                 |
        |================== SRTP / SCTP 媒体流 ==========>|
        |<================ SRTP / SCTP 媒体流 ============|
```

信令只用到第 11 步附近；ICE / DTLS / 媒体传输全是点对点（或经 TURN）。

---

## 4. 最小可用 Demo（浏览器 ↔ 浏览器）

下面是"两个浏览器 tab 同屏对喊"最小版。信令用一个极简 WebSocket 服务代理。

```js
const signaling = new WebSocket('wss://your-signal-server/');

const pc = new RTCPeerConnection({
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
});

// 1. 把本地媒体加进去
const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
stream.getTracks().forEach(t => pc.addTrack(t, stream));

// 2. 远端轨来了就放到 <video> 里播
pc.ontrack = (e) => {
  document.getElementById('remote').srcObject = e.streams[0];
};

// 3. 本地收到 ICE candidate 就发给对面
pc.onicecandidate = (e) => {
  if (e.candidate) signaling.send(JSON.stringify({ type: 'ice', candidate: e.candidate }));
};

// 4. 监听连接状态（排障用）
pc.onconnectionstatechange = () => console.log('state:', pc.connectionState);
pc.oniceconnectionstatechange = () => console.log('ice:', pc.iceConnectionState);

// 5. 处理信令消息
signaling.onmessage = async (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.type === 'offer') {
    await pc.setRemoteDescription(msg.sdp);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    signaling.send(JSON.stringify({ type: 'answer', sdp: answer }));
  } else if (msg.type === 'answer') {
    await pc.setRemoteDescription(msg.sdp);
  } else if (msg.type === 'ice') {
    await pc.addIceCandidate(msg.candidate);
  }
};

// 6. 发起方主动 createOffer
async function call() {
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  signaling.send(JSON.stringify({ type: 'offer', sdp: offer }));
}
```

信令服务端是普通 WebSocket，只做"把谁发的消息广播到房间里其他人"。

---

## 5. DataChannel：不是音视频，也能用 WebRTC

不用媒体轨，只开一条点对点可靠（或不可靠）通道传自定义数据：

```js
const pc = new RTCPeerConnection({ iceServers: [...] });

const dc = pc.createDataChannel('game', {
  ordered: false,         // 不保序（UDP-like）
  maxRetransmits: 0,      // 不重传
});

dc.onopen = () => dc.send('hi');
dc.onmessage = (e) => console.log(e.data);
```

**DataChannel vs WebSocket**：

| 维度 | DataChannel | WebSocket |
| --- | --- | --- |
| 拓扑 | 点对点（无中心服务器中转） | 客户端 ↔ 服务器 |
| 可靠性选项 | 可靠/不可靠、有序/无序都有 | 只有可靠有序 |
| 延迟 | UDP 直连，最低 | 经服务器，有一跳 |
| 穿透复杂度 | 需要信令 + STUN/TURN | 基本就一条 wss |
| 加密 | DTLS（必选）| TLS（可选）|

典型用法：联机游戏同步、文件 P2P 传输、屏幕共享辅助通道、白板协同（大厅走 WS，白板笔画走 DataChannel）。

---

## 6. 拓扑：1:1 / Mesh / SFU / MCU

随着人数变化，架构必须换：

| 拓扑 | 用法 | 上行 | 下行 | 适用 |
| --- | --- | --- | --- | --- |
| **1:1** | 纯 P2P | 1 | 1 | 视频通话、客服 |
| **Mesh** | 每对都 P2P | N-1 条 | N-1 条 | ≤ 4 人小会议 |
| **SFU**（Selective Forwarding Unit）| 客户端上行给服务器，服务器分发 | 1 | N-1 | 会议、直播互动（主流）|
| **MCU**（Multipoint Control Unit）| 服务器解码 / 混流 / 再编码 | 1 | 1 | 客户端弱 / 兼容老设备 |

上行带宽是瓶颈：一个 720p 视频大约 1–2 Mbps。Mesh 模式下 5 人会议就要 4 路上行 = 8 Mbps，家用宽带撑不住。所以**超过 4 人几乎必上 SFU**。

开源/托管 SFU：

- **mediasoup**（Node C++，灵活，自己控制最多）
- **Janus**（C，模块化，生态老）
- **LiveKit**（Go，开箱即用，有云托管）
- **Jitsi**（Java，会议产品化最完整）
- **Pion**（Go 全家桶，写自己的 SFU 首选）

---

## 7. 排障手册（WebRTC 的核心价值区）

WebRTC 问题很多，但分层看就清楚了。按"信令 → ICE → DTLS → 媒体"的顺序排。

### 7.1 终极武器：`chrome://webrtc-internals`

Chrome / Edge 内置诊断页，在通话进行时打开，你能看到：

- 每个 PeerConnection 的所有事件（setLocalDescription、onicecandidate、...）
- **ICE candidate pair 的选中情况**：哪对在用？是 relay 吗？
- **每条流的实时统计**：bitrate、packets lost、jitter、roundTripTime
- 完整的 SDP offer / answer

第一次看这个页面会觉得信息过载，但这是线上 WebRTC 调试**必学工具**，其他一切都是次选。

Firefox：`about:webrtc`。

### 7.2 症状：根本建不起来

按 PeerConnection 状态流看是卡在哪：

| `iceConnectionState` | 含义 | 排查方向 |
| --- | --- | --- |
| `new` → 卡住 | ICE 还没开始 | 信令没把 SDP / candidate 送达；Check 对方是否 setRemoteDescription 了 |
| `checking` → `failed` | candidate 配对全失败 | **大概率缺 TURN**，或 TURN 密码错、端口被墙 |
| `connected` → `disconnected` | 连上后断了 | 网络切换、NAT 端口到期；等 ICE restart |
| `failed` | 放弃 | 重新协商或换策略 |

### 7.3 症状：ICE 直接跑到 failed

按概率排：

1. **没配 TURN** 或 TURN 不通 —— 让一端开手机热点再测，失败就是没 TURN
2. **TURN 认证错** —— 用户名密码错，或用了短时凭据（time-limited credential）过期
3. **防火墙封 UDP** —— 企业网常见；TURN 要开 **TCP 443** fallback（TURN over TLS）
4. **两端用了不同的 iceServers 配置** —— 有一端没走 TURN，对不上

### 7.4 症状：连上了但听不到声 / 看不到画面

分三步：

1. **本地采集是否拿到**：`stream.getTracks()` 看 track 数量；看本地 `<video>` 能不能预览
2. **track 是不是加进了 PeerConnection**：看 `pc.getSenders()` 有几条
3. **远端是不是没收到**：`pc.ontrack` 有没有触发；`webrtc-internals` 里 `inbound-rtp` 的 `packetsReceived` 是不是在涨

常见原因：

- SDP 方向设错：`sendonly` 意味着我只发不收
- 没 `addTrack` 就 `createOffer`：offer 里没媒体行
- Autoplay 策略：Safari / Chrome 要求 `<video>` 有 `muted` 或用户手势过
- 用了 `replaceTrack(null)` 之后忘了换回来

### 7.5 症状：画面卡、花屏

从 `getStats` 的这几个指标看：

- **packetsLost / packetsReceived**：> 5% 就算严重丢包
- **jitter**：抖动；> 30ms 音频会卡
- **roundTripTime**：RTT；> 300ms 交互明显延迟
- **qualityLimitationReason**：`bandwidth` / `cpu` 告诉你瓶颈在哪

对策：

- 丢包 → 自适应降码率；启用 FEC / NACK / RTX（WebRTC 默认都有，但 SFU 要配对）
- CPU 满 → 发送端降分辨率；接收端关闭不必要的大画面（SFU 的 simulcast + layer 选择）
- 长 RTT → 考虑就近 SFU

### 7.6 症状：getUserMedia 报错

| 错误名 | 原因 |
| --- | --- |
| `NotAllowedError` | 用户拒绝授权，或不是 HTTPS |
| `NotFoundError` | 没有匹配的设备 |
| `NotReadableError` | 设备被别的程序占着 |
| `OverconstrainedError` | constraints 太严（比如要求不支持的分辨率）|
| `TypeError` | constraints 为空 |

HTTPS 是硬门槛（localhost 例外）。

### 7.7 症状：双方同时 createOffer，协商乱了（glare）

经典 bug。解法是 **perfect negotiation pattern**（W3C 文档里的例子）：

- 每端维护一个 `polite` 布尔值（一个 true 一个 false）
- `onnegotiationneeded` 时直接 createOffer
- 收到对方 offer 时，如果自己已经发了 offer：
  - `polite` 端回滚（`setLocalDescription({ type: 'rollback' })`），接受对方 offer
  - `impolite` 端忽略对方 offer

别自己从零写，去抄 MDN 那个示例。

### 7.8 症状：上线能跑，部署到企业网全挂

企业网常见限制：

- UDP 全被封 → 强制 TURN over TCP / TLS，跑在 443
- 出站代理 → 在 `RTCConfiguration` 里配 `iceTransportPolicy: 'relay'` 让它只走 TURN（调试用；生产别写死）

### 7.9 调试工具箱

| 目的 | 工具 |
| --- | --- |
| 全局状态 | `chrome://webrtc-internals` / `about:webrtc` |
| 程序化读指标 | `pc.getStats()` 定期拉 |
| 看 SDP | webrtc-internals 里复制；或 `pc.localDescription.sdp` |
| 验证 TURN | Trickle ICE 测试页（Google 有一个在线工具） |
| 抓包 | Wireshark（SRTP 内容解不开，但可以看包到没到、丢没丢）|

---

## 8. 典型生产部署架构

```
  Client A          Client B
     \                 /
      \  信令 (WSS)  /
       \            /
        ↘          ↙
         信令服务器（房间管理、鉴权、TURN 凭据分发）
        /          \
       /            \
      /              \
     ↓                ↓
   STUN             TURN        SFU (大房间时)
  （公网镜子）       （中继）      （上行 1、下行 N）
```

生产要点：

- **TURN 凭据必须短时**：后端生成时限 TTL 的 HMAC credential，避免泄漏
- **信令服务器做鉴权**：WebRTC 本身没有身份认证概念，所有身份来自信令
- **SFU 水平扩展**：按房间路由；级联（cascade）SFU 可以支持万人会议
- **监控**：定期采集 `getStats` 汇报到后端，做 QoE 看板

---

## 9. WebRTC vs WebSocket vs SSE

| 维度 | SSE | WebSocket | WebRTC |
| --- | --- | --- | --- |
| 方向 | S → C | 双向 | 双向（P2P）|
| 是否经服务器 | 是 | 是 | 通常否（TURN 时是）|
| 传输 | HTTP chunked / HTTP/2 DATA | TCP 帧 | UDP + SRTP / SCTP |
| 延迟 | 中 | 中 | 最低 |
| 二进制支持 | ❌ | ✅ | ✅ |
| NAT 穿透 | 不需要 | 不需要 | 核心问题 |
| 内置音视频 | ❌ | ❌ | ✅ |
| 复杂度 | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 运维成本 | 低 | 低 | 高（要 STUN/TURN/SFU）|

**结合使用**的例子（常见）：

- 通话产品：**WS 做信令** + **WebRTC 传媒体**
- 直播互动：**WS 发弹幕 / 互动** + **WebRTC/HLS 拉流**
- 协同白板：**WS 广播操作** + **WebRTC DataChannel 传大文件**

---

## 10. 速查 / 规范

**连接流程 6 步**：getUserMedia → addTrack → createOffer → setLocalDesc → 信令 → setRemoteDesc（对端 answer 回来）；ICE candidate 同时 trickle 互发。

**ICE 候选类型**：host / srflx（STUN）/ prflx / relay（TURN）。

**黄金排障工具**：`chrome://webrtc-internals`。进不去其他排障没意义。

**生产必备**：STUN（免费够用）+ TURN（自己部署 or 托管）+ 信令服务器（WS）+（人多时）SFU。

**规范 / 资源**：

- W3C WebRTC: https://www.w3.org/TR/webrtc/
- MDN WebRTC API: https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API
- webrtchacks: https://webrtchacks.com/（深度文章）
- High Performance Browser Networking（Ilya Grigorik）第 18 章：免费在线
- LiveKit docs: https://docs.livekit.io/（看他们的 issue 比看规范学得快）
- coturn（最常用的 TURN 开源实现）: https://github.com/coturn/coturn
