# 02 · 副本層 (ISR / HW / LEO / min.insync.replicas)

## 我以為(理論層)

- ISR = "in-sync replicas",相對於 leader 落後不超過 `replica.lag.time.max.ms` 的 follower 集合
- HW (high watermark) = 所有 ISR 都已寫入的最高 offset,消費者只能讀到 HW
- LEO (log end offset) = 每個 replica 已寫入的最高 offset
- `min.insync.replicas` 是寫入端約束:`acks=all` 時,ISR 數量 < min.insync.replicas 會拋 `NotEnoughReplicasException`
- broker 掛掉/隔離 → ISR 收縮 → 如果 ISR 數量還夠,寫入繼續;不夠則寫入受阻

## 我想用實機回答的問題

| 問題 | scenario |
|---|---|
| broker 被網路隔離後 ISR 收縮要多久?寫入受影響嗎? | 01-isr-shrink-on-network-isolation |
| (待補) min.insync.replicas 觸發後,producer 看到什麼? | 02 |
| (待補) 同時掛兩個 broker 在 RF=3 下會怎樣? | 03 |
| (待補) unclean leader election 怎麼觸發、誰會被選? | 04 |
| (待補) HW 和 LEO 在實機上的滯後可以多大? | 05 |

## 章節進度

- [x] 01-isr-shrink-on-network-isolation
- [ ] 02-min-isr-trigger
- [ ] 03-double-broker-loss
- [ ] 04-unclean-leader-election
- [ ] 05-hw-leo-divergence

## 對應已有理論筆記

- `../../kafka/broker.md`(副本機制總覽)
- `../../kafka/kafka-消息防丢.md`(acks 與 ISR 的關係)
