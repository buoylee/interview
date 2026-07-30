# MySQL InnoDB Cluster 高可用学习专题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套可重复部署、可注入故障、可用业务证据验证的 MySQL 8.4 InnoDB Cluster 学习专题，使学习者能独立完成选型、部署、切换、恢复与 RPO／RTO 证明。

**Architecture:** 现有 MySQL 8.0.36 Primary／Replica Lab 保持不动；新建独立 `mysql-ha` Compose project，运行 3 个 Single-Primary InnoDB Cluster 成员、2 个 MySQL Router、2 个持续写入 worker、故障控制脚本及证据 verifier。理论、产品机制、生产 Runbook 与 8 个核心 Scenario 分档；完整 Cluster outage 作为 Runbook 支援演练，不扩成额外的核心 Scenario。所有可用性结论都回到客户端 ledger、Cluster 状态和成员最终数据三类证据。

**Tech Stack:** MySQL Server／Shell／Router 8.4.10、Docker Compose、Oracle Linux 9 tooling image、Python 3.12.13、MySQL Connector/Python 9.7.0、JavaScript AdminAPI、Bash、`unittest`、Markdown。

**Spec:** `docs/superpowers/specs/2026-07-22-mysql-innodb-cluster-ha-learning-design.md`

## Global Constraints

- 主线固定为 3 个 MySQL 8.4 LTS 成员、Single-Primary、MySQL Shell／AdminAPI 和 2 个 MySQL Router；不实现 multi-primary、自动读写分离、ClusterSet、Kubernetes Operator 或 PXC。
- 固定镜像 `mysql:8.4.10`、`container-registry.oracle.com/mysql/community-router:8.4.10`、`python:3.12.13-slim-bookworm`，固定 `mysql-connector-python==9.7.0`；MySQL Shell 8.4.10 由官方 MySQL Yum repository 安装进独立 tooling image。版本变化必须单独评审。
- `mysql:8.4.10` 与 Python image 同时提供 `linux/amd64`、`linux/arm64`；官方 Router 8.4.10 image 只有 `linux/amd64`，因此 Router 与 MySQL Shell tooling service 明确使用 `platform: linux/amd64`。Apple Silicon 上的 Router／Shell 时序包含模拟开销，只能证明行为，不能当作生产性能值。
- 固定 `innodb_flush_log_at_trx_commit=1`、`sync_binlog=1`、GTID、ROW binlog、`BEFORE_ON_PRIMARY_FAILOVER`、`OFFLINE_MODE`、`autoRejoinTries=3`、`super_read_only=ON` 启动保护。
- Lab 为缩短可重复故障测试，固定 `expelTimeout=5` 与 `group_replication_unreachable_majority_timeout=5`；教程必须把它们标为 Lab-only，不得直接作为生产推荐值。
- Compose project 名称固定为 `mysql-ha`，容器、网络和 volumes 不得复用或修改现有 `mysql-handson/00-lab/docker-compose.yml` 的资源。
- DB 服务只命名 `db1`／`db2`／`db3`，角色由 Cluster 动态决定；禁止把容器名写成固定 Primary／Secondary。
- 两个 workload worker 分别固定连接 Router A／B 的 `6446` 读写端口，共享 evidence 目录但各写一个 JSONL ledger，避免并发写同一文件。
- 只有显式 `connection.commit()` 返回成功才记为 `SUCCESS`；SQL 尚未发送前失败记为 `FAILURE`；SQL 已发送或 commit 响应没有确定结果时记为 `UNKNOWN`，不得自动重放未知请求。
- `request_id` 是业务幂等键并受唯一约束；所有 `SUCCESS` 必须存在、同一键只能有一条业务记录、所有 `UNKNOWN` 必须可查明。
- 所有 Scenario 必须从干净状态独立运行，保存原始证据到被 Git 忽略的 `mysql-handson/00-lab/ha/evidence/`，正文只写已实测的关键片段。
- 完整 Cluster 恢复必须先执行 `dba.rebootClusterFromCompleteOutage(..., {dryRun:true})`；正常流程禁止 `force:true`。
- 本地 Compose 只证明软件行为，不宣称复现主机、交换机、磁盘控制器、文件系统或可用区故障。
- 教材正文沿用仓库现有简体中文风格，保留 MySQL API、变量、状态与命令的原始英文拼写。
- 当前主工作树已有无关修改；执行计划时先使用 `superpowers:using-git-worktrees` 建立隔离 worktree，任何 commit 只暂存本任务列出的文件。

## File Map

| 路径 | 单一责任 |
|---|---|
| `mysql-handson/00-lab/ha/compose.yml` | 声明独立 DB、Router、worker、verifier、tools 与 recovery 服务 |
| `mysql-handson/00-lab/ha/config/common.cnf` | 固定所有成员共有的 GTID、binlog 与 durability 基线 |
| `mysql-handson/00-lab/ha/tools/Dockerfile` | 从官方 Yum repository 安装独立的 MySQL Shell／client 8.4.10，不假设 Server image 含 `mysqlsh` |
| `mysql-handson/00-lab/ha/bootstrap/*.js` | AdminAPI 建群、状态、切主、rejoin 与完整 outage reboot |
| `mysql-handson/00-lab/ha/init/01-orders.sql` | 创建最小业务表、唯一幂等键与 Lab 账号 |
| `mysql-handson/00-lab/ha/workload/` | 发送 `create_order`、严格分类三态结果、写 JSONL ledger |
| `mysql-handson/00-lab/ha/verifier/` | 对账 ledger、拓扑、fencing、成员数据与 Scenario 时间窗 |
| `mysql-handson/00-lab/ha/faults/` | 只在 `mysql-ha` project 内注入、记录并恢复故障 |
| `mysql-handson/00-lab/ha/scenarios/run.sh` | 为每个 Scenario 编排 reset、预热、故障、恢复与验证 |
| `mysql-handson/09-replication-and-ha/ha-foundations.md` | 产品无关的 HA 理论与判断框架 |
| `mysql-handson/09-replication-and-ha/innodb-cluster/README.md` | MySQL 8.4 组件、提交、failover、配置和实验导航 |
| `mysql-handson/09-replication-and-ha/innodb-cluster/production-runbook.md` | 生产部署检查、观测、维护与故障处置 |
| `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/*.md` | 8 个核心实验的预期、实测证据与落差 |
| `mysql-handson/99-interview-cards/q-*.md` | 只压缩答案并链回理论和实验证据 |

---

### Task 1: 建立隔离的三成员 Compose 基线

**Files:**
- Create: `mysql-handson/00-lab/ha/.env.example`
- Create: `mysql-handson/00-lab/ha/compose.yml`
- Create: `mysql-handson/00-lab/ha/config/common.cnf`
- Create: `mysql-handson/00-lab/ha/Makefile`
- Create: `mysql-handson/00-lab/ha/tests/test_layout.py`
- Modify: `.gitignore:35-42`

**Interfaces:**
- Consumes: Docker Compose v2 and unused host ports `13306`／`13307`／`13308`.
- Produces: `db1`／`db2`／`db3` standalone instances on network `mysql-ha-net`; Task 2 will configure them into one Cluster.

- [ ] **Step 1: Write the failing layout test**

```python
# mysql-handson/00-lab/ha/tests/test_layout.py
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LayoutTest(unittest.TestCase):
    def test_compose_pins_three_dynamic_role_members(self):
        text = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("name: mysql-ha", text)
        self.assertGreaterEqual(text.count("image: mysql:8.4.10"), 1)
        for member in ("db1", "db2", "db3"):
            self.assertIn(f"  {member}:\n", text)
            self.assertNotIn(f"mysql-ha-primary-{member}", text)

    def test_common_config_pins_durability(self):
        text = (ROOT / "config/common.cnf").read_text(encoding="utf-8")
        for setting in (
            "gtid_mode=ON",
            "enforce_gtid_consistency=ON",
            "binlog_format=ROW",
            "plugin_load_add=group_replication.so",
            "innodb_flush_log_at_trx_commit=1",
            "sync_binlog=1",
            "super_read_only=ON",
            "group_replication_unreachable_majority_timeout=5",
        ):
            self.assertIn(setting, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the baseline is absent**

Run:

```bash
python3 -m unittest mysql-handson/00-lab/ha/tests/test_layout.py -v
```

Expected: FAIL with `FileNotFoundError` for `compose.yml`.

- [ ] **Step 3: Add the shared MySQL configuration**

```ini
# mysql-handson/00-lab/ha/config/common.cnf
[mysqld]
bind_address=0.0.0.0
report_port=3306
default_storage_engine=InnoDB
gtid_mode=ON
enforce_gtid_consistency=ON
log_bin=binlog
binlog_format=ROW
binlog_row_image=FULL
skip_replica_start=ON
plugin_load_add=group_replication.so
innodb_flush_log_at_trx_commit=1
sync_binlog=1
group_replication_consistency=BEFORE_ON_PRIMARY_FAILOVER
super_read_only=ON
group_replication_unreachable_majority_timeout=5
binlog_expire_logs_seconds=604800
```

- [ ] **Step 4: Add explicit local credentials and the three-member Compose file**

```dotenv
# mysql-handson/00-lab/ha/.env.example
MYSQL_ROOT_PASSWORD=ha-root
MYSQL_CLUSTER_ADMIN=icadmin
MYSQL_CLUSTER_ADMIN_PASSWORD=ha-cluster
MYSQL_APP_USER=ha_app
MYSQL_APP_PASSWORD=ha-app
```

```yaml
# mysql-handson/00-lab/ha/compose.yml
name: mysql-ha

x-db-common: &db-common
  image: mysql:8.4.10
  restart: on-failure
  environment:
    MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-ha-root}
    MYSQL_ROOT_HOST: "%"
  volumes:
    - ./config/common.cnf:/etc/mysql/conf.d/ha-common.cnf:ro
  healthcheck:
    test: ["CMD-SHELL", "mysqladmin ping -h127.0.0.1 -uroot -p$$MYSQL_ROOT_PASSWORD --silent"]
    interval: 3s
    timeout: 2s
    retries: 40
    start_period: 20s
  networks: [ha-net]

services:
  db1:
    <<: *db-common
    hostname: db1
    container_name: mysql-ha-db1
    command: ["--server-id=1", "--report-host=db1"]
    ports: ["13306:3306"]
    volumes:
      - ./config/common.cnf:/etc/mysql/conf.d/ha-common.cnf:ro
      - db1-data:/var/lib/mysql

  db2:
    <<: *db-common
    hostname: db2
    container_name: mysql-ha-db2
    command: ["--server-id=2", "--report-host=db2"]
    ports: ["13307:3306"]
    volumes:
      - ./config/common.cnf:/etc/mysql/conf.d/ha-common.cnf:ro
      - db2-data:/var/lib/mysql

  db3:
    <<: *db-common
    hostname: db3
    container_name: mysql-ha-db3
    command: ["--server-id=3", "--report-host=db3"]
    ports: ["13308:3306"]
    volumes:
      - ./config/common.cnf:/etc/mysql/conf.d/ha-common.cnf:ro
      - db3-data:/var/lib/mysql

networks:
  ha-net:
    name: mysql-ha-net

volumes:
  db1-data:
  db2-data:
  db3-data:
```

- [ ] **Step 5: Add safe lifecycle targets and ignore generated evidence**

```makefile
# mysql-handson/00-lab/ha/Makefile
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
```

Append to `.gitignore`:

```gitignore

# MySQL HA lab runtime evidence
mysql-handson/00-lab/ha/evidence/
```

- [ ] **Step 6: Run static and live baseline verification**

Run:

```bash
python3 -m unittest mysql-handson/00-lab/ha/tests/test_layout.py -v
make -C mysql-handson/00-lab/ha config
make -C mysql-handson/00-lab/ha reset
make -C mysql-handson/00-lab/ha up-db
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml exec -T db1 mysql -uroot -pha-root -Nse "SELECT @@server_id, @@report_host, @@gtid_mode, @@innodb_flush_log_at_trx_commit, @@sync_binlog"
```

Expected: 2 tests PASS; Compose config exits `0`; all three DB containers are healthy; SQL prints `1`, `db1`, `ON`, `1`, `1`.

- [ ] **Step 7: Commit**

```bash
git add .gitignore mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): add isolated three-member lab"
```

---

### Task 2: 用 AdminAPI 建群并接入双 Router

**Files:**
- Create: `mysql-handson/00-lab/ha/tools/Dockerfile`
- Create: `mysql-handson/00-lab/ha/bootstrap/cluster.js`
- Create: `mysql-handson/00-lab/ha/bootstrap/status.js`
- Create: `mysql-handson/00-lab/ha/bootstrap/set-primary.js`
- Create: `mysql-handson/00-lab/ha/init/01-orders.sql`
- Modify: `mysql-handson/00-lab/ha/compose.yml`
- Modify: `mysql-handson/00-lab/ha/Makefile`
- Modify: `mysql-handson/00-lab/ha/tests/test_layout.py`

**Interfaces:**
- Consumes: healthy `db1`／`db2`／`db3` and credentials from `.env`.
- Produces: MySQL Shell／client 8.4.10 tooling image, Cluster `haLabCluster`, deterministic election weights `100/80/60`, Router A at host port `16446`, Router B at `17446`, and table `ha_lab.orders(request_id)`.

- [ ] **Step 1: Extend the failing layout test for Cluster and Router invariants**

Add:

```python
    def test_cluster_script_pins_failover_safety(self):
        text = (ROOT / "bootstrap/cluster.js").read_text(encoding="utf-8")
        for setting in (
            "BEFORE_ON_PRIMARY_FAILOVER",
            "OFFLINE_MODE",
            "autoRejoinTries: 3",
            "expelTimeout: 5",
            "communicationStack: 'MYSQL'",
        ):
            self.assertIn(setting, text)

    def test_two_routers_only_expose_read_write_path(self):
        text = (ROOT / "compose.yml").read_text(encoding="utf-8")
        self.assertIn("16446:6446", text)
        self.assertIn("17446:6446", text)
        self.assertEqual(text.count("community-router:8.4.10"), 2)
        self.assertGreaterEqual(text.count("platform: linux/amd64"), 4)

    def test_mysql_shell_uses_a_separate_official_package_image(self):
        text = (ROOT / "tools/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM --platform=linux/amd64 oraclelinux:9-slim", text)
        self.assertIn("mysql84-community-release-el9-4.noarch.rpm", text)
        self.assertIn("mysql-shell-8.4.10", text)
```

Run:

```bash
python3 -m unittest mysql-handson/00-lab/ha/tests/test_layout.py -v
```

Expected: the original 2 tests PASS; the new 3 tests FAIL because tooling, bootstrap and Router definitions do not exist.

- [ ] **Step 2: Add an idempotent AdminAPI bootstrap script**

```javascript
// mysql-handson/00-lab/ha/bootstrap/cluster.js
shell.options.useWizards = false;

const rootPassword = os.getenv('MYSQL_ROOT_PASSWORD') || 'ha-root';
const adminUser = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const adminPassword = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const clusterName = 'haLabCluster';
const members = [
  {host: 'db1', weight: 100},
  {host: 'db2', weight: 80},
  {host: 'db3', weight: 60},
];

function connection(user, password, host) {
  return {scheme: 'mysql', user, password, host, port: 3306};
}

for (const member of members) {
  dba.configureInstance(connection('root', rootPassword, member.host), {
    clusterAdmin: adminUser,
    clusterAdminPassword: adminPassword,
  });
}

shell.connect(connection(adminUser, adminPassword, 'db1'));
let cluster;
try {
  cluster = dba.getCluster(clusterName);
} catch (error) {
  cluster = dba.createCluster(clusterName, {
    communicationStack: 'MYSQL',
    consistency: 'BEFORE_ON_PRIMARY_FAILOVER',
    exitStateAction: 'OFFLINE_MODE',
    autoRejoinTries: 3,
    expelTimeout: 5,
    memberWeight: 100,
  });
}

