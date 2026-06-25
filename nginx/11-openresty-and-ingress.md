# 11 · 外圈:OpenResty + ingress-nginx(輕)

> 一句話:這章把 Nginx 的兩個「外圈」拉進來——**OpenResty** 讓你在 Nginx 裡用 Lua 做純設定搞不定的事,**ingress-nginx** 讓你在 k8s 裡用 Ingress 物件驅動 Nginx。兩塊都是「輕量指路」:講清為什麼、何時用、最小例;細節 ↪ 指出去。

ch01–10 教的是「用設定語言駕馭 Nginx」。但有兩個場景純設定覆蓋不到:**第一**,你想在請求路徑裡呼叫外部服務、動態做決策——Nginx 的設定語言是宣告式的,沒有「執行一段邏輯、等回應、再決定怎麼做」的能力;**第二**,你在 k8s 裡跑服務,想用叢集原生的方式聲明路由規則,而不是手動維護 `nginx.conf`。OpenResty 解決第一個,ingress-nginx 解決第二個。

---

## 1. OpenResty:讓 Nginx 可程式化

### 1.1 為什麼純設定不夠

Nginx 的設定語言非常強大——`map`、`geo`、`limit_req`、`proxy_cache`……可以把大多數流量策略宣告出來。但它有一條根本邊界:**宣告式,不能跑任意邏輯、不能呼叫外部服務、不能讀寫共享狀態(跨請求)**。

幾個典型超出這條邊界的場景:

| 需求 | 純設定能不能搞定 | 原因 |
|---|---|---|
| **動態鑑權**:每個請求打一個鑑權服務(`/auth`)拿結果 | 不能 | `proxy_pass` 是轉發整個請求,不是「先發一個子請求再決定放行」 |
| **複雜路由**:讀 JWT payload 裡的 tenant 欄位決定後端 | 不能 | `$http_xxx` 只能取 header 原文,無法 decode / 解析 JSON |
| **跨 worker 共享計數器**:精細的業務限流(不只是 `limit_req` 的 IP 粒度) | 不能直接 | `limit_req_zone` 是同節點共享但功能固定,無法自訂計數邏輯 |
| **呼叫 Redis/外部 API**:請求裡帶 session token,查 Redis 驗合法性 | 不能 | 純設定沒有 socket 操作能力 |

**OpenResty** 就是為打破這條邊界而生的:它在 Nginx 的各個**請求處理階段**(phase)嵌入 Lua 虛擬機,讓你能在每個 phase 跑一段 Lua 邏輯。Lua 在 OpenResty 裡是**非同步、協程式的**——呼叫 Redis、MySQL、HTTP subrequest 都是 yield/resume,不阻塞 worker 事件迴圈(引擎模型 ↪ `gateway/01-reverse-proxy-engine.md`)。

> **APISIX** 本身就是基於 OpenResty 的雲原生 API 網關——它用 Lua 外掛做動態路由、鑑權、限流。用過 APISIX 你就在用 OpenResty 的能力,只是被封裝了。

### 1.2 Lua 掛在哪個 phase

OpenResty 在 Nginx 請求管線(↪ `gateway/02-request-pipeline.md` 的 filter chain 抽象)的各個 phase 各提供一個 Lua 鉤子。對應關係如下:

| Lua 鉤子指令 | 對應 Nginx phase | 典型用途 |
|---|---|---|
| `set_by_lua` / `set_by_lua_block` | **rewrite 之前** / `set` phase | 計算並設定 Nginx 變數(純計算,不能做 I/O) |
| `rewrite_by_lua` / `rewrite_by_lua_block` | **rewrite phase** | 改 URI、設變數;可做 I/O(呼叫 Redis 查 A/B 分組) |
| `access_by_lua` / `access_by_lua_block` | **access phase** | **鑑權/放行判斷主戰場**;可呼叫外部鑑權服務、讀 header/cookie 決定 403/放行 |
| `content_by_lua` / `content_by_lua_block` | **content phase** | 完全接管回應生成(像 `proxy_pass` 的角色,但用 Lua 邏輯控制) |
| `header_filter_by_lua` / `header_filter_by_lua_block` | **header filter phase** | 改寫回應頭(加/刪 header,在後端回應頭到客戶端之前攔截) |
| `body_filter_by_lua` / `body_filter_by_lua_block` | **body filter phase** | 改寫回應體(串流改內容,注意對效能的影響) |
| `log_by_lua` / `log_by_lua_block` | **log phase** | 自訂日誌邏輯、非同步上報指標(不阻塞請求本身) |

**ch01 的 phase 觀念在這裡落地**:你在哪個鉤子裡寫 Lua,就決定了它在請求生命週期的哪個時機介入。`access_by_lua` 是最常用的——鑑權就是「在 content phase 之前,決定這個請求能不能走下去」。

