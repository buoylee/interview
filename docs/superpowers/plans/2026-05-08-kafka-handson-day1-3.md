# Kafka Hands-on Lab — Day 1-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a 3-broker KRaft Kafka lab with observability + chaos tooling, then complete the first end-to-end scenario (ISR shrink under network isolation) so the user can answer "重分配 broker 時還能不能接受請求" with a real metrics chart.

**Architecture:** Single docker-compose stack: 3 × `apache/kafka` (KRaft mode), Kafka UI, Prometheus, Grafana, JMX-exporter Java agent (mounted into each broker), Toxiproxy for network fault injection. All operations driven from a `Makefile` so scenarios stay terse.

**Tech Stack:** docker compose, apache/kafka 3.8 (KRaft), prom/prometheus, grafana/grafana, provectuslabs/kafka-ui, ghcr.io/shopify/toxiproxy, Prometheus jmx_exporter Java agent.

**Scope guardrail:** This plan delivers Days 1-3 of the design (`docs/superpowers/specs/2026-05-08-kafka-handson-design.md`). Day 4-7 (more scenarios + main README polish) follow the same scenario template and don't need their own plan.

---

## File Structure (decomposition)

```
interview/MQ/kafka-handson/
├── README.md                           # Task 12 (main entry)
├── 00-lab/
│   ├── docker-compose.yml              # Task 2
│   ├── Makefile                        # Task 6 (basic) + 7 (chaos)
│   ├── prometheus.yml                  # Task 4
│   ├── jmx-exporter/
│   │   └── config.yml                  # Task 3
│   ├── toxiproxy/
│   │   └── config.json                 # Task 2 (initial), Task 7 (proxies)
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/datasource.yml   # Task 5
│       │   └── dashboards/dashboards.yml    # Task 5
│       └── dashboards/
│           └── kafka-overview.json     # Task 5
├── templates/
│   └── scenario-template.md            # Task 9
├── 01-storage/README.md                # Task 1 (placeholder)
├── 02-replication/
│   ├── README.md                       # Task 9
│   └── scenarios/
│       └── 01-isr-shrink-on-network-isolation.md  # Task 10 + 11
├── 03-controller/README.md             # Task 1 (placeholder)
├── 04-producer/README.md               # Task 1 (placeholder)
├── 05-consumer/README.md               # Task 1 (placeholder)
├── 06-transaction/README.md            # Task 1 (placeholder)
├── 07-ops/README.md                    # Task 1 (placeholder)
└── 99-interview-cards/README.md        # Task 1 (placeholder)
```

**Decomposition rationale:**
- `00-lab/` is self-contained — change a broker config, rerun `make reset`, all scenarios benefit.
- Scenarios are individual `.md` files, not folders — keeps cognitive overhead low when scanning.
- `templates/scenario-template.md` is the source of truth for scenario format. New scenarios start by copying it.
- Chapter `README.md`s are single-file responsibility (overview + scenario list).

---

## Task 1: Create directory skeleton + chapter README placeholders

**Files:**
- Create: `interview/MQ/kafka-handson/01-storage/README.md`
- Create: `interview/MQ/kafka-handson/02-replication/README.md` (will be replaced in Task 9, placeholder for now)
- Create: `interview/MQ/kafka-handson/03-controller/README.md`
- Create: `interview/MQ/kafka-handson/04-producer/README.md`
- Create: `interview/MQ/kafka-handson/05-consumer/README.md`
- Create: `interview/MQ/kafka-handson/06-transaction/README.md`
- Create: `interview/MQ/kafka-handson/07-ops/README.md`
- Create: `interview/MQ/kafka-handson/99-interview-cards/README.md`
- Create: `interview/MQ/kafka-handson/02-replication/scenarios/.gitkeep`

- [ ] **Step 1: Create the directory tree**

```bash
cd interview/MQ/kafka-handson
mkdir -p 00-lab/jmx-exporter 00-lab/toxiproxy 00-lab/grafana/provisioning/datasources 00-lab/grafana/provisioning/dashboards 00-lab/grafana/dashboards
mkdir -p templates
mkdir -p 01-storage 02-replication/scenarios 03-controller 04-producer 05-consumer 06-transaction 07-ops 99-interview-cards
touch 02-replication/scenarios/.gitkeep
```

- [ ] **Step 2: Write each chapter placeholder README**

Each placeholder uses the same template — pick the chapter's title and one-line scope. Example for `01-storage/README.md`:

```markdown
# 01 · 存儲層 (log / segment / index / page cache)

> 本章節尚未開始。規劃 scenarios:segment roll、index 查找、log compaction、page cache 命中、磁碟滿時 broker 行為。

掃 `00-lab/` 起 lab,然後從 `02-replication/` 開始(第一個有完整 scenario 的章節)。
```

Write the same shape for `03-controller`, `04-producer`, `05-consumer`, `06-transaction`, `07-ops`, `99-interview-cards`. Replace the title and scenario list per the spec table:

- 03 · Controller / 元數據 (KRaft) — controller 切換、元數據傳播延遲、Topic 創建/刪除
- 04 · Producer — acks=0/1/all 丟失差異、idempotent 重試、batch+linger、partitioner
- 05 · Consumer — rebalance 全過程、cooperative sticky vs range、offset commit、lag 突增
- 06 · 事務 / exactly-once — 跨 partition 事務、abort 後消費者看到什麼、read_committed
- 07 · 運維 — partition reassignment、quota、JMX 關鍵指標、滾動升級、磁碟擴容
- 99 · 面試卡 — 跑完章節後反向打包,每張卡引用對應 scenario 的「實機告訴我」段

For `02-replication/README.md`, write a placeholder for now (Task 9 replaces it):

```markdown
# 02 · 副本層 (ISR / HW / LEO / min.insync.replicas)

> 本章節 scaffolding 中,Task 9 會寫完整版本。
```

- [ ] **Step 3: Commit**

```bash
cd interview/MQ/kafka-handson
git add 01-storage 02-replication 03-controller 04-producer 05-consumer 06-transaction 07-ops 99-interview-cards
git commit -m "kafka-handson: scaffold chapter directories with placeholder READMEs"
```

---

## Task 2: docker-compose.yml + initial toxiproxy config

**Files:**
- Create: `interview/MQ/kafka-handson/00-lab/docker-compose.yml`
- Create: `interview/MQ/kafka-handson/00-lab/toxiproxy/config.json`

- [ ] **Step 1: Write docker-compose.yml**

Path: `interview/MQ/kafka-handson/00-lab/docker-compose.yml`

```yaml
name: kafka-handson

x-kafka-common: &kafka-common
  image: apache/kafka:3.8.0
  environment: &kafka-env
    KAFKA_PROCESS_ROLES: controller,broker
    KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka-1:9093,2@kafka-2:9093,3@kafka-3:9093
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
    KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
    KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
    KAFKA_AUTO_CREATE_TOPICS_ENABLE: "false"
    KAFKA_NUM_PARTITIONS: 3
    KAFKA_DEFAULT_REPLICATION_FACTOR: 3
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
    KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
    KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 2
    KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
    CLUSTER_ID: 5L6g3nShT-eMCtK--X86sw
    KAFKA_OPTS: "-javaagent:/opt/jmx-exporter/jmx_prometheus_javaagent.jar=5556:/opt/jmx-exporter/config.yml"
  volumes:
    - ./jmx-exporter:/opt/jmx-exporter:ro

services:
  kafka-1:
    <<: *kafka-common
    container_name: kafka-1
    hostname: kafka-1
    environment:
      <<: *kafka-env
      KAFKA_NODE_ID: 1
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-1:9092
    ports:
      - "19092:9092"
      - "5556:5556"

  kafka-2:
    <<: *kafka-common
    container_name: kafka-2
    hostname: kafka-2
    environment:
      <<: *kafka-env
      KAFKA_NODE_ID: 2
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-2:9092
    ports:
      - "29092:9092"
      - "5557:5556"

  kafka-3:
    <<: *kafka-common
    container_name: kafka-3
    hostname: kafka-3
    environment:
      <<: *kafka-env
      KAFKA_NODE_ID: 3
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka-3:9092
    ports:
      - "39092:9092"
      - "5558:5556"

  kafka-ui:
    image: provectuslabs/kafka-ui:v0.7.2
    container_name: kafka-ui
    depends_on: [kafka-1, kafka-2, kafka-3]
    environment:
      KAFKA_CLUSTERS_0_NAME: handson
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka-1:9092,kafka-2:9092,kafka-3:9092
    ports:
      - "8080:8080"

  prometheus:
    image: prom/prometheus:v2.55.0
    container_name: prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:11.2.0
    container_name: grafana
    depends_on: [prometheus]
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: Viewer
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"

  toxiproxy:
    image: ghcr.io/shopify/toxiproxy:2.9.0
    container_name: toxiproxy
    command: ["-host=0.0.0.0", "-config=/config/toxiproxy.json"]
    volumes:
      - ./toxiproxy/config.json:/config/toxiproxy.json:ro
    ports:
      - "8474:8474"
      - "21092:21092"
      - "22092:22092"
      - "23092:23092"
```

