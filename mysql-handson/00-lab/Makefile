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

.PHONY: up-obs down-obs

up-obs:
	docker compose --profile obs up -d
	@echo "Grafana: http://localhost:3000 (anonymous viewer)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Exporter: http://localhost:9104/metrics"

down-obs:
	docker compose --profile obs stop

.PHONY: up-replica mysql-replica replica-setup replica-status

up-replica:
	docker compose --profile replica up -d
	@echo "Waiting for replica to be healthy..."
	@until [ "$$(docker inspect -f '{{.State.Health.Status}}' mysql-replica 2>/dev/null)" = "healthy" ]; do sleep 2; done

mysql-replica:
	docker compose exec -it mysql-replica mysql -uroot -proot

# Run once after up-replica to wire replication via GTID auto-position.
replica-setup:
	docker compose exec mysql-replica mysql -uroot -proot -e "\
	  STOP REPLICA; \
	  RESET REPLICA ALL; \
	  CHANGE REPLICATION SOURCE TO \
	    SOURCE_HOST='toxiproxy', \
	    SOURCE_PORT=3316, \
	    SOURCE_USER='repl', \
	    SOURCE_PASSWORD='repl', \
	    SOURCE_AUTO_POSITION=1, \
	    GET_SOURCE_PUBLIC_KEY=1; \
	  START REPLICA;"
	@sleep 2
	@$(MAKE) replica-status

replica-status:
	docker compose exec mysql-replica mysql -uroot -proot -e "SHOW REPLICA STATUS\G" | grep -E "Replica_(IO|SQL)_Running|Seconds_Behind|Last_.*Error"

.PHONY: chaos-replica-lag chaos-replica-cut chaos-restore

# Inject latency on primary->replica connection. Usage: make chaos-replica-lag MS=500
chaos-replica-lag:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t latency -a latency=$${MS:-500} -n lag mysql-primary-for-replica

chaos-replica-cut:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t timeout -a timeout=0 -n cut mysql-primary-for-replica

chaos-restore:
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n lag mysql-primary-for-replica
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n cut mysql-primary-for-replica

.PHONY: explain slow general-log-on general-log-off innodb-status pfs-top processlist

# Usage: make explain SQL="select * from sbtest1 where k=42"
explain:
	@docker compose exec mysql-primary mysql -uroot -proot sbtest -e "EXPLAIN FORMAT=TREE $(SQL); SET optimizer_trace='enabled=on'; $(SQL); SELECT TRACE FROM information_schema.optimizer_trace\G; SET optimizer_trace='enabled=off';"

slow:
	docker compose exec mysql-primary tail -f /var/lib/mysql/slow.log

general-log-on:
	docker compose exec mysql-primary mysql -uroot -proot -e "SET GLOBAL general_log_file='/var/lib/mysql/general.log'; SET GLOBAL general_log=ON;"

general-log-off:
	docker compose exec mysql-primary mysql -uroot -proot -e "SET GLOBAL general_log=OFF;"

innodb-status:
	docker compose exec mysql-primary mysql -uroot -proot -e "SHOW ENGINE INNODB STATUS\G"

pfs-top:
	docker compose exec mysql-primary mysql -uroot -proot -e "\
	  SELECT DIGEST_TEXT, COUNT_STAR, AVG_TIMER_WAIT/1e9 AS avg_ms, SUM_ROWS_EXAMINED \
	  FROM performance_schema.events_statements_summary_by_digest \
	  WHERE SCHEMA_NAME='sbtest' \
	  ORDER BY SUM_TIMER_WAIT DESC LIMIT 10\G"

processlist:
	docker compose exec mysql-primary mysql -uroot -proot -e "SHOW PROCESSLIST;"
