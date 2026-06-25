# 04 · 長連接 LB ②:對 client / 南北向 —— 你不控 client 時怎麼辦

> 🔬 上一章的長連接修法,全建立在「**你控兩端、能改 client**」之上。這章 client 變成**瀏覽器 / 手機 App**(WebSocket、SSE、手機長連 gRPC)——你**改不動它**。逼不動 client 重連、配不了它的 `round_robin`、推不了新版本給它。所以南北向是**另一套完全不同的工具箱**。

---

## Part A · 為什麼南北向要分開講

東西向和南北向的差別,一句話:**控制權**。

| | 東西向(`03`) | 南北向(這章) |
|---|---|---|
| client 是誰 | 你自家的服務 | **瀏覽器 / 手機 / 第三方**,你不控 |
| 能改 client 行為嗎 | 能(設 round_robin、接 xDS) | **不能**(頂多靠你自己寫的前端 / App 重連邏輯) |
| 能逼它重連嗎 | 能(server `MaxConnectionAge` → client 自動重連) | **逼了它不一定乖乖回來**,還可能一窩蜂回來 |
| 連接性質 | gRPC / DB 池,多為無狀態複用 | **常帶會話狀態**(WebSocket 連上後綁了用戶 / 房間) |
| LB 在哪 | kube-proxy / 客戶端 / sidecar | **雲 L4 LB + L7 Ingress/Gateway**(集群入口) |

南北向長連接的典型:**聊天 / 推送(WebSocket)**、**伺服器推流(SSE)**、**手機長連**。它們的麻煩不在「請求怎麼分散」(每個 client 一條連接,連上哪個 pod 差別不大),而在 **連接的生命週期**:建立時往哪放、發版 / 縮容時怎麼不斷、斷了怎麼優雅回來。

---

## Part B · 南北向長連接的五個真問題 🔬

### 1. LB 層換人:雲 L4 LB + L7 入口,小心 idle timeout

南北向流量從集群外進來,先過**雲廠商的負載均衡器**(NLB / ALB),再進 **Ingress / Gateway**。兩個坑:

- **雲 LB 默認 idle timeout 會砍長連接**:NLB / ALB 對「一段時間沒有字節流動」的連接會默默斷開(默認常見 60s~350s)。WebSocket 空閒時就被砍 → client 莫名其妙掉線。**解法:調大 idle timeout + 應用層心跳 / keepalive**(定期發 ping 幀,讓連接「看起來活著」)。
- **要走 L7 才認得 WebSocket / SSE 升級**:WebSocket 靠 HTTP `Upgrade` 握手,Ingress 控制器要開 WebSocket 支持(大多默認支持,但超時 / 緩衝要單獨配)。SSE 是長住的 HTTP 響應,**反向代理的響應緩衝要關掉**(否則代理憋著不下發,SSE 就「不流」了)。

### 2. 逼不動 client 重解析 → 把主動權交給「優雅關閉 + client 重連」

東西向能靠 server `MaxConnectionAge` 逼 client 重連、重新均衡。南北向**逼不動**瀏覽器去重新解析 DNS。能做的是反過來設計:

- **server 端要主動、優雅地關**(發版 / 縮容時 close 連接,而不是硬斷 TCP)。
- **client 端(你自己寫的前端 / App)要有重連邏輯** —— 斷了自動重連。**這是你唯一能控的 client 行為,必須一開始就寫進去。**

### 3. 縮容 / 發版的「驚群」(thundering herd)

南北向最毒的坑:你滾動發布,**一個 pod 上幾萬條 WebSocket 同時被斷** → 幾萬個 client **同一秒一起重連** → 流量尖峰打爆剩下的 pod / 後端,甚至雪崩。

> 解法:**重連要加抖動(jitter)+ 指數退避**。client 不要「斷了立刻重連」,而是「隨機等 0~N 秒再重連」,把尖峰攤平。server 端滾動也要**慢**(一次只滾一個 pod、給足排空時間),別同時掀翻多個 pod。

### 4. sticky(會話保持)和均衡的衝突

WebSocket 連上後常**綁了狀態**(這條連接屬於用戶 X、在房間 Y)。如果狀態存在 pod 本地內存,你就需要 **session affinity** 讓同一 client 回同一 pod —— 但 affinity 本身**和均衡是衝突的**(綁死了就不能再平衡),而且 pod 一掛狀態就沒了。

> 更好的架構:**讓 pod 無狀態**,把會話狀態 / 路由放到外部(Redis 存會話、用 pub/sub 廣播消息),這樣連哪個 pod 都行,發版重連也不丟狀態。能不 sticky 就不 sticky —— sticky 是退而求其次。

