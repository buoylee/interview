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

.PHONY: load load-clean

# Usage: make load ROWS=1000000
load:
	docker compose --profile load up -d sysbench
	docker compose exec sysbench sysbench oltp_read_write \
	  --db-driver=mysql \
	  --mysql-host=mysql-primary --mysql-port=3306 \
	  --mysql-user=root --mysql-password=root --mysql-db=sbtest \
	  --tables=1 --table-size=$${ROWS:-100000} \
	  prepare

load-clean:
	docker compose exec sysbench sysbench oltp_read_write \
	  --db-driver=mysql \
	  --mysql-host=mysql-primary --mysql-port=3306 \
	  --mysql-user=root --mysql-password=root --mysql-db=sbtest \
	  --tables=1 cleanup