**Note on the JMX-exporter agent jar:** the volume mount expects `jmx_prometheus_javaagent.jar` at `00-lab/jmx-exporter/`. Task 6's `make bootstrap` target downloads it.

**Note on Toxiproxy:** the proxies for chaos work get added to `toxiproxy/config.json` in Task 7 (the chaos-targets task). Task 2 just provides an empty starter so the container boots.

- [ ] **Step 2: Write the empty toxiproxy config**

Path: `interview/MQ/kafka-handson/00-lab/toxiproxy/config.json`

```json
[]
```

- [ ] **Step 3: Validate compose syntax**

Run:
```bash
cd interview/MQ/kafka-handson/00-lab
docker compose config > /dev/null && echo OK
```

Expected: `OK`. If you see errors, the YAML is malformed — fix and re-run.

- [ ] **Step 4: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/docker-compose.yml 00-lab/toxiproxy/config.json
git commit -m "kafka-handson: add 3-broker KRaft compose stack with UI/Prom/Grafana/Toxiproxy"
```

---

## Task 3: JMX exporter config

**Files:**
- Create: `interview/MQ/kafka-handson/00-lab/jmx-exporter/config.yml`

This config drives which JMX MBeans get exposed as Prometheus metrics. We use a focused subset (not the full kitchen sink) so the metric names stay readable when grepping.

- [ ] **Step 1: Write the JMX exporter config**

Path: `interview/MQ/kafka-handson/00-lab/jmx-exporter/config.yml`

```yaml
lowercaseOutputName: true
lowercaseOutputLabelNames: true

rules:
  # Broker request metrics (per request type: Produce, Fetch, Metadata, ...)
  - pattern: "kafka.network<type=RequestMetrics, name=(RequestsPerSec|TotalTimeMs|LocalTimeMs|RequestQueueTimeMs|ResponseSendTimeMs), request=(\\w+)><>(Count|Mean|50thPercentile|99thPercentile|999thPercentile)"
    name: "kafka_network_request_$1_$3"
    labels:
      request: "$2"

  # Replica manager — the heart of replication observability
  - pattern: "kafka.server<type=ReplicaManager, name=(UnderReplicatedPartitions|UnderMinIsrPartitionCount|AtMinIsrPartitionCount|OfflineReplicaCount|PartitionCount|LeaderCount|IsrShrinksPerSec|IsrExpandsPerSec)><>(Value|Count|OneMinuteRate)"
    name: "kafka_server_replicamanager_$1_$2"

  # Controller (KRaft active controller)
  - pattern: "kafka.controller<type=KafkaController, name=(ActiveControllerCount|OfflinePartitionsCount|GlobalTopicCount|GlobalPartitionCount|MetadataErrorCount)><>Value"
    name: "kafka_controller_$1"

  # Log size per topic-partition
  - pattern: "kafka.log<type=Log, name=(Size|NumLogSegments|LogStartOffset|LogEndOffset), topic=(.+), partition=(\\d+)><>Value"
    name: "kafka_log_$1"
    labels:
      topic: "$2"
      partition: "$3"

  # BytesIn/BytesOut per topic
  - pattern: "kafka.server<type=BrokerTopicMetrics, name=(BytesInPerSec|BytesOutPerSec|MessagesInPerSec|TotalProduceRequestsPerSec|TotalFetchRequestsPerSec)><>(Count|OneMinuteRate)"
    name: "kafka_server_brokertopic_$1_$2"

  - pattern: "kafka.server<type=BrokerTopicMetrics, name=(BytesInPerSec|BytesOutPerSec|MessagesInPerSec), topic=(.+)><>(Count|OneMinuteRate)"
    name: "kafka_server_brokertopic_$1_$3"
    labels:
      topic: "$2"

  # JVM
  - pattern: "java.lang<type=Memory><HeapMemoryUsage>(used|committed|max)"
    name: "jvm_memory_heap_$1_bytes"

  - pattern: "java.lang<type=GarbageCollector, name=(.+)><>(CollectionCount|CollectionTime)"
    name: "jvm_gc_$2"
    labels:
      gc: "$1"
