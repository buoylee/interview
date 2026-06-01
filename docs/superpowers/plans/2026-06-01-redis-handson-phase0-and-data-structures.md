# Redis Hands-on Phase 0 (Lab) + Phase 1 (02-data-structures) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建起 `interview/redis-handson/` 的可重跑 Redis 7.4 实验环境(Phase 0),并完整写出第一章 `02-data-structures`(编码转换 scenario + 7 段笔记 + 面试卡),作为后续 12 章的范式样板。

**Architecture:** lab 在 `00-lab/`(Docker compose,单机默认 + cluster/sentinel/obs/ui 各自 profile),所有 scenario 通过 `make` 目标引用 lab,不把 compose 抄进每个 scenario。章节 README 走固定 7 段;scenario 走「预期(留空格给学习者)→ 跑 → 实机 → ⚠️落差」纪律;面试卡反向链接回 scenario。

**Tech Stack:** Redis 7.4、redis-cli、Lua、Docker Compose、redis_exporter + Prometheus + Grafana、toxiproxy、RedisInsight、GNU Make。

参考 spec:`docs/superpowers/specs/2026-06-01-redis-handson-design.md`
参考范式:`docs/superpowers/plans/2026-05-13-mysql-handson-phase0-and-indexing.md`

---

## File Structure

Phase 0 + Phase 1 会创建/修改以下文件:

```
interview/redis-handson/
├── README.md                         ← 入口(Task 13)
├── 00-lab/
│   ├── docker-compose.yml            ← single(默认) + cluster/sentinel/obs/ui profile(Task 2,7,8,9,11)
│   ├── conf/redis.conf               ← 单机预配观测参数(Task 3)
│   ├── conf/redis-cluster.conf       ← cluster 节点模板(Task 8)
│   ├── conf/sentinel.conf            ← 哨兵配置(Task 9)
│   ├── init/gen-keys.sh              ← 造大量/大/热 key(Task 6)
│   ├── cluster/create-cluster.sh     ← cluster create 脚本(Task 8)
│   ├── prometheus.yml                ← (Task 8)
│   ├── grafana/                      ← 匿名 viewer + redis 面板(Task 8)
│   └── Makefile                      ← 全部 make 目标(Task 4,6,8,9,10,11)
├── 01-execution-model/README.md      ← stub(Task 1)
├── 02-data-structures/
│   ├── README.md                     ← 完整 7 段(Task 14)
│   └── scenarios/
│       ├── 01-hash-listpack-to-hashtable.md   (Task 15-16)
│       ├── 02-zset-listpack-to-skiplist.md     (Task 17-18)
│       ├── 03-string-int-embstr-raw.md         (Task 19-20)
│       └── 04-set-intset-listpack-hashtable.md (Task 21-22)
├── 03..13/README.md                  ← stub(Task 1)
├── 99-interview-cards/
│   └── q-redis-encoding-transitions.md         (Task 23)
└── templates/scenario-template.md    ← (Task 12)
```

## Cross-cutting conventions

- **容器名固定**:单机 `redis`,cluster 节点 `redis-node-1..6`,哨兵 `redis-sn-1..3` + 主从 `redis-m`/`redis-r1`/`redis-r2`。
- **所有 redis-cli 通过容器执行**:`docker compose exec redis redis-cli ...`,Makefile 已封装。
- **提交粒度**:每个 scenario 分两次 commit(先 prediction,后实机),与纪律一致。配置类 task 各自一次 commit。
- **版本标注**:涉及 7.0(listpack 取代 ziplist、FUNCTION)、7.2(set 引入 listpack 编码)、6.0(io-threads)差异时,章内小节标注。
- **commit message 前缀**:`redis-handson:`。

---

## Phase 0 — Lab + Scaffolding (Tasks 1-13)

### Task 1: 建目录骨架 + stub 章节 README

**Files:**
- Create: `redis-handson/01-execution-model/README.md` ... `redis-handson/13-rate-limiting/README.md`(13 个 stub)
- Create: `redis-handson/99-interview-cards/.gitkeep`、`redis-handson/00-lab/.gitkeep`、`redis-handson/templates/.gitkeep`

- [ ] **Step 1: 建目录与 stub**

```bash
cd interview/redis-handson
for d in 01-execution-model 02-data-structures 03-advanced-types 04-expiry-eviction \
         05-persistence 06-caching-patterns 07-distributed-locks 08-transactions-scripting \
         09-pubsub-streams-mq 10-replication-sentinel 11-cluster 12-production-ops 13-rate-limiting; do
  mkdir -p "$d/scenarios"
  printf '# %s\n\n> 待写。占位,保持章节顺序。\n' "$d" > "$d/README.md"
done
mkdir -p 00-lab/conf 00-lab/init 00-lab/cluster 00-lab/grafana 99-interview-cards templates
touch 99-interview-cards/.gitkeep templates/.gitkeep
```

- [ ] **Step 2: 验证目录结构**

Run: `find redis-handson -maxdepth 2 -name README.md | sort`
Expected: 列出 13 个章节 README。

- [ ] **Step 3: Commit**

```bash
git add redis-handson && git commit -m "redis-handson: 目录骨架 + 13 章 stub README"
```

---

### Task 2: 写单机 docker-compose.yml(只起 redis)

**Files:**
- Create: `redis-handson/00-lab/docker-compose.yml`

- [ ] **Step 1: 写 compose(单机 service)**

```yaml
# 默认只起单机 redis;cluster / sentinel / obs / ui 在后续 task 以 profile 追加。
services:
  redis:
    image: redis:7.4
    container_name: redis
    command: ["redis-server", "/etc/redis/redis.conf"]
    ports: ["6379:6379"]
    volumes:
      - ./conf/redis.conf:/etc/redis/redis.conf:ro
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 3s
      retries: 10

volumes:
  redis-data:
```

- [ ] **Step 2: Commit**

```bash
git add redis-handson/00-lab/docker-compose.yml
git commit -m "redis-handson: 00-lab 单机 compose"
```

---

### Task 3: 写单机 redis.conf(预配观测参数)

**Files:**
- Create: `redis-handson/00-lab/conf/redis.conf`

- [ ] **Step 1: 写 conf**

