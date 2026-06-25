# 12 · 選型與「何時從 Nginx 畢業」

> 一句話:這是 track 的收口章——不是要你放棄 Nginx,而是讓你清楚知道它的邊界在哪裡、什麼時候繼續用、什麼時候該換別的、換的時候怎麼做不翻車。

學完前 11 章,你已經能用 Nginx 搭出一個生產級接入層:location 匹配(ch01)、反代與 upstream(ch04)、proxy_cache(ch05)、limit_req(ch06)、TLS 憑證管理(ch07)、零停機 reload(ch08)、性能調優(ch09)、可觀測除錯(ch10)。這一章做兩件事:**明確 Nginx 的真實邊界**,以及**給你一張可複用的生產 checklist**,讓你帶著這份工具用到它真正撐不住的那天,再有信心換掉它。

> **本章不重複完整的跨網關選型。** Nginx / Envoy / Kong / APISIX / Spring Cloud Gateway / 雲託管的六維對照表、絞殺者遷移模式、上線生產清單的通用版本,都已在 ↪ [`gateway/11-selection-and-production-playbook.md`](../gateway/11-selection-and-production-playbook.md) 覆蓋完整。本章只從 **「Nginx 視角」** 切入:它能做什麼、不能做什麼、何時該走。

---

## 1. Nginx 在選型地圖裡的座標

### 1.1 對照表:五個近鄰的強項與適用場景

| | **Nginx** | **Caddy** | **Envoy** | **HAProxy** | **APISIX** | **雲託管(ALB/API Gateway)** |
|---|---|---|---|---|---|---|
| **定位** | 通用反向代理 / Web Server | 自動 HTTPS 的輕量代理 | 雲原生資料面 | 極穩定 L4/L7 LB | 雲原生 API 網關 | 全託管 HTTP/API 層 |
| **配置模型** | 靜態設定檔 + reload | Caddyfile(宣告式,極簡) | xDS API 動態下發 | 靜態設定 + `reload`/`SIGUSR2` | etcd watch 動態下發 | 廠商控制台 / SDK |
| **TLS 管理** | 手動 + certbot/acme.sh | **自動申請 + 續期(內建 ACME)** | 憑證由控制面推送 | 手動 | 手動 / ACME 模組 | **全自動(廠商管)** |
| **動態配置** | 弱(每次改設定要 reload) | 支援 API 動態修改 | **強(不重啟推路由/限流)** | 弱 | **強(管理 API 即時生效)** | 廠商控制台即時 |
| **插件/擴展** | 少(需 OpenResty/Lua) | 插件不多,官方優先 | WASM / C++ filter | 極少 | **豐富(Lua 插件市場)** | 廠商功能 |
| **可觀測** | 基本(log + stub_status) | 基本 | **精細(OpenTelemetry 內建)** | 基本 | 中等(插件接 Prometheus) | 廠商監控 |
| **L4 / TCP 代理** | 基本(`stream` 模組) | 不支援 | 支援 | **強項,L4 是主場** | 支援 | 看廠商 |
| **性能** | 高 | 高 | 高 | 高(以 L4 LB 著稱) | 高(OpenResty 底) | 看廠商,吞吐受限 |
| **運維成本** | 低 | **最低(自動 TLS)** | 中高(需控制面) | 低 | 中(需 etcd/管理 API) | **最低(不用自運維)** |
| **逃生票** | ✅ 自托管 | ✅ | ✅ | ✅ | ✅ | ❌ 廠商鎖定 |

**一句話定位**:

- **Caddy**:只想省 TLS 運維、設定寫得越少越好——換它。
- **Envoy**:k8s 環境、service mesh 資料面、需要不重啟動態路由——換它(或讓 Istio/Linkerd 幫你管)。
- **HAProxy**:TCP/L4 負載均衡是主場景、或需要極致穩定性與最細粒度的健康檢查——換它。
- **APISIX**:API 網關場景、需要動態限流/鑑權/插件市場、團隊不綁 Java——換它。
- **雲託管**:在雲上且不想自運維、能接受廠商鎖定——用它,並保留一份遷回開源的 B 計畫。

---

## 2. 🔬 何時該從 Nginx「畢業」——實質判據,不是套話

