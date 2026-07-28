# MySQL 8.4 InnoDB Cluster：从提交边界到故障切换

本章把[产品无关的 HA 基础](../ha-foundations.md)落到一个可执行的 MySQL 8.4 Lab。先记住成功边界：唯一合法写入方向、已确认业务结果不丢、UNKNOWN 可按稳定 `request_id` 对账、恢复后数据收敛。这里不重复 quorum、五平面或 RPO／RTO 理论；遇到术语先回到基础章。

## 1. 这套方案解决什么，不解决什么

InnoDB Cluster 把三台 MySQL Server 的 Group Replication、AdminAPI 管理入口和 Router 元数据路由组合起来，解决单成员故障下的多数派选主、旧 Primary 失权、新连接发现新 Primary，以及成员恢复。

它不替应用完成幂等、UNKNOWN 对账或搬迁现有连接；不替备份／PITR 恢复已复制的误删；不证明跨机、跨 rack／AZ、DNS、证书或磁盘故障。职责与故障模型见[基础章 §3–§8](../ha-foundations.md)。

## 2. 组件责任：Server、Group Replication、Shell／AdminAPI、Router、应用

| 组件 | 正责任 | 明确不负责 |
|---|---|---|
| Server／InnoDB | 执行事务、redo／binlog durability、数据页与本地读写栅栏 | 不重试应用请求（Server／InnoDB does not retry application requests） |
| Group Replication | 成员视图、quorum、认证／复制、Single-Primary 角色与 flow control | 不移动既有客户端连接（Group Replication does not move existing client connections） |
| Shell／AdminAPI | 建立、检查、切主、rejoin、complete-outage reboot | 不在 SQL data path（Shell／AdminAPI is not on the SQL data path） |
| Router | 消费 metadata，把新连接送到当前可用角色 | 不复制数据，也不选 Primary（Router does not copy data or elect a Primary） |
| 应用 | 稳定 `request_id`、幂等、SUCCESS／FAILURE／UNKNOWN、bounded retry、连接重建 | 不能假设 failover 对连接透明（The application cannot assume failover is connection-transparent） |

## 3. 三节点 Single-Primary 拓扑

```text
workload/app ─┬─ Router A :6446 ─┐
              └─ Router B :6446 ─┴─ metadata route ─> one writable Primary
                                                   ├─ db1 weight 100
                                                   ├─ db2 weight 80
                                                   └─ db3 weight 60
                                         2/3 quorum; two ONLINE Secondaries
Shell/AdminAPI ─────────────────────────────── control/operations only
```

两个 Router 只是两个入口；应用必须实际使用多个 endpoint 或上游健康检查。三成员都在同一 Compose network／宿主机，因此只证明协议行为，不证明独立故障域。

## 4. 正常提交时序

```text
Client
  → Router
  → Primary 执行事务                                      [1 Primary execution]
  → 产生并传播 write set                                  [2 write-set generation／propagation]
  → Group Replication 排序与认证                           [3 ordering／certification]
  → Primary 本地提交                                      [4 local commit]
  → Client 收到 SUCCESS                                   [5 client success]
  → Secondary 继续 apply                                  [6 Secondary apply]
  → Secondary 对该事务可读                                [7 Secondary read visibility]
```

上图第 4 步是 `Primary 本地提交`。Router 不参与 commit。多数派完成组内决策不代表所有 Secondary 已 apply，更不代表已达到 Secondary read visibility；Secondary 可能存在 applier backlog。`innodb_flush_log_at_trx_commit=1` 与 `sync_binlog=1` 约束本地 durability；quorum、日志落盘、Primary commit、Secondary 可读与页刷盘仍是不同边界。本文把 ACK 保留给 replica receive／confirmation boundary；应用层结果写作 SUCCESS。Client 断线时应用先记 UNKNOWN，再按原 `request_id` 查明。完整七边界见[基础章 §6](../ha-foundations.md)。

## 5. Primary failover 时序

```text
旧 Primary 无法联络
  → Group 更新成员视图
  → 多数派排除故障成员
  → 选出新 Primary
  → 新 Primary 处理必要 backlog
  → 开放写入
  → Router 更新拓扑
  → 旧连接断开
  → 应用重新连接
  → 新连接到达新 Primary
  → 新 Primary 执行事务                                  [1 Primary execution]
  → 产生并传播 write set                                 [2 write-set generation／propagation]
  → Group Replication 排序与认证                          [3 ordering／certification]
  → 新 Primary 本地提交                                  [4 local commit]
  → Client 收到 SUCCESS                                  [5 client success]
  → Secondary apply                                      [6 Secondary apply]
  → Secondary 对该事务可读                               [7 Secondary read visibility]
```

