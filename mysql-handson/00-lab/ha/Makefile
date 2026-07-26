DC := docker compose --project-name mysql-ha --file compose.yml

.PHONY: config up-db down reset ps logs

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