```

- [ ] **Step 2: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/jmx-exporter/config.yml
git commit -m "kafka-handson: add JMX exporter rules for replication / controller / topic metrics"
```

---

## Task 4: Prometheus scrape config

**Files:**
- Create: `interview/MQ/kafka-handson/00-lab/prometheus.yml`

- [ ] **Step 1: Write the prometheus config**

Path: `interview/MQ/kafka-handson/00-lab/prometheus.yml`

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: kafka
    static_configs:
      - targets:
          - kafka-1:5556
          - kafka-2:5556
          - kafka-3:5556
        labels:
          cluster: handson
    relabel_configs:
      - source_labels: [__address__]
        regex: "kafka-(\\d+):5556"
        target_label: broker
        replacement: "$1"
```

- [ ] **Step 2: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/prometheus.yml
git commit -m "kafka-handson: add Prometheus scrape config with broker label"
```

---

## Task 5: Grafana provisioning + base dashboard

**Files:**
- Create: `interview/MQ/kafka-handson/00-lab/grafana/provisioning/datasources/datasource.yml`
- Create: `interview/MQ/kafka-handson/00-lab/grafana/provisioning/dashboards/dashboards.yml`
- Create: `interview/MQ/kafka-handson/00-lab/grafana/dashboards/kafka-overview.json`

- [ ] **Step 1: Datasource provisioning**

Path: `interview/MQ/kafka-handson/00-lab/grafana/provisioning/datasources/datasource.yml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

- [ ] **Step 2: Dashboard provider**

Path: `interview/MQ/kafka-handson/00-lab/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1
providers:
  - name: kafka-handson
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 3: Base overview dashboard**

Path: `interview/MQ/kafka-handson/00-lab/grafana/dashboards/kafka-overview.json`

This is a minimal dashboard with the panels needed for the first scenario. It includes ISR shrink/expand rate, under-replicated count, leader count per broker, and bytes in/out — these are exactly what scenario `01-isr-shrink-on-network-isolation` reads.

```json
{
  "title": "Kafka Overview (handson)",
  "uid": "kafka-overview",
  "schemaVersion": 39,
  "version": 1,
  "refresh": "5s",
  "time": {"from": "now-15m", "to": "now"},
  "panels": [
    {
      "id": 1,
      "title": "Under-Replicated Partitions",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
      "targets": [
        {"expr": "kafka_server_replicamanager_underreplicatedpartitions_value", "legendFormat": "broker {{broker}}"}
      ]
    },
    {
      "id": 2,
      "title": "ISR Shrinks / sec",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
      "targets": [
        {"expr": "rate(kafka_server_replicamanager_isrshrinkspersec_count[1m])", "legendFormat": "broker {{broker}}"}
      ]
    },
    {
      "id": 3,
      "title": "Leader Count per Broker",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
      "targets": [
        {"expr": "kafka_server_replicamanager_leadercount_value", "legendFormat": "broker {{broker}}"}
      ]
    },
    {
      "id": 4,
      "title": "Active Controller",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
      "targets": [
        {"expr": "kafka_controller_activecontrollercount", "legendFormat": "broker {{broker}}"}
      ]
    },
    {
      "id": 5,
      "title": "Bytes In / sec",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 0, "y": 16, "w": 12, "h": 8},
      "targets": [
        {"expr": "rate(kafka_server_brokertopic_bytesinpersec_count[1m])", "legendFormat": "broker {{broker}}"}
      ]
    },
    {
      "id": 6,
      "title": "Produce Request p99 latency (ms)",
      "type": "timeseries",
      "datasource": {"type": "prometheus", "uid": "Prometheus"},
      "gridPos": {"x": 12, "y": 16, "w": 12, "h": 8},
      "targets": [
        {"expr": "kafka_network_request_totaltimems_99thpercentile{request=\"Produce\"}", "legendFormat": "broker {{broker}}"}
      ]
    }
  ]
}
```