for (const member of members.slice(1)) {
  const address = `${member.host}:3306`;
  const topology = cluster.status().defaultReplicaSet.topology;
  if (!Object.prototype.hasOwnProperty.call(topology, address)) {
    cluster.addInstance(connection(adminUser, adminPassword, member.host), {
      recoveryMethod: 'clone',
      memberWeight: member.weight,
    });
  }
}

print(JSON.stringify(cluster.status({extended: 1}), null, 2));
```

- [ ] **Step 3: Add status and controlled-switchover scripts**

```javascript
// mysql-handson/00-lab/ha/bootstrap/status.js
shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
shell.connect({scheme: 'mysql', user, password, host: os.getenv('MYSQL_SEED') || 'db1', port: 3306});
print(JSON.stringify(dba.getCluster('haLabCluster').status({extended: 2}), null, 2));
```

```javascript
// mysql-handson/00-lab/ha/bootstrap/set-primary.js
shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const target = os.getenv('MYSQL_TARGET_MEMBER') || 'db2';
shell.connect({scheme: 'mysql', user, password, host: os.getenv('MYSQL_SEED') || 'db1', port: 3306});
const cluster = dba.getCluster('haLabCluster');
cluster.setPrimaryInstance(`${user}@${target}:3306`);
print(JSON.stringify(cluster.status({extended: 1}), null, 2));
```

- [ ] **Step 4: Add the replicated business schema and least-privilege app account**

```sql
-- mysql-handson/00-lab/ha/init/01-orders.sql
CREATE DATABASE IF NOT EXISTS ha_lab;

CREATE TABLE IF NOT EXISTS ha_lab.orders (
  request_id VARCHAR(96) NOT NULL,
  payload JSON NOT NULL,
  via_router VARCHAR(32) NOT NULL,
  written_by VARCHAR(64) NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (request_id)
) ENGINE=InnoDB;

CREATE USER IF NOT EXISTS 'ha_app'@'%' IDENTIFIED BY 'ha-app';
GRANT SELECT, INSERT, UPDATE ON ha_lab.* TO 'ha_app'@'%';
```

- [ ] **Step 5: Add a pinned MySQL Shell tooling image**

The Server image is not used as a Shell image. Build a separate `linux/amd64` tooling image from Oracle Linux and the official MySQL 8.4 Yum repositories:

```dockerfile
# mysql-handson/00-lab/ha/tools/Dockerfile
FROM --platform=linux/amd64 oraclelinux:9-slim

RUN microdnf install -y \
      https://repo.mysql.com/mysql84-community-release-el9-4.noarch.rpm \
 && microdnf install -y \
      mysql-shell-8.4.10 \
      mysql-community-client-8.4.10 \
 && microdnf clean all

ENTRYPOINT []
CMD ["mysqlsh"]
```

The implementation must fail at image build time if those exact packages are unavailable; it must not silently install MySQL Shell 9.x or an unpinned client.

- [ ] **Step 6: Add tools, bootstrap and two official Router services**

Insert under `services:` in `compose.yml`:

```yaml
  shell:
    platform: linux/amd64
    build:
      context: .
      dockerfile: tools/Dockerfile
    command: ["sleep", "infinity"]
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-ha-root}
      MYSQL_CLUSTER_ADMIN: ${MYSQL_CLUSTER_ADMIN:-icadmin}
      MYSQL_CLUSTER_ADMIN_PASSWORD: ${MYSQL_CLUSTER_ADMIN_PASSWORD:-ha-cluster}
      MYSQL_APP_USER: ${MYSQL_APP_USER:-ha_app}
      MYSQL_APP_PASSWORD: ${MYSQL_APP_PASSWORD:-ha-app}
    volumes:
      - ./bootstrap:/bootstrap:ro
      - ./init:/init:ro
      - ./evidence:/evidence
    networks: [ha-net]

  cluster-bootstrap:
    platform: linux/amd64
    build:
      context: .
      dockerfile: tools/Dockerfile
    entrypoint: ["mysqlsh", "--js", "--file=/bootstrap/cluster.js"]
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-ha-root}
      MYSQL_CLUSTER_ADMIN: ${MYSQL_CLUSTER_ADMIN:-icadmin}
      MYSQL_CLUSTER_ADMIN_PASSWORD: ${MYSQL_CLUSTER_ADMIN_PASSWORD:-ha-cluster}
    volumes:
      - ./bootstrap:/bootstrap:ro
    depends_on:
      db1: {condition: service_healthy}
      db2: {condition: service_healthy}
      db3: {condition: service_healthy}
    networks: [ha-net]

  router-a:
    platform: linux/amd64
    image: container-registry.oracle.com/mysql/community-router:8.4.10
    container_name: mysql-ha-router-a
    environment:
      MYSQL_HOST: db1
      MYSQL_PORT: 3306
      MYSQL_USER: ${MYSQL_CLUSTER_ADMIN:-icadmin}
      MYSQL_PASSWORD: ${MYSQL_CLUSTER_ADMIN_PASSWORD:-ha-cluster}
      MYSQL_INNODB_CLUSTER_MEMBERS: 3
      MYSQL_CREATE_ROUTER_USER: 1
      MYSQL_ROUTER_BOOTSTRAP_EXTRA_OPTIONS: --conf-use-gr-notifications
    ports: ["16446:6446"]
    networks: [ha-net]

  router-b:
    platform: linux/amd64
    image: container-registry.oracle.com/mysql/community-router:8.4.10
    container_name: mysql-ha-router-b
    environment:
      MYSQL_HOST: db2
      MYSQL_PORT: 3306
      MYSQL_USER: ${MYSQL_CLUSTER_ADMIN:-icadmin}
      MYSQL_PASSWORD: ${MYSQL_CLUSTER_ADMIN_PASSWORD:-ha-cluster}
      MYSQL_INNODB_CLUSTER_MEMBERS: 3
      MYSQL_CREATE_ROUTER_USER: 1
      MYSQL_ROUTER_BOOTSTRAP_EXTRA_OPTIONS: --conf-use-gr-notifications
    ports: ["17446:6446"]
    networks: [ha-net]
```

- [ ] **Step 7: Add Cluster lifecycle targets**

Append to the HA `Makefile`:

```makefile
.PHONY: up bootstrap routers init status switchover mysql-a mysql-b

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
```

- [ ] **Step 8: Build from empty volumes and verify Router routing**

Run:

```bash
make -C mysql-handson/00-lab/ha reset
make -C mysql-handson/00-lab/ha up
python3 -m unittest mysql-handson/00-lab/ha/tests/test_layout.py -v
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml run --rm shell mysqlsh --version
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse "SELECT @@hostname, @@read_only, @@super_read_only"
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml run --rm shell mysql -hrouter-b -P6446 -uha_app -pha-app -Nse "SELECT @@hostname, @@read_only, @@super_read_only"
```

Expected: `mysqlsh --version` reports 8.4.10; Cluster status is `OK`, exactly 3 topology entries are `ONLINE`, exactly one member is `PRIMARY`／`R/W`, both Router queries return that same hostname with `0 0`, and all 5 layout tests PASS.

- [ ] **Step 9: Commit**

```bash
git add mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): bootstrap cluster and dual routers"
```

---

### Task 3: 以 TDD 实现请求三态与 ledger contract

**Files:**
- Create: `mysql-handson/00-lab/ha/workload/Dockerfile`
- Create: `mysql-handson/00-lab/ha/workload/requirements.txt`
- Create: `mysql-handson/00-lab/ha/workload/__init__.py`
- Create: `mysql-handson/00-lab/ha/workload/model.py`
- Create: `mysql-handson/00-lab/ha/workload/client.py`
- Create: `mysql-handson/00-lab/ha/tests/__init__.py`
- Create: `mysql-handson/00-lab/ha/tests/test_outcomes.py`

**Interfaces:**
- Consumes: a zero-argument `connect()` callable returning a Connector/Python connection.
- Produces: `Outcome`, `OrderRequest`, `LedgerRecord`, `JsonlLedger` and `execute_order(connect, request, max_connect_retries)`; Task 4 and Task 5 depend on these exact names.

- [ ] **Step 1: Write failing outcome tests**

Create an empty `mysql-handson/00-lab/ha/tests/__init__.py`, then add:

```python
# mysql-handson/00-lab/ha/tests/test_outcomes.py
from pathlib import Path
import tempfile
import unittest

from workload.client import execute_order
from workload.model import JsonlLedger, LedgerRecord, OrderRequest, Outcome


class FakeCursor:
    def __init__(self, execute_error=None):
        self.execute_error = execute_error
        self.calls = 0

    def execute(self, sql, params):
        self.calls += 1
        if self.execute_error:
            raise self.execute_error

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor, commit_error=None):
        self._cursor = cursor
        self.commit_error = commit_error
        self.commit_calls = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_calls += 1
        if self.commit_error:
            raise self.commit_error

    def close(self):
        pass


class ReadOnlyError(Exception):
    errno = 1290


class OutcomeTest(unittest.TestCase):
    def setUp(self):
        self.request = OrderRequest("req-1", '{"item":"book"}', "router-a")

    def test_success_requires_execute_and_commit_to_return(self):
        connection = FakeConnection(FakeCursor())
        record = execute_order(lambda: connection, self.request, 2)
        self.assertEqual(record.outcome, Outcome.SUCCESS)
        self.assertEqual(connection.commit_calls, 1)

    def test_pre_send_connection_failure_can_retry(self):
        attempts = 0

        def connect():
            nonlocal attempts
            attempts += 1
            raise ConnectionError("not connected")

        record = execute_order(connect, self.request, 2)
        self.assertEqual(record.outcome, Outcome.FAILURE)
        self.assertEqual(record.retries, 2)
        self.assertEqual(attempts, 3)

    def test_post_send_disconnect_is_unknown_and_never_replayed(self):
        cursor = FakeCursor(ConnectionResetError("response lost"))
        calls = 0

        def connect():
            nonlocal calls
            calls += 1
            return FakeConnection(cursor)

        record = execute_order(connect, self.request, 5)
        self.assertEqual(record.outcome, Outcome.UNKNOWN)
        self.assertEqual(calls, 1)
        self.assertEqual(cursor.calls, 1)

    def test_commit_disconnect_is_unknown_and_never_replayed(self):
        cursor = FakeCursor()
        connection = FakeConnection(cursor, ConnectionResetError("commit response lost"))
        calls = 0

        def connect():
            nonlocal calls
            calls += 1
            return connection

        record = execute_order(connect, self.request, 5)
        self.assertEqual(record.outcome, Outcome.UNKNOWN)
        self.assertEqual(calls, 1)
        self.assertEqual(cursor.calls, 1)
        self.assertEqual(connection.commit_calls, 1)

    def test_explicit_server_rejection_is_failure_and_never_replayed(self):
        cursor = FakeCursor(ReadOnlyError("server is read only"))
        record = execute_order(lambda: FakeConnection(cursor), self.request, 5)
        self.assertEqual(record.outcome, Outcome.FAILURE)
        self.assertEqual(cursor.calls, 1)

    def test_jsonl_round_trip_preserves_contract(self):
        record = execute_order(lambda: FakeConnection(FakeCursor()), self.request, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            JsonlLedger(path).append(record)
            self.assertEqual(JsonlLedger.load([path]), [record])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify imports fail**

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_outcomes.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'workload.client'`.

- [ ] **Step 3: Implement the immutable result model and JSONL ledger**

```python
# mysql-handson/00-lab/ha/workload/model.py
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Iterable


class Outcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OrderRequest:
    request_id: str
    payload: str
    router: str


@dataclass(frozen=True)
class LedgerRecord:
    request_id: str
    payload: str
    router: str
    started_at: str
    finished_at: str
    outcome: Outcome
    retries: int
    error_type: str | None

    def to_json(self) -> str:
        value = asdict(self)
        value["outcome"] = self.outcome.value
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "LedgerRecord":
        data = json.loads(value)
        data["outcome"] = Outcome(data["outcome"])
        return cls(**data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class JsonlLedger:
    def __init__(self, path: Path):
        self.path = path

    def append(self, record: LedgerRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.to_json() + "\n")
            handle.flush()

    @staticmethod
    def load(paths: Iterable[Path]) -> list[LedgerRecord]:
        records: list[LedgerRecord] = []
        for path in sorted(paths):
            if path.exists():
                records.extend(
                    LedgerRecord.from_json(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
        return records
```

Create an empty `workload/__init__.py`.

- [ ] **Step 4: Implement the no-blind-replay client boundary**

```python
# mysql-handson/00-lab/ha/workload/client.py
from collections.abc import Callable
import time
from typing import Protocol

from workload.model import LedgerRecord, OrderRequest, Outcome, utc_now


INSERT_ORDER = """
INSERT INTO ha_lab.orders(request_id, payload, via_router, written_by)
VALUES (%s, CAST(%s AS JSON), %s, @@hostname)
ON DUPLICATE KEY UPDATE request_id = VALUES(request_id)
"""

AMBIGUOUS_TRANSPORT_ERRNOS = {2006, 2013, 2055}


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[str, str, str]) -> None: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


def execute_order(
    connect: Callable[[], Connection],
    request: OrderRequest,
    max_connect_retries: int,
) -> LedgerRecord:
    started_at = utc_now()
    retries = 0
    connection: Connection | None = None
    cursor: Cursor | None = None

    while True:
        try:
            connection = connect()
            cursor = connection.cursor()
            break
        except Exception as error:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass
            if retries >= max_connect_retries:
                return LedgerRecord(
                    request.request_id, request.payload, request.router,
                    started_at, utc_now(), Outcome.FAILURE, retries,
                    type(error).__name__,
                )
            retries += 1
            time.sleep(min(0.1 * (2 ** retries), 1.0))

    try:
        cursor.execute(INSERT_ORDER, (request.request_id, request.payload, request.router))
        connection.commit()
        return LedgerRecord(
            request.request_id, request.payload, request.router,
            started_at, utc_now(), Outcome.SUCCESS, retries, None,
        )
    except Exception as error:
        errno = getattr(error, "errno", None)
        outcome = (
            Outcome.FAILURE
            if errno is not None and errno not in AMBIGUOUS_TRANSPORT_ERRNOS
            else Outcome.UNKNOWN
        )
        return LedgerRecord(
            request.request_id, request.payload, request.router,
            started_at, utc_now(), outcome, retries,
            type(error).__name__,
        )
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass
```

- [ ] **Step 5: Add the pinned workload image**

```text
# mysql-handson/00-lab/ha/workload/requirements.txt
mysql-connector-python==9.7.0
```

```dockerfile
# mysql-handson/00-lab/ha/workload/Dockerfile
FROM python:3.12.13-slim-bookworm

WORKDIR /app
COPY workload/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY workload /app/workload
COPY tests /app/tests
ENV PYTHONPATH=/app
```

- [ ] **Step 6: Run unit tests in host Python and the pinned image**

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_outcomes.py -v
docker build -f mysql-handson/00-lab/ha/workload/Dockerfile -t mysql-ha-workload:test mysql-handson/00-lab/ha
docker run --rm mysql-ha-workload:test python -m unittest tests.test_outcomes -v
```

Expected: all 6 tests PASS twice; execute／commit transport-loss tests prove only one SQL attempt occurs, while distinguishing an explicit server rejection from an ambiguous response loss.

- [ ] **Step 7: Commit**

```bash
git add mysql-handson/00-lab/ha/workload mysql-handson/00-lab/ha/tests/__init__.py mysql-handson/00-lab/ha/tests/test_outcomes.py
git commit -m "feat(mysql-ha): model client transaction outcomes"
```

---

### Task 4: 运行双 Router 持续写入并生成 ledger

**Files:**
- Create: `mysql-handson/00-lab/ha/workload/runner.py`
- Create: `mysql-handson/00-lab/ha/tests/test_runner.py`
- Modify: `mysql-handson/00-lab/ha/compose.yml`
- Modify: `mysql-handson/00-lab/ha/Makefile`
- Modify: `mysql-handson/00-lab/ha/workload/Dockerfile`

**Interfaces:**
- Consumes: Task 3 `execute_order()` and Router endpoints `router-a:6446`／`router-b:6446`.
- Produces: `/evidence/ledger-router-a.jsonl` and `/evidence/ledger-router-b.jsonl`; Task 5 verifier reads `ledger-*.jsonl`.

- [ ] **Step 1: Write a failing runner test**

```python
# mysql-handson/00-lab/ha/tests/test_runner.py
from pathlib import Path
import tempfile
import unittest

from workload.model import JsonlLedger, LedgerRecord, Outcome
from workload.runner import run_workload


class RunnerTest(unittest.TestCase):
    def test_bounded_runner_writes_one_record_per_request(self):
        def fake_execute(connect, request, retries):
            return LedgerRecord(
                request.request_id, request.payload, request.router,
                "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.001+00:00",
                Outcome.SUCCESS, 0, None,
            )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger-router-a.jsonl"
            run_workload("router-a", path, 3, 0, lambda: object(), fake_execute)
            records = JsonlLedger.load([path])
            self.assertEqual(len(records), 3)
            self.assertTrue(all(record.router == "router-a" for record in records))
            self.assertEqual(len({record.request_id for record in records}), 3)


if __name__ == "__main__":
    unittest.main()
```

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_runner.py -v
```

Expected: FAIL because `workload.runner` does not exist.

- [ ] **Step 2: Implement the bounded／continuous runner**

```python
# mysql-handson/00-lab/ha/workload/runner.py
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
import signal
import time
import uuid

from workload.client import execute_order
from workload.model import JsonlLedger, LedgerRecord, OrderRequest


Execute = Callable[[Callable[[], object], OrderRequest, int], LedgerRecord]
running = True


def stop(_signum, _frame) -> None:
    global running
    running = False


def run_workload(
    router_label: str,
    ledger_path: Path,
    max_requests: int,
    interval_ms: int,
    connect: Callable[[], object],
    execute: Execute = execute_order,
) -> None:
    ledger = JsonlLedger(ledger_path)
    sent = 0
    while running and (max_requests == 0 or sent < max_requests):
        request = OrderRequest(
            request_id=f"{router_label}-{uuid.uuid4()}",
            payload=json.dumps({"item": "book", "sequence": sent}),
            router=router_label,
        )
        ledger.append(execute(connect, request, 2))
        sent += 1
        time.sleep(interval_ms / 1000)


def main() -> None:
    import mysql.connector

    parser = argparse.ArgumentParser()
    parser.add_argument("--router-label", required=True)
    parser.add_argument("--router-host", required=True)
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--interval-ms", type=int, default=100)
    args = parser.parse_args()

    def connect():
        return mysql.connector.connect(
            host=args.router_host,
            port=6446,
            user=os.getenv("MYSQL_APP_USER", "ha_app"),
            password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
            database="ha_lab",
            autocommit=False,
            connection_timeout=2,
            read_timeout=3,
            write_timeout=3,
        )

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    run_workload(
        args.router_label,
        Path(f"/evidence/ledger-{args.router_label}.jsonl"),
        args.max_requests,
        args.interval_ms,
        connect,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Add both worker services**

Insert under `services:` in `compose.yml`:

```yaml
  workload-a:
    build:
      context: .
      dockerfile: workload/Dockerfile
    command: ["python", "-m", "workload.runner", "--router-label", "router-a", "--router-host", "router-a"]
    environment:
      MYSQL_APP_USER: ${MYSQL_APP_USER:-ha_app}
      MYSQL_APP_PASSWORD: ${MYSQL_APP_PASSWORD:-ha-app}
    volumes: ["./evidence:/evidence"]
    depends_on: [router-a]
    networks: [ha-net]

  workload-b:
    build:
      context: .
      dockerfile: workload/Dockerfile
    command: ["python", "-m", "workload.runner", "--router-label", "router-b", "--router-host", "router-b"]
    environment:
      MYSQL_APP_USER: ${MYSQL_APP_USER:-ha_app}
      MYSQL_APP_PASSWORD: ${MYSQL_APP_PASSWORD:-ha-app}
    volumes: ["./evidence:/evidence"]
    depends_on: [router-b]
    networks: [ha-net]
```

Update `workload/Dockerfile` to execute modules by default:

```dockerfile
CMD ["python", "-m", "workload.runner", "--help"]
```

- [ ] **Step 4: Add workload lifecycle targets**

Append to `Makefile`:

```makefile
.PHONY: workload-start workload-stop workload-once workload-burst

workload-start:
	@mkdir -p evidence
	$(DC) up -d --build workload-a workload-b

workload-stop:
	-$(DC) stop workload-a workload-b

workload-once:
	@mkdir -p evidence
	$(DC) run --rm workload-a python -m workload.runner --router-label router-a --router-host router-a --max-requests $${N:-10} --interval-ms 0
	$(DC) run --rm workload-b python -m workload.runner --router-label router-b --router-host router-b --max-requests $${N:-10} --interval-ms 0

workload-burst:
	@mkdir -p evidence
	$(DC) run --rm workload-a python -m workload.runner --router-label burst-a --router-host router-a --max-requests $${N:-1000} --interval-ms 0 & pid_a=$$!; \
	$(DC) run --rm workload-b python -m workload.runner --router-label burst-b --router-host router-b --max-requests $${N:-1000} --interval-ms 0 & pid_b=$$!; \
	wait $$pid_a; status_a=$$?; wait $$pid_b; status_b=$$?; \
	[ $$status_a -eq 0 ] && [ $$status_b -eq 0 ]
```

- [ ] **Step 5: Run unit and live dual-Router verification**

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_runner.py -v
make -C mysql-handson/00-lab/ha up
make -C mysql-handson/00-lab/ha workload-once N=5
wc -l mysql-handson/00-lab/ha/evidence/ledger-router-a.jsonl mysql-handson/00-lab/ha/evidence/ledger-router-b.jsonl
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse "SELECT via_router, written_by, COUNT(*) FROM ha_lab.orders GROUP BY via_router, written_by ORDER BY via_router, written_by"
```

Expected: runner unit test PASS; each ledger has 5 lines; SQL returns one row for each Router with count `5`, and both rows identify the same current Primary in `written_by`.

- [ ] **Step 6: Commit**

```bash
git add mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): add dual-router workload runner"
```

---
### Task 5: 自动核对客户端结果、拓扑与成员数据

**Files:**
- Create: `mysql-handson/00-lab/ha/verifier/__init__.py`
- Create: `mysql-handson/00-lab/ha/verifier/verify.py`
- Create: `mysql-handson/00-lab/ha/tests/test_verifier.py`
- Modify: `mysql-handson/00-lab/ha/workload/Dockerfile`
- Modify: `mysql-handson/00-lab/ha/compose.yml`
- Modify: `mysql-handson/00-lab/ha/Makefile`

**Interfaces:**
- Consumes: all `ledger-*.jsonl`, direct member endpoints `db1:3306`／`db2:3306`／`db3:3306`, and `replication_group_members`.
- Produces: `/evidence/verification.json` plus process exit `0` only when every ONLINE member has crossed the Primary GTID convergence barrier and acknowledged writes, Primary uniqueness and member data all satisfy assertions.

- [ ] **Step 1: Write failing pure verifier tests**

```python
# mysql-handson/00-lab/ha/tests/test_verifier.py
import unittest

from verifier.verify import evaluate
from workload.model import LedgerRecord, Outcome


def record(request_id: str, outcome: Outcome) -> LedgerRecord:
    return LedgerRecord(
        request_id, "{}", "router-a",
        "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00.001+00:00",
        outcome, 0, None,
    )


class VerifierTest(unittest.TestCase):
    def test_missing_acknowledged_write_fails(self):
        report = evaluate(
            [record("ack-1", Outcome.SUCCESS)],
            {"db1": [], "db2": [], "db3": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertIn("acknowledged request missing: ack-1", report["errors"])

    def test_unknown_is_reconciled_as_committed_or_absent(self):
        report = evaluate(
            [record("u1", Outcome.UNKNOWN), record("u2", Outcome.UNKNOWN)],
            {"db1": ["u1"]},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertEqual(report["unknown"], {"committed": ["u1"], "absent": ["u2"]})

    def test_divergent_online_members_fail(self):
        report = evaluate(
            [],
            {"db1": ["a"], "db2": ["a", "b"]},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "SECONDARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertIn("online member data diverged", report["errors"])

    def test_two_primaries_fail(self):
        report = evaluate(
            [],
            {"db1": [], "db2": []},
            [
                {"host": "db1", "role": "PRIMARY", "state": "ONLINE"},
                {"host": "db2", "role": "PRIMARY", "state": "ONLINE"},
            ],
            expected_online=2,
        )
        self.assertIn("expected exactly one ONLINE PRIMARY, got 2", report["errors"])

    def test_duplicate_business_result_fails(self):
        report = evaluate(
            [],
            {"db1": ["dup", "dup"]},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
        )
        self.assertIn("duplicate business result detected", report["errors"])

    def test_gtid_convergence_timeout_fails(self):
        report = evaluate(
            [],
            {"db1": []},
            [{"host": "db1", "role": "PRIMARY", "state": "ONLINE"}],
            expected_online=1,
            convergence_errors=["db2 did not apply the Primary GTID set"],
        )
        self.assertIn("db2 did not apply the Primary GTID set", report["errors"])


if __name__ == "__main__":
    unittest.main()
```

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_verifier.py -v
```

Expected: FAIL because `verifier.verify` does not exist.

- [ ] **Step 2: Implement the pure evaluation rules and live collector**

```python
# mysql-handson/00-lab/ha/verifier/verify.py
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from typing import Any

from workload.model import JsonlLedger, LedgerRecord, Outcome


def evaluate(
    records: list[LedgerRecord],
    member_ids: dict[str, list[str]],
    topology: list[dict[str, str]],
    expected_online: int,
    convergence_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[str] = list(convergence_errors or [])
    canonical_rows = next(iter(member_ids.values()), [])
    canonical = set(canonical_rows)
    acknowledged = sorted({r.request_id for r in records if r.outcome is Outcome.SUCCESS})
    unknown_ids = sorted({r.request_id for r in records if r.outcome is Outcome.UNKNOWN})

    for request_id in acknowledged:
        if request_id not in canonical:
            errors.append(f"acknowledged request missing: {request_id}")

    counts = Counter(canonical_rows)
    if any(count != 1 for count in counts.values()):
        errors.append("duplicate business result detected")

    snapshots = [set(rows) for rows in member_ids.values()]
    if snapshots and any(snapshot != snapshots[0] for snapshot in snapshots[1:]):
        errors.append("online member data diverged")

    online = [member for member in topology if member["state"] == "ONLINE"]
    primaries = [member for member in online if member["role"] == "PRIMARY"]
    if len(online) != expected_online:
        errors.append(f"expected {expected_online} ONLINE members, got {len(online)}")
    if len(primaries) != 1:
        errors.append(f"expected exactly one ONLINE PRIMARY, got {len(primaries)}")

    return {
        "ok": not errors,
        "errors": errors,
        "outcomes": dict(Counter(record.outcome.value for record in records)),
        "acknowledged": len(acknowledged),
        "unknown": {
            "committed": [value for value in unknown_ids if value in canonical],
            "absent": [value for value in unknown_ids if value not in canonical],
        },
        "members": {host: len(ids) for host, ids in member_ids.items()},
        "topology": topology,
    }


def connect(host: str, user: str | None = None, password: str | None = None):
    import mysql.connector

    return mysql.connector.connect(
        host=host,
        port=3306,
        user=user or os.getenv("MYSQL_CLUSTER_ADMIN", "icadmin"),
        password=password or os.getenv("MYSQL_CLUSTER_ADMIN_PASSWORD", "ha-cluster"),
        connection_timeout=3,
    )


def fetch_ids(host: str) -> list[str]:
    connection = connect(
        host,
        os.getenv("MYSQL_APP_USER", "ha_app"),
        os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
    )
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT request_id FROM ha_lab.orders ORDER BY request_id")
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


def fetch_topology() -> list[dict[str, str]]:
    for seed in ("db1", "db2", "db3"):
        try:
            connection = connect(seed)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT MEMBER_HOST, MEMBER_ROLE, MEMBER_STATE "
                "FROM performance_schema.replication_group_members ORDER BY MEMBER_HOST"
            )
            rows = [
                {"host": host, "role": role, "state": state}
                for host, role, state in cursor.fetchall()
            ]
            connection.close()
            return rows
        except Exception:
            continue
    return []


def fetch_gtid_executed(host: str) -> str:
    connection = connect(host)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT @@GLOBAL.gtid_executed")
        return str(cursor.fetchone()[0])
    finally:
        connection.close()


def wait_for_gtid(host: str, gtid_set: str, timeout_seconds: int = 30) -> bool:
    connection = connect(host)
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT WAIT_FOR_EXECUTED_GTID_SET(%s, %s)",
            (gtid_set, timeout_seconds),
        )
        return int(cursor.fetchone()[0]) == 0
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--expected-online", type=int, default=3)
    args = parser.parse_args()

    records = JsonlLedger.load(args.evidence_dir.glob("ledger-*.jsonl"))
    topology = fetch_topology()
    online_hosts = [row["host"] for row in topology if row["state"] == "ONLINE"]
    primary_hosts = [
        row["host"] for row in topology
        if row["state"] == "ONLINE" and row["role"] == "PRIMARY"
    ]
    convergence_errors: list[str] = []
    if len(primary_hosts) == 1:
        primary_gtid = fetch_gtid_executed(primary_hosts[0])
        for host in online_hosts:
            if not wait_for_gtid(host, primary_gtid):
                convergence_errors.append(
                    f"{host} did not apply the Primary GTID set"
                )
    else:
        convergence_errors.append(
            f"GTID barrier requires exactly one ONLINE PRIMARY, got {len(primary_hosts)}"
        )
    member_ids = {host: fetch_ids(host) for host in online_hosts}
    report = evaluate(
        records,
        member_ids,
        topology,
        args.expected_online,
        convergence_errors,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    (args.evidence_dir / "verification.json").write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
```

Create an empty `verifier/__init__.py`.

- [ ] **Step 3: Package and expose the verifier service**

Add to `workload/Dockerfile`:

```dockerfile
COPY verifier /app/verifier
```

Add under `services:` in `compose.yml`:

```yaml
  verifier:
    build:
      context: .
      dockerfile: workload/Dockerfile
    command: ["python", "-m", "verifier.verify", "--expected-online", "3"]
    environment:
      MYSQL_CLUSTER_ADMIN: ${MYSQL_CLUSTER_ADMIN:-icadmin}
      MYSQL_CLUSTER_ADMIN_PASSWORD: ${MYSQL_CLUSTER_ADMIN_PASSWORD:-ha-cluster}
      MYSQL_APP_USER: ${MYSQL_APP_USER:-ha_app}
      MYSQL_APP_PASSWORD: ${MYSQL_APP_PASSWORD:-ha-app}
    volumes: ["./evidence:/evidence"]
    networks: [ha-net]
```

Append to `Makefile`:

```makefile
.PHONY: test verify

test:
	docker build -f workload/Dockerfile -t mysql-ha-workload:test .
	docker run --rm mysql-ha-workload:test python -m unittest discover -s tests -v

verify:
	$(DC) run --rm verifier python -m verifier.verify --expected-online $${EXPECTED_ONLINE:-3}
```

- [ ] **Step 4: Prove the verifier detects a missing acknowledged write**

Run the green path first:

```bash
make -C mysql-handson/00-lab/ha test
make -C mysql-handson/00-lab/ha reset
make -C mysql-handson/00-lab/ha up
make -C mysql-handson/00-lab/ha workload-once N=5
make -C mysql-handson/00-lab/ha verify
```

Expected: all unit tests PASS and `verification.json` contains `"ok": true`, `"acknowledged": 10`, no convergence error, three equal member counts, and one ONLINE Primary.

The unit test `test_missing_acknowledged_write_fails` is the explicit negative path: it supplies a `SUCCESS` ledger record absent from the member data and must assert `acknowledged request missing: ack-1`.

- [ ] **Step 5: Commit**

```bash
git add mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): verify outcomes topology and replicas"
```

---

### Task 6: 实现有边界的故障注入与恢复控制器

**Files:**
- Create: `mysql-handson/00-lab/ha/faults/lib.sh`
- Create: `mysql-handson/00-lab/ha/faults/inject.sh`
- Create: `mysql-handson/00-lab/ha/faults/restore.sh`
- Create: `mysql-handson/00-lab/ha/bootstrap/rejoin.js`
- Create: `mysql-handson/00-lab/ha/tests/test_fault_scripts.py`
- Modify: `mysql-handson/00-lab/ha/Makefile`

**Interfaces:**
- Consumes: only containers labeled by Compose project `mysql-ha` and network `mysql-ha-net`.
- Produces: `evidence/events.jsonl` with `fault_begin`／`fault_active`／`fault_end`, plus `evidence/fault-state.env` used only by `restore.sh`.

- [ ] **Step 1: Write failing safety tests**

```python
# mysql-handson/00-lab/ha/tests/test_fault_scripts.py
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FaultScriptTest(unittest.TestCase):
    def test_faults_are_scoped_to_project_and_network(self):
        text = (ROOT / "faults/lib.sh").read_text(encoding="utf-8")
        self.assertIn("--project-name mysql-ha", text)
        self.assertIn("mysql-ha-net", text)

    def test_injector_has_all_first_seven_fault_modes(self):
        text = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        for name in (
            "planned-switchover", "primary-crash", "primary-partition",
            "quorum-loss", "slow-member", "router-failure", "member-rejoin",
        ):
            self.assertIn(f"{name})", text)

    def test_fault_scripts_do_not_use_host_wide_cleanup(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "faults").glob("*.sh"))
        for forbidden in ("docker system prune", "docker network prune", "pkill", "killall"):
            self.assertNotIn(forbidden, text)

    def test_recovery_state_precedes_reversible_partition_mutation(self):
        text = (ROOT / "faults/inject.sh").read_text(encoding="utf-8")
        self.assertIn(
            'write_state\n    docker network disconnect --force "$NETWORK" "mysql-ha-$target"',
            text,
        )


if __name__ == "__main__":
    unittest.main()
```

Run:

```bash
python3 -m unittest mysql-handson/00-lab/ha/tests/test_fault_scripts.py -v
```

Expected: FAIL because the fault scripts do not exist.

- [ ] **Step 2: Add shared discovery, state and event helpers**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/faults/lib.sh
set -euo pipefail

HA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$HA_ROOT/compose.yml")
NETWORK=mysql-ha-net
EVENTS="$HA_ROOT/evidence/events.jsonl"
STATE="$HA_ROOT/evidence/fault-state.env"
ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-ha-root}"

mkdir -p "$HA_ROOT/evidence"

now_utc() {
  python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat(timespec="microseconds"))'
}

record_event() {
  local phase="$1" scenario="$2" target="$3"
  printf '{"at":"%s","phase":"%s","scenario":"%s","target":"%s"}\n' \
    "$(now_utc)" "$phase" "$scenario" "$target" >> "$EVENTS"
}

query_group() {
  local sql="$1" seed
  for seed in db1 db2 db3; do
    if output="$("${DC[@]}" exec -T "$seed" mysql -uroot -p"$ROOT_PASSWORD" -Nse "$sql" 2>/dev/null)"; then
      printf '%s\n' "$output"
      return 0
    fi
  done
  return 1
}

primary_member() {
  query_group "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'"
}

secondary_members() {
  query_group "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='SECONDARY' AND MEMBER_STATE='ONLINE' ORDER BY MEMBER_HOST"
}

wait_for_online() {
  local expected="$1" count
  for _ in $(seq 1 60); do
    count="$(query_group "SELECT COUNT(*) FROM performance_schema.replication_group_members WHERE MEMBER_STATE='ONLINE'" || true)"
    [ "$count" = "$expected" ] && return 0
    sleep 1
  done
  return 1
}
```

- [ ] **Step 3: Add the seven bounded injection modes**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/faults/inject.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

scenario="${1:?usage: inject.sh SCENARIO}"
target=""
targets=""
record_event fault_begin "$scenario" pending

write_state() {
  {
    printf 'SCENARIO=%q\n' "$scenario"
    printf 'TARGET=%q\n' "$target"
    printf 'TARGETS=%q\n' "$targets"
    printf 'OLD_FLOW_THRESHOLD=%q\n' "${old_threshold:-25000}"
  } > "$STATE"
}

case "$scenario" in
  planned-switchover)
    old_primary="$(primary_member)"
    target=db2
    [ "$old_primary" = db2 ] && target=db3
    write_state
    "${DC[@]}" run --rm -e MYSQL_SEED="$old_primary" -e MYSQL_TARGET_MEMBER="$target" \
      shell mysqlsh --js --file=/bootstrap/set-primary.js
    ;;
  primary-crash)
    target="$(primary_member)"
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
  primary-partition)
    target="$(primary_member)"
    write_state
    docker network disconnect --force "$NETWORK" "mysql-ha-$target"
    offline_mode=0
    super_read_only=0
    for _ in $(seq 1 20); do
      values="$(
        "${DC[@]}" exec -T "$target" mysql -uroot -p"$ROOT_PASSWORD" -Nse \
          "SELECT @@offline_mode, @@super_read_only" 2>/dev/null || true
      )"
      if [ -n "$values" ]; then
        read -r offline_mode super_read_only <<< "$values"
        if [ "$offline_mode" = 1 ] || [ "$super_read_only" = 1 ]; then break; fi
      fi
      sleep 1
    done
    if [ "$offline_mode" != 1 ] && [ "$super_read_only" != 1 ]; then
      echo "isolated Primary was not fenced" >&2
      exit 1
    fi
    if "${DC[@]}" exec -T "$target" mysql -h127.0.0.1 -uha_app -pha-app ha_lab \
      -e "INSERT INTO orders(request_id,payload,via_router) VALUES ('fence-probe-$target', JSON_OBJECT('probe',true), 'direct')"; then
      echo "fenced Primary accepted an application write" >&2
      exit 1
    fi
    printf '{"target":"%s","offline_mode":%s,"super_read_only":%s,"write_rejected":true}\n' \
      "$target" "$offline_mode" "$super_read_only" > "$HA_ROOT/evidence/fencing.json"
    ;;
  quorum-loss)
    target="$(primary_member)"
    targets="$(secondary_members | tr '\n' ' ' | xargs)"
    write_state
    "${DC[@]}" stop $targets
    # Do not wait past the Lab's 5-second unreachable-majority timeout here.
    # The running workload proves commits cannot complete without quorum.
    ;;
  slow-member)
    target=db3
    [ "$(primary_member)" = db3 ] && target=db2
    old_threshold="$(query_group 'SELECT @@group_replication_flow_control_applier_threshold')"
    write_state
    for member in db1 db2 db3; do
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=10"
    done
    docker update --cpus 0.10 "mysql-ha-$target" >/dev/null
    ;;
  router-failure)
    target=router-a
    write_state
    "${DC[@]}" stop router-a
    ;;
  member-rejoin)
    target="$(secondary_members | head -n1)"
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
  *)
    echo "unsupported scenario: $scenario" >&2
    exit 2
    ;;
esac

record_event fault_active "$scenario" "${target:-$targets}"
```

- [ ] **Step 4: Add rejoin and exact inverse operations**

```javascript
// mysql-handson/00-lab/ha/bootstrap/rejoin.js
shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const seed = os.getenv('MYSQL_SEED') || 'db1';
const target = os.getenv('MYSQL_TARGET_MEMBER');
if (!target) throw new Error('MYSQL_TARGET_MEMBER is required');
shell.connect({scheme: 'mysql', user, password, host: seed, port: 3306});
const cluster = dba.getCluster('haLabCluster');
cluster.rejoinInstance({scheme: 'mysql', user, password, host: target, port: 3306});
print(JSON.stringify(cluster.status({extended: 1}), null, 2));
```

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/faults/restore.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"
[ -f "$STATE" ] || { echo "missing fault state" >&2; exit 2; }
source "$STATE"

rejoin() {
  local target="$1" seed state
  docker update --restart=on-failure "mysql-ha-$target" >/dev/null 2>&1 || true
  "${DC[@]}" up -d "$target"
  record_event rejoin_begin "$SCENARIO" "$target"
  for _ in $(seq 1 60); do
    if "${DC[@]}" exec -T "$target" mysqladmin ping -uroot -p"$ROOT_PASSWORD" --silent; then break; fi
    sleep 1
  done
  state="$(query_group "SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_HOST='$target'" || true)"
  if [ "$state" != ONLINE ]; then
    seed="$(primary_member)"
    "${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_TARGET_MEMBER="$target" \
      shell mysqlsh --js --file=/bootstrap/rejoin.js
  fi
  for _ in $(seq 1 90); do
    state="$(query_group "SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_HOST='$target'" || true)"
    [ "$state" = ONLINE ] && break
    sleep 1
  done
  [ "$state" = ONLINE ]
  record_event rejoin_online "$SCENARIO" "$target"
}

case "$SCENARIO" in
  planned-switchover) ;;
  primary-crash|member-rejoin) rejoin "$TARGET" ;;
  primary-partition)
    docker network connect "$NETWORK" "mysql-ha-$TARGET" >/dev/null 2>&1 || true
    rejoin "$TARGET"
    ;;
  quorum-loss)
    record_event quorum_restore_begin "$SCENARIO" "$TARGETS"
    for member in $TARGETS; do rejoin "$member"; done
    ;;
  slow-member)
    docker update --cpus 0 "mysql-ha-$TARGET" >/dev/null
    for member in db1 db2 db3; do
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=$OLD_FLOW_THRESHOLD"
    done
    ;;
  router-failure) "${DC[@]}" up -d router-a ;;
esac

wait_for_online 3
record_event fault_end "$SCENARIO" "${TARGET:-$TARGETS}"
rm -f "$STATE"
```

- [ ] **Step 5: Add Make targets and verify script syntax**

Append to `Makefile`:

```makefile
.PHONY: fault restore

fault:
	./faults/inject.sh $${SCENARIO:?set SCENARIO}

restore:
	./faults/restore.sh
```

Run:

```bash
chmod +x mysql-handson/00-lab/ha/faults/inject.sh mysql-handson/00-lab/ha/faults/restore.sh
bash -n mysql-handson/00-lab/ha/faults/lib.sh
bash -n mysql-handson/00-lab/ha/faults/inject.sh
bash -n mysql-handson/00-lab/ha/faults/restore.sh
python3 -m unittest mysql-handson/00-lab/ha/tests/test_fault_scripts.py -v
```

Expected: executable bits are recorded; all Bash syntax checks exit `0`; all 4 safety tests PASS.

- [ ] **Step 6: Exercise one reversible fault**

Run:

```bash
make -C mysql-handson/00-lab/ha reset
make -C mysql-handson/00-lab/ha up
make -C mysql-handson/00-lab/ha fault SCENARIO=router-failure
docker compose --project-name mysql-ha --file mysql-handson/00-lab/ha/compose.yml ps router-a router-b
make -C mysql-handson/00-lab/ha restore
make -C mysql-handson/00-lab/ha status
```

Expected: Router A is stopped while Router B stays running; restore starts Router A; Cluster remains `OK` with 3 ONLINE members.

- [ ] **Step 7: Commit**

```bash
git add mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): add scoped fault controller"
```

---

### Task 7: 实现 Scenario 01–07 的观测与断言框架

**Files:**
- Create: `mysql-handson/00-lab/ha/verifier/metrics.py`
- Create: `mysql-handson/00-lab/ha/verifier/scenarios.py`
- Create: `mysql-handson/00-lab/ha/verifier/session_probe.py`
- Create: `mysql-handson/00-lab/ha/verifier/timeline.py`
- Create: `mysql-handson/00-lab/ha/scenarios/run.sh`
- Create: `mysql-handson/00-lab/ha/tests/test_scenarios.py`
- Modify: `mysql-handson/00-lab/ha/Makefile`

**Interfaces:**
- Consumes: Task 4 ledgers, Task 5 base verification and Task 6 event windows.
- Produces: `evidence/scenario-verification.json`, segmented RTO, old-session／new-session Router evidence, and scenario-specific hard assertions. Task 8 consumes this framework to run and document the first seven core scenarios.

- [ ] **Step 1: Write failing scenario-window tests**

```python
# mysql-handson/00-lab/ha/tests/test_scenarios.py
import unittest

from verifier.scenarios import assert_scenario
from workload.model import LedgerRecord, Outcome


def result(router, at, outcome):
    return LedgerRecord(
        f"{router}-{at}", "{}", router, at, at, outcome, 0, None,
    )


