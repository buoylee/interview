# Scenario 01（架构师整合）: 写风暴下 redo × Buffer Pool × checkpoint 怎么互相拖垮

> 这是一道**跨章综合大题**：把 ch02（Buffer Pool/刷脏）、ch04（执行/影响行数）、ch06（锁）、ch07（redo/checkpoint）串成一条写入压力下的因果链。单实例就能跑出来。

## 我想验证的问题

一波密集写入打进来，系统内部会怎样连锁反应？具体地：

- redo 的 LSN 冲在前面，checkpoint（脏页落盘进度）追得上吗？二者之差（checkpoint age）会涨到哪？
- Buffer Pool 的脏页会堆多高？page cleaner 会不会自己加速？
- redo log **开太小**会发生什么——报错？还是别的？
- 这条链上，哪个环节先成为瓶颈、对外表现成什么症状？

## 预期（基于 ch02 §3.3 + ch07 §3.3 推算）

写入 → 改页（Buffer Pool 脏页 +1）+ 写 redo（LSN 推进）。脏页不立刻落盘（WAL），所以 **checkpoint age = LSN − Last checkpoint** 会涨。InnoDB 有**自适应刷脏**（adaptive flush）：checkpoint age 越接近 redo 容量，page cleaner 刷得越猛，试图把它摁在墙下。预期：

- **redo 够大**：checkpoint age 冲高后被自适应刷脏压住，在某条水位线附近震荡，不报错。
- **redo 太小**：checkpoint age 很快顶到水位线，InnoDB 只能**限流写入**（让写等刷脏）来不让它越界 → 对外表现是「**写入 TPS 莫名被卡住**」，而不是报错。

## 环境

- `up2`（5 万行）+ 存储过程 `storm(n)`：做 n 次全表 `UPDATE`（每次弄脏大量页、写约 4.3MB redo）
- 关键参数：`innodb_buffer_pool_size=256MB`（16384 页）、`innodb_redo_log_capacity=100MB`、`innodb_io_capacity=200`（故意调低，刷脏慢、好观察）
- 采样：`SHOW ENGINE INNODB STATUS` 的 LOG 段算 checkpoint age；状态变量 `Innodb_buffer_pool_pages_dirty / _pages_flushed / Innodb_log_waits / Innodb_buffer_pool_wait_free`

```sql
DELIMITER //
CREATE PROCEDURE storm(n INT)
BEGIN DECLARE i INT DEFAULT 0;
  WHILE i<n DO UPDATE up2 SET age=age+1; SET i=i+1; END WHILE;
END //
DELIMITER ;
```

## 步骤

1. **A（redo=100MB）**：4 个连接并发 `CALL storm(150)`，每秒采一次 checkpoint age / 脏页% / 累计刷脏页。
2. **B（redo=32MB）**：`SET GLOBAL innodb_redo_log_capacity=32*1024*1024;`，再用 6 个并发 storm 压，观察 checkpoint age 顶到哪、写入是否被限流。跑完 `SET GLOBAL ... =100MB` 还原。

## 实机告诉我（本机实测，MySQL 8.0.36）

### A. redo=100MB —— 自适应刷脏「顶住」

```
基线   ckp_age=    0KB( 0%redo) dirty= 0% flushed=15161
T+1s   ckp_age=43104KB(42%redo) dirty= 7% flushed=15361
T+2s   ckp_age=74243KB(72%redo) dirty=12% flushed=16305
T+4s   ckp_age=85368KB(83%redo) dirty=13% flushed=18589   ← 冲到 83%
T+6s   ckp_age=84646KB(82%redo) dirty= 8% flushed=21218
T+8s   ckp_age=85368KB(83%redo) dirty=13% flushed=23348   ← 被摁在 ~83% 震荡
T+10s  ckp_age=85368KB(83%redo) dirty= 5% flushed=26781
T+14s  ckp_age=71283KB(69%redo) dirty=11% flushed=29437
风暴后 ckp_age=64555KB(63%redo) dirty= 7% flushed=85744   ← 风暴停, 刷脏狂追(+5万页)
全程 log_waits=0  wait_free=0
```

