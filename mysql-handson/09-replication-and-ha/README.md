# 主从复制与高可用

## 1. 核心问题

主从复制解决三件事：**(a)** 数据冗余 + 故障恢复（主库挂了，提升从库）；**(b)** 读写分离（读流量分散到从库）；**(c)** 备份不影响主库。本章解决：

- binlog 怎么从主库"飞"到从库，中间有几个线程、哪个容易成为瓶颈
- 为什么会有主从延迟，怎么定位
- 异步 / 半同步 / MGR 三种模式分别在什么场景用
- GTID 和位点（binlog file + position）切换有什么差异
- 读写分离的"读自己的写"陷阱怎么破

## 2. 直觉理解

把主库想成一个**「主作者」**，从库是**「抄写员」**，binlog 是主作者每写一笔就寄出去的**「手稿副本」**。

**异步复制**（默认）：主作者写完就扔出去，不等抄写员回信。抄写员慢了、网断了，主作者完全不知道。好处：主库写入延迟最低；坏处：主库宕机时抄写员可能还没抄完，数据就丢了。

**半同步**：主作者写完后，必须等**至少一个抄写员回信说「我收到了」**，才算这笔稿子发完。等了 10 秒（默认超时）没回信，退化成异步。好处：主库宕机时那份收到回信的从库一定有最新数据；坏处：每次写入多一个网络 RTT。

**MGR（Group Replication）**：三个人（或更多）坐在一个投票房间里，**写一笔要超过半数人点头才真正写下去**（Paxos 类协议）。好处：真正强一致；坏处：写入性能随节点数下降，网络抖动就会触发流控或重新选主。

> 面试一句话区分：**异步 = 发完不等回执；半同步 = 至少一个回执才算完；MGR = 多数票通过才写**。

## 3. 原理深入

### 3.1 三线程模型（dump / IO / SQL）+ relay log

```
主库                        从库
─────────────────────       ─────────────────────────────────────
  binlog file ──┐            ┌── relay log file ──┐
                │            │                    │
           [dump thread] ──→ [IO thread]      [SQL thread / MTS workers]
                                                   │
                                              InnoDB 存储引擎
```

**主库 dump thread**：每个从库连接对应一个 dump thread。从库发起 `COM_REGISTER_SLAVE` + `COM_BINLOG_DUMP` 之后，dump thread 负责按位点（或 GTID）读 binlog 并推给从库。一个主库有 N 个从库就有 N 个 dump thread，这是主库的 CPU / IO 隐性开销。

**从库 IO thread**：接收 dump thread 推来的 binlog event，写到**本地 relay log**（格式和 binlog 几乎相同）。写成功后向主库回 ACK（半同步的 ACK 也在这一步）。IO thread 几乎不会成为瓶颈，它只是网络搬运工。

**从库 SQL thread**：读 relay log，把事件重放（apply）到 InnoDB。**5.7 之前默认单线程**：从库永远是串行 apply，主库并发写入有多快都得排队，这是主从延迟最常见的根因。

**MTS（Multi-Threaded Slave/Replica，8.0 默认开启）**：SQL thread 变成 coordinator，把 relay log 里的事务分发给 worker pool 并行执行。分发策略由 `replica_parallel_type` 控制：

| `replica_parallel_type` 值 | 策略 | 适用场景 |
|---|---|---|
| `DATABASE`（5.7 默认）| 按 schema 分发，不同 DB 并行 | 多 DB 写入均匀时有效 |
| `LOGICAL_CLOCK`（8.0 默认）| 同一 binlog group commit 里的事务并行 | 单 DB 高并发写入时效果好 |

`replica_parallel_workers`（8.0 默认 4，建议 8-16，不要超过主库并发连接数）控制 worker 数量。

**relay log 清理**：SQL thread apply 完成后自动清理，或由 `relay_log_purge=ON`（默认）控制。relay log 满（`max_relay_log_size`，默认 0 即与 `max_binlog_size` 同，默认 1GB）会自动轮转新文件。

### 3.2 binlog 格式对复制的影响

`binlog_format` 有三种，复制层面最重要的是 **ROW**（8.0 默认）。