```conf
# ---- 网络 ----
bind 0.0.0.0
protected-mode no            # lab 内网,12 章安全 scenario 再开
port 6379

# ---- 内存 / 淘汰(04 章 scenario 会改 policy)----
maxmemory 256mb
maxmemory-policy noeviction

# ---- 持久化(05 章 scenario 会切 always / 关 aof 对比)----
appendonly yes
appendfsync everysec
save 60 1000

# ---- 慢查询(12 章)----
slowlog-log-slower-than 10000   # 10ms
slowlog-max-len 128

# ---- 延迟监控(12 章 LATENCY DOCTOR)----
latency-monitor-threshold 100

# ---- 编码转换阈值(02 章 scenario 直接调,这里放默认值便于对照)----
hash-max-listpack-entries 128
hash-max-listpack-value 64
list-max-listpack-size 128
set-max-intset-entries 512
set-max-listpack-entries 128
set-max-listpack-value 64
zset-max-listpack-entries 128
zset-max-listpack-value 64

# ---- io-threads(01 章 scenario 切换;默认 1 表示单 IO 线程)----
io-threads 1

# ---- 键空间通知(03/09 章)----
notify-keyspace-events ""
```

- [ ] **Step 2: Commit**

```bash
git add redis-handson/00-lab/conf/redis.conf
git commit -m "redis-handson: 单机 redis.conf 观测参数预配"
```

---

### Task 4: 写 Makefile 基础(up/down/reset/cli/ps/logs)

**Files:**
- Create: `redis-handson/00-lab/Makefile`

- [ ] **Step 1: 写 Makefile 基础段**

```makefile
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
```

- [ ] **Step 2: Commit**

```bash
git add redis-handson/00-lab/Makefile
git commit -m "redis-handson: Makefile 基础(up/down/reset/cli)"
```

---

### Task 5: 起 lab,验证单机可用

**Files:** 无(验证 task)

- [ ] **Step 1: 起 lab**

Run: `cd redis-handson/00-lab && make up`
Expected: 末行 `redis healthy on :6379`。

- [ ] **Step 2: 验证 PING + 版本**

Run: `docker compose exec redis redis-cli PING && docker compose exec redis redis-cli INFO server | grep redis_version`
Expected: `PONG` 且 `redis_version:7.4.x`。

- [ ] **Step 3: 验证编码参数已加载**

Run: `docker compose exec redis redis-cli CONFIG GET hash-max-listpack-entries`
Expected: `1) "hash-max-listpack-entries" 2) "128"`。

- [ ] **Step 4: 关掉(不删数据)**

Run: `make down`
Expected: 容器停止。(本 task 无 commit。)

---

### Task 6: 加造数据脚本 + `make load`(为编码/淘汰/大key scenario 备料)

**Files:**
- Create: `redis-handson/00-lab/init/gen-keys.sh`
- Modify: `redis-handson/00-lab/Makefile`(追加 load 段)

- [ ] **Step 1: 写造 key 脚本**

```bash
#!/usr/bin/env sh
# Usage: 在容器内跑。N=要造的普通 key 数量(默认 100000)
N="${N:-100000}"
echo "generating $N string keys via pipe..."
{
  i=0
  while [ "$i" -lt "$N" ]; do
    printf 'SET key:%s val:%s\n' "$i" "$i"
    i=$((i+1))
  done
} | redis-cli --pipe
# 造一个大 hash(给 12 章 bigkeys)
redis-cli del bighash >/dev/null
{ i=0; while [ "$i" -lt 50000 ]; do printf 'HSET bighash f%s v%s\n' "$i" "$i"; i=$((i+1)); done; } | redis-cli --pipe
echo "done. dbsize=$(redis-cli dbsize)"
```

- [ ] **Step 2: 追加 Makefile load 目标**

```makefile
.PHONY: load
# Usage: make load N=100000
load:
	docker compose cp init/gen-keys.sh redis:/tmp/gen-keys.sh
	docker compose exec -e N=$${N:-100000} redis sh /tmp/gen-keys.sh
```

- [ ] **Step 3: 验证**

Run: `make up && make load N=10000`
Expected: 末行 `done. dbsize=10001`(10000 string + bighash)。

- [ ] **Step 4: Commit**

```bash
git add redis-handson/00-lab/init/gen-keys.sh redis-handson/00-lab/Makefile
git commit -m "redis-handson: 造数据脚本 + make load"
```

---

### Task 7: 加观测 helper(slowlog/latency/bigkeys/encoding/mem/info/bench/monitor)

**Files:**
- Modify: `redis-handson/00-lab/Makefile`(追加观测段)

- [ ] **Step 1: 追加观测目标**

```makefile
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
```

- [ ] **Step 2: 验证 encoding helper**

Run: `make up && make load N=1000 && make encoding K=bighash`
Expected: `hashtable`(50000 字段远超 128 阈值)。

- [ ] **Step 3: Commit**

```bash
git add redis-handson/00-lab/Makefile
git commit -m "redis-handson: 观测 helper(encoding/mem/slowlog/latency/bigkeys/bench)"
```

---

### Task 8: 加 cluster(6 节点 3主3从)+ toxiproxy + 观测栈,均为 profile

**Files:**
- Create: `redis-handson/00-lab/conf/redis-cluster.conf`
- Create: `redis-handson/00-lab/cluster/create-cluster.sh`
- Create: `redis-handson/00-lab/prometheus.yml`
- Modify: `redis-handson/00-lab/docker-compose.yml`(追加 cluster/obs/toxiproxy services + profiles)
- Modify: `redis-handson/00-lab/Makefile`(追加 up-cluster/cluster-init/cli-cluster/up-obs/chaos-*)

- [ ] **Step 1: cluster 节点 conf 模板**

```conf
# conf/redis-cluster.conf — 6 个节点共用,端口由 command 覆盖
cluster-enabled yes
cluster-config-file nodes.conf
cluster-node-timeout 5000
appendonly yes
protected-mode no
```

- [ ] **Step 2: cluster create 脚本**

```bash
#!/usr/bin/env sh
# 在 redis-node-1 容器内执行:用 6 个节点建 3主3从
redis-cli --cluster create \
  redis-node-1:6379 redis-node-2:6379 redis-node-3:6379 \
  redis-node-4:6379 redis-node-5:6379 redis-node-6:6379 \
  --cluster-replicas 1 --cluster-yes
```

