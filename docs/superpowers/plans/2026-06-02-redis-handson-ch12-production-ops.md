# Redis Hands-on 第 12 章 生产运维 Implementation Plan

> REQUIRED SUB-SKILL: superpowers:executing-plans。

**Goal:** 写出 `12-production-ops` 的 7 段 README + 3 个**已实测**可跑 scenario(大key定位拆分 / 热key定位 / 慢命令与延迟归因)+ 2 张面试卡,补完 Phase 1 最后一块真空区——「线上出事怎么查」。

**Architecture:** 单机 Redis cli。大key/热key 用 `--bigkeys/--memkeys/--hotkeys` + `MEMORY USAGE/OBJECT FREQ`;慢命令用 `SLOWLOG`;延迟用 `LATENCY` 监控。连接池 / RESP3 客户端缓存(`CLIENT TRACKING`,连接级,演示不便)/ ACL 安全 在 README 讲解。

**Tech Stack:** Redis 7.4、redis-cli `--bigkeys/--memkeys/--hotkeys`、`SLOWLOG`、`LATENCY`、`OBJECT FREQ`、`MEMORY USAGE`。

参考 spec §12。范式:02/06/07 章。

---

## File Structure
```
redis-handson/12-production-ops/
├── README.md
└── scenarios/
    ├── 01-bigkey-locate-and-split.md
    ├── 02-hotkey-locate-lfu.md
    └── 03-slowlog-and-latency.md
redis-handson/99-interview-cards/
├── q-redis-bigkey-hotkey.md
└── q-redis-latency-troubleshooting.md
```

## 已实测的关键数据(写 scenario 时用)

- **sc01 大key**:`bighash` = hashtable / 2786544B(2.78MB)/ 50000 字段;`HGETALL bighash` 延迟 4ms(单线程阻塞);拆成 500 个 100 字段分片 → 每片 **listpack** → 合计 **895584B(0.87MB,降到 ~1/3)**。`--bigkeys` 能定位到它。
- **sc02 热key**:`maxmemory-policy allkeys-lfu` 下偏斜访问,`OBJECT FREQ hot:A=38`(LFU 对数计数,非真实次数)、`hot:B=9`;`--hotkeys` 列出 hot:A(38)/hot:B(9)。
- **sc03 慢命令/延迟**:`slowlog-log-slower-than` 降到 1000µs 后,`KEYS *`(10万 key)耗 **~4.7ms** 进 SLOWLOG;`LATENCY` 把超阈值命令记为 `command` 事件——阈值 50ms 时 `DEBUG SLEEP 0.2` 留 200ms 记录,但**默认阈值 100ms 会滤掉几 ms 的命令**(KEYS* 4.5ms 抓不到)。两个坑:`enable-debug-command` 默认 `no`(DEBUG 被禁,本 lab 开启);默认阈值偏高要调低。
  > 注:lab 的 `redis.conf` 已加 `enable-debug-command yes`(01 阻塞演示、延迟监控等需要)。

## Tasks

### Task 1: README（7 段）
要点:
1. 核心问题:线上 Redis 出事(慢、内存涨、CPU 高、延迟毛刺)怎么定位治理。
2. 直觉:Redis 单线程,任何一个**大 key 操作 / 慢命令 / fork 阻塞**都会卡住所有请求;运维就是「找出谁在卡、为什么卡」。
3. 原理深入:
   - **大key**:单 key 过大 → 操作 O(N) 阻塞、迁移/删除卡顿、网络打满。定位 `--bigkeys`(按类型最大)/`--memkeys`(按内存)/`MEMORY USAGE`。治理:拆分(分片成 listpack)、`UNLINK` 异步删、`HSCAN` 渐进读。
   - **热key**:单 key QPS 过高 → 单分片/单线程热点。定位 `--hotkeys`(需 LFU)/`OBJECT FREQ`。治理:本地缓存、读副本、key 打散(加随机后缀分散到多 key)。
   - **慢命令**:`SLOWLOG`(超 `slowlog-log-slower-than` µs 记录);避免 `KEYS`/大 `LRANGE`/大 `SORT`,用 `SCAN`。
   - **延迟毛刺归因**:`LATENCY DOCTOR/LATEST/HISTORY`;常见源:fork(bgsave/AOF rewrite)、AOF fsync、THP、swap、大 key、慢命令。
   - **连接**:连接池(复用,别每次新建)、`maxclients`、`CLIENT LIST/KILL`。
   - **RESP3 客户端缓存**:`CLIENT TRACKING ON`,服务端 key 变更推 invalidation,客户端本地缓存(连接级特性)。
   - **安全**:`protected-mode`、`requirepass`、ACL `user`、禁危险命令(`rename-command`)。
4. 日常开发:别造大key/热key(设计期就拆);线上慎用 `KEYS/FLUSHALL/大range`;删大key用 `UNLINK`。
5. 调优实战:三件套排查 SOP —— ① `--bigkeys`/`--memkeys` 找大key ② `SLOWLOG GET` 找慢命令 ③ `LATENCY DOCTOR` 找毛刺源。
6. 面试高频:大key危害与治理、热key打散、`SLOWLOG` 用法、延迟毛刺归因、`SCAN` vs `KEYS`、`UNLINK` vs `DEL`。
7. 一句话总结:Redis 单线程,运维核心是「别让任何单次操作卡住事件循环」——大key拆、热key散、慢命令换 SCAN、毛刺看 LATENCY DOCTOR。
- 末尾对照:连接池(Jedis/Lettuce pool、redis-py ConnectionPool)、RESP3 client-side caching 简述。
- Commit `redis-handson: 12-production-ops README(7段+大key热key慢查延迟+连接安全)`

### Task 2: sc01 大key 定位与拆分（用上面已测数据）
Commit `redis-handson: scenario 12-01 大key 定位(--bigkeys)+拆分省2/3内存`

### Task 3: sc02 热key 定位（LFU + --hotkeys）
Commit `redis-handson: scenario 12-02 热key 定位(LFU/OBJECT FREQ/--hotkeys)`

### Task 4: sc03 慢命令与延迟归因（SLOWLOG + LATENCY，含 DEBUG SLEEP 不计入落差）
Commit `redis-handson: scenario 12-03 SLOWLOG + LATENCY 延迟归因`

### Task 5: 面试卡 大key/热key 治理
`q-redis-bigkey-hotkey.md`。Commit `redis-handson: 面试卡 大key热key定位与治理`

### Task 6: 面试卡 延迟排查 SOP
`q-redis-latency-troubleshooting.md`。Commit `redis-handson: 面试卡 延迟毛刺排查SOP`

## Self-Review
- 覆盖 spec §12(大key/热key/SLOWLOG/延迟/连接池/客户端缓存/ACL)。✅ 客户端缓存因连接级特性以 README 讲解替代 scenario。
- 3 scenario 全已实测。
- 收尾:`make up` 单机 + flushall 回干净。

**下一步**:执行;Phase 1(02/06/07/12)四章真空区收官。
