# Scenario 01: 注入主从延迟，看 `Seconds_Behind_Source` 为什么不准

> ⚠️ **实机状态**：本 scenario 的 lab 步骤已就绪（`00-lab` 的 toxiproxy + replica + `make chaos-replica-lag`）。本次撰写 session 中，宿主 Docker（OrbStack）中途重启导致从库容器网络损坏，**未能跑出真值**；复制拓扑本身在 session 早段已验证可用（`Replica_IO_Running: Yes` / `Auto_Position: 1`）。下方「实机告诉我」是**强预期**，请按步骤在稳定环境跑出真值替换（`make down && make up-replica && make replica-setup`）。

## 我想验证的问题

`Seconds_Behind_Source` 是大家最常用的延迟指标。但它准吗？如果主从之间有 800ms 网络延迟、主库又突然灌一批写，这个值能如实反映「从库落后多少」吗？

## 预期（基于 ch09 §3.8 推算）

`Seconds_Behind_Source` 的算法是 `当前时间 − 从库正在 apply 的那条事件在主库的时间戳`。它的毛病：

- 它反映的是「**正在 apply 的那条**有多旧」，不是「relay log 里还积压多少」。
- IO thread 还没把 binlog 拉过来时（网络延迟段），SQL thread 无事可做，`Seconds_Behind_Source` 可能显示 **0**，但其实主库已经写了一堆、只是还没传到从库——**假装没延迟**。
- 更准的是看 GTID 差集：`Retrieved_Gtid_Set`（IO 拉到的）vs `Executed_Gtid_Set`（SQL 执行的）vs 主库 `gtid_executed`。

## 环境 / 步骤

```bash
cd 00-lab
make up-replica && make replica-setup      # 起从库 + GTID 复制
make chaos-replica-lag MS=800              # toxiproxy 注入主→从 800ms 延迟

# 主库快速写一批
make mysql  ->  INSERT INTO repl_demo(v) SELECT 1 FROM information_schema.columns LIMIT 200;

# 立刻在从库看
make mysql-replica  ->  SHOW REPLICA STATUS\G     # 看 Seconds_Behind_Source / Retrieved vs Executed GTID
# 对比主从 gtid_executed
make mysql          ->  SELECT @@global.gtid_executed;
make mysql-replica  ->  SELECT @@global.gtid_executed;

make chaos-restore                         # 移除延迟，从库追上
```

## 实机告诉我（强预期，待跑真值替换）

```
# 注入 800ms 延迟、主库写 200 行后，立刻看从库：
Replica_IO_Running: Yes
Replica_SQL_Running: Yes
Seconds_Behind_Source: 0          ← 看起来「没延迟」，其实只是 binlog 还卡在 800ms 链路上没到
Retrieved_Gtid_Set: ...:1-50      ← IO 只拉到一部分
Executed_Gtid_Set:  ...:1-50

# 主库 vs 从库 gtid_executed（真实差距在这）：
primary: fd8a...:1-203
replica: fd8a...:1-150            ← 落后 53 个事务，但 Seconds_Behind_Source 没体现

# make chaos-restore 后等几秒：
Seconds_Behind_Source: 0          ← 这次是真的追上了
replica gtid_executed: fd8a...:1-203
```

## ⚠️ 预期 vs 实机落差（跑完补）

- 重点验证：延迟注入期间 `Seconds_Behind_Source` 是否真的显示一个**偏小甚至 0** 的值，而 GTID 差集却明确落后——证明「光看 Seconds_Behind_Source 会漏报延迟」。
- 工程结论：生产监控**别只靠 `Seconds_Behind_Source`**；用 `pt-heartbeat`（主库定时写心跳时间戳、从库测差）或 GTID 差集（`Retrieved` vs `Executed`）才靠谱（ch09 §3.8）。

## 连到的面试卡

- `99-interview-cards/q-replica-lag-metrics.md`