| 格式 | 内容 | 复制安全 | 大小 | 注意事项 |
|---|---|---|---|---|
| `STATEMENT` | SQL 语句原文 | **危险**：`NOW()`、`RAND()`、`UUID()` 在从库执行结果不同 | 最小 | 5.7 前老环境遗留，新项目不要用 |
| `ROW` | 每行变更前后的实际数据 | **安全**：精确记录哪行变成什么 | 最大（大批量 UPDATE 会爆 binlog）| 8.0 默认，推荐 |
| `MIXED` | 自动选 STATEMENT / ROW | 比 STATEMENT 略安全 | 中等 | 仍有边界情况不一致，避免用于新架构 |

**ROW 格式下的 `binlog_row_image`**：
- `FULL`（默认）：记录整行 before + after，最安全，最大
- `MINIMAL`：只记录变更列 + 主键，能显著减少 binlog 大小
- `NOBLOB`：不记录未变更的 BLOB 列

> 实战：大批量 `DELETE` + ROW 格式会导致 binlog 暴涨。可临时改 `SET SESSION binlog_row_image='MINIMAL'` 或拆分批次（`LIMIT 1000` 一批）。

### 3.3 GTID 复制 vs 位点复制

#### 位点复制（传统方式）

从库用 `binlog file + position` 记录"我复制到哪了"：

```sql
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='primary',
  SOURCE_USER='repl',
  SOURCE_PASSWORD='xxx',
  SOURCE_LOG_FILE='binlog.000023',
  SOURCE_LOG_POS=4109284;
START REPLICA;
```

切主时必须人工找到新主库对应的正确位点（或用 `MASTER_AUTO_POSITION=0` + 手动 `mysqlbinlog` 对齐），容易出错。

#### GTID 复制（MySQL 5.6+ 推荐）

**GTID = `server_uuid:transaction_id`**，每个事务全局唯一标识。从库记录"我已经执行了哪些 GTID 集合"（`gtid_executed`），主库知道"哪些 GTID 我还没发给你"，自动算差集。

开启条件：
```ini
# my.cnf（主从都要加）
gtid_mode         = ON
enforce_gtid_consistency = ON
```

切换新主库（GTID 模式下）：
```sql
-- 在新从库（准备提升为主或切到新主）上执行
STOP REPLICA;
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='new-primary',
  SOURCE_USER='repl',
  SOURCE_PASSWORD='xxx',
  SOURCE_AUTO_POSITION=1;   -- 关键：让从库自动用 GTID 算位点差集
START REPLICA;
```

验证 GTID 同步状态：
```sql
-- 在从库查
SHOW REPLICA STATUS\G
-- 关注：
--   Executed_Gtid_Set   从库已执行的 GTID 集合
--   Retrieved_Gtid_Set  IO thread 已拉到的 GTID 集合
--   两者差 = "已拉未执行"（relay log 积压）

-- 在主库查
SELECT @@global.gtid_executed;   -- 主库已提交的 GTID 集合
```

**GTID 的限制**：
- 不能在事务内执行 `CREATE TABLE ... SELECT`（MySQL 8.0.21 前）
- 不支持 `CREATE TEMPORARY TABLE`（在 RBR 模式可绕过，但要注意）
- `gtid_mode` 变更需要滚动重启（`OFF` → `OFF_PERMISSIVE` → `ON_PERMISSIVE` → `ON`），不能直接切

| 维度 | 位点复制 | GTID 复制 |
|---|---|---|
| 切主难度 | 高（手工找位点） | 低（`SOURCE_AUTO_POSITION=1`） |
| 容灾恢复 | 复杂 | 简单（备份里有 GTID 集合） |
| 监控/审计 | 看 file + pos | 看 GTID 集合差集 |
| 限制 | 无 | 部分 DDL 不支持 |
| 推荐 | 老系统维护 | **新项目都用 GTID** |

### 3.4 异步 / 半同步 / MGR 三档对比表

| 维度 | 异步复制 | 半同步复制 | MGR |
|---|---|---|---|
| **数据持久性（主库 crash）** | 可能丢失（从库 ACK 前 crash 则丢）| 至少 1 个从库有数据（lossless 模式）| 多数节点确认，不丢 |
| **写延迟** | 最低（不等 ACK） | +1 RTT（等 ACK，通常 1-5ms） | +1 RTT + Paxos 协议开销 |
| **读一致性** | 弱（从库可能落后） | 弱（从库落后但有上限）| 强（单主单写模式）|
| **故障切换** | 手动或 MHA | 手动或 MHA | **自动**（原生选主）|
| **部署复杂度** | 低 | 低 | 高（至少 3 节点，需要 group_replication 插件）|
| **适用场景** | 读多写少，允许少量数据丢失的报表/分析 | 金融/交易核心，可接受极小写延迟增加 | 需要自动 HA + 强一致的核心业务 |
| **MySQL 版本** | 所有版本 | 5.5+ 插件，5.7+ 内置 lossless | 5.7.17+ |

