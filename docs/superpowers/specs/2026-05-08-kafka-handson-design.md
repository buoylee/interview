# Kafka Hands-on Lab + 深度筆記 設計文件

**日期**: 2026-05-08
**作者**: jimmylee
**目標倉庫位置**: `interview/MQ/kafka-handson/`

---

## 背景與動機

使用者已對 Kafka 有相對深入的理論認識(已存在筆記:`broker.md`, `consumer.md`, `producer.md`, `kafka事务.md`, `kafka-消息防丢.md`, `log.md`, `mmap-pagecache-...md`, `概述-三高架构设计剖析.md`),但缺乏實機操作經驗。當被問到偏運維/行為層的問題(例如「Kafka 在重新分配 broker 時是否無法接受請求?」),即使有理論底子也難以給出有把握的回答,因為缺少把理論連結到「實機指標 / 日誌 / 觀察」的肌肉記憶。

本項目目標:**透過一個可重跑的 Kafka 實驗環境,把理論層面的 Kafka 知識在實機上「跑過一遍」,並沉澱成有結構的筆記與面試答案卡。**

## 非目標

- 不做 Streams / Connect 的實驗(面試問到的機率低,且環境成本高)
- 不做完整的 RocketMQ / RabbitMQ / Pulsar 實機,只在 Kafka 對應章節的「對比」段落提及差異
- 不追求生產級的 chaos engineering(用 Toxiproxy 即可,不上 chaos-mesh)
- 不為了完美 lab 而拖延寫第一個 scenario(Day 2 能跑通就動手)

## 核心方法

**分層骨架(top-down)+ 場景單元(bottom-up)的混合式**:

- 章節按 Kafka 七層展開,確保最後筆記是有結構的、能講系統圖的
- 每章內部由獨立可跑的 scenario 單元組成,確保每天能進步、能單點對齊面試題
- 面試卡作為「反向產出」(每章寫完後再翻譯),確保每張卡都有實機背書

## 目錄結構

```
interview/MQ/kafka-handson/
├── README.md                    ← 入口:目錄 + 怎麼用 + lab 啟動方式
├── 00-lab/                      ← 實驗環境(中量級)
│   ├── docker-compose.yml       ← 3 broker KRaft + Kafka UI + Prom + Grafana + Toxiproxy
│   ├── prometheus.yml
│   ├── grafana/dashboards/      ← 預匯入 broker / topic / consumer 三張板
│   ├── jmx_exporter_config.yml
│   └── Makefile                 ← up / down / reset / topic / produce / consume / chaos-*
├── 01-storage/                  ← 章節1: 存儲層(log/segment/index)
│   ├── README.md                ← 本層的「我以為 vs 實機」+ 系統圖
│   └── scenarios/
│       ├── 01-segment-roll.md
│       ├── 02-index-lookup.md
│       └── ...
├── 02-replication/              ← 章節2: 副本層(ISR/HW/LEO/min.insync.replicas)
├── 03-controller/               ← 章節3: Controller / 元數據(KRaft)
├── 04-producer/                 ← 章節4: Producer (acks, idempotent, batch, linger)
├── 05-consumer/                 ← 章節5: Consumer (rebalance, offset, assignor)
├── 06-transaction/              ← 章節6: 事務 / exactly-once
├── 07-ops/                      ← 章節7: 運維面(reassignment, quota, observability)
└── 99-interview-cards/          ← 反向產物:把劇本打包成面試題答案卡
    ├── q-broker-reassignment.md
    └── ...
```

### 兩個關鍵架構決定

1. **lab 跟筆記分開但同 repo**:lab 在 `00-lab/`,章節 scenario 引用 lab 的腳本(`make chaos-isolate-broker-2`),而不是把 docker-compose 抄到每個劇本裡。改 lab 一次,所有劇本都受益。
2. **`99-interview-cards/` 是反向產物,不是源頭**:跑完劇本、寫完章節筆記之後,再把它「翻譯」成面試卡(問題 → 一句話回答 → 證據鏈接到 scenario 文件)。

## 章節骨架(7 層)

每章固定三件事:**「我以為」→ 跑 N 個 scenario → 「實機告訴我」**。