class ScenarioAssertionTest(unittest.TestCase):
    def test_quorum_loss_allows_no_success_in_active_window(self):
        records = [
            result("router-a", "2026-01-01T00:00:02+00:00", Outcome.SUCCESS),
            result("router-a", "2026-01-01T00:00:05+00:00", Outcome.SUCCESS),
        ]
        events = [
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "quorum_restore_begin", "at": "2026-01-01T00:00:03+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:04+00:00"},
        ]
        report = assert_scenario("quorum-loss", records, events)
        self.assertIn("write succeeded without quorum", report["errors"])

    def test_router_failure_requires_router_b_success(self):
        records = [result("router-b", "2026-01-01T00:00:02+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
        ]
        self.assertEqual(assert_scenario("router-failure", records, events)["errors"], [])

    def test_slow_member_requires_queue_and_flow_control_growth(self):
        events = [
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:03+00:00"},
        ]
        metrics = [
            {"phase": "before", "members": {"db3": {
                "applier_queue": 0,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
            {"phase": "active", "members": {"db3": {
                "applier_queue": 12,
                "flow_control_applier_threshold": 10,
                "flow_control_mode": "QUOTA",
            }}},
        ]
        report = assert_scenario("slow-member", [], events, metrics)
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["metrics"]["flow_control_triggered"])

    def test_primary_crash_reports_segmented_rto(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:00.100000+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        report = assert_scenario("primary-crash", records, events, timeline=timeline)
        self.assertEqual(
            report["rto_segments_ms"],
            {"detection": 1000, "election": 1000, "backlog_fence": 500,
             "router_refresh": 500,
             "application_reconnect": 1000, "total": 4000},
        )

    def test_primary_partition_requires_fencing_evidence(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        fencing = {"offline_mode": 1, "super_read_only": 1, "write_rejected": True}
        session = {
            "old_backend": "db1",
            "existing_session_disconnected": True,
            "new_backend": "db2",
        }
        self.assertEqual(
            assert_scenario(
                "primary-partition", records, events,
                timeline=timeline, fencing=fencing, session=session,
            )["errors"],
            [],
        )

    def test_member_rejoin_requires_explicit_recovery_events(self):
        events = [
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "rejoin_begin", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "rejoin_online", "at": "2026-01-01T00:00:03+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:04+00:00"},
        ]
        self.assertEqual(assert_scenario("member-rejoin", [], events)["errors"], [])

    def test_failover_requires_old_session_disconnect_and_new_backend(self):
        records = [result("router-a", "2026-01-01T00:00:04+00:00", Outcome.SUCCESS)]
        events = [
            {"phase": "fault_begin", "at": "2026-01-01T00:00:00+00:00"},
            {"phase": "fault_active", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "fault_end", "at": "2026-01-01T00:00:05+00:00"},
        ]
        timeline = [
            {"phase": "failure_detected", "at": "2026-01-01T00:00:01+00:00"},
            {"phase": "primary_elected", "at": "2026-01-01T00:00:02+00:00"},
            {"phase": "primary_writable", "at": "2026-01-01T00:00:02.500000+00:00"},
            {"phase": "router_ready", "at": "2026-01-01T00:00:03+00:00"},
        ]
        session = {
            "old_backend": "db1",
            "existing_session_disconnected": True,
            "new_backend": "db2",
        }
        self.assertEqual(
            assert_scenario(
                "primary-crash", records, events, timeline=timeline, session=session,
            )["errors"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
```

Run:

```bash
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_scenarios.py -v
```

Expected: FAIL because `verifier.scenarios` does not exist.

- [ ] **Step 2: Implement event-window and RTO assertions**

```python
# mysql-handson/00-lab/ha/verifier/scenarios.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from workload.model import LedgerRecord, Outcome


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assert_scenario(
    scenario: str,
    records: list[LedgerRecord],
    events: list[dict[str, str]],
    metrics: list[dict[str, Any]] | None = None,
    timeline: list[dict[str, str]] | None = None,
    fencing: dict[str, Any] | None = None,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    active = next(event for event in events if event["phase"] == "fault_active")
    window_end_phase = "quorum_restore_begin" if scenario == "quorum-loss" else "fault_end"
    ended = next(event for event in events if event["phase"] == window_end_phase)
    start_at, end_at = parse(active["at"]), parse(ended["at"])
    during = [record for record in records if start_at <= parse(record.finished_at) <= end_at]
    attempts_started_during = [
        record for record in records
        if start_at <= parse(record.started_at) and parse(record.finished_at) <= end_at
    ]
    successes = [
        record for record in attempts_started_during if record.outcome is Outcome.SUCCESS
    ]

    if scenario == "quorum-loss" and any(
        record.outcome is Outcome.SUCCESS for record in attempts_started_during
    ):
        errors.append("write succeeded without quorum")
    if scenario == "quorum-loss":
        restored_at = parse(next(event for event in events if event["phase"] == "fault_end")["at"])
        if not any(
            record.outcome is Outcome.SUCCESS and parse(record.finished_at) > restored_at
            for record in records
        ):
            errors.append("writes did not resume after quorum restoration")
    if scenario == "router-failure" and not any(
        record.router == "router-b" and record.outcome is Outcome.SUCCESS
        for record in attempts_started_during
    ):
        errors.append("router-b had no successful write during router-a outage")
    if scenario in {"planned-switchover", "primary-crash", "primary-partition"} and not successes:
        errors.append("service did not resume writes during failover window")
    if scenario == "primary-partition" and not (
        fencing
        and fencing.get("write_rejected") is True
        and (fencing.get("offline_mode") == 1 or fencing.get("super_read_only") == 1)
    ):
        errors.append("isolated Primary fencing was not proven")
    if scenario == "member-rejoin":
        phases = [event["phase"] for event in events]
        if "rejoin_begin" not in phases or "rejoin_online" not in phases:
            errors.append("member rejoin transition was not proven")
        elif phases.index("rejoin_begin") >= phases.index("rejoin_online"):
            errors.append("member rejoin events are out of order")
    if scenario in {"planned-switchover", "primary-crash", "primary-partition"}:
        if not session or session.get("existing_session_disconnected") is not True:
            errors.append("old Router session disconnect was not proven")
        elif not session.get("new_backend") or session["new_backend"] == session.get("old_backend"):
            errors.append("new Router session did not reach the new Primary")

    metric_summary: dict[str, Any] = {}
    if scenario == "slow-member":
        snapshots = {snapshot["phase"]: snapshot for snapshot in (metrics or [])}
        before_metrics = snapshots.get("before", {"members": {}})
        active_metrics = snapshots.get("active", {"members": {}})

        def max_queue(snapshot: dict[str, Any]) -> int:
            return max(
                (int(member["applier_queue"]) for member in snapshot["members"].values()),
                default=0,
            )

        active_members = list(active_metrics["members"].values())
        active_queue = max_queue(active_metrics)
        active_threshold = min(
            (int(member["flow_control_applier_threshold"]) for member in active_members),
            default=0,
        )
        flow_control_triggered = bool(active_members) and any(
            member["flow_control_mode"] == "QUOTA"
            and int(member["applier_queue"]) >= int(member["flow_control_applier_threshold"])
            for member in active_members
        )

        def p95_ms(values: list[int]) -> int | None:
            if not values:
                return None
            ordered = sorted(values)
            return ordered[int(0.95 * (len(ordered) - 1))]

        before_latencies = [
            int((parse(record.finished_at) - parse(record.started_at)).total_seconds() * 1000)
            for record in records
            if record.outcome is Outcome.SUCCESS and parse(record.finished_at) < start_at
        ]
        active_latencies = [
            int((parse(record.finished_at) - parse(record.started_at)).total_seconds() * 1000)
            for record in during
            if record.outcome is Outcome.SUCCESS
        ]

        metric_summary = {
            "applier_queue_delta": active_queue - max_queue(before_metrics),
            "active_applier_queue": active_queue,
            "active_threshold": active_threshold,
            "flow_control_triggered": flow_control_triggered,
            "before_p95_ms": p95_ms(before_latencies),
            "active_p95_ms": p95_ms(active_latencies),
        }
        if metric_summary["applier_queue_delta"] <= 0:
            errors.append("slow member did not grow the applier queue")
        if not flow_control_triggered:
            errors.append("applier queue did not cross the active flow-control threshold")

    before = sorted(
        (parse(record.finished_at) for record in records
         if record.outcome is Outcome.SUCCESS and parse(record.finished_at) < start_at),
    )
    after = sorted(
        (parse(record.finished_at) for record in records
         if record.outcome is Outcome.SUCCESS and parse(record.started_at) >= start_at),
    )
    rto_ms = None
    if before and after:
        rto_ms = int((after[0] - before[-1]).total_seconds() * 1000)

    rto_segments_ms: dict[str, int] = {}
    if scenario in {"planned-switchover", "primary-crash", "primary-partition"}:
        points = {point["phase"]: parse(point["at"]) for point in (timeline or [])}
        begin_at = parse(next(event for event in events if event["phase"] == "fault_begin")["at"])
        required = ("failure_detected", "primary_elected", "primary_writable", "router_ready")
        app_success = None
        if all(name in points for name in required):
            app_success = min(
                (parse(record.finished_at) for record in records
                 if record.outcome is Outcome.SUCCESS
                 and parse(record.started_at) >= points["router_ready"]),
                default=None,
            )
        if app_success is None:
            errors.append("segmented RTO timeline is incomplete")
        else:
            rto_segments_ms = {
                "detection": int((points["failure_detected"] - begin_at).total_seconds() * 1000),
                "election": int((points["primary_elected"] - points["failure_detected"]).total_seconds() * 1000),
                "backlog_fence": int((points["primary_writable"] - points["primary_elected"]).total_seconds() * 1000),
                "router_refresh": int((points["router_ready"] - points["primary_writable"]).total_seconds() * 1000),
                "application_reconnect": int((app_success - points["router_ready"]).total_seconds() * 1000),
                "total": int((app_success - begin_at).total_seconds() * 1000),
            }
            if any(value < 0 for value in rto_segments_ms.values()):
                errors.append("segmented RTO events are out of order")

    return {
        "scenario": scenario,
        "errors": errors,
        "ok": not errors,
        "rto_ms": rto_ms,
        "rto_segments_ms": rto_segments_ms,
        "metrics": metric_summary,
        "fencing": fencing or {},
        "session": session or {},
        "during": {
            outcome.value: sum(record.outcome is outcome for record in during)
            for outcome in Outcome
        },
        "attempts_started_during_window": len(attempts_started_during),
    }
```

Add the live metric collector used by the slow-member assertion:

```python
# mysql-handson/00-lab/ha/verifier/metrics.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from verifier.verify import connect


def collect(phase: str) -> dict:
    members = {}
    for host in ("db1", "db2", "db3"):
        connection = connect(host)
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE "
                "FROM performance_schema.replication_group_member_stats "
                "WHERE MEMBER_ID=@@server_uuid"
            )
            row = cursor.fetchone()
            cursor.execute(
                "SELECT @@GLOBAL.group_replication_flow_control_applier_threshold, "
                "@@GLOBAL.group_replication_flow_control_mode"
            )
            threshold, mode = cursor.fetchone()
            members[host] = {
                "applier_queue": int(row[0]) if row else 0,
                "flow_control_applier_threshold": int(threshold),
                "flow_control_mode": str(mode),
            }
        finally:
            connection.close()
    return {
        "phase": phase,
        "at": datetime.now(timezone.utc).isoformat(),
        "members": members,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("before", "active"))
    parser.add_argument("--output", type=Path, default=Path("/evidence/metrics.jsonl"))
    args = parser.parse_args()
    snapshot = collect(args.phase)
    with args.output.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(snapshot, sort_keys=True) + "\n")
    print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
```

Add a persistent-session probe for the three Primary-change scenarios. It opens one Router session before `fault_active`, proves that the old session is disconnected after its backend loses the Primary role, then proves that a newly established session reaches a different backend:

```python
# mysql-handson/00-lab/ha/verifier/session_probe.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

import mysql.connector


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(router: str):
    return mysql.connector.connect(
        host=router,
        port=6446,
        user=os.getenv("MYSQL_APP_USER", "ha_app"),
        password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
        database="ha_lab",
        connection_timeout=1,
        read_timeout=1,
        write_timeout=1,
    )


def backend(connection) -> str:
    cursor = connection.cursor()
    cursor.execute("SELECT @@hostname")
    value = str(cursor.fetchone()[0])
    cursor.close()
    return value


def wait_for_phase(events: Path, phase: str, deadline: float) -> None:
    needle = f'"phase":"{phase}"'
    while time.monotonic() < deadline:
        if events.exists() and needle in events.read_text(encoding="utf-8"):
            return
        time.sleep(0.05)
    raise TimeoutError(f"event not observed: {phase}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--router", default="router-a")
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    deadline = time.monotonic() + args.timeout_seconds

    old_connection = connect(args.router)
    old_backend = backend(old_connection)
    (args.evidence_dir / "session-ready").write_text(old_backend + "\n", encoding="utf-8")
    wait_for_phase(args.evidence_dir / "events.jsonl", "fault_active", deadline)

    disconnected_at = None
    while time.monotonic() < deadline:
        try:
            backend(old_connection)
        except Exception:
            disconnected_at = now()
            break
        time.sleep(0.1)
    try:
        old_connection.close()
    except Exception:
        pass

    new_backend = None
    reconnected_at = None
    while disconnected_at and time.monotonic() < deadline:
        try:
            connection = connect(args.router)
            candidate = backend(connection)
            connection.close()
            if candidate != old_backend:
                new_backend = candidate
                reconnected_at = now()
                break
        except Exception:
            pass
        time.sleep(0.1)

    report = {
        "old_backend": old_backend,
        "existing_session_disconnected": disconnected_at is not None,
        "disconnected_at": disconnected_at,
        "new_backend": new_backend,
        "reconnected_at": reconnected_at,
    }
    output = args.evidence_dir / "session.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if disconnected_at and new_backend else 1)


if __name__ == "__main__":
    main()
```

Add the failover observer. It starts before fault injection, waits for `fault_begin`, then records the first externally observable loss of the old write role, the new Primary election, the new Primary becoming writable after its backlog fence, and the first Router connection reaching it:

```python
# mysql-handson/00-lab/ha/verifier/timeline.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from verifier.verify import connect, fetch_topology


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append(path: Path, phase: str, **fields: str) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "phase": phase, **fields}, sort_keys=True) + "\n")


def router_target(host: str) -> str | None:
    import mysql.connector

    try:
        connection = mysql.connector.connect(
            host=host,
            port=6446,
            user=os.getenv("MYSQL_APP_USER", "ha_app"),
            password=os.getenv("MYSQL_APP_PASSWORD", "ha-app"),
            database="ha_lab",
            connection_timeout=1,
        )
        cursor = connection.cursor()
        cursor.execute("SELECT @@hostname")
        value = str(cursor.fetchone()[0])
        connection.close()
        return value
    except Exception:
        return None


def member_is_writable(host: str) -> bool:
    try:
        connection = connect(host)
        cursor = connection.cursor()
        cursor.execute("SELECT @@super_read_only, @@offline_mode")
        super_read_only, offline_mode = cursor.fetchone()
        connection.close()
        return int(super_read_only) == 0 and int(offline_mode) == 0
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-primary", required=True)
    parser.add_argument("--evidence-dir", type=Path, default=Path("/evidence"))
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    args = parser.parse_args()
    events = args.evidence_dir / "events.jsonl"
    output = args.evidence_dir / "timeline.jsonl"
    deadline = time.monotonic() + args.timeout_seconds

    while time.monotonic() < deadline:
        if events.exists() and '"phase":"fault_begin"' in events.read_text(encoding="utf-8"):
            break
        time.sleep(0.05)
    else:
        raise SystemExit("fault_begin was not observed")

    detected = False
    elected: str | None = None
    writable = False
    while time.monotonic() < deadline:
        topology = fetch_topology()
        old = next((row for row in topology if row["host"] == args.old_primary), None)
        if not detected and (old is None or old["state"] != "ONLINE" or old["role"] != "PRIMARY"):
            append(output, "failure_detected", old_primary=args.old_primary)
            detected = True
        primary = next(
            (row["host"] for row in topology
             if row["state"] == "ONLINE" and row["role"] == "PRIMARY" and row["host"] != args.old_primary),
            None,
        )
        if detected and primary and elected is None:
            elected = primary
            append(output, "primary_elected", new_primary=primary)
        if elected and not writable and member_is_writable(elected):
            append(output, "primary_writable", new_primary=elected)
            writable = True
        if elected and writable:
            for router in ("router-a", "router-b"):
                if router_target(router) == elected:
                    append(output, "router_ready", router=router, new_primary=elected)
                    return
        time.sleep(0.1)
    raise SystemExit("failover timeline did not complete")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Add the independent scenario runner**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/scenarios/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
scenario="${1:?usage: run.sh SCENARIO}"
case "$scenario" in
  planned-switchover|primary-crash|primary-partition|quorum-loss|slow-member|router-failure|member-rejoin) ;;
  *) echo "unsupported scenario: $scenario" >&2; exit 2 ;;
esac

