# 主从延迟怎么量？为什么不能只看 `Seconds_Behind_Source`？

## 一句话回答

`Seconds_Behind_Source` 算的是「当前时间 − 从库正在 apply 的那条事件在主库的时间戳」——它只反映「**正在 apply 的那条**有多旧」，不反映「relay log 里还积压多少」。binlog 还卡在网络上没传到从库时，SQL thread 无事可做，这个值可能显示 0，**假装没延迟**。更准的是 `pt-heartbeat`（主库写心跳、从库测差）或 GTID 差集（`Retrieved_Gtid_Set` vs `Executed_Gtid_Set` vs 主库 `gtid_executed`）。

## 要点

- 卡在大事务里时，`Seconds_Behind_Source` 也会失真（反映大事务开始时间，不反映队列深度）。
- 生产监控用 `pt-heartbeat` 配 Prometheus 告警，比裸 `Seconds_Behind_Source` 准。
- GTID 差集能精确算出「还差多少个事务没 apply」。

## 证据链接

- 实测注入 800ms 延迟看指标失真：[ch09 Scenario 01](../09-replication-and-ha/scenarios/01-replica-lag-and-seconds-behind.md)
- 章节原理：[ch09 §3.8](../09-replication-and-ha/README.md)

## 易追问的延伸

- **Q: 延迟六大原因？** → 大事务、长 DDL、主库写压力（单 SQL thread 上限）、从库硬件慢、网络、从库被读流量抢 CPU（ch09 §3.8）。
- **Q: 开了 MTS 还延迟？** → LOGICAL_CLOCK 并行度依赖主库 group commit 批次，低 TPS 批次小并行度上不去；用 WRITESET 或 `binlog_group_commit_sync_delay` 凑批（ch09 §3.10）。
