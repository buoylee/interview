# GTID 复制比位点复制强在哪？errant 事务怎么检测处理？

## 一句话回答

GTID（`SOURCE_AUTO_POSITION=1`）下，从库把自己执行过的 `gtid_executed` 集合告诉主库，主库从「缺的那个 GTID」开始补发——**断点续传不用人工算 binlog file+position，天然幂等**。位点模式断网恢复要人工 `CHANGE ... SOURCE_LOG_FILE/POS`，算错就丢数据或重复。代价是要防 **errant（幽灵）事务**：从库上有、主库没有的 GTID（直连从库写出来的），用 `GTID_SUBTRACT(replica_gtid, primary_gtid)` 检测，故障切换时会爆。

## 要点

- 断网恢复：GTID 自动续传，从库无人工干预就追平。
- errant 检测：`GTID_SUBTRACT(从库 gtid_executed, 主库 gtid_executed)` 非空 = 幽灵事务。
- errant 处理：在新主注入空事务覆盖该 GTID（确认无价值后）；预防靠 `super_read_only=ON`。

## 证据链接

- 断裂 + GTID 自动续传：[ch09 Scenario 02](../09-replication-and-ha/scenarios/02-replication-break-and-gtid-resume.md)
- errant 检测：[ch09 Scenario 03](../09-replication-and-ha/scenarios/03-errant-transaction-detect.md)
- 章节原理：[ch09 §3.3 / §3.11](../09-replication-and-ha/README.md)

## 易追问的延伸

- **Q: 老项目怎么开 GTID？** → `OFF→OFF_PERMISSIVE→ON_PERMISSIVE→ON` 滚动，每步需重启，大集群是周级操作。
- **Q: PITR 与 errant 的关系？** → 从「有 errant 的从库」做备份会把幽灵数据带进恢复实例；备份源要干净（ch11 §3.4 PITR 坑 3）。
