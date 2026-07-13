# FastAPI 模塊日誌差異治理補充實施計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有 logging track 中補充一套以 FastAPI 片段示範的決策框架，讓讀者能依 verbosity、流量、去向、保存與安全差異選擇 level、filter、sampling、routing、retention 或 redaction。

**Architecture:** 唯一完整入口放在 `logging/05-配置讓它真的吐.md` 的 Python 段落，集中呈現決策表、四類場景與操作邊界。`01` 只修正 level 與動態調級定位，`07` 只修正面試提示與上線檢查，兩者連回 `05`，避免再次分散答案。

**Tech Stack:** Markdown、Python stdlib `logging` / `dictConfig`、FastAPI middleware、Uvicorn、HTTPX、SQLAlchemy、Git 文字校驗

## Global Constraints

- 只修改 `logging/01-日誌等級-rubric.md`、`logging/05-配置讓它真的吐.md`、`logging/07-面試自檢與落地清單.md`。
- 不修改 `logging/examples/python/`，不新增可運行服務、dependency 或管理 endpoint。
- 只用 FastAPI/Python 片段；不延伸 Go、Java 實作。
- `DEBUG`、`INFO`、`WARNING`、`ERROR` 在所有模塊保持一致 severity 語意；模塊重要性不得改寫 severity。
- 5xx、exception、慢請求與 audit 不進一般成功流量的 sampling。
- 動態調級只能描述成可選事故工具；必須提示 TTL、權限、審計與多 worker/副本一致性。
- 法規或財務 audit 必須指向 durable audit store / transactional outbox；application log 只能作查詢副本。
- 延續現有繁體中文、半形標點與「原理 → 範例 → 避坑 → 清單」文風。

---

### Task 1: 在 `05` 建立 FastAPI 模塊日誌治理主入口

**Files:**
- Modify: `logging/05-配置讓它真的吐.md:20-80`

**Interfaces:**
- Consumes: 現有 Python logger 階層、`getLogger(__name__)`、`propagate`、root-only handler 與 `dictConfig` 說明
- Produces: 主節標題「真實場景：FastAPI 不同模塊，不只靠 level」，供 Task 2 的 `01`、`07` 引用

- [ ] **Step 1: 記錄新增內容目前不存在**

Run:

~~~bash
rg -n '真實場景：FastAPI 不同模塊|severity 與 policy|AccessPolicyFilter|channel=audit|transactional outbox' logging/05-配置讓它真的吐.md
~~~

Expected: 無輸出，退出碼為 1。

- [ ] **Step 2: 在 Python 段落後插入完整治理主節**

在 `basicConfig()` 陷阱段落之後、`## 三、Go` 之前插入：

~~~~markdown
### 真實場景：FastAPI 不同模塊，不只靠 level

#### 先分清 severity 與 policy

不同模塊可以有不同的**日誌 policy**，但不應有不同的 **severity 語意**。`ERROR` 在 payment、order、auth 都表示「某項功能未能完成，需要處理」；不能因為 payment 比較重要，就把正常成功事件升成 `ERROR`。

真正需要分開控制的是：

| 差異或問題 | 首選機制 | FastAPI 場景 | 不該怎麼做 |
|---|---|---|---|
| 診斷細節不同 | logger namespace + selective level override | 只把 `app.payment` 臨時開到 `DEBUG` | 全服務永久 `DEBUG` |
| access log 流量太大 | filter + sampling/rate limit | 2xx 採樣，5xx 與慢請求全留 | 把正常 request 改記成 `WARNING` |
| 第三方 library 太吵 | dependency logger threshold | `httpx`、`sqlalchemy.engine` 設 `WARNING` | 修改第三方事件 severity |
| 日誌去向不同 | named logger + handler/collector routing | `app.audit` 送受保護 index | 靠 message 字串猜來源 |
| 保存期限不同 | channel + backend retention | audit 長期、access 短期 | FastAPI request path 自管 rotation |
| 資料敏感 | allowlist + redaction + ACL | token、cookie、密碼永不輸出 | 以關閉 `DEBUG` 代替遮罩 |
| 單次事故排障 | scoped override / trace filter | 放大指定 namespace 或 `trace_id` | 公開、永久的 `setLevel` endpoint |

一句話：**level 只控制 verbosity；filter 控制哪些事件留下；handler/collector 控制送去哪；backend 控制保存與權限。**