### 3.5 半同步 lossless 模式

**5.7 之前（lossy，AFTER_COMMIT 模式）**：

```
主库写 binlog → 提交事务（storage engine commit） → 等从库 ACK → 返回客户端
```

问题：主库 commit 之后、等到 ACK 之前宕机。这时从库没 ACK，主库上事务已提交，**但从库没收到 binlog**。新主选这个从库会丢事务。

**5.7+ lossless（AFTER_SYNC 模式，默认）**：

```
主库写 binlog → 等从库 ACK（binlog 落盘但还没 commit）→ commit → 返回客户端
```

关键差异：**ACK 在 storage engine commit 之前**。主库 crash 时：若从库已 ACK，从库有数据，新主切换安全；若从库未 ACK，主库 binlog 里有但没提交，重启后回滚，不丢。

相关参数：

```ini
# 主库（插件名 MySQL 8.0.26 前叫 rpl_semi_sync_master_*，之后改名）
plugin-load-add = semisync_source.so
rpl_semi_sync_source_enabled          = 1
rpl_semi_sync_source_wait_for_replica_count = 1        # 等几个从库 ACK，默认 1
rpl_semi_sync_source_timeout          = 10000          # 超时 ms，默认 10s，超时退化异步
rpl_semi_sync_source_wait_point       = AFTER_SYNC     # lossless 模式，默认

# 从库
plugin-load-add = semisync_replica.so
rpl_semi_sync_replica_enabled         = 1
```

**超时退化**：如果从库因为网络抖动没有在 10s 内 ACK，主库自动降级为异步，日志里会出现 `Semi-sync replication switched OFF` 警告。监控应对这个告警做报警。

### 3.6 MGR 简述（Paxos / 单主多主 / 流控）

**MGR 的一致性协议**：基于 **Paxos 变种（MySQL 内部叫 XCom）**，写入时每个事务先广播给组内所有成员，超过半数确认（`(N/2)+1` 个节点响应）后才能提交。冲突检测在广播阶段进行，多主模式下同一行被两个节点并发修改时，后提交的事务回滚。

**单主 vs 多主模式**：

| | 单主（Single-Primary）| 多主（Multi-Primary）|
|---|---|---|
| 写入节点 | 只有 primary 可写 | 所有节点均可写 |
| 冲突 | 无（单写入点）| 有（需要冲突检测 + 回滚）|
| 推荐度 | **官方推荐** | 慎用（回滚增加应用复杂度）|
| 切主 | 自动选主（基于权重 + 最新事务）| N/A |

**流控（Flow Control）**：MGR 有内置流控机制，当某个节点 apply 队列积压超过 `group_replication_flow_control_applier_threshold`（默认 25000 个事务）时，会发出 flow control 消息，让写入节点降速。表现：写入突然变慢，日志出现 `[GCS] Certification garbage collection` 或 flow control 告警。处理方式：提高从节点硬件 / 减少写入量 / 调高阈值（治标）。

**MGR 最小部署**：3 节点（奇数，保证多数票），推荐用 MySQL Shell 的 `dba.createCluster()` 配置（InnoDB Cluster 方式）。

```ini
# my.cnf 关键配置
group_replication_group_name           = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"  # UUID，整组一样
group_replication_start_on_boot        = ON
group_replication_local_address        = "node1:33061"
group_replication_group_seeds          = "node1:33061,node2:33061,node3:33061"
group_replication_bootstrap_group      = OFF   # 只有第一个节点初始化时临时设为 ON
```

### 3.7 读写分离三种方案对比

读写分离核心：写 → 主库，读 → 从库。三种实现方式各有取舍：

#### 方案 A：应用层（ShardingSphere / MyCAT / GORM 插件）

应用代码或 ORM 配置主从 DataSource，读操作用 `@ReadOnly` 或路由注解走从库连接池。

**ShardingSphere-JDBC 示例**（Java）：
```yaml
# application.yml
spring:
  shardingsphere:
    datasource:
      names: primary,replica0,replica1
    rules:
      readwrite-splitting:
        data-sources:
          my-ds:
            write-data-source-name: primary
            read-data-source-names: replica0,replica1
            load-balancer-name: round-robin
```