「畢業」不是貶義——是用對工具的時候了。Nginx 的根本模型是 **「靜態設定檔 + reload 才生效」**,這個設計對多數場景既簡單又可靠。但它有幾個硬邊界:

### 邊界一:需要不重啟的動態路由/限流變更

**Nginx 的現實**:每次改一條 `location`、調一個 `limit_req` 閾值,你都要:

1. 改 `nginx.conf`(可能在設定管理系統裡)
2. 跑 `nginx -t` 校驗
3. 觸發 `nginx -s reload`

Reload 本身很安全(ch08 講透了:listen socket 由 master 持有、舊 worker 把在途請求處理完才退),但**操作鏈長**。在 k8s 環境裡,Pod IP 每次重建都變,如果 upstream 的 IP 清單要跟著改,你要麼接 ingress-nginx 讓它幫你 watch + reload(ch11),要麼接 coredns 靠 DNS 解析,要麼……換掉 Nginx。

**畢業判據**:路由規則每天修改超過幾次、或後端拓撲頻繁變動且你需要秒級生效 → 換 **Envoy**(xDS API push)或 **APISIX**(etcd watch + 管理 API)。

### 邊界二:需要服務發現整合

Nginx 沒有內建的服務發現。它不認識 Consul、Kubernetes Service、Eureka。你能做到的只有:

- 用 `upstream` 裡的 IP 清單 + 被動健康檢查(`max_fails`/`fail_timeout`,ch04)
- 讓外部工具(confd、consul-template、ingress controller)監聽服務發現、更新設定、觸發 reload

這個「外部工具膠水層」能工作,但每次拓撲變化有幾秒到幾十秒延遲,且又引入了一個需要維護的組件。

**畢業判據**:微服務環境下後端實例數時常在變(容器彈性擴縮、滾動發布)、且你希望 0 延遲感知拓撲變化 → 換 **Envoy**(Istio/控制面整合)或 **APISIX**。

### 邊界三:需要豐富的插件生態——開箱即用

你想要:
- 按 API key / JWT 鑑權,開箱即用
- 請求轉換(改 body、添加字段)
- OpenID Connect / OAuth2 流程
- 熔斷器(circuit breaker)
- 請求簽名、IP 白名單管理 UI

純 Nginx 能做這些,但都要靠 Lua(OpenResty,ch11)自己寫或找第三方模組。門檻不低、維護成本不低。

**畢業判據**:需要 3 個以上非基礎的插件功能、且不想自己用 Lua 實現 → 換 **APISIX** 或 **Kong**。

### 邊界四:需要精細的可觀測性

Nginx 的可觀測能力(ch10 講透):

- access log(你要自己設計 `log_format`)
- `stub_status`(Active/reading/writing/waiting 四個數字)
- 接 nginx-prometheus-exporter 拿到更多指標

它沒有:
- 原生 OpenTelemetry trace 注入(需要 OpenResty 的 opentelemetry-lua 模組)
- per-route 的 RED 指標(Rate/Errors/Duration)開箱即用
- 動態 sampling 控制

**畢業判據**:你的可觀測基礎設施是 OpenTelemetry 主軸、需要端到端 trace 在網關層零配置注入,或需要 per-route 精細指標 → 換 **Envoy**(OTel 內建)。

### 畢業決策速查

```
你遇到的場景                                       建議
─────────────────────────────────────────────────────────────────
reload 管理成本可接受、設定變化不頻繁               → 繼續用 Nginx(你還沒到邊界)
只想省掉 certbot + cron + 手動憑證管理              → 換 Caddy
後端 IP 頻繁變、服務發現要秒級感知                 → 換 Envoy 或 APISIX
需要 3 個以上開箱即用插件(鑑權/熔斷/轉換)         → 換 APISIX 或 Kong
k8s 環境已用 Istio / Linkerd(mesh 管流量)          → 換 Envoy(mesh 資料面)
OTel trace 要在網關層零配置注入                     → 換 Envoy
L4/TCP 負載均衡是主場景                             → 換 HAProxy
在雲上、不想自運維基礎設施                          → 雲 ALB/API Gateway(留逃生票)
```

> **沒到邊界就別換**。遷移有成本、新工具有新的學習曲線與運維負擔。Nginx 的「設定即文件、reload 可審計」在穩定的生產環境是優點,不是缺點。

---

## 3. 生產 Checklist:從 Nginx track 各章蒸餾

把前面 11 章「你以後會忘記但出事了最後悔沒做」的點收口成一張清單。

### 3.1 設定校驗與版本升級

- [ ] **每次改設定前先 `nginx -t`**,校驗語法與邏輯,設定錯 reload 會讓新 worker 起不來而舊 worker 繼續跑——不會爆炸但改動也沒生效(ch08)。
- [ ] **灰度 reload**:多台實例時,先 reload 一台,觀察 error_log + access_log 無 5xx 上升,再推其他台。
- [ ] **版本升級用熱升級**:`USR2` 起新 master + 新 worker、`WINCH` 收舊 worker、`QUIT` 收舊 master;出錯可把舊 master 拉回(ch08)。容器環境用滾動更新替代。
- [ ] **設定納入版本控制**:`nginx.conf` 進 git,不要直接在伺服器上改。

### 3.2 監控接入

- [ ] **生產 log_format 包含四個核心欄位**:`$request_time`(總耗時)、`$upstream_response_time`(後端耗時)、`$status`、`$upstream_status`——兩耗時相減定位網關自身延遲 vs 後端延遲(ch10)。
- [ ] **`$upstream_cache_status` 加進 log** 或回應頭,即時觀察快取命中率(ch05 / ch10)。
- [ ] **開 `stub_status`**,接 nginx-prometheus-exporter,把 Active/waiting 指標接入告警(ch10)。
- [ ] **設 `error_log warn`** 在生產,排查問題時臨時改 `debug`(需 `--with-debug` 編譯)(ch10)。

### 3.3 限流與超時兜底

- [ ] **超時三件套都設**:`proxy_connect_timeout`(連後端的等待)/ `proxy_send_timeout`(送請求到後端的最大等待)/ `proxy_read_timeout`(等後端回應的最大等待);沒有一個超時設成「無限等」(ch04)。
- [ ] **`limit_req` 狀態碼改成 429**:默認 503 容易和「後端全掛」混淆,`limit_req_status 429;` 語義清楚(ch06)。
- [ ] **跨節點配額提醒**:`limit_req` 的共享記憶體 zone 只在同節點 worker 之間共享,跨節點不共享——多台 Nginx 的全域速率配額必須外移到 Redis / 網關層(ch06)。

### 3.4 TLS 自動續期

- [ ] **certbot 或 acme.sh 設 cron / systemd timer 自動續期**,別等憑證快過期再手動(ch07)。
- [ ] **測試自動續期**:用 `certbot renew --dry-run` 提前驗證(ch07)。
- [ ] **HSTS 注意 `add_header` 繼承陷阱**:在 `location` 層加了任何 `add_header`,父層 HSTS header 會消失——需在每個設了 `add_header` 的 location 把 HSTS 也補進去(ch01 / ch07)。
- [ ] **OCSP stapling 開啟**:`ssl_stapling on; ssl_stapling_verify on;` 省掉客戶端一次 CA 查詢往返(ch07)。

### 3.5 快取配置

- [ ] **`proxy_cache_lock on`**:防同一 key 並發 miss 同時打後端(快取擊穿)(ch05)。
- [ ] **`proxy_cache_use_stale error timeout updating`**:後端掛了或慢了,先回舊快取給客戶端,不要直接 502(ch05)。
- [ ] **`proxy_cache_key` 設計**:確認 key 裡不含敏感資訊、不含不應區分快取的欄位,防快取污染(ch05)。

---

## 4. 常見故障速查(回扣 ch10 狀態碼表)

ch10 已有完整的「症狀 → 定位 → 根因」playbook,這裡只列「最容易搞混」的幾組,作為 ch10 的快速索引:

| 狀態碼 | 誰造成的 | 第一步查什麼 | 回扣 |
|---|---|---|---|
| **499** | **客戶端** 在 Nginx 回應前主動斷開 | 客戶端超時設定、用戶取消操作 | ch10 |
| **502 Bad Gateway** | **後端** 拒連 / 連不上 / 回了非法 HTTP | 後端進程是否在跑、埠是否正確、upstream 健康檢查狀態 | ch04 / ch10 |
| **504 Gateway Timeout** | **後端** 回應慢,超過 `proxy_read_timeout` | 後端慢查詢、GC 暫停、下游依賴慢 | ch04 / ch10 |
| **503** | **Nginx 自身** 限流或 upstream 全部熔斷 | `limit_req` / `limit_conn` 日誌、upstream 所有 server 的 max_fails 狀態 | ch06 / ch10 |

**最常混淆的兩對**:

- **502 vs 504**:502 = 後端根本沒回(連線失敗/協議錯誤),504 = 後端連上了但回得太慢。查日誌裡的 `$upstream_response_time`——502 時這個值是 `-`(沒拿到),504 時這個值是一個很大的數(等滿了 timeout)。
- **499 vs 504**:499 是客戶端先放棄,504 是後端先超時。客戶端設定的超時 < Nginx 的 `proxy_read_timeout` 時常見 499;反過來才是 504。

**連線耗盡的早期信號**:

```
error_log 出現 "worker_connections are not enough"
stub_status 的 active 長期接近 worker_connections 上限
```

確認後調整 `worker_connections` + `worker_rlimit_nofile`,並同步確認 OS 的 `ulimit -n`(三者要一起調,見 ch09)。

---

## 5. 面試高頻點

**「什麼時候不該再用 Nginx?」**

> 四個邊界:1. 需要**不重啟動態路由/限流**——Nginx 的 reload 模型在頻繁改動時管理成本高,換 Envoy(xDS push)或 APISIX(管理 API)。2. 需要**服務發現無縫整合**——後端 IP 頻繁變動又要秒級感知,換 Envoy/APISIX。3. 需要**開箱即用插件**——鑑權/熔斷/請求轉換不想自己寫 Lua,換 APISIX/Kong。4. 需要**精細可觀測**——OTel trace 要零配置注入,換 Envoy。如果只是想省 TLS 運維,換 Caddy 就夠了。

**白板話術補充**——面試官問「你們的 Nginx 什麼時候遷到 APISIX 的,為什麼?」

> 「我們在後端服務容器化之後,upstream IP 開始頻繁變——每次 Pod 重建都要改 nginx.conf 然後 reload,配上灰度流程大概 5–10 分鐘才能生效。加上我們開始需要按 API key 做鑑權、按用戶等級做差異限流,這兩件事用純 Nginx 都要自己寫 Lua,維護成本高。就是這兩個痛點推著我們把 Nginx 換成 APISIX——用管理 API 動態改限流、插件開箱即用,reload 問題也消失了。」

---

## 交叉引用

- 完整六維選型對照(Nginx/Envoy/Kong/APISIX/Spring Cloud Gateway/雲託管)+ 絞殺者遷移模式 + 通用上線清單 → ↪ [`gateway/11-selection-and-production-playbook.md`](../gateway/11-selection-and-production-playbook.md)
- AI/LLM 流量的網關需求與選型 → ↪ [`gateway/10-ai-llm-gateway.md`](../gateway/10-ai-llm-gateway.md)
- xDS 動態配置、控制面/資料面分離的原理 → ↪ [`gateway/08-gateway-as-distributed-system.md`](../gateway/08-gateway-as-distributed-system.md)、[`gateway/09-data-plane-control-plane-and-mesh.md`](../gateway/09-data-plane-control-plane-and-mesh.md)
- ingress-nginx 讓 Nginx 接近動態配置的方式 → ↪ ch11([`11-openresty-and-ingress.md`](./11-openresty-and-ingress.md))
- 反向代理 / upstream / 超時設定 → ↪ ch04([`04-reverse-proxy-and-upstream.md`](./04-reverse-proxy-and-upstream.md))
- 限流邊界(跨節點問題)→ ↪ ch06([`06-rate-limiting.md`](./06-rate-limiting.md))
- TLS 自動續期 / OCSP → ↪ ch07([`07-tls.md`](./07-tls.md))
- reload 平滑 / 熱升級 / `nginx -t` → ↪ ch08([`08-operations-zero-downtime.md`](./08-operations-zero-downtime.md))
- 性能調優(worker_connections / ulimit 三層聯動)→ ↪ ch09([`09-performance-tuning.md`](./09-performance-tuning.md))
- 可觀測 / 狀態碼診斷 / 連線耗盡 → ↪ ch10([`10-observability-debugging.md`](./10-observability-debugging.md))