#### 1. 業務模塊：用 namespace 表達來源

每個模塊只取得自己的 logger，提交正確 severity、穩定事件名與必要 context：

```python
# app/payment/service.py
import logging

log = logging.getLogger(__name__)  # app.payment.service


def mark_payment_succeeded(order_id: str, gateway: str) -> None:
    log.info(
        "payment succeeded",
        extra={
            "event_name": "payment_succeeded",
            "order_id": order_id,
            "gateway": gateway,
        },
    )
    log.debug(
        "payment decision details",
        extra={
            "event_name": "payment_decision_debug",
            "order_id": order_id,
        },
    )
```

`app.order` 等其他業務模塊沿用 `getLogger(__name__)`，平時繼承 root 的 `INFO`。只有事故範圍已確認在 payment 時，才用版本化配置把 `app.payment` 改成 `DEBUG`：

```python
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"handlers": ["stdout"], "level": "INFO"},
    "loggers": {
        "app.payment": {"level": "INFO"},  # 事故期間才改 DEBUG
        "httpx": {"level": "WARNING"},
        "sqlalchemy.engine": {"level": "WARNING"},
    },
}
```

注意 handler 的門檻是 `DEBUG`：child logger 顯式開 `DEBUG` 後，record 冒泡到 root handler 時才能輸出。root logger 的 `INFO` 不會重新過濾已由 child logger 接受的 record；祖先 handler 自己的 level 才會再過濾（見本章第六節）。

#### 2. Access log：按事件特性採樣，不扭曲 severity

需要結構化欄位、慢請求規則或 sampling 時，可停用 Uvicorn 預設 access log，由 middleware 發出一條 `app.access` request summary：

```python
# app/logging.py
import hashlib
import logging


class AccessPolicyFilter(logging.Filter):
    def __init__(self, sample_rate: float = 0.1, slow_ms: float = 1000.0):
        super().__init__()
        self.sample_rate = sample_rate
        self.slow_ms = slow_ms

    def filter(self, record: logging.LogRecord) -> bool:
        status_code = int(getattr(record, "status_code", 0))
        duration_ms = float(getattr(record, "duration_ms", 0.0))
        route = str(getattr(record, "route", ""))

        if status_code >= 500 or duration_ms >= self.slow_ms:
            return True
        if 400 <= status_code < 500:
            return True
        if route in {"/healthz", "/readyz"}:
            return False

        request_id = str(getattr(record, "request_id", ""))
        if not request_id:
            return True  # 缺採樣鍵時保守保留，避免靜默丟失

        digest = hashlib.blake2b(
            request_id.encode("utf-8"), digest_size=8
        ).digest()
        bucket = int.from_bytes(digest, "big") / 2**64
        return bucket < self.sample_rate
```

```python
# app/main.py
import logging
import time

from fastapi import FastAPI, Request

app = FastAPI()
access_log = logging.getLogger("app.access")


@app.middleware("http")
async def access_summary(request: Request, call_next):
    started = time.monotonic()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route_object = request.scope.get("route")
        route = getattr(route_object, "path", request.url.path)
        access_log.info(
            "request completed",
            extra={
                "event_name": "http_request_completed",
                "request_id": getattr(
                    request.state,
                    "request_id",
                    request.headers.get("x-request-id", ""),
                ),
                "method": request.method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(
                    (time.monotonic() - started) * 1000, 1
                ),
            },
        )
```

Filter 只掛 `app.access` 的 handler，不能掛 root，否則會誤採樣業務、exception 與 audit：

```python
"filters": {
    "access_policy": {
        "()": "app.logging.AccessPolicyFilter",
        "sample_rate": 0.1,
        "slow_ms": 1000.0,
    }
},
"handlers": {
    "access_stdout": {
        "class": "logging.StreamHandler",
        "level": "INFO",
        "filters": ["access_policy"],
        "formatter": "json",
        "stream": "ext://sys.stdout",
    }
},
"loggers": {
    "app.access": {
        "handlers": ["access_stdout"],
        "level": "INFO",
        "propagate": False,
    }
},
```

此 middleware 的 500 summary 仍是 access 事件，不取代全域 exception handler 的 `ERROR + stack trace`。部署時二選一：

