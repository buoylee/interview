# Report/export Docker demo

這是一個可重跑的縮小實驗，用來觀察兩件事：buffered 與 chunked export 是否產生相同結果，以及 export 期間一個小型 OLTP counter 是否仍持續前進。它不是 benchmark，也不能代表 production capacity。

## 執行

```bash
cd mysql-handson/00-lab/senior-scenarios
./run-demo.sh test
./run-demo.sh run
./run-demo.sh cleanup
```

`test` 在 `--network none` 的 Python container 內執行 unit tests、compile 與 shell syntax checks。`run` 建立全新的 demo-only MySQL、network、data volume 和 runner；若同名資源已存在，它會要求先執行 `cleanup`，不會暗中覆寫。`cleanup` 只刪除帶有 `com.openai.codex.scope=mysql-senior-demo` label 的五個固定名稱資源。

需要查看狀態時可執行：

```bash
./run-demo.sh inspect
```

## 固定資料量

- `10,000` 筆 orders
- 每張 order 恰好 `3` 筆 items，共 `30,000` 筆
- `1,000` 筆可寫入的 OLTP probe rows

報表資料在 export 期間不修改；OLTP worker 只更新獨立的 `oltp_probe`。這讓輸出正確性與「是否還有 OLTP progress」可以分開觀察。

## 比較內容

- buffered：用 `fetchall()` 把結果收進 client memory，再寫 TSV。
- chunked：用 `fetchmany(1000)` 分批寫 TSV，client memory 隨 batch size 有界。
- 兩者都使用相同 SQL 與 deterministic `ORDER BY`。
- 驗收比較 `30,000` rows、first/last key、檔案 SHA-256，以及兩段 export 前後的 OLTP counter delta。

`OLTP delta > 0` 只證明這個小型 demo 中 counter 有前進；它不等於 latency SLO，也不能證明大型報表對 production 沒有影響。

## macOS 邊界

Host 只執行 Git 與 Docker CLI：不執行或安裝 host Python、`uv`、`pip`、MySQL，不建立 host runtime/artifact directory，也不使用 writable bind mount。Python、MySQL、seed data 與 TSV artifacts 全部留在帶 scope label 的 Docker resources；`cleanup` 後 demo data 與 artifacts 一起消失。

所有 demo containers 固定限制為 `2 CPUs`、`2 GiB` memory、`256 PIDs`。它不會操作既有的 `mysql-primary` 或任何 `mysql-senior-scenarios-*` resource。
