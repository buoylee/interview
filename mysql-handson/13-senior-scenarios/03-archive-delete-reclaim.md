# 归档、批量删除与空间回收

| 结论／证据 | 等级 | 当前含义 |
|---|---|---|
| run `20260731T021647Z` 的 S=100,000 三条 mutation path | `SCALED_REPRODUCED (S=100000)` | big delete、batch delete 与 partition drop 各三次通过 correctness；这是隔离单机 S 实验，不外推生产吞吐、P99 或 replica lag。 |
| ch02／05／07／09／11 的机制边界 | `REUSED` | 直接链接既有 mechanism owner，不在这里重写页、MVCC、日志、复制与 PITR 原理。 |
| 生产 retention、archive、delete 与 reclaim 决策 | `REASONED` | 由业务不变式与机制推导；没有外推本机耗时、redo、空间或线上延迟。 |

## 陌生题目

> 一张持续增长的历史表要删除三个月前的数据并释放磁盘，你怎么做，如何避免拖垮线上、误删 legal hold、制造复制延迟或以为 `DELETE` 后文件一定变小？

这不是一句「分批删」就能结束的问题。先把资料生命周期拆开，否则很容易把「行已不可见」「purge 已追上」「InnoDB 可以复用页」和「OS 看见文件缩小」误当成同一件事。

## 四个独立阶段与完成标准

```text
retention = 哪些数据何时有资格离开热库
archive   = 冷数据放在哪里，如何验证可读和完整
delete    = 行不可见、undo/redo/binlog、purge 与 replica apply
reclaim   = InnoDB 可复用页 vs tablespace/OS 实际缩小
```

四阶段必须分别验收：

1. **retention**：固定 eligibility cutoff、时区、资料 owner 与 legal-hold exclusion；不能用「大约三个月」作为 destructive predicate。
2. **archive**：有稳定 `archive_run_id`、source／archive manifests、唯一身份、对象版本与实际可读验证。
3. **delete**：有可重复的固定 predicate、batch watermark、剩余资料不变式、purge state、replica lag 与线上 P99 停止条件。
4. **reclaim**：先说明目标是让 InnoDB 复用页，还是让 tablespace／OS 文件真正缩小；后者还要有 peak-space、MDL、时间与 restore source。

进入任何不可逆步骤前，evidence manifest 必须写明：

- cutoff 与 legal-hold 排除规则；
- source、archive、hold 的 count／range／fingerprint；
- destructive SQL 的 operator、change ticket 与审批；
- 当前 disk reserve、P99 budget、replica lag budget；
- 明确 restore source 及最近一次 restore drill 结果；
- batch identity、已确认 commit 的 watermark 与 restart point。

缺任何一项就不进入 destructive SQL。client 在 statement／commit 后 timeout 或失联时，结果是 `UNKNOWN`；先按 manifest 与 watermark 查证，不能把它当 `FAILED` 盲目重跑。

## 先澄清的约束

- retention 是按业务事件时间、建立时间还是法规时钟？cutoff 用哪个时区，谁能变更？
- legal hold 是 row-level 例外还是整个 tenant／月份冻结？解除是否需要双人审批和审计？
- archive 的 RPO、restore SLA、查询方式与保存年限是什么？冷库和热库是否共故障域？
- 当前表是否 file-per-table、是否已按 retention key 分区、所有 unique key 是否能包含 partition key？
- 线上 P99 latency budget、最低 disk reserve、redo checkpoint pressure 与 replica lag budget 各是多少？
- replica 是只读查询节点、灾备候选还是两者皆是？大量变更必须多久 apply 完？
- 删除期间能否暂停写入？本次 S lab 没有 concurrent OLTP，不能回答线上 P95／P99 影响。
- 已经满盘时，可否先扩容／迁移，还是错误地期待 rebuild 在零额外空间下救急？

## 跨章执行链

本场景只组装机制，完整原理由下列 owner 负责：

- [ch02 InnoDB storage](../02-innodb-storage/README.md)：page／extent／segment／tablespace、file-per-table 与 Buffer Pool。
- [ch05 transaction and MVCC](../05-mvcc-and-transaction/README.md)：长事务、undo version、purge 受旧 ReadView 阻塞。
- [ch07 logs and crash safety](../07-logs-and-crashsafe/README.md)：每次 `DELETE` 的 undo、redo、binlog、checkpoint 与 commit 边界。
- [ch09 replication and HA](../09-replication-and-ha/README.md)：source receive、relay、apply、visibility 与 replica lag。
- [ch11 operations and restore](../11-ops-and-troubleshooting/README.md)：备份、PITR、磁盘操作与 restore drill。

机制链接为 `REUSED`；本文件对生产 choices 的组装仍是 `REASONED`。

## S dataset：六个固定 table roles

S 实验固定为 2026 年 1–6 月的 100,000 行 deterministic rows。六个业务 table roles 必须恰为：

| table | role |
|---|---|
| `archive_source` | immutable seed；只作验收与 S lab restore source，不执行 destructive SQL |
| `archive_big_delete` | 单一大事务路径 |
| `archive_batch_delete` | 每次 1,000 行并 autocommit 的 bounded path |
| `archive_partitioned` | 按月 `RANGE COLUMNS(created_at)` 的 partition-drop path |
| `archive_cold` | 通过 manifest 验证的 archive copy |
| `archive_hold` | 从可 drop partitions 分离、仍可查询的 legal-hold rows |

