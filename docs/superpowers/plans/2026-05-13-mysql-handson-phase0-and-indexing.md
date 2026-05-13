# MySQL Hands-on Phase 0 (Lab) + Phase 1 (03-indexing) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable MySQL 8.0 lab (Docker + observability + chaos) and complete the `03-indexing` chapter end-to-end (README + 5 scenarios + 2 interview cards), as a proof-of-method before tackling the other 10 chapters in separate plans.

**Architecture:** `interview/mysql-handson/` mirrors `MQ/kafka-handson/`. Lab in `00-lab/` (docker-compose with mysql primary+replica, mysqld_exporter, Prometheus, Grafana, toxiproxy). Chapter folders have `README.md` (7-section template) + `scenarios/*.md`. Cards in `99-interview-cards/`. Scenarios follow predict→run→observe discipline with **two separate commits per scenario**: first the prediction, then the observation.

**Tech Stack:** Docker Compose v2, MySQL 8.0.36, Toxiproxy 2.7, mysqld_exporter 0.15, Prometheus 2.45, Grafana 10.4, sysbench, GNU Make.

**Plan scope:** Phase 0 (Tasks 1-14) + Phase 1 (Tasks 15-30). Phases 2-5 covered by future plans.

**Spec:** `docs/superpowers/specs/2026-05-13-mysql-handson-design.md`

---

## File Structure

```
interview/mysql-handson/
├── README.md                              ← Task 14
├── 00-lab/
│   ├── docker-compose.yml                 ← Tasks 2,7,8,9,10
│   ├── my.cnf/primary.cnf                 ← Task 3
│   ├── my.cnf/replica.cnf                 ← Task 9
│   ├── init/01-create-schema.sql          ← Task 4
│   ├── init/02-replica-user.sql           ← Task 9
│   ├── prometheus.yml                     ← Task 8
│   ├── grafana/provisioning/...           ← Task 8
│   ├── toxiproxy/config.json              ← Task 10
│   └── Makefile                           ← Tasks 5,7,8,9,10,11
├── 01-architecture/README.md              ← Task 1 (stub)
├── 02-innodb-storage/README.md            ← Task 1 (stub)
├── 03-indexing/
│   ├── README.md                          ← Tasks 15, 28
│   └── scenarios/
│       ├── 01-bplus-tree-three-layers.md          ← Tasks 16, 17
│       ├── 02-leftmost-prefix-violation.md        ← Tasks 18, 19
│       ├── 03-covering-index-saves-roundtrip.md   ← Tasks 20, 21
│       ├── 04-icp-on-off-comparison.md            ← Tasks 22, 23
│       └── 05-implicit-type-conversion-kills.md   ← Tasks 24, 25
├── 04-execution-and-explain/README.md     ← Task 1 (stub)
├── 05-mvcc-and-transaction/README.md      ← Task 1 (stub)
├── 06-locking/README.md                   ← Task 1 (stub)
├── 07-logs-and-crashsafe/README.md        ← Task 1 (stub)
├── 08-sql-tuning/README.md                ← Task 1 (stub)
├── 09-replication-and-ha/README.md        ← Task 1 (stub)
├── 10-sharding-and-scaling/README.md      ← Task 1 (stub)
├── 11-ops-and-troubleshooting/README.md   ← Task 1 (stub)
├── 99-interview-cards/
│   ├── q-why-bplus-tree.md                ← Task 29
│   └── q-when-does-index-fail.md          ← Task 30
└── templates/scenario-template.md         ← Task 13
```

---

## Cross-cutting conventions

- **Working directory** for `docker compose` / `make` commands is `interview/mysql-handson/00-lab/` unless stated otherwise.
- **All paths in this plan are relative to repo root** `/Users/buoy/Development/gitrepo/interview/`.
- **Two-commit scenario discipline:** every scenario gets one commit after writing the prediction (sections "我想验证的问题" / "环境" / "预期" / "步骤" filled, but "实机告诉我" empty), then a second commit after running it and filling in observation + gap. Tasks are paired (16+17, 18+19, etc.) to enforce this.
- **Use `docker compose`** (v2 syntax), not `docker-compose`.
- **MySQL client inside container:** `make mysql` is a shortcut for `docker compose exec -it mysql-primary mysql -uroot -proot sbtest`.

---

## Phase 0 — Lab + Scaffolding (Tasks 1-14)

### Task 1: Create directory skeleton + stub chapter READMEs

**Files:**
- Create: `interview/mysql-handson/` (root + 11 chapter dirs + `99-interview-cards/` + `templates/` + `00-lab/` subdirs)
- Create: 10 stub `README.md` files (one per chapter except 03)

- [ ] **Step 1: Create all directories**

```bash
cd /Users/buoy/Development/gitrepo/interview
mkdir -p mysql-handson/{00-lab/{my.cnf,init,grafana/provisioning/{datasources,dashboards},grafana/dashboards,toxiproxy},01-architecture,02-innodb-storage,03-indexing/scenarios,04-execution-and-explain,05-mvcc-and-transaction,06-locking,07-logs-and-crashsafe,08-sql-tuning,09-replication-and-ha,10-sharding-and-scaling,11-ops-and-troubleshooting,99-interview-cards,templates}
```

- [ ] **Step 2: Write stub READMEs for chapters 01,02,04-11**

For each of these 10 chapters create `interview/mysql-handson/<chapter>/README.md` with this exact content (replace `<TITLE>` with the chapter title from the table below):

```markdown
# <TITLE>

> 本章尚未撰写。占位中。完成后将包含 7 段：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 调优实战 / 面试高频考点 / 一句话总结。

参考 `03-indexing/README.md` 作为完整章节示例。
```

Titles:
| 章节 | TITLE |
|---|---|
| 01-architecture | MySQL 整体架构 |
| 02-innodb-storage | InnoDB 存储引擎 |
| 04-execution-and-explain | SQL 执行流程与 Explain |
| 05-mvcc-and-transaction | 事务与 MVCC |
| 06-locking | 锁机制 |
| 07-logs-and-crashsafe | Redo / Undo / Binlog 与 Crash-safe |
| 08-sql-tuning | SQL 调优实战 |
| 09-replication-and-ha | 主从复制与高可用 |
| 10-sharding-and-scaling | 分库分表与扩展性 |
| 11-ops-and-troubleshooting | 运维与排障 |

- [ ] **Step 3: Verify structure**

```bash
cd /Users/buoy/Development/gitrepo/interview
find mysql-handson -type d | sort
find mysql-handson -name README.md | sort
```

Expected: 17 dirs (root + 11 chapters + 99-cards + templates + 00-lab + 00-lab/my.cnf + 00-lab/init + 00-lab/grafana + ...). 10 README.md files (the chapter stubs; root README and 03-indexing/README come later).

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/
git commit -m "mysql-handson: scaffold directory layout + stub chapter READMEs"
```

---

### Task 2: Write minimal docker-compose.yml (primary only)

**Files:**
- Create: `interview/mysql-handson/00-lab/docker-compose.yml`

- [ ] **Step 1: Write docker-compose.yml**

Content:

```yaml
name: mysql-handson

services:
  mysql-primary:
    image: mysql:8.0.36
    container_name: mysql-primary
    command:
      - --defaults-extra-file=/etc/mysql/conf.d/primary.cnf
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: sbtest
    ports:
      - "3306:3306"
    volumes:
      - ./my.cnf/primary.cnf:/etc/mysql/conf.d/primary.cnf:ro
      - ./init:/docker-entrypoint-initdb.d:ro
      - mysql-primary-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-uroot", "-proot"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 30s

volumes:
  mysql-primary-data:
```

- [ ] **Step 2: Validate yaml**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
docker compose config > /dev/null
```

Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/docker-compose.yml
git commit -m "mysql-handson(00-lab): add minimal docker-compose with primary only"
```

---

### Task 3: Write primary my.cnf

**Files:**
- Create: `interview/mysql-handson/00-lab/my.cnf/primary.cnf`

- [ ] **Step 1: Write primary.cnf**

```ini
[mysqld]
server-id = 1
log_bin = mysql-bin
binlog_format = ROW
gtid_mode = ON
enforce_gtid_consistency = ON

# Buffer pool deliberately small so eviction is observable
innodb_buffer_pool_size = 256M
innodb_flush_log_at_trx_commit = 1
innodb_print_all_deadlocks = ON
innodb_status_output = ON

# Slow query / performance schema
slow_query_log = ON
slow_query_log_file = /var/lib/mysql/slow.log
long_query_time = 0.1
log_queries_not_using_indexes = ON

performance_schema = ON

