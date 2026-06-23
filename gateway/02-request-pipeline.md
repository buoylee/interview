# 02 · 請求管線 / Filter Chain:網關的靈魂 🔬

> 一句話:**網關不是一坨 if-else,它是一條「按序流過的管線」。** 一個請求進來,依次穿過 路由匹配 → 認證 → 授權 → 限流 → 改寫 → 轉發後端 → 回應過濾 → 埋點,每一段是一個可插拔的 filter。這是整個 track 的骨架——後面 ch03~07 講的每件事,本質都是「往這條管線的某一段塞一個 filter」。

如果只能記住網關的一件事,就記這條管線。面試問「一個請求進網關到打到後端經過哪些階段」,答的就是它。

---

## 1. 🔬 標準管線:請求向下穿、回應向上回

把網關想成一串同心的「關卡」。請求**向下**逐層穿過(每關可以攔截/改寫/放行),打到後端;回應**向上**逐層穿回(每關可以再改寫/記錄)。

```
        ┌───────────────────────── 請求進入 ─────────────────────────┐
        ▼
  ① 接收 & 解析     收完 HTTP、解出 method/path/header(L7,見 ch01 §5)
        │
  ② 路由匹配        按 host/path/header 找到目標 route + upstream(ch03)
        │
  ③ 認證 authn      你是誰?驗 JWT / API Key / mTLS(ch04)
        │
  ④ 授權 authz      你能不能訪問這個資源?RBAC/ABAC(ch04)
        │
  ⑤ 限流 / 配額     這個用戶/路由還有額度嗎?超了就擋(ch05)
        │
  ⑥ 請求改寫        加減 header、改 path、注入 traceId(ch06/ch07)
        │
  ⑦ 轉發 upstream   經連線池打到後端;含超時/重試/熔斷(ch01/ch03/ch05)
        │
        ▼  ────────────── 後端處理 ──────────────
        ▲
  ⑧ 回應過濾        改回應 header/body、脫敏、壓縮(ch06)
        │
  ⑨ 埋點 / 日誌     記 latency/status/consumer,出 metrics & trace(ch07)
        ▲
        └───────────────────────── 回應返回 ─────────────────────────┘
```

這就是「filter chain / 中間件鏈」模型。**每一關都能做三件事之一**:放行(交給下一關)、改寫後放行、或**短路返回**(直接給客戶端一個回應,後面的關都不跑——見 §3)。

> **給 Java/Go 背景的橋接**:這跟你寫過的 **Servlet `Filter` 鏈**、Spring `HandlerInterceptor`、Go 的 `http.Handler` middleware(`func(next) handler`)是**完全同一個模式**——「在到達業務邏輯前後,串一排可插拔的橫切處理」。網關只是把這條鏈**從進程內搬到了獨立的網路元件**,讓所有後端服務共用一套。你已經會了,只是換了部署位置。

---

## 2. 🔬 同一套抽象,四種長相

市面上的網關看起來各家一套術語,但骨子裡都是上面這條管線。把它們擺一起你就不會被名詞嚇到:

| 網關 | 管線怎麼表達 | 階段命名 |
|---|---|---|
| **Envoy** | **HTTP filter chain**:一串 `http_filters`,請求依序過(`jwt_authn` → `ratelimit` → `router`) | filter 按配置順序;`router` filter 在最後負責轉發 |
| **Kong** | **plugin + phases**:每個 plugin 掛在某個階段 | `certificate` → `rewrite` → `access`(鑑權/限流多在這)→ `header_filter` → `body_filter` → `log` |
| **APISIX** | **plugin + phases**(類 OpenResty 階段) | `rewrite` → `access` → `header_filter` → `body_filter` → `log` |
| **Spring Cloud Gateway** | **`GlobalFilter` / `GatewayFilter`**,用 `Ordered` 排序 | `pre` 段(轉發前)與 `post` 段(回應後),靠 filter 的 order 值決定先後 |

**看穿本質**:不管叫 filter、plugin 還是 GatewayFilter,都是「**按序執行、可短路、有 pre/post 兩段**」的同一個東西。Envoy 的 `router` filter、Kong 的 upstream proxy、SCG 的轉發,都對應管線圖裡的 ⑦——**轉發永遠在請求段的最後**,因為它前面的關全是「決定要不要、怎麼打後端」。

