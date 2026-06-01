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
