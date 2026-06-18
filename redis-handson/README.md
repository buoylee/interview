# Redis Hands-on — 系统笔记 + 实机白皮书

把 `interview/redis/` 的零散面试理论在实机上重新跑过一遍,沉淀成有结构的 scenario + 章节笔记 + 面试卡。**目标:从「会背」升级到「会用 + 知其所以然」。**

设计来源:`docs/superpowers/specs/2026-06-01-redis-handson-design.md`
目标版本:Redis 7.4。

## 怎么用这个 repo

1. **第一次来**:`cd 00-lab && make up`,等到 `redis healthy`。`make cli` 进 redis-cli 看到提示符就 OK。想要图形界面 `make up-ui` 开 http://localhost:5540。
2. **答不好「该不该用 Redis / 使用场景」**(面试最常答虚处):先读 `00-when-to-use/` —— 全 repo 的 top-down 选型导读,场景目录会把你带到对应章节当证据。
3. **想学某主题**:从章节 README 开始,每章固定 7 段(核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 调优实战 / 面试高频考点 / 一句话总结)。
4. **想答某面试题**:去 `99-interview-cards/` 找卡,每张卡链回 scenario 当证据。
5. **想加 scenario**:复制 `templates/scenario-template.md` 到对应章节 `scenarios/`,**先写「预期」、commit 一次**,再跑、再 commit 观察结果。

## 客户端语言约定

- **原理 / 运维 / 排查**:`redis-cli` + `redis.conf` + Lua(语言无关)。
- **应用模式(锁/限流/缓存重建)**:Java/Redisson 为主 + redis-py 对照镜像。

## 章节地图

- `00-when-to-use/` — **选型决策导读**:该不该用 Redis / 用哪种姿势 / 什么时候别用 / vs 替代品(top-down,场景目录链回各章)★
- `01-execution-model/` — 单线程 + epoll + io-threads + 什么命令会卡
- `02-data-structures/` — 5 类型 + 底层编码 + OBJECT ENCODING 实测 + 选型决策表 ← **第一个完整章节**
- `03-advanced-types/` — bitmap / HyperLogLog / GEO / Stream / bitfield
- `04-expiry-eviction/` — 惰性+定期删除 + 8 淘汰策略 + LRU/LFU
- `05-persistence/` — RDB / AOF / 混合 + 丢数据边界
- `06-caching-patterns/` — 缓存模式 + 一致性 + 穿透击穿雪崩 ★
- `07-distributed-locks/` — SETNX+Lua / Redisson 看门狗 / RedLock 争议
- `08-transactions-scripting/` — MULTI/WATCH / Lua / pipeline / FUNCTION
- `09-pubsub-streams-mq/` — pub/sub vs List vs Stream 当 MQ
- `10-replication-sentinel/` — psync / 复制积压 / 哨兵故障转移 / 脑裂
- `11-cluster/` — 槽 / CRC16 / MOVED&ASK / reshard / 故障转移
- `12-production-ops/` — 大key / 热key / SLOWLOG / 延迟毛刺 / 连接池 ★
- `13-rate-limiting/` — 固定/滑动窗口 / 令牌桶 / RRateLimiter
- `99-interview-cards/` — 反向产出的面试题答案卡

## Lab 速查

```bash
cd 00-lab
make up / down / reset                 # 单机生命周期
make cli                               # redis-cli
make load N=100000                     # 造 key
make encoding K=mykey                  # OBJECT ENCODING
make mem K=mykey                       # MEMORY USAGE
make slowlog / latency / bigkeys       # 观测
make up-cluster && make cluster-init   # 3主3从 + cli-cluster
make up-sentinel                       # 1主2从 + 3 哨兵
make up-obs                            # exporter + Prometheus + Grafana
make up-ui                             # RedisInsight
make chaos-lag MS=500 / chaos-restore  # toxiproxy 注入
```

## 纪律

1. **「预期」必须在跑之前写**,且单独 commit 一次。预期被实机污染就学不到东西了。
2. **「实机告诉我」当天填**。隔天就忘了当下的惊讶点。
3. **「⚠️ 预期 vs 实机落差」是这个方法的核心输出**。每个 scenario 都「完全对应预期」说明 scenario 太简单或预期太模糊。