- [ ] **Step 3: prometheus.yml**

```yaml
global:
  scrape_interval: 5s
scrape_configs:
  - job_name: redis
    static_configs:
      - targets: ['redis_exporter:9121']
```

- [ ] **Step 4: 追加 compose services(cluster + toxiproxy + obs)**

```yaml
  # ---- cluster profile: 6 节点 ----
  redis-node-1: &cnode
    image: redis:7.4
    command: ["redis-server", "/etc/redis/redis.conf"]
    volumes: ["./conf/redis-cluster.conf:/etc/redis/redis.conf:ro"]
    profiles: ["cluster"]
    container_name: redis-node-1
    ports: ["7001:6379"]
  redis-node-2:
    <<: *cnode
    container_name: redis-node-2
    ports: ["7002:6379"]
  redis-node-3:
    <<: *cnode
    container_name: redis-node-3
    ports: ["7003:6379"]
  redis-node-4:
    <<: *cnode
    container_name: redis-node-4
    ports: ["7004:6379"]
  redis-node-5:
    <<: *cnode
    container_name: redis-node-5
    ports: ["7005:6379"]
  redis-node-6:
    <<: *cnode
    container_name: redis-node-6
    ports: ["7006:6379"]

  # ---- chaos ----
  toxiproxy:
    image: ghcr.io/shopify/toxiproxy:2.9.0
    container_name: toxiproxy
    profiles: ["cluster", "sentinel"]
    ports: ["8474:8474"]

  # ---- obs profile ----
  redis_exporter:
    image: oliver006/redis_exporter:v1.62.0
    container_name: redis_exporter
    command: ["--redis.addr=redis://redis:6379"]
    profiles: ["obs"]
    ports: ["9121:9121"]
  prometheus:
    image: prom/prometheus:v2.54.1
    container_name: prometheus
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
    profiles: ["obs"]
    ports: ["9090:9090"]
  grafana:
    image: grafana/grafana:11.2.0
    container_name: grafana
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
    profiles: ["obs"]
    ports: ["3000:3000"]
```

- [ ] **Step 5: 追加 Makefile cluster/obs/chaos 目标**

```makefile
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

# Usage: make chaos-lag MS=500  (在 cluster 节点间注入延迟,需先建 toxiproxy 代理 — 见 10/11 章 scenario)
chaos-lag:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t latency -a latency=$${MS:-500} -n lag node-link || true

chaos-cut:
	docker compose exec toxiproxy /toxiproxy-cli toxic add -t timeout -a timeout=0 -n cut node-link || true

chaos-restore:
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n lag node-link
	-docker compose exec toxiproxy /toxiproxy-cli toxic remove -n cut node-link
```

- [ ] **Step 6: 验证 cluster 起得来**

Run: `make up-cluster && sleep 3 && make cluster-init`
Expected: 输出含 `[OK] All 16384 slots covered.`

- [ ] **Step 7: 验证 cluster 路由**

Run: `docker compose exec redis-node-1 redis-cli -c set foo bar && docker compose exec redis-node-1 redis-cli -c cluster info | grep cluster_state`
Expected: `cluster_state:ok`(set 可能伴随一次 `-> Redirected to slot`)。

- [ ] **Step 8: 收掉 cluster**

Run: `make down-cluster`

- [ ] **Step 9: Commit**

```bash
git add redis-handson/00-lab
git commit -m "redis-handson: cluster(3主3从)+ toxiproxy + obs 栈(profile)"
```

---

### Task 9: 加 sentinel profile(1主2从 + 3 哨兵)

**Files:**
- Create: `redis-handson/00-lab/conf/sentinel.conf`
- Modify: `redis-handson/00-lab/docker-compose.yml`(追加 sentinel services)
- Modify: `redis-handson/00-lab/Makefile`(追加 up-sentinel)

- [ ] **Step 1: sentinel.conf**

```conf
sentinel resolve-hostnames yes
sentinel monitor mymaster redis-m 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
```

- [ ] **Step 2: 追加 compose sentinel services**

```yaml
  # ---- sentinel profile: 1 主 2 从 + 3 哨兵 ----
  redis-m:
    image: redis:7.4
    container_name: redis-m
    command: ["redis-server", "--appendonly", "yes"]
    profiles: ["sentinel"]
  redis-r1: &replica
    image: redis:7.4
    container_name: redis-r1
    command: ["redis-server", "--replicaof", "redis-m", "6379"]
    profiles: ["sentinel"]
    depends_on: ["redis-m"]
  redis-r2:
    <<: *replica
    container_name: redis-r2
  redis-sn-1: &sentinel
    image: redis:7.4
    container_name: redis-sn-1
    command: ["redis-sentinel", "/etc/redis/sentinel.conf"]
    volumes: ["./conf/sentinel.conf:/etc/redis/sentinel.conf"]
    profiles: ["sentinel"]
    depends_on: ["redis-m"]
  redis-sn-2:
    <<: *sentinel
    container_name: redis-sn-2
  redis-sn-3:
    <<: *sentinel
    container_name: redis-sn-3
```

> 注:sentinel 会写自己的 conf,volume 不能用 `:ro`。每个哨兵共用同一份初始 conf,启动后各自改写。

- [ ] **Step 3: 追加 Makefile**

```makefile
.PHONY: up-sentinel down-sentinel sentinel-status

up-sentinel:
	docker compose --profile sentinel up -d
	@echo "1 master + 2 replicas + 3 sentinels up."

down-sentinel:
	docker compose --profile sentinel down

sentinel-status:
	docker compose exec redis-sn-1 redis-cli -p 26379 sentinel master mymaster
```

> 注:redis-sentinel 默认监听 26379。compose 内服务互通无需映射端口;需要本机访问时再加 `ports`。

- [ ] **Step 4: 验证主从 + 哨兵感知**

Run: `make up-sentinel && sleep 6 && docker compose exec redis-m redis-cli info replication | grep connected_slaves`
Expected: `connected_slaves:2`。

Run: `docker compose exec redis-sn-1 redis-cli -p 26379 sentinel master mymaster | head -4`
Expected: 输出含 `mymaster` 与 `redis-m` 的 ip/port。

