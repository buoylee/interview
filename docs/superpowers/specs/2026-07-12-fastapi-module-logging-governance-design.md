# FastAPI 模塊日誌差異治理補充設計

## 背景

目前 `logging/` 已說明 Python logger 階層、`propagate`、`dictConfig` 與按 logger 設定 level，也提到事故期間把某個模塊臨時調到 `DEBUG`。但內容容易讓讀者得到兩個錯誤印象：不同模塊的日誌差異主要靠 level 解決，以及動態 `setLevel()` 是生產服務的必備能力。

真實場景中的差異還包括流量、輸出去向、保存期限、查詢維度與資料敏感度。補充內容需先分類問題，再選擇 level、filter、sampling、routing、retention 或 redaction；不能把所有差異壓成一個 severity threshold。

## 目標

- 用 FastAPI 程式片段說明不同模塊日誌差異的業界可行處理方式。
- 明確區分事件的 severity 語意與模塊的輸出 policy。
- 建立「先判斷差異類型，再選控制機制」的決策框架。
- 覆蓋業務模塊、access log、第三方 library、audit/security 四類場景。
- 修正現有章節對動態調級必要性的過度表述。

## 非目標

- 不修改或擴充 `logging/examples/python/` 可運行範例。
- 不建立 FastAPI 管理 endpoint、配置中心或跨 worker 廣播機制。
- 不把文檔片段包裝成完整 logging library。
- 不延伸 Go、Java 範例。
- 不以 application log 取代 metrics、alerting 或合規 audit store。

## 核心原則

### Severity 與 policy 分離

`DEBUG`、`INFO`、`WARNING`、`ERROR` 在整個服務中保持一致語意。模塊差異由獨立 policy 控制：最低輸出門檻、採樣率、handler、目的地、保存期限與資料遮罩。不能因為某個模塊比較重要，就把正常事件重新定義成 `ERROR`。

### 業務代碼只描述事件

FastAPI 業務模塊使用 `logging.getLogger(__name__)`，提交正確 severity、穩定 `event_name` 與必要 context。業務代碼不自行掛 handler、不自行設定 level，也不決定 backend retention。

### 中央配置與平台各自負責

- Python logging config：logger threshold、filter、handler 與 propagation。
- Collector：跨服務 routing、批次傳輸與失敗監控。
- Log backend：index、retention、ACL 與查詢。

## 決策框架

正文新增一張決策表：

| 差異或問題 | 首選機制 | FastAPI 場景 | 不應使用 |
|---|---|---|---|
| 診斷細節不同 | logger namespace + selective level override | `app.payment` 臨時 `DEBUG` | 全服務永久 `DEBUG` |
| access log 流量太大 | filter + sampling/rate limit | 2xx 採樣，5xx 與慢請求全留 | 把所有 access log 提到 `WARNING` |
| 第三方 library 太吵 | dependency logger threshold | `httpx`、`sqlalchemy.engine` 設 `WARNING` | 修改第三方訊息的 severity |
| 日誌去向不同 | named logger + handler/collector routing | `app.audit` 路由到受保護 index | 只靠 message 字串搜尋 |
| 保存期限不同 | channel + backend retention | audit 長期、access 短期 | 在 FastAPI request path 自管 rotation |
| 資料敏感 | allowlist + redaction + ACL | token、cookie、密碼永不輸出 | 以關閉 `DEBUG` 代替遮罩 |
| 單次事故排障 | scoped override 或 trace/request filter | 放大指定模塊或 `trace_id` | 公開、永久的 `setLevel` endpoint |

Level 仍是控制 verbosity 的正確工具，但只處理決策表中的一個維度。

## FastAPI 片段設計

### 1. 業務模塊

以 `app.payment.service` 與 `app.order.service` 示範 `logging.getLogger(__name__)`。root 提供環境預設，子 logger 平時繼承；只有確認需要時才對 `app.payment` 設 override。

片段需說明：child logger 若顯式允許 `DEBUG`，目的地 handler 的 level 不能再次把它攔掉。handler 仍集中配置，避免 propagation 造成重複輸出。

### 2. Access log

使用獨立 `app.access` logger 表達結構化 request summary。片段示範以 `status_code`、`duration_ms`、route template 等欄位作 policy：

- 5xx、exception、慢請求全部保留。
- 一般 2xx 才可採樣。
- health/readiness endpoint 可單獨降噪。
- sampling filter 只掛 access handler，不影響業務與 exception 日誌。