### 1.3 `lua_shared_dict`:跨 worker 共享狀態

ch06 講過 Nginx `limit_req` 的一個邊界:**zone 是同節點所有 worker 共享的共享記憶體,但只限於 `limit_req` 自己的邏輯**——你沒辦法用它存自訂的業務計數器。

OpenResty 的 **`lua_shared_dict`** 填補這個缺口:它在 `http` 區塊宣告一塊**跨 worker 共享的記憶體字典**,所有 Lua 程式碼都能讀寫它,操作是原子的(用鎖保護)。

```nginx
# nginx.conf(OpenResty)
http {
    lua_shared_dict token_cache 10m;   # 宣告一個 10 MB 的共享字典
    lua_shared_dict rate_counter 5m;   # 另一個計數器字典

    server {
        listen 80;
        location /api/ {
            access_by_lua_block {
                local cache = ngx.shared.token_cache
                local token = ngx.req.get_headers()["Authorization"]
                -- 先查快取
                local valid = cache:get(token)
                if not valid then
                    -- 呼叫鑑權服務(非同步、不阻塞 worker)
                    -- ... (略:用 ngx.location.capture 或 resty.http)
                    cache:set(token, "ok", 60)  -- 快取 60 秒
                end
            }
            proxy_pass http://backend;
        }
    }
}
```

`lua_shared_dict` 讓你能實作「token 快取」「滑動視窗計數器」「黑名單」等需要跨請求、跨 worker 共享狀態的業務邏輯——這是純 Nginx 設定做不到的。

### 1.4 最小例:access_by_lua 讀 header 決定放行

最常見的 OpenResty 起手式——用 `access_by_lua_block` 做最小鑑權:

```nginx
location /protected/ {
    access_by_lua_block {
        local api_key = ngx.req.get_headers()["X-Api-Key"]
        if api_key ~= "secret-key-123" then
            ngx.status = 403
            ngx.say("Forbidden")
            ngx.exit(403)   -- 終止請求,不繼續到 content phase
        end
        -- key 對了,什麼都不做,繼續走 proxy_pass
    }
    proxy_pass http://backend;
}
```

這個例子展示了 `access_by_lua_block` 的基本結構:
- `ngx.req.get_headers()` — 讀請求頭(`ngx.*` 是 OpenResty 提供的 API,綁定到當前請求上下文)
- `ngx.status` / `ngx.say` / `ngx.exit` — 直接發回應並終止請求
- 不呼叫 `ngx.exit` 就繼續到下一 phase(這裡是 `proxy_pass` 的 content phase)

> **面試一句話(「什麼時候該上 OpenResty」)**:「純 Nginx 設定是宣告式的,處理靜態策略沒問題;一旦需要『在請求路徑裡跑任意邏輯、呼叫外部服務、讀寫跨 worker 共享狀態』,就是 OpenResty 的場景。常見需求:動態鑑權(每個請求打鑑權服務)、讀 JWT payload 做複雜路由、自訂計數器/黑名單。」

### 1.5 何時升級到 OpenResty、何時直接換 Envoy/APISIX

| 場景 | 建議 |
|---|---|
| 有幾個鑑權/路由邏輯需要自訂,但整體是 Nginx 生態 | **OpenResty**:在現有 Nginx 技術棧上加 Lua,改動最小 |
| 需要動態配置(不 reload 就能改路由)、豐富的外掛市場、雲原生整合 | **APISIX**(底層是 OpenResty,但給你 Admin API + 控制面,不用自己寫 Lua) |
| 需要 xDS 動態設定、精細可觀測性(trace/metric 原生)、mesh 整合 | **Envoy**:控制面/資料面分離架構(↪ `gateway/09-data-plane-control-plane-and-mesh.md`) |
| Lua 技術棧對團隊是負擔,功能可以用成熟外掛解決 | 直接選 **APISIX** 或 **雲託管 API Gateway**,不要裸寫 OpenResty |

**核心判據**:如果你主要在「用設定控制 Nginx」,留在 nginx track(ch01–10);如果你需要「在請求路徑裡跑程式邏輯」,進 OpenResty;如果你需要「動態控制面 + 不 reload + 外掛生態」,選 APISIX 或 Envoy。完整網關選型見 ↪ `gateway/11-selection-and-production-playbook.md`。

---

## 2. ingress-nginx:用 k8s 物件驅動 Nginx

### 2.1 為什麼要 ingress-nginx

在 k8s 叢集裡,每個服務(`Service`)有一個叢集內部 IP,但外部流量要進來必須有一個入口。**Ingress** 是 k8s 的 API 物件,用來宣告「哪個 hostname + path 路由到哪個 Service」——它只是一個規則聲明,本身不做任何流量轉發。真正轉發流量的是 **Ingress Controller**。

