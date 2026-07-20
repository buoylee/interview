# WAL 是什么？redo log 的 LSN 和 checkpoint 什么关系？

## 一句话回答

**WAL（Write-Ahead Logging）= 数据页写出前，对应 redo 必须先持久化；脏页可以稍后刷**。**LSN** 是 redo 的字节进度；**Last checkpoint** 是相关脏页已安全落盘的进度。二者之差 = **checkpoint age** = 「仍需依赖 redo 恢复的数据页修改量」；逼近 redo 容量上限会触发强制刷脏、写停顿。

## 要点

- WAL 不消灭最终的数据页随机写；它把随机刷页移出 commit 关键路径，并用 Group Commit、后台并行和同页修改合并摊薄成本。
- 同一个 16KB B+Tree page 在刷出前被改 100 次：会有对应 redo，但可能只写一次最终 page 镜像；若命中 100 个不同 page，最终仍要刷 100 页。
- 实际内存链路：CPU 把 redo 复制进 InnoDB user-space log buffer；log writer 经 `write/pwrite` 交给 kernel page cache；log flusher 用 `fsync` 推进到持久介质。
- `innodb_flush_log_at_trx_commit`：`0` 不等 write/flush；`1` 等 `fsync`；`2` 等 write、不等 `fsync`。
- 崩溃恢复：先用 redo **前滚**（恢复已提交未刷盘的页），再用 undo **回滚**未提交事务。
- `innodb_flush_log_at_trx_commit=1` 每次提交 fsync redo（双一配置的一半）。

## 证据链接

- 实测灌 1 万更新：LSN 涨 5.6MB、checkpoint 纹丝不动，两线分叉：[ch07 Scenario 01](../07-logs-and-crashsafe/scenarios/01-redo-lsn-and-checkpoint-age.md)
- 章节原理与 user-space/kernel-space 实际操作：[ch07 §3.2 / §3.3](../07-logs-and-crashsafe/README.md)

## 易追问的延伸

- **Q: checkpoint age 太大怎么办？** → 调 `innodb_io_capacity(_max)` 提刷脏速度，或加大 `innodb_redo_log_capacity` 减少强制 checkpoint。
- **Q: redo 和 binlog 区别？** → redo 是 InnoDB 物理日志（循环写、crash 恢复用）；binlog 是 Server 层逻辑日志（追加写、复制/PITR 用）。
