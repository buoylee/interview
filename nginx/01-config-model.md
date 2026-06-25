# 01 · 設定模型:區塊、繼承、location 匹配 🔬⭐

> 一句話:這是全 track 的地基。02–12 每一章都假設你能讀懂一個 `server`/`location` 區塊、並**預測一個請求會落到哪一段設定**。把「設定語言」這門課先上完,後面寫 `proxy_cache`、`limit_req`、TLS 都是往這個模型上掛指令。

Nginx 的設定檔不是一堆零散開關,而是一套有**作用域、有繼承、有匹配優先級**的小語言。看不懂它,你寫的每一段 `location` 都是在賭命中;看懂它,你能盯著一份 `nginx.conf` 在腦子裡跑出「這個 URI 會被哪條規則接住、`$uri` 此刻是什麼」。

這一章把四件事講死:**區塊層級與指令繼承**(含 `add_header` 那個吃人的陷阱)、**`location` 五檔匹配優先級**(核心)、**`root` vs `alias`**、**內建變數**,最後拆穿**「`if` is evil」的真相**並給替代方案。

> 引擎為什麼快(master-worker、epoll、連線池)不在這裡——那是 `gateway/01-reverse-proxy-engine.md` 的事。本章只教「怎麼**用設定**駕馭這台引擎」。

---

## 1. 區塊層級:設定有作用域

Nginx 設定是一棵**巢狀的區塊樹**,每一層叫一個 **context(上下文)**。一條指令(directive)只能寫在它被允許的 context 裡,寫錯地方 `nginx -t` 會直接報錯。

```
main (檔案最外層,沒有大括號)
│   user / worker_processes / pid / error_log …  ← 進程級全局
│
├── events { … }              ← 連線處理:worker_connections / use epoll
│
└── http { … }                ← 所有 HTTP 相關的根:gzip / log_format / proxy_* / upstream
    │
    ├── upstream backend { … } ← 後端組(ch04 講)
    │
    └── server { … }          ← 一個虛擬主機:listen / server_name / ssl_*
        │   server_name api.example.com;
        │
        └── location /path { … }  ← 對某段 URI 的處理:proxy_pass / root / try_files
            │
            └── location ~ \.php$ { … }  ← location 可以再巢狀
```

| context | 放什麼 | 心智 |
|---|---|---|
| **main** | `user`、`worker_processes`、`pid`、頂層 `error_log` | 進程怎麼跑(誰啟動、幾個 worker) |
| **events** | `worker_connections`、`use epoll`、`accept_mutex` | 連線怎麼收(↪ 機制在 `gateway/01`) |
| **http** | `gzip`、`log_format`、`proxy_*` 默認值、`upstream`、`server` | 所有 HTTP 行為的根,也是「定默認值」的好地方 |
| **server** | `listen`、`server_name`、`ssl_certificate`、`location` | 一個虛擬主機 = 一個對外身份 |
| **location** | `proxy_pass`、`root`/`alias`、`try_files`、`return` | 「某段 URI 怎麼處理」的最小單位 |

> 一個 `http` 裡可以有多個 `server`(多虛擬主機),Nginx 按 `listen` + `server_name` 選中其中一個,再進它的 `location` 匹配。`server` 選擇本身也有規則(精確名 > 前綴 `*.` 通配 > 後綴通配 > 正則 > `default_server`),但日常踩坑集中在 `location`,所以本章重火力放 `location`。

---

## 2. 🔬 指令繼承:外層傳給內層,內層能覆蓋——但有例外

這是「在腦中跑設定」的第一塊內幕:**一條指令在哪些 context 生效,以及內外層怎麼合併。**

### 2.1 基本規則:向下繼承、同名覆蓋

大多數指令遵循「**outer → inner 向下繼承,inner 出現同名就覆蓋**」:

```nginx
http {
    gzip on;                    # http 層開啟
    proxy_read_timeout 60s;     # http 層默認 60s

    server {
        proxy_read_timeout 10s; # ← 這個 server 覆蓋成 10s

        location /slow/ {
            proxy_read_timeout 300s;  # ← 這個 location 再覆蓋成 300s
        }
        location /fast/ {
            # 沒寫 → 繼承 server 的 10s
        }
    }
}
```