- [ ] **Step 5: 收掉**

Run: `make down-sentinel`

- [ ] **Step 6: Commit**

```bash
git add redis-handson/00-lab
git commit -m "redis-handson: sentinel profile(1主2从+3哨兵)"
```

---

### Task 10: 加 RedisInsight(ui profile)

**Files:**
- Modify: `redis-handson/00-lab/docker-compose.yml`(追加 redisinsight)
- Modify: `redis-handson/00-lab/Makefile`(追加 up-ui)

- [ ] **Step 1: 追加 compose**

```yaml
  redisinsight:
    image: redis/redisinsight:2.58
    container_name: redisinsight
    profiles: ["ui"]
    ports: ["5540:5540"]
```

- [ ] **Step 2: 追加 Makefile**

```makefile
.PHONY: up-ui down-ui
up-ui:
	docker compose --profile ui up -d
	@echo "RedisInsight: http://localhost:5540 (add db host=redis port=6379)"
down-ui:
	docker compose --profile ui stop
```

- [ ] **Step 3: 验证**

Run: `make up-ui && sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://localhost:5540`
Expected: `200`(或 `301`/`302`,服务起来即可)。

- [ ] **Step 4: Commit**

```bash
git add redis-handson/00-lab
git commit -m "redis-handson: RedisInsight(ui profile)"
```

---

### Task 11: 写 scenario 模板

**Files:**
- Create: `redis-handson/templates/scenario-template.md`

- [ ] **Step 1: 写模板**

````markdown
# Scenario: <一句话描述>

## 我想验证的问题

<一句话。例:「同一个 hash,字段数从 128 涨到 129 时 OBJECT ENCODING 会不会从 listpack 变 hashtable?」>

## 预期(写实验前的假设)

> **请在跑 lab 之前填这一段**。基于章节 README 教过的规则(不要查),把下列空格填上,写完单独 commit 一次("prediction only"),再开始跑。
>
> - 我以为触发条件是 _____,转换后编码变成 _____。
> - 我以为内存/性能会 _____。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab:`make up`(cluster scenario 用 `make up-cluster && make cluster-init`)
- 造数据:`make load N=<N>`(如适用)

## 步骤

1. ...
2. ...

## 实机告诉我(跑完当天填)

```
<贴 redis-cli 输出 / INFO 片段 / SLOWLOG / LATENCY 报告>
```

观察到的关键事实:

- ...

## ⚠️ 预期 vs 实机落差

<这是核心输出。完全对应预期 = scenario 太简单或预期太模糊。>

- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡

- `99-interview-cards/q-xxx.md`
````

- [ ] **Step 2: Commit**

```bash
git add redis-handson/templates/scenario-template.md
git commit -m "redis-handson: scenario 模板"
```

---

### Task 12: 写顶层 README

**Files:**
- Create: `redis-handson/README.md`

- [ ] **Step 1: 写 README**

````markdown
# Redis Hands-on — 系统笔记 + 实机白皮书

把 `interview/redis/` 的零散面试理论在实机上重新跑过一遍,沉淀成有结构的 scenario + 章节笔记 + 面试卡。**目标:从「会背」升级到「会用 + 知其所以然」。**

设计来源:`docs/superpowers/specs/2026-06-01-redis-handson-design.md`
目标版本:Redis 7.4。

## 怎么用这个 repo

1. **第一次来**:`cd 00-lab && make up`,等到 `redis healthy`。`make cli` 进 redis-cli 看到提示符就 OK。想要图形界面 `make up-ui` 开 http://localhost:5540。
2. **想学某主题**:从章节 README 开始,每章固定 7 段(核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 调优实战 / 面试高频考点 / 一句话总结)。
3. **想答某面试题**:去 `99-interview-cards/` 找卡,每张卡链回 scenario 当证据。
4. **想加 scenario**:复制 `templates/scenario-template.md` 到对应章节 `scenarios/`,**先写「预期」、commit 一次**,再跑、再 commit 观察结果。

## 客户端语言约定

- **原理 / 运维 / 排查**:`redis-cli` + `redis.conf` + Lua(语言无关)。
- **应用模式(锁/限流/缓存重建)**:Java/Redisson 为主 + redis-py 对照镜像。

## 章节地图

- `01-execution-model/` — 单线程 + epoll + io-threads + 什么命令会卡
- `02-data-structures/` — 5 类型 + 底层编码 + OBJECT ENCODING 实测 + 选型决策表 ← **第一个完整章节**
- `03-advanced-types/` — bitmap / HyperLogLog / GEO / Stream / bitfield
- `04-expiry-eviction/` — 惰性+定期删除 + 8 淘汰策略 + LRU/LFU
- `05-persistence/` — RDB / AOF / 混合 + 丢数据边界
- `06-caching-patterns/` — 缓存模式 + 一致性 + 穿透击穿雪崩 ★
- `07-distributed-locks/` — SETNX+Lua / Redisson 看门狗 / RedLock 争议
- `08-transactions-scripting/` — MULTI/WATCH / Lua / pipeline / FUNCTION
- `09-pubsub-streams-mq/` — pub/sub vs List vs Stream 当 MQ
- `10-replication-sentinel/` — psync / 复制积压 / 哨兵故障转移 / 脑裂
- `11-cluster/` — 槽 / CRC16 / MOVED&ASK / reshard / 故障转移
- `12-production-ops/` — 大key / 热key / SLOWLOG / 延迟毛刺 / 连接池 ★
- `13-rate-limiting/` — 固定/滑动窗口 / 令牌桶 / RRateLimiter
- `99-interview-cards/` — 反向产出的面试题答案卡

## Lab 速查

```bash
cd 00-lab
make up / down / reset                 # 单机生命周期
make cli                               # redis-cli
make load N=100000                     # 造 key
make encoding K=mykey                  # OBJECT ENCODING
make mem K=mykey                       # MEMORY USAGE
make slowlog / latency / bigkeys       # 观测
make up-cluster && make cluster-init   # 3主3从 + cli-cluster
make up-sentinel                       # 1主2从 + 3 哨兵
make up-obs                            # exporter + Prometheus + Grafana
make up-ui                             # RedisInsight
make chaos-lag MS=500 / chaos-restore  # toxiproxy 注入
```

