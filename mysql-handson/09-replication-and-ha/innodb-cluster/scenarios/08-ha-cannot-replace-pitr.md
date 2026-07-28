# Scenario 08：HA 不能替代 PITR

## 我想验证的问题

Group Replication 能否自动撤销一个已经合法提交并复制的误删事务。

## 预期（实机执行前记录）

- 错误 `DELETE` 是合法事务，Group Replication 会把它复制到所有成员；自动 failover 不会找回历史版本。
- 恢复链是「先还原一致全备份，再从备份记录的位置重放 binlog，到 destructive transaction 之前停止」。
- 时间戳只用于定位；实验以 `SHOW BINARY LOG STATUS` 所表示的 file／position 语义作为精确边界，实际起点由一致备份内嵌的 source coordinate 提供。
- 恢复必须落到隔离的 `recovery` 实例，核对后再规划业务回迁，不能直接覆盖在线 Cluster。
- Group Replication HA 解决当前副本可用性与故障转移；PITR 解决已经提交后的历史状态恢复，两者不是同一能力。

## 预期执行链

1. 停止并完成所有写入后制作 `--single-transaction --source-data=2` 一致备份，以备份内坐标作为 replay start。
2. 经 Router 写入唯一的 `pitr-keep`，立即记录同一 binlog 文件的 stop position。
3. 经 Router 提交全表误删，并确认 `db1/db2/db3` 都为零行。
4. 在 profile 隔离的 `recovery` MySQL 导入全备份，只重放 `[start, stop)` 的 binlog。
5. 核对 `pitr-keep`、恢复行数及在线 Cluster 仍保持误删后的状态；不把恢复实例覆盖回 Cluster。

## 证据契约

成功运行的本地证据会归档到被 Git ignore 的
`mysql-handson/00-lab/ha/evidence/runs/ha-cannot-replace-pitr/<run-id>/`。至少应包含：
`source-primary.txt`、`base.sql`、`base-count.txt`、`binlog-window.txt`、
`expected-count.txt`、`member-zero.txt`、`recovery-keep-row.txt`、
`recovered-count.txt`、`expected-projection.tsv`、`recovered-projection.tsv`、
`final-topology.txt`、`final-member-counts.txt` 与 `base-dump.stderr`。
`recovery-readiness.txt` 记录 recovery 接受已认证 SQL 所需的尝试次数与秒数；
`recovery-readiness-errors.txt` 保留等待期间的认证／连接错误。

## 实测

- 指定成功 run ID：`20260728T061309Z`。本机生成且被 Git ignore 的 archive 为
  `mysql-handson/00-lab/ha/evidence/runs/ha-cannot-replace-pitr/20260728T061309Z/`；
  本节的数据分别来自其中的 `source-primary.txt`、`base-count.txt`、
  `binlog-window.txt`、`expected-count.txt`、`member-zero.txt`、
  `recovery-keep-row.txt`、`recovered-count.txt`、`final-topology.txt` 与
  `final-member-counts.txt`，完整行核对来自 `expected-projection.tsv` 与
  `recovered-projection.tsv`，认证就绪边界来自 `recovery-readiness.txt`。
- source Primary 为 `db1`；一致全备份内记录的 replay 起点是
  `binlog.000004:238`，保留行提交后的 stop position 是同一文件的 `591`。
  这些 file／position 是权威边界；运行时间不用于精确停止。
- base dump 有 10 行；写入 `pitr-keep` 后预期为 11 行。Cluster-wide
  `DELETE` 后 `db1=0`、`db2=0`、`db3=0`，证明 HA 忠实复制了误操作。
- 隔离 `recovery` 实例导入 base dump，再重放 `[238, 591)` 后得到 11 行，
  且唯一查询命中 `pitr-keep`。恢复前后的 11 行都按 `request_id` 排序，并把
  `request_id/payload/via_router/written_by` 逐栏编码为带 NULL 标记的 HEX；两份
  projection 经 runtime `cmp -s` byte-for-byte 相同，destructive transaction
  没有进入 replay，也没有其他行被替换或改写。
- recovery 首次启动第 4 次尝试才接受已认证 SQL，耗时 6 秒；脚本没有把只证明
  mysqld 存活的 `mysqladmin ping` 当成认证完成。
- 恢复完成后在线 Cluster 仍为 `db1=PRIMARY/ONLINE`、
  `db2/db3=SECONDARY/ONLINE`，三成员再次查询仍各为 0 行。恢复数据没有覆盖
  在线 Cluster。

## 预期 vs 实机落差

- 结论符合预期。实现上进一步收紧了起点：不在 dump 完成后另做一次
  `SHOW BINARY LOG STATUS`，而是由 `--source-data=2` 把一致性快照对应的
  source coordinate 写进 dump；`SHOW BINARY LOG STATUS` 只用于记录保留事务后的
  stop position。

## 生产边界

- 本实验证明的是单文件 position replay。若 start／stop 跨 binlog 文件，脚本会
  fail closed；生产恢复应显式编排多文件，而不是静默跨越。
- `recovery` 只用于核对和准备后续业务回迁。将恢复结果切回线上仍需要停写、差异
  核对、切换和回滚计划，本 Scenario 没有把它冒充成自动 HA 能力。
