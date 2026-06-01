.PHONY: help up down reset ps logs cli

help:
	@echo "Targets:"
	@echo "  up          - start single redis (default)"
	@echo "  down        - stop (keep volume)"
	@echo "  reset       - stop + remove volume (fresh)"
	@echo "  cli         - redis-cli into single redis"
	@echo "  ps / logs   - status / tail logs"

up:
	docker compose up -d redis
	@echo "Waiting for redis to be healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' redis 2>/dev/null)" = "healthy" ]; do sleep 1; done
	@echo "redis healthy on :6379"

down:
	docker compose down

reset:
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f $${S:-redis}

cli:
	docker compose exec -it redis redis-cli

.PHONY: load
# Usage: make load N=100000
load:
	docker compose cp init/gen-keys.sh redis:/tmp/gen-keys.sh
	docker compose exec -e N=$${N:-100000} redis sh /tmp/gen-keys.sh

.PHONY: encoding mem info slowlog latency bigkeys memkeys hotkeys bench monitor

# Usage: make encoding K=mykey
encoding:
	docker compose exec redis redis-cli OBJECT ENCODING $(K)

mem:
	docker compose exec redis redis-cli MEMORY USAGE $(K)

# Usage: make info S=memory
info:
	docker compose exec redis redis-cli INFO $${S:-everything}

slowlog:
	docker compose exec redis redis-cli SLOWLOG GET 10

latency:
	docker compose exec -it redis redis-cli --latency-history

bigkeys:
	docker compose exec redis redis-cli --bigkeys

memkeys:
	docker compose exec redis redis-cli --memkeys

# 需要 maxmemory-policy 为 LFU 才有意义
hotkeys:
	docker compose exec redis redis-cli --hotkeys

# Usage: make bench ARGS="-t set,get -n 100000 -q"
bench:
	docker compose exec redis redis-benchmark $${ARGS:--q -n 100000 -t set,get}

monitor:
	@echo "MONITOR 会显示所有命令,勿在生产用。Ctrl-C 退出。"
	docker compose exec -it redis redis-cli MONITOR

.PHONY: up-cluster cluster-init cli-cluster down-cluster up-obs down-obs chaos-lag chaos-cut chaos-restore

up-cluster:
	docker compose --profile cluster up -d
	@echo "6 nodes up on :7001-7006. Run 'make cluster-init' once."

cluster-init:
	docker compose cp cluster/create-cluster.sh redis-node-1:/tmp/create-cluster.sh
	docker compose exec redis-node-1 sh /tmp/create-cluster.sh
	@echo "cluster created (3 masters + 3 replicas)."

cli-cluster:
	docker compose exec -it redis-node-1 redis-cli -c

down-cluster:
	docker compose --profile cluster down

up-obs:
	docker compose --profile obs up -d
	@echo "Grafana: http://localhost:3000  Prometheus: http://localhost:9090  exporter: :9121"

down-obs:
	docker compose --profile obs stop

# Usage: make chaos-lag MS=500 (在 cluster 节点间注入延迟,需先建 toxiproxy 代理 — 见 10/11 章 scenario)
chaos-lag:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t latency -a latency=$${MS:-500} -n lag node-link || true

chaos-cut:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t timeout -a timeout=0 -n cut node-link || true

chaos-restore:
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n lag node-link
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n cut node-link

.PHONY: up-sentinel down-sentinel sentinel-status

up-sentinel:
	docker compose --profile sentinel up -d
	@echo "1 master + 2 replicas + 3 sentinels up."

down-sentinel:
	docker compose --profile sentinel down

sentinel-status:
	docker compose exec redis-sn-1 redis-cli -p 26379 sentinel master mymaster

.PHONY: up-ui down-ui
up-ui:
	docker compose --profile ui up -d
	@echo "RedisInsight: http://localhost:5540 (add db host=redis port=6379)"
down-ui:
	docker compose --profile ui stop