**ingress-nginx** 就是「以 Nginx 為資料面的 Ingress Controller」——它 watch k8s 的 `Ingress` 物件,把規則渲染成 `nginx.conf`,然後 reload Nginx 讓設定生效。

### 2.2 🔬 Ingress 資源 → Nginx config 這一跳

這一跳是 ingress-nginx 的核心,也是面試最高頻的問題:**「ingress-nginx 怎麼把 Ingress 物件變成 Nginx 設定?」**

```
┌─────────────────────────────────────────────────────────────┐
│ k8s API Server                                              │
│   Ingress 物件(你 kubectl apply 的 YAML)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │  watch(持續監聽 Ingress/Service/Endpoints 變化)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ ingress-nginx Controller(Pod,跑在叢集裡)                     │
│                                                              │
│  ① 接收到 Ingress 變更事件                                    │
│  ② 讀取所有 Ingress + 關聯 Service/Endpoints                 │
│  ③ 渲染成完整的 nginx.conf(Go template)                      │
│  ④ nginx -t 校驗新設定(有錯就告警、不換)                      │
│  ⑤ nginx -s reload(= 給 master 發 HUP)                      │
│     └─ 就是 ch08 講的那個 reload:                            │
│        listen socket 不關、舊 worker 優雅退、新 worker 接管   │
└─────────────────────────────────────────────────────────────┘
```

**這個「reload」就是 ch08 的那個 reload**——ingress-nginx 渲染完設定後做的事,和你手動 `nginx -s reload` 是完全一樣的機制:master 持有 listen socket、舊 worker 處理完在途請求才退、設定有錯不換(↪ `nginx/08-operations-zero-downtime.md`)。

一個 Ingress YAML 範例:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2        # annotation 控制 Nginx 行為
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /v1(/|$)(.*)
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

ingress-nginx controller 把這個 YAML 渲染成類似這樣的 Nginx 設定片段(大幅簡化):

```nginx
# 由 controller 自動生成,你不需要手寫
server {
    server_name api.example.com;
    listen 80;

    location ~* "^/v1(/|$)(.*)" {
        rewrite "^/v1(/|$)(.*)" /$2 break;   # rewrite-target annotation 的效果
        client_max_body_size 10m;              # proxy-body-size annotation 的效果
        proxy_pass http://upstream-api-service-80;
        # ... 其他 proxy_* 設定
    }
}
```

### 2.3 常用 annotation

Annotation 是在 Nginx 設定層面控制行為的主要方式——每個 annotation 對應 ingress-nginx 在渲染 `nginx.conf` 時插入的某段設定:

| Annotation | 對應 Nginx 設定效果 | 典型場景 |
|---|---|---|
| `nginx.ingress.kubernetes.io/rewrite-target: /` | `rewrite` 指令改 URI | 路徑前綴 strip(外部 `/api/v1/foo` → 後端 `/foo`) |
| `nginx.ingress.kubernetes.io/proxy-body-size: 50m` | `client_max_body_size 50m` | 允許大檔案上傳 |
| `nginx.ingress.kubernetes.io/ssl-redirect: "true"` | `return 301 https://...` | 強制 HTTPS |
| `nginx.ingress.kubernetes.io/configuration-snippet` | **直接插入一段 Nginx 設定** | 需要寫原生 Nginx 指令(如自訂 `add_header`、`proxy_set_header`) |

**`configuration-snippet`** 是逃生艙:當 annotation 不夠表達你想要的設定時,可以直接貼一段 Nginx 設定進去。

```yaml
annotations:
  nginx.ingress.kubernetes.io/configuration-snippet: |
    add_header X-Custom-Header "hello" always;
    proxy_set_header X-Real-IP $remote_addr;
```

> **注意**:出於安全考量(允許注入任意 Nginx 指令),新版 ingress-nginx 預設禁止 `configuration-snippet`,需要在 controller 層面明確啟用(`allow-snippet-annotations: "true"`)。這是個常見的升級踩坑點。

### 2.4 分層架構:雲 LB → ingress-nginx → Service

```
Internet
    │
    ▼
雲 LB(ALB / NLB / GCP LB)    ← L4/L7 雲端入口,做 TLS 終止或直穿
    │  NodePort / LoadBalancer Service
    ▼
ingress-nginx Pod              ← L7 路由:hostname + path → Service
    │  ClusterIP
    ▼
後端 Service(ClusterIP)        ← k8s Service 做 Pod 選擇與負載均衡
    │
    ▼
後端 Pod
```

這三層各管一段:
- **雲 LB**:把外部流量導進叢集,通常負責 L4 進入點(也可以做 L7 TLS 終止)。
- **ingress-nginx**:在叢集內做 L7 路由——根據 hostname、path 把請求導到對應的 Service。
- **Service**:在 Pod 之間做負載均衡(kube-proxy / eBPF 實現)。