`BEFORE_ON_PRIMARY_FAILOVER` 把“处理必要 backlog”放在“开放写入”之前，避免新 Primary 向应用呈现数据倒退，但会增加恢复等待。Router 只更新新连接目标；应用须丢弃旧连接、bounded reconnect，并按原 `request_id` 查询断线请求。检测、选举、backlog fence、Router refresh、应用重连要分别量；不能把最终 `3 ONLINE` 倒推出客户端 RTO。

## 6. 固定配置快照与每项理由

| 固定值 | 理由／边界 |
|---|---|
| `mysql:8.4.10` | 固定 Server baseline，避免浮动 tag |
| `community-router:8.4.10` | Router 与 Server 同一 8.4 patch baseline |
| `mysql-shell=8.4.10`（独立 Oracle Linux tooling image） | AdminAPI 版本固定；不把 Shell 塞进 Server image |
| `communicationStack=MYSQL` | 组通信复用 MySQL protocol stack |
| `consistency=BEFORE_ON_PRIMARY_FAILOVER` | 新 Primary 在 failover 后开放流量前处理 backlog |
| `exitStateAction=OFFLINE_MODE` | 异常退出组后 fail closed；实测 fencing 也可能表现为 `super_read_only=1` |
| `autoRejoinTries=3` | 短暂故障有限自动重试；失败后交给人判断 |
| `expelTimeout=5` | Lab 加速成员驱逐，不是生产默认建议 |
| `group_replication_unreachable_majority_timeout=5`（仅 Lab） | Lab 加速失去多数派后的 fencing |
| `memberWeight=db1:100,db2:80,db3:60` | 让演练中的候选顺序可预测，不替代 quorum |
| `super_read_only=ON`（启动保护） | mysqld 启动但尚未获组内角色时不接受普通写 |
| `innodb_flush_log_at_trx_commit=1` | 每次 commit 刷 redo，明确本地 durability baseline |
| `sync_binlog=1` | 每次事务同步 binlog，降低 OS crash 后 binlog 丢失窗口 |

权威实现是 [`00-lab/ha/compose.yml`](../../00-lab/ha/compose.yml)、[`config/common.cnf`](../../00-lab/ha/config/common.cnf)、[`tools/Dockerfile`](../../00-lab/ha/tools/Dockerfile)、[`bootstrap/cluster.js`](../../00-lab/ha/bootstrap/cluster.js) 与 [`init/01-persist-super-read-only.sql`](../../00-lab/ha/init/01-persist-super-read-only.sql)，本表不是第二份配置源。`expelTimeout=5` 和 `group_replication_unreachable_majority_timeout=5` 是 Lab timing knobs；生产要用 RTT／loss baseline、误驱逐风险与 RTO 预算重新决策，不能照抄。

Router 与 Shell tooling 固定运行于 `linux/amd64`。Apple Silicon 上包含 amd64 emulation overhead，因此本地时间只可作为 behavioral evidence，不可当作生产容量或 RTO 证明。

## 7. 从空实例建立 Cluster

```bash
make -C mysql-handson/00-lab/ha config
make -C mysql-handson/00-lab/ha up-db
make -C mysql-handson/00-lab/ha bootstrap
make -C mysql-handson/00-lab/ha routers
make -C mysql-handson/00-lab/ha init
make -C mysql-handson/00-lab/ha status
```

`make -C mysql-handson/00-lab/ha up-db` 首次建立空 volume 时，Docker entrypoint 先在每个独立成员执行挂载的 `init/01-persist-super-read-only.sql` 与 `init/01-orders.sql`；这发生在建群之前。随后 `make -C mysql-handson/00-lab/ha bootstrap` 执行 `dba.configureInstance()`、在 `db1` create／get Cluster、以 Clone 加入 `db2/db3` 并等待三成员 ONLINE；`make -C mysql-handson/00-lab/ha routers` 再启动并等待两个 Router。最后 `make -C mysql-handson/00-lab/ha init` 经 Router A 在当前 Primary 重跑 idempotent `init/01-orders.sql`，确保应用 schema／account 存在；它不是 Docker entrypoint 的首次初始化时点。日常可直接运行 `make -C mysql-handson/00-lab/ha up`。