| 优点 | 缺点 |
|---|---|
| 无需额外组件，部署简单 | 侵入应用代码；多语言需多套实现 |
| 可以精细控制哪条 SQL 走哪里 | 连接池分散在每个应用实例 |

#### 方案 B：中间件代理（ProxySQL）

在应用和 MySQL 之间加一层代理，按 SQL 类型自动路由：`SELECT` → 从库，`INSERT/UPDATE/DELETE` → 主库。

**ProxySQL 关键配置**：
```sql
-- 在 ProxySQL Admin 里执行
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (1,'primary',3306);
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (2,'replica0',3306);
INSERT INTO mysql_servers(hostgroup_id, hostname, port) VALUES (2,'replica1',3306);

-- 写到 hostgroup 1，读到 hostgroup 2
INSERT INTO mysql_query_rules(rule_id,active,match_digest,destination_hostgroup,apply)
  VALUES (1,1,'^SELECT.*FOR UPDATE',1,1),  -- SELECT FOR UPDATE 仍走主
         (2,1,'^SELECT',2,1);
LOAD MYSQL SERVERS TO RUNTIME; SAVE MYSQL SERVERS TO DISK;
```

| 优点 | 缺点 |
|---|---|
| 对应用透明，无侵入 | 多一个故障点；运维成本 |
| 支持连接池复用，连接数管理好 | ProxySQL 本身需 HA 部署（两个实例 + Keepalived）|
| 可做查询重写、SQL 限流、黑名单 | |

#### 方案 C：JDBC Replication Driver（ConnectorJ）

MySQL Connector/J 内置的 `jdbc:mysql:replication://` 协议，`autocommit=true` 的 `SELECT` 自动走从库，事务内或写操作走主库。

```java
// JDBC URL
jdbc:mysql:replication://primary:3306,replica0:3306,replica1:3306/mydb
  ?allowSourceDownConnections=true
  &readFromSourceWhenNoReplicas=true
```

适合 Java 单体应用快速上手，但对连接管理控制粒度有限，生产多用 ProxySQL 代替。

#### 三方案对比总结

| 维度 | 应用层（ShardingSphere 等）| ProxySQL | JDBC ReplicationDriver |
|---|---|---|---|
| 应用侵入 | 高 | **无** | 低 |
| 运维复杂度 | 低 | 中（需额外 HA）| 低 |
| 连接数管理 | 差（每实例独立池）| **好**（统一代理池）| 中 |
| SQL 粒度控制 | 高 | 高 | 低 |
| 适用规模 | 中小 | **中大型生产** | 小型 / 原型 |

### 3.8 主从延迟原因 + 定位手段

#### 主从延迟的六大原因

1. **大事务**：单个事务修改 100 万行（如全表 UPDATE），主库一次提交，从库 SQL thread 要串行 apply 100 万行操作，期间积压所有后续事务。

2. **长 DDL**：`ALTER TABLE` 在主库是 Online DDL（可能只锁几秒），但 binlog 里记录的是整个 DDL 语句，从库 apply 时也要走 DDL，且可能锁整张表——从库延迟 = DDL 执行时间。

3. **主库写入压力**：主库 TPS 高（1 万事务/秒），从库 SQL thread 单线程 apply 上限约 2000-5000 事务/秒（取决于硬件），积压无可避免。解决：开 MTS（`replica_parallel_workers=8`）。

4. **从库硬件慢**：从库 CPU 低、磁盘 IOPS 低（如主库用 NVMe，从库用 SATA HDD），apply 速度追不上。

5. **网络**：主从跨机房或带宽打满时，IO thread 拉 binlog 慢，relay log 积压晚，SQL thread 再快也没原料。

6. **从库上有慢查询**：从库既被读流量打，又要 apply relay log，CPU 争抢，apply 变慢。

#### 定位手段

**第一步：`SHOW REPLICA STATUS\G`**

```
关键字段解读：

Slave_IO_Running: Yes           -- IO thread 正常运行
Slave_SQL_Running: Yes          -- SQL thread 正常运行（No = apply 出错，看下面的 Error）
Seconds_Behind_Source: 47       -- 估算延迟秒数（注意：这是估算！）
Last_SQL_Error: ...             -- SQL thread 报错原因（如主键冲突、行不存在）
Exec_Master_Log_Pos: 12345678   -- SQL thread 已执行到的主库 binlog 位点
Read_Master_Log_Pos: 12456789   -- IO thread 已读到的位点
-- 两者差 = relay log 积压量（字节）
Retrieved_Gtid_Set: xxx
Executed_Gtid_Set: yyy          -- GTID 差集 = 还未 apply 的事务
```