正文需說明兩種可行部署：保留並獨立配置 `uvicorn.access`；或停用預設 access log，改由 ASGI/FastAPI middleware 發出結構化 `app.access` 事件。不能同時保留兩者而造成一個 request 記兩次。

### 3. 第三方 library

在集中式 `dictConfig` 片段中設定 `httpx` 與 `sqlalchemy.engine` 的門檻。說明 SQLAlchemy `echo` 與顯式 logging config 不應同時開啟，以免重複輸出。事故期間的調整應限制在目標 namespace，而不是提高整個 root verbosity。

### 4. Audit/security

使用 `app.audit` logger 與穩定 `event_name` 示範 refund approval 等安全事件。事件欄位採 allowlist，不包含 token、cookie、密碼或完整 request body。

`app.audit` 可使用獨立 handler 並停止 propagation，collector 再依 `channel=audit` 路由到受限儲存。普通排障 audit/security log 可使用此方案；法規或財務證據必須走 transactional outbox 或 durable append-only audit store，application log 只作查詢副本。

## 資料流與錯誤邊界

```text
FastAPI module
  -> named logger
  -> effective severity threshold
  -> filter (sampling / redaction)
  -> handler / stdout
  -> collector routing
  -> index / retention / ACL
```

- Filter 讀取自訂 LogRecord 欄位時使用安全預設；缺少欄位不可令 request 失敗。
- Exception、5xx、慢請求與 audit 不進一般成功流量的 sampling 規則。
- Logging sink 或 collector 故障不得直接拖垮一般 FastAPI request path；丟失與積壓另以 metric/alert 監控。
- 合規上要求「業務成功必須伴隨 audit 成功」時，改用 durable event/outbox，不把同步 remote log handler 放進交易成功條件。

## 動態調級定位

動態調級改寫為可選 incident-response 工具，不是所有服務的基線要求。首選版本化配置加 rolling restart；只有不能重啟且排障 SLA 確有需要時，才建立 runtime override。

文檔僅列出安全條件，不提供 endpoint 實作：

- logger namespace 與 level allowlist；
- 管理權限與審計；
- TTL 自動恢復與手動回滾；
- Uvicorn 多 worker、容器副本間同步；
- 變更範圍與流量成本限制。

單一 worker 中呼叫 `logger.setLevel()` 只改該進程記憶體，不能描述成多 worker 生產服務的完整方案。

## 文件修改範圍

### `logging/05-配置讓它真的吐.md`

在 Python `dictConfig` 與 logger 階層內容後新增主節「FastAPI：不同模塊的差異，不只靠日誌等級」。放入決策表、四類片段、資料流、反例與操作邊界。此節是唯一完整入口。

### `logging/01-日誌等級-rubric.md`

把「能動態調等級是線上 debug 的關鍵能力」改為「可選事故工具」。補一句：level 控制 verbosity，routing、sampling、retention 與 redaction 應使用其他機制。連回 `05` 主節。

### `logging/07-面試自檢與落地清單.md`

把「必須不重啟把某模塊臨時開 DEBUG」改為「具備受控排障策略」。提示配置變更與 rolling restart 是可接受基線；runtime override 若存在，必須處理 TTL、權限、審計與多 worker 一致性。連回 `05` 主節。

## 官方依據

實作時引用並直接連結：

- Python `logging` logger hierarchy、`getLogger(__name__)`、propagation 與 handler level。
- Python `logging.config` 的逐 logger 配置與 incremental configuration 邊界。
- Uvicorn logging config、access log 與 multi-worker deployment。
- SQLAlchemy logger namespaces 與 `echo` 互動。

引用只支撐技術事實；具體治理建議明確標記為本項目基於這些機制整理的工程建議。

## 驗收標準

- 讀者能先判斷問題屬於 verbosity、流量、去向、保存或安全，再選擇控制機制。
- 正文明確說明 level 只控制 verbosity，不重新定義各模塊的 severity 語意。
- 業務、access、第三方、audit/security 四類 FastAPI 片段皆可獨立理解。
- Access 方案明確避免 Uvicorn access log 與自訂 middleware 雙重記錄。
- 5xx、exception、慢請求與 audit 不會被一般 2xx sampling 規則丟棄。
- 合規 audit 與 best-effort application log 的邊界清楚。
- 動態調級不再被描述為必備能力，也不暗示單進程 `setLevel()` 能同步所有 worker。
- `01`、`05`、`07` 對動態調級與模塊差異的說法互相一致。
- Markdown code fence、連結、logger namespace 與術語一致。