## 纪律

1. **「预期」必须在跑之前写**,且单独 commit 一次。预期被实机污染就学不到东西了。
2. **「实机告诉我」当天填**。隔天就忘了当下的惊讶点。
3. **「⚠️ 预期 vs 实机落差」是这个方法的核心输出**。每个 scenario 都「完全对应预期」说明 scenario 太简单或预期太模糊。
````

- [ ] **Step 2: Commit**

```bash
git add redis-handson/README.md
git commit -m "redis-handson: 顶层 README(导航+lab速查+纪律)"
```

---

## Phase 1 — 02-data-structures 章节完整 (Tasks 13-23)

### Task 13: 写 02-data-structures/README.md 七段骨架(含完整原理)

**Files:**
- Modify: `redis-handson/02-data-structures/README.md`(替换 stub)

- [ ] **Step 1: 写完整 README**(七段,关键表格 inline)

````markdown
# 数据结构与底层编码（Data Structures & Encodings）

## 1. 核心问题

Redis 对外是 5 个基础类型（String/List/Hash/Set/ZSet），但每个类型底层**根据数据规模选不同编码**。本章解决三件事：
**(a)** 每个类型有哪些底层编码、各自的数据结构；
**(b)** 编码在什么阈值下、朝哪个方向转换（为什么不可逆）；
**(c)** 写业务时**什么场景该掏哪个类型**，以及编码对内存/性能的影响。

## 2. 直觉理解

Redis 的每个 value 都是一个「对象」（`redisObject`：type + encoding + lru + refcount + 指向真正数据的指针）。**同一个 type，数据少时用紧凑编码省内存，数据大了自动换成高效结构**——像快递：一两件用信封（listpack，连续内存、省空间但插入要挪动），几百件换成货架（hashtable/skiplist，有指针开销但增删快）。换货架是**单向的**：一旦升级，删到很小也不会退回信封（避免抖动）。

## 3. 原理深入

### 3.1 redisObject 与编码

`OBJECT ENCODING key` 看当前编码。每个 type 的编码与触发转换的参数：

| Type | 小数据编码 | 大数据编码 | 触发转换的参数（默认） |
|---|---|---|---|
| String | `int`（整数）/ `embstr`（≤44字节） | `raw`（>44字节 或被 APPEND/SETRANGE 改过） | embstr↔raw 边界 = 44 字节（硬编码） |
| List | `listpack` | `quicklist`（listpack 链表） | `list-max-listpack-size`（128） |
| Hash | `listpack` | `hashtable` | `hash-max-listpack-entries`(128) **或** `hash-max-listpack-value`(64B) |
| Set | `intset`（全整数）/ `listpack`（7.2+，小且非全整数） | `hashtable` | `set-max-intset-entries`(512)、`set-max-listpack-entries`(128)、`set-max-listpack-value`(64B) |
| ZSet | `listpack` | `skiplist`（+ dict） | `zset-max-listpack-entries`(128) **或** `zset-max-listpack-value`(64B) |

**转换是单向的**：超阈值升级后不会因删除而回退。

### 3.2 关键底层结构

- **SDS**（Simple Dynamic String）：String 的底层。记录 len/alloc，O(1) 取长度、二进制安全、预分配减少 realloc。`embstr` 把 redisObject 和 SDS 连续分配（一次 malloc，≤44 字节）；`raw` 分开两次分配。
- **listpack**（7.0 取代 ziplist）：一块连续内存,每个 entry 自带长度,**没有 ziplist 的「连锁更新」隐患**(ziplist 每个 entry 存前一个 entry 的长度,中间膨胀会引发级联 realloc)。
- **quicklist**：listpack 节点串成的双向链表,兼顾内存与两端操作。
- **intset**：全整数的 Set,有序整型数组,二分查找;插入非整数或超 512 个 → 升级。
- **skiplist + dict**：ZSet 用跳表（按 score 有序、支持范围）+ 字典（member→score O(1)）双结构,空间换 O(logN) 范围 + O(1) 单查。

## 4. 日常开发应用

**选型决策表（业务 → 类型）**：

| 业务场景 | 选 | 理由 |
|---|---|---|
| 计数器 / 限流计数 | String + `INCR` | 原子自增 |
| 对象/实体字段 | Hash | 部分字段读写,比整体 JSON 省带宽 |
| 队列 / 最近 N 条 | List（`LPUSH`/`LRANGE`/`LTRIM`） | 两端 O(1) |
| 去重 / 标签 / 共同好友 | Set（`SADD`/`SINTER`） | 集合运算 |
| 排行榜 / 延迟队列 / 范围查 | ZSet（`ZADD`/`ZRANGEBYSCORE`） | 按 score 有序 |
| 签到 / 布隆底层 / 在线状态 | bitmap（见 03 章） | 1 bit/用户 |

**写业务时**：
- 大 key 警惕：单个 hash/zset/list 元素数别让它无限涨（见 12 章 `--bigkeys`）。大 hash 用 `field` 分桶或拆 key。
- 想省内存就让数据待在紧凑编码内（控制元素数 < 阈值、value < 64 字节），用 `make encoding K=` 确认。

## 5. 调优实战

**Case A：「这个 hash 占内存比预期大很多」**
1. `make encoding K=h` → 若是 `hashtable`,说明超了阈值,每个 entry 有 dictEntry + SDS 指针开销。
2. 若元素数不多但都是大 value（>64B）→ 是 `hash-max-listpack-value` 触发的,考虑压缩 value 或拆字段。
3. 对照 `make mem K=h` 看实际字节。

**Case B：「想多塞点进 listpack 省内存,能不能调大阈值」**
→ 可以调 `hash-max-listpack-entries`,但 listpack 是 O(N) 查找/插入,调太大单次操作变慢、且大块连续内存易触发 realloc。**省内存 vs CPU 的权衡**,scenario 01 实测拐点。

## 6. 面试高频考点

### 编码转换阈值（必背 + 能讲所以然）
见 §3.1 表。追问「为什么单向不回退」→ 避免在阈值附近反复抖动。

### embstr vs raw 为什么是 44 字节
redisObject 16 字节 + SDS header 3 字节 + 终止符等,凑够一个 64 字节内存块（jemalloc 分配粒度）→ 字符串本体 ≤44 字节时能和 redisObject 一次分配（embstr）。