`/fast/` 沒寫 `proxy_read_timeout`,於是用 `server` 的 `10s`;`/slow/` 自己寫了 `300s`,就用自己的。**「就近原則」:最靠內、離 location 最近的那個值贏。** 這讓你能「在 http 層定一套合理默認,只在需要特殊化的 location 裡覆蓋」。

> 內幕注意:**繼承的是「值」不是「合併」**。`proxy_read_timeout 300s` 不是在 60s 上疊加,而是整個換掉。對單值指令這很直覺;但對**可以出現多次的指令**(如 `add_header`),「換掉」會變成下面那個吃人陷阱。

### 2.2 🔬 `add_header` 的繼承陷阱(面試高頻 + 線上事故高頻)

`add_header` 是「陣列型」指令——你可以在一個 context 裡寫好幾條,給回應加好幾個頭。它的繼承規則是整個 Nginx 設定裡**最反直覺**的一條:

> **只要某一層(更內層)出現了任何一條 `add_header`,這一層就會丟掉「從外層繼承來的所有 `add_header`」,只保留自己這層寫的。**

它**不是逐條合併**,而是「**內層一旦發聲,外層全部作廢**」。看這個會出事的例子:

```nginx
server {
    add_header X-Frame-Options "DENY";                # 想全站防點擊劫持
    add_header Strict-Transport-Security "max-age=63072000";  # 想全站 HSTS

    location /api/ {
        add_header X-Request-Id $request_id;          # ← 只想多加一個 header
        proxy_pass http://backend;
    }
}
```

**直覺以為**:`/api/` 的回應有三個頭(X-Frame-Options + HSTS + X-Request-Id)。
**真相**:`/api/` 的回應**只有 X-Request-Id**——因為 `location` 裡出現了 `add_header`,它把 `server` 層那兩個安全頭**全部丟掉了**。你的 HSTS 和防劫持頭在 `/api/` 上**靜默消失**,測試時很容易漏掉,上線後才被安全掃描打臉。

**怎麼防(三選一,按場景)**:

1. **內層需要的頭,把外層的也重抄一遍**(最直白,但容易漏抄):
   ```nginx
   location /api/ {
       add_header X-Frame-Options "DENY";
       add_header Strict-Transport-Security "max-age=63072000";
       add_header X-Request-Id $request_id;
       proxy_pass http://backend;
   }
   ```

2. **用 `include` 把公共安全頭抽成一個片段,在每個需要的 location 裡 `include`**(DRY,推薦給多 location 的站點):
   ```nginx
   # security-headers.conf
   add_header X-Frame-Options "DENY" always;
   add_header Strict-Transport-Security "max-age=63072000" always;
   ```
   ```nginx
   location /api/ {
       include security-headers.conf;
       add_header X-Request-Id $request_id;
       proxy_pass http://backend;
   }
   ```

3. **盡量把 `add_header` 統一放在同一層**:能放 `server` 就全放 `server`,別在 `location` 裡零星加,避免「內層發聲」這件事發生。

> 兩個容易連帶搞錯的點:
> - **`always` 參數**:不加 `always` 時,`add_header` 只在 2xx/3xx 等「正常」回應上加頭;後端回 4xx/5xx 時頭就沒了。安全頭(HSTS/CSP)通常要加 `always`,確保錯誤頁也帶上。
> - **`proxy_pass` 後端自己回的頭**:`add_header` 加的是 Nginx 這層的頭,和後端回應裡已有的同名頭是**兩回事**(可能出現重複頭)。要「改寫/刪除後端的頭」用的是另一組指令(`proxy_hide_header` / `proxy_set_header` 是給請求的),別混。

**面試一句話**:「`add_header` 不是逐條合併——子層只要寫了一條 `add_header`,父層所有 `add_header` 全部失效,得在子層重抄或用 `include`。」這句答出來就贏一半人。

---

## 3. 🔬⭐ `location` 匹配優先級:核心中的核心

一個請求進到選中的 `server` 後,Nginx 要決定「這個 URI 交給哪個 `location` 處理」。一個 `server` 裡常有十幾條 `location`,**它們不是按寫的順序從上往下試**——而是按一套**固定的優先級**。背不清這套規則,你寫的 `location` 命中就是玄學。

**先把完整規則列死(白板上就口述這五檔順序)**:

| 檔位 | 寫法 | 匹配方式 | 命中後行為 |
|---|---|---|---|
| **① 精確** | `location = /path` | URI **完全等於** `/path` | 命中**立即停止**,直接用它 |
| **② 前綴+停止** | `location ^~ /path/` | URI **以 `/path/` 開頭**,且是「最長前綴」 | 命中後**不再比任何正則**,直接用它 |
| **③ 正則** | `location ~ 正則`(區分大小寫)<br>`location ~* 正則`(不分大小寫) | URI **匹配正則** | **按它們在設定檔裡出現的先後順序**逐個試,**第一個**命中即停 |
| **④ 普通前綴(回退)** | `location /path`(不帶修飾符) | URI 以 `/path` 開頭 | 記住「**最長**的那個前綴」,當沒有任何正則命中時**回退**用它 |

**完整裁決流程(Nginx 真實的執行順序)**:

```
1. 先掃所有「前綴型」location（= 與 ^~ 與普通前綴），找出：
   a. 有沒有 = 精確命中？  ──有──► 立即用它，結束。
   b. 記下「最長前綴匹配」是哪一條。
2. 看「最長前綴匹配」這條：
   - 如果它帶 ^~ ──► 直接用它，不再比正則，結束。
3. 否則，按設定檔出現順序逐個試「正則」location：
   - 第一個命中的正則 ──► 用它，結束（後面的正則不再試）。
4. 都沒有正則命中 ──► 回退到第 1b 記下的「最長前綴匹配」，用它。
```

把它壓成一句口訣:**「精確命中即停 > 帶 `^~` 的最長前綴命中即停(不比正則) > 正則按出現序第一個命中即停 > 最長前綴回退。」**

### 3.1 請求 URI → 命中哪條(對照表)

給定這份設定(故意讓它們「打架」):

```nginx
server {
    location = /login          { return 200 "A 精確\n"; }
    location ^~ /static/        { return 200 "B 前綴停止\n"; }
    location ~* \.(jpg|png)$    { return 200 "C 正則-圖片\n"; }
    location ~  ^/api/v1/       { return 200 "D 正則-api\n"; }
    location /                  { return 200 "E 根前綴(兜底)\n"; }
}
```

| 請求 URI | 命中 | 為什麼 |
|---|---|---|
| `/login` | **A** | `= /login` 精確命中,第①檔最高,立即停 |
| `/login/` | **E** | `= /login` 要求**完全相等**,`/login/` 不等;無正則命中 → 回退最長前綴 `/` |
| `/static/app.js` | **B** | 最長前綴是 `^~ /static/`,帶 `^~` → 不比正則,直接用 B |
| `/static/logo.png` | **B** | **仍是 B!** `^~` 命中後**不再比正則**,所以 C(圖片正則)沒機會 |
| `/img/logo.png` | **C** | 最長前綴是 `/`(不帶 `^~`)→ 進正則,C 先於 D 出現且命中 → C |
| `/img/logo.JPG` | **C** | `~*` 不分大小寫,`.JPG` 也算圖片 → C |
| `/api/v1/users` | **D** | 最長前綴是 `/` → 進正則,C 不中(非圖片)、D 中 → D |
| `/api/v2/users` | **E** | 最長前綴 `/`,C/D 都不中(D 寫死 `/api/v1/`)→ 回退 `/` → E |
| `/anything-else` | **E** | 無精確、無 `^~`、無正則命中 → 回退最長前綴 `/` |

**這張表裡最容易被考/被坑的兩格**:
- `/static/logo.png` → **B 不是 C**:很多人以為「圖片就走圖片正則」,但 `^~` 一旦在前綴階段勝出就**短路掉整個正則階段**。想讓 `/static/` 下的圖片也走某條正則,就**別**用 `^~`。
- `/login/` → **E 不是 A**:`=` 是**完全相等**,差一個尾斜線就掉到兜底。

> ⭐ **白板答法**(被問「`location` 匹配優先級」時,口述這串就滿分):
> 「Nginx 先掃前綴型。**精確 `=` 命中就立即用**;否則記住最長前綴——如果它帶 `^~`,直接用、**不比正則**;否則進正則階段,**按設定檔出現順序第一個命中的正則勝出**;正則都不中,才回退到剛才那個最長前綴。所以順序是 `=` > `^~` > 正則(出現序)> 最長前綴。」

---

## 4. `root` vs `alias`:路徑拼接最容易錯的地方

