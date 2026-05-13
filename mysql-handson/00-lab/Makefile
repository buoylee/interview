.PHONY: help up down reset ps logs mysql

help:
	@echo "Targets:"
	@echo "  up         - start the lab (primary only by default)"
	@echo "  down       - stop the lab (keep volumes)"
	@echo "  reset      - stop + remove volumes (fresh state)"
	@echo "  ps         - show container status"
	@echo "  logs S=name - tail logs of service S (default: mysql-primary)"
	@echo "  mysql      - open mysql cli on primary as root, db sbtest"

up:
	docker compose up -d
	@echo "Waiting for primary to be healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' mysql-primary 2>/dev/null)" = "healthy" ]; do sleep 2; done
	@echo "Primary healthy."

down:
	docker compose down

reset:
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f $${S:-mysql-primary}

mysql:
	docker compose exec -it mysql-primary mysql -uroot -proot sbtest
