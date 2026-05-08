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

# Catch-all so `make logs kafka-1` doesn't error
%:
	@:
