# WAL 是什么？redo log 的 LSN 和 checkpoint 什么关系？

## 一句话回答

**WAL（Write-Ahead Logging）= 改数据前先把 redo 顺序写盘，脏页晚点批量刷**。**LSN** 是 redo 写到的字节位置，每次修改立即推进；**Last checkpoint** 是脏页已安全落盘的位置，**滞后于 LSN**。二者之差 = **checkpoint age** = 「已写 redo 但脏页还没落盘」的量——它越大，崩溃恢复要重放的 redo 越多；逼近 redo 容量上限会触发强制刷脏、写停顿。

## 要点

- redo 顺序写（快），数据页随机写（慢）——WAL 用「顺序的 redo」换「延迟的随机刷盘」。
- 崩溃恢复：先用 redo **前滚**（恢复已提交未刷盘的页），再用 undo **回滚**未提交事务。
- `innodb_flush_log_at_trx_commit=1` 每次提交 fsync redo（双一配置的一半）。

## 证据链接

- 实测灌 1 万更新：LSN 涨 5.6MB、checkpoint 纹丝不动，两线分叉：[ch07 Scenario 01](../07-logs-and-crashsafe/scenarios/01-redo-lsn-and-checkpoint-age.md)
- 章节原理：[ch07 §3.2 / §3.3](../07-logs-and-crashsafe/README.md)

## 易追问的延伸

- **Q: checkpoint age 太大怎么办？** → 调 `innodb_io_capacity(_max)` 提刷脏速度，或加大 `innodb_redo_log_capacity` 减少强制 checkpoint。
- **Q: redo 和 binlog 区别？** → redo 是 InnoDB 物理日志（循环写、crash 恢复用）；binlog 是 Server 层逻辑日志（追加写、复制/PITR 用）。