`make -C mysql-handson/00-lab/ha reset` 执行 Compose `down --volumes --remove-orphans`：删除 `mysql-ha` containers、named volumes、Compose network 与 orphans；随后只删除 `evidence/` 顶层的普通文件，既有 archive 子目录不在这一步递归删除。

## 8. Router bootstrap 与应用重连

`router-a` 以 `db1`、`router-b` 以 `db2` 作为 bootstrap seed；seed 只是读取 Cluster metadata 的入口，不是永久 Primary。Lab 的 RW 端口是容器内 `6446`，主机映射 `16446`／`17446`。

```bash
make -C mysql-handson/00-lab/ha mysql-a
make -C mysql-handson/00-lab/ha mysql-b
make -C mysql-handson/00-lab/ha workload-once N=10
```

已有 session 在切主或 Router 故障时可断开；连接池必须丢弃坏连接、在多个入口间 bounded retry，并以原 `request_id` 对账 UNKNOWN。Router green 只证明入口，不证明业务 commit 或成员收敛。

## 9. 观测成员、队列、flow control 与 Router

以下查询在成员上由 DBA／数据库平台 owner 执行。

```sql
SELECT MEMBER_HOST, MEMBER_ROLE, MEMBER_STATE
FROM performance_schema.replication_group_members
ORDER BY MEMBER_HOST;
```

这些字段的 owner 都是 Group Replication membership view：`MEMBER_HOST` 标识该 view 中的成员地址；`MEMBER_ROLE` 表示 `PRIMARY`／`SECONDARY`，Single-Primary 应仅一个 `PRIMARY`；`MEMBER_STATE` 是该成员在组内的生命周期状态。`ONLINE` 是必要但不充分条件；还要独立证明业务 ledger 与三成员 data／ID equality。

```sql
SELECT MEMBER_ID,
       COUNT_TRANSACTIONS_IN_QUEUE,
       COUNT_TRANSACTIONS_CHECKED,
       COUNT_CONFLICTS_DETECTED,
       COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE,
       COUNT_TRANSACTIONS_REMOTE_APPLIED
FROM performance_schema.replication_group_member_stats;
```

这些字段由 Group Replication 写入、Performance Schema 暴露：`MEMBER_ID` 是统计行所属成员的 server UUID，用于把本表关联到 membership view；`COUNT_TRANSACTIONS_IN_QUEUE` 是本地 certifier queue；`COUNT_TRANSACTIONS_CHECKED` 是已检查的事务累计量；`COUNT_CONFLICTS_DETECTED` 是检测到认证冲突的累计量；`COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE` 是已接收但尚待 apply 的远端事务 backlog；`COUNT_TRANSACTIONS_REMOTE_APPLIED` 是已 apply 的远端事务累计量。累计量看增量，queue 看采样时点，均需结合采样速率和 workload 解读。

```sql
SELECT @@global.group_replication_flow_control_mode,
       @@global.group_replication_flow_control_applier_threshold,
       @@global.group_replication_flow_control_certifier_threshold;
```

配置 owner 是 DBA／数据库平台：`group_replication_flow_control_mode` 选择 flow-control 算法，固定基线期望 `QUOTA`；`group_replication_flow_control_applier_threshold` 是 remote applier queue 的触发阈值；`group_replication_flow_control_certifier_threshold` 是 certifier queue 的触发阈值，不能拿它解释 applier backlog。固定 8.4 Community baseline 的硬证据是 mode 为 `QUOTA` 时，核心 `COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE` 跨过当前 `flow_control_applier_threshold`；不依赖 optional component-specific throttle counters。

```sql
SELECT @@global.group_replication_consistency,
       @@global.group_replication_exit_state_action,
       @@global.group_replication_autorejoin_tries,
       @@global.group_replication_member_expel_timeout,
       @@global.group_replication_unreachable_majority_timeout;
```

这组变量由 DBA／数据库平台 owner 核对运行值是否漂移：`group_replication_consistency` 是读写／failover consistency gate；`group_replication_exit_state_action` 决定成员异常离组后的 fencing action；`group_replication_autorejoin_tries` 是自动 rejoin 尝试次数；`group_replication_member_expel_timeout` 是怀疑成员到驱逐的等待；`group_replication_unreachable_majority_timeout` 是成员失去多数派后进入错误／停写动作前的等待。Router 另由入口 owner 监控两个 `6446` endpoint、metadata refresh 与连接错误率。