- 保留 `uvicorn.access`，在中央配置單獨調整它；
- 使用 `uvicorn --no-access-log`，改由上述 middleware 產生結構化 access event。

兩者同時開會讓每個 request 記兩次。

#### 3. 第三方 library：只調它的 namespace

`httpx`、`sqlalchemy.engine` 等第三方 logger 在中央 `dictConfig` 設門檻，不在業務模塊呼叫 `setLevel()`。SQLAlchemy 已由 logging config 管理時，保持 `echo=False`；`echo=True` 會額外配置輸出，容易產生重複日誌。

事故若需要 SQL 細節，只調 `sqlalchemy.engine`；事故結束恢復原值。不要把 root 改成 `DEBUG`，否則所有 framework/library 一起放大。

#### 4. Audit/security：分流，但別冒充可靠帳本

普通安全事件可用獨立 logger 與 allowlist 欄位：

```python
import logging

audit_log = logging.getLogger("app.audit")


def record_refund_approved(
    actor_id: str, order_id: str, refund_id: str
) -> None:
    audit_log.info(
        "refund approved",
        extra={
            "event_name": "refund_approved",
            "channel": "audit",
            "actor_id": actor_id,
            "order_id": order_id,
            "refund_id": refund_id,
        },
    )
```

```python
"handlers": {
    "audit_stdout": {
        "class": "logging.StreamHandler",
        "level": "INFO",
        "formatter": "json",
        "stream": "ext://sys.stdout",
    }
},
"loggers": {
    "app.audit": {
        "handlers": ["audit_stdout"],
        "level": "INFO",
        "propagate": False,
    }
},
```

Collector 依 `channel=audit` 路由到受限 index，backend 設獨立 retention 與 ACL。欄位採 allowlist；token、cookie、密碼、完整 request body 不得進日誌。

若 audit 是法規、財務或「業務成功必須留下證據」的記錄，不能只靠 best-effort application log。這類事件應寫 transactional outbox 或 durable append-only audit store，日誌只作查詢副本。

#### 處理流程與失敗邊界

```text
FastAPI module
  → named logger
  → effective severity threshold
  → filter（sampling / redaction）
  → handler / stdout
  → collector routing
  → index / retention / ACL
```

- 業務代碼負責 severity、`event_name` 與 context；
- logging config 負責 level、filter、handler；
- collector/backend 負責 routing、retention 與 ACL；
- filter 使用 `getattr(record, field, default)`，缺欄位不可令 request 失敗；
- exception、5xx、慢請求與 audit 不進一般 2xx sampling；
- 不在 request path 使用同步 remote handler；collector 丟失或積壓另用 metric/alert 監控。

#### 動態調級：可選事故工具，不是基線

基線做法是版本化 config/env 加 rolling restart。只有不能重啟且排障 SLA 確有需要，才提供 runtime override；此時必須具備 logger/level allowlist、管理權限、審計、TTL 自動恢復與手動回滾。

Uvicorn 多 worker 與多個容器副本各有獨立進程記憶體。單次 `logger.setLevel()` 只修改收到請求的 worker，不會自動同步其他 worker/副本；沒有集中配置或廣播時，不能宣稱已完成生產級動態調級。

#### 常見反例

- 每個模塊自己掛 handler、自己 `setLevel()`；
- 用 `ERROR` 表達「這個模塊很重要」；
- 為壓低成本而採樣 5xx、exception 或 audit；
- 用關閉 `DEBUG` 代替敏感資料遮罩；
- 同時保留 `uvicorn.access` 與自訂 access middleware；
- 把普通 application log 當成法規 audit 的唯一證據。

#### 官方依據

