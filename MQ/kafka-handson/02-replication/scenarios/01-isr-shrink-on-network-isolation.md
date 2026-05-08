# Scenario 01: broker-2 被網路隔離後 ISR 怎麼變化、producer acks=all 會怎樣

## 我想驗證的問題

當 broker-2 從集群網路斷開時:
1. ISR 從 3 收縮到 2 需要多久?
2. 在 ISR 還沒收縮的窗口內,producer (acks=all, min.isr=2) 是阻塞、超時還是繼續寫?
3. ISR 收縮後,producer 行為有變嗎?
4. 恢復 broker-2 後,它何時重新進 ISR?

## 預期(寫實驗前的假設)

我以為:

- ISR 收縮會在 `replica.lag.time.max.ms` (預設 30s,我這裡會調成 10s) 之後觸發。在這 10s 內,broker-1(leader)會持續嘗試把訊息推給 broker-2,直到 timeout 才把它踢出 ISR。
- 在這 10s 窗口內,producer 的 acks=all 寫入會**阻塞或變慢**,因為要等 ISR=3 的 ack。一旦超過 `request.timeout.ms` 會收到 timeout 異常。
- ISR 收縮到 2 之後,因為 min.insync.replicas=2,寫入會繼續正常進行(ack 只需要 leader + broker-3)。
- 恢復網路後,broker-2 需要追平 leader 的 LEO 才會重新進 ISR。追平時間取決於隔離期間積累的 lag。

## 環境

- compose: `00-lab/docker-compose.yml`(已起)
- topic: `make topic NAME=t-isr PARTS=3 RF=3`
- 額外設定:
  ```bash
  docker exec kafka-1 /opt/kafka/bin/kafka-configs.sh \
    --bootstrap-server kafka-1:9092 \
    --entity-type topics --entity-name t-isr \
    --alter --add-config min.insync.replicas=2
  ```
- broker 端 `replica.lag.time.max.ms` 改成 10000(這個改起來要 broker 重啟才生效,留作延伸實驗;先用預設 30000 跑一次,觀察 30s 收縮)

## 觸發步驟

1. **準備 topic 並確認初始 ISR=[1,2,3]**

   ```bash
   make topic NAME=t-isr PARTS=3 RF=3
   docker exec kafka-1 /opt/kafka/bin/kafka-configs.sh \
     --bootstrap-server kafka-1:9092 \
     --entity-type topics --entity-name t-isr \
     --alter --add-config min.insync.replicas=2
   make describe TOPIC=t-isr
   # 確認三個 partition 的 ISR 都是 [1,2,3]
   ```

2. **在背景持續寫入(終端 A)**

   ```bash
   make produce TOPIC=t-isr RATE=100
   # 留著別關
   ```

3. **打開 Grafana(瀏覽器)**

   http://localhost:3000/d/kafka-overview/kafka-overview-handson — 把時間視窗調成 last 5 min,refresh 5s

4. **記錄當下時間,然後隔離 broker-2(終端 B)**

   ```bash
   date "+%H:%M:%S"  # 記下來,例如 T0
   make chaos-isolate BROKER=2
   ```

5. **觀察 30~40 秒,記錄 ISR 收縮發生在 T0 + ?? 秒**

   邊看 Grafana 的 "Under-Replicated Partitions" 面板,邊觀察 producer 終端有沒有報錯。每 5 秒手動執行:

   ```bash
   make describe TOPIC=t-isr
   # 看 Isr 欄位什麼時候從 [1,2,3] 變成 [1,3] 之類
   ```

6. **恢復網路,記錄 broker-2 重進 ISR 的時間**

   ```bash
   date "+%H:%M:%S"  # T1
   make chaos-restore BROKER=2
   # 持續每 5 秒 describe,看 Isr 何時恢復成 [1,2,3]
   ```

7. **停止 producer(終端 A 按 Ctrl-C)**

## 觀察點(指標 + 日誌)

- **Grafana → Under-Replicated Partitions**:預期從 0 跳到 N(N = broker-2 持有的 partition 數,大概 1-2 個)
- **Grafana → ISR Shrinks / sec**:預期在 T0 + ~30s 出現一個尖峰
- **Grafana → Bytes In / sec**:預期 broker-2 的曲線歸 0,broker-1/3 維持寫入速率(因為 producer 持續送)
- **`make describe TOPIC=t-isr`**:每次跑都看 Isr 欄位變化
- **broker-1 log**:`make logs kafka-1 | grep -E "(Shrinking|Expanding) ISR"`,預期看到 `Shrinking ISR from 1,2,3 to 1,3`
- **producer 終端**:預期在收縮前的 30s 窗口內看到 `org.apache.kafka.common.errors.NotEnoughReplicasException` 或寫入延遲飆高;收縮後恢復正常

## 實機告訴我(跑完才填)

- ISR 從 [1,2,3] 收縮到 [1,3] 的實際時間:T0 + ____ 秒
- 在收縮窗口內 producer 行為:
- 收縮後 producer 行為:
- 恢復網路後 broker-2 重進 ISR 時間:T1 + ____ 秒
- broker-1 log 中收縮的關鍵行(貼上來):
- ✅ / ❌ 我預期對嗎?
- ⚠️ <寫下「我以為的」和「實機的」之間的最大落差 — 這是面試時最值錢的一句話>

## 一句話結論(將來要進面試卡的)

<跑完才填,格式:「<前置條件> 下,<行為>,<量化>」>

## 延伸問題(下次補)

- 把 `replica.lag.time.max.ms` 改成 5s,收縮速度會變快 5s 還是不變?
- 同時隔離 broker-2 和 broker-3 會怎樣(min.isr=2 觸發)?新 scenario 02。
- 如果在隔離期間 broker-1(leader)也掛掉,會選誰當 leader?新 scenario 04。
- 把 `acks=1` 改成 `acks=all`,producer 端 throughput 變化多大?屬於 04-producer 章節。