`Seconds_Behind_Source` **为什么不准确**：它的计算方式是 `(当前时间) - (relay log 里当前正在 apply 的事件的 timestamp)`。如果 SQL thread 卡在一个大事务里，这个值会反映大事务开始的时间差，不反映真实队列深度。relay log 有积压但 SQL thread 正在执行大事务时，`Seconds_Behind_Source` 可能表现为平稳，不报警——很容易误判。

**第二步：`pt-heartbeat`（更准确）**

Percona Toolkit 的 `pt-heartbeat` 在主库定时写一个心跳时间戳到专用表，从库测量这个时间戳和当前时间差：

```bash
# 主库：后台运行心跳写入
pt-heartbeat --host=primary --user=root --password=xxx \
  --database=test --create-table --update --daemonize

# 从库：监控延迟（每 0.5 秒采样一次）
pt-heartbeat --host=replica --user=root --password=xxx \
  --database=test --monitor --interval=0.5
```

输出：`0.50s [  0.50s,  0.47s,  0.48s ]`（当前值 + 滑动平均）。比 `Seconds_Behind_Source` 准确，可配 Prometheus 告警阈值。

**第三步：定位是哪类大事务**

```sql
-- 在从库查当前 SQL thread 在 apply 什么
SHOW PROCESSLIST;  -- 找 system user（SQL thread），看 State 和 Info

-- 或查 performance_schema
SELECT * FROM performance_schema.replication_applier_status_by_worker\G
-- 看 APPLYING_TRANSACTION_ORIGINAL_COMMIT_TIMESTAMP 
-- 和 APPLYING_TRANSACTION_START_APPLY_TIMESTAMP 的差值
```

### 3.9 写后立即读问题（"读自己的写"，Read Your Writes）

**问题描述**：用户下单（写主库） → 立即查订单状态（读从库）→ 从库延迟 2 秒 → 用户看到"订单不存在"。

这是读写分离的经典陷阱，有四种应对策略：

#### 策略 1：写后强制路由主库（推荐）

在写操作之后的一段时间内（或同一请求上下文内），所有读也走主库。

实现方式：
- **Session 标记**：写操作后在请求 context 或 Redis Session 里打标记（如 `last_write_ts=now`），中间件读到标记则路由主库。ProxySQL 支持 `SET @routing=master` 会话变量。
- **ShardingSphere** 支持 `Hint` 强制走主库：`HintManager.getInstance().setMasterRouteOnly()`

```java
// ShardingSphere Hint 示例
try (HintManager hintManager = HintManager.getInstance()) {
    hintManager.setWriteRouteOnly();    // 这次 SELECT 走主库
    return orderRepository.findById(orderId);
}
```

**缺点**：主库读流量增加，但窗口期短（通常 1-5s），可接受。

#### 策略 2：主键 Cookie / Token

返回给客户端一个"写入版本号"（可以是 GTID 或自增 ID），下次读请求带上这个版本号。中间件检查从库是否已 apply 到这个版本：

```sql
-- 检查从库是否已追上
SELECT WAIT_FOR_EXECUTED_GTID_SET('uuid:1-12345', 1);  -- 等最多 1 秒
-- 返回 0 = 已追上，1 = 超时
```

`WAIT_FOR_EXECUTED_GTID_SET()` 是 MySQL 内置函数，可在读请求时调用，追上了就从从库读，超时就走主库。

#### 策略 3：半同步保证（高要求场景）

lossless 半同步保证写操作返回时，**至少一个从库**已收到 binlog。如果读请求路由到的就是这个从库，则读到写。但：多个从库时无法保证路由到哪个 ACK 过的从库，且延迟仍存在（只是"量"更小）。

#### 策略 4：接受最终一致性 + UX 补偿

对一致性要求不高的场景（如点赞数、阅读量）：接受短暂不一致 + 前端乐观更新（先在本地显示写入结果，后台异步刷新）。

