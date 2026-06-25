# lab/config-matching — location 優先級 + rewrite 命中實測

> 對照章節:`nginx/01-config-model.md`(location 優先級)、`nginx/02-rewrite-and-internal-redirect.md`(rewrite flag)

## 目的

把 ch01/ch02 的「紙上規則」變成看得見的 HTTP 行為:
每個 `location` 區塊回應 `matched: <name>`,讓你親眼確認哪條規則贏。

---

## 如何執行

```bash
# 啟動容器(對外 18080)
docker compose up -d
sleep 3

# 發請求 + 斷言
bash run.sh

# 清理
docker compose down -v
```

---

## 預期命中表

| 請求路徑 | 命中 location | 優先級規則 | 預期回應 |
|---|---|---|---|
| `/exact` | `= /exact` | 精確比對(最高,命中即停) | `matched: exact` |
| `/prefix-stop/x` | `^~ /prefix-stop/` | 前綴非正則(命中即停,不再看正則) | `matched: prefix-stop` |
| `/a.JPG` | `~* \.(jpg\|png)$` | 大小寫不敏感正則 | `matched: regex-image` |
| `/api/users` | `~ ^/api/` | 大小寫敏感正則(按順序,先到先得) | `matched: regex-api` |
| `/whatever` | `/`(一般前綴兜底) | 無正則命中回退最長前綴 | `matched: longest-prefix` |
| `/old/thing` | `/new/`(rewrite 後重走) | `rewrite ... last` 改 URI 後重走 location | `matched: new` |

---

## 優先級規則速查(對照 ch01)

```
= (精確)  >  ^~ (前綴止步)  >  ~/~* (正則,按出現順序)  >  最長一般前綴
```

重點細節:
- `^~ /prefix-stop/` 命中後**不再看後面的正則**,即使 `/prefix-stop/x.jpg` 也命中 `^~` 而非 `~*`。
- 正則是**按設定檔出現順序**,第一個命中即停——`~ ^/api/` 寫在 `~* image` 前,所以 `/api/foo.jpg` 命中 api 而非 image。
- `rewrite ... last` 改完 URI 後**重走整個 location 匹配流程**(`break` 則不會)。

---

## 預期輸出

```
/exact -> matched: exact
/prefix-stop/x -> matched: prefix-stop
/a.JPG -> matched: regex-image
/api/users -> matched: regex-api
/whatever -> matched: longest-prefix
/old/thing -> matched: new
ALL PASS
```