> Kong/APISIX 把階段拆成 `header_filter`(只改頭,還沒拿到 body)和 `body_filter`(改 body)是有道理的:很多場景(改個 header、加個 CORS)根本不需要緩衝整個 body,在 `header_filter` 階段就能流式處理、省記憶體。這呼應 ch06 的「流式 vs 緩衝」。

---

## 3. 🔬 順序為什麼要緊:限流放鑑權「前」還是「後」?

管線的威力在於**順序可調**,而順序直接決定系統行為。最經典的面試題就是這個:

**方案 A:限流在鑑權「前」(④之前先⑤)**
- 好處:匿名洪水流量在最便宜的一關就被擋掉,**不用付出驗 JWT/查 introspection 的 CPU**。
- 壞處:只能按 **IP / 全域** 限流(這時還不知道「你是誰」),按用戶/租戶的配額做不了;且惡意用戶可以換 IP 繞過。

**方案 B:限流在鑑權「後」(④之後再⑤)**
- 好處:已經認出身份,可以按 **用戶 / API Key / 租戶** 做精細配額(「金牌客戶 1000/s,免費版 10/s」)。
- 壞處:**鑑權這關自己會被打**——攻擊者狂發無效 token,你每個都得驗,鑑權成了被攻擊面。

**生產上常見的是「兩段限流」**:邊緣先一道**粗粒度 IP 限流 / 連線限速**(擋住明顯的洪水,保護鑑權關),鑑權之後再一道**細粒度按用戶配額**。一句話答法:**看你要保護什麼——保護 CPU 就把粗限流前置,做精細配額就把它放鑑權後;大流量系統兩道都要。**

這就是「管線是網關靈魂」的具體意義:**同樣幾個 filter,擺放順序不同,系統的安全性與成本就不同。**

---

## 4. 🔬 短路、提前返回、與 pre/post 兩段

- **短路(short-circuit)**:任何一關都能**不再往下傳**,直接生成回應返回。鑑權失敗 → 直接 `401`,後面的限流/路由/後端**完全不跑**。限流超額 → 直接 `429`。這是管線「省資源」的關鍵:越早擋住,浪費越少(也是 §3 把限流前置的理由)。
- **pre / post 兩段**:同一個 filter 通常能在「轉發前」和「回應後」各掛一段邏輯。例:可觀測 filter 在 pre 段記下開始時間、注入 traceId,在 post 段算出 latency、記訪問日誌(ch07)。SCG 的 `filter(exchange, chain)` 裡 `chain.filter(...).then(...)` 的 `then` 就是 post 段。
- **改寫掛在哪兩段**:請求改寫(加內部 header、改 path、脫掉外部不該傳的頭)掛在 ⑥(轉發前);回應改寫(脫敏、加 CORS 頭、壓縮)掛在 ⑧(回應後)。

---

## 本章小結

- 網關 = **一條按序流過的管線**:接收→路由→認證→授權→限流→改寫→轉發→回應過濾→埋點。
- Envoy filter chain / Kong & APISIX plugin phases / SCG `GlobalFilter` 是**同一個模式**的不同命名:按序、可短路、有 pre/post。**轉發永遠在請求段最後。**
- **順序決定行為**:限流放鑑權前(省 CPU、只能粗粒度)還是後(精細配額、但鑑權被打)是經典取捨;大流量常兩段都做。
- **短路**讓越早的關擋住越省資源;**pre/post** 讓同一 filter 跨越轉發前後(可觀測就靠這個算 latency)。
- 它跟你熟的 Servlet Filter / Go middleware 是同一個東西,只是搬到了網路邊緣。

## 章末問答(複習自檢,答案要點都在前面正文)

1. 畫出網關的標準請求管線(至少 7 段),並說明「請求向下穿、回應向上回」是什麼意思。
2. Envoy 的 filter chain、Kong 的 plugin phases、Spring Cloud Gateway 的 GlobalFilter,共同的抽象是什麼?「轉發」這一步為什麼總在請求段的最後?
3. 限流放在鑑權前和放在鑑權後,各有什麼好處與代價?為什麼大流量系統常常兩道都要?
4. 什麼是 filter 的「短路」?舉一個它省下資源的例子。
5. 一個「算請求延遲並寫訪問日誌」的可觀測 filter,為什麼需要 pre/post 兩段?