| 策略 | 一致性保证 | 主库压力 | 实现复杂度 |
|---|---|---|---|
| 写后路由主库 | 强 | 增加 | 低 |
| 主键 Cookie + WAIT_FOR_EXECUTED_GTID_SET | 精确 | 不增加 | 中 |
| 半同步保证 | 近强（有概率）| 不增加 | 低（配置层）|
| 最终一致 + 乐观 UI | 无 | 不增加 | 低 |

## 4. 日常开发应用

**建表和 DML 设计**
- 避免单个事务超过 100MB binlog。大批量 `DELETE / UPDATE` 拆成 `LIMIT 1000` 的循环，每次 commit 一次，减少从库 apply 积压。
- 不要在业务高峰期跑 `ALTER TABLE`。用 `pt-online-schema-change` 或 MySQL 8.0 的 Instant ADD COLUMN，binlog 里记录的是 row 变更而非全表 DDL，从库 apply 代价低得多。

**复制监控报警要配哪些**
- `Seconds_Behind_Source > 30`：延迟告警（初级，不准确但快）
- `pt-heartbeat` 检测延迟 > 5s：精确延迟告警
- `Slave_IO_Running = No` 或 `Slave_SQL_Running = No`：复制中断告警（P0）
- `Semi_sync_master_status = OFF`：半同步降级为异步告警（P1）
- MGR 节点数 < 3：告警（失去多数票能力）

**GTID 是否要开**
- **新项目：一定开**。`gtid_mode=ON + enforce_gtid_consistency=ON`，切主容灾时省去 90% 的操作复杂度。
- **老项目迁移**：按 `OFF → OFF_PERMISSIVE → ON_PERMISSIVE → ON` 滚动升级，不停机可做，但要验证应用里有没有 GTID 不支持的 DDL（`CREATE TABLE ... SELECT`）。

**读写分离中间件选型**
- 团队人手少 + Java 栈 → ShardingSphere-JDBC，配置简单，不用维护代理
- 异构语言 + 大规模 + 需要连接池聚合 → ProxySQL，功能丰富，但需要额外运维

## 5. 调优实战

### Case A：主从延迟突然飙到 100s，怎么排查

```
步骤：

1. 先确认复制是否仍在运行
   SHOW REPLICA STATUS\G
   -- 看 Slave_IO_Running / Slave_SQL_Running 都是 Yes
   -- 如果有 No，先看 Last_Error

2. 看 Seconds_Behind_Source 的变化趋势（是在涨还是在降）
   -- 在涨 = SQL thread 追不上；在降 = 只是高峰过去了

3. 找大事务
   -- 在主库查刚才写了什么
   mysqlbinlog --base64-output=decode-rows -v binlog.000023 | grep -A5 "# at" | head -100
   -- 或用 pt-query-digest 分析 binlog：
   mysqlbinlog binlog.000023 | pt-query-digest --type=binlog

4. 查从库 MTS 状态
   SELECT * FROM performance_schema.replication_applier_status_by_worker\G
   -- 看是否有 worker 卡住、error_message

5. 如果是 DDL 导致
   -- 查主库当时执行了什么 DDL
   -- 从库只能等，或用 pt-osc 重跑（有风险）

6. 如果是持续高 TPS 追不上
   -- 检查 replica_parallel_workers 是否已开 MTS
   SHOW VARIABLES LIKE 'replica_parallel_workers';
   -- 调大：SET GLOBAL replica_parallel_workers = 8;
   --（不需要重启，立即生效，但可能需要 STOP REPLICA SQL_THREAD; START REPLICA SQL_THREAD;）

7. 如果从库硬件不够
   -- iostat -x 1 / vmstat 1 查 IO 和 CPU
   -- 从库升级硬件或减少从库读流量（多加一个从库分担）
```

### Case B：切主流程（计划内切换）

**前提**：半同步开启，主从延迟 < 1s。

```bash
# 步骤 1：停止主库写入（让从库追上）
# 在主库执行：
mysql -e "FLUSH TABLES WITH READ LOCK;"  # 全局读锁
# 或更优雅：在应用层停止写流量（切流量到新主 VIP 之前）

# 步骤 2：确认从库追上
# 在从库：
mysql -e "SHOW REPLICA STATUS\G" | grep Seconds_Behind_Source
# 等到 = 0

# 步骤 3：在从库停止复制，提升为主库
mysql -e "STOP REPLICA;"
mysql -e "RESET REPLICA ALL;"  # 清除从库身份
# my.cnf 里去掉 read_only / super_read_only（或动态改）
mysql -e "SET GLOBAL read_only=0; SET GLOBAL super_read_only=0;"

# 步骤 4：其他从库切到新主库
mysql -e "CHANGE REPLICATION SOURCE TO SOURCE_HOST='new-primary', SOURCE_AUTO_POSITION=1; START REPLICA;"

# 步骤 5：应用层切 VIP / DNS 到新主库

# 步骤 6：解开老主库的读锁（如果还活着），变为从库
mysql -e "UNLOCK TABLES;"
mysql -e "CHANGE REPLICATION SOURCE TO SOURCE_HOST='new-primary', SOURCE_AUTO_POSITION=1; START REPLICA;"
```