- [ ] **Step 4: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/grafana
git commit -m "kafka-handson: add Grafana datasource + provisioned overview dashboard"
```

---

## Task 6: Makefile (basic targets)

**Files:**
- Create: `interview/MQ/kafka-handson/00-lab/Makefile`

This task adds **only basic lifecycle + topic + produce/consume targets**. Chaos targets land in Task 7.

- [ ] **Step 1: Write the Makefile**

Path: `interview/MQ/kafka-handson/00-lab/Makefile`

```make
SHELL := /bin/bash

JMX_AGENT_VERSION := 1.0.1
JMX_AGENT_URL     := https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/$(JMX_AGENT_VERSION)/jmx_prometheus_javaagent-$(JMX_AGENT_VERSION).jar
JMX_AGENT_PATH    := jmx-exporter/jmx_prometheus_javaagent.jar

BROKER_CONTAINER  := kafka-1
BOOTSTRAP         := kafka-1:9092,kafka-2:9092,kafka-3:9092

PARTS ?= 3
RF    ?= 3
RATE  ?= 100

.PHONY: bootstrap up down reset ps logs topic topics describe produce consume groups lag

bootstrap: $(JMX_AGENT_PATH)

$(JMX_AGENT_PATH):
	@echo "Downloading JMX exporter agent v$(JMX_AGENT_VERSION)..."
	curl -L -o $@ $(JMX_AGENT_URL)

up: bootstrap
	docker compose up -d
	@echo ""
	@echo "Kafka UI:    http://localhost:8080"
	@echo "Prometheus:  http://localhost:9090"
	@echo "Grafana:     http://localhost:3000  (anonymous Viewer enabled)"

down:
	docker compose down

reset:
	docker compose down -v
	$(MAKE) up

ps:
	docker compose ps

logs:
	docker compose logs -f $(filter-out $@,$(MAKECMDGOALS))

topic:
	@if [ -z "$(NAME)" ]; then echo "Usage: make topic NAME=foo [PARTS=3] [RF=3]"; exit 1; fi
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--bootstrap-server $(BOOTSTRAP) \
		--create --topic $(NAME) --partitions $(PARTS) --replication-factor $(RF) \
		--if-not-exists

topics:
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--bootstrap-server $(BOOTSTRAP) --list

describe:
	@if [ -z "$(TOPIC)" ]; then echo "Usage: make describe TOPIC=foo"; exit 1; fi
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-topics.sh \
		--bootstrap-server $(BOOTSTRAP) --describe --topic $(TOPIC)

produce:
	@if [ -z "$(TOPIC)" ]; then echo "Usage: make produce TOPIC=foo [RATE=100]"; exit 1; fi
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-producer-perf-test.sh \
		--topic $(TOPIC) \
		--num-records 1000000000 \
		--record-size 200 \
		--throughput $(RATE) \
		--producer-props bootstrap.servers=$(BOOTSTRAP) acks=all linger.ms=5

consume:
	@if [ -z "$(TOPIC)" ]; then echo "Usage: make consume TOPIC=foo GROUP=g1"; exit 1; fi
	@if [ -z "$(GROUP)" ]; then echo "Usage: make consume TOPIC=foo GROUP=g1"; exit 1; fi
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-console-consumer.sh \
		--bootstrap-server $(BOOTSTRAP) \
		--topic $(TOPIC) --group $(GROUP) --from-beginning

groups:
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-consumer-groups.sh \
		--bootstrap-server $(BOOTSTRAP) --list

lag:
	@if [ -z "$(GROUP)" ]; then echo "Usage: make lag GROUP=g1"; exit 1; fi
	docker exec $(BROKER_CONTAINER) /opt/kafka/bin/kafka-consumer-groups.sh \
		--bootstrap-server $(BOOTSTRAP) --describe --group $(GROUP)

# Catch-all so `make logs kafka-1` doesn't error
%:
	@:
```

- [ ] **Step 2: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/Makefile
git commit -m "kafka-handson: add Makefile (lifecycle + topic + produce/consume + lag)"
```

---

## Task 7: Makefile chaos targets + Toxiproxy proxy config

**Files:**
- Modify: `interview/MQ/kafka-handson/00-lab/Makefile`
- Modify: `interview/MQ/kafka-handson/00-lab/toxiproxy/config.json`