### ZSet 为什么用 skiplist + dict 两个结构
跳表给「按 score 范围/排名」O(logN),dict 给「member→score」O(1)。少了 dict,`ZSCORE` 要 O(N)。

### listpack 为什么取代 ziplist
ziplist 每个 entry 存前驱长度,中部 entry 变长会引发**连锁更新**（级联 realloc,最坏 O(N²)）。listpack 每个 entry 只存自身长度,消除连锁更新。

## 7. 一句话总结

Redis 每个 value 是 redisObject,同 type 按数据规模在「紧凑编码（listpack/intset/embstr）」与「高效结构（hashtable/skiplist/quicklist/raw）」间**单向升级**。选型先按业务语义挑 type（计数→String、对象→Hash、排行→ZSet…),再用 `OBJECT ENCODING` 确认是否还在紧凑编码内省内存。详见 Scenarios 01-04。

## Scenarios

- [01 - hash listpack → hashtable 转换阈值](scenarios/01-hash-listpack-to-hashtable.md)
- [02 - zset listpack → skiplist + 内存对比](scenarios/02-zset-listpack-to-skiplist.md)
- [03 - String int / embstr / raw 三态与 44 字节边界](scenarios/03-string-int-embstr-raw.md)
- [04 - Set intset / listpack / hashtable 三编码](scenarios/04-set-intset-listpack-hashtable.md)
````

- [ ] **Step 2: Commit**

```bash
git add redis-handson/02-data-structures/README.md
git commit -m "redis-handson: 02-data-structures README(7段+编码表+选型表)"
```

---

### Task 14: Scenario 01 — 写预期(hash listpack→hashtable)

**Files:**
- Create: `redis-handson/02-data-structures/scenarios/01-hash-listpack-to-hashtable.md`

- [ ] **Step 1: 写 scenario(预期段留学习者空格 + 环境 + 步骤,实机/落差留空)**

````markdown
# Scenario 01: hash listpack → hashtable 转换阈值

## 我想验证的问题

一个 hash,字段数从 128 涨到 129 时,`OBJECT ENCODING` 会不会从 `listpack` 变 `hashtable`?如果字段数不到 128 但某个 value 超过 64 字节呢?转成 hashtable 后再删回很小,会变回 listpack 吗?

## 预期(写实验前的假设)

> **请在跑 lab 之前填这一段**(基于 README §3.1,不要查):
>
> - 触发转 hashtable 的两个条件:字段数 > _____ **或** 单个 value 字节 > _____。
> - 我以为加到第 _____ 个字段时编码翻转。
> - 我以为删回 1 个字段后编码会 / 不会 退回 listpack(选一个),因为 _____。
>
> 填完单独 commit 一次("prediction only"),再跑下面步骤。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab:`make up`
- 默认阈值:`hash-max-listpack-entries 128`、`hash-max-listpack-value 64`

## 步骤

```bash
cd 00-lab && make up
# 1) 128 个字段:看是否还在 listpack
docker compose exec redis redis-cli del h
docker compose exec redis sh -c 'for i in $(seq 1 128); do redis-cli hset h f$i v$i >/dev/null; done'
make encoding K=h            # 预期 listpack?
# 2) 加第 129 个:看是否翻转
docker compose exec redis redis-cli hset h f129 v129
make encoding K=h            # 预期 hashtable?
# 3) value 长度触发:新 hash,只 1 个字段但 value 65 字节
docker compose exec redis redis-cli del h2
docker compose exec redis redis-cli hset h2 f1 "$(printf 'x%.0s' $(seq 1 65))"
make encoding K=h2           # 预期 hashtable?
# 4) 删回很小,看能否退回 listpack
docker compose exec redis redis-cli del h3
docker compose exec redis sh -c 'for i in $(seq 1 200); do redis-cli hset h3 f$i v$i >/dev/null; done'
make encoding K=h3           # hashtable
docker compose exec redis redis-cli hdel h3 $(docker compose exec redis redis-cli hkeys h3 | tail -n +2 | tr -d "\r")
make encoding K=h3           # 退回 listpack?
```

## 实机告诉我(跑完当天填)

```
<贴每步 OBJECT ENCODING 输出>
```

观察到的关键事实:

- ...

## ⚠️ 预期 vs 实机落差

- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡

- `99-interview-cards/q-redis-encoding-transitions.md`
````

- [ ] **Step 2: Commit(prediction only — 但本 task 由 plan 执行者代填环境/步骤,预期空格留给学习者)**

```bash
git add redis-handson/02-data-structures/scenarios/01-hash-listpack-to-hashtable.md
git commit -m "redis-handson: scenario 02-01 hash 编码转换(预期+步骤)"
```

---

### Task 15: Scenario 01 — 跑实机并填观测

**Files:**
- Modify: `redis-handson/02-data-structures/scenarios/01-hash-listpack-to-hashtable.md`(填「实机告诉我」+「落差」)

- [ ] **Step 1: 起 lab 并跑步骤**

Run: 依次执行 scenario「步骤」中的命令块。
Expected(参考结论,用于自检实机是否正常):
- 步骤 1(128 字段)→ `listpack`
- 步骤 2(129 字段)→ `hashtable`
- 步骤 3(1 字段 65 字节 value)→ `hashtable`
- 步骤 4(删回很小)→ 仍 `hashtable`(单向不退回)

- [ ] **Step 2: 把真实输出填进「实机告诉我」**,并写「⚠️ 预期 vs 实机落差」三行(我以为/实际/我学到)。

- [ ] **Step 3: Commit**

```bash
git add redis-handson/02-data-structures/scenarios/01-hash-listpack-to-hashtable.md
git commit -m "redis-handson: scenario 02-01 实机观测 + 落差"
```

---

### Task 16: Scenario 02 — 写预期(zset listpack→skiplist + 内存对比)

**Files:**
- Create: `redis-handson/02-data-structures/scenarios/02-zset-listpack-to-skiplist.md`

- [ ] **Step 1: 写 scenario**

````markdown
# Scenario 02: zset listpack → skiplist + 内存对比

## 我想验证的问题

ZSet 在 `listpack` 与 `skiplist` 两种编码下,存同样数量元素的**内存差多少**?转换发生在第几个元素?