- checkpoint age 2 秒内冲到 **83% redo 容量**，然后**被自适应刷脏死死摁在 ~83% 那条线震荡**——`flushed` 从 15161 一路涨到 29437（风暴中 14 秒刷了 ~1.4 万页），风暴一停又暴冲到 85744（把积压脏页清掉）。
- 脏页比例在 5%~13% 之间，page cleaner 跟得上，没有 `log_waits` / `wait_free`。
- **这是健康的「顶住」**：redo 足够大 + 自适应刷脏 = checkpoint age 被钉在墙（100%）下面。

### B. redo=32MB —— checkpoint age 顶到水位、写入被限流

```
redo 现= 32MB
基线   ckp_age=    0KB(  0%redo) dirty= 0%
T+1s   ckp_age=26749KB( 81%redo) dirty= 4% flushed=87547
T+4s   ckp_age=26749KB( 81%redo) dirty= 4% flushed=89298
T+8s   ckp_age=26749KB( 81%redo) dirty= 4% flushed=90431
T+12s  ckp_age=26749KB( 81%redo) dirty= 3% flushed=93798
全程 log_waits=0
（6 个并发 storm 跑了 2 分钟都没跑完 —— 写入被限流，UPDATE 慢到爬）
```

- checkpoint age **被精确钉死在 26749KB = 32MB 的 81%**，纹丝不动整整 12 秒。
- 没有报错、`log_waits` 仍是 0——但**写入被严重限流**：同样的 6 个 storm，2 分钟都没跑完（不得不 KILL）。InnoDB 为了不让 checkpoint age 越过水位，**让写入操作去等刷脏**，于是 TPS 被锁死在「刷脏能力」这个上限上。

## ⚠️ 预期 vs 实机落差

- 预期方向全中，但**最反直觉、也最该带走的一点**：redo 开太小**不会报错**，而是把写入 TPS **悄悄**压到「单位时间能刷多少脏页」这个天花板。生产上表现成「写入毫无征兆地变慢、QPS 上不去」，查半天 SQL、索引、锁都没问题——根因在 redo 容量 + io_capacity 这条刷脂线。
- 把四章串起来的因果链（架构师要能完整口述）：
  1. **一条写入** = 改聚簇/二级索引页（ch02 脏页）+ 写 redo（ch07 LSN↑）+ 按 WHERE 加锁（ch06；没索引就锁全表，见 [Scenario 01](../../06-locking/scenarios/01-no-index-locks-whole-table.md)）。
  2. WHERE 没走索引（ch04 `type=ALL`）→ 扫更多行 → 改更多页 + 写更多 redo + 锁更多行 → **同一波写入把这条链上每个环节都放大**。
  3. redo 涨快（ch07）→ checkpoint age 逼近容量 → 自适应刷脏猛刷（ch02）→ 抢 IO（io_capacity 上限）→ 刷不动时**回压写入**（限流）+ 脏页/锁堆积 → 锁等待 + 慢查询雪崩（ch11 各 SOP）。
- 直接可用的诊断/调参：
  - `SHOW ENGINE INNODB STATUS` LOG 段，盯 **`Log sequence number` 与 `Last checkpoint at` 的差**（checkpoint age）。长期贴着 redo 容量的 ~75-80% = 刷脏在拼命顶 → 写压力过大或 redo 偏小。
  - 写入 TPS 上不去、但 CPU/锁都不忙 → 查 `innodb_redo_log_capacity` 是否过小、`innodb_io_capacity(_max)` 是否卡住刷脏速度。
  - 真要扛写入尖峰：**加大 redo（给 checkpoint age 更多缓冲）+ 提高 io_capacity_max（让刷脏跟得上）+ 加大 Buffer Pool（容纳脏页）**，三者配套，缺一会成为新瓶颈。

## 连到的面试卡

- `99-interview-cards/q-write-storm-pipeline.md`
