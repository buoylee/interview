# MySQL 资深场景推理

读完各章原理却答不出陌生题，缺的通常不是再背一组参数，而是把跨章节知识按约束、执行链、取舍、证据与恢复组装成方案的能力。本目录是这个 cross-chapter assembly 路由层；ch01–11 仍是机制与事实的 owner。

## 为什么学完原理仍答不出陌生题

陌生题不会先告诉你该用哪一章。先从业务不变式、数据量、停机窗口、可接受数据陈旧度、可否重跑和验证方式收敛约束，才知道该把哪些机制接成可执行方案。

## 一套可迁移的场景解题器

先遮住正文口述，再按固定八步展开：

1. 约束：澄清业务不变式、规模、SLO、停机与重跑边界。
2. 执行链：从 client／SQL 到 Server、InnoDB、日志、复制与外部输出。
3. 成本与瓶颈：估算 CPU、内存、I/O、网络、锁、写放大与 backlog。
4. 正确性与风险：明确会错什么、UNKNOWN 在哪里发生、如何隔离 side effect。
5. 基准方案：在已声明假设下给出最小可行的安全流程。
6. 替代方案与取舍：约束变化时说明何时换方案及代价。
7. 验证：定义指标、验收、不变式、停止条件与证据等级。
8. 恢复与回滚：定义 batch identity、watermark、重试、回滚与 restart point。

## 两遍练习法

- 第一遍：30 秒收敛假设与 baseline。
- 第二遍：3–5 分钟补齐成本、风险、证据与 rollback。

口述后才打开对应 owner；不要先阅读答案再把复述误当成推理能力。

## 19 类问题与唯一 owner

每个问题族只有一个 scenario owner；`13` 负责路由，不复制这些 owner 的完整正文。

| # | 问题族 | 唯一 scenario owner | `13` 的处理 |
|---|---|---|---|
| 1 | 从 access pattern 设计表、主键、型别、约束与索引 | [从 access patterns 设计 schema](01-schema-from-access-patterns.md) | `REPRODUCED (S=100000)` |
| 2 | 高效且安全地汇入 1,000 万行 | [高效安全地导入 1,000 万行](02-bulk-load-10m.md) | `SCALED_REPRODUCED (M=1,000,000)`；L disk gate 未通过 |
| 3 | 线上 schema 变更与资料 backfill | `python-data/07-migrations.md` | 路由；MySQL DDL 机制连到 ch11 |
| 4 | 历史资料归档、大量删除与空间回收 | [归档、批量删除与空间回收](03-archive-delete-reclaim.md) | `SCALED_REPRODUCED (S=100000)` |
| 5 | 资料分布改变造成执行计划退化 | `mysql-handson/04-execution-and-explain/scenarios/01-plan-flips-by-selectivity.md` | 路由 |
| 6 | 大型 JOIN、报表与全量汇出如何隔离 OLTP | [大型报表与导出隔离](04-report-export-isolation.md)；[container lab](../00-lab/senior-scenarios/README.md) | `SCALED_REPRODUCED (S=10000 orders, 30000 items)`；JOIN 机制连到 ch08 |
| 7 | 深分页到大批量汇出的完整处理 | [大型报表与导出隔离](04-report-export-isolation.md) | `SCALED_REPRODUCED (S=10000 orders, 30000 items)`；场景组装；分页机制连到 ch08 scenario 03 |
| 8 | 高并发扣库存与防超卖 | `system-design-scenarios/16-秒杀与票务.md` | 路由 |
| 9 | 订单／支付／库存的 UNKNOWN、幂等与对账 | `financial-consistency/03-order-payment-inventory/README.md` | 路由；面试卡作闭卷入口 |
| 10 | 热点库存行、锁竞争与死锁取舍 | `system-design-scenarios/16-秒杀与票务.md` | 路由；锁机制连到 ch06 |
| 11 | MySQL CPU 100% 排查 | `mysql-handson/11-ops-and-troubleshooting/README.md` Case A | 路由 |
| 12 | 连接数耗尽与慢查堆积 | `mysql-handson/11-ops-and-troubleshooting/README.md` Case B | 路由 |
| 13 | 写风暴、checkpoint 与吞吐崩塌 | `mysql-handson/11-ops-and-troubleshooting/scenarios/01-write-storm-checkpoint-throttle.md` | 路由 |
| 14 | replica lag 与 Read Your Writes | `mysql-handson/09-replication-and-ha/README.md` | 路由 |
| 15 | Primary 故障、fencing、Router 与 failover | `mysql-handson/09-replication-and-ha/innodb-cluster/README.md` | 路由到既有实测 scenario |
| 16 | 误删后 PITR，以及 HA 为何不能取代备份 | `mysql-handson/09-replication-and-ha/innodb-cluster/scenarios/08-ha-cannot-replace-pitr.md` | 路由 |
| 17 | 是否该分库分表 | `mysql-handson/10-sharding-and-scaling/README.md` | 路由 |
| 18 | 分片键、热点、扩容与 reshard | `mysql-handson/10-sharding-and-scaling/README.md` | 路由 |
| 19 | 线上分片迁移、双写与 CDC 校验 | `mysql-handson/10-sharding-and-scaling/README.md` Case C | 路由；CDC 故障闭环连到 `mysql-es-cdc-handson` |