兩個都用來把 URI 映射到磁碟檔案路徑,但**拼接方式完全不同**,混用會 404 或洩漏路徑。

- **`root`**:把**整個 URI** 接在 `root` 後面。
  最終路徑 = `root 值` + `整個請求 URI`。
- **`alias`**:把 `location` 的前綴**替換掉**,只保留 URI 剩下的部分接上去。
  最終路徑 = `alias 值` + `(URI 去掉 location 前綴後剩下的部分)`。

對照同一個請求 `/static/css/app.css`:

| 設定 | 計算 | 最終磁碟路徑 |
|---|---|---|
| `location /static/ { root /var/www; }` | `/var/www` + `/static/css/app.css` | `/var/www/static/css/app.css` |
| `location /static/ { alias /var/www/assets/; }` | `/var/www/assets/` + `css/app.css`(去掉前綴 `/static/`) | `/var/www/assets/css/app.css` |

**口訣**:`root` **保留** location 前綴(整個 URI 都拼上去),`alias` **吃掉** location 前綴(用 alias 值替換它)。

### 尾斜線陷阱(最常見的 `alias` 事故)

用 `alias` 時,**`location` 前綴和 `alias` 值的尾斜線要對齊**,否則路徑會錯位:

```nginx
# ✗ 危險:location 帶尾斜線、alias 不帶
location /static/ {
    alias /var/www/assets;   # 請求 /static/app.css → /var/www/assetsapp.css(少了斜線,黏在一起!)
}

# ✓ 正確:兩邊都帶尾斜線
location /static/ {
    alias /var/www/assets/;  # 請求 /static/app.css → /var/www/assets/app.css
}
```

**經驗法則**:用 `alias` 時,`location` 前綴帶尾斜線,`alias` 值也帶尾斜線(成對出現)。`root` 沒有這個問題(它拼整個 URI,尾斜線本身就在 URI 裡)。

> 另一個坑:**`alias` 不要和正則 `location` + `try_files` 隨便混用**(老版本有已知 bug,且路徑拼接更難推);純前綴 `location` 用 `alias` 最穩。日常建議:**能用 `root` 就用 `root`,只有當「URL 路徑」和「磁碟目錄名」對不上時才用 `alias`。**

---

## 5. 內建變數:`$uri` / `$request_uri` / `$args` / `$host`

Nginx 在處理請求時把一堆資訊存進**內建變數**,你在 `log_format`、`proxy_set_header`、`rewrite`、`if`、`map` 裡都會用到。挑日常最高頻、最容易用錯的幾組講清「何時用哪個」。

| 變數 | 是什麼 | 例(請求 `GET /a%20b/c?id=1&p=2`) |
|---|---|---|
| **`$uri`** | **解碼後、且可被內部改寫**的當前 URI(不含 query string) | `/a b/c`(`%20` 解碼成空格;若被 `rewrite` 改過,這裡是改後的值) |
| **`$request_uri`** | **原始**請求行裡的完整 URI(**含** query string,**不解碼、不被改寫**) | `/a%20b/c?id=1&p=2` |
| **`$args`** | 完整 query string(`?` 後面那串,不含 `?`) | `id=1&p=2` |
| **`$arg_xxx`** | 某個具體 query 參數的值 | `$arg_id` = `1`、`$arg_p` = `2` |
| **`$host`** | 請求的主機名(優先取請求行/`Host` 頭,小寫;比 `$http_host` 多了正規化與兜底) | `api.example.com` |
| **`$http_xxx`** | 任意請求頭,`xxx` 是頭名小寫、`-` 換成 `_` | `$http_user_agent`、`$http_x_forwarded_for` |

**最關鍵的一條區別 —— `$uri` vs `$request_uri`**:

- **`$uri` 是「Nginx 內部當前看到的路徑」**:已 URL 解碼、不含 query、且**會隨 `rewrite`/內部跳轉改變**。你想對「處理過程中的路徑」做判斷(例如比對副檔名),用 `$uri`。
- **`$request_uri` 是「客戶端原樣發來的東西」**:不解碼、含 query、永遠是原始值。你想**原樣轉發給後端**或記錄客戶端真實請求的,用 `$request_uri`。

一個典型用法區別:
```nginx
# 想把客戶端的原始完整路徑(含 query)原樣記到日誌 / 傳給後端 → $request_uri
log_format main '$remote_addr "$request_uri" $status';

# 想在 rewrite 階段判斷「當前路徑」是不是某個目錄 → $uri(它反映改寫後的狀態)
if ($uri ~ ^/old/) { ... }
```

