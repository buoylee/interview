DC := docker compose --project-name mysql-ha --file compose.yml

.PHONY: config up-db down reset ps logs up bootstrap routers init status switchover mysql-a mysql-b

config:
	$(DC) config --quiet

up-db:
	$(DC) up -d db1 db2 db3
	@for service in db1 db2 db3; do \
		until [ "$$(docker inspect --format '{{.State.Health.Status}}' mysql-ha-$$service 2>/dev/null)" = healthy ]; do sleep 2; done; \
	done

down:
	$(DC) down

reset:
	$(DC) down --volumes --remove-orphans
	@mkdir -p evidence
	@find evidence -mindepth 1 -maxdepth 1 -type f -delete

ps:
	$(DC) ps

logs:
	$(DC) logs -f $${S:-db1}

bootstrap: up-db
	$(DC) run --rm cluster-bootstrap

routers: bootstrap
	$(DC) up -d router-a router-b
	@for router in router-a router-b; do \
		$(DC) run --rm shell sh -c "until mysqladmin ping -h$$router -P6446 -uroot -p$${MYSQL_ROOT_PASSWORD:-ha-root} --silent; do sleep 2; done"; \
	done

init: routers
	$(DC) run --rm shell mysql -hrouter-a -P6446 -uroot -p$${MYSQL_ROOT_PASSWORD:-ha-root} < init/01-orders.sql

up: init
	@$(DC) run --rm shell sh -c 'until mysqladmin ping -hrouter-a -P6446 -uha_app -pha-app --silent; do sleep 2; done'
	@$(MAKE) status

status:
	$(DC) run --rm shell mysqlsh --js --file=/bootstrap/status.js

switchover:
	$(DC) run --rm -e MYSQL_TARGET_MEMBER=$${TARGET:-db2} shell mysqlsh --js --file=/bootstrap/set-primary.js

mysql-a:
	$(DC) run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app ha_lab

mysql-b:
	$(DC) run --rm shell mysql -hrouter-b -P6446 -uha_app -pha-app ha_lab
