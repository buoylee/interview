# （架构师）一波密集写入，MySQL 内部怎么连锁反应？写 TPS 上不去查哪？

## 一句话回答

一条写入会同时：**改页（Buffer Pool 脏页↑，ch02）+ 写 redo（LSN↑，ch07）+ 按 WHERE 加锁（ch06）**。密集写入让 **checkpoint age = LSN − Last checkpoint** 逼近 redo 容量，触发**自适应刷脏**狂刷脏页抢 IO；当刷脏能力（受 `innodb_io_capacity` 限）跟不上时，InnoDB **回压、限流写入**——所以「写 TPS 莫名上不去、但 CPU/锁都不忙」时，第一嫌疑是 **redo 容量太小 / io_capacity 卡住刷脏**，而不是 SQL 本身。

## 要点

- 实测 redo=100MB：checkpoint age 冲到 83% 被自适应刷脏摁住、不报错（健康）。
- 实测 redo=32MB：checkpoint age 钉死在 81%，写入被限流到 TPS 天花板，6 个 storm 2 分钟跑不完（**redo 太小不报错，只悄悄限流**）。
- WHERE 没走索引（`type=ALL`）会把这条链每个环节同时放大：扫更多行→改更多页→写更多 redo→锁更多行。

## 证据链接

- 写风暴跨章整合实测（顶住 vs 限流两组数据）：[ch11 Scenario 01](../11-ops-and-troubleshooting/scenarios/01-write-storm-checkpoint-throttle.md)
- 关联：[redo/checkpoint](q-wal-redo-checkpoint.md) · [无索引锁全表](q-no-index-lock-escalation.md)

## 易追问的延伸

- **Q: 怎么定位是 redo 瓶颈？** → `SHOW ENGINE INNODB STATUS` LOG 段看 checkpoint age 是否长期贴着 redo 容量的 ~75-80%；是则刷脏在硬顶。
- **Q: 怎么扛写入尖峰？** → 加大 `innodb_redo_log_capacity` + 提 `innodb_io_capacity_max` + 加大 Buffer Pool，三者配套，缺一会成新瓶颈。
- **Q: log_waits 一定会涨吗？** → 不一定。InnoDB 多靠「限流写入」把 checkpoint age 摁在墙下，所以常见症状是 TPS 下降而非 `log_waits` 报警。