[从 access patterns 设计 schema](01-schema-from-access-patterns.md) 已完成 run ID `20260730T214437Z` 的 `REPRODUCED (S=100000)`；[高效安全地导入 1,000 万行](02-bulk-load-10m.md) 为 `SCALED_REPRODUCED (M=1,000,000)`；[归档、批量删除与空间回收](03-archive-delete-reclaim.md) 为 `SCALED_REPRODUCED (S=100000)`；[大型报表与导出隔离](04-report-export-isolation.md) 已完成 `SCALED_REPRODUCED (S=10000 orders, 30000 items)` Docker 缩小实验。

## 四个新增场景

| 场景 | 状态 | 负责的问题 |
|---|---|---|
| `01-schema-from-access-patterns.md` | `REPRODUCED (S=100000)` | 从 access pattern 推导 schema |
| [高效安全地导入 1,000 万行](02-bulk-load-10m.md) | `SCALED_REPRODUCED (M=1,000,000)` | 1,000 万行安全、高吞吐、可恢复汇入 |
| [归档、批量删除与空间回收](03-archive-delete-reclaim.md) | `SCALED_REPRODUCED (S=100000)` | retention、archive、delete、purge 与 reclaim |
| [大型报表与导出隔离](04-report-export-isolation.md) | `SCALED_REPRODUCED (S=10000 orders, 30000 items)` | 报表／汇出与 OLTP 隔离，含深分页到汇出 |

## 证据等级

| 标签 | 精确含义 |
|---|---|
| `REPRODUCED` | 文件宣称的目标条件已实际执行，且正确性与完成条件通过 |
| `SCALED_REPRODUCED` | 只在缩小资料量或简化故障域实跑；不能外推为目标规模已完成 |
| `READY_UNRUN` | 命令、预期、验收与停止条件已准备，但尚未执行 |
| `REASONED` | 由机制或架构推导，没有宣称本机实测 |
| `REUSED` | 结论直接引用 repository 内既有、可追溯的实验证据 |

## 面试输出标准

- **30 秒**：先问最关键的约束，再给 baseline、最大风险与验证方式。
- **3–5 分钟**：走完执行链、成本模型、正确性、方案取舍、停止条件与恢复／rollback。

| 结果 | 精确定义 |
|---|---|
| `SUCCEEDED` | 完成且通过不变式。 |
| `FAILED` | 已确认没有完成，可依既定规则修正或重跑。 |
| `UNKNOWN` | client 在 statement／commit 后失联或 timeout，数据库可能已提交；必须先按 batch identity（run ID／batch ID）查证，不能把 `UNKNOWN` 当 `FAILED` 自动重跑。 |
| `ABORTED` | 因停止条件主动中止，保留 restart point。 |

## 与其他目录的边界

- ch01–11 是 mechanism owner：定义 MySQL 为什么这样执行。
- ch12 是 compression：快速压缩面试答案，不承载长场景推导。
- ch99 是 closed-book：遮住答案练习提问、口述与追问。
- ch00-lab 是 evidence environment：提供可重跑的实验环境与证据来源。
