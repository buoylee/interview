# InnoDB Cluster Production Runbook

本 Runbook 是决策文件，不是第二份配置。Lab 的唯一执行入口是 [`mysql-handson/00-lab/ha/Makefile`](../../00-lab/ha/Makefile)，固定实现见[产品指南 §6](README.md#6-固定配置快照与每项理由)，理论边界见[产品无关 HA 基础](../ha-foundations.md)。所有本地 archive 被 Git ignore；“measured”只表示该 Compose Lab 实跑，不表示生产验证。

## 1. Production baseline and failure-domain assumptions

- 三个投票成员使用 Single-Primary，落在独立 host 与 rack／AZ；任失一个仍保留 2/3 quorum。
- 至少两个 Router 实例落在独立故障域；应用或 LB 实际使用两个入口。
- RPO／RTO、读一致性、failure detector、容量和 PITR 由服务 owner 签字，不从 Lab 5 秒参数照抄。
- Quorum loss is not repaired by letting both partitions accept writes.
- Compose 同宿主机、同 network、amd64 emulation 的结果是 behavioral evidence only。

## 2. Pre-deployment checklist

| 项目 | owner | check | failure consequence | evidence |
|---|---|---|---|---|
| 独立 power／host／rack 或 AZ | Infra | 三成员与 Router placement 无共同单点 | 一次物理故障失去 quorum／入口 | CMDB topology、故障域演练 |
| DNS／stable addresses | Network | 正反解、TTL、地址生命周期符合成员身份 | 成员／Router 无法重连或误连 | DNS audit、解析与 failover log |
| RTT／packet loss baseline | Network／DBA | 峰值、p99、loss 与 jitter 有基线 | 误驱逐、flow control、RTO 放大 | 连续探测 dashboard |
| TLS／certificate rotation | Security／DBA | Server、GR、Router 信任链与无中断轮换 | 组通信或客户端认证中断 | 到期告警、rotation drill |
| Secrets | Security／SRE | admin／Router／app 分权、轮换、无明文仓库 | 横向移动或全组失控 | vault policy、access audit |
| Time sync | Infra | NTP／chrony offset 受控并告警 | timeline、证书、审计失真 | offset dashboard |
| Disk durability | Storage／DBA | write cache／flush 语义、`innodb_flush_log_at_trx_commit=1`、`sync_binlog=1` 经验证 | client-confirmed SUCCESS／business result 在 power loss 后丢失；这不同于 replica receive／confirmation ACK | vendor config、power-cut test |
| Backup retention | Backup owner | 全备／增量／binlog 留存覆盖业务窗口 | 无法恢复目标时间 | catalog、retention audit |
| Restore drills | Backup owner／业务 | 隔离恢复、精确边界、数据核对与回迁演练 | 备份存在但不可用 | drill report、RTO/RPO |
| Capacity headroom | Capacity／DBA | 单成员故障时 CPU、IOPS、disk、connections 可承载 | failover 后过载、队列失控 | capacity model、load test |
| Router placement | Platform | 两实例独立，health check 与 metadata 可达 | 入口单点或同时失效 | deployment topology、chaos drill |
| App timeout／pool | App owner | bounded retry、坏连接淘汰、多 endpoint、稳定 `request_id` | 重试风暴、重复业务、长中断 | integration test、pool metrics |
| Escalation ownership | Incident commander | DBA／Network／Storage／App on-call 与决策权限明确 | 故障时无人可 fence／恢复 | roster、tabletop drill |

## 3. Build and acceptance

Lab 重现命令：

```bash
make -C mysql-handson/00-lab/ha reset
make -C mysql-handson/00-lab/ha config
make -C mysql-handson/00-lab/ha up
make -C mysql-handson/00-lab/ha verify
```

生产 acceptance 需另行证明：唯一可写 Primary、三个独立故障域、两个真实入口、durability、应用三态／对账、备份恢复、容量与每种故障的分段 RTO。Lab green 不能替代这些签字证据。

## 4. Daily observability and alert thresholds

DBA 持续采集成员 `ROLE/STATE`、唯一 Primary、GTID、`super_read_only/offline_mode`、certifier／applier queue、`COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE`、flow-control mode／threshold、rejoin／expel 和磁盘。Platform 采集每个 Router 的健康、metadata refresh、connections 与错误率；App 采集 SUCCESS／FAILURE／UNKNOWN、重连、pool exhaustion 和按 `request_id` 对账结果。

`ONLINE` necessary-not-sufficient：告警恢复必须同时看 backlog、唯一可写 Primary、Router probe、业务 ledger 与成员数据 equality。阈值来自生产 baseline；Lab 中 QUOTA 的硬证据是 applier queue 跨 active threshold，不把 optional throttle counter 当依赖。

## 5. Controlled switchover

### Trigger

计划维护、负载迁移或验证 failover readiness，已批准变更窗口。

### Symptom

无故障；目标是把唯一 Primary 从当前成员迁往已验证目标。

### First checks

确认 `3 ONLINE / 1 PRIMARY`、queue 已排空、目标资源健康、两个 Router 与应用 UNKNOWN 对账正常。

### Automatic recovery boundary

AdminAPI 完成角色切换；Router 只更新新连接目标，不搬迁旧 session。

### Human intervention boundary

选择目标、quiesce 高风险作业、观察分段 RTO；任一栅栏或数据证据异常即停止维护。

### Safe operations

保留稳定 `request_id`，允许旧连接断开并 bounded reconnect；切后运行 verifier。

### Operations that risk split-brain or divergence

绕过 AdminAPI 直接让两成员可写、忽略旧 Primary 写栅栏，或把断线请求用新业务键重放。

### Commands

Lab：`make -C mysql-handson/00-lab/ha switchover TARGET=db2`；完整演练：`make -C mysql-handson/00-lab/ha scenario SCENARIO=planned-switchover`。生产命令由 change record 绑定版本与目标，不照抄 Lab target。

### Success evidence

唯一新 Primary、旧 Primary SECONDARY／不可写、Router 新连接到新 Primary、UNKNOWN 全部对账、acknowledged business IDs 收敛；Lab measured run `planned-switchover/20260726T094213Z/`。

### Return to normal topology

恢复流量和告警，确认三成员 ONLINE、queue 清零、业务基线稳定，归档 timeline。

## 6. Rolling maintenance and upgrade

### Trigger

安全补丁、minor upgrade、OS／证书维护；兼容矩阵和 rollback 已批准。

### Symptom

逐台成员或 Router 退出服务，容量降级但仍须保有 quorum 与入口冗余。

### First checks

验证备份、版本兼容、容量 headroom、当前唯一 Primary、queue、证书和 on-call。

### Automatic recovery boundary

成员短暂返回可由 auto-rejoin 尝试；这不证明升级成功或数据可服务。

### Human intervention boundary

每批只动一个投票成员；每步 acceptance green 才进入下一步，Primary 最后或先受控切换。

### Safe operations

先 Secondary，再 Router 分批，再受控 Primary；每步检查 GTID、ONLINE、backlog、业务数据。

### Operations that risk split-brain or divergence

同时停两个投票成员、混用不兼容版本、在成员未追平时继续下一批。

### Commands

生产/operator example：使用组织批准的 deployment controller drain／upgrade 单成员；Lab 只用 `make -C mysql-handson/00-lab/ha status`、`make -C mysql-handson/00-lab/ha verify` 检查，不提供生产升级命令。

### Success evidence

每步 `3 ONLINE / 1 PRIMARY`、版本符合矩阵、queue 恢复、Router 与业务 probe green、无 missing acknowledged business IDs。

### Return to normal topology

恢复 placement 与容量、关闭变更窗口，保留每步状态、版本、GTID 和业务核对。

## 7. Primary failure with quorum

### Trigger

Primary process／host 失败，而两个成员互通并保有 2/3 quorum。

### Symptom

旧连接失败；多数派产生新 Primary；短时 FAILURE／UNKNOWN 与重连上升。

### First checks

从多数派侧确认 view、唯一 ONLINE Primary、旧成员不可写、Router 新连接目标和 UNKNOWN ledger。

### Automatic recovery boundary

GR 选主，`BEFORE_ON_PRIMARY_FAILOVER` 等 backlog，Router 更新新连接；不会迁移旧 session 或判断业务 UNKNOWN。

### Human intervention boundary

若无唯一 Primary、backlog 不降、旧 Primary 仍可写、或 acknowledged business ID 缺失，立即升级 incident 并阻止导流。

### Safe operations

应用 bounded reconnect；按原 `request_id` 查询 UNKNOWN；隔离旧成员后再诊断／rejoin。

### Operations that risk split-brain or divergence

手动解除旧 Primary `super_read_only`、绕过 Router 写旧地址、盲重试生成新业务操作。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-crash`，状态／对账：`make -C mysql-handson/00-lab/ha status` 与 `make -C mysql-handson/00-lab/ha verify`。

### Success evidence

新 Primary 唯一且可写、旧成员 fenced、Router 重连、SUCCESS 可查、UNKNOWN 已归类、成员最终一致；Lab measured run `primary-crash/20260726T095829Z/`。

### Return to normal topology

旧成员按 §12 gate 恢复，容量与队列回基线后解除 incident。

## 8. Primary partition／repeated expulsion／network flapping

### Trigger

Primary 与多数派网络分区，或成员反复 expelled／rejoin。

### Symptom

两边观察不同 view；少数派旧 Primary 应不可写，多数派可能选新 Primary；连接反复断开。

### First checks

分别从两侧采集 view、`super_read_only`、`offline_mode`、写探针、RTT／loss、交换机与主机事件。

### Automatic recovery boundary

多数派可选主；`exitStateAction=OFFLINE_MODE`／服务端栅栏限制失权成员。自动 rejoin 只有有限三次。

### Human intervention boundary

反复 flapping、无法证明旧端 fenced、或成员出现 errant GTID 时，隔离故障域并停止自动恢复。

### Safe operations

以服务端不可写和直接写探针证明 fencing；修复网络后检查 GTID 再 rejoin。

### Operations that risk split-brain or divergence

仅凭 Router 摘除／网络 ACL 就宣称 fenced，或在少数派旧 Primary 开写。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=primary-partition`。生产网络操作只能由 Network owner 按 incident change 执行。

### Success evidence

少数派直接写拒绝、多数派唯一 Primary、请求对账和最终三成员收敛；Lab measured run `primary-partition/20260726T100107Z/`。

### Return to normal topology

网络 baseline 稳定一个观察窗，成员完成 rejoin／apply／业务核对，才恢复流量资格。

## 9. Quorum loss

### Trigger

三成员中只剩一个可达，或网络切割导致任何一侧都没有多数派。

### Symptom

失去 quorum 后停止安全写；入口可能存活但请求失败／UNKNOWN。

### First checks

冻结变更，分别采集成员 view、GTID、服务端 fencing、Router／应用流量和故障域事实。

### Automatic recovery boundary

协议应 fail closed；恢复成员可能仍不能普通 rejoin，需 complete-outage 决策。

### Human intervention boundary

incident commander 决定恢复哪一 partition；必须先证明所有排除成员 fenced，并确认 GTID-superset seed。

### Safe operations

Quorum loss is not repaired by letting both partitions accept writes. 先 quiesce traffic、三成员服务端 fencing、GTID 等待与最终相等复核，再按 §13 dry-run／actual。

### Operations that risk split-brain or divergence

`forceQuorumUsingPartitionOf()` is an explicit disaster decision, not a routine recovery shortcut; first prove all excluded members are fenced. 禁止双边强开或默认 `force:true`。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=quorum-loss`。`forceQuorumUsingPartitionOf()` 只作为生产/operator disaster API 名称记录，本 Lab 正常路径不调用它。

### Success evidence

`quorum_blocked` 到 restore 前零 SUCCESS、UNKNOWN 可对账；恢复后唯一可写 Primary、Router rollback probe 与 ID equality。Lab measured run `quorum-loss/20260728T051412Z/`。

### Return to normal topology

恢复三成员、两个入口与业务流量，检查所有 fencing 临时动作撤销且配置无漂移，完成事后审计。

## 10. Slow member／flow control

### Trigger

applier queue 持续上升并跨 active QUOTA threshold，或 write latency／throughput 异常。

### Symptom

`COUNT_TRANSACTIONS_REMOTE_IN_APPLIER_QUEUE` 增长、flow control 背压；延迟不一定单调上升。

### First checks

查 mode／applier threshold、各成员 queue、apply rate、CPU／IO／disk／network 与 workload 变化。

### Automatic recovery boundary

QUOTA 限制发送速率保护慢成员；它不修复慢磁盘、资源争用或坏查询。

### Human intervention boundary

queue 不回落、容量耗尽或业务 SLO 受损时，由 DBA／Capacity owner 限流、扩容或隔离根因。

### Safe operations

先保留指标和 workload，修复资源根因；成员恢复后等待 queue 清零并做数据 equality。

### Operations that risk split-brain or divergence

为消除告警盲目调高 threshold、关闭 flow control，或把成员 ONLINE 当作已追平。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=slow-member`；查询使用[指南 §9](README.md#9-观测成员队列flow-control-与-router)的实际 Performance Schema SQL。

### Success evidence

QUOTA mode 下 queue 跨 threshold 的因果窗口、恢复后 queue／成员数据收敛。Lab measured run `slow-member/20260728T052238Z/`；p95 仅观察值。

### Return to normal topology

资源与 queue 保持基线一个观察窗，撤销临时限流并记录容量决策。

## 11. Router outage

### Trigger

一个 Router process／host／network path 不可用。

### Symptom

绑定该入口的连接失败；另一入口应继续新建连接，数据库 topology 不一定变化。

### First checks

分别探测两个 Router、metadata connectivity、LB endpoint、连接池 endpoint 使用和数据库唯一 Primary。

### Automatic recovery boundary

Router 不互相迁移连接；应用／LB 只有配置并使用替代 endpoint 才会恢复。

### Human intervention boundary

若两个入口同域或应用只用单 endpoint，Platform／App owner 立即修正导流并控制 retry storm。

### Safe operations

摘除坏入口，保留原 `request_id`，经健康入口 bounded reconnect 并核对 UNKNOWN。

### Operations that risk split-brain or divergence

把 Router failure 当数据库 failover 手动切主，或无限快速重连耗尽连接。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=router-failure`；单入口 shell 为 `make -C mysql-handson/00-lab/ha mysql-a`／`make -C mysql-handson/00-lab/ha mysql-b`。

### Success evidence

Router B 在 A outage 窗仍有 SUCCESS、Cluster 未不必要切主、UNKNOWN 已对账；Lab measured run `router-failure/20260728T052430Z/`。

### Return to normal topology

重建坏 Router，确认 metadata／TLS／health check，再渐进加入 LB；观察连接与错误率。

## 12. Member cannot rejoin

### Trigger

auto-rejoin 耗尽、成员 ERROR／OFFLINE、GTID 缺口／分叉或本地数据不可信。

### Symptom

mysqld 可 ping 但成员不 ONLINE，queue／GTID 不收敛；Cluster 可能仍以 2/3 服务。

### First checks

成员 state、error log、GTID set／errant transaction、donor binlog 保留、disk、网络和 Clone 容量。

### Automatic recovery boundary

`autoRejoinTries=3` 只覆盖短暂故障；成功返回进程不等于可以服务。

### Human intervention boundary

DBA 选择 rejoin、incremental、Clone 或重建；任何 GTID divergence／corruption 要 fail closed。

### Safe operations

A rejoining member does not serve traffic until state, backlog and business data are verified. 先 fencing，选择可信 donor，恢复后做三层 gate。

### Operations that risk split-brain or divergence

因为端口可达就导流、跳过 errant GTID 检查，或 Clone 自错误 donor。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=member-rejoin`。生产 `rejoinInstance()`／Clone 是经 GTID 与 donor 审核后的 operator action，不是自动复制本文字符串。

### Success evidence

`rejoin_begin < rejoin_online`、最终 `3 ONLINE / 1 PRIMARY`、两个 UNKNOWN 均对账为 committed、三成员业务 request ID 集相同；Lab measured run `member-rejoin/20260728T052648Z/`。

### Return to normal topology

观察成员稳定、恢复 placement／告警，确认无临时绕路与配置漂移。

## 13. Complete Cluster outage

### Trigger

所有成员停止或组状态无法通过普通 rejoin 恢复。

### Symptom

没有 ONLINE Primary，Router 无 RW destination；各成员可能保有不同 GTID 进度。

### First checks

quiesce Router／应用；采集每成员 GTID、fencing、start-on-boot、业务 IDs、故障根因与备份状态。

### Automatic recovery boundary

没有普通自动 failover；需要 operator 选择安全 seed 并执行 AdminAPI reboot。

### Human intervention boundary

DBA 与 incident commander 只在证明 seed 为 GTID-superset、所有成员 fenced 后批准 actual reboot。

### Safe operations

`dba.rebootClusterFromCompleteOutage()` runs with `dryRun:true` first and selects a GTID-superset seed; `force:true` is not the default path. dry-run 报告通过才 actual，之后检查唯一可写 Primary、Router rollback probe 和 ID `cmp -s`。

### Operations that risk split-brain or divergence

从落后 seed 启动、跳过 fresh GTID equality、默认 `force:true`、客户端未停写时停止 GR。

### Commands

Lab 唯一入口：`make -C mysql-handson/00-lab/ha recovery-complete-outage`，内部调用 [`bootstrap/reboot.js`](../../00-lab/ha/bootstrap/reboot.js)。生产需把同样 gates 接入组织审批与审计。

### Success evidence

Task 9 supporting measured drill 位于本机 Git-ignored `evidence/complete-outage/`：outage `2026-07-26T13:39:50.368282+00:00`、dry-run `13:39:59.842044`、actual `13:40:01.782459`、verified `13:40:16.350305`；before／after IDs byte-equal、`3 ONLINE / 1 writable PRIMARY`、Router rollback 未留行。它**不是八个核心 Scenario 之一**，也不是生产 RTO 证明。

### Return to normal topology

恢复每成员原 start-on-boot 值、两个 Router 和受控流量；验证业务数据、队列和配置后关闭 outage。

## 14. Accidental delete／logical corruption／PITR

### Trigger

已合法提交并复制的误删、错误更新或逻辑损坏。

### Symptom

错误状态出现在所有在线成员；failover 后仍错误。

### First checks

停止扩大损害，记录 destructive transaction／binlog boundary、备份坐标、受影响 invariant 和在线 Cluster 状态。

### Automatic recovery boundary

Group Replication 只复制当前状态，不能撤销合法事务；HA failover 无历史版本。

### Human intervention boundary

Backup owner／DBA／业务 owner 选择恢复点、隔离 target、验证数据和回迁／回滚方案。

### Safe operations

Logical corruption is restored to an isolated target from backup plus binlog; it is not fixed by failover. 以备份内 source coordinate 起点和精确 stop position 重放，隔离核对。

### Operations that risk split-brain or divergence

直接覆盖在线 Cluster、用时间戳代替精确日志边界、未核对就导流，或把更多副本当备份。

### Commands

Lab：`make -C mysql-handson/00-lab/ha scenario SCENARIO=ha-cannot-replace-pitr`；实现和边界见[核心 Scenario 08](scenarios/08-ha-cannot-replace-pitr.md)。生产恢复工具链由 Backup owner 管理。

### Success evidence

误删确实到三成员；isolated recovery 在 destructive transaction 前恢复完整 projection，在线 Cluster 未被覆盖。Lab measured run `ha-cannot-replace-pitr/20260728T062708Z/`。

### Return to normal topology

业务签字恢复数据，执行停写／差异核对／切回／回滚计划；保存备份、日志边界与审计链。

## 15. Regular drills and evidence retention

至少按季度或重大版本／拓扑变更后演练八个核心 Scenario，并单独演练 complete-outage recovery；PITR 频率须满足备份风险。每次从已声明 clean state 开始，保留版本／配置 hash、故障注入、UTC timeline、请求三态、UNKNOWN reconciliation、分段 RTO、成员／Router 状态、GTID、business ID equality、operator 与审批。

Lab archive 路径及成功 run ID 在[指南 §12](README.md#12-八个核心-scenario-学习顺序)。本机 Git-ignored evidence 可用于复现，但不是集中审计存储；生产证据应写入不可变、受权限和 retention 管理的系统。失败演练不能被最新一次 PASS 覆盖，架构推理也不能标为 measured proof。