> `$host` vs `$http_host`:`$http_host` 是原始 `Host` 頭(可能沒有、可能帶大小寫);`$host` 做了正規化(小寫、缺 Host 時用 `server_name` 兜底)。**反代設 `proxy_set_header Host $host;` 通常比 `$http_host` 穩**(這條到 ch04 反代章會再用到)。

---

## 6. 🔬 「`if` is evil」的真相:不是不能用,是只在窄場景可預測

社群名言 **「If Is Evil」**(官方 wiki 的標題)常被誤解成「永遠別用 `if`」。真相更精確,也是面試想聽的:

> **`if` 在 `location` 內部只有對 `return` 和 `rewrite` 兩條指令行為是確定可預測的;一旦在 `if` 裡放 `proxy_pass`、`try_files`、`add_header`、`alias` 等其他指令,行為就可能出乎意料、甚至段錯誤。**

**為什麼會這樣(內幕)**:`location` 內的 `if` 其實會建立一個**隱形的巢狀 location**,把請求「轉移」進這個匿名 location 處理。問題是這個轉移過程**不會繼承外層 location 的內容指令**(content handler、`try_files` 設定、`add_header` 等),於是:

- `if` 裡放 `try_files` → 外層的 `try_files` 可能被吃掉,回退鏈失效。
- `if` 裡放 `proxy_pass` 配合外層也有 `proxy_pass` → 兩個 content handler 打架,結果視版本而定。
- 兩個 `if` 都想改同一件事 → 後一個未必如你所願地接著前一個。

`return` 和 `rewrite` 之所以安全,是因為它們是**rewrite 階段**的指令(這個階段就是設計來「改 URI / 早退」的,↪ Nginx 的 phase 模型對應 `gateway/02-request-pipeline.md` 講的 `rewrite`/`access`/`content` 管線),不依賴 content handler 的繼承,所以在 `if` 裡也表現一致。

### 安全用法(可以放心寫)

```nginx
# ✓ if + return:安全。非法 method 直接擋
if ($request_method = POST) { return 405; }

# ✓ if + rewrite:安全。舊路徑跳新路徑
if ($http_user_agent ~* "bot") { rewrite ^ /bot-page last; }
```

### 危險用法 → 給替代方案

**場景 A:想「根據某個條件選不同後端 / 不同變數值」** → 用 **`map`**(在 `http` 層宣告,把輸入變數映射成輸出變數,純查表、無副作用、可預測):

```nginx
# ✗ 別這樣(if 裡藏 proxy_pass / 變數賦值,行為不穩)
# location /api/ {
#     if ($arg_version = v2) { proxy_pass http://backend_v2; }
#     proxy_pass http://backend_v1;
# }

# ✓ 用 map:在 http 層把條件映射成一個變數,location 裡乾淨地用它
map $arg_version $api_backend {
    default  backend_v1;
    v2       backend_v2;
}
server {
    location /api/ {
        proxy_pass http://$api_backend;   # 由 map 決定,行為確定
    }
}
```

**場景 B:想「按檔案是否存在做不同處理 / SPA 回退」** → 用 **`try_files`**(它就是為「按存在性回退」設計的,比 `if (-f ...)` 安全得多):

```nginx
# ✗ 別這樣
# location / {
#     if (-f $request_filename) { ... }
#     if (!-f $request_filename) { rewrite ^ /index.html; }
# }

# ✓ 用 try_files:依序試,命中即用,最後回退
location / {
    try_files $uri $uri/ /index.html;   # SPA 標準寫法(細節在 ch02)
}
```

**一句總結**:`if` 只在「`return`/`rewrite` 早退或跳轉」時用;**「選後端 / 賦值」交給 `map`,「按檔案存在性回退」交給 `try_files`。** 這就把 `if` 的雷區全繞開了。

> **面試一句話**:「`if` 不是不能用——它只對 `return`/`rewrite` 可預測,因為這兩個是 rewrite 階段指令;配 `proxy_pass`/`try_files`/`add_header` 會因為它建了隱形巢狀 location、不繼承內容指令而出詭異結果。所以條件選後端用 `map`,條件回退用 `try_files`。」

---

## 交叉引用