fault_may_be_active=0
cleanup() {
  status=$?
  trap - EXIT
  if [ "$fault_may_be_active" = 1 ] && [ -f "$ROOT/evidence/fault-state.env" ]; then
    make -C "$ROOT" restore || true
  fi
  make -C "$ROOT" workload-stop >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

make -C "$ROOT" reset
make -C "$ROOT" up
make -C "$ROOT" workload-start
sleep "${WARMUP_SECONDS:-5}"
watcher_pid=""
session_pid=""
if [[ "$scenario" = planned-switchover || "$scenario" = primary-crash || "$scenario" = primary-partition ]]; then
  old_primary="$("${DC[@]}" exec -T db1 mysql -uroot -pha-root -Nse "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'")"
  "${DC[@]}" run --rm verifier python -m verifier.timeline --old-primary "$old_primary" &
  watcher_pid=$!
  "${DC[@]}" run --rm verifier python -m verifier.session_probe --router router-a &
  session_pid=$!
  for _ in $(seq 1 100); do
    [ -f "$ROOT/evidence/session-ready" ] && break
    sleep 0.05
  done
  [ -f "$ROOT/evidence/session-ready" ]
fi
if [ "$scenario" = slow-member ]; then
  "${DC[@]}" run --rm verifier python -m verifier.metrics --phase before
fi
fault_may_be_active=1
make -C "$ROOT" fault SCENARIO="$scenario"
if [ -n "$watcher_pid" ]; then wait "$watcher_pid"; fi
if [ -n "$session_pid" ]; then wait "$session_pid"; fi
if [ "$scenario" = slow-member ]; then
  make -C "$ROOT" workload-burst N=2000 &
  burst_pid=$!
  sleep 3
  "${DC[@]}" run --rm verifier python -m verifier.metrics --phase active
  wait "$burst_pid"
fi
fault_seconds="${FAULT_SECONDS:-12}"
if [ "$scenario" = quorum-loss ] && [ -z "${FAULT_SECONDS+x}" ]; then
  fault_seconds=3
fi
sleep "$fault_seconds"
make -C "$ROOT" restore
fault_may_be_active=0
sleep "${RECOVERY_SECONDS:-5}"
make -C "$ROOT" workload-stop
make -C "$ROOT" verify
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse \
  "SELECT written_by, COUNT(*) FROM ha_lab.orders GROUP BY written_by ORDER BY written_by" \
  > "$ROOT/evidence/written-by.txt"
"${DC[@]}" run --rm verifier \
  python -c "import json; from pathlib import Path; from workload.model import JsonlLedger; from verifier.scenarios import assert_scenario; root=Path('/evidence'); records=JsonlLedger.load(root.glob('ledger-*.jsonl')); events=[json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]; metric_path=root/'metrics.jsonl'; metrics=[json.loads(line) for line in metric_path.read_text().splitlines()] if metric_path.exists() else []; timeline_path=root/'timeline.jsonl'; timeline=[json.loads(line) for line in timeline_path.read_text().splitlines()] if timeline_path.exists() else []; fencing_path=root/'fencing.json'; fencing=json.loads(fencing_path.read_text()) if fencing_path.exists() else {}; session_path=root/'session.json'; session=json.loads(session_path.read_text()) if session_path.exists() else {}; report=assert_scenario('$scenario', records, events, metrics, timeline, fencing, session); (root/'scenario-verification.json').write_text(json.dumps(report, indent=2)+'\\n'); print(json.dumps(report, indent=2)); raise SystemExit(0 if report['ok'] else 1)"
archive="$ROOT/evidence/runs/$scenario/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$archive"
find "$ROOT/evidence" -mindepth 1 -maxdepth 1 -type f -exec cp {} "$archive"/ \;
trap - EXIT
```

Append to `Makefile`:

```makefile
.PHONY: scenario

scenario:
	./scenarios/run.sh $${SCENARIO:?set SCENARIO}
```

- [ ] **Step 4: Verify and commit the Scenario framework**

Run:

```bash
chmod +x mysql-handson/00-lab/ha/scenarios/run.sh
bash -n mysql-handson/00-lab/ha/scenarios/run.sh
PYTHONPATH=mysql-handson/00-lab/ha python3 -m unittest mysql-handson/00-lab/ha/tests/test_scenarios.py -v
git diff --check
```

Expected: the executable bit is recorded; Bash syntax exits `0`; all 7 scenario assertion tests PASS; whitespace check is silent.

```bash
git add mysql-handson/00-lab/ha
git commit -m "feat(mysql-ha): add scenario evidence framework"
```

---

### Task 8: 运行并记录核心 Scenario 01–07

**Files:**
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/01-planned-switchover.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/02-primary-crash.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/03-primary-partition.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/04-quorum-loss.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/05-slow-member.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/06-router-failure.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/07-member-rejoin.md`

**Interfaces:**
- Consumes: Task 7 runner plus its archived ledger, topology, timeline, session, fencing and queue evidence.
- Produces: seven independently rerunnable, evidence-backed Scenario reports; runtime values are added only after their matching run succeeds.

- [ ] **Step 1: Commit the prediction-only Scenario documents before running faults**

Each prediction commit contains only the headings that can be written before execution:

```markdown
# Scenario NN: 标题

## 我想验证的问题
## 预期
## 环境与命令
```

Use this exact command table in the matching file; do not invent runtime values:

| 文件 | 标题 | 命令 | 预期硬断言 |
|---|---|---|---|
| `01-planned-switchover.md` | 计划内切换不是零断线 | `make scenario SCENARIO=planned-switchover` | 新旧 Primary 唯一、既有连接可断、写入恢复、量出 RTO |
| `02-primary-crash.md` | Primary crash 后谁完成 failover | `make scenario SCENARIO=primary-crash` | 多数派选新 Primary、Router 只迁移新连接、所有 SUCCESS 存在，并量出 detection／election／backlog fence／Router refresh／application reconnect 五段 RTO |
| `03-primary-partition.md` | 少数派 Primary 必须被 fencing | `make scenario SCENARIO=primary-partition` | 隔离节点进入 `OFFLINE_MODE`／不可写，多数派继续写，重连后安全 rejoin |
| `04-quorum-loss.md` | 没有多数派宁可停止写 | `make scenario SCENARIO=quorum-loss` | 在 `fault_active` 后才开始、并于 `quorum_restore_begin` 前完成的请求零 SUCCESS，避免把故障前已跨过提交边界的 in-flight 请求误判为无 quorum 写入；默认 3 秒窗口保持在 Lab 的 5 秒 unreachable-majority timeout 内；恢复 quorum 后才继续 |
| `05-slow-member.md` | 慢成员如何触发 backlog 与 flow control | `make scenario SCENARIO=slow-member` | core Performance Schema 的 applier queue 跨过生效中的 QUOTA threshold；记录前后 p95 写延迟但不把易受环境噪声影响的延迟升高设为硬断言；成员最终追平 |
| `06-router-failure.md` | 双 Router 解决入口单点 | `make scenario SCENARIO=router-failure` | Router A worker 失败或未知，Router B worker 在故障窗仍有 SUCCESS |
| `07-member-rejoin.md` | 离群成员不能直接恢复服务 | `make scenario SCENARIO=member-rejoin` | `rejoin_begin` 先于 `rejoin_online`，成员经恢复阶段回到 ONLINE，三成员 ID 集完全相同 |

Commit:

```bash
git add mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/0[1-7]-*.md
git commit -m "docs(mysql-ha): record scenario predictions"
```

- [ ] **Step 2: Run all seven scenarios and capture generated evidence**

Run each command separately so one failure cannot hide another:

```bash
make -C mysql-handson/00-lab/ha scenario SCENARIO=planned-switchover
make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-crash
make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-partition
make -C mysql-handson/00-lab/ha scenario SCENARIO=quorum-loss
make -C mysql-handson/00-lab/ha scenario SCENARIO=slow-member
make -C mysql-handson/00-lab/ha scenario SCENARIO=router-failure
make -C mysql-handson/00-lab/ha scenario SCENARIO=member-rejoin
```

Expected for every run: base `verification.json` has `"ok": true`; scenario report has `"ok": true`; final status has 3 ONLINE members and exactly one Primary. The runner preserves top-level evidence under `evidence/runs/<scenario>/<UTC run id>/` before the next reset.

- [ ] **Step 3: Append measured evidence without rewriting the predictions**

For each file, append these exact headings after the successful run: `客户端证据`, `Cluster／成员证据`, `数据一致性证据`, `实机告诉我`, `预期 vs 实机落差`, `生产边界`, and `连到的面试卡`. Copy only these real fields from its preserved evidence: event timestamps, old/new Primary, `written_by` distribution, old-session disconnect and new-session backend where applicable, result counts by state, `rto_ms`, `rto_segments_ms`, topology modes, member row counts, and the relevant core queue／threshold or fencing fields. The `预期 vs 实机落差` section must explicitly state at least one observed timing or state-transition detail; if a run contradicted the prediction, explain the contradiction rather than editing the prediction retroactively.

Run:

```bash
rg -n '^## (客户端证据|Cluster／成员证据|数据一致性证据|实机告诉我|预期 vs 实机落差)$|rto_ms|SUCCESS|UNKNOWN|PRIMARY|ONLINE' mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/0[1-7]-*.md
git diff --check
```

Expected: every file contains all evidence headings and actual values; `git diff --check` is silent.

- [ ] **Step 4: Commit the measured reports**

```bash
git add mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/0[1-7]-*.md
git commit -m "test(mysql-ha): verify failover and recovery scenarios"
```

---

### Task 9: 把完整 Cluster outage 作为生产恢复演练

**Files:**
- Create: `mysql-handson/00-lab/ha/bootstrap/reboot.js`
- Create: `mysql-handson/00-lab/ha/scenarios/complete-outage.sh`
- Modify: `mysql-handson/00-lab/ha/Makefile`

**Interfaces:**
- Consumes: stopped Router and DB containers whose volumes remain intact.
- Produces: a supporting production-Runbook drill with a dry-run report, a safely rebooted Cluster from a pre-verified GTID-superset seed, exactly one writable Primary, and preserved business IDs. This drill is audited but is not numbered or counted as a core Scenario.

- [ ] **Step 1: Add AdminAPI dry-run／actual reboot script**

```javascript
// mysql-handson/00-lab/ha/bootstrap/reboot.js
shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const seed = os.getenv('MYSQL_SEED') || 'db1';
const dryRun = (os.getenv('MYSQL_REBOOT_DRY_RUN') || '1') === '1';
shell.connect({scheme: 'mysql', user, password, host: seed, port: 3306});
const cluster = dba.rebootClusterFromCompleteOutage('haLabCluster', {dryRun});
if (!dryRun) print(JSON.stringify(cluster.status({extended: 2}), null, 2));
```

- [ ] **Step 2: Add the complete-outage orchestration**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/scenarios/complete-outage.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
OUT="$ROOT/evidence/complete-outage"

now_utc() {
  python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat(timespec="microseconds"))'
}

record() {
  printf '{"at":"%s","phase":"%s"}\n' "$(now_utc)" "$1" >> "$OUT/events.jsonl"
}

make -C "$ROOT" reset
mkdir -p "$OUT"
rm -f \
  "$OUT/events.jsonl" \
  "$OUT/reboot-dry-run.txt" \
  "$OUT/reboot-actual.txt" \
  "$OUT/seed.txt" \
  "$OUT/before-ids.txt" \
  "$OUT/after-ids.txt" \
  "$OUT/final-status.json"
make -C "$ROOT" up
make -C "$ROOT" workload-once N=20
make -C "$ROOT" verify
seed="$("${DC[@]}" exec -T db1 mysql -uroot -pha-root -Nse "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'")"
printf '%s\n' "$seed" > "$OUT/seed.txt"
"${DC[@]}" stop router-a router-b
gtid="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse 'SELECT @@GLOBAL.gtid_executed')"
for member in db1 db2 db3; do
  waited="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse "SELECT WAIT_FOR_EXECUTED_GTID_SET('$gtid', 30)")"
  [ "$waited" = 0 ]
done
before="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse 'SELECT request_id FROM ha_lab.orders ORDER BY request_id')"
printf '%s\n' "$before" > "$OUT/before-ids.txt"

record outage_begin
"${DC[@]}" stop db1 db2 db3
"${DC[@]}" up -d db1 db2 db3
for member in db1 db2 db3; do
  until "${DC[@]}" exec -T "$member" mysqladmin ping -uroot -pha-root --silent; do sleep 2; done
done

record dry_run_begin
"${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=1 shell \
  mysqlsh --js --file=/bootstrap/reboot.js | tee "$OUT/reboot-dry-run.txt"
record actual_reboot_begin
"${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=0 shell \
  mysqlsh --js --file=/bootstrap/reboot.js | tee "$OUT/reboot-actual.txt"
online=0
for _ in $(seq 1 90); do
  online="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse "SELECT COUNT(*) FROM performance_schema.replication_group_members WHERE MEMBER_STATE='ONLINE'")"
  [ "$online" = 3 ] && break
  sleep 1
done
[ "$online" = 3 ]
"${DC[@]}" up -d router-a router-b
until "${DC[@]}" run --rm shell mysqladmin ping -hrouter-a -P6446 -uha_app -pha-app --silent; do sleep 2; done
make -C "$ROOT" verify
after="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse 'SELECT request_id FROM ha_lab.orders ORDER BY request_id')"
printf '%s\n' "$after" > "$OUT/after-ids.txt"
[ "$before" = "$after" ]
"${DC[@]}" run --rm shell mysqlsh --js --file=/bootstrap/status.js > "$OUT/final-status.json"
record recovery_verified
```

Append to `Makefile`; use a recovery target name so the exercise cannot be mistaken for a ninth core Scenario:

```makefile
.PHONY: recovery-complete-outage

recovery-complete-outage:
	./scenarios/complete-outage.sh
```

- [ ] **Step 3: Run the supporting drill and retain evidence for the Runbook**

Record these expectations in the operator notes at the top of `complete-outage.sh` before execution; Task 12 later carries the measured result into `production-runbook.md`:

```markdown
- `docker compose start` 只会启动进程，不会自行恢复已经全部停止的 Group Replication。
- 必须先让所有已知成员可达；本实验在停机前核对三份数据一致、保存当时的 Primary 作为候选 seed，再以 `dryRun:true` 验证它可安全重启 Cluster。
- 正常路径不使用 `force:true`；低 GTID 或分叉成员不能被强行选为 seed。
- 恢复成功的证据是唯一 R/W Primary、3 个 ONLINE 成员以及恢复前后业务 ID 集相同，不是容器变成 running。
```

Run:

```bash
chmod +x mysql-handson/00-lab/ha/scenarios/complete-outage.sh
bash -n mysql-handson/00-lab/ha/scenarios/complete-outage.sh
make -C mysql-handson/00-lab/ha recovery-complete-outage
```

Expected: the executable bit is recorded; dry-run completes without mutation; actual reboot succeeds; final verifier is green; ordered before／after business ID lists are byte-for-byte equal. Preserve the validated seed, topology, counts and command timings under `evidence/complete-outage/` for Task 12; do not create a numbered Scenario document.

- [ ] **Step 4: Commit**

```bash
git add mysql-handson/00-lab/ha/bootstrap/reboot.js mysql-handson/00-lab/ha/scenarios/complete-outage.sh mysql-handson/00-lab/ha/Makefile
git commit -m "test(mysql-ha): verify complete outage recovery"
```

---

### Task 10: 用全备份与 binlog position 实证核心 Scenario 08

**Files:**
- Create: `mysql-handson/00-lab/ha/scenarios/pitr.sh`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/08-ha-cannot-replace-pitr.md`
- Modify: `mysql-handson/00-lab/ha/compose.yml`
- Modify: `mysql-handson/00-lab/ha/Makefile`
- Modify: `mysql-handson/00-lab/ha/scenarios/run.sh`

**Interfaces:**
- Consumes: an ONLINE Cluster with binary logging and a dedicated standalone `recovery` service.
- Produces: the eighth core Scenario `ha-cannot-replace-pitr`, a base dump, saved start／stop binlog position, a Cluster-wide replicated accidental `DELETE`, and a recovery instance containing the intended pre-delete rows.

- [ ] **Step 1: Add a profile-scoped recovery instance**

Insert under `services:` in `compose.yml`:

```yaml
  recovery:
    image: mysql:8.4.10
    profiles: ["recovery"]
    container_name: mysql-ha-recovery
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-ha-root}
      MYSQL_ROOT_HOST: "%"
    ports: ["13309:3306"]
    volumes: ["recovery-data:/var/lib/mysql"]
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h127.0.0.1 -uroot -p$$MYSQL_ROOT_PASSWORD --silent"]
      interval: 3s
      timeout: 2s
      retries: 40
      start_period: 20s
    networks: [ha-net]
```

Add under `volumes:`:

```yaml
  recovery-data:
```

- [ ] **Step 2: Add a position-based PITR script**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/scenarios/pitr.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
OUT="$ROOT/evidence/pitr"
mkdir -p "$OUT"
rm -f \
  "$OUT/base.sql" \
  "$OUT/member-zero.txt" \
  "$OUT/recovered-count.txt" \
  "$OUT/binlog-window.txt"

make -C "$ROOT" reset
make -C "$ROOT" up
make -C "$ROOT" workload-once N=5
source "$ROOT/faults/lib.sh"
primary="$(primary_member)"

"${DC[@]}" exec -T "$primary" mysql -uroot -pha-root -e "FLUSH BINARY LOGS"
"${DC[@]}" run --rm shell mysqldump -h"$primary" -uroot -pha-root \
  --single-transaction --set-gtid-purged=OFF --databases ha_lab > "$OUT/base.sql"
read -r start_file start_pos _ < <("${DC[@]}" exec -T "$primary" mysql -uroot -pha-root -Nse "SHOW BINARY LOG STATUS")

keep_id="pitr-keep"
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -pha-root -e \
  "INSERT INTO ha_lab.orders(request_id,payload,via_router,written_by) VALUES ('$keep_id', JSON_OBJECT('keep',true), 'router-a', @@hostname)"