- [Python Logger Objects](https://docs.python.org/3/library/logging.html#logger-objects)：logger hierarchy、`getLogger(__name__)`、effective level 與 propagation。
- [Python logging.config](https://docs.python.org/3/library/logging.config.html#logging-config-dictschema)：逐 logger 的 level、handler、filter 與 `propagate` 配置。
- [Uvicorn Logging Settings](https://www.uvicorn.org/settings/#logging)：`--log-config`、`--log-level` 與 `--no-access-log`。
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/#built-in)：`--workers` 啟動多個獨立進程。
- [SQLAlchemy Configuring Logging](https://docs.sqlalchemy.org/en/20/core/engines.html#configuring-logging)：`sqlalchemy.engine` / `sqlalchemy.pool` namespace 與 `echo` 的互動。

以上官方資料支撐 logging 機制；sampling、routing、retention 與 audit 邊界是本章基於這些機制整理的工程治理建議。
~~~~

- [ ] **Step 3: 驗證主節結構與四類場景齊全**

Run:

~~~bash
rg -n '真實場景：FastAPI 不同模塊|先分清 severity 與 policy|業務模塊：用 namespace|Access log：按事件特性採樣|第三方 library：只調它的 namespace|Audit/security：分流|處理流程與失敗邊界|動態調級：可選事故工具|常見反例|官方依據' logging/05-配置讓它真的吐.md
~~~

Expected: 十個標題各匹配一次，依正文順序出現。

Run:

~~~bash
rg -n 'AccessPolicyFilter|status_code >= 500|duration_ms >= self.slow_ms|channel=audit|transactional outbox|uvicorn --no-access-log|sqlalchemy.engine|TTL 自動恢復|獨立進程記憶體' logging/05-配置讓它真的吐.md
~~~

Expected: access sampling、audit durable 邊界、Uvicorn 二選一、第三方 logger 與動態調級限制全部匹配。

- [ ] **Step 4: 驗證 Markdown 與變更邊界**

Run:

~~~bash
awk '/^```/{n++} END {print "code_fences=" n; exit n%2}' logging/05-配置讓它真的吐.md
git diff --check -- logging/05-配置讓它真的吐.md
git diff --name-only
~~~

Expected:

- `awk` 顯示偶數個 code fences 且退出碼為 0；
- `git diff --check` 無輸出，退出碼為 0；
- `git diff --name-only` 包含 `logging/05-配置讓它真的吐.md`；既有非本任務修改可存在，但不能被 stage。

- [ ] **Step 5: 只提交 `05` 主節**

~~~bash
git add logging/05-配置讓它真的吐.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs(logging): add FastAPI log policy guide"
~~~

Expected: staged name 只有 `logging/05-配置讓它真的吐.md`；commit 成功。

### Task 2: 對齊 `01`、`07` 的動態調級定位

**Files:**
- Modify: `logging/01-日誌等級-rubric.md:104-109,170-176`
- Modify: `logging/07-面試自檢與落地清單.md:37-38,48-53`

**Interfaces:**
- Consumes: Task 1 的主節名稱「真實場景：FastAPI 不同模塊，不只靠 level」與受控動態調級條件
- Produces: 三章一致的面試答案與上線清單，不再把公開 `setLevel` endpoint 描述為標準必備

- [ ] **Step 1: 確認舊表述仍存在**

Run:

~~~bash
rg -n '能動態調等級.*關鍵能力|Python 暴露一個內部端點|有能力.*不重啟把某模組|把某模組臨時開到 DEBUG|能.*不重啟.*某模組臨時開 DEBUG' logging/01-日誌等級-rubric.md logging/07-面試自檢與落地清單.md
~~~

Expected: `01` 的動態調級段落與落地清單、`07` 的 Q10 與上線清單均有匹配。

- [ ] **Step 2: 改寫 `01` 的原理段落與落地清單**

將 `01` 目前從「能動態調等級」到「不用為了一次 debug 重新部署」的引用區塊替換為：

~~~markdown
> 🔬 **動態調等級是可選的事故排障工具，不是所有服務的必備能力。**
>
> 基線做法是用版本化 config/env 設定 root 與少數 logger override，透過 rolling restart 生效。只有不能重啟且排障 SLA 確有需要，才提供 runtime override。
>
> Runtime override 若存在，必須限制 logger namespace 與 level、驗證管理權限、記錄審計、設定 TTL 自動恢復，並同步所有 worker/副本。Python 單一進程中的 `logger.setLevel(...)` 只改該進程，不能視為多 worker 生產方案。
>
> 另外，level 只控制 verbosity。不同模塊的 sampling、routing、retention 與 redaction 應使用 filter、handler/collector 與 backend policy；詳見 `05` 的「FastAPI 不同模塊，不只靠 level」。
~~~

把落地清單中的：

~~~markdown
- [ ] prod 門檻設 **INFO**;有能力**不重啟把某模組臨時開到 DEBUG**(LevelVar / actuator / 內部端點)。
~~~

替換為：

~~~markdown
- [ ] prod 有明確 root 預設與少數 logger override；具備受控排障策略。Runtime override 若存在，須有權限、審計、TTL 與跨 worker/副本同步。
~~~

- [ ] **Step 3: 改寫 `07` 的面試提示與上線清單**

保留 Q10 問題，將提示替換為：

~~~markdown
> 提示:先用版本化 config/env 對目標 logger 做 override，再以 rolling restart 生效，這已是可接受的生產基線。若排障 SLA 要求不重啟，runtime override 才是進階選項；必須有 namespace/level allowlist、權限、審計、TTL 自動恢復，並同步所有 worker/副本。不同模塊若是流量、去向、保存或安全要求不同，應改用 sampling、routing、retention 或 redaction，而不是一律調 level（見 `05`「FastAPI 不同模塊，不只靠 level」）。
~~~

將「等級」清單中的：

~~~markdown
- [ ] prod 門檻 = INFO;能**不重啟**把某模組臨時開 DEBUG。
~~~

替換為：

~~~markdown
- [ ] prod 有 root 預設與少數 logger override；具備受控排障策略，且不以 level 代替 sampling、routing、retention 或 redaction。
~~~

- [ ] **Step 4: 驗證舊承諾已清理，新邊界三章一致**

Run:

~~~bash
rg -n '能動態調等級.*關鍵能力|Python 暴露一個內部端點|有能力.*不重啟把某模組|能.*不重啟.*某模組臨時開 DEBUG' logging/01-日誌等級-rubric.md logging/07-面試自檢與落地清單.md
~~~

Expected: 無輸出，退出碼為 1。

Run:

~~~bash
rg -n '可選的事故排障工具|版本化 config/env|TTL 自動恢復|跨 worker/副本同步|受控排障策略|sampling、routing、retention.*redaction|FastAPI 不同模塊，不只靠 level' logging/01-日誌等級-rubric.md logging/05-配置讓它真的吐.md logging/07-面試自檢與落地清單.md
~~~

Expected:

- `01` 包含可選事故工具、版本化配置、TTL、多 worker 與主節引用；
- `05` 包含完整決策框架；
- `07` 包含受控排障策略、非 level 機制與主節引用。

- [ ] **Step 5: 逐段複讀並驗證 Markdown**

Run:

~~~bash
sed -n '96,116p' logging/01-日誌等級-rubric.md
sed -n '168,180p' logging/01-日誌等級-rubric.md
sed -n '34,56p' logging/07-面試自檢與落地清單.md
awk '/^```/{n++} END {print "01_code_fences=" n; exit n%2}' logging/01-日誌等級-rubric.md
awk '/^```/{n++} END {print "07_code_fences=" n; exit n%2}' logging/07-面試自檢與落地清單.md
git diff --check -- logging/01-日誌等級-rubric.md logging/07-面試自檢與落地清單.md
~~~

Expected:

- `01` 閱讀順序為 level 用途 → 動態調級定位 → level 以外的 policy → 過濾機制；
- `07` 的 Q10 與上線清單使用相同基線與進階條件；
- 兩份文件 code fences 為偶數，diff check 無錯。

- [ ] **Step 6: 只提交 `01`、`07`**

~~~bash
git add logging/01-日誌等級-rubric.md logging/07-面試自檢與落地清單.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs(logging): align log override guidance"
~~~

Expected: staged names 只有 `logging/01-日誌等級-rubric.md`、`logging/07-面試自檢與落地清單.md`；commit 成功。

- [ ] **Step 7: 最終驗證完整變更**

Run:

~~~bash
git show --stat --oneline HEAD~1..HEAD
git diff HEAD~2..HEAD --check
git diff --name-only HEAD~2..HEAD
rg -n '真實場景：FastAPI 不同模塊|severity 與 policy|AccessPolicyFilter|channel=audit|transactional outbox|可選的事故排障工具|受控排障策略' logging/01-日誌等級-rubric.md logging/05-配置讓它真的吐.md logging/07-面試自檢與落地清單.md
~~~

Expected:

- 最近兩個 task commits 只修改 `01`、`05`、`07`；
- diff check 無錯；
- 主節、四類治理關鍵字、audit 邊界與動態調級修正文案全部存在。

Run:

~~~bash
git status --short
~~~

Expected: 本計畫三份文件無未提交修改；使用者原有的其他 working-tree 修改可繼續存在。