### Case C：紧急切主（主库宕机，无法等待）

**风险**：如果是异步复制，可能有事务丢失。

```bash
# 步骤 1：选延迟最小的从库（Seconds_Behind_Source 最小 / Executed_Gtid_Set 最大）
# 在每个候选从库查：
mysql -e "SHOW REPLICA STATUS\G" | grep -E "Seconds_Behind|Executed_Gtid"

# 步骤 2：在选中的从库，确认复制已停（主库宕了 IO thread 会自动断）
mysql -e "STOP REPLICA;"

# 步骤 3：提升为主库
mysql -e "RESET REPLICA ALL;"
mysql -e "SET GLOBAL read_only=0; SET GLOBAL super_read_only=0;"

# 步骤 4：其他从库切过来
mysql -e "CHANGE REPLICATION SOURCE TO SOURCE_HOST='emergency-new-primary', SOURCE_AUTO_POSITION=1; START REPLICA;"

# 步骤 5：应用层切流量

# 步骤 6：事后核查数据丢失
# 比较 old_primary 的 gtid_executed（如果能拿到 binlog）
# 和 new_primary 的 gtid_executed 差集 = 丢失的事务
```

> 建议：核心业务用**半同步 lossless + `rpl_semi_sync_source_wait_for_replica_count=1`**，紧急切主时选收到 ACK 的从库，丢失风险降到几乎为零。

### Case D：MGR 节点离群（UNREACHABLE / ERROR 状态）

```sql
-- 查 MGR 组成员状态
SELECT MEMBER_HOST, MEMBER_PORT, MEMBER_STATE, MEMBER_ROLE
FROM performance_schema.replication_group_members;

-- 正常输出：
-- MEMBER_STATE = ONLINE，一个 PRIMARY，其余 SECONDARY
-- 异常：UNREACHABLE（网络断，其他节点视角）/ ERROR（本节点 apply 出错）
```

**处理流程**：

1. **UNREACHABLE**：网络分区或节点宕机。其他节点会等待 `group_replication_member_expel_timeout`（默认 5s）后将其踢出组。若剩余 ONLINE 节点 ≥ `(N/2)+1` 则组继续工作。若 < 则整组停止写入（Split Brain 保护）。

2. **ERROR 状态**：节点 apply relay log 出错（如主键冲突）。查 `replication_applier_status_by_worker` 找原因。修复后：
   ```sql
   STOP GROUP_REPLICATION;
   -- 修复数据冲突（手动或 skip）
   SET GLOBAL group_replication_recovery_get_public_key=ON;
   START GROUP_REPLICATION;
   -- 节点会自动 rejoin，通过 distributed recovery 追上差距
   ```

3. **网络恢复后节点重新加入**：MGR 支持 distributed recovery，节点自动从其他成员同步缺失的事务（通过 binlog 或 clone plugin），无需手动导数据。

## 6. 面试高频考点

### 必考对比

| 维度 | 异步复制 | 半同步（lossless）| MGR |
|---|---|---|---|
| 主库 crash 会丢数据吗 | 可能（从库未 ACK 的事务丢）| **不会**（ACK 在 commit 前）| 不会 |
| 写性能影响 | 无 | +1 RTT（约 1-5ms）| +协议开销（约 2-10ms）|
| 自动故障切换 | 不支持（需 MHA 等）| 不支持（需 MHA 等）| **原生支持** |
| 部署最低节点数 | 1 主 1 从 | 1 主 1 从 | **3 节点** |
| 适用业务 | 报表、大数据同步 | 金融交易核心 | 高可用 OLTP |

### GTID vs 位点 — 三句话答法