- **請求在 Nginx 內部經過哪些階段(phase:rewrite → access → content → log)、`if`/`rewrite` 為什麼是「rewrite 階段」指令**:↪ `gateway/02-request-pipeline.md`(那裡用「filter chain / 管線」抽象講透了階段順序與短路;本章只落地成 Nginx 的 `location`/`if`/`rewrite` 設定)。
- **引擎為什麼快(master-worker、epoll、worker 怎麼收連線)**:↪ `gateway/01-reverse-proxy-engine.md`,本章不重講。
- **`rewrite` 的 flag、`try_files` 回退鏈、命名 location、內部跳轉**:本章只把 `if`/替代方案點到,完整的「URI 改寫與內部跳轉」在下一章 ↪ `02-rewrite-and-internal-redirect.md`。
- **`add_header` 與 HSTS/安全頭的實戰**:↪ `07-tls.md`(會再用到本章的繼承陷阱)。

---

## 本章小結

- **區塊有作用域**:`main → events → http → server → location`,每層只放它被允許的指令;`http` 是定默認值的好地方。
- **指令繼承 = 向下繼承、就近覆蓋**,但繼承的是「值」不是「合併」。
- **`add_header` 陷阱**:子層只要出現任一條 `add_header`,就**丟掉父層全部 `add_header`**——不是逐條合併。對策:子層重抄 / `include` 公共片段 / 統一放同一層;安全頭記得加 `always`。
- **`location` 五檔優先級(背死)**:`=` 精確命中即停 > `^~` 最長前綴命中即停(**不再比正則**)> 正則 `~`/`~*` **按設定檔出現順序**第一個命中即停 > 最長前綴回退。
- **`root` vs `alias`**:`root` 拼整個 URI(保留 location 前綴),`alias` 替換 location 前綴;`alias` 的尾斜線要成對,否則路徑黏錯。
- **變數**:`$uri`(解碼、可被改寫,判當前路徑用)vs `$request_uri`(原始、含 query、不變,原樣轉發/記錄用);`$args`/`$arg_xxx`、`$host`(比 `$http_host` 穩)。
- **`if` is evil**:只對 `return`/`rewrite` 安全;選後端用 `map`,按存在性回退用 `try_files`。

## 章末問答(複習自檢,答案要點都在前面正文)

1. 一條 `proxy_read_timeout` 寫在 `http` 層、`server` 層沒寫、某個 `location` 寫了 `300s`,這個 location 用哪個值?「就近覆蓋」具體是什麼意思?

2. `server` 層寫了兩條安全用的 `add_header`,某個 `location` 裡又寫了一條 `add_header X-Request-Id ...`,這個 location 的回應會帶幾個頭?為什麼?要保住那兩個安全頭有哪幾種做法?

3. 把 `location` 五檔匹配優先級**從高到低**口述一遍。其中「`^~` 命中後不再比正則」這條,會讓哪一類請求出現「以為走正則、其實沒走」的反直覺結果?

4. **(命中題)** 給定以下四條 `location`:
   ```nginx
   location = /img/logo.png   { return 200 "W\n"; }
   location ^~ /img/          { return 200 "X\n"; }
   location ~* \.png$         { return 200 "Y\n"; }
   location /                 { return 200 "Z\n"; }
   ```
   請求 `GET /img/logo.png` 命中哪條?請求 `GET /img/banner.png` 命中哪條?請求 `GET /css/logo.png` 命中哪條?各說一句為什麼。
   <details><summary>對答案</summary>
   `/img/logo.png` → **W**(`=` 精確命中,最高檔立即停)。
   `/img/banner.png` → **X**(無精確;最長前綴 `^~ /img/` 命中 → 不比正則,所以不是 Y)。
   `/css/logo.png` → **Y**(無精確、無 `^~` 命中;最長前綴是 `/` 不帶 `^~` → 進正則,`\.png$` 命中 → Y,不是兜底 Z)。
   </details>

5. 同一個請求 `/static/app.css`,`location /static/` 下分別用 `root /data;` 和 `alias /data/files/;`,最終各映射到哪個磁碟路徑?`alias` 的尾斜線寫錯會發生什麼?

6. 為什麼說「`if` 只對 `return`/`rewrite` 安全」?要「依 query 參數選不同後端」和「檔案不存在時回退到 index.html」,分別該用什麼指令替代 `if`?
