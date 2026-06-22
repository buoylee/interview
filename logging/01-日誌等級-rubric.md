# 01 · 日誌等級 rubric(3am 會不會被叫醒)

> 治的症狀:**「等級不夠看不到」**(太少端)和**「一長串都是雜訊」**(太多端)。
> 這兩個其實是**同一個病**:等級沒分對,所以你沒辦法用一個門檻同時「留下重要的、擋掉吵的」。

---

## 一、原理:等級是給「未來的讀者」分的,不是給「現在的你」分的

新手最大的誤解:**把等級當成「這條對我有多重要」**。於是自己在乎的就 `INFO`、不在乎的就 `DEBUG`——結果線上全是 `INFO`,門檻調不動。

正確的心智模型:**等級是「嚴重程度 severity」,回答的是「未來誰、在什麼情況下,需要看到這條」。**

一個會分級的工程師,腦中有這把尺(由重到輕):

| 等級 | 一句話定義 | 判準問題 | 線上預設看不看得到 |
|---|---|---|---|
| **FATAL/CRITICAL** | 程式無法繼續、要掛了 | 「進程是不是要死了?」 | 看得到 |
| **ERROR** | 一件事**失敗了,而且需要人介入** | **「3am 我願意為這條被叫醒嗎?」** | 看得到 |
| **WARN** | 降級 / 可疑 / 自己恢復了,但值得注意 | 「系統撐住了,但有點不對勁?」 | 看得到 |
| **INFO** | 正常但重要的事件,系統的**行為足跡** | 「事後要還原『系統做了什麼』時需要嗎?」 | **看得到(prod 預設地板)** |
| **DEBUG** | 開發者診斷用的細節 | 「平常不用看,出事時想打開來追?」 | 預設**關**,可動態開 |
| **TRACE** | 消防水管:逐筆、逐迴圈、wire dump | 「我要看到每一個細節?」 | 預設**關** |

### 兩把最好用的判準尺

**① ERROR 的尺:3am 測試。**
> 「如果這條在凌晨三點觸發,我願意被 call 醒去處理嗎?」
> 願意 → `ERROR`(它應該能觸發告警)。
> 不願意(系統自己處理掉了、不需要人動作)→ 那它是 `WARN` 或 `INFO`,**不是 ERROR**。

這把尺直接解決最常見的線上慘劇:**所有 except 都記 ERROR**,於是告警天天響、狼來了喊到沒人理,真正的 ERROR 被淹沒。「使用者輸入了非法參數、我回 400」——這**不是 ERROR**,這是系統正常運作(`INFO` 或 `WARN`),沒人需要半夜起來。

**② INFO 的尺:還原現場測試。**
> 「事後要重建『這個請求/這個系統做了什麼』時,我會需要這條嗎?」
> 會 → `INFO`(請求進出、狀態轉換、業務里程碑如「訂單成立」)。
> 不會,只是開發時想看的中間值 → `DEBUG`。

`INFO` 是**生產環境的地板**:它是你的稽核足跡,平時就開著。`DEBUG` 是地板以下,平時關著、出事才打開。**這個「地板」設計能成立的前提,就是你有把該 INFO 的記成 INFO、該 DEBUG 的記成 DEBUG** —— 否則你想關 DEBUG 降噪,結果把重要的也關掉了(因為它們也被你記成 DEBUG)。

---

## 二、三語言並排:等級長什麼樣、怎麼設門檻

三語言的「階梯」概念一樣,只是級數和名字略有出入:

| 概念 | Python `logging` | Go `log/slog` | Java SLF4J |
|---|---|---|---|
| 最嚴重 | `CRITICAL` (50) | (無內建,自訂) | (無內建;Log4j2 有 `FATAL`) |
| 失敗要人管 | `ERROR` (40) | `LevelError` (8) | `ERROR` |
| 可疑/降級 | `WARNING` (30) | `LevelWarn` (4) | `WARN` |
| 正常足跡 | `INFO` (20) | `LevelInfo` (0) | `INFO` |
| 診斷細節 | `DEBUG` (10) | `LevelDebug` (-4) | `DEBUG` |
| 消防水管 | (無;自訂) | (無;自訂) | `TRACE` |

> 注意三件事:① Python 用 `CRITICAL` 不是 `FATAL`;② Go `slog` 只有四級,而且是**整數刻度**(Info=0),你可以插自訂級(例如 `LevelInfo+2` 當 "NOTICE");③ Go/slog 沒有內建 TRACE,Python 沒有內建 TRACE/FATAL —— 需要時自己定義。

### 怎麼設「門檻」(只放行 ≥ 某級)

**Python**

```python
import logging

logger = logging.getLogger("myapp")
logger.setLevel(logging.INFO)        # 門檻:INFO 以上才處理,DEBUG 被擋

logger.info("order placed", extra={"order_id": 1001})   # 放行
logger.debug("raw payload=%s", payload)                  # 被擋掉(看不到)
```

**Go(`log/slog`)**

```go
import (
    "log/slog"
    "os"
)

h := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,           // 門檻:Info 以上才輸出
})
logger := slog.New(h)

logger.Info("order placed", "order_id", 1001)   // 放行
logger.Debug("raw payload", "body", payload)     // 被擋掉
```

