# Kafka Hands-on — 實機白皮書

把 `MQ/kafka/` 的理論筆記在實機上跑過一遍,並沉澱成有結構的 scenario + 面試卡。

設計來源:`docs/superpowers/specs/2026-05-08-kafka-handson-design.md`

## 怎麼用這個 repo

1. **第一次來**:讀 `00-lab/` 下的 `Makefile` 注釋,然後 `cd 00-lab && make up`,等鏡像下完。瀏覽器打開 http://localhost:3000 看到 Grafana 有資料就算 lab OK 了。
2. **想答某個面試題**:先去 `99-interview-cards/` 找對應卡片;卡片會把每個論點鏈接到 scenario 文件,點過去看「實機告訴我」段。
3. **想學某個主題**:從章節 README 開始(每章開頭有「我以為」+ scenario 列表)。
4. **想加新 scenario**:複製 `templates/scenario-template.md` 到對應章節 `scenarios/` 下,**先寫「預期」、commit 一次**,再跑、再 commit 觀察結果。預期/實機分兩次 commit 是刻意的紀律。

## 章節地圖

- `01-storage/` — log / segment / index / page cache
- `02-replication/` — ISR / HW / LEO / min.insync.replicas ← **第一個有完整 scenario 的章節**
- `03-controller/` — KRaft controller、元數據傳播
- `04-producer/` — acks / idempotent / batch / linger
- `05-consumer/` — rebalance / assignor / offset / lag
- `06-transaction/` — exactly-once / 跨 partition 事務
- `07-ops/` — partition reassignment / quota / 滾動升級
- `99-interview-cards/` — 反向打包的面試題答案卡

## Lab 速查

```bash
cd 00-lab

make up                              # 起整套(第一次會下載 JMX agent + docker images)
make down                            # 停掉
make reset                           # 連 volume 一起清,回到初始狀態
make ps                              # 看哪些容器活著
make logs kafka-1                    # 跟某個 broker 的 log

make topic NAME=foo PARTS=3 RF=3     # 建 topic
make describe TOPIC=foo              # 看 partition / ISR
make produce TOPIC=foo RATE=100      # 持續寫(100 msg/s)
make consume TOPIC=foo GROUP=g1      # 持續讀
make groups                          # 列所有 consumer group
make lag GROUP=g1                    # 看某 group 的 lag

make chaos-isolate BROKER=2          # 把 broker-2 從 docker network 拔掉
make chaos-restore BROKER=2          # 接回去
make chaos-latency BROKER=2 MS=500   # toxiproxy 給 broker-2 加延遲
make chaos-clear BROKER=2            # 清掉 toxic
make stop-broker N=2                 # 直接 docker stop(模擬硬掛)
make start-broker N=2
```

| 服務 | URL |
|---|---|
| Kafka UI | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana (匿名 Viewer) | http://localhost:3000/d/kafka-overview/kafka-overview-handson |

## 紀律

寫 scenario 時遵守的三條規則(不要省):

1. **「預期」必須在跑之前寫**,而且要單獨 commit 一次。預期被實機污染就學不到東西了。
2. **「實機告訴我」當天填**。隔天就忘了當下的驚訝點。
3. **「⚠️ 預期 vs 實機落差」是這個方法的核心輸出**。如果每個 scenario 都是「預期完全對應」,那要嘛你選的 scenario 太簡單,要嘛你的「預期」寫太模糊。