---

## 本章小結

- Nginx 的核心邊界是**「靜態設定檔 + reload」模型**——穩定場景優點(可審計、版本控制友善),高動態場景缺點(改動延遲、管理鏈長)。
- **四個畢業判據**:動態路由需求、服務發現整合、插件生態、精細可觀測——**任何一個成立且痛夠深,就換對應的工具**,不要硬撐。
- **只想省 TLS 運維**:換 Caddy,不需要動全棧。
- **生產 checklist** 五組回扣前面各章:設定校驗(ch08)、監控接入(ch10)、超時/限流兜底(ch04/ch06)、TLS 自動續期(ch07)、快取安全設定(ch05)。
- **502 vs 504 vs 499 vs 503** 四碼最常混淆,先看 `$upstream_response_time` 定位是「沒連上」還是「等太久」還是「客戶端先走」還是「Nginx 自己擋」。
- 完整跨網關選型已在 ↪ `gateway/11`,本章只切 Nginx 自己的視角。

---

## 章末問答(複習自檢,答案要點都在前面正文)

**Q1.** Nginx 的哪個核心設計決定了它在容器/微服務環境的天花板?具體會帶來什麼問題?

<details>
<summary>答案要點</summary>

核心設計是「靜態設定檔 + reload 才生效」。在容器環境下,每次後端 Pod IP 變動都要改設定、跑 `nginx -t`、觸發 reload,操作鏈長且有秒到十幾秒的延遲。大量微服務場景下這個頻率難以接受,需要外部工具(consul-template/ingress controller)做膠水層。

</details>

**Q2.** 什麼情況下換 Caddy 就夠了?什麼情況下一定要換 Envoy 或 APISIX?

<details>
<summary>答案要點</summary>

換 Caddy 就夠:唯一痛點是 TLS 運維繁瑣(certbot + cron + 手動設定更新),功能需求不變。換 Envoy/APISIX 才夠:需要動態路由(不 reload 生效)、服務發現整合、豐富插件生態、或精細可觀測(OTel trace 零配置注入)——這些 Caddy 也做不到,需要真正不同設計的工具。

</details>

**Q3.** Nginx 的 `limit_req` 跨多台實例時為什麼達不到全域限速?正確的補救方案是什麼?

<details>
<summary>答案要點</summary>

`limit_req` 的共享記憶體 zone 只在**同一個 Nginx 進程的 worker 之間共享**,不跨機器。三台 Nginx 各自有各自的 zone,每台各自計 `10r/s`,實際全域效果是 `30r/s`。補救:把速率計數外移到 Redis(原子操作),用 OpenResty Lua / APISIX 的分散式限流插件實現跨節點共享計數。

</details>

**Q4.** 生產環境 Nginx 每次修改設定的標準流程是什麼?哪個環節最容易省略?

<details>
<summary>答案要點</summary>

標準流程:修改 `nginx.conf`(在版本控制裡)→ `nginx -t` 校驗語法 → 一台先 reload + 觀察日誌 → 確認無 5xx 再推其餘台(灰度 reload)。最容易省略的是「先單台 reload 觀察」,尤其在急著上線時直接全台一起推,結果設定有邏輯問題(如 `proxy_pass` 尾斜線錯、header 繼承被蓋)時全部出問題才發現。

</details>

**Q5.** 訪問日誌裡看到一批 502,`$upstream_response_time` 欄位值是 `-`。這說明什麼?下一步查什麼?

<details>
<summary>答案要點</summary>

`$upstream_response_time` 為 `-` 表示 Nginx 沒有成功連上 upstream(連線建立就失敗或被拒),並非連上之後超時。這是 502 的典型特徵。下一步:1. 確認後端進程是否在跑(ps / docker ps);2. 確認埠和 `upstream` 裡的 IP/埠是否正確;3. 看 `error_log` 裡的 `connect() failed`/`connection refused`/`no live upstream while connecting to upstream` 等具體報錯。

</details>