> **Gateway API vs Ingress**:Ingress API 已存在多年但表達力有限(annotation 是非標準的);**Gateway API** 是更新的 k8s 標準,把路由/後端/基礎設施分層聲明,表達力更強、移植性更好。ingress-nginx 也在支援 Gateway API。k8s 網路全景與 Gateway API 的演進 ↪ `cloud-native/05-networking.md`、`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`。

> **其他 Ingress Controller**:每個 controller 的資料面不同——Traefik(Go)、HAProxy Ingress、Kong Ingress(API 網關)、AWS Load Balancer Controller(直接驅動 ALB)。annotation 是非可移植的,換 controller 通常要重寫 annotation。

> **面試一句話(「ingress-nginx 怎麼把 Ingress 變成 Nginx 設定」)**:「ingress-nginx controller watch k8s 的 Ingress 物件,收到變更就把所有 Ingress 規則渲染成一份完整的 `nginx.conf`,然後做 `nginx -s reload`——就是普通的 Nginx reload,listen socket 不關、舊 worker 優雅退,所以流量不中斷。annotation 是你控制渲染出的 Nginx 設定內容的旋鈕。」

---

## 交叉引用

- **Nginx 請求處理 phase(rewrite/access/content/log)**:↪ `nginx/01-config-model.md`(本 track 地基,Lua 鉤子對應這些 phase)
- **reload 機制(listen socket 由 master 持有、舊 worker 優雅退)**:↪ `nginx/08-operations-zero-downtime.md`(ingress-nginx 的 reload 就是這個機制)
- **可程式化網關演化、filter chain 抽象**:↪ `gateway/02-request-pipeline.md`、`gateway/09-data-plane-control-plane-and-mesh.md`
- **k8s 網路全景、Gateway API、eBPF 資料面**:↪ `cloud-native/05-networking.md`、`cloud-native-landscape/03-networking-ebpf-and-gateway-api.md`
- **完整網關選型(Envoy/APISIX/Kong/雲託管)**:↪ `gateway/11-selection-and-production-playbook.md`
- **Nginx 限流的單機邊界(為何 `lua_shared_dict` 仍是單機)**:↪ `nginx/06-rate-limiting.md`;跨節點分散式限流 ↪ `gateway/05-traffic-control.md`

---

## 本章小結

**OpenResty:**
- 純 Nginx 設定是宣告式的,一旦需要「在請求路徑裡跑邏輯、呼叫外部服務、跨 worker 共享狀態」就需要 OpenResty。
- Lua 鉤子掛在各個 phase:`access_by_lua` 是鑑權主戰場,`content_by_lua` 完全接管回應,`log_by_lua` 做非同步日誌。
- `lua_shared_dict` 補了「跨 worker 共享計數器/快取」的缺口(但仍是單機,跨節點需 Redis)。
- 升級路徑:純設定 → OpenResty(加 Lua) → APISIX(OpenResty + 控制面) → Envoy(需要動態 xDS + mesh)。

**ingress-nginx:**
- **核心一跳**:controller watch Ingress 物件 → 渲染 `nginx.conf` → `nginx -s reload`(ch08 的 reload,流量不中斷)。
- annotation 是控制渲染內容的旋鈕;`configuration-snippet` 是直接插入原生 Nginx 設定的逃生艙(新版需顯式啟用)。
- 分層:雲 LB(外部入口) → ingress-nginx(L7 路由) → Service(Pod 負載均衡)。
- Gateway API 是 Ingress 的進化方向,表達力更強、annotation 更標準化。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 純 Nginx 設定搞不定、但 OpenResty 可以搞定的三個典型場景是什麼?為什麼宣告式設定在這些場景裡力不從心?

2. `access_by_lua_block` 和 `content_by_lua_block` 各在請求的哪個 phase 執行?如果 `access_by_lua_block` 裡呼叫了 `ngx.exit(403)`,後面的 `proxy_pass` 還會執行嗎?

3. `lua_shared_dict` 宣告的字典是「跨 worker 共享」的——但它能解決分散式限流的問題嗎?為什麼?要做跨節點的全域計數器該怎麼辦?

4. **核心題:「ingress-nginx 怎麼把 Ingress 物件變成 Nginx 設定?」** 請把 watch → 渲染 → reload 這一跳的步驟口述一遍,並說明這個 reload 為什麼不會中斷在途請求。

5. 你在 Ingress 上加了一個 `nginx.ingress.kubernetes.io/rewrite-target: /$2` annotation,這個 annotation 最終影響的是什麼?它是怎麼「生效」的?

6. 叢集裡的請求流量路徑:Internet 進來的請求,要經過哪幾層才能到後端 Pod?每層各負責什麼?Gateway API 和 Ingress 的主要差異是什麼?