**Java(`logback.xml`,設定檔分級,程式碼不碰門檻)**

```xml
<configuration>
  <logger name="com.myapp" level="INFO"/>   <!-- 門檻在設定檔,可不重啟改 -->
</configuration>
```

```java
private static final Logger log = LoggerFactory.getLogger(OrderService.class);

log.info("order placed, orderId={}", 1001);   // 放行
log.debug("raw payload={}", payload);          // 被擋掉
```

> 🔬 **「能動態調等級」是線上 debug 的關鍵能力。** 三語言都支援不重啟改門檻:
> - Java/Logback 監看 `logback.xml`(`scan="true"`)或用 `/actuator/loggers` 端點動態調某個 logger 到 DEBUG。
> - Go 用 `slog.LevelVar`(一個可原子更新的 level 變數)接到一個 HTTP 端點,線上拉桿。
> - Python 暴露一個內部端點呼叫 `logger.setLevel(...)`。
>
> 這就是「平時 INFO、出事把某個模組臨時開到 DEBUG 撈完再關」的做法 —— 不用為了一次 debug 重新部署。面試被問「線上問題但日誌不夠細怎麼辦」,答這個。

---

## 三、🔬 內幕:level 過濾到底在哪一步發生?(關係到效能)

很多人以為「`log.debug(...)` 反正被擋掉就不花錢」。**錯一半。** 過濾確實會短路,但**參數在呼叫前就已經算好了**:

```python
log.debug("user=%s", expensive())   # expensive() 一定被呼叫!即使 DEBUG 被擋
```

過濾的順序是:**先組好引數 → 進 `logger.debug` → 才檢查 `isEnabledFor(DEBUG)` → 不過就丟掉**。所以「被擋掉」省的是**格式化字串 + 寫 IO** 的錢,**沒省**「算引數」的錢。

三語言的短路檢查點:
- Python:`logger.isEnabledFor(level)`,`debug()` 內部會先問它。
- Go slog:`logger.Enabled(ctx, level)`,handler 在真正處理前判斷。
- Java SLF4J:`log.isDebugEnabled()`,或靠 `{}` 佔位符延遲字串拼接。

**這就是為什麼用「參數化」而不是「字串拼接」**(`06` 章詳談):

```python
log.debug("user=%s", user)        # ✅ 被擋時不拼字串
log.debug(f"user={user}")          # ❌ f-string 在進函式前就拼好了,白花錢
```

但注意:參數化只省「拼字串」,省不了「算 `expensive()`」。真要省,得自己 `if log.isEnabledFor(DEBUG)` 包起來(或 Go 的 `LogValuer`、Java 的 `Supplier`)。

---

## 四、反例(你十之八九中過)

**反例 1:所有 except 都記 ERROR。**

```python
try:
    user = get_user(uid)
except UserNotFound:
    log.error("user not found")    # ❌ 使用者查無此人是「正常業務」,不是該叫醒人的 ERROR
    return 404
```
→ 結果:ERROR 告警天天響、狼來了,真正的 ERROR 被淹。
✅ 改成 `log.info("user not found, uid=%s", uid)`(或 WARN),把 ERROR 留給「真的需要人介入」的失敗(DB 連不上、下游 5xx)。

**反例 2:所有東西都記 INFO。**
→ prod 的 INFO 變成雜訊海,你想降噪只能升到 WARN,結果連「訂單成立」這種要留的足跡都看不到了。
✅ 嚴格區分:**要還原現場的 → INFO;開發時才想看的中間值 → DEBUG**。讓你能靠調門檻控制噪音。

**反例 3:把 WARN 當「我比較在乎的 INFO」。**
→ WARN 變成情緒分級(「這個我覺得重要」),失去「系統撐住了但不對勁」的明確語意,沒人知道該不該管。
✅ WARN 的語意很窄:**降級、retry 後才成功、用了 fallback、逼近限制、用了 deprecated 路徑**。

**反例 4:`log.error` 之後沒有任何上下文。**
```java
log.error("save failed");   // ❌ 哪個 user?哪筆訂單?什麼錯?
```
→ 你看到了等級對的 ERROR,但還是 debug 不了。
✅ 等級對只是第一步,還要帶上下文與堆疊(→ `03`、`04`)。

---

## 五、這章的落地清單

- [ ] 心裡有那把尺:FATAL > ERROR > WARN > INFO > DEBUG > TRACE,且知道每級**一句話定義**。
- [ ] 每次寫 `log.error` 前過一次「**3am 我願意為這條被叫醒嗎?**」——不願意就降級。
- [ ] 每次寫 `log.info` 前過一次「**事後還原現場我需要它嗎?**」——只是中間值就降 DEBUG。
- [ ] prod 門檻設 **INFO**;有能力**不重啟把某模組臨時開到 DEBUG**(LevelVar / actuator / 內部端點)。
- [ ] DEBUG 用參數化(`"%s"`/`"{}"`/slog kv),不用 f-string / 字串拼接。

---

> 下一章 `02`:等級對了,但**該在哪些位置記、記什麼內容**?這章解決「沒日誌」和「一長串」—— 因為這兩個都是「記錯位置」的後果。