# Misc
default_authentication_plugin = mysql_native_password
character_set_server = utf8mb4
collation_server = utf8mb4_0900_ai_ci
```

- [ ] **Step 2: Verify key settings present**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
grep -E '^(server-id|log_bin|innodb_buffer_pool_size|slow_query_log|performance_schema)' my.cnf/primary.cnf
```

Expected: 5 lines printed.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/my.cnf/primary.cnf
git commit -m "mysql-handson(00-lab): add primary my.cnf with slow log + pfs + small buffer pool"
```

---

### Task 4: Write schema init SQL

**Files:**
- Create: `interview/mysql-handson/00-lab/init/01-create-schema.sql`

- [ ] **Step 1: Write init script**

```sql
-- Schema for hands-on scenarios. sbtest table mirrors sysbench-oltp shape
-- so we can load it with sysbench or hand-crafted INSERTs.

CREATE DATABASE IF NOT EXISTS sbtest
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

USE sbtest;

CREATE TABLE IF NOT EXISTS sbtest1 (
  id INT NOT NULL AUTO_INCREMENT,
  k  INT NOT NULL DEFAULT 0,
  c  CHAR(120) NOT NULL DEFAULT '',
  pad CHAR(60) NOT NULL DEFAULT '',
  PRIMARY KEY (id),
  KEY k_1 (k)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A second table without secondary index, used in scenarios that build
-- their own index to observe before/after.
CREATE TABLE IF NOT EXISTS user_profile (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(64) NOT NULL,
  age  INT NOT NULL,
  city VARCHAR(64) NOT NULL,
  email VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Verify SQL parses (syntax check via mysql --execute is offline-free with mysql client absent; just confirm file exists)**

```bash
ls -l /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab/init/01-create-schema.sql
```

Expected: file size > 0.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/init/01-create-schema.sql
git commit -m "mysql-handson(00-lab): add init schema (sbtest1 + user_profile)"
```

---

### Task 5: Write Makefile basics (up/down/reset/mysql/logs)

**Files:**
- Create: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Write Makefile**

```makefile
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
```

- [ ] **Step 2: Verify Makefile syntactically OK**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make -n up
```

Expected: shows `docker compose up -d` and `until` loop in echo.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/Makefile
git commit -m "mysql-handson(00-lab): add Makefile basics (up/down/reset/mysql)"
```

---

### Task 6: Bring lab up, verify primary works

**Files:** none modified — runtime verification only.

- [ ] **Step 1: Start lab**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make up
```

Expected: `Primary healthy.` printed within ~60s.

- [ ] **Step 2: Verify mysql version + schema**

```bash
docker compose exec mysql-primary mysql -uroot -proot -e "SELECT VERSION(); SHOW DATABASES; SHOW TABLES FROM sbtest;"
```

Expected: VERSION starts with `8.0.36`. Databases include `sbtest`. Tables: `sbtest1`, `user_profile`.

- [ ] **Step 3: Verify slow log + pfs active**

```bash
docker compose exec mysql-primary mysql -uroot -proot -e "SHOW VARIABLES WHERE Variable_name IN ('slow_query_log','performance_schema','innodb_buffer_pool_size','log_bin','gtid_mode');"
```

Expected: slow_query_log=ON, performance_schema=ON, innodb_buffer_pool_size≈268435456 (256M), log_bin=ON, gtid_mode=ON.

- [ ] **Step 4: Tear down and commit verification result**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make down
```

No commit (no file changes); proceed to Task 7. If Step 3 failed, fix `primary.cnf` (Task 3) and retry.

---

### Task 7: Add sysbench service + `make load`

**Files:**
- Modify: `interview/mysql-handson/00-lab/docker-compose.yml`
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Add sysbench service**

Append under `services:` in `docker-compose.yml` (before `volumes:`):

```yaml
  sysbench:
    image: severalnines/sysbench:latest
    container_name: sysbench
    profiles: ["load"]
    depends_on:
      mysql-primary:
        condition: service_healthy
    entrypoint: ["sleep", "infinity"]
```

- [ ] **Step 2: Add Makefile load target**

Append to `Makefile`:

```makefile
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
```

- [ ] **Step 3: Test load with 1000 rows**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make up
make load ROWS=1000
docker compose exec mysql-primary mysql -uroot -proot -e "SELECT COUNT(*) FROM sbtest.sbtest1;"
```

Expected: count ≈ 1000 (sysbench creates with this size).

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/docker-compose.yml mysql-handson/00-lab/Makefile
git commit -m "mysql-handson(00-lab): add sysbench loader (make load ROWS=N)"
```

---

### Task 8: Add observability stack (mysqld_exporter + Prometheus + Grafana)

**Files:**
- Modify: `interview/mysql-handson/00-lab/docker-compose.yml`
- Create: `interview/mysql-handson/00-lab/prometheus.yml`
- Create: `interview/mysql-handson/00-lab/grafana/provisioning/datasources/prometheus.yml`
- Create: `interview/mysql-handson/00-lab/grafana/provisioning/dashboards/dashboards.yml`
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Add services to docker-compose.yml under `profiles: ["obs"]`**

Append under `services:`:

```yaml
  mysqld-exporter:
    image: prom/mysqld-exporter:v0.15.1
    container_name: mysqld-exporter
    profiles: ["obs"]
    depends_on:
      mysql-primary:
        condition: service_healthy
    command:
      - --mysqld.address=mysql-primary:3306
      - --mysqld.username=root
      - --collect.info_schema.innodb_metrics
      - --collect.info_schema.processlist
      - --collect.engine_innodb_status
    environment:
      MYSQLD_EXPORTER_PASSWORD: root
    ports:
      - "9104:9104"

  prometheus:
    image: prom/prometheus:v2.45.6
    container_name: prometheus
    profiles: ["obs"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:10.4.5
    container_name: grafana
    profiles: ["obs"]
    environment:
      GF_AUTH_ANONYMOUS_ENABLED: "true"
      GF_AUTH_ANONYMOUS_ORG_ROLE: "Viewer"
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
```

- [ ] **Step 2: Write prometheus.yml**

```yaml
global:
  scrape_interval: 10s

scrape_configs:
  - job_name: mysqld
    static_configs:
      - targets: ["mysqld-exporter:9104"]
```

- [ ] **Step 3: Write grafana datasource provisioning**

`grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

- [ ] **Step 4: Write grafana dashboard provider**

`grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1
providers:
  - name: mysql-handson
    folder: ""
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 5: Download a community MySQL dashboard**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab/grafana/dashboards
curl -fsSL -o mysql-overview.json \
  "https://grafana.com/api/dashboards/14057/revisions/latest/download"
test -s mysql-overview.json
```

Expected: file size > 1KB. If `grafana.com` not reachable, fall back to an empty stub:

```bash
echo '{"title":"MySQL Overview (placeholder)","panels":[]}' > mysql-overview.json
```

and document in a TODO comment at top of `dashboards.yml` to import dashboard 14057 manually.

- [ ] **Step 6: Add Makefile targets `up-obs` / `down-obs`**

Append to `Makefile`:

```makefile
.PHONY: up-obs down-obs

up-obs:
	docker compose --profile obs up -d
	@echo "Grafana: http://localhost:3000 (anonymous viewer)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Exporter: http://localhost:9104/metrics"

down-obs:
	docker compose --profile obs stop
```

- [ ] **Step 7: Verify observability**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make up
make up-obs
sleep 15
curl -sf http://localhost:9104/metrics | grep -c '^mysql_global_status' | head -1
curl -sf http://localhost:9090/api/v1/targets | grep -o '"health":"up"' | wc -l
curl -sf http://localhost:3000/api/health
```

Expected: exporter returns ≥10 lines, prometheus targets shows ≥1 healthy, grafana returns `{"database":"ok"...}`.

- [ ] **Step 8: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/docker-compose.yml mysql-handson/00-lab/prometheus.yml mysql-handson/00-lab/grafana/ mysql-handson/00-lab/Makefile
git commit -m "mysql-handson(00-lab): add observability stack (exporter+prom+grafana, profile obs)"
```

---

### Task 9: Add replica + replication setup

**Files:**
- Modify: `interview/mysql-handson/00-lab/docker-compose.yml`
- Create: `interview/mysql-handson/00-lab/my.cnf/replica.cnf`
- Create: `interview/mysql-handson/00-lab/init/02-replica-user.sql`
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Write replica.cnf**

```ini
[mysqld]
server-id = 2
log_bin = mysql-bin
binlog_format = ROW
gtid_mode = ON
enforce_gtid_consistency = ON
relay_log = mysql-relay
read_only = ON
super_read_only = ON

innodb_buffer_pool_size = 256M

slow_query_log = ON
slow_query_log_file = /var/lib/mysql/slow.log
long_query_time = 0.1

performance_schema = ON
default_authentication_plugin = mysql_native_password
character_set_server = utf8mb4
```

- [ ] **Step 2: Write replica user init SQL**

`init/02-replica-user.sql`:

```sql
CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED WITH mysql_native_password BY 'repl';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
```

- [ ] **Step 3: Add replica service to docker-compose.yml**

Append under `services:`:

```yaml
  mysql-replica:
    image: mysql:8.0.36
    container_name: mysql-replica
    profiles: ["replica"]
    command:
      - --defaults-extra-file=/etc/mysql/conf.d/replica.cnf
    environment:
      MYSQL_ROOT_PASSWORD: root
    depends_on:
      mysql-primary:
        condition: service_healthy
    ports:
      - "3307:3306"
    volumes:
      - ./my.cnf/replica.cnf:/etc/mysql/conf.d/replica.cnf:ro
      - mysql-replica-data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-uroot", "-proot"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 30s
```

And add `mysql-replica-data:` to the `volumes:` section at the bottom.

- [ ] **Step 4: Add Makefile targets**

Append:

```makefile
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
	    SOURCE_HOST='mysql-primary', \
	    SOURCE_PORT=3306, \
	    SOURCE_USER='repl', \
	    SOURCE_PASSWORD='repl', \
	    SOURCE_AUTO_POSITION=1, \
	    GET_SOURCE_PUBLIC_KEY=1; \
	  START REPLICA;"
	@sleep 2
	@$(MAKE) replica-status

replica-status:
	docker compose exec mysql-replica mysql -uroot -proot -e "SHOW REPLICA STATUS\G" | grep -E "Replica_(IO|SQL)_Running|Seconds_Behind|Last_.*Error"
```

- [ ] **Step 5: Bring up and wire**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make reset       # fresh state so the replica user creation runs on primary
make up
make up-replica
make replica-setup
```

Expected `replica-status` output:
```
Replica_IO_Running: Yes
Replica_SQL_Running: Yes
Seconds_Behind_Source: 0
Last_IO_Error:
Last_SQL_Error:
```

- [ ] **Step 6: Smoke test replication**

```bash
docker compose exec mysql-primary mysql -uroot -proot -e "INSERT INTO sbtest.user_profile (name,age,city,email) VALUES ('alice',30,'Taipei','a@x.com');"
sleep 1
docker compose exec mysql-replica mysql -uroot -proot -e "SELECT * FROM sbtest.user_profile;"
```

Expected: replica returns the inserted row.

- [ ] **Step 7: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/
git commit -m "mysql-handson(00-lab): add replica + GTID replication (profile replica)"
```

---

### Task 10: Add toxiproxy for chaos

**Files:**
- Modify: `interview/mysql-handson/00-lab/docker-compose.yml`
- Create: `interview/mysql-handson/00-lab/toxiproxy/config.json`
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Write toxiproxy config**

`toxiproxy/config.json`:

```json
[
  {
    "name": "mysql-primary-for-replica",
    "listen": "0.0.0.0:3316",
    "upstream": "mysql-primary:3306",
    "enabled": true
  }
]
```

- [ ] **Step 2: Add toxiproxy service to docker-compose.yml**

Append under `services:`:

```yaml
  toxiproxy:
    image: ghcr.io/shopify/toxiproxy:2.7.0
    container_name: toxiproxy
    profiles: ["replica"]
    command: ["-host=0.0.0.0", "-config=/config/config.json"]
    volumes:
      - ./toxiproxy/config.json:/config/config.json:ro
    ports:
      - "8474:8474"
      - "3316:3316"
```

- [ ] **Step 3: Update replica setup to go through toxiproxy**

Edit the `replica-setup` target in `Makefile`, change `SOURCE_HOST='mysql-primary'` and `SOURCE_PORT=3306` to:

```
SOURCE_HOST='toxiproxy', \
SOURCE_PORT=3316, \
```

- [ ] **Step 4: Add chaos targets**

Append to `Makefile`:

```makefile
.PHONY: chaos-replica-lag chaos-replica-cut chaos-restore

# Inject latency on primary->replica connection. Usage: make chaos-replica-lag MS=500
chaos-replica-lag:
	docker compose exec toxiproxy /toxiproxy-cli toxic add mysql-primary-for-replica \
	  -t latency -a latency=$${MS:-500} -n lag

chaos-replica-cut:
	docker compose exec toxiproxy /toxiproxy-cli toxic add mysql-primary-for-replica \
	  -t timeout -a timeout=0 -n cut

chaos-restore:
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n lag mysql-primary-for-replica
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n cut mysql-primary-for-replica
```

- [ ] **Step 5: Verify**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make reset
make up
make up-replica
make replica-setup
make chaos-replica-lag MS=1000
# Generate writes on primary
docker compose exec mysql-primary mysql -uroot -proot -e "INSERT INTO sbtest.user_profile (name,age,city,email) SELECT 'bob',25,'TPE','b@x.com' FROM information_schema.tables LIMIT 50;"
sleep 3
make replica-status
make chaos-restore
sleep 3
make replica-status
```

Expected: With lag, `Seconds_Behind_Source` > 0. After `chaos-restore` and a few seconds, returns to 0.

- [ ] **Step 6: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/
git commit -m "mysql-handson(00-lab): add toxiproxy + chaos-replica-lag/cut/restore"
```

---

### Task 11: Add observation helpers (explain / slow / innodb-status / pfs-top)

**Files:**
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Append observation targets**

```makefile
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
```

- [ ] **Step 2: Smoke test each**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make explain SQL="SELECT * FROM sbtest1 WHERE k=42"
make innodb-status | head -20
make pfs-top
make processlist
```

Expected: each returns output without error. The explain target prints a TREE plan and an optimizer_trace JSON.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/Makefile
git commit -m "mysql-handson(00-lab): add observation helpers (explain/slow/innodb-status/pfs-top)"
```

---

### Task 12: Add adminer (optional web UI under profile)

**Files:**
- Modify: `interview/mysql-handson/00-lab/docker-compose.yml`
- Modify: `interview/mysql-handson/00-lab/Makefile`

- [ ] **Step 1: Add adminer service**

```yaml
  adminer:
    image: adminer:4.8.1
    container_name: adminer
    profiles: ["ui"]
    ports:
      - "8080:8080"
    depends_on:
      mysql-primary:
        condition: service_healthy
```

- [ ] **Step 2: Add Makefile target**

```makefile
.PHONY: up-ui

up-ui:
	docker compose --profile ui up -d
	@echo "Adminer: http://localhost:8080 (server=mysql-primary user=root pass=root db=sbtest)"
```

- [ ] **Step 3: Verify**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make up-ui
sleep 3
curl -sf http://localhost:8080/ | head -1
```

Expected: html response.

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/00-lab/docker-compose.yml mysql-handson/00-lab/Makefile
git commit -m "mysql-handson(00-lab): add adminer web UI (profile ui)"
```

---

### Task 13: Write scenario template

**Files:**
- Create: `interview/mysql-handson/templates/scenario-template.md`

- [ ] **Step 1: Write template**

```markdown
# Scenario: <一句话描述>

## 我想验证的问题

<一句话。例：「同一条 SELECT，在 1k 行和 100w 行时优化器是否会走不同的计划？」>

## 预期（写实验前的假设）

<把你「以为」的行为写下来，越具体越好。写完才能跑，跑完才能对照。>

> 纪律：本节填完后请单独 commit 一次，再开始跑 lab。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`
- schema：`init/01-create-schema.sql` 自动创建 `sbtest1`、`user_profile`
- 灌数据：`make load ROWS=<N>`（如适用）

## 步骤

1. ...
2. ...
3. ...

## 实机告诉我（跑完当天填）

```
<贴 explain / SHOW STATUS / SHOW ENGINE INNODB STATUS / 慢查日志片段>
```

观察到的关键事实：

- ...
- ...

## ⚠️ 预期 vs 实机落差

<这是本 scenario 的核心输出。完全对应预期 = scenario 太简单或预期太模糊。>

- 我以为：……
- 实际：……
- 我学到：……

## 连到的面试卡

- `99-interview-cards/q-xxx.md`
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/templates/scenario-template.md
git commit -m "mysql-handson(templates): add scenario template (predict→run→observe)"
```

---

### Task 14: Write top-level README

**Files:**
- Create: `interview/mysql-handson/README.md`

- [ ] **Step 1: Write README**

```markdown
# MySQL Hands-on — 系统笔记 + 实机白皮书

把 `interview/mysql/` 的零散笔记在实机上跑过一遍，沉淀成有结构的 scenario + 章节笔记 + 面试卡。

设计来源：`docs/superpowers/specs/2026-05-13-mysql-handson-design.md`

## 怎么用这个 repo

1. **第一次来**：`cd 00-lab && make up`，等镜像下完。`make mysql` 进 cli，看到 `sbtest>` 提示符就 OK。想看面板再 `make up-obs`，浏览器开 http://localhost:3000。
2. **想答某个面试题**：去 `99-interview-cards/` 找卡，每张卡链回 scenario 作为证据。
3. **想学某个主题**：从章节 README 开始，每章固定 7 段（核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 调优实战 / 面试高频考点 / 一句话总结）。
4. **想加新 scenario**：复制 `templates/scenario-template.md` 到对应章节 `scenarios/`，**先写「预期」、commit 一次**，再跑、再 commit 观察结果。预期/实机分两次 commit 是刻意的纪律。

## 章节地图

- `01-architecture/` — Server 层 + 引擎层 + 一条 SQL 的旅程
- `02-innodb-storage/` — 页/区/段 + Buffer Pool + Change Buffer + AHI
- `03-indexing/` — B+树 / 聚簇 vs 二级 / 联合索引 / 覆盖 / ICP / MRR ← **第一个有完整 scenario 的章节**
- `04-execution-and-explain/` — Parser → Optimizer → Executor + Explain 完整解读
- `05-mvcc-and-transaction/` — 事务 ACID + MVCC + Undo Log + RR 真相
- `06-locking/` — 行/表/间隙/Next-Key/插入意向 + 死锁案例
- `07-logs-and-crashsafe/` — Redo / Undo / Binlog + WAL + 两阶段提交
- `08-sql-tuning/` — 慢查日志 + 索引设计 + JOIN + ORDER BY + filesort + 临时表
- `09-replication-and-ha/` — 主从 + 半同步 + MGR + 读写分离
- `10-sharding-and-scaling/` — 分库分表 + 全局 ID + 在线迁移
- `11-ops-and-troubleshooting/` — Online DDL + pt-osc + 备份 + 参数调优
- `99-interview-cards/` — 反向产出的面试题答案卡

## Lab 速查

```bash
cd 00-lab

make up                                       # 起 primary (默认)
make up-replica && make replica-setup         # 起 replica + 建立复制
make up-obs                                   # 起 prom + grafana + exporter
make up-ui                                    # 起 adminer
make down / make reset                        # 停 / 重置

make mysql / make mysql-replica               # 进 cli
make load ROWS=1000000                        # sysbench 灌数据

make explain SQL="select ..."                 # explain + optimizer_trace
make slow                                     # tail 慢查日志
make innodb-status                            # SHOW ENGINE INNODB STATUS
make pfs-top                                  # performance_schema top SQL
make processlist

make chaos-replica-lag MS=500                 # 注入主从延迟
make chaos-replica-cut                        # 切断主从
make chaos-restore
```

| 服务 | URL |
|---|---|
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Adminer | http://localhost:8080 |
| Toxiproxy API | http://localhost:8474 |

## 纪律

写 scenario 时遵守的三条规则（不要省）：

1. **「预期」必须在跑之前写**，且要单独 commit 一次。预期被实机污染就学不到东西了。
2. **「实机告诉我」当天填**。隔天就忘了当下的惊讶点。
3. **「⚠️ 预期 vs 实机落差」是这个方法的核心输出**。每个 scenario 都「完全对应预期」说明 scenario 太简单或预期太模糊。
```

- [ ] **Step 2: Verify links**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson
for d in 01-architecture 02-innodb-storage 03-indexing 04-execution-and-explain 05-mvcc-and-transaction 06-locking 07-logs-and-crashsafe 08-sql-tuning 09-replication-and-ha 10-sharding-and-scaling 11-ops-and-troubleshooting 99-interview-cards templates; do
  test -d "$d" && echo "OK $d" || echo "MISSING $d"
done
```

Expected: 13 "OK" lines.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/README.md
git commit -m "mysql-handson: add top-level README (entry point + lab quickref)"
```

---

## Phase 1 — 03-indexing chapter complete (Tasks 15-30)

### Task 15: Scaffold 03-indexing/README.md with 7 sections

**Files:**
- Create: `interview/mysql-handson/03-indexing/README.md`

- [ ] **Step 1: Write skeleton with all 7 sections present**

```markdown
# 索引（Indexing）

## 1. 核心问题

索引是「在不全表扫的前提下，快速定位行」的数据结构。本章解决三件事：
**(a)** 为什么 MySQL/InnoDB 用 B+ 树，不用其他结构；
**(b)** 怎么读懂一条 SQL 走没走索引、走的是哪个；
**(c)** 写 SQL 和建表时，怎样的索引设计才能跑得快。

## 2. 直觉理解

想像一本 1000 页的字典，没有索引你要从头翻；按拼音排序的目录是「一层索引」，能让你跳到大概页数；如果目录本身又有「字头索引」（A 在前 50 页，B 在 51-100…），就是「两层索引」。InnoDB 的 B+ 树就是这种**多层目录**，但有两个关键特点：

- **目录不是一本，是两本**：一本按主键排（叫聚簇索引，叶子节点直接存整行数据），其余的都是「指向主键的目录」（二级索引，叶子节点只存主键值，要回去聚簇索引再查一次，叫「回表」）
- **每一页 16KB**：所以三层 B+ 树能放下大约几千万行（具体数字见 Scenario 01）

## 3. 原理深入

> 写完 Scenarios 01-05 之后回来补这一节，引用 scenario 数据。

待补的子节：
- 3.1 B+ 树 vs B 树 vs 红黑树 vs Hash：为什么选 B+ 树
- 3.2 聚簇索引 vs 二级索引：叶子节点存什么、回表是什么
- 3.3 联合索引 + 最左前缀
- 3.4 覆盖索引（covering index）省回表
- 3.5 索引下推（Index Condition Pushdown，ICP）
- 3.6 Multi-Range Read（MRR）
- 3.7 索引为什么会失效（前导通配、隐式类型转换、对列做函数运算、OR 跨列）

## 4. 日常开发应用

> 写完 Scenarios 02-05 之后补。重点：建表时怎么定主键、怎么定联合索引顺序、什么时候加覆盖索引、不要让 ORM 自动生成奇怪的 SQL。

## 5. 调优实战

> 写完 Scenarios 02-05 之后补。case：
> - 拿到一条慢 SQL，先看 explain 的 type/key/rows/Extra 四列
> - 怀疑索引没走，用 optimizer_trace 看成本估算
> - 改不动 SQL 时，怎么加 hint（force index / use index / 8.0 的 optimizer hint）

## 6. 面试高频考点

> 写完后补。常见对比表：
> - 聚簇 vs 非聚簇 / 主键索引 vs 唯一索引
> - 何时回表 / 何时不回表
> - 联合索引顺序的两条原则（区分度 + 最左前缀使用率）
> - "为什么用 B+ 树" 三句话答法

## 7. 一句话总结

> 写完后补。3-5 行。

## Scenarios

- [01 - B+ 树三层能放多少行](scenarios/01-bplus-tree-three-layers.md)
- [02 - 联合索引最左前缀失效](scenarios/02-leftmost-prefix-violation.md)
- [03 - 覆盖索引省回表](scenarios/03-covering-index-saves-roundtrip.md)
- [04 - 索引下推（ICP）开关前后对比](scenarios/04-icp-on-off-comparison.md)
- [05 - 隐式类型转换让索引失效](scenarios/05-implicit-type-conversion-kills-index.md)
```

- [ ] **Step 2: Verify 7 sections present**

```bash
grep -c '^## [1-7]\.' /Users/buoy/Development/gitrepo/interview/mysql-handson/03-indexing/README.md
```

Expected: `7`

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/README.md
git commit -m "mysql-handson(03-indexing): scaffold chapter README with 7 sections"
```

---

### Task 16: Scenario 01 — write prediction (B+ tree three layers)

**Files:**
- Create: `interview/mysql-handson/03-indexing/scenarios/01-bplus-tree-three-layers.md`

- [ ] **Step 1: Write scenario file with prediction sections only**

```markdown
# Scenario 01: B+ 树三层能放多少行

## 我想验证的问题

InnoDB 默认页大小是 16KB。如果一棵 B+ 树只有 3 层（root + 中间层 + 叶子层），主键是 BIGINT（8 字节），它能放多少行数据？「索引最多 3 层」这句话是从哪来的？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**。基于你目前的理解（不要查），把下列空格填上：
>
> - 一页 16KB，一个「指针 + 主键」对大约占 _____ 字节（如果主键是 BIGINT），所以一页能放约 _____ 个非叶子节点条目（向上取整）。
> - 三层 B+ 树：root × 中间 × 叶子，每个叶子页能放约 _____ 行（如果一行平均 1KB）。
> - 三层总行数估算 ≈ _____ 行。
> - 我以为答案是 1000 万级 / 1 亿级 / 10 亿级？为什么？
>
> 这一段填完就 commit 一次（"prediction only"），再开始下面的步骤。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`
- schema：`init/01-create-schema.sql`（用 `sbtest1` 表，主键 INT 默认自增）
- 注意：本 scenario 不需要灌很多数据，主要是查 `information_schema` 估算

## 步骤

1. 起 lab：`make up`
2. 灌少量数据，用来观察页结构：`make load ROWS=10000`
3. 查表的存储参数和实际页数：

   ```sql
   SELECT NAME, FILE_SIZE, ALLOCATED_SIZE
   FROM information_schema.INNODB_TABLESPACES
   WHERE NAME LIKE 'sbtest%';

   SELECT TABLE_NAME, INDEX_NAME, STAT_NAME, STAT_VALUE, STAT_DESCRIPTION
   FROM mysql.innodb_index_stats
   WHERE TABLE_NAME = 'sbtest1';
   ```
4. 查每行实际占多少字节：

   ```sql
   SHOW TABLE STATUS LIKE 'sbtest1'\G
   ```

   看 `Avg_row_length`、`Data_length`、`Index_length`。
5. 估算公式：
   - 非叶子节点：每个条目 ≈ 主键大小 + 6 字节（页号指针） = 8+6=14 字节（BIGINT 主键）。一页 16384 字节，约能放 16384/14 ≈ 1170 个条目。
   - 叶子节点：每页能放 16384/Avg_row_length 行。
   - 三层总行数 = 1170 × 1170 × (16384/Avg_row_length)
6. 把估算结果与 `mysql.innodb_index_stats` 里 `n_leaf_pages`、`size`、`n_diff_pfx*` 等指标对照。

## 实机告诉我（跑完当天填）

```
<贴 SHOW TABLE STATUS 输出片段>
<贴 innodb_index_stats 关键行>
```

观察到的关键事实：

- ...

## ⚠️ 预期 vs 实机落差

- 我以为：……
- 实际：……
- 我学到：……

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
```

- [ ] **Step 2: Verify file structure**

```bash
grep -c '^## ' /Users/buoy/Development/gitrepo/interview/mysql-handson/03-indexing/scenarios/01-bplus-tree-three-layers.md
```

Expected: ≥ 7 sections.

- [ ] **Step 3: Commit (prediction-only commit)**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/01-bplus-tree-three-layers.md
git commit -m "mysql-handson(03-indexing/01): scaffold B+ tree depth scenario (prediction TBD)"
```

> **Reader of this plan:** the user fills in `## 预期` content before running. The commit above intentionally lands the scenario in "prediction not yet filled" state so the next commit is "prediction filled" — that's the discipline. If you (the executing engineer) are the user, fill in the prediction NOW based on your current understanding, then `git commit --amend` (or a new commit) labeled "prediction filled" before proceeding to Task 17.

---

### Task 17: Scenario 01 — run and observe

**Files:**
- Modify: `interview/mysql-handson/03-indexing/scenarios/01-bplus-tree-three-layers.md`

- [ ] **Step 1: Bring lab up and load**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
make up
make load ROWS=10000
```

- [ ] **Step 2: Capture observations**

```bash
docker compose exec mysql-primary mysql -uroot -proot sbtest -e "SHOW TABLE STATUS LIKE 'sbtest1'\G"
docker compose exec mysql-primary mysql -uroot -proot -e "SELECT TABLE_NAME, INDEX_NAME, STAT_NAME, STAT_VALUE FROM mysql.innodb_index_stats WHERE TABLE_NAME='sbtest1';"
```

- [ ] **Step 3: Update the scenario file**

In `01-bplus-tree-three-layers.md`, replace the `## 实机告诉我` section content with the captured output (paste in fenced blocks) and the `⚠️ 预期 vs 实机落差` with at least three bullets:
- `我以为：<your prediction>`
- `实际：<actual numbers>`
- `我学到：<the gap, e.g., "Avg_row_length 不是 1KB 而是 X 字节，所以三层能装的行数是 Y，比我预期多/少 Z 倍">`

- [ ] **Step 4: Commit (observation commit)**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/01-bplus-tree-three-layers.md
git commit -m "mysql-handson(03-indexing/01): observe B+ tree depth on real data"
```

---

### Task 18: Scenario 02 — prediction (leftmost prefix)

**Files:**
- Create: `interview/mysql-handson/03-indexing/scenarios/02-leftmost-prefix-violation.md`

- [ ] **Step 1: Write scenario file**

```markdown
# Scenario 02: 联合索引最左前缀失效

## 我想验证的问题

表 `user_profile` 加联合索引 `(city, age, name)`。下面 4 条查询哪些走索引、走到第几列、Extra 提示什么？

```sql
-- Q1
SELECT * FROM user_profile WHERE city='Taipei' AND age=30 AND name='alice';
-- Q2
SELECT * FROM user_profile WHERE city='Taipei' AND age=30;
-- Q3
SELECT * FROM user_profile WHERE city='Taipei' AND name='alice';
-- Q4
SELECT * FROM user_profile WHERE age=30 AND name='alice';
```

## 预期（写实验前的假设）

> 填空（不要查）。对每条 Q 给出：
> - 走不走索引（看 explain.key）
> - 走到第几列（看 key_len 大致估算）
> - Extra 里有没有 `Using where` / `Using index condition` / `Using index`

|     | 走索引？ | 用到几列 | Extra |
|-----|---|---|---|
| Q1  |   |   |   |
| Q2  |   |   |   |
| Q3  |   |   |   |
| Q4  |   |   |   |

> 填完先 commit 一次。

## 环境

- `make up`
- 灌少量数据：

  ```sql
  INSERT INTO user_profile (name,age,city,email)
  SELECT CONCAT('u',n), 20+(n%50), ELT(1+(n%5),'Taipei','Tokyo','Seoul','HK','SF'), CONCAT('u',n,'@x.com')
  FROM (SELECT a.n+10*b.n+100*c.n AS n FROM
        (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) a,
        (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) b,
        (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9) c
       ) t;
  ```
  这会插入 1000 行，城市/年龄/姓名都有分布。

## 步骤

1. 建联合索引：`ALTER TABLE user_profile ADD INDEX idx_city_age_name (city, age, name);`
2. 对每条 Q 跑 `EXPLAIN FORMAT=TRADITIONAL <sql>` 和 `EXPLAIN FORMAT=TREE <sql>`
3. 记录 type / key / key_len / rows / Extra
4. 用 `make explain SQL="..."` 也跑一次看 optimizer_trace（重点看 `range_scan_alternatives`、`cost_for_plan`）

## 实机告诉我

```
<贴每条 Q 的 explain 输出>
```

|     | 走索引？ | 用到几列 | Extra | 备注 |
|-----|---|---|---|---|
| Q1  |   |   |   |   |
| Q2  |   |   |   |   |
| Q3  |   |   |   |   |
| Q4  |   |   |   |   |

## ⚠️ 预期 vs 实机落差

- 我以为 Q3 走全部三列：实际 ……
- 我以为 Q4 不走索引：实际 ……
- 我学到：「最左前缀」对 = 号查询和范围查询的行为分别是 ……

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
```

- [ ] **Step 2: Commit (prediction-pending)**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/02-leftmost-prefix-violation.md
git commit -m "mysql-handson(03-indexing/02): scaffold leftmost-prefix scenario"
```

> User fills in prediction table now, commits, then proceeds to Task 19.

---

### Task 19: Scenario 02 — run and observe

**Files:**
- Modify: `interview/mysql-handson/03-indexing/scenarios/02-leftmost-prefix-violation.md`

- [ ] **Step 1: Run all 4 queries**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
docker compose exec mysql-primary mysql -uroot -proot sbtest -e "ALTER TABLE user_profile ADD INDEX idx_city_age_name (city, age, name);"
# Run the INSERT block from the scenario file once
for Q in \
  "EXPLAIN SELECT * FROM user_profile WHERE city='Taipei' AND age=30 AND name='alice'" \
  "EXPLAIN SELECT * FROM user_profile WHERE city='Taipei' AND age=30" \
  "EXPLAIN SELECT * FROM user_profile WHERE city='Taipei' AND name='alice'" \
  "EXPLAIN SELECT * FROM user_profile WHERE age=30 AND name='alice'"; do
  echo "=== $Q ==="
  docker compose exec mysql-primary mysql -uroot -proot sbtest -e "$Q\G"
done
```

- [ ] **Step 2: Fill in observation table + gap**

Edit `02-leftmost-prefix-violation.md`:
- Paste explain outputs into `## 实机告诉我`
- Fill the result table
- Write 3+ bullets in `## ⚠️ 预期 vs 实机落差` covering at minimum:
  - What Q3 actually does (it uses city only — name skipped because age is a gap)
  - Whether Q4 truly does not use the index (likely full scan unless small table → in-memory)
  - The "skip scan" behavior in 8.0 if it kicks in

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/02-leftmost-prefix-violation.md
git commit -m "mysql-handson(03-indexing/02): observe leftmost-prefix behavior in 8.0"
```

---

### Task 20: Scenario 03 — prediction (covering index)

**Files:**
- Create: `interview/mysql-handson/03-indexing/scenarios/03-covering-index-saves-roundtrip.md`

- [ ] **Step 1: Write scenario**

```markdown
# Scenario 03: 覆盖索引省回表

## 我想验证的问题

同样一条 `SELECT name, age FROM user_profile WHERE city='Taipei'`：
- 索引 A：`(city)`
- 索引 B：`(city, name, age)`（覆盖了 SELECT 列表）

走 A 和走 B 的 explain 有什么差别？性能差多少？

## 预期

> 填空：
> - 索引 A 的 Extra 会显示 ……
> - 索引 B 的 Extra 会显示 ……
> - 回表代价大约是几次随机 IO？
> - 性能差大概几倍？

## 环境

- 接 Scenario 02 的数据（1000+ 行）。若全新环境，先 `make up` + 插入数据。

## 步骤

1. 仅保留单列索引：`ALTER TABLE user_profile DROP INDEX idx_city_age_name, ADD INDEX idx_city (city);`
2. 跑 `EXPLAIN FORMAT=TREE SELECT name, age FROM user_profile WHERE city='Taipei';`，记录 Extra
3. 换成覆盖索引：`ALTER TABLE user_profile DROP INDEX idx_city, ADD INDEX idx_city_name_age (city, name, age);`
4. 同样的 SQL 再跑 explain，对比 Extra
5. 对两个版本各跑 `BENCHMARK(1000, ...)` 或 `SELECT SQL_NO_CACHE ...` 多次取平均

## 实机告诉我

```
<两次 explain 的 Extra 行>
<计时对比>
```

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-why-bplus-tree.md`
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/03-covering-index-saves-roundtrip.md
git commit -m "mysql-handson(03-indexing/03): scaffold covering-index scenario"
```

---

### Task 21: Scenario 03 — run and observe

**Files:**
- Modify: `interview/mysql-handson/03-indexing/scenarios/03-covering-index-saves-roundtrip.md`

- [ ] **Step 1: Run the steps from the scenario**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
docker compose exec mysql-primary mysql -uroot -proot sbtest -e "
ALTER TABLE user_profile DROP INDEX idx_city_age_name;
ALTER TABLE user_profile ADD INDEX idx_city (city);
EXPLAIN FORMAT=TREE SELECT name, age FROM user_profile WHERE city='Taipei';
ALTER TABLE user_profile DROP INDEX idx_city;
ALTER TABLE user_profile ADD INDEX idx_city_name_age (city, name, age);
EXPLAIN FORMAT=TREE SELECT name, age FROM user_profile WHERE city='Taipei';
"
```

- [ ] **Step 2: Fill observation in scenario file**

Look for `Using index` (covering) vs absence of it (回表). Fill in `## 实机告诉我` and `## ⚠️ 预期 vs 实机落差` (≥3 bullets).

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/03-covering-index-saves-roundtrip.md
git commit -m "mysql-handson(03-indexing/03): observe covering vs non-covering index"
```

---

### Task 22: Scenario 04 — prediction (ICP on/off)

**Files:**
- Create: `interview/mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md`

- [ ] **Step 1: Write scenario**

```markdown
# Scenario 04: 索引下推（ICP）开关前后对比

## 我想验证的问题

沿用 Scenario 03 建立的索引 `idx_city_name_age (city, name, age)`，SQL：
```sql
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
```

`name LIKE '%a%'` 是范围条件，但 `name` **在索引里**——这是 ICP 起作用的前提（索引含但 WHERE 不是等值/不能定位区间的列）。
- ICP 开（默认）：Extra 会是什么？引擎层 vs Server 层各做什么？
- ICP 关：Extra 会变成什么？rows 数字会不会变？读了多少行回去 Server 层过滤？

## 预期

> 填表：

|     | Extra | rows | 谁过滤 name LIKE |
|-----|---|---|---|
| ICP on  |   |   |   |
| ICP off |   |   |   |

## 环境

- 已建索引 `idx_city_name_age (city, name, age)`（来自 Scenario 03）

## 步骤

1. ICP 默认开。跑 `EXPLAIN FORMAT=TREE` + 业务 SQL，记录
2. `SET optimizer_switch='index_condition_pushdown=off';`
3. 同 SQL 再跑 explain，对比
4. 用 `SHOW SESSION STATUS LIKE 'Handler_read%';` 在两种状态下分别跑一次 SELECT，看 Handler_read_next 差几倍
5. 跑完 `SET optimizer_switch='index_condition_pushdown=on';` 还原

## 实机告诉我

|     | Extra | rows | Handler_read_next |
|-----|---|---|---|

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md
git commit -m "mysql-handson(03-indexing/04): scaffold ICP on/off scenario"
```

---

### Task 23: Scenario 04 — run and observe

**Files:**
- Modify: `interview/mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md`

- [ ] **Step 1: Run**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
docker compose exec mysql-primary mysql -uroot -proot sbtest -e "
EXPLAIN FORMAT=TREE SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
FLUSH STATUS;
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
SHOW SESSION STATUS LIKE 'Handler_read%';

SET optimizer_switch='index_condition_pushdown=off';
EXPLAIN FORMAT=TREE SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
FLUSH STATUS;
SELECT * FROM user_profile WHERE city='Taipei' AND age > 25 AND name LIKE '%a%';
SHOW SESSION STATUS LIKE 'Handler_read%';
SET optimizer_switch='index_condition_pushdown=on';
"
```

- [ ] **Step 2: Fill observation + gap**

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/04-icp-on-off-comparison.md
git commit -m "mysql-handson(03-indexing/04): observe ICP impact via Handler_read_next"
```

---

### Task 24: Scenario 05 — prediction (implicit type conversion)

**Files:**
- Create: `interview/mysql-handson/03-indexing/scenarios/05-implicit-type-conversion-kills-index.md`

- [ ] **Step 1: Write scenario**

```markdown
# Scenario 05: 隐式类型转换让索引失效

## 我想验证的问题

`user_profile.email` 是 VARCHAR(128) 且有索引。
- Q1: `WHERE email = 'a@x.com'` — 走索引吗？
- Q2: `WHERE email = 100` — 走索引吗？type 列是什么？
- Q3: 反例：表 `t(id VARCHAR(10), idx)` 然后 `WHERE id = 100` —— 走索引吗？

## 预期

> 填空：
> - Q1 走索引 / type=___
> - Q2 走 / 不走？为什么？
> - Q3 走 / 不走？为什么？
> - 规则一句话：当 _________ 时索引失效，因为 ……

## 环境

- 沿用 user_profile，先建 email 索引：`ALTER TABLE user_profile ADD INDEX idx_email (email);`
- 额外建对照表：

  ```sql
  CREATE TABLE varchar_id_test (id VARCHAR(10) PRIMARY KEY, payload VARCHAR(20));
  INSERT INTO varchar_id_test VALUES ('100','a'),('200','b'),('abc','c');
  ```

## 步骤

1. `EXPLAIN SELECT * FROM user_profile WHERE email='a@x.com';`
2. `EXPLAIN SELECT * FROM user_profile WHERE email=100;` ← 注意类型对比方向
3. `EXPLAIN SELECT * FROM varchar_id_test WHERE id=100;`
4. `SHOW WARNINGS;` 看是否有 1739/类型转换警告

## 实机告诉我

|   | type | key | rows | warnings |
|---|---|---|---|---|
| Q1 |   |   |   |   |
| Q2 |   |   |   |   |
| Q3 |   |   |   |   |

## ⚠️ 预期 vs 实机落差

- ...

## 连到的面试卡

- `99-interview-cards/q-when-does-index-fail.md`
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/05-implicit-type-conversion-kills-index.md
git commit -m "mysql-handson(03-indexing/05): scaffold implicit-type-conversion scenario"
```

---

### Task 25: Scenario 05 — run and observe

**Files:**
- Modify: `interview/mysql-handson/03-indexing/scenarios/05-implicit-type-conversion-kills-index.md`

- [ ] **Step 1: Run**

```bash
cd /Users/buoy/Development/gitrepo/interview/mysql-handson/00-lab
docker compose exec mysql-primary mysql -uroot -proot sbtest -e "
ALTER TABLE user_profile ADD INDEX idx_email (email);
CREATE TABLE IF NOT EXISTS varchar_id_test (id VARCHAR(10) PRIMARY KEY, payload VARCHAR(20));
INSERT IGNORE INTO varchar_id_test VALUES ('100','a'),('200','b'),('abc','c');

EXPLAIN SELECT * FROM user_profile WHERE email='a@x.com';
SHOW WARNINGS;

EXPLAIN SELECT * FROM user_profile WHERE email=100;
SHOW WARNINGS;

EXPLAIN SELECT * FROM varchar_id_test WHERE id=100;
SHOW WARNINGS;
"
```

- [ ] **Step 2: Fill observation table + gap**

The key insight to record: MySQL converts the VARCHAR column to number per the comparison rules (CONVERT(col, DOUBLE) wraps the column, making the index useless), but `string_col = string_literal` is fine.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/scenarios/05-implicit-type-conversion-kills-index.md
git commit -m "mysql-handson(03-indexing/05): observe implicit conversion turning index into full scan"
```

---

### Task 26: Backfill 03-indexing README section 3 (原理深入)

**Files:**
- Modify: `interview/mysql-handson/03-indexing/README.md` (replace the `## 3. 原理深入` placeholder)

- [ ] **Step 1: Rewrite section 3**

Replace the existing `## 3. 原理深入` block with this content (keep sections 1, 2, 4-7 intact):

```markdown
## 3. 原理深入

### 3.1 为什么是 B+ 树

| 数据结构 | 问题 | B+ 树的回应 |
|---|---|---|
| 二叉树 / 红黑树 | 树太高，10^7 行要 23 层 → 23 次 IO | B+ 树扇出大（一页 ≈ 1170 条目），3 层就够装千万级（见 Scenario 01） |
| Hash | 不支持范围、不支持排序 | B+ 树叶子节点按顺序串成链表 |
| B 树 | 内部节点也存数据 → 扇出小、范围查找要回上层 | B+ 树内部节点只存键，所有数据在叶子，扇出更大 + 范围扫描沿链表 |

### 3.2 聚簇索引 vs 二级索引

- **聚簇索引**（clustered，又叫主键索引）：叶子节点 = 整行数据。InnoDB 每张表有且仅有一个聚簇索引。没显式主键时，InnoDB 选第一个非空 UNIQUE 列；都没有就用隐藏的 6 字节 `DB_ROW_ID`。
- **二级索引**（secondary，又叫非聚簇）：叶子节点 = 索引列值 + **主键值**。所以走二级索引拿不在索引里的列时，要再用主键去聚簇索引查一遍——这叫**回表**。
- 一句话区别：MyISAM 的二级索引叶子节点存的是「物理行地址」，InnoDB 存的是「主键值」。所以 InnoDB 的主键变更代价高，主键不要选会变的列。

### 3.3 联合索引 + 最左前缀

联合索引 `(a,b,c)` 按 a→b→c 排序。能走索引的条件（详见 Scenario 02）：

- `WHERE a=? AND b=? AND c=?` — 全用
- `WHERE a=? AND b=?` — 用 a,b
- `WHERE a=? AND c=?` — 只用 a，c 在 Server 层过滤（或 ICP 下推）
- `WHERE b=? AND c=?` — 通常全扫；8.0 在某些条件下会 **skip scan**

**联合索引设计两条原则**：
1. 把**经常作为等值条件**的列放最左
2. 把**区分度高**的列放靠前（但不要让区分度低的列「卡」住后面）

### 3.4 覆盖索引

如果 SELECT 列表只引用索引里的列，就不需要回表。explain Extra 出现 `Using index`。代价：索引变胖、写入慢。详见 Scenario 03。

### 3.5 索引下推（ICP）

5.6+ 默认开。把**索引中包含的列**的 WHERE 条件下推到引擎层做过滤，少回表多少次取决于过滤性。详见 Scenario 04。

### 3.6 Multi-Range Read（MRR）

二级索引范围扫返回的主键是按二级索引顺序的，回表会变成随机 IO。MRR 把主键先排序再批量回表，把随机变顺序。默认 `mrr_cost_based=on`，优化器只在估算划算时启用。

### 3.7 索引为什么会失效

- **隐式类型转换**：`WHERE varchar_col = 100` → 列被 CONVERT，索引无用（Scenario 05）
- **对列做函数 / 表达式**：`WHERE DATE(t)='2026-01-01'` —— 5.7 失效，8.0 可用「函数索引」补救
- **前导通配**：`LIKE '%abc'` 不能走 B+ 树，因为不知道从哪一页开始
- **OR 跨列**：除非每列都有索引，否则常常退化为全扫（可改 UNION ALL）
- **数据量太小** / **预估代价不划算**：优化器选择全扫，看 `optimizer_trace` 里的 `cost_for_plan`
```

- [ ] **Step 2: Verify**

```bash
grep -c '^### 3\.[1-7]' /Users/buoy/Development/gitrepo/interview/mysql-handson/03-indexing/README.md
```

Expected: `7`

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/README.md
git commit -m "mysql-handson(03-indexing): backfill principles (3.1-3.7) with scenario refs"
```

---

### Task 27: Backfill 03-indexing README sections 4-5 (日常应用 + 调优实战)

**Files:**
- Modify: `interview/mysql-handson/03-indexing/README.md`

- [ ] **Step 1: Replace sections 4 and 5**

Replace existing `## 4. 日常开发应用` and `## 5. 调优实战` blocks with:

```markdown
## 4. 日常开发应用

**建表时**
- 主键用自增 BIGINT（不要选 UUID 当主键 —— 随机插入导致页分裂频繁。详见 Scenario 01 的「为什么主键有序很重要」备注）
- 二级索引宁少勿多：每个二级索引在写入时都要维护，且占空间
- 联合索引顺序按 §3.3 两条原则定

**写 SQL 时**
- 写完每条非纯主键查询，本能反应是 `EXPLAIN` 一下（`make explain SQL="..."` 一键）
- 等值条件 + 比较条件混用时，**等值列优先**放索引前列
- WHERE 里不要对索引列做函数 / 类型转换（参考 §3.7）
- LIMIT 深翻页（`LIMIT 100000, 20`）改成 **延迟关联**：先在覆盖索引上拿到主键再回表
- 不要在 ORM 上盲信 — Hibernate / GORM / Sequelize 生成的 SQL 经常多 SELECT 字段、缺索引提示。打开 query log（`make general-log-on`）抓一次实际跑的 SQL 比对

## 5. 调优实战

**Case A：「这条 SQL 上线后慢了，看不出原因」**

1. `make slow` tail 慢查日志，找到 SQL
2. `make explain SQL="..."` 看 type / key / rows / Extra
3. 看到 `type=ALL` 或 `Using filesort` / `Using temporary` —— 99% 是索引缺失或没走
4. 如果走了索引但 rows 远大于实际返回行数 → 走了「不对的」索引；用 `force index` 试更优的
5. 都没问题但还是慢 → 看 `make innodb-status` 是否在等锁

**Case B：「联合索引有 5 列，新来的同事看不懂顺序怎么定」**

1. 列出所有用到这个索引的查询（grep 代码 + general log）
2. 每条查询写出 WHERE 列 + 是 = 还是 范围
3. 按「等值优先 + 高区分度优先 + 高频优先」三轴排序
4. 索引列超过 4-5 列就要警惕：可能是查询本身该拆，不是索引该长

**Case C：「explain 看起来 OK，但生产某次跑了 30s」**

→ 多半是数据分布偏斜（city='Taipei' 占 80% 数据时，优化器估算「这条 WHERE 能减 5%」就走错了）。用 `optimizer_trace` 找成本估算，必要时跑 `ANALYZE TABLE` 更新统计或用 hint 强制。
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/README.md
git commit -m "mysql-handson(03-indexing): backfill section 4 (daily dev) + section 5 (tuning cases)"
```

---

### Task 28: Backfill 03-indexing README sections 6-7 (面试 + 一句话总结)

**Files:**
- Modify: `interview/mysql-handson/03-indexing/README.md`

- [ ] **Step 1: Replace sections 6 and 7**

```markdown
## 6. 面试高频考点

### 必考对比

| 维度 | 聚簇索引 | 二级索引 |
|---|---|---|
| 叶子节点存什么 | 整行数据 | 索引列值 + 主键值 |
| 一张表能有几个 | 1 | 多个 |
| 主键变更代价 | 高（数据物理重排） | 中（只动二级索引） |
| 是否需要回表 | 不需要 | SELECT 列超出索引列时需要 |

### "为什么选 B+ 树" — 三句话答法

1. 树高决定 IO 次数。一页 16KB、扇出 1000+，3 层 B+ 树能装千万级，对应 3 次磁盘 IO。
2. 叶子节点有序双向链表，**范围查询和排序都不用回到根**。
3. 内部节点只存键不存数据，比 B 树扇出更大，进一步压低树高。

### "RR 隔离级别 + 联合索引能不能避免幻读" 类陷阱题
→ 见 06-locking 章和 05-mvcc-and-transaction 章。

### 易错点

- **索引选择性 ≠ 索引区分度高就一定好**：还要看是否覆盖热点查询
- **`type=index` 不是 `type=index range`**：前者是「扫描整个索引」，依然慢，只比 `ALL` 略好
- **explain 的 rows 是估算**：不准也很正常，优化器是基于统计的，必要时 `ANALYZE TABLE`

## 7. 一句话总结

InnoDB 的索引是「按主键聚簇 + 多个二级索引指向主键」的 B+ 树。建表先想清楚主键，联合索引按「等值列 → 范围列、高区分度优先」排，写完 SQL 先 explain。看到 `Using filesort` / `Using temporary` / `type=ALL` 三件套要警觉；看到 `Using index` 是覆盖索引在起作用。详见 Scenarios 01-05。
```

- [ ] **Step 2: Verify all 7 sections still present and complete (no remaining "> 写完...补" placeholders)**

```bash
grep -n '写完.*补\|TBD\|待补\|TODO' /Users/buoy/Development/gitrepo/interview/mysql-handson/03-indexing/README.md
```

Expected: no matches.

- [ ] **Step 3: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/03-indexing/README.md
git commit -m "mysql-handson(03-indexing): backfill section 6 (interview) + 7 (one-liner summary)"
```

---

### Task 29: Interview card — q-why-bplus-tree

**Files:**
- Create: `interview/mysql-handson/99-interview-cards/q-why-bplus-tree.md`

- [ ] **Step 1: Write card**

```markdown
# 为什么 MySQL/InnoDB 用 B+ 树做索引？

## 一句话回答

为了**最小化磁盘 IO 次数**：B+ 树扇出大（一页 16KB 能放 1000+ 个键），三层就能装千万级数据，对应 3 次 IO；叶子节点有序链表让范围查询和排序无需回到根。

## 三层论证

1. **树高决定 IO 次数**。10^7 行：二叉树 23 层（23 次 IO），B 树 ≈ 4 层，B+ 树 3 层。
2. **B+ 树 vs B 树**：B+ 树内部节点只存键不存数据，扇出更大；叶子有序双向链表，范围扫描沿链表走，不用回到上层。
3. **B+ 树 vs Hash**：Hash 不支持范围和排序，且哈希冲突让最坏情况退化。

## 证据链接

- 三层 B+ 树容量实测：[Scenario 01](../03-indexing/scenarios/01-bplus-tree-three-layers.md)
- 覆盖索引省回表的代价对比：[Scenario 03](../03-indexing/scenarios/03-covering-index-saves-roundtrip.md)
- 章节原理：[03-indexing §3.1](../03-indexing/README.md)

## 易追问的延伸

- **Q: 那为什么主键不要用 UUID？** → UUID 无序，每次插入导致页分裂频繁；自增 BIGINT 顺序写入，页紧凑。
- **Q: 为什么页大小是 16KB？** → 平衡：太小→树变高；太大→单次 IO 慢。16KB 是磁盘 IO 的甜点。
- **Q: 8.0 移除了 Query Cache，那 InnoDB 还有什么缓存？** → Buffer Pool（热页）、Change Buffer（非唯一二级索引的写延迟应用）、Adaptive Hash Index（热点 B+ 树路径变成 hash）。
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/99-interview-cards/q-why-bplus-tree.md
git commit -m "mysql-handson(99-cards): add q-why-bplus-tree linked to scenarios 01,03"
```

---

### Task 30: Interview card — q-when-does-index-fail

**Files:**
- Create: `interview/mysql-handson/99-interview-cards/q-when-does-index-fail.md`

- [ ] **Step 1: Write card**

```markdown
# 索引什么时候会失效？

## 一句话回答

**核心规则**：当 WHERE 条件让索引列发生**变换**（类型转换、函数调用、表达式运算）或破坏**索引顺序**（前导通配 `LIKE '%x'`、最左前缀缺失、OR 跨非索引列）时，索引失效。

## 6 种典型场景

| 场景 | 例子 | 失效原因 |
|---|---|---|
| 隐式类型转换 | `WHERE varchar_col = 100` | MySQL 把列做 CAST，索引列被包装 → Scenario 05 |
| 函数 / 表达式 | `WHERE DATE(t)='2026-01-01'` | 5.7 失效；8.0 可建函数索引补救 |
| 前导通配 | `LIKE '%abc'` | B+ 树无法定位起始页 |
| 最左前缀缺失 | 索引 `(a,b,c)`，`WHERE b=?` | 索引按 a 排序，跳 a 就找不到入口（8.0 有 skip scan 例外） → Scenario 02 |
| OR 跨列 | `WHERE a=? OR x=?`（x 无索引） | 整体退化为全扫；改 UNION ALL |
| 优化器估算不划算 | 小表 / 选择性低 | type=ALL；用 optimizer_trace 看 cost → Scenario 04 末段 |

## 排查 SOP

1. `EXPLAIN` 看 type 和 key
2. type 是 ALL/index？key 是 NULL？→ 索引没走
3. 看 WHERE 是否中招上表 6 种
4. 看 Extra 是否 `Using filesort` / `Using temporary`（不一定是索引问题，但常伴随）
5. `optimizer_trace` 看是不是优化器主动放弃了索引

## 证据链接

- 联合索引最左前缀实测：[Scenario 02](../03-indexing/scenarios/02-leftmost-prefix-violation.md)
- ICP 开关对比（间接影响索引使用率）：[Scenario 04](../03-indexing/scenarios/04-icp-on-off-comparison.md)
- 隐式类型转换实测：[Scenario 05](../03-indexing/scenarios/05-implicit-type-conversion-kills-index.md)
- 章节原理：[03-indexing §3.7](../03-indexing/README.md)

## 易追问的延伸

- **Q: 8.0 的 skip scan 是什么？** → 联合索引 `(a,b)` 上的 `WHERE b=?` 在某些条件下，优化器会枚举 a 的不同值分别扫，比全扫快但比直接走索引慢。看 explain Extra 里的 `Using index for skip scan`。
- **Q: 怎么强制走 / 不走索引？** → `FORCE INDEX(idx)` / `IGNORE INDEX(idx)`；8.0 推荐用 optimizer hint `/*+ INDEX(tbl idx) */`。
- **Q: ANALYZE TABLE 多久跑一次？** → 数据量稳定时不用主动跑，大变化（批量导入 / 删除）后必须跑，让优化器拿到最新统计。
```

- [ ] **Step 2: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add mysql-handson/99-interview-cards/q-when-does-index-fail.md
git commit -m "mysql-handson(99-cards): add q-when-does-index-fail linked to scenarios 02,04,05"
```

---

## Done criteria for this plan

- [ ] `make up` brings up lab, `make mysql` works
- [ ] `make up-replica && make replica-setup` shows `Replica_(IO|SQL)_Running: Yes` and `Seconds_Behind_Source: 0`
- [ ] `make chaos-replica-lag MS=500` measurably bumps `Seconds_Behind_Source`, `make chaos-restore` brings it back to 0
- [ ] `make up-obs` makes Grafana reachable at `http://localhost:3000`
- [ ] `03-indexing/README.md` has all 7 sections, no placeholder text matching `TODO|待补|写完.*补`
- [ ] All 5 scenarios in `03-indexing/scenarios/` exist; each has been committed at least twice (prediction commit + observation commit) — verifiable via `git log --oneline mysql-handson/03-indexing/scenarios/`
- [ ] 2 interview cards exist in `99-interview-cards/`, each linking back to at least one scenario

When all of the above are checked, write a new plan for the next chapter (suggested: `04-execution-and-explain` since the user is already deep in explain by then, or `02-innodb-storage` for the natural bottom-up flow).
