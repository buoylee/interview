# Scenario: <一句話描述>

> 複製這個檔案到對應章節的 `scenarios/` 下,改 filename 為 `NN-short-slug.md`(NN 是兩位數順序)。

## 我想驗證的問題
<一句話。例如:「broker 從 ISR 被踢出需要多久?期間 producer acks=all 會怎樣?」>

## 預期(寫實驗前的假設)
<一段話。把你「以為」的行為寫下來。⚠️ 這段必須在跑實驗之前寫完,不可以在「實機告訴我」之後回頭改。>

## 環境
- compose: `00-lab/docker-compose.yml`
- topic: `make topic NAME=<name> PARTS=<n> RF=<n>`
- 額外設定: <例如 `min.insync.replicas=2`,在 topic 創建後用 `kafka-configs.sh` 改>

## 觸發步驟
1. <步驟 1,精確到 make 指令>
2. <步驟 2>
3. ...

## 觀察點(指標 + 日誌)
- Grafana 面板:<panel 名> — 預期看到什麼
- Prometheus 查詢:`<promql>` — 預期看到什麼
- Broker 日誌:`make logs kafka-N | grep <pattern>` — 預期看到什麼
- Producer/Consumer 端:預期會不會拋異常,什麼異常

## 實機告訴我(跑完才填)
- <觀察點 1>: <實際數值/截圖路徑/日誌片段>
- <觀察點 2>: ...
- ✅ / ❌ 我預期對嗎?<哪裡對、哪裡錯>
- ⚠️ <如果預期錯了,把錯誤的那一條單獨高亮 — 這是這個 scenario 的核心知識增量>

## 一句話結論(將來要進面試卡的)
<跑完才填,格式建議:「<前置條件> 下,<行為>,<量化>」>
<例:「acks=all + min.insync.replicas=2 在 RF=3 集群下,單 broker 隔離不會阻塞寫入,ISR 收縮在 ~10s 後發生」>

## 延伸問題(下次補)
- <讓 future-me 知道這條線還能往哪挖>