## 预期(写实验前的假设)

> **跑前填**(基于 README §3.1/§3.2,不要查):
>
> - 转 skiplist 的条件:元素数 > _____ 或 member 字节 > _____。
> - 我以为 200 个元素的 zset,skiplist 比 listpack 内存大约 多/少 _____ %(skiplist 有跳表指针 + dict 开销)。
>
> 填完单独 commit 一次。

## 环境

- 起 lab:`make up`;阈值 `zset-max-listpack-entries 128`、`zset-max-listpack-value 64`。

## 步骤

```bash
cd 00-lab && make up
# 1) 127 元素:listpack,记内存
docker compose exec redis redis-cli del z
docker compose exec redis sh -c 'for i in $(seq 1 127); do redis-cli zadd z $i m$i >/dev/null; done'
make encoding K=z ; make mem K=z
# 2) 加到 129:转 skiplist,记内存
docker compose exec redis redis-cli zadd z 128 m128 129 m129
make encoding K=z ; make mem K=z
# 3) 同样 200 元素,分别在两种编码下对比(临时调大阈值造 listpack 版)
docker compose exec redis redis-cli config set zset-max-listpack-entries 1000
docker compose exec redis redis-cli del zlp
docker compose exec redis sh -c 'for i in $(seq 1 200); do redis-cli zadd zlp $i m$i >/dev/null; done'
make encoding K=zlp ; make mem K=zlp     # listpack 版 200 元素内存
docker compose exec redis redis-cli config set zset-max-listpack-entries 128
```

## 实机告诉我(跑完当天填)
```
<贴 encoding + MEMORY USAGE 数字>
```
观察到的关键事实:
- ...

## ⚠️ 预期 vs 实机落差
- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡
- `99-interview-cards/q-redis-encoding-transitions.md`
````

- [ ] **Step 2: Commit**

```bash
git add redis-handson/02-data-structures/scenarios/02-zset-listpack-to-skiplist.md
git commit -m "redis-handson: scenario 02-02 zset 编码 + 内存(预期+步骤)"
```

---

### Task 17: Scenario 02 — 跑实机并填观测

**Files:**
- Modify: `redis-handson/02-data-structures/scenarios/02-zset-listpack-to-skiplist.md`

- [ ] **Step 1: 跑步骤**
Expected(参考):步骤 1 `listpack`;步骤 2 `skiplist`;步骤 3 listpack 版 200 元素内存**小于**同元素 skiplist 版(skiplist 有指针 + dict 开销)。

- [ ] **Step 2: 填「实机告诉我」+「落差」。**

- [ ] **Step 3: Commit**
```bash
git add redis-handson/02-data-structures/scenarios/02-zset-listpack-to-skiplist.md
git commit -m "redis-handson: scenario 02-02 实机观测 + 落差"
```

---

### Task 18: Scenario 03 — 写预期(String int/embstr/raw + 44 字节)

**Files:**
- Create: `redis-handson/02-data-structures/scenarios/03-string-int-embstr-raw.md`

- [ ] **Step 1: 写 scenario**

````markdown
# Scenario 03: String int / embstr / raw 三态与 44 字节边界

## 我想验证的问题

String 在什么情况下是 `int` / `embstr` / `raw`?embstr 与 raw 的分界精确在哪个长度?对一个 embstr 做 `APPEND` 会发生什么?

## 预期(写实验前的假设)

> **跑前填**(基于 README §3.1/§3.2/§6,不要查):
>
> - 纯整数值 → 编码 _____。
> - 短字符串(≤ _____ 字节)→ `embstr`,超过 → `raw`。
> - 对 embstr `APPEND` 一个字符后 → 编码变 _____(因为 _____)。
>
> 填完单独 commit。

## 环境
- 起 lab:`make up`。

## 步骤
```bash
cd 00-lab && make up
docker compose exec redis redis-cli set s1 12345 ; make encoding K=s1          # int?
docker compose exec redis redis-cli set s2 "hello" ; make encoding K=s2        # embstr?
docker compose exec redis redis-cli set s3 "$(printf 'x%.0s' $(seq 1 44))" ; make encoding K=s3   # 44 字节: embstr?
docker compose exec redis redis-cli set s4 "$(printf 'x%.0s' $(seq 1 45))" ; make encoding K=s4   # 45 字节: raw?
docker compose exec redis redis-cli set s5 "ab" ; docker compose exec redis redis-cli append s5 "c" ; make encoding K=s5   # append 后: raw?
```

## 实机告诉我(跑完当天填)
```
<贴 5 个 encoding 输出>
```
观察到的关键事实:
- ...

## ⚠️ 预期 vs 实机落差
- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡
- `99-interview-cards/q-redis-encoding-transitions.md`
````

- [ ] **Step 2: Commit**
```bash
git add redis-handson/02-data-structures/scenarios/03-string-int-embstr-raw.md
git commit -m "redis-handson: scenario 02-03 String 三态(预期+步骤)"
```

---

### Task 19: Scenario 03 — 跑实机并填观测

**Files:**
- Modify: `redis-handson/02-data-structures/scenarios/03-string-int-embstr-raw.md`

- [ ] **Step 1: 跑步骤**
Expected(参考):s1=`int`;s2=`embstr`;s3(44字节)=`embstr`;s4(45字节)=`raw`;s5(append 后)=`raw`(APPEND 总是转 raw)。

- [ ] **Step 2: 填「实机告诉我」+「落差」。**

- [ ] **Step 3: Commit**
```bash
git add redis-handson/02-data-structures/scenarios/03-string-int-embstr-raw.md
git commit -m "redis-handson: scenario 02-03 实机观测 + 落差"
```

---

### Task 20: Scenario 04 — 写预期(Set intset/listpack/hashtable,标注 7.2+)

**Files:**
- Create: `redis-handson/02-data-structures/scenarios/04-set-intset-listpack-hashtable.md`

- [ ] **Step 1: 写 scenario**

````markdown
# Scenario 04: Set intset / listpack / hashtable 三编码

> 版本注:`listpack` 作为 Set 的编码是 **Redis 7.2+** 引入。7.0/7.1 只有 intset→hashtable 两态。本 lab 用 7.4。

