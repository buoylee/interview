# 生产运维与排查（Production Ops & Troubleshooting）

## 1. 核心问题

线上 Redis 出事——**变慢 / 内存暴涨 / CPU 飙高 / 延迟毛刺 / 连接耗尽**——怎么快速定位是谁在卡、为什么卡、怎么治。本章把「出事怎么查」的工具链跑一遍。

## 2. 直觉理解

记住一句话:**Redis 主线程是单线程的**。所以任何一次「大 key 操作 / 慢命令 / fork 阻塞」都会**卡住所有其他请求**——不是这条请求慢，是它后面排队的全慢。运维的本质就是：**别让任何单次操作长时间占住事件循环**，以及出事后快速找到那个占住的家伙。

## 3. 原理深入

### 3.1 大 key（big key）
- **危害**:单 key 过大 → 操作 O(N) 阻塞主线程（`HGETALL`/`SMEMBERS` 全量）、`DEL` 卡顿、迁移/持久化拖慢、网络带宽打满。
- **定位**:`redis-cli --bigkeys`（每种类型最大的 key）、`--memkeys`（按内存采样）、`MEMORY USAGE <key>`（精确字节）。
- **治理**:**拆分**（大 hash/zset 分片成多个小 key，每片落 listpack 反而更省内存——sc01 实测拆分后内存降到 ~1/3）；删大 key 用 **`UNLINK`**（异步回收，不阻塞）而非 `DEL`；读用 `HSCAN`/`SSCAN` 渐进遍历，不要全量。

### 3.2 热 key（hot key）
- **危害**:单 key QPS 过高 → 集中打在它所在的单个分片/单线程上，cluster 下某个节点被打爆。
- **定位**:`redis-cli --hotkeys`（需 `maxmemory-policy` 为 LFU）、`OBJECT FREQ <key>`（LFU 访问频率，**对数计数**不是真实次数 —— sc02 实测 5000 次访问 freq 只到 38）。
- **治理**:本地缓存（JVM/进程内挡一层）、读副本分摊、**key 打散**（`hot:k` → `hot:k:{0..N}` 随机分散到多 key/多分片）。

### 3.3 慢命令与 SLOWLOG
- `SLOWLOG`:执行超过 `slowlog-log-slower-than`（微秒）的命令被记录，`SLOWLOG GET n` 查看，`SLOWLOG RESET` 清空。
- 元凶常是 `KEYS *`（O(N) 扫全库，sc03 实测 10 万 key 耗 4.5ms）、大 `LRANGE 0 -1`、大 `SORT`、复杂 Lua。**线上一律用 `SCAN` 替代 `KEYS`**。

### 3.4 延迟毛刺归因
- `LATENCY DOCTOR`（人话诊断）、`LATENCY LATEST`、`LATENCY HISTORY <event>`、`LATENCY RESET`；开关靠 `latency-monitor-threshold <ms>`。
- 常见延迟源:**fork**（bgsave / AOF rewrite，大实例 fork 慢）、**AOF fsync**（`appendfsync always` 每次刷盘）、**THP**（透明大页，建议关）、**swap**（内存不足换出，致命）、大 key、慢命令。
- ⚠️ 实测发现:**`DEBUG SLEEP` 不会被 LATENCY 监控记录**（它是合成阻塞，不计入命令延迟采样）；只有**真实重命令**（全量 LRANGE/HGETALL 等）才记为 `command` 事件（sc03）。

### 3.5 连接与安全
- **连接池**:客户端复用连接，别每请求新建（建连有 TCP+认证开销）；`maxclients` 限上限；`CLIENT LIST`/`CLIENT KILL` 查杀。
- **RESP3 客户端缓存**:`CLIENT TRACKING ON`（连接级），服务端在 key 变更时推 invalidation 消息，客户端可安全地本地缓存读结果，减少往返。是连接级特性。
- **安全**:`protected-mode`、`requirepass`、**ACL**（`user` 细粒度授权）、`rename-command` 禁掉/改名危险命令(`FLUSHALL`/`KEYS`/`DEBUG`)。

## 4. 日常开发应用

- 设计期就别造大 key / 热 key（按 id 分片、热点打散）。
- 线上**禁** `KEYS`、`FLUSHALL`、大 range、`MONITOR`（长跑）；删大 key 用 `UNLINK`。
- 客户端用连接池;关键实例配 ACL + 改名危险命令。

## 5. 调优实战 —— 出事三件套 SOP

1. **内存涨 / 单命令慢** → `redis-cli --bigkeys` + `--memkeys` 找大 key，`MEMORY USAGE` 量化，拆分/`UNLINK`。
2. **某命令拖累全局** → `SLOWLOG GET 10` 找慢命令，看是不是 `KEYS`/大 range，换 `SCAN`。
3. **周期性延迟毛刺** → `LATENCY DOCTOR` + `LATENCY HISTORY`，对照 fork（bgsave 时间点）/ AOF rewrite / swap（`INFO memory` 看 `mem_fragmentation_ratio`、机器 swap）。

## 6. 面试高频考点

- **大 key 危害 + 怎么定位治理**:O(N) 阻塞单线程；`--bigkeys`/`--memkeys` 定位；拆分 + `UNLINK` + `SCAN`。
- **热 key 怎么发现和打散**:`--hotkeys`（LFU）;本地缓存 / 读副本 / key 加随机后缀分散。
- **`SCAN` 为什么比 `KEYS` 好**:游标渐进、每次 O(1) 摊还、不阻塞（见 01 章 SCAN）。
- **`UNLINK` vs `DEL`**:UNLINK 后台线程异步回收内存，不阻塞主线程。
- **延迟毛刺怎么归因**:`LATENCY DOCTOR`;重点查 fork / AOF fsync / THP / swap。

## 7. 一句话总结

Redis 单线程,运维核心是**别让任何单次操作卡住事件循环**:大 key 拆分 + `UNLINK`、热 key 打散、慢命令用 `SCAN` 替 `KEYS`、延迟毛刺用 `LATENCY DOCTOR` 归因(重点 fork/AOF/THP/swap)。出事先跑三件套:`--bigkeys` → `SLOWLOG GET` → `LATENCY DOCTOR`。

## 对照镜像（reference）

- 连接池:Java `JedisPool`/`LettuceConnectionFactory`、Python `redis.ConnectionPool(max_connections=...)`——复用连接、控上限。
- RESP3 客户端缓存:`redis-py` `Redis(protocol=3)` + 客户端侧缓存库;Lettuce 支持 client-side caching。

## Scenarios

- [01 - 大 key 定位（--bigkeys）与拆分省内存](scenarios/01-bigkey-locate-and-split.md)
- [02 - 热 key 定位（LFU / OBJECT FREQ / --hotkeys）](scenarios/02-hotkey-locate-lfu.md)
- [03 - SLOWLOG 抓慢命令 + LATENCY 延迟归因](scenarios/03-slowlog-and-latency.md)