最终验证用实现提供的命令，而非只看状态：

```bash
make -C mysql-handson/00-lab/ha status
make -C mysql-handson/00-lab/ha verify
```

## 10. 节点恢复：auto-rejoin、rejoin、Clone／incremental

短暂失联先由 `autoRejoinTries=3` 尝试；失败后，人必须检查 member state、GTID、errant transaction、queue 与数据损坏。可追上且无分叉才使用 AdminAPI `rejoinInstance()`；缺失范围较大或本地数据不可信时选择 Clone。incremental recovery 只有在 donor 保有所需 GTID／binlog 且集合兼容时才成立。

A rejoining member does not serve traffic until state, backlog and business data are verified. Lab 的完整路径与证据见 [Scenario 07](scenarios/07-member-rejoin.md)，入口与成员修复是两个不同计时器。

## 11. 完整 outage reboot

全部成员停止后不能假装普通 failover。先 quiesce Router／客户端，证明各服务端不可写，取得每成员 GTID；只有包含所有成员事务的 GTID-superset 才可做 seed。然后停止 GR，执行：

```bash
make -C mysql-handson/00-lab/ha recovery-complete-outage
```

脚本先调用 `dba.rebootClusterFromCompleteOutage(..., {dryRun:true})`，再 actual；默认不使用 `force:true`。成功门槛是 `3 ONLINE / 1 PRIMARY`、唯一 Primary 可写、Router transaction rollback probe、业务 ID before／after `cmp -s` 相等，并恢复每成员原来的 start-on-boot 值。操作决策见 [Runbook §13](production-runbook.md#13-complete-cluster-outage)。

## 12. 八个核心 Scenario 学习顺序

证据 archive 在本机且被 Git ignore；文档提交的是可追溯 run ID，不把本地 archive 冒充仓库内或生产证据。

| 顺序 | 学习重点 | 指定成功 run ID／本地证据索引 | 状态 |
|---|---|---|---|
| [01 planned switchover](scenarios/01-planned-switchover.md) | 计划切主仍断旧 session；分段 RTO | `mysql-handson/00-lab/ha/evidence/runs/planned-switchover/20260726T094213Z/` | measured Lab PASS |
| [02 Primary crash](scenarios/02-primary-crash.md) | 多数派选主、Router 新连接、acknowledged business IDs 对账 | `mysql-handson/00-lab/ha/evidence/runs/primary-crash/20260726T095829Z/` | measured Lab PASS |
| [03 Primary partition](scenarios/03-primary-partition.md) | 少数派 fencing、多数派续写 | `mysql-handson/00-lab/ha/evidence/runs/primary-partition/20260726T100107Z/` | measured Lab PASS |
| [04 quorum loss](scenarios/04-quorum-loss.md) | `quorum_blocked` 后零 SUCCESS、安全恢复 | `mysql-handson/00-lab/ha/evidence/runs/quorum-loss/20260728T051412Z/` | measured Lab PASS |
| [05 slow member](scenarios/05-slow-member.md) | QUOTA queue 跨 threshold，不拿 p95 当硬断言 | `mysql-handson/00-lab/ha/evidence/runs/slow-member/20260728T052238Z/` | measured Lab PASS |
| [06 Router failure](scenarios/06-router-failure.md) | 一个入口故障、另一个入口持续成功 | `mysql-handson/00-lab/ha/evidence/runs/router-failure/20260728T052430Z/` | measured Lab PASS |
| [07 member rejoin](scenarios/07-member-rejoin.md) | rejoin ONLINE 与业务恢复边界分离 | `mysql-handson/00-lab/ha/evidence/runs/member-rejoin/20260728T052648Z/` | measured Lab PASS |
| [08 HA cannot replace PITR](scenarios/08-ha-cannot-replace-pitr.md) | 误删全组传播、隔离 PITR | `mysql-handson/00-lab/ha/evidence/runs/ha-cannot-replace-pitr/20260728T062708Z/` | measured Lab PASS |

Task 9 complete-outage drill 是 Runbook supporting evidence，**不是第九个核心 Scenario**。它的本地索引为 `mysql-handson/00-lab/ha/evidence/complete-outage/`，最终 measured lifecycle 是 `2026-07-26T13:39:50.368282+00:00` 到 `2026-07-26T13:40:16.350305+00:00`；证明的是本机安全恢复链，不是生产 RTO。

## 13. Compose Lab 与生产故障域的边界

| Lab 已实测 | 仍只是 architecture reasoning／生产待证 |
|---|---|
| 单宿主机内成员进程、network namespace、Router 容器故障 | 独立 power／host／rack 或 AZ、共享网络设备与存储故障 |
| 固定版本、三成员、Single-Primary、协议状态与 fencing | 真实 RTT／loss、DNS、TLS rotation、密钥、NTP、磁盘写屏障 |
| 连续 workload、请求三态、分段 RTO、成员 ID equality | 生产流量、连接池、LB、容量 headroom、告警和升级窗口 |
| 隔离 recovery container 的单文件 position PITR | 生产备份保留、跨文件／跨域恢复、回迁与审计 |

amd64 emulation、Lab 的 5 秒 timing knobs 与单机资源争用都会改变时间。这里的 measured run 只支撑所声明的行为；上线条件、owner、证据与失败后果见 [Production Runbook](production-runbook.md)。

## 14. 完成标准审计

以下结果来自 2026-07-28 的独立 clean-reset 重跑。证据 archive 被 Git ignore，只是当前工作站上的可复核索引；其中失败尝试也被保留，不会冒充成功证据。

| Criterion | Evidence command／file | Result |
|---|---|---|
| clean build | `mysql-handson/00-lab/ha/verify-static.sh`（Compose config、全部 Bash syntax、全部 unit／link tests、unfinished-marker scan、`git diff --check`） | PASS |
| independent reset | 逐一执行 `make -C mysql-handson/00-lab/ha scenario SCENARIO=<01..08>`；每个正常入口先执行 recovery-aware `reset` | PASS；八个命令均以独立空 volume 开始并退出 `0` |
| segmented RTO | `evidence/runs/planned-switchover/20260728T071817Z/scenario-verification.json` | PASS；detection／election／backlog-fence／Router refresh／application reconnect 均有分段，客户端 RTO `499 ms` |
| acknowledged writes | Scenario 01–07 成功 archive 的共同 `verification.json`；例如 `evidence/runs/quorum-loss/20260728T073723Z/verification.json`。Scenario 08 没有这份共同报告，改查 `20260728T075958Z/{member-zero.txt,final-member-counts.txt,expected-projection.tsv,recovered-projection.tsv,final-topology.txt,recovery-readiness.txt}` | PASS；Scenario 01–07 的共同 verifier 均为 `errors=[]`，示例 run 的 `211` 个 ACK 在三成员各 `211` 行；Scenario 08 以两份五栏 projection 的 `cmp -s`、两组三成员 `0／0／0`、最终拓扑与 authenticated recovery readiness 证明其 PITR 专属结果 |
| unknown reconciliation | `evidence/runs/primary-partition/20260728T072358Z/verification.json` 与 `evidence/runs/member-rejoin/20260728T075804Z/verification.json` | PASS；前者 `1` 个、后者 `2` 个 UNKNOWN 均按原 `request_id` 对账为 committed |
| minority fencing | `evidence/runs/primary-partition/20260728T072358Z/fencing.json`、`scenario-verification.json` | PASS；原 Primary `super_read_only=1` 且 direct write 被拒绝 |
| quorum loss | `evidence/runs/quorum-loss/20260728T073723Z/events.jsonl`、`scenario-verification.json` | PASS；五阶段严格有序；grace 窗 `0 SUCCESS／12 FAILURE／2 UNKNOWN`，硬门槛 `quorum_blocked→quorum_restore_begin` 为 `0 SUCCESS／8 FAILURE／0 UNKNOWN` |
| Router failover | `evidence/runs/router-failure/20260728T075444Z/ledger-router-{a,b}.jsonl` | PASS；Router A 为 `87 SUCCESS／12 FAILURE` 时 Router B 仍有 `184 SUCCESS／0 FAILURE` |
| rejoin | `evidence/runs/member-rejoin/20260728T075804Z/events.jsonl`、`verification.json` | PASS；`rejoin_begin < rejoin_online`，最终三成员 ONLINE、一个 Primary、业务行收敛 |
| complete outage | `make -C mysql-handson/00-lab/ha recovery-complete-outage`；`evidence/complete-outage/{events.jsonl,before-ids.txt,after-ids.txt,final-status.json}` | PASS；dry-run 后 actual，`cmp -s before-ids.txt after-ids.txt` 退出 `0`（各 `40` 行），最终三成员 ONLINE、一个可写 Primary |
| PITR | `evidence/runs/ha-cannot-replace-pitr/20260728T075958Z/` | PASS；三在线成员保持误删后的 `0／0／0`，隔离 recovery 从 base `10` 恢复到 `11` 行，五栏 projection 逐字节相等，边界为 `binlog.000004:238→591` |
| documented Runbook | [production-runbook.md](production-runbook.md)；`rg -n '^## ' mysql-handson/09-replication-and-ha/innodb-cluster/production-runbook.md` | PASS；部署、切换、故障、恢复、定期演练共 15 个明确章节 |
| learner explanation exercise | [基础章 §11 自测题](../ha-foundations.md#11-自测题)；`rg -n '^## 11\. 自测题|<details><summary>答案</summary>' mysql-handson/09-replication-and-ha/ha-foundations.md` | PASS；实际提供 5 道逐层解释题及 5 个可展开答案，不以聊天中的口头回答代替证据 |
| physical-failure boundary | [§13 Compose Lab 与生产故障域的边界](#13-compose-lab-与生产故障域的边界) | PASS（scope documented）；只声明容器／network namespace 的实测结果，独立主机、机架／AZ、真实磁盘与共享设备故障明确为未实证 |

失败证据同样保留：Scenario 04 的 `evidence/runs/quorum-loss/20260728T072538Z-failed-router-readiness/` 是 Router bootstrap/readiness race；Scenario 05 的 `evidence/runs/slow-member/20260728T073920Z-failed-recovering-timeout/` 是受限成员仍处于 RECOVERING 时 bounded wait 到期。两者之后都从独立 clean reset 取得了上表所列 matching PASS；失败 run 不用于支持完成标准。

## 15. 第二方案评估 gate

这里评估的是「现有证据是否出现必须用 PXC 回答的选型缺口」，不是比较功能数量。`Result` 必须是当前证据下的确定值；本节不部署 PXC。

| Candidate gap／condition | Evidence required | Rule for `Yes` | Result | Observed evidence |
|---|---|---|---|---|
| Galera commit／certification semantics | 指出主方案的提交证据无法回答的具体选型问题 | 缺口关联已完成 Scenario，且会改变真实选型 | No | 八个 Scenario 已回答当前 Single-Primary 目标的成功边界、quorum、fencing、ACK／UNKNOWN 与恢复；尚无业务约束要求用 Galera 语义作不同决策 |
| Multi-primary conflict semantics | 指出单 Primary 主线无法回答的具体写入约束 | 缺口可用同一业务 invariant 验证，且不是追求功能数量 | No | 当前 invariant 是唯一写方向与稳定 `request_id`；没有多站点主动写、写入分片或必须接受认证冲突的需求证据 |
| SST／IST recovery semantics | 指出 Clone／incremental 恢复证据无法回答的具体恢复约束 | 缺口关联 RTO、运维风险或容量决策 | No | 已验证 rejoin、Clone／incremental 决策边界、complete-outage 与 PITR；当前没有恢复窗口、donor 压力或容量约束显示 SST／IST 会改变选型 |
| 同一 workload、故障模型与 verifier 能否公平复用？ | 列出无需改语义即可复用的接口 | 请求三态、故障窗口与最终数据断言都无需降级 | Yes | `request_id` 三态 ledger、fault lifecycle、成员最终 ID equality、Router 双入口与 verifier 数据断言可保持原语义复用；产品专属注入／拓扑查询需替换 |
| 新方案的学习收益是否大于部署、恢复、维护成本？ | 给出新增任务数量和预期决策收益 | 新增实验能回答当前证据无法回答的选型问题 | No | 至少需要镜像／拓扑、bootstrap、故障注入、SST／IST 恢复、验证器适配、文档与审计等 6 类新增任务，但前三个机制缺口全为 `No`，没有新增决策收益可抵消成本 |

**Overall gate result: No.** 三个机制缺口没有至少两个 concrete／important／independently verifiable `Yes`；虽然接口可复用，学习收益也没有超过新增部署与恢复维护成本。因此本专题停在架构比较，不开启 PXC brainstorming／design，也不增加任何 PXC Compose 或命令。