`seed_digit` 只是同一 namespaced schema 内、seed 完立即删除的普通 helper table，不是第七个资料角色，也不是 temporary table。S lab 只允许在隔离的 `mysql_senior_scenarios` schema 执行。

### 精确 DDL、seed 与 partition layout

```sql
CREATE DATABASE IF NOT EXISTS mysql_senior_scenarios
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mysql_senior_scenarios;

CREATE TABLE archive_source (
  id         BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id),
  KEY idx_created (created_at, id)
) ENGINE=InnoDB;

CREATE TABLE archive_big_delete LIKE archive_source;
CREATE TABLE archive_batch_delete LIKE archive_source;

CREATE TABLE archive_partitioned (
  id         BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL,
  payload    VARCHAR(128) NOT NULL,
  legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id, created_at),
  KEY idx_created (created_at, id)
) ENGINE=InnoDB
PARTITION BY RANGE COLUMNS(created_at) (
  PARTITION p202601 VALUES LESS THAN ('2026-02-01'),
  PARTITION p202602 VALUES LESS THAN ('2026-03-01'),
  PARTITION p202603 VALUES LESS THAN ('2026-04-01'),
  PARTITION p202604 VALUES LESS THAN ('2026-05-01'),
  PARTITION p202605 VALUES LESS THAN ('2026-06-01'),
  PARTITION p202606 VALUES LESS THAN ('2026-07-01'),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);

DROP TABLE IF EXISTS seed_digit;
CREATE TABLE seed_digit (d TINYINT UNSIGNED PRIMARY KEY);
INSERT INTO seed_digit VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9);

INSERT INTO archive_source (id, created_at, payload, legal_hold)
SELECT n,
       TIMESTAMPADD(
         SECOND,
         FLOOR((n - 1) / 6),
         TIMESTAMPADD(MONTH, MOD(n - 1, 6), '2026-01-01 00:00:00')
       ),
       CONCAT('archive-', LPAD(n, 12, '0')),
       n <= 55 AND MOD(n - 1, 6) = 0
FROM (
  SELECT 1 + d0.d + 10*d1.d + 100*d2.d + 1000*d3.d
           + 10000*d4.d + 100000*d5.d AS n
  FROM seed_digit AS d0
  CROSS JOIN seed_digit AS d1
  CROSS JOIN seed_digit AS d2
  CROSS JOIN seed_digit AS d3
  CROSS JOIN seed_digit AS d4
  CROSS JOIN seed_digit AS d5
  ORDER BY n
  LIMIT 100000
) AS seq;

INSERT INTO archive_big_delete SELECT * FROM archive_source;
INSERT INTO archive_batch_delete SELECT * FROM archive_source;
INSERT INTO archive_partitioned
SELECT * FROM archive_source
WHERE NOT (created_at < '2026-04-01 00:00:00' AND legal_hold = TRUE);

DROP TABLE seed_digit;
```