| 章節 | 對應已有筆記 | 規劃中的 scenarios |
|---|---|---|
| **01 存儲** | `log.md`, `mmap-pagecache-...md` | segment roll、index 查找、log compaction、page cache 命中、磁碟滿時 broker 行為 |
| **02 副本** | `broker.md` | ISR 收縮(慢副本)、min.insync.replicas 觸發、unclean leader election、HW vs LEO 的滯後可視化 |
| **03 Controller** | `broker.md` | controller 切換(KRaft 下 controller quorum 選舉)、元數據傳播延遲、Topic 創建/刪除過程 |
| **04 Producer** | `producer.md`, `kafka-消息防丢.md` | acks=0/1/all 的丟失差異、idempotent producer 重試、batch + linger 對吞吐的影響、partitioner 選擇 |
| **05 Consumer** | `consumer.md` | rebalance 全過程(stop-the-world 觀察)、cooperative sticky vs range、offset commit 時機 vs 重複消費、lag 突增定位 |
| **06 事務** | `kafka事务.md` | 跨 partition 事務、abort 後消費者看到什麼、read_committed vs read_uncommitted、與 idempotent 的關係 |
| **07 運維** | (新) | **partition reassignment、quota 限流觸發、JMX 關鍵指標清單、滾動升級、磁碟擴容** |

### 順序的理由

章節順序刻意是「底層先」,**因為上層的詭異現象往往要靠底層解釋**。例如 consumer rebalance 為什麼有時候會把所有人 stop-the-world,根因要追到 group coordinator + offset topic + assignor 設計,而不是只看 consumer.md。

### 不單獨開的章節

- **Streams / Connect**:面試問到的機率低,而且裝起來重。如果哪天工作要用,再單獨補。

## Scenario 單元模板

每個 scenario 都長一樣,跑十個之後就有肌肉記憶:

```markdown
# Scenario: <一句話描述>

## 我想驗證的問題
<一句話。例如:「broker 從 ISR 被踢出需要多久?期間 producer acks=all 會怎樣?」>

## 預期(寫實驗前的假設)
<一段話。把「以為」的行為寫下來。重點:寫完才能跑,跑完才能對照。>

## 環境
- compose: `00-lab/docker-compose.yml`
- topic: `make topic NAME=t-isr PARTS=3 RF=3`
- 額外設定: `min.insync.replicas=2`, `replica.lag.time.max.ms=10000`

## 觸發步驟
1. `make produce TOPIC=t-isr RATE=100`            # 持續寫入做底噪
2. `make chaos-isolate BROKER=2`                  # toxiproxy 切 broker-2 的網
3. 等 30 秒
4. `make chaos-restore BROKER=2`

## 觀察點(指標 + 日誌)
- Grafana → ISR size 曲線
- Grafana → UnderReplicatedPartitions
- broker-1 的 controller log: `Shrinking ISR from ...`
- producer 端:有沒有 `NotEnoughReplicasException`?
- consumer 端:有沒有 lag 抖動?

## 實機告訴我(跑完才填)
- ISR 收縮觸發時間: ___ 秒(對照 replica.lag.time.max.ms)
- producer 在隔離期間的行為: ___
- ✅ / ❌ 我預期對嗎?哪裡錯了?

## 一句話結論(將來要進面試卡的)
<例如:「acks=all + min.insync.replicas=2 在 RF=3 集群下,單 broker 隔離不會阻塞寫入,但 ISR 收縮有 ~10s 滯後窗口」>

## 延伸問題(下次補)
- 如果 min.insync.replicas=3 呢?
- 如果同時隔離兩個 broker 呢?
```

### 三個刻意設計

1. **「預期」必須在跑之前寫**。這是這個方法的核心 — 強迫把「以為的 Kafka」吐出來,再去和真機碰撞。如果省掉這一步,實驗的記憶量會少 80%,因為大腦沒有「驚訝點」可以掛東西。
2. **「實機告訴我」要寫對錯,不能只抄結果**。對照預期 → 找出落差 → 落差才是知識增量。
3. **「一句話結論」是面試卡的種子**。寫的時候強迫自己用「條件 + 行為 + 量化」的格式,不要「Kafka 的 ISR 機制是...」這種八股開頭。

## Lab 工具棧細節

`00-lab/docker-compose.yml` 起以下服務:

| 服務 | 鏡像 | 用途 | 暴露端口 |
|---|---|---|---|
| kafka-1, kafka-2, kafka-3 | `confluentinc/cp-kafka` (KRaft mode,no Zookeeper) | 3 broker 集群,RF=3 才能跑出真實副本場景 | 9092, 9093, 9094 |
| kafka-ui | `provectuslabs/kafka-ui` | 視覺化 topic/partition/consumer group | 8080 |
| prometheus | `prom/prometheus` | 抓 JMX exporter 指標 | 9090 |
| grafana | `grafana/grafana` | 三張預配置 dashboard | 3000 |
| jmx-exporter | sidecar,每個 broker 一個 | JMX → Prometheus 格式 | 5556/5557/5558 |
| toxiproxy | `ghcr.io/shopify/toxiproxy` | 注入網路故障(latency/loss/cut)— 實機驗證「重分配 broker 時可不可以接受請求」這類題目的關鍵工具 | 8474 (admin) |

### Makefile target 一覽

```
make up                              # 起整套
make down                            # 停掉
make reset                           # down + 刪 volume + up,回到乾淨狀態
make topic NAME=foo PARTS=3 RF=3     # 建 topic
make produce TOPIC=foo RATE=100      # 持續寫(底噪)
make consume TOPIC=foo GROUP=g1      # 持續讀
make perf-produce TOPIC=foo          # kafka-producer-perf-test 壓測
make chaos-isolate BROKER=2          # toxiproxy 切 broker-2 對外網路
make chaos-latency BROKER=2 MS=500   # 給 broker-2 加 500ms 延遲
make chaos-restore BROKER=2          # 恢復
make stop-broker N=2                 # 直接 docker stop(模擬硬掛)
make start-broker N=2
make describe TOPIC=foo              # kafka-topics --describe
make groups                          # 列所有 consumer group
make lag GROUP=g1                    # 看 lag
```

### 三個工具棧取捨

1. **用 KRaft 不用 Zookeeper**。Kafka 4.0 (2025) 已經把 ZK 拔掉了,面試官現在問也是問 KRaft 為主。沿用 ZK 會多裝一個服務、多學一套 controller 模型,沒有收益。
2. **Java client 為主、kcat 為輔**。Kafka canonical 客戶端是 Java,面試官說「producer」「consumer」預設指的是 Java client 行為(包括 idempotent/batch/linger 的精確語義)。kcat 用來做快速 debug。如果要加 Go client,放 `04-producer/` 或 `05-consumer/` 章節下作為對比實驗。
3. **Toxiproxy 而不是 chaos-mesh / pumba**。輕、單機、API 簡單、跟 docker-compose 配合好。chaos-mesh 是 k8s 才好用,pumba 不能精確控網路層。

## 推進節奏

### 啟動順序(第一週)

```
Day 1-2: 把 00-lab 起來,跑通 produce + consume + 一張 grafana 看到指標
Day 3:   寫第一個 scenario(建議 02-replication/01-isr-shrink-on-network-isolation.md)
         — 直接命中「重分配 broker 時還能不能接受請求」的痛點,完成後立刻有「我能答這題了」的爽感
Day 4-5: 再寫 2 個 scenario,把模板用順
Day 6-7: 回頭把 README 寫好,把模板和啟動流程沉澱下來
```

### 之後的節奏

每週推進 2-3 個 scenario。一個章節大概 4-6 週寫完。整體 7 章預計 6-9 個月 — 但**這不是需要全部跑完才有價值**,寫到哪面試到哪都能用。

### 防止項目跑歪的關鍵節制

1. **每個 scenario 跑完當天就要寫「實機告訴我」段落**。隔天就忘了當下的驚訝點,寫出來會變成抄日誌。
2. **不要追求 lab 完美才開始寫第一個 scenario**。Day 2 能跑通 produce/consume 就動手寫,後面缺什麼工具邊用邊加。
3. **`99-interview-cards/` 在每章寫完才開始**。寫到一半就想「這要怎麼變面試題答案」會打斷觀察的純粹性。
4. **遇到「跑完發現預期錯了」是這個方法的最佳產出**,要刻意標記出來(模板「實機告訴我」段下面用 ⚠️ 標),這些就是比別人強的地方。

## 成功標準

- [ ] `00-lab/` 可以一條 `make up` 起來,Grafana 看得到指標
- [ ] 至少完成 02-replication 章節(含 ≥4 個 scenario + 章節 README + 1-2 張面試卡)
- [ ] 用 `99-interview-cards/q-broker-reassignment.md` 能對著面試官講清楚「重分配 broker 時是否影響寫入」,且每個論點都鏈接到對應 scenario 的「實機告訴我」段
- [ ] 形成「下一個 scenario 該寫什麼」的自我驅動感,不需要外部規劃

## 下一步

進入 writing-plans skill,把本設計拆成可執行的實施計劃(從 lab 搭建 → 第一個 scenario → 第一張面試卡)。