### 5. 發版時的連接排空(graceful drain)

存量長連接在 pod 下線時要**排空**,不能一刀切:

- pod 收到 SIGTERM → **先從 Service Endpoints 摘除**(不再接新連接)→ **給存量連接時間優雅收尾 / 通知 client 重連** → 再退出。
- 配 `preStop` hook(常見一個 sleep,等 Endpoints 摘除生效)+ 調大 `terminationGracePeriodSeconds`。
- 這套「優雅下線」的機制細節(SIGTERM 時序、preStop、為什麼要先摘 Endpoints 再停)本 repo 有專章:**`distribution/zero-downtime-release/05-connection-lifecycle`**,這裡不重講。

### WebSocket vs SSE vs long-poll(選型一句話)

| 方式 | 方向 | 一句話 |
|---|---|---|
| **WebSocket** | 雙向 | 真雙工,聊天 / 協同;但有狀態、發版最難搞 |
| **SSE** | 單向(server→client)| 推送 / 流式輸出(LLM 打字機),純 HTTP、過代理簡單;注意關代理緩衝 |
| **long-poll** | 模擬 | 最兼容、最笨;高頻下浪費連接,能用 SSE/WS 就別用 |

---

## Part C · 收口:南北向長連接的設計順序

```
1. 能不長連就不長連          ── SSE 夠用就別上 WebSocket
2. 能無狀態就無狀態          ── 狀態進 Redis,別綁 pod(躲開 sticky)
3. client 端先寫好重連+抖動  ── 你唯一能控的 client 行為
4. 入口調 idle timeout + 心跳 ── 別被雲 LB 默默砍
5. 發版慢滾 + 連接排空        ── preStop / 先摘 Endpoints(→ zero-downtime-release/05)
```

> 對照記憶:**東西向是「怎麼把請求分散到多 pod」(你能改 client);南北向是「怎麼讓有狀態的長連接在你不控 client 的前提下,活得久、斷得優雅、回得平穩」。** 兩章合起來才是完整的「k8s 長連接」答案。

---

## 交叉引用

- **連接排空 / 優雅下線機制(SIGTERM / preStop / 先摘 Endpoints)→ `distribution/zero-downtime-release/05-connection-lifecycle`**
- **東西向長連接(你控兩端)→ `03`**
- **Ingress / Gateway API / L7 入口 → `cloud-native-landscape/03`、`gateway/`**
- **邊緣 LB 算法 / 會話保持 → `gateway/03-routing-and-load-balancing`**

---

## 本章小結

- **南北向 ≠ 東西向**:client 是瀏覽器 / 手機,**你不控、改不動、逼不動**;連接常**帶會話狀態**;LB 在**雲 L4 + L7 入口**。
- **五個真問題**:① 雲 LB idle timeout 砍連接(調 timeout + 心跳)② 逼不動 client 重連(靠 server 優雅關 + client 重連邏輯)③ 發版驚群(重連抖動 + 指數退避 + 慢滾)④ sticky 和均衡衝突(優先做無狀態,狀態進 Redis)⑤ 連接排空(preStop + 先摘 Endpoints → zero-downtime-release/05)。
- **設計順序**:能不長連就不長連、能無狀態就無狀態、client 先寫重連抖動、入口調 timeout、發版慢滾排空。
- **下一章**:跳出 Java,看 Go/Python **怎麼和 k8s 整合** —— 沒有全家桶,靠講契約。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 南北向和東西向長連接最根本的差別是什麼?(一個詞)
2. 為什麼雲 LB 會默默砍掉你的 WebSocket?兩個對策是什麼?
3. SSE 過反向代理時為什麼可能「不流」?怎麼修?
4. 「驚群 / thundering herd」在發版時怎麼發生?重連抖動 + 指數退避怎麼救?
5. WebSocket 的 sticky 需求從哪來?為什麼說「能不 sticky 就不 sticky」?無狀態化怎麼做?
6. 連接排空為什麼要「先摘 Endpoints 再停」?(細節去哪章查)
7. WebSocket / SSE / long-poll 各適合什麼場景?
8. 為什麼東西向的 `MaxConnectionAge` 招式在南北向用不上?
9. 南北向長連接的「設計順序」五步是什麼?
10. **綜合題**:面試官說「我們聊天服務用 WebSocket,每次發版用戶就大面積掉線還引發雪崩」——從 sticky/狀態、連接排空、重連驚群三個角度給出完整改造方案。