read -r stop_file stop_pos _ < <("${DC[@]}" exec -T "$primary" mysql -uroot -pha-root -Nse "SHOW BINARY LOG STATUS")
[ "$start_file" = "$stop_file" ]
expected_count="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -pha-root -Nse 'SELECT COUNT(*) FROM ha_lab.orders')"

"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -pha-root -e "DELETE FROM ha_lab.orders"
: > "$OUT/member-zero.txt"
for member in db1 db2 db3; do
  count=-1
  for _ in $(seq 1 30); do
    count="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse 'SELECT COUNT(*) FROM ha_lab.orders')"
    [ "$count" = 0 ] && break
    sleep 1
  done
  [ "$count" = 0 ]
  printf '%s %s\n' "$member" "$count" >> "$OUT/member-zero.txt"
done

"${DC[@]}" --profile recovery up -d recovery
until "${DC[@]}" exec -T recovery mysqladmin ping -uroot -pha-root --silent; do sleep 2; done
"${DC[@]}" exec -T recovery mysql -uroot -pha-root < "$OUT/base.sql"
"${DC[@]}" run --rm shell bash -o pipefail -c \
  "mysqlbinlog --read-from-remote-server --skip-gtids -h$primary -uroot -pha-root --start-position=$start_pos --stop-position=$stop_pos $start_file | mysql --binary-mode=1 -hrecovery -uroot -pha-root"

"${DC[@]}" exec -T recovery mysql -uroot -pha-root -Nse \
  "SELECT request_id FROM ha_lab.orders WHERE request_id='$keep_id'" | grep -qx "$keep_id"
recovered_count="$("${DC[@]}" exec -T recovery mysql -uroot -pha-root -Nse 'SELECT COUNT(*) FROM ha_lab.orders')"
[ "$recovered_count" = "$expected_count" ]
printf '%s\n' "$recovered_count" > "$OUT/recovered-count.txt"
printf '%s %s %s\n' "$start_file" "$start_pos" "$stop_pos" > "$OUT/binlog-window.txt"
```

- [ ] **Step 3: Route the eighth Scenario and write its prediction document**

Replace the earlier `reset` recipe in `Makefile` so a prior recovery container and volume cannot leak into another run; do not define a second `reset` target:

```makefile
reset:
	$(DC) --profile recovery down --volumes --remove-orphans
	@mkdir -p evidence
	@find evidence -mindepth 1 -maxdepth 1 -type f -delete
```

Update `scenarios/run.sh` immediately after parsing `scenario`, before the 01–07 case statement:

```bash
if [ "$scenario" = ha-cannot-replace-pitr ]; then
  exec "$ROOT/scenarios/pitr.sh"
fi
```

`08-ha-cannot-replace-pitr.md` must state before execution:

```markdown
- 错误 `DELETE` 是合法事务，Group Replication 会把它复制到所有成员；自动 failover 不会找回历史版本。
- 恢复链是「先还原一致全备份，再从备份记录的位置重放 binlog，到 destructive transaction 之前停止」。
- 时间戳只用于定位；实验以 `SHOW BINARY LOG STATUS` 的 file／position 作为精确边界。
- 恢复必须落到隔离的 recovery 实例，核对后再规划业务回迁，不能直接覆盖在线 Cluster。
```

- [ ] **Step 4: Run PITR and record actual recovery evidence**

Run:

```bash
chmod +x mysql-handson/00-lab/ha/scenarios/pitr.sh
bash -n mysql-handson/00-lab/ha/scenarios/pitr.sh
make -C mysql-handson/00-lab/ha scenario SCENARIO=ha-cannot-replace-pitr
```

Expected: the executable bit is recorded; all three Cluster members contain zero orders after the accidental delete; the recovery instance contains `pitr-keep` and all base-dump rows; replay excludes the delete; `binlog-window.txt` records one file and exact start／stop positions. Copy those positions, counts and member-zero evidence into the Scenario document.

- [ ] **Step 5: Commit**

```bash
git add mysql-handson/00-lab/ha/compose.yml mysql-handson/00-lab/ha/Makefile mysql-handson/00-lab/ha/scenarios/run.sh mysql-handson/00-lab/ha/scenarios/pitr.sh mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/08-ha-cannot-replace-pitr.md
git commit -m "test(mysql-ha): prove point-in-time recovery boundary"
```

---

### Task 11: 写产品无关的 HA 理论主线

**Files:**
- Create: `mysql-handson/09-replication-and-ha/ha-foundations.md`

**Interfaces:**
- Consumes: existing Chapter 09 replication concepts `ACK != apply != readable`.
- Produces: a product-neutral decision model referenced by the InnoDB Cluster guide, all Scenario reports and interview cards.

- [ ] **Step 1: Assert the theory document is absent and existing replication chapter stays canonical**

Run:

```bash
test ! -e mysql-handson/09-replication-and-ha/ha-foundations.md
rg -n 'ACK != apply|多数派|MySQL Router' mysql-handson/09-replication-and-ha/README.md
```

Expected: the first command exits `0`; the second still finds the existing replication boundaries that this document will link to rather than duplicate.

- [ ] **Step 2: Write the complete mental-model structure**

The new document must contain these sections in this order:

```markdown
# MySQL HA 基础：先定义承诺，再讨论产品

## 1. 先问：客户端看到成功时，系统承诺了什么
## 2. 三态请求结果：成功、失败、未知
## 3. 五个平面：应用、路由、控制、数据、存储
## 4. 故障模型：程序、主机、网络、慢节点、存储、入口、故障域
## 5. Quorum、选主与 fencing
## 6. 一次提交必须拆开的七个边界
## 7. RPO／RTO 与分段测量
## 8. HA、Backup／PITR、DR、Read Scaling 的边界
## 9. 从需求反推方案的决策表
## 10. 用本专题验证这些结论
## 11. 自测题
```

The three-state table must be exactly:

```markdown
| 客户端观察 | 数据库事实 | 应用动作 |
|---|---|---|
| 收到成功响应 | 事务已跨过方案定义的成功边界 | 记录成功；之后必须能按 `request_id` 找到 |
| 明确得知 SQL 未发送／事务未提交 | 没有业务结果 | 可以用同一 `request_id` 重试 |
| SQL 已发送但响应丢失 | 可能提交，也可能未提交 | 先按 `request_id` 查明；禁止生成新业务键盲重试 |
```

The failure matrix must answer all five questions for every fault:

```markdown
| 故障 | 还能否安全写 | 还能否安全读 | 谁决定 | 谁必须被 fencing | 未知结果来源 | 恢复入口 |
|---|---|---|---|---|---|---|
| MySQL 进程崩溃 | 取决于剩余成员是否有 quorum | 健康成员可按已声明的一致性语义读 | 控制面／成员协议 | 故障进程 | commit 与响应之间断线 | 选主后重连、旧成员 rejoin |
| 整台主机失效 | 同上 | 健康主机上的成员可读 | 控制面／成员协议 | 故障主机 | 客户端连接消失 | 替换主机或恢复成员 |
| 原 Primary 与多数派分区 | 多数派一侧可以 | 多数派可读；少数派旧 Primary 不可信 | quorum | 少数派旧 Primary | 旧连接失效 | 网络恢复后验证并 rejoin |
| 失去 quorum | 不可以 | 只有明确接受陈旧性的读策略才可讨论，不能当强一致读 | 成员协议 | 所有剩余少数派 | 在失去多数派前后的请求 | 恢复多数派，禁止双边强开 |
| 节点很慢 | 通常可以但吞吐受 flow control 约束 | 可读，但慢成员可能落后 | 数据面＋控制面 | 失联后才 fencing | 超时但事务可能完成 | 找出 queue／资源根因 |
| Router 失效 | Cluster 可写但该入口不可达 | 另一 Router／直连健康成员仍可读 | 路由面／应用 | 故障 Router | 连接中断 | 另一个 Router＋应用重连 |
| 存储损坏／误删 | HA 不能恢复历史正确版本 | 可能可读但业务事实已经错误 | 存储／恢复系统 | 损坏副本或在线写入口 | 恢复过程中的业务请求 | 隔离恢复＋Backup／PITR |
| 整个故障域失效 | 本地域不可写；是否可切换取决于另建的 DR | 本地域不可读 | DR 控制面与业务决策 | 原故障域写入口 | 跨域切换窗口内请求 | 本 Lab 不实现；进入 DR Runbook |
```

The seven boundaries must remain numbered exactly as in the approved spec: Primary execution, write-set generation／propagation, ordering／certification, local commit, client success, Secondary apply, Secondary read visibility.

- [ ] **Step 3: Add measurable worksheets instead of qualitative claims**

Include these formulas and worksheet:

```markdown
- `RPO = 故障后缺失且曾被确认成功的业务结果数`；本 Lab 的通过值是 `0`。
- `客户端观测 RTO = 故障窗后首次 SUCCESS 时间 - 故障前最后一次 SUCCESS 时间`。
- `总 RTO = 检测 + view change／选主 + backlog fence + Router topology refresh + 应用重连`。

| 时间点 | 从哪里取证 |
|---|---|
| fault begin／active／end | `evidence/events.jsonl` |
| 最后一次故障前成功 | `ledger-*.jsonl` |
| 检测、选主、可写与 Router ready | `evidence/timeline.jsonl`（由成员状态、直连可写探针与 Router 探针产生） |
| Router 后第一次成功 | 对应 worker ledger |
| 成员全部追平 | verifier 的成员 ID 集比较 |
```

- [ ] **Step 4: Add exact scope boundaries and self-test answers**

The document must state directly:

```markdown
本地 Compose 只能验证成员协议、路由、客户端重连和数据结果；它不能证明三台容器拥有独立电源、磁盘、交换机或可用区。生产结论必须重新验证故障域、网络 RTT／抖动、存储持久性和备份可恢复性。
```

End with five questions and collapsed answers covering: two nodes and quorum, success vs unknown, ACK vs apply, Router vs election, HA vs PITR. Each answer must name the exact layer responsible.

- [ ] **Step 5: Verify scope and commit**

Run:

```bash
rg -n '^## [1-9]|^## 10\.|^## 11\.|三态请求结果|五个平面|Quorum、选主与 fencing|七个边界|RPO =|客户端观测 RTO|HA、Backup／PITR、DR、Read Scaling' mysql-handson/09-replication-and-ha/ha-foundations.md
rg -n 'MHA 部署|Orchestrator 部署|multi-primary 配置|Kubernetes' mysql-handson/09-replication-and-ha/ha-foundations.md
git diff --check
```

Expected: every required heading and boundary is found; the product-deployment search returns no matches; whitespace check is silent.

```bash
git add mysql-handson/09-replication-and-ha/ha-foundations.md
git commit -m "docs(mysql-ha): add product-neutral HA foundations"
```

---

### Task 12: 写 InnoDB Cluster 教程与生产 Runbook

**Files:**
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/README.md`
- Create: `mysql-handson/09-replication-and-ha/innodb-cluster/production-runbook.md`

**Interfaces:**
- Consumes: Task 11 terminology, Task 2 exact baseline, Tasks 8 and 10 measured core Scenario evidence, and Task 9 complete-outage recovery evidence.
- Produces: one learning path from component responsibility through production operations, with commands that map to the implemented Lab rather than a second configuration source.

- [ ] **Step 1: Write the product guide with fixed section contract**

`innodb-cluster/README.md` must contain:

```markdown
# MySQL 8.4 InnoDB Cluster：从提交边界到故障切换

## 1. 这套方案解决什么，不解决什么
## 2. 组件责任：Server、Group Replication、Shell／AdminAPI、Router、应用
## 3. 三节点 Single-Primary 拓扑
## 4. 正常提交时序
## 5. Primary failover 时序
## 6. 固定配置快照与每项理由
## 7. 从空实例建立 Cluster
## 8. Router bootstrap 与应用重连
## 9. 观测成员、队列、flow control 与 Router
## 10. 节点恢复：auto-rejoin、rejoin、Clone／incremental
## 11. 完整 outage reboot
## 12. 八个核心 Scenario 学习顺序
## 13. Compose Lab 与生产故障域的边界
```

The component table must state these negative responsibilities:

- Server／InnoDB does not retry application requests.
- Group Replication does not move existing client connections.
- Shell／AdminAPI is not on the SQL data path.
- Router does not copy data or elect a Primary.
- The application cannot assume failover is connection-transparent.

The normal and failover sequence diagrams must preserve the exact boundaries from the spec. The config snapshot must list:

```text
mysql:8.4.10
community-router:8.4.10
mysql-shell=8.4.10（独立 Oracle Linux tooling image）
communicationStack=MYSQL
consistency=BEFORE_ON_PRIMARY_FAILOVER
exitStateAction=OFFLINE_MODE
autoRejoinTries=3
expelTimeout=5
group_replication_unreachable_majority_timeout=5（仅 Lab）
memberWeight=db1:100,db2:80,db3:60
super_read_only=ON（启动保护）
innodb_flush_log_at_trx_commit=1
sync_binlog=1
```

The guide must say that Router and Shell tooling run as `linux/amd64`; on Apple Silicon their timings include emulation overhead and are behavioral evidence only. It must also separate Lab timing knobs (`expelTimeout=5`, `group_replication_unreachable_majority_timeout=5`) from production tuning decisions.

- [ ] **Step 2: Include exact operational queries**

The guide must explain the owner and interpretation of each field around these runnable queries:

```sql
SELECT MEMBER_HOST, MEMBER_ROLE, MEMBER_STATE
FROM performance_schema.replication_group_members
ORDER BY MEMBER_HOST;

SELECT MEMBER_ID,
       COUNT_TRANSACTIONS_IN_QUEUE,
       COUNT_TRANSACTIONS_CHECKED,
       COUNT_CONFLICTS_DETECTED,
       COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE,
       COUNT_TRANSACTIONS_REMOTE_APPLIED
FROM performance_schema.replication_group_member_stats;

SELECT @@global.group_replication_flow_control_mode,
       @@global.group_replication_flow_control_applier_threshold,
       @@global.group_replication_flow_control_certifier_threshold;

SELECT @@global.group_replication_consistency,
       @@global.group_replication_exit_state_action,
       @@global.group_replication_autorejoin_tries,
       @@global.group_replication_member_expel_timeout,
       @@global.group_replication_unreachable_majority_timeout;
```

The prose must explicitly say that `ONLINE` is necessary but not sufficient; business ledger and member-data equality are separate evidence. For the pinned 8.4 Community baseline, the hard flow-control evidence is the core `COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE` value crossing the active applier threshold while mode is `QUOTA`; do not depend on optional component-specific throttle counters.

- [ ] **Step 3: Write the production Runbook as a decision document**

`production-runbook.md` must contain:

```markdown
# InnoDB Cluster Production Runbook

## 1. Production baseline and failure-domain assumptions
## 2. Pre-deployment checklist
## 3. Build and acceptance
## 4. Daily observability and alert thresholds
## 5. Controlled switchover
## 6. Rolling maintenance and upgrade
## 7. Primary failure with quorum
## 8. Primary partition／repeated expulsion／network flapping
## 9. Quorum loss
## 10. Slow member／flow control
## 11. Router outage
## 12. Member cannot rejoin
## 13. Complete Cluster outage
## 14. Accidental delete／logical corruption／PITR
## 15. Regular drills and evidence retention
```

Every incident section must use this exact shape:

```markdown
### Trigger
### Symptom
### First checks
### Automatic recovery boundary
### Human intervention boundary
### Safe operations
### Operations that risk split-brain or divergence
### Commands
### Success evidence
### Return to normal topology
```

Mandatory safety statements:

```markdown
- Quorum loss is not repaired by letting both partitions accept writes.
- `forceQuorumUsingPartitionOf()` is an explicit disaster decision, not a routine recovery shortcut; first prove all excluded members are fenced.
- `dba.rebootClusterFromCompleteOutage()` runs with `dryRun:true` first and selects a GTID-superset seed; `force:true` is not the default path.
- A rejoining member does not serve traffic until state, backlog and business data are verified.
- Logical corruption is restored to an isolated target from backup plus binlog; it is not fixed by failover.
```

