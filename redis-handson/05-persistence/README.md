# 持久化（RDB / AOF / 混合）

## 1. 核心问题

Redis 数据在内存里，进程一挂就没了。持久化解决「重启后还能不能恢复」。本章讲清:RDB 快照、AOF 命令日志、7.x 的混合持久化(multi-part AOF)各怎么工作、**各自能保证不丢多少数据**、以及刷盘策略对性能的影响。

## 2. 直觉理解

两种思路:
- **RDB**=定时给内存拍**快照**存成一个二进制文件。恢复快、文件小,但两次快照之间崩溃就丢这段(sc01 实测:无快照崩溃 → 数据全丢)。
- **AOF**=把每条**写命令**追加到日志,重启时重放。丢得少(取决于刷盘频率),但文件大、恢复慢。
- **混合**(7.x 默认)=AOF 的 base 用 RDB 格式(快),tail 用 AOF 命令(不丢),两全。

一句话:**RDB 管「快」,AOF 管「不丢」,混合两者兼得。**

## 3. 原理深入

### 3.1 RDB:快照 + fork + COW
- `SAVE`(阻塞主线程,别用)/ `BGSAVE`(后台)。`BGSAVE` 时主进程 **fork** 出子进程,子进程把内存写成 `dump.rdb`。
- **COW(写时复制)**:fork 后父子共享内存页,父进程继续接写请求,被写的页才复制一份。所以 fork 期间内存可能涨(取决于写入量),大实例 fork 本身也会让主线程短暂卡顿(见 12 章延迟归因)。
- 触发:`save <秒> <改动数>` 规则(如 `save 60 1000`)、手动 `BGSAVE`、关机。

### 3.2 AOF:命令日志 + 刷盘 + rewrite
- 每条写命令先执行、再**追加**到 AOF 缓冲,按 `appendfsync` 刷盘:
  | appendfsync | 行为 | 丢数据 | 吞吐(sc02 实测) |
  |---|---|---|---|
  | `always` | 每条命令都 fsync | 几乎不丢 | ~35k rps(慢 ~8 倍) |
  | `everysec` | 每秒 fsync 一次 | 最多丢 ~1s | ~289k rps(默认,推荐) |
  | `no` | 交给 OS 刷 | 丢得多 | 最快 |
- **AOF rewrite**:AOF 会越追越大,`BGREWRITEAOF`(也 fork)用当前内存状态重写出一个更小的等价 AOF。
- **为什么先执行后写日志?**(与 MySQL redo 的 WAL 相反)避免记录错误命令、不阻塞当前写;代价是命令执行成功但写日志前崩溃会丢这条(7.x 的回复在刷盘后的下个 eventloop 才发,client 收到 success 即已落盘——见旧笔记 `redis/持久化.md`)。

### 3.3 混合持久化(Redis 7 multi-part AOF)
7.x 默认 `aof-use-rdb-preamble yes`。AOF 不再是单文件,而是 `appendonlydir/` 下一组(sc01 实测):
- `appendonly.aof.1.base.rdb`——**base 用 RDB 格式**(加载快)
- `appendonly.aof.1.incr.aof`——增量命令(不丢)
- `appendonly.aof.manifest`——清单
恢复时先加载 base.rdb 再重放 incr.aof,兼得 RDB 的快与 AOF 的不丢。

### 3.4 数据丢失边界(sc01 实测)
- RDB-only + 两次快照间崩溃 → 丢这段全部(实测无快照崩溃 dbsize 归零)。
- AOF everysec → 最多丢 ~1s。
- AOF always → 几乎不丢(代价 8 倍吞吐)。
- RDB+AOF 同时开,重启**优先用 AOF 恢复**(丢得最少)。

## 4. 日常开发应用

- 要「尽量不丢」→ 开 AOF `everysec`(默认就是,平衡点);对丢数据零容忍且能接受慢 → `always`(很少用)。
- 要快速备份/迁移/主从全量同步 → RDB(`BGSAVE` 出的 `dump.rdb`)。
- 生产一般**两个都开**(RDB 做备份、AOF 保不丢),7.x 混合持久化已是默认形态。
- `BGSAVE`/`BGREWRITEAOF` 都 fork,挑低峰期;监控 fork 耗时(`INFO stats` 的 `latest_fork_usec`)。

## 5. 调优实战

- **重启后数据少了** → 查是不是只开了 RDB 且崩在快照间;或 AOF 没开/被 `appendonly no`。
- **写吞吐上不去** → 是不是 `appendfsync always`(sc02:慢 8 倍),改 `everysec`。
- **周期性延迟毛刺** → fork(BGSAVE/AOF rewrite)导致;`LATENCY HISTORY fork`、`latest_fork_usec`,挑低峰、控实例大小。
- **AOF 文件巨大** → 触发/调 `auto-aof-rewrite-percentage`。

## 6. 面试高频考点

- **RDB vs AOF 区别与取舍**:快/小 vs 不丢/大;恢复优先 AOF。
- **appendfsync 三档 + 各丢多少**(always/everysec/no)。
- **BGSAVE 为什么用 fork + COW**:不阻塞主线程;COW 省内存但写多会涨。
- **混合持久化是什么**:7.x multi-part AOF,base 用 RDB 格式 + incr 用 AOF。
- **AOF 为什么后写日志**(vs WAL):避免记错命令、不阻塞;client 收到 success 时已落盘。

## 7. 一句话总结

**RDB** 快照(fork+COW,快/小,崩在快照间丢一段);**AOF** 命令日志(`everysec` 最多丢 1s、`always` 慢 8 倍但几乎不丢);**7.x 混合持久化**=AOF 的 base 用 RDB 格式 + incr 用 AOF,默认形态。要不丢开 AOF,重启优先 AOF 恢复。

## Scenarios

- [01 - 崩溃恢复:RDB-only 丢数据 vs AOF 不丢 + multi-part AOF 结构](scenarios/01-crash-recovery-rdb-vs-aof.md)
- [02 - appendfsync always vs everysec 吞吐对比](scenarios/02-appendfsync-throughput.md)
