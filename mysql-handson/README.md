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
