# Redis 持久化:RDB / AOF / 混合,各保证不丢多少？

## 一句话回答

**RDB**=定时快照(fork+COW,快/小,崩在快照间丢一段);**AOF**=写命令日志(`everysec` 最多丢 1s、`always` 几乎不丢但慢 ~8 倍);**7.x 混合持久化**=multi-part AOF,base 用 RDB 格式 + incr 用 AOF 命令。要不丢开 AOF,RDB+AOF 同开时重启**优先用 AOF** 恢复。

## RDB vs AOF

| | RDB | AOF |
|---|---|---|
| 形式 | 内存快照(二进制) | 写命令日志 |
| 恢复 | 快、文件小 | 慢、文件大 |
| 丢数据 | 两次快照间全丢 | `everysec` ~1s / `always` 几乎不丢 |
| 机制 | `BGSAVE` fork 子进程 + COW | 追加 + `appendfsync` 刷盘 + rewrite |
| 用途 | 备份/迁移/主从全量同步 | 保不丢 |

## appendfsync 三档(sc02 实测)

| | 丢数据 | 吞吐 |
|---|---|---|
| `always` | 几乎不丢 | 35k rps(慢 8 倍) |
| `everysec` | 最多 ~1s | 289k rps(默认推荐) |
| `no` | 多 | ~313k rps |

## 实测证据

- 崩溃恢复:RDB-only `kill -9` 后 dbsize=0(丢光);AOF everysec → dbsize=100(全在);AOF 目录 = `*.base.rdb`(RDB格式)+`*.incr.aof`+manifest。[sc01](../05-persistence/scenarios/01-crash-recovery-rdb-vs-aof.md)
- `always` 35k vs `everysec` 289k vs 关 AOF 313k。[sc02](../05-persistence/scenarios/02-appendfsync-throughput.md)

## 易追问的延伸

- **BGSAVE 为什么 fork + COW?** 子进程写快照不阻塞主线程;COW 父子共享页、被写才复制,省内存但写多会涨。
- **混合持久化是什么?** 7.x multi-part AOF:base 用 RDB 格式(加载快)+ incr 用 AOF(不丢)。
- **AOF 为什么先执行命令后写日志?**(vs MySQL WAL 先写日志)避免记录错误命令、不阻塞;7.x client 收到 success 时已落盘。
- **延迟毛刺和持久化的关系?** fork(BGSAVE/AOF rewrite)会让主线程短暂卡;`latest_fork_usec`/`LATENCY HISTORY fork` 排查(12 章)。

## 证据链接

- 章节原理:[05-persistence](../05-persistence/README.md)
- 实测:[sc01 崩溃恢复](../05-persistence/scenarios/01-crash-recovery-rdb-vs-aof.md)、[sc02 fsync 吞吐](../05-persistence/scenarios/02-appendfsync-throughput.md)