MySQL 要求 partition expression 用到的每个 column 都出现在每个 unique key 中，primary key 也属于 unique key，所以 partitioned table 使用 `PRIMARY KEY(id, created_at)`，不能照抄 nonpartition 的 `PRIMARY KEY(id)`；这是 [MySQL 8.0 partition unique-key rule](https://dev.mysql.com/doc/refman/8.0/en/partitioning-limitations-partitioning-keys-unique-keys.html) 的 schema 约束，不是性能偏好。

```sql
CREATE TABLE archive_cold (
  archive_run_id CHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  source_id      BIGINT UNSIGNED NOT NULL,
  created_at     DATETIME(6) NOT NULL,
  payload        VARCHAR(128) NOT NULL,
  PRIMARY KEY (archive_run_id, source_id)
) ENGINE=InnoDB;

CREATE TABLE archive_hold (
  source_id   BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME(6) NOT NULL,
  payload     VARCHAR(128) NOT NULL,
  hold_reason VARCHAR(64) NOT NULL,
  PRIMARY KEY (source_id)
) ENGINE=InnoDB;
```

### 固定 predicate 与 seed invariants

本场景唯一 old-data predicate 是：

```sql
created_at < '2026-04-01 00:00:00' AND legal_hold = FALSE
```

不要改成 `NOW() - INTERVAL 3 MONTH`，否则不同 trial 不再同源，重跑也失去稳定边界。seed 的纯数学预期是：

| invariant | expected before mutation |
|---|---:|
| `archive_source`／两个 nonpartition copies | 100,000 rows each |
| cutoff 前总 rows | 50,001 |
| cutoff 前 `legal_hold=TRUE` | exactly 10 |
| eligible old rows | 49,991 |
| `archive_partitioned` | 99,990 rows；十个 old holds 已排除 |
| `p202601`–`p202603` 合计 | 49,991 rows |

Task 8 的 run `20260731T021647Z` 已逐项验证这些 expected invariants；实际 manifest 记录在后文 evidence。

## destructive SQL 前的 archive manifest

S lab 使用稳定身份：

```text
archive_run_id = ARCHIVE2026Q1S01
cutoff         = 2026-04-01 00:00:00
```

对每个 mutation source 的 eligible range 先保存同一形状的 manifest：

```sql
SELECT COUNT(*) AS rows,
       MIN(id) AS min_id,
       MAX(id) AS max_id,
       SUM(id) AS sum_id,
       BIT_XOR(CRC32(CONCAT_WS('#', id, created_at, payload))) AS lab_fingerprint
FROM source_table
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE;
```

`source_table` 依次实例化为 `archive_source`、`archive_big_delete`、`archive_batch_delete` 与尚未 drop 的 `archive_partitioned`。四者必须与 immutable source manifest 一致，才可继续。

### copy、唯一身份与 cold-side compare

先确认该 run identity 没有旧资料；若前次 client 失联，先查询而不是删除或覆盖：

```sql
SELECT COUNT(*)
FROM archive_cold
WHERE archive_run_id = 'ARCHIVE2026Q1S01';

INSERT INTO archive_cold
  (archive_run_id, source_id, created_at, payload)
SELECT 'ARCHIVE2026Q1S01', id, created_at, payload
FROM archive_source
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE;
```

`PRIMARY KEY(archive_run_id, source_id)` 让同一 archive identity 不会静默出现 duplicate。commit 成功后，以 `source_id AS id` 取得同形 manifest：

```sql
SELECT COUNT(*) AS rows,
       MIN(source_id) AS min_id,
       MAX(source_id) AS max_id,
       SUM(source_id) AS sum_id,
       BIT_XOR(
         CRC32(CONCAT_WS('#', source_id, created_at, payload))
       ) AS lab_fingerprint
FROM archive_cold
WHERE archive_run_id = 'ARCHIVE2026Q1S01';
```

只有 source 与 cold 的五个 aggregates 全部相等、随机抽样能实际读出 payload、evidence artifact 已持久化，才算 archive verified。CRC32／`BIT_XOR` 只是 lab fingerprint，不是密码学完整性证明；生产 archive 应使用更强 manifest、immutable object versioning、独立故障域、访问审计与定期 restore drill。

### legal hold separation

十个 old held rows 必须先复制进 `archive_hold`：

```sql
INSERT INTO archive_hold (source_id, created_at, payload, hold_reason)
SELECT id, created_at, payload, 'legal-hold-s-lab'
FROM archive_source
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = TRUE;

SELECT COUNT(*) AS held_rows,
       MIN(source_id) AS min_id,
       MAX(source_id) AS max_id,
       SUM(source_id) AS sum_id,
       BIT_XOR(
         CRC32(CONCAT_WS('#', source_id, created_at, payload))
       ) AS lab_fingerprint
FROM archive_hold;
```

结果必须与 `archive_source` 的 held manifest 相等且 `held_rows=10`。`archive_partitioned` 的 seed 已把这十行排除，因此 whole-month partitions 才全部具备 drop eligibility。row-level exception 与 partition boundary 不一致时，blind partition drop 会连 hold 一起丢掉；必须先以资料 placement 分离，不能用「DDL 很快」覆盖正确性问题。

## 共同量测口径

run `20260731T021647Z` 对 A／B／C 每条 path 都按以下口径记录：

| field | contract |
|---|---|
| elapsed | client monotonic start／end，明确是否含 throttle sleep |
| affected rows | statement row count 与 before／after invariant 差值交叉验证 |
| redo delta | 同一 server status 计数器的 before／after；记录变量名、版本与重启边界 |
| binlog growth | before／after file+position；跨 file rotation 时按 `SHOW BINARY LOGS` 汇总，`log_bin=OFF` 则标 `NOT_APPLICABLE` |
| purge state | `SHOW ENGINE INNODB STATUS` 的 `History list length` 与长事务清单 |
| logical size | `information_schema.TABLES`／`PARTITIONS` 的 data+index estimates |
| physical size | 有 datadir 权限才记录对应 table／partition tablespace file；否则明确 `NOT_OBSERVED` |
| correctness | archive、hold、remaining rows、range 与 fingerprint invariants |

本 S lab 没有 concurrent OLTP，因此不产生 P95 或 P99 latency claim。若明确启用 production-like concurrent profile，必须在 run 前填入 `p99_budget_ms` 与持续窗口；超过 budget 就停止新 batch，而不是事后挑一段好看的 latency。

## Path A：一个大事务

```sql
START TRANSACTION;

DELETE FROM archive_big_delete
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE;

COMMIT;
```

执行前必须已验证 archive、hold、disk reserve 与 restore source。statement 期间观察 affected rows、locks、redo／checkpoint、binlog 与磁盘；commit 后再验收剩余资料。

停止／恢复边界：

- commit 前的业务或正确性问题可 `ROLLBACK`，但大量 rollback 本身会继续消耗时间、I/O 与 undo，不能假设瞬间恢复。
- MySQL restart、I/O error、lock wait、disk reserve 或 checkpoint pressure 触发时，不再发新 destructive SQL；等待 crash recovery／rollback 状态明确。
- client 在 `DELETE` 或 `COMMIT` 后失联是 `UNKNOWN`；先查 eligible count 与 manifests，绝不直接再发同一大事务。
- 已确认 commit 后不能以普通 rollback 还原；S lab restore source 是 immutable `archive_source`，生产是 verified versioned archive 加已演练的 backup／PITR。

## Path B：1,000-row autocommit batches

每个 batch 先只读取得 candidate boundary：

```sql
SELECT id
FROM archive_batch_delete
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE
ORDER BY id
LIMIT 1000;
```

然后在 `autocommit=1` session 执行固定 mutation：

```sql
DELETE FROM archive_batch_delete
WHERE created_at < '2026-04-01 00:00:00'
  AND legal_hold = FALSE
ORDER BY id
LIMIT 1000;
```

每次确认 commit 后，controller 把以下 watermark durable append 到 run evidence，才 sleep 50 ms 再发下一批：

```text
archive_run_id
path = batch_delete
batch_seq
candidate_min_id
candidate_max_id
expected_rows
affected_rows
eligible_rows_after
committed_at
status = SUCCEEDED | FAILED | UNKNOWN | ABORTED
```

S dataset 的六个 roles 不另加 control table；watermark 存在 task evidence journal。生产可用独立 control store，但同样要让 `(archive_run_id,path,batch_seq)` 唯一。固定 predicate 令已删除 rows 自然不再匹配，因此 restart 仍从剩余资料取下一批；watermark 是 audit／reconciliation boundary，不是把 predicate 偷换成易漏资料的动态时间。

如果 client 在 batch statement 后失联，将该 batch 标为 `UNKNOWN`。以 `candidate_max_id` 范围、eligible count 与 cumulative manifest reconciliation 判断事务是否全有或全无；未确认前不前进 watermark，也不把 batch 当 `FAILED` 自动重送。

每批之间重新检查以下停止条件：

- free disk 低于预先保留的 reserve；
- lock wait／deadlock 超过 budget；
- MySQL restart、I/O error 或连接进入 `UNKNOWN`；
- archive／hold／remaining correctness mismatch；
- redo checkpoint age／dirty-page pressure 越过预设 budget；
- 明确使用 replica profile 时，replication lag 越过预声明 budget；
- 明确使用 concurrent profile 时，线上 P99 连续越过预声明 budget。

任一命中就停止**下一批**并持久化 `ABORTED` restart point。已提交 batches 不 rollback；修复原因后，从 verified watermark 和当前固定 predicate 继续。相较 Path A，它以更多 commits、总时间和 orchestration 换取 bounded transaction、throttle 与 resume。

## Path C：whole-partition drop

进入 DDL 前必须同时证明：

1. `archive_cold` manifest 与 49,991 个 eligible old source rows 相同；
2. `archive_hold` 恰有十行且 held manifest 相同；
3. `archive_partitioned` 的 `p202601`–`p202603` manifest 与 cold 相同，且其中 `legal_hold=TRUE` 为零；
4. restore source、disk reserve、MDL／replica stop budgets 已记录。

然后才执行：

```sql
ALTER TABLE archive_partitioned
  DROP PARTITION p202601,p202602,p202603;
```

MySQL 官方说明 `DROP PARTITION` 适用于 RANGE／LIST partitions，并会丢弃 named partitions 内的资料；因此它是 irreversible DDL，不是可以事后 `ROLLBACK` 的 row delete（[ALTER TABLE partition operations](https://dev.mysql.com/doc/refman/8.0/en/alter-table-partition-operations.html)）。

即使 `binlog_format=ROW`，`ALTER TABLE` 等 DDL 仍以 statement format 写入 binary log；A／B 的 row-changing `DELETE` 则可能为每个 changed row 写 row event。官方也明确指出大量 DML 在 RBR 下可能显著增加 binlog data（[binary log format](https://dev.mysql.com/doc/refman/8.0/en/binary-log-setting.html)、[SBR vs RBR](https://dev.mysql.com/doc/refman/8.0/en/replication-sbr-rbr.html)）。所以 partition drop 通常避开逐行 DML 的日志量，但 replica 仍要接收并执行 DDL，MDL、apply 时间与 lag 仍须观察，不能称为「零成本」。

DDL 发出后 client timeout 同样是 `UNKNOWN`：查 `information_schema.PARTITIONS`、remaining invariant 与 archive／hold manifests，不能再次盲发。恢复是由 `archive_cold` 加 `archive_hold` 重建资料，或从已演练 backup／PITR 恢复到独立实例后再受控回灌；不是 rollback DDL。

## delete、purge、reuse 与 OS reclaim 的边界

`DELETE` 不会立即从 database file 物理移除 record。InnoDB 先 delete-mark；当旧版本不再被 MVCC／rollback 需要时，background purge 才处理 history list 并物理清除 record。`History list length` 是 purge lag 的观察之一，长 consistent-read transaction 会让它增长（[MySQL 8.0 purge configuration](https://dev.mysql.com/doc/refman/8.0/en/innodb-purge-configuration.html)）。

因此要分四个 verdict：

1. **SQL visibility complete**：eligible query 已为零，held／recent rows 仍可见。
2. **purge caught up**：history list 已回到 run 前稳定范围，且没有 blocker long transaction；这不等于文件缩小。
3. **InnoDB reuse available**：被清掉的 records／pages 留在 tablespace 内，可由同表后续资料复用；通常不能据此承诺 `.ibd` 立即变小。
4. **OS reclaim complete**：实际 tablespace file 缩小或 partition file 消失，并用 filesystem／tablespace evidence 验证。

MySQL 8.0 默认 file-per-table；官方文件说明 truncate／drop file-per-table table 时空间可回到 OS，而 shared tablespace 的 freed space 通常只供 InnoDB 内部复用（[file-per-table tablespaces](https://dev.mysql.com/doc/refman/8.0/en/innodb-file-per-table-tablespaces.html)、[TRUNCATE reclaim boundary](https://dev.mysql.com/doc/refman/8.0/en/innodb-truncate-table-reclaim-space.html)）。官方 partition operations 文件也说明每个 InnoDB partition 有自己的 `.ibd` tablespace file；对这种 layout，drop whole partition 才可能直接移除对应 partition file（[ALTER TABLE partition operations](https://dev.mysql.com/doc/refman/8.0/en/alter-table-partition-operations.html)）。仍要以本机 `FILE_NAME`／filesystem before-after 证明，不能只看 `DATA_FREE` 推断。

`OPTIMIZE TABLE` 对 InnoDB 会映射为 table rebuild／`ALTER TABLE ... FORCE`，可重组 table 与 indexes 并回收 file-per-table 的 unused space；它会用 online DDL，但 prepare／commit 仍短暂取得 exclusive table lock，特殊条件下还会走 table-copy method，而且默认会写入 binlog 复制到 replicas（[MySQL 8.0 OPTIMIZE TABLE](https://dev.mysql.com/doc/refman/8.0/en/optimize-table.html)）。

所以 baseline 不是「每次大删后自动 `OPTIMIZE TABLE`」：

- 先问业务是否真的需要 OS reclaim；未来还会增长时，内部 page reuse 可能已足够。
- rebuild 前估算 table+indexes 的 peak space、临时空间、redo／I/O、MDL、完成时间和 replica 影响。
- 先证明 restore source 和 rollback／cutover 方法，再安排 maintenance window。
- 已满盘时不启动需要额外 peak space 的 rebuild；先扩容、迁移或从其他安全资料释放空间。

## S 实测 evidence

### 环境、身份与停止边界

run `20260731T021647Z` 只使用 owned dedicated container
`mysql-senior-scenarios-mysql`、volume
`mysql-senior-scenarios-data` 与 `127.0.0.1:33306`。环境是 MySQL
8.0.36、4 CPU／4 GiB limit、`innodb_file_per_table=1`、
`innodb_flush_log_at_trx_commit=1`、`sync_binlog=1`、
`binlog_format=ROW`、`log_bin=1`。开始时 `/private/tmp` 可用
24,303,628,288 bytes；primary run 当时只持久化了 free bytes 与 5 GiB
reserve，未保存一个可审计的 S-peak 数值，不能事后冒充为完整的
predeclared arithmetic gate。

raw evidence 清理后的 fix-round review 只读查询 retained `.ibd`，并用已
记录的三个 dropped partition files 复原 seed-state footprint：

```text
retained archive .ibd files                    =    94,617,600
3 dropped old partitions × 9,437,184           =    28,311,552
seed-state six-role .ibd footprint              =   122,929,152
same-size transient second-copy／undo allowance =   122,929,152
largest observed mutation redo delta            =    10,910,720
largest observed mutation binlog delta          =     2,023,690
retrospective runtime／evidence safety pad       =    67,108,864
conservative S-peak upper bound                  =   325,901,578
5 GiB reserve                                    = 5,368,709,120
required                                         = 5,694,610,698
preflight free                                   = 24,303,628,288
margin                                           = 18,609,017,590
```

这证明原 PASS verdict 在该保守 retrospective upper bound 下仍成立，但
不改写历史：run 前真正 predeclared 的只有 5 GiB reserve、runtime／
checkpoint limits 与停止条件；325,901,578-byte upper bound 是 fix round
才重建的 audit。旧 `mysql-primary` 保持 `exited`，全程没有启动或使用。

资料身份和执行身份刻意分开：

```text
lab run ID    = 20260731T021647Z
archive_run_id = ARCHIVE2026Q1S01
cutoff         = 2026-04-01 00:00:00
```

先声明 1,500 秒总 runtime budget、180 秒 destructive statement
timeout、60 秒 history-list observation window、512 MiB checkpoint-age
limit 与 5 GiB disk reserve。任一 correctness mismatch、statement outcome
`UNKNOWN`、restart／unhealthy、I/O error、disk reserve、checkpoint age 或
`Innodb_log_waits` 越界就停止，不自动 retry。实际总 run 为 237.913 秒，
没有命中停止条件。这里没有 replica 或 concurrent OLTP profile，因此
replica lag 与 P95／P99 都是 `NOT_OBSERVED`。

### immutable source、archive 与 legal-hold manifest

建立 archive tables 前先确认 namespace 中没有旧 `archive_*` tables。
`archive_cold` 的该 run identity 与 `archive_hold` 都先验为零，再各执行
一次普通 `INSERT`；没有 `INSERT IGNORE`、upsert 或重复插入来掩盖边界。
seed 后 `seed_digit` 已删除。

| manifest | rows | min id | max id | sum id | lab fingerprint |
|---|---:|---:|---:|---:|---:|
| complete `archive_source` | 100,000 | 1 | 100,000 | 5,000,050,000 | 4,242,170,261 |
| eligible source／`archive_cold` | 49,991 | 2 | 99,999 | 2,500,049,720 | 3,443,153,953 |
| old `legal_hold` source／`archive_hold` | 10 | 1 | 55 | 280 | 104,009,398 |
| recent source | 49,999 | 4 | 100,000 | 2,500,000,000 | 936,588,034 |
| `archive_partitioned UNION ALL archive_hold` | 100,000 | 1 | 100,000 | 5,000,050,000 | 4,242,170,261 |

月分布实际为 January–April 各 16,667 rows，May–June 各 16,666
rows；cutoff 前共 50,001，其中 exactly 10 为 hold，剩余 49,991
eligible。cold archive 还实际读出 `2／archive-000000000002`、
`3／archive-000000000003` 与 `8／archive-000000000008`，不只比较
count。每个 destructive trial 前，path manifest 都再次与 immutable
source／cold／hold 比较；任一不等本来就不会发送 DELETE 或 DDL。

这组 `BIT_XOR(CRC32(...))` 仍只是 lab fingerprint。生产必须使用更强的
immutable manifest、object version、独立故障域与 restore drill；S lab
的 restore source 是未 mutation 的 `archive_source`。

### 三路各三次结果

每轮按 A→B→C 执行；每条 path 都从同一 immutable source 重建自己的
path table，stable archive identity 不重复写入。elapsed 是 client
monotonic；redo 使用 `Innodb_os_log_written` delta；binlog 以
`SHOW BINARY LOGS` total bytes delta 计算，三轮都没有 rotation。

| path／trial | elapsed seconds | mutation-only seconds | redo bytes | binlog bytes | affected |
|---|---:|---:|---:|---:|---:|
| A big delete／1 | 0.134383 | 同 elapsed | 6,158,848 | 2,008,555 | 49,991 |
| A big delete／2 | 0.125073 | 同 elapsed | 5,483,520 | 2,008,555 | 49,991 |
| A big delete／3 | 0.124207 | 同 elapsed | 5,491,712 | 2,008,555 | 49,991 |
| B batch delete／1 | 12.154967 | 2.684960 | 10,875,904 | 2,023,690 | 49,991 |
| B batch delete／2 | 12.864937 | 3.078112 | 10,910,720 | 2,023,690 | 49,991 |
| B batch delete／3 | 12.246044 | 2.892629 | 10,875,904 | 2,023,690 | 49,991 |
| C partition drop／1 | 0.069888 | 同 elapsed | 37,888 | 291 | 49,991 |
| C partition drop／2 | 0.064891 | 同 elapsed | 37,376 | 291 | 49,991 |
| C partition drop／3 | 0.071314 | 同 elapsed | 41,984 | 291 | 49,991 |

A 的 timer 包住完整 client invocation：
`START TRANSACTION → DELETE → SELECT ROW_COUNT() → COMMIT`。表中的
affected=49,991 只在整个 invocation 成功返回、也就是收到 COMMIT ack 后
才采信；随后用新的 read-only query 验证 eligible=0、hot=50,009，并取得
immediate post-commit redo／binlog／history／size snapshot。它不是在
DELETE statement 完成、transaction 尚未 commit 时发布 logical
visibility。

A median／range 是 0.125073／0.124207–0.134383 秒；B end-to-end
median／range 是 12.246044／12.154967–12.864937 秒，包含每批 50 ms
sleep、candidate query、watermark fsync 与 controller checks，不能拿它和
A 的单 statement timing 当成纯 SQL benchmark。B mutation-only
median 是 2.892629 秒。C statement／ack median／range 是
0.069888／0.064891–0.071314 秒。

这些数字只证明本机 S 的机制差异：A 是一个 49,991-row transaction；
B 是 49 个 1,000-row commits 加最后 991 rows，共 50 个 bounded
transactions；C 是已通过 placement proof 的三个 whole-partition DDL。
不能把这个 timing 排名外推到 1,000 万行、concurrent OLTP、不同 storage
或 replicas。

### batch 中断、watermark 与恢复

B trial 1 在 batch 3 已收到 commit ack、durable append watermark 后，于
statement boundary 暂停发送下一批并验证状态。为了不把同一 process 内的
pause 冒充 restart proof，timing trials 完成后又做了一次两阶段 recovery
drill：phase 1 controller PID 86424 在 batch 3 写入并 `fsync` checkpoint
后退出；另一个 PID 88570 的新 process 才进入 phase 2。process 之间再次
只读验证：

```text
last completed batch = 3
cumulative deleted   = 3,000
hot rows remaining   = 97,000
eligible remaining   = 46,991
held remaining       = 10
recent remaining     = 49,999
```

phase 2 先证明 checkpoint 与当前表的四个 counts 相同，且 PID 与 phase 1
不同，才仍用相同 fixed predicate 从 batch 4 继续；没有把时间边界或
candidate watermark 偷换成新的 deletion predicate。最终 batch 50 的
candidate range 是 `98019–99999`，expected／affected 都是 991，
eligible after 为 0，hold／recent／conservation manifests 再次通过。

三个 timing trials 和额外 recovery drill 都为每批保存 candidate
min／max、expected、affected、cumulative、eligible-after、50 ms
throttle 与 disk／checkpoint／restart checks；每轮都是 50 commits，
没有 duplicate side effect、`UNKNOWN` 或 retry。

### visibility、history list、reuse 与 OS reclaim

四个 milestone 分开取证，不能互相替代：

| path | SQL／metadata visibility | history-list observation | `DATA_LENGTH／INDEX_LENGTH／DATA_FREE` | physical `.ibd` |
|---|---|---|---|---|
| A | COMMIT ack 后 eligible=0、hot=50,009 | 33→34≤35、11→12≤13、9→10≤11；另一个独立查询在 0.028–0.032 s 内确认仍在 run 前 neighborhood | 三轮 pre／immediate／post observation 都是 6,832,128／3,686,400／3,145,728 bytes | 三轮一直 17,825,792 bytes |
| B | 最后 batch ack 后 eligible=0、hot=50,009 | 40→5≤42 用 0.031 s；21→29 后 15.859 s 到 1≤23；17→27 后 20.353 s 到 0≤19 | 三轮 pre／immediate／post observation 同样是 6,832,128／3,686,400／3,145,728 bytes | 三轮一直 17,825,792 bytes |
| C | DDL ack 后只剩 `p202604／p202605／p202606／pmax`，hot=49,999 | 38→46 后 27.964 s 到 0≤40；28→36 后 57.266 s 到 0≤30；27→35 后 53.081 s 到 0≤29 | old partitions 的 metadata rows 与 logical estimates 随 partition metadata 一起消失 | 每轮三个 old files 各 9,437,184 bytes，都在 DDL ack 后的第一次 filesystem snapshot 已消失 |

history target 预先定义为 `max(5, pre + 2)`。`History list length` 是
server-global、会受内部事务与其他 activity 影响的 noisy observation；
上表只证明后来回到该 neighborhood，不把等待秒数归因为某一 DELETE／DDL
的精确 purge duration。尤其 C 的 27.964–57.266 秒不是 DDL latency：
`ALTER TABLE ... DROP PARTITION` 已在 0.065–0.071 秒返回，metadata、
remaining manifest 与三个 file disappearance 都在 ack 后立即取证。

A／B 在 rows 不可见且 history 回到 neighborhood 后，`.ibd` 都没有缩小；
本次 `DATA_FREE` 和 information-schema size estimates 也没有变化。这证明
普通 DELETE 没有完成 OS reclaim，但不能用 estimates 反向证明某个具体
page 已经可复用。C 则实际观察到三个独立 partition tablespace file
消失，合计 28,311,552 bytes；这个结果依赖 file-per-table、monthly
partition layout 和 hold separation。

### gated `OPTIMIZE TABLE`

只在 B 的 final 50,009-row state 完成 visibility、correctness 与
history observation 后再量 gate。以完整 source table 的
`DATA_LENGTH + INDEX_LENGTH = 10,518,528` bytes 作为 second-copy
estimate，加 5,368,709,120-byte reserve，required 为
5,379,227,648 bytes；当时 free 24,078,176,256 bytes，gate 通过。

受控 S maintenance experiment 的 `OPTIMIZE TABLE archive_batch_delete`
实际回报 `doing recreate + analyze instead`／`OK`，耗时 0.573160 秒。
`.ibd` 从 17,825,792 缩到 11,534,336 bytes，减少 6,291,456 bytes；
redo／binlog 另增加 81,920／225 bytes。immediate
information-schema estimates pre／post 都是
`DATA_LENGTH=6,569,984`、`INDEX_LENGTH=3,407,872`、
`DATA_FREE=3,145,728`，再次说明 estimates 不能代替 filesystem
evidence。OPTIMIZE 后 hot／cold conservation、hold 与 recent manifest
仍通过。

这不是生产 recommendation。S 表很小、没有 concurrent MDL contender、
replica 或 crash；生产 rebuild 必须重新评估真正 table+indexes size、
temporary／redo peak、MDL、I/O、window、replica apply、restore source
与 rollback／cutover。

### correctness 与 expected-vs-actual

九次 destructive trials 都满足：

- A／B：hot=50,009、eligible=0、hold manifest exactly 10、recent
  manifest 49,999，且 hot+cold=100,000；
- C：old partitions 不存在、partitioned hot=49,999，且
  hot+cold+hold=100,000；
- all：cold 49,991 与 hold 10 的 five-field manifests 始终不变；
- final globals 与 run 前相同，dedicated container
  `running／healthy／restart_count=0／restart=no`，旧 container 仍
  `exited`。

| 我以为 | 实际 | 我学到 |
|---|---|---|
| 一个大 DELETE 最简单，所以也是默认生产方案 | S 中 statement 很快，但它仍是不可 throttle／resume 的 49,991-row transaction | elapsed 不能替代 transaction risk、UNKNOWN reconciliation 与 replica apply boundary |
| 分批只会比较慢 | B 的 end-to-end 确实更长、redo／binlog 也略多，但中断后从 verified watermark 安全恢复 | bounded commits 买到 stop／throttle／resume control，不是白白损失性能 |
| partition drop 快就能忽略 legal hold | C 只有先证明 10 holds 已分离、droppable partitions hold=0、union 等于 source 才安全 | schema／retention／hold placement 是 DDL 速度成立前的 correctness contract |
| rows 删除、purge、文件缩小会一起完成 | A／B rows 已不可见且 history 回到 neighborhood，`.ibd` 仍不变；C 的独立 partition files 才直接消失 | logical delete、history observation、page reuse 与 OS reclaim 必须分开验收 |
| `OPTIMIZE` 后看 `DATA_FREE` 就够 | information-schema estimates 没变，但 filesystem `.ibd` 实际缩小 | reclaim claim 要用正确 physical evidence，而且 rebuild 仍需 disk／MDL／window gate |

因此只有 S mechanics 标为 `SCALED_REPRODUCED (S=100000)`；生产
retention window、batch size、throughput、P99、replica lag、archive
RPO／RTO、OPTIMIZE window 与目标 1,000 万行行为仍是 `REASONED` 或
`NOT_OBSERVED`。

## post-mutation correctness

三个 path 各自完成后必须满足：

| path | expected invariant |
|---|---|
| A／B | hot table 50,009 rows；eligible old rows 0；十个 old holds 仍可查询 |
| C | `p202601`–`p202603` 不存在；partitioned hot table 49,999 rows |
| all | `archive_cold` 49,991 rows且 manifest 不变；`archive_hold` exactly 10 rows且 manifest 不变 |
| conservation | A／B：hot + cold = 100,000；C：partitioned hot + cold + hold = 100,000 |

还要验证 recent rows 的 count／min／max／sum／fingerprint 与 immutable `archive_source` 相同。count 对了但 fingerprint、hold 或 range 错了，仍是 correctness failure，不能报告完成。

## 30 秒

我会先固定 retention cutoff、时区、legal hold、archive restore SLA、disk reserve、P99 和 replica-lag budget。destructive SQL 前先把 eligible rows 复制到有稳定 run ID 的 cold archive，用 count／range／sum／fingerprint 双边验证，并把 holds 分离且确认可读。没有 partition key 就用 `ORDER BY id LIMIT 1000` 的 autocommit batch，每批记录 watermark、sleep、重查停止条件；若 whole months 已按 retention key 分区且没有 row-level 例外，验证后才 drop partitions。最后分开验收行不可见、purge、页可复用和 OS 文件回收，绝不承诺 `DELETE` 会让 `.ibd` 自动缩小。

## 3–5 分钟

我先把问题拆成 retention、archive、delete、reclaim。retention 定义固定 cutoff 和 legal-hold exclusion；archive 以稳定 `archive_run_id` 建立 immutable copy，source/cold 用同形 manifest 验证，并要求独立 restore source 与 drill。delete 有三条路：一个大事务最简单，但 undo、redo、row binlog、rollback 与 replica apply 都集中成不可控 burst；1,000-row autocommit batches 虽较慢，却能在每个 verified watermark 后 throttle、停下和续跑；只有 schema 的 partition boundary 与 retention 对齐、unique key 合法、holds 已分离时，才用 whole-partition drop。

执行链上，row delete 先变更可见性并产生 undo、redo、binlog，旧版本仍可能被长事务需要；purge 追上后 records／pages 才能回收给 InnoDB 使用。file-per-table 的 `.ibd` 通常不会因普通 `DELETE` 立即缩小。需要 OS reclaim 时，partition drop 可在适合 layout 下移除 partition tablespace；`OPTIMIZE TABLE` 则是 rebuild，要先规划 peak disk、MDL、I/O、replica 与 restore path，不是每次删除后的默认动作。

验证时每条 path 都记录 elapsed、affected rows、redo delta、binlog growth、history list、logical／physical size 与 remaining invariants。S lab 没有 concurrent OLTP，所以不声称 P95／P99。生产批次只在 disk、lock、I/O、correctness、checkpoint、replica lag 与 P99 budgets 内继续；timeout 后是 `UNKNOWN`，先按 candidate boundary、manifest 与 watermark 对账，不盲重跑。

## 追问树

### legal hold 怎么办？

row-level hold 不能和可 drop month 混在一起。先把 held rows 复制到 `archive_hold`，核对 exactly 10 与 fingerprint，再确认 droppable partitions 内 hold 为零。生产还要有 hold owner、解除审批和审计；做不到就不用 partition drop。

### replica lag 已经很高怎么办？

先停止新 batch，不把 source 清理优先级放在 replica recovery 之前。确认 receive 与 apply 的真实 backlog、当前大事务／DDL、disk 与 worker 状态；只有 lag 回到预声明 budget 才继续。大事务会让 apply 不可切割，bounded batches 才有 throttle 点；partition DDL 也仍须在 replica 执行。

### disk pressure 正在上升怎么办？

停止新 mutation，区分 data、undo、redo、binlog、relay、temporary space 哪个在长。普通 `DELETE` 可能先增加 undo／redo／binlog，不能当即时腾盘工具。保留 emergency reserve，先扩容或安全清理已确认可删的外部／日志资料。

### 没有 partition key 怎么办？

不要临时把生产大表硬改成 partitioned 后立刻 drop。先走 indexed fixed predicate 的 bounded delete；若 retention 是长期需求，再独立设计包含 partition key 的所有 unique keys、backfill／cutover、legal-hold placement 与 restore plan。

### 没有 archive 怎么办？

默认不删。先建立可读、可版本化、可验 manifest 的 archive，并完成 restore drill；只有业务明确批准不保留且 backup／PITR 满足法规与恢复要求时，才能重新定义 completion。

### restore SLA 很短怎么办？

不要只承诺「有对象存储」。用真实资料量演练 archive lookup、bulk restore、index rebuild、校验与 cutover，确认 RTO；必要时保留更热的 nearline store 或更细 partition。SLA 由 restore drill 证明，不由文件存在证明。

### 磁盘已经满了怎么办？

不启动巨大 `DELETE`、rollback 或 `OPTIMIZE TABLE` 来赌博，因为它们还需要写 undo／redo／binlog、temporary 或 rebuild peak space。先停止非必要写入、扩容／迁移、清理已确认安全的临时或过期日志并恢复 reserve；随后才按 archive manifest 做 bounded delete 或已验证的 partition drop。