## 我想验证的问题

Set 全是整数时是什么编码?加一个非整数元素后变什么?超过 512 个整数呢?三条转换路径分别由哪个参数触发?

## 预期(写实验前的假设)

> **跑前填**(基于 README §3.1,不要查):
>
> - 全整数且 ≤512 个 → 编码 _____。
> - 加入一个非整数(且元素少)→ 编码 _____。
> - 整数个数 > _____ → 直接 _____。
> - 非整数 Set 元素 > 128 或某元素 > 64 字节 → _____。
>
> 填完单独 commit。

## 环境
- 起 lab:`make up`;阈值 `set-max-intset-entries 512`、`set-max-listpack-entries 128`、`set-max-listpack-value 64`。

## 步骤
```bash
cd 00-lab && make up
# 1) 全整数,3 个
docker compose exec redis redis-cli del st1
docker compose exec redis redis-cli sadd st1 1 2 3 ; make encoding K=st1            # intset?
# 2) 加一个非整数
docker compose exec redis redis-cli sadd st1 hello ; make encoding K=st1            # listpack?
# 3) 全整数但 513 个
docker compose exec redis redis-cli del st2
docker compose exec redis sh -c 'redis-cli sadd st2 $(seq 1 513) >/dev/null' ; make encoding K=st2   # hashtable?
# 4) 非整数 129 个
docker compose exec redis redis-cli del st3
docker compose exec redis sh -c 'for i in $(seq 1 129); do redis-cli sadd st3 m$i >/dev/null; done' ; make encoding K=st3   # hashtable?
```

## 实机告诉我(跑完当天填)
```
<贴 4 个 encoding 输出>
```
观察到的关键事实:
- ...

## ⚠️ 预期 vs 实机落差
- 我以为:……
- 实际:……
- 我学到:……

## 连到的面试卡
- `99-interview-cards/q-redis-encoding-transitions.md`
````

- [ ] **Step 2: Commit**
```bash
git add redis-handson/02-data-structures/scenarios/04-set-intset-listpack-hashtable.md
git commit -m "redis-handson: scenario 02-04 Set 三编码(预期+步骤)"
```

---

### Task 21: Scenario 04 — 跑实机并填观测

**Files:**
- Modify: `redis-handson/02-data-structures/scenarios/04-set-intset-listpack-hashtable.md`

- [ ] **Step 1: 跑步骤**
Expected(参考,7.4):st1(全整数)=`intset`;加非整数后=`listpack`;st2(513 整数)=`hashtable`(超 intset 阈值,且 >128 listpack 阈值);st3(129 非整数)=`hashtable`。

- [ ] **Step 2: 填「实机告诉我」+「落差」。**

- [ ] **Step 3: Commit**
```bash
git add redis-handson/02-data-structures/scenarios/04-set-intset-listpack-hashtable.md
git commit -m "redis-handson: scenario 02-04 实机观测 + 落差"
```

---

### Task 22: 写面试卡 — 编码转换

**Files:**
- Create: `redis-handson/99-interview-cards/q-redis-encoding-transitions.md`

- [ ] **Step 1: 写卡**

````markdown
# Redis 各类型的底层编码与转换阈值是什么?

## 一句话回答

每个 type 按数据规模在「紧凑编码」与「高效结构」间**单向升级**:String `int/embstr(≤44B)/raw`;List/Hash/ZSet `listpack → hashtable/skiplist/quicklist`;Set `intset → listpack(7.2+) → hashtable`。超阈值后**不回退**,避免抖动。

## 阈值表

| Type | 紧凑 | 升级后 | 触发参数(默认) |
|---|---|---|---|
| String | int / embstr(≤44B) | raw | 44 字节硬边界;APPEND/SETRANGE 必转 raw |
| List | listpack | quicklist | `list-max-listpack-size`(128) |
| Hash | listpack | hashtable | entries 128 **或** value 64B |
| Set | intset / listpack | hashtable | intset 512;listpack entries 128/value 64B |
| ZSet | listpack | skiplist(+dict) | entries 128 **或** value 64B |

## 易追问的延伸

- **embstr 为什么是 44 字节?** redisObject(16B)+SDS header+终止符 凑满 64B jemalloc 块 → 本体 ≤44B 可一次分配。证据:[scenario 03](../02-data-structures/scenarios/03-string-int-embstr-raw.md)
- **ZSet 为什么 skiplist + dict 两个结构?** 跳表给范围/排名 O(logN),dict 给 member→score O(1)。证据:[scenario 02](../02-data-structures/scenarios/02-zset-listpack-to-skiplist.md)
- **listpack 凭什么取代 ziplist?** 消除 ziplist 的连锁更新(级联 realloc)。
- **转换可逆吗?** 不可逆。证据:[scenario 01 步骤 4](../02-data-structures/scenarios/01-hash-listpack-to-hashtable.md)

## 证据链接

- 章节原理:[02-data-structures §3](../02-data-structures/README.md)
- 实测:scenarios 01-04
````

- [ ] **Step 2: Commit**

```bash
git add redis-handson/99-interview-cards/q-redis-encoding-transitions.md
git commit -m "redis-handson: 面试卡 编码转换阈值"
```

---

## Self-Review(写完即查)

**1. Spec coverage**:本 plan 覆盖 spec 的 Phase 0(lab,Task 1-12)+ Phase 1 首章 02-data-structures(Task 13-22)。spec 其余 12 章留待后续 plan(增量,逐章)。✅
**2. Placeholder scan**:无 TBD/TODO;scenario 的「预期空格」与「实机告诉我」是**刻意留给学习者/实机**的纪律产物,非 plan 占位。✅
**3. Type consistency**:容器名(`redis`/`redis-node-N`/`redis-m`/`redis-sn-N`)、make 目标名(`encoding K=`/`mem K=`/`up-cluster`/`cluster-init`)、conf 参数名(`hash-max-listpack-entries` 等)在 README、Makefile、scenario、面试卡间一致。✅
**4. 版本正确性**:Set listpack 编码标注 7.2+;listpack 取代 ziplist 标注 7.0;io-threads 6.0。✅

---

**下一步**:执行本 plan。后续章节(06 缓存模式 / 07 锁 / 12 生产运维 …)各自再写增量 plan。