**Approach:** Toxiproxy sits in front of brokers' inter-broker listener. We don't actually want clients going through it (that's overcomplicated for now); instead, we use Toxiproxy as a way to inject latency/disconnects on **broker-to-broker traffic**, which is what triggers ISR shrinks. For the first scenario we use the simpler `docker network` disconnect approach via `make chaos-isolate`, and Toxiproxy targets are reserved for finer-grained latency injection.

- [ ] **Step 1: Replace toxiproxy/config.json with proxies for finer-grained injection**

Path: `interview/MQ/kafka-handson/00-lab/toxiproxy/config.json`

```json
[
  {"name": "broker-1", "listen": "0.0.0.0:21092", "upstream": "kafka-1:9092", "enabled": true},
  {"name": "broker-2", "listen": "0.0.0.0:22092", "upstream": "kafka-2:9092", "enabled": true},
  {"name": "broker-3", "listen": "0.0.0.0:23092", "upstream": "kafka-3:9092", "enabled": true}
]
```

- [ ] **Step 2: Append chaos targets to the Makefile**

Append to: `interview/MQ/kafka-handson/00-lab/Makefile` (just before the catch-all `%:` rule at the bottom)

```make
.PHONY: chaos-isolate chaos-restore chaos-latency chaos-clear stop-broker start-broker

# Hard isolate: disconnect broker N from the docker network entirely.
# Triggers ISR shrink because broker can't talk to peers OR clients.
chaos-isolate:
	@if [ -z "$(BROKER)" ]; then echo "Usage: make chaos-isolate BROKER=2"; exit 1; fi
	docker network disconnect kafka-handson_default kafka-$(BROKER)
	@echo "broker-$(BROKER) isolated from docker network"

chaos-restore:
	@if [ -z "$(BROKER)" ]; then echo "Usage: make chaos-restore BROKER=2"; exit 1; fi
	docker network connect kafka-handson_default kafka-$(BROKER)
	@echo "broker-$(BROKER) reconnected"

# Soft latency injection via toxiproxy on the proxied port (21092/22092/23092).
# Note: this only affects clients connecting via the proxy, not inter-broker traffic.
# Use this for producer-side latency experiments, not for ISR experiments.
chaos-latency:
	@if [ -z "$(BROKER)" ] || [ -z "$(MS)" ]; then echo "Usage: make chaos-latency BROKER=2 MS=500"; exit 1; fi
	curl -s -X POST http://localhost:8474/proxies/broker-$(BROKER)/toxics \
		-d '{"type":"latency","attributes":{"latency":$(MS)}}' \
		-H "Content-Type: application/json" | jq .

chaos-clear:
	@if [ -z "$(BROKER)" ]; then echo "Usage: make chaos-clear BROKER=2"; exit 1; fi
	@for tox in $$(curl -s http://localhost:8474/proxies/broker-$(BROKER)/toxics | jq -r '.[].name'); do \
		curl -s -X DELETE http://localhost:8474/proxies/broker-$(BROKER)/toxics/$$tox; \
		echo "removed toxic $$tox from broker-$(BROKER)"; \
	done

stop-broker:
	@if [ -z "$(N)" ]; then echo "Usage: make stop-broker N=2"; exit 1; fi
	docker stop kafka-$(N)

start-broker:
	@if [ -z "$(N)" ]; then echo "Usage: make start-broker N=2"; exit 1; fi
	docker start kafka-$(N)
```

- [ ] **Step 3: Commit**

```bash
cd interview/MQ/kafka-handson
git add 00-lab/Makefile 00-lab/toxiproxy/config.json
git commit -m "kafka-handson: add chaos targets (isolate / latency / stop) + toxiproxy proxies"
```

---

## Task 8: Smoke test the full stack

This task is **interactive** — no commit. Goal: prove the lab works end-to-end before writing scenarios against it.

- [ ] **Step 1: Bring the stack up**

```bash
cd interview/MQ/kafka-handson/00-lab
make up
```

Expected: `make bootstrap` runs once and downloads the JMX agent jar (~600KB). Then docker pulls images (first time: 5-10 min). At the end:

```
Kafka UI:    http://localhost:8080
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3000  (anonymous Viewer enabled)
```

- [ ] **Step 2: Wait for brokers to settle, then check status**

```bash
sleep 20
make ps
```

Expected: all 7 containers `Up`. If `kafka-1/2/3` show `Restarting`, run `make logs kafka-1` and look for:
- Listener config errors (mistype in compose)
- JMX agent file-not-found (`bootstrap` target failed)
- KRaft cluster ID mismatch (run `make reset` to wipe volumes)

- [ ] **Step 3: Create a smoke topic and check replication is healthy**

```bash
make topic NAME=smoke PARTS=3 RF=3
make describe TOPIC=smoke
```

Expected output includes lines like:
```
Topic: smoke   Partition: 0   Leader: 1   Replicas: 1,2,3   Isr: 1,2,3
Topic: smoke   Partition: 1   Leader: 2   Replicas: 2,3,1   Isr: 2,3,1
Topic: smoke   Partition: 2   Leader: 3   Replicas: 3,1,2   Isr: 3,1,2
```

If `Isr` is shorter than `Replicas`, brokers haven't fully synced — wait 30s and re-run `describe`.

- [ ] **Step 4: Push some traffic in the background**

In one terminal:
```bash
make produce TOPIC=smoke RATE=200
```
(leave running)

- [ ] **Step 5: Verify metrics flow**

Open http://localhost:9090/graph and query:
```
kafka_server_brokertopic_bytesinpersec_count
```
Expected: 3 series, one per broker, increasing over time.

Open http://localhost:3000/d/kafka-overview/kafka-overview-handson.
Expected: "Bytes In / sec" panel shows traffic on at least one broker. "Under-Replicated Partitions" shows 0. "Active Controller" shows 1 on exactly one broker.

If Grafana shows "No data": check the datasource (Configuration → Data sources → Prometheus → Test). URL should be `http://prometheus:9090`.

- [ ] **Step 6: Stop the producer**

In the producer terminal: `Ctrl-C`.

- [ ] **Step 7: Note any issues in your scratchpad** (no commit)

If anything broke and required a fix, fold the fix back into the relevant Task (2/3/4/5/6/7) and re-commit. Lab must be reproducible from a clean clone.

---

## Task 9: Scenario template + 02-replication chapter README

**Files:**
- Create: `interview/MQ/kafka-handson/templates/scenario-template.md`
- Modify: `interview/MQ/kafka-handson/02-replication/README.md` (replace placeholder from Task 1)

- [ ] **Step 1: Write the scenario template**

Path: `interview/MQ/kafka-handson/templates/scenario-template.md`

```markdown
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
<格式建議:「<前置條件> 下,<行為>,<量化>」>
<例:「acks=all + min.insync.replicas=2 在 RF=3 集群下,單 broker 隔離不會阻塞寫入,ISR 收縮在 ~10s 後發生」>

## 延伸問題(下次補)
- <讓 future-me 知道這條線還能往哪挖>
```

- [ ] **Step 2: Replace `02-replication/README.md` with the real chapter intro**

Path: `interview/MQ/kafka-handson/02-replication/README.md`

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
cd interview/MQ/kafka-handson
git add templates/scenario-template.md 02-replication/README.md
git commit -m "kafka-handson: add scenario template + 02-replication chapter intro"
```

---

## Task 10: First scenario — ASSUMPTIONS phase only

**Files:**
- Create: `interview/MQ/kafka-handson/02-replication/scenarios/01-isr-shrink-on-network-isolation.md`

⚠️ **Critical:** this task writes **everything except the "實機告訴我" and "一句話結論" sections**. The whole point of the method is that you write your assumptions BEFORE running, then the run produces a knowledge delta. Do NOT skip ahead to filling in observations.

- [ ] **Step 1: Write the scenario doc with assumptions filled in, observations empty**

Path: `interview/MQ/kafka-handson/02-replication/scenarios/01-isr-shrink-on-network-isolation.md`

```markdown
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
```

- [ ] **Step 2: Commit (this is the "I'm about to run an experiment" snapshot)**

```bash
cd interview/MQ/kafka-handson
git add 02-replication/scenarios/01-isr-shrink-on-network-isolation.md
git commit -m "kafka-handson(02-replication/01): scaffold ISR-shrink scenario with assumptions

預期已寫入,實機觀察待跑完補。Commit 在這刻是為了凍結「我以為的」,
跑完後 amend 不掉,只能用後續 commit 補實機觀察 — 確保預期不被實機結果污染。"
```

---

## Task 11: Run the first scenario, fill in observations

**Files:**
- Modify: `interview/MQ/kafka-handson/02-replication/scenarios/01-isr-shrink-on-network-isolation.md`

This is **interactive execution** — actually run the steps, observe, and write what happened.

- [ ] **Step 1: Make sure lab is up and clean**

```bash
cd interview/MQ/kafka-handson/00-lab
make ps  # all 7 services Up?
# if not: make reset
```

- [ ] **Step 2: Execute the scenario steps from Task 10's doc, exactly**

Follow steps 1-7 of the "觸發步驟" section. Capture:
- Wall-clock times (T0, T1, ISR-shrink moment)
- Producer terminal output (any exceptions? latency spikes?)
- Output of each `make describe` call
- Grafana screenshot path (save to `02-replication/scenarios/01-isr-shrink-screenshots/` if you want to embed)

Recommended: open a third terminal and run `make logs kafka-1 | grep -E "(Shrinking|Expanding) ISR"` so you have the broker log evidence ready.

- [ ] **Step 3: Fill in "實機告訴我" and "一句話結論"**

Edit `02-replication/scenarios/01-isr-shrink-on-network-isolation.md`. Replace the empty observation lines with your actual measurements. **Be ruthless about the ⚠️ line** — if your prediction matched perfectly, write "預期完全對應" and explain what specifically was confirmed. If you were wrong, write what you got wrong and why.

The "一句話結論" should be one sentence in the format `<前置條件> 下,<行為>,<量化>`. Example shape:

> acks=all + min.insync.replicas=2 在 RF=3 集群、replica.lag.time.max.ms=30000 預設下,broker-2 網路隔離後 ISR 在 ~30s 後收縮為 [1,3];收縮窗口內 producer 寫入未阻塞(因為 leader 仍能在收到 ack 前 timeout)/阻塞(因為 leader 等不到 broker-2 的 ack)— **以實機為準**。

- [ ] **Step 4: Commit observations**

```bash
cd interview/MQ/kafka-handson
git add 02-replication/scenarios/01-isr-shrink-on-network-isolation.md
git commit -m "kafka-handson(02-replication/01): fill in observations + 一句話結論

實機跑完。<一句話總結你的最大發現>"
```

The commit message body should mention what surprised you — that's the searchable artifact for "what did I learn from scenario 01".

---

## Task 12: Main README

**Files:**
- Create: `interview/MQ/kafka-handson/README.md`

- [ ] **Step 1: Write the entry README**

Path: `interview/MQ/kafka-handson/README.md`

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
cd interview/MQ/kafka-handson
git add README.md
git commit -m "kafka-handson: add main README with usage / chapter map / lab quickref"
```

---

## Self-Review Checklist (run after writing the plan)

- ✅ **Spec coverage**:
  - 目錄結構 → Task 1, 2, 5, 9
  - 章節骨架 → Task 1 (placeholders) + Task 9 (02 real)
  - Scenario 模板 → Task 9 (templates/), Task 10 (first instance)
  - Lab 工具棧 → Task 2-7
  - Makefile 完整列表 → Task 6 + 7
  - 三個 lab 取捨(KRaft / Java client / Toxiproxy) → 體現在 compose + Makefile + Toxiproxy 的選用
  - 啟動順序(Day 1-3) → 整個 plan 對應 Day 1-3
  - 「預期/實機分開 commit」紀律 → Task 10 (預期) + Task 11 (實機) 兩次 commit
  - 99-interview-cards 反向產出 → README + Task 1 placeholder(實際打包不在 Day 1-3 範圍)
- ✅ **Placeholder scan**: 沒有 TBD / TODO / "implement later"。所有 code block 都是完整檔案。
- ✅ **Type/name consistency**: `make chaos-isolate` 在 Task 7 定義,被 scenario 模板 (Task 9) 和 scenario 01 (Task 10) 一致引用;網路名 `kafka-handson_default` 來自 compose `name: kafka-handson`,在 chaos-isolate 中對齊使用;Grafana dashboard uid `kafka-overview` 在 dashboard JSON、smoke test、README 一致。
- ✅ **Scope check**: 單一可交付目標(Day 1-3:lab + 第一個 scenario),不混入後續章節。

---

## Plan complete

Plan saved to `docs/superpowers/plans/2026-05-08-kafka-handson-day1-3.md`.