The complete-outage section must include the measured Task 9 drill as supporting Runbook evidence and explicitly state that it is not one of the eight core Scenarios. The PITR section links to core Scenario 08.

- [ ] **Step 4: Add production-only checklists absent from Compose**

Include explicit rows for independent power／host／rack or AZ, DNS and stable addresses, RTT and packet-loss baselines, TLS and certificate rotation, secrets, time sync, disk durability, backup retention, restore drills, capacity headroom, Router placement, application timeout／pool behavior, and escalation ownership. Each row must have `owner`, `check`, `failure consequence`, and `evidence` columns.

- [ ] **Step 5: Verify guide／Runbook coverage and commit**

Run:

```bash
rg -n '^## (1|2|3|4|5|6|7|8|9|10|11|12|13)\.' mysql-handson/09-replication-and-ha/innodb-cluster/README.md
rg -n '^## (1|2|3|4|5|6|7|8|9|10|11|12|13|14|15)\.' mysql-handson/09-replication-and-ha/innodb-cluster/production-runbook.md
rg -n 'BEFORE_ON_PRIMARY_FAILOVER|OFFLINE_MODE|autoRejoinTries|expelTimeout|unreachable_majority_timeout|super_read_only|COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE|flow_control_applier_threshold|forceQuorumUsingPartitionOf|dryRun:true|GTID-superset|isolated' mysql-handson/09-replication-and-ha/innodb-cluster/{README.md,production-runbook.md}
git diff --check
```

Expected: all sections and safety anchors are present; whitespace check is silent.

```bash
git add mysql-handson/09-replication-and-ha/innodb-cluster/README.md mysql-handson/09-replication-and-ha/innodb-cluster/production-runbook.md
git commit -m "docs(mysql-ha): add cluster guide and production runbook"
```

---

### Task 13: 接入章节导航、统一 Make 入口与面试卡

**Files:**
- Modify: `mysql-handson/00-lab/Makefile:1-12,133-138`
- Modify: `mysql-handson/09-replication-and-ha/README.md:704-714`
- Modify: `mysql-handson/README.md:7-52`
- Create: `mysql-handson/99-interview-cards/q-ha-vs-replication.md`
- Create: `mysql-handson/99-interview-cards/q-quorum-and-fencing.md`
- Create: `mysql-handson/99-interview-cards/q-transaction-outcome-unknown.md`
- Create: `mysql-handson/99-interview-cards/q-innodb-cluster-failover.md`

**Interfaces:**
- Consumes: completed docs and measured Scenario paths.
- Produces: canonical discovery path plus `make ha-*` forwarding targets; no duplicate theory in parent README or cards.

- [ ] **Step 1: Add parent Makefile forwarding targets without changing existing targets**

Append to `mysql-handson/00-lab/Makefile`:

```makefile
.PHONY: ha-config ha-up ha-down ha-reset ha-status ha-test ha-verify ha-scenario

ha-config:
	$(MAKE) -C ha config

ha-up:
	$(MAKE) -C ha up

ha-down:
	$(MAKE) -C ha down

ha-reset:
	$(MAKE) -C ha reset

ha-status:
	$(MAKE) -C ha status

ha-test:
	$(MAKE) -C ha test

ha-verify:
	$(MAKE) -C ha verify

ha-scenario:
	$(MAKE) -C ha scenario SCENARIO=$${SCENARIO:?set SCENARIO}
```

Add matching one-line help entries, but do not rename `up`, `up-replica`, `replica-setup`, `chaos-*`, or their resources.

- [ ] **Step 2: Add compact Chapter 09 navigation**

Append after the existing three traditional replication Scenario links:

```markdown
## InnoDB Cluster 高可用专题

这条专题不再重复异步／半同步复制，而是从「客户端收到成功究竟承诺什么」进入完整 HA：

1. [产品无关的 HA 基础](ha-foundations.md)
2. [MySQL 8.4 InnoDB Cluster 主线](innodb-cluster/README.md)
3. [Production Runbook](innodb-cluster/production-runbook.md)
4. [8 个核心 Scenario](innodb-cluster/scenarios/01-planned-switchover.md)

主线固定为 3 成员 Single-Primary＋双 Router。MHA／旧 Orchestrator 只保留历史机制与失败反例；PXC 只有在主线完成后的机制缺口评估通过时，才进入独立设计。
```

- [ ] **Step 3: Update the root MySQL learning map and quick commands**

Change the Chapter 09 map row to mention both the three existing replication scenarios and the new eight-scenario HA track. Add this block to `Lab 速查`:

```bash
make ha-up                                    # 独立 MySQL 8.4 三成员 Cluster＋双 Router
make ha-status / make ha-verify               # 拓扑状态／客户端与成员数据对账
make ha-scenario SCENARIO=primary-crash       # 独立 reset 后运行一个 HA Scenario
make ha-reset                                 # 只删除 mysql-ha project 的容器与 volumes
```

- [ ] **Step 4: Create four compact evidence-linked interview cards**

Every card uses the existing structure `一句话回答 → 要点 → 证据链接 → 易追问的延伸`. Use these exact one-sentence answers:

```markdown
# q-ha-vs-replication.md
复制回答「数据怎么到另一台」，HA 还必须回答故障检测、quorum、选主、fencing、连接重建、业务结果与恢复；有副本不等于系统已经高可用。

# q-quorum-and-fencing.md
三节点用 2/3 多数派保证只有一个可继续决策的分区，fencing 再让失去资格的旧 Primary 不可写；只有选主没有 fencing，仍可能形成双写。

# q-transaction-outcome-unknown.md
SQL 已发出但成功响应丢失时，事务可能提交也可能未提交；应用必须用原 `request_id` 查明并保持幂等，不能把超时直接当失败生成新业务操作。

# q-innodb-cluster-failover.md
Group Replication 完成成员视图与 Primary 选举，`BEFORE_ON_PRIMARY_FAILOVER` 挡住新 Primary 直到 backlog 处理完成，Router 更新新连接目标，应用负责丢弃旧连接并重连。
```

Each card must link to one theory anchor, one product-guide anchor and at least one measured Scenario; no card may copy a full command sequence.

- [ ] **Step 5: Verify all navigation and forwarding targets**

Run:

```bash
make -C mysql-handson/00-lab ha-config
rg -n 'ha-foundations|innodb-cluster/README|production-runbook|8 个核心|PXC' mysql-handson/09-replication-and-ha/README.md
rg -n 'ha-up|ha-status|ha-verify|ha-scenario|ha-reset' mysql-handson/{README.md,00-lab/Makefile}
rg -n '^## 一句话回答$|^## 要点$|^## 证据链接$|^## 易追问的延伸$' mysql-handson/99-interview-cards/q-{ha-vs-replication,quorum-and-fencing,transaction-outcome-unknown,innodb-cluster-failover}.md
git diff --check
```

Expected: Compose config exits `0`; all links／targets／card sections are found; existing Primary／Replica commands remain unchanged; whitespace check is silent.

- [ ] **Step 6: Commit**

```bash
git add mysql-handson/00-lab/Makefile mysql-handson/09-replication-and-ha/README.md mysql-handson/README.md mysql-handson/99-interview-cards/q-ha-vs-replication.md mysql-handson/99-interview-cards/q-quorum-and-fencing.md mysql-handson/99-interview-cards/q-transaction-outcome-unknown.md mysql-handson/99-interview-cards/q-innodb-cluster-failover.md
git commit -m "docs(mysql-ha): integrate learning path and interview cards"
```

---

### Task 14: 全量验证、完成标准审计与第二方案 gate

**Files:**
- Create: `mysql-handson/00-lab/ha/verify-static.sh`
- Create: `mysql-handson/00-lab/ha/tests/test_links.py`
- Modify: `mysql-handson/09-replication-and-ha/innodb-cluster/README.md`

**Interfaces:**
- Consumes: all previous tasks from a clean worktree and empty `mysql-ha` volumes.
- Produces: static checks, eight independent green core Scenario runs, one separately named complete-outage recovery drill, a requirement-by-requirement audit, and an explicit PXC gate result without implementing PXC.

- [ ] **Step 1: Add a relative-link test scoped to the new track**

```python
# mysql-handson/00-lab/ha/tests/test_links.py
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[4]
TRACK = REPO / "mysql-handson/09-replication-and-ha"
FILES = [
    TRACK / "ha-foundations.md",
    TRACK / "innodb-cluster/README.md",
    TRACK / "innodb-cluster/production-runbook.md",
    *sorted((TRACK / "innodb-cluster/scenarios").glob("*.md")),
]


class LinkTest(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        missing = []
        for source in FILES:
            text = source.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", text):
                if "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (source.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{source.relative_to(REPO)} -> {target}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add one static verification entrypoint**

```bash
#!/usr/bin/env bash
# mysql-handson/00-lab/ha/verify-static.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../../.." && pwd)"

docker compose --project-name mysql-ha --file "$ROOT/compose.yml" config --quiet
for script in "$ROOT"/faults/*.sh "$ROOT"/scenarios/*.sh; do bash -n "$script"; done
PYTHONPATH="$ROOT" python3 -m unittest discover -s "$ROOT/tests" -v
if rg -n 'T[B]D|T[O]DO|待[补]|待[跑]真值|place[holder]' \
  "$REPO/mysql-handson/09-replication-and-ha/ha-foundations.md" \
  "$REPO/mysql-handson/09-replication-and-ha/innodb-cluster"; then
  echo "unfinished marker found" >&2
  exit 1
fi
git -C "$REPO" diff --check
```

Run:

```bash
chmod +x mysql-handson/00-lab/ha/verify-static.sh
mysql-handson/00-lab/ha/verify-static.sh
```

Expected: Compose and all Bash syntax checks pass; every unit／link test passes; the unfinished-marker scan has no matches; `git diff --check` is silent.

- [ ] **Step 3: Run eight core Scenarios and the supporting recovery drill from independent clean state**

Run:

```bash
make -C mysql-handson/00-lab/ha scenario SCENARIO=planned-switchover
make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-crash
make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-partition
make -C mysql-handson/00-lab/ha scenario SCENARIO=quorum-loss
make -C mysql-handson/00-lab/ha scenario SCENARIO=slow-member
make -C mysql-handson/00-lab/ha scenario SCENARIO=router-failure
make -C mysql-handson/00-lab/ha scenario SCENARIO=member-rejoin
make -C mysql-handson/00-lab/ha scenario SCENARIO=ha-cannot-replace-pitr
make -C mysql-handson/00-lab/ha recovery-complete-outage
```

Expected: every command exits `0`. Core runs 01–07 finish with one Primary, 3 ONLINE members and zero missing acknowledged requests; run 04 has zero SUCCESS for requests begun after `fault_active` and completed before `quorum_restore_begin`; run 06 has Router B success during Router A outage. Core run 08 proves the delete reached all three members while the isolated recovery instance restores `pitr-keep` before the delete boundary. The separately named complete-outage drill preserves the exact pre-outage business ID set and is not counted as a ninth Scenario.

- [ ] **Step 4: Audit every approved completion criterion**

Add a `完成标准审计` table to `innodb-cluster/README.md` with one row for each spec criterion and these columns:

```markdown
| Criterion | Evidence command／file | Result |
|---|---|---|
```

There must be rows for clean build, independent reset, segmented RTO, acknowledged writes, unknown reconciliation, minority fencing, quorum loss, Router failover, rejoin, complete outage, PITR, documented Runbook, learner explanation exercise, and physical-failure boundary. Every Result must be backed by a command or measured Scenario path; a failed criterion blocks completion.

- [ ] **Step 5: Apply the PXC gate without expanding scope**

Append a `第二方案评估 gate` section using this deterministic rubric:

```markdown
| Candidate gap／condition | Evidence required | Rule for `Yes` |
|---|---|---|
| Galera commit／certification semantics | 指出主方案的提交证据无法回答的具体选型问题 | 缺口关联已完成 Scenario，且会改变真实选型 |
| Multi-primary conflict semantics | 指出单 Primary 主线无法回答的具体写入约束 | 缺口可用同一业务 invariant 验证，且不是追求功能数量 |
| SST／IST recovery semantics | 指出 Clone／incremental 恢复证据无法回答的具体恢复约束 | 缺口关联 RTO、运维风险或容量决策 |
| 同一 workload、故障模型与 verifier 能否公平复用？ | 列出无需改语义即可复用的接口 | 请求三态、故障窗口与最终数据断言都无需降级 |
| 新方案的学习收益是否大于部署、恢复、维护成本？ | 给出新增任务数量和预期决策收益 | 新增实验能回答当前证据无法回答的选型问题 |
```

After reviewing the completed evidence, add an explicit `Result` (`Yes` or `No`) and an `Observed evidence` value to every row; empty or conditional results fail the gate. Opening a new PXC brainstorming／design session requires all of the following: at least two of the three mechanism-gap rows are concrete, important, independently verifiable `Yes`; interface reuse is `Yes`; and learning benefit exceeds cost. Otherwise this implementation stops at an architecture comparison. This task must not add PXC Compose files or commands.

- [ ] **Step 6: Verify change scope and commit final audit tooling**

Run:

```bash
plan_base="$(git log -n1 --format=%H --grep='^docs(mysql): plan InnoDB Cluster HA track$')"
test -n "$plan_base"
git diff --name-only "$plan_base"..HEAD
git diff "$plan_base"..HEAD --check
git status --short
```

Expected: changed files after the committed plan are limited to the design-approved HA Lab, Chapter 09 HA track, four cards, MySQL navigation, parent Lab Makefile, and `.gitignore`; no existing `00-lab/docker-compose.yml` or traditional replication Scenario changed. The worktree is otherwise clean inside the isolated worktree.

```bash
git add mysql-handson/00-lab/ha/verify-static.sh mysql-handson/00-lab/ha/tests/test_links.py mysql-handson/09-replication-and-ha/innodb-cluster/README.md
git commit -m "test(mysql-ha): audit complete HA learning track"
```

---

## Official References Used by the Plan

- [MySQL 8.4 InnoDB Cluster setup](https://dev.mysql.com/doc/mysql-shell/8.4/en/setting-up-innodb-cluster-and-mysql-router.html)
- [InnoDB Cluster requirements](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster-requirements.html)
- [Failover consistency](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-innodb-cluster-failover-consistency.html)
- [Automatic rejoin and exit state](https://dev.mysql.com/doc/mysql-shell/8.4/en/configuring-automatic-rejoin-of-instances.html)
- [Rejoining an instance](https://dev.mysql.com/doc/mysql-shell/8.4/en/rejoin-cluster.html)
- [Complete-outage reboot](https://dev.mysql.com/doc/mysql-shell/8.4/en/reboot-outage.html)
- [Install MySQL Shell on Linux](https://dev.mysql.com/doc/mysql-shell/8.4/en/mysql-shell-install-linux-quick.html)
- [Router Docker variables](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-installation-docker.html)
- [Router bootstrap](https://dev.mysql.com/doc/mysql-shell/8.4/en/admin-api-bootstrapping-router.html)
- [Router connection handling configuration](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-conf-options.html)
- [Router metadata and destination changes](https://dev.mysql.com/doc/mysql-router/8.4/en/mysql-router-general-metadata.html)
- [Group Replication flow control](https://dev.mysql.com/doc/refman/8.4/en/group-replication-flow-control.html)
- [Group Replication member statistics table](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-group-member-stats-table.html)
- [Group Replication failure exit action](https://dev.mysql.com/doc/refman/8.4/en/group-replication-responses-failure-exit.html)
- [Group Replication system variables](https://dev.mysql.com/doc/refman/8.4/en/group-replication-system-variables.html)
- [Point-in-time recovery using binary log](https://dev.mysql.com/doc/refman/8.4/en/point-in-time-recovery-binlog.html)
- [MySQL official image 8.4.10](https://hub.docker.com/_/mysql/tags?name=8.4.10)
