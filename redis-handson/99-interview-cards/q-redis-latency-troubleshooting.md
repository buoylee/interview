# Redis 延迟毛刺 / 变慢，怎么排查？

## 一句话回答

Redis 单线程,变慢=有东西卡住了事件循环。**出事三件套**:`--bigkeys`/`--memkeys` 找大 key → `SLOWLOG GET` 找慢命令 → `LATENCY DOCTOR` 找延迟源（fork / AOF fsync / THP / swap）。

## 排查 SOP

1. **`SLOWLOG GET 10`** —— 哪条命令慢?常见元凶 `KEYS *`（实测 10 万 key 4.5ms）、大 `LRANGE 0 -1`、大 `SORT`、复杂 Lua → 改用 `SCAN`、分页。
2. **`--bigkeys` / `--memkeys`** —— 是不是某个大 key 的 O(N) 操作在阻塞 → 拆分 + `UNLINK`。
3. **`LATENCY DOCTOR` / `LATENCY HISTORY <event>`** —— 周期性毛刺归因:
   - `fork` 事件 → bgsave / AOF rewrite（大实例 fork 慢，对齐 RDB 时间点）
   - `aof-fsync` → `appendfsync always` 太激进
   - 机器层:**THP**（透明大页,建议关）、**swap**（内存不足换出,致命,`INFO memory` + 机器 swap）
4. **`INFO`** —— `mem_fragmentation_ratio`（碎片）、`connected_clients`（连接耗尽）、`instantaneous_ops_per_sec`、`keyspace_hits/misses`。

## 易踩的坑（实测）

- **`latency-monitor-threshold` 默认 100ms 偏高**:几 ms 的慢命令(如 `KEYS *` ~4.5ms)根本不进 `LATENCY` —— 排查时先调低阈值。[sc03](../12-production-ops/scenarios/03-slowlog-and-latency.md)
- **`DEBUG` 默认被禁**(`enable-debug-command no`):生产上不能直接 `DEBUG SLEEP` 现场测;开启 + 调低阈值后,`DEBUG SLEEP` 与真实重命令都会记为 `command` 事件。
- `SLOWLOG` 阈值 `slowlog-log-slower-than`（微秒);线上别设太低否则日志爆。

## 易追问的延伸

- **fork 为什么导致毛刺?** bgsave/AOF rewrite 要 fork 子进程,COW 下大实例复制页表耗时,fork 期间主线程阻塞。
- **`SCAN` 为什么不阻塞?** 游标渐进、每次只扫一小批、O(1) 摊还(见 01 章)。
- **`MONITOR` 能长期开吗?** 不能,它转发所有命令,本身就是性能杀手,只短期诊断用。

## 证据链接

- 章节原理:[12-production-ops §3.3/§3.4](../12-production-ops/README.md)
- 实测:[sc03 SLOWLOG + LATENCY](../12-production-ops/scenarios/03-slowlog-and-latency.md)