1. GTID 给每个事务打全局唯一标签，从库记录"已执行 GTID 集合"，切主时只需 `SOURCE_AUTO_POSITION=1`，自动计算差集，不用手工找 file + pos。
2. 位点复制靠 binlog 文件名 + 偏移量定位，切主时必须手工或借助工具对齐位点，容易出错。
3. 新项目一定用 GTID；老项目迁移按 `OFF→OFF_PERMISSIVE→ON_PERMISSIVE→ON` 四步滚动完成。

### SHOW REPLICA STATUS 关键字段解读

| 字段 | 含义 | 异常时怎么看 |
|---|---|---|
| `Slave_IO_Running` | IO thread 是否运行 | No = 主库连不上或网络断，看 `Last_IO_Error` |
| `Slave_SQL_Running` | SQL thread 是否运行 | No = apply 出错，看 `Last_SQL_Error`（通常是主键冲突 / 行不存在）|
| `Seconds_Behind_Source` | 估算延迟（秒）| > 30 就要关注；单靠这个不够准确，结合 pt-heartbeat |
| `Master_Log_File / Read_Master_Log_Pos` | IO thread 已读到主库 binlog 的位点 | 与主库 `SHOW MASTER STATUS` 对比看积压 |
| `Relay_Master_Log_File / Exec_Master_Log_Pos` | SQL thread 已 apply 到主库 binlog 的位点 | 与 `Read_Master_Log_Pos` 差 = relay log 积压字节数 |
| `Retrieved_Gtid_Set` | IO thread 已拉取的 GTID 集合 | - |
| `Executed_Gtid_Set` | SQL thread 已执行的 GTID 集合 | 与主库 `gtid_executed` 做差集 = 未 apply 的事务 |
| `Auto_Position` | 是否用 GTID 自动定位 | 1 = GTID 模式，0 = 位点模式 |

### 易错点

- **`Seconds_Behind_Source = 0` 不等于没有延迟**：SQL thread 恰好空闲时显示 0，但可能积压的 relay log 还很多（IO thread 还在追）。要同时看 `Retrieved_Gtid_Set` vs `Executed_Gtid_Set`。

- **半同步超时退化**：`rpl_semi_sync_source_timeout=10000`（10s），网络抖动时主库悄悄降级为异步，如果没有告警，你以为是半同步其实已经是异步了。监控 `Rpl_semi_sync_master_status` 变量。

- **MTS 并行不是无限制的**：`LOGICAL_CLOCK` 模式下，只有在主库**同一 group commit 批次**里提交的事务才能并行 apply。主库 TPS 低时 group commit 批次小，从库并行度也上不去。这时要看主库的 `binlog_group_commit_sync_delay`（人为引入主库 commit 等待以凑更大批次）。

- **MGR 和半同步不兼容**：不要在 MGR 集群里同时开半同步插件，两者有冲突。MGR 有自己的 Paxos 一致性保证。

- **`read_only` vs `super_read_only`**：从库应同时设 `super_read_only=ON`，否则有 `SUPER` 权限的用户（运维人员）可能误写从库，导致主从数据分叉（split brain 的软件版本）。

### 主从延迟的"根因树"

```
主从延迟
├── 从库 apply 慢
│   ├── 单线程 SQL thread → 开 MTS（replica_parallel_workers≥4）
│   ├── 大事务 → 拆分 DML；避免长 DDL
│   └── 从库硬件差 → 升级或减少从库读流量
├── 主库 binlog 生成快（写入压力大）
│   └── 从库 apply 能力 < 主库写速度 → MTS + 更多 workers
├── 网络传输慢
│   └── IO thread 速度 < 主库写速度 → 优化网络 / 压缩（binlog_transaction_compression=ON，8.0.20+）
└── 从库有慢查询争 CPU / IO
    └── 读写分离但读流量过重 → 加从库；分开只读从库和复制从库
```

## 7. 一句话总结

主从复制的本质是**三线程（dump / IO / SQL）搬运并重放 binlog**；默认异步会丢数据，lossless 半同步在 commit 前等 ACK 解决丢失问题，MGR 用 Paxos 投票做原生 HA；用 GTID 替代位点让切主从"手工对齐坐标"变成"自动算差集"；读写分离的"读自己的写"问题用写后路由主库或 `WAIT_FOR_EXECUTED_GTID_SET()` 解决；延迟飙升先看 `SHOW REPLICA STATUS` + `pt-heartbeat`，根因多半是大事务或 SQL thread 单线程跑不过主库写入速度。
