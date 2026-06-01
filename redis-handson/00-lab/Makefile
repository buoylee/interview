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
