# Redis 学习 → 已迁移到 `redis-handson/`

> 这个目录早期是 2024 末写的零散面试理论笔记。系统化、可实机重跑的 Redis 学习/面试课程已重建在 **[`../redis-handson/`](../redis-handson/)**。

## 去哪学

➡️ **[`redis-handson/`](../redis-handson/)** —— 资深「会用 + 知其所以然」定位的动手课:

- 形态:13 章,每章七段式(核心问题 / 直觉 / 原理深入 / 日常开发 / 调优实战 / 面试高频 / 一句话总结)+ Docker lab(单机/cluster/哨兵/监控)+ 33 个 scenario(全 Redis 7.4.9 实机跑过,「预期 vs 实机落差」是核心产出)+ 16 张面试卡。
- 客户端约定:原理/运维/排查用 `redis-cli`+Lua(语言无关),应用模式(锁/限流/缓存)Java/Redisson 为主 + redis-py 对照。
- 设计 spec:[`docs/superpowers/specs/2026-06-01-redis-handson-design.md`](../docs/superpowers/specs/2026-06-01-redis-handson-design.md)
- 怎么用:`cd redis-handson/00-lab && make up && make cli`。

## 旧笔记

原来的 17 个 md(`概述.md`、`数据结构.md`、`持久化.md`、`部署模式.md`、`缓存穿透.md` 等)+ 图片已移到 [`_archive/`](./_archive/) 保留。
它们的内容已被新课**更完整地覆盖、且都用实机重新验证过**:

| 旧笔记 | 现在看(已实机验证) |
|--------|--------|
| `概述.md`、`单线程-网络IO.md`(单线程/epoll) | [`01-execution-model`](../redis-handson/01-execution-model/) |
| `数据结构.md`(编码/SDS/skiplist) | [`02-data-structures`](../redis-handson/02-data-structures/) |
| `redis-steam.md`、`redis-channel.md` | [`03-advanced-types`](../redis-handson/03-advanced-types/) + [`09-pubsub-streams-mq`](../redis-handson/09-pubsub-streams-mq/) |
| `淘汰策略.md` | [`04-expiry-eviction`](../redis-handson/04-expiry-eviction/) |
| `持久化.md`(RDB/AOF/混合) | [`05-persistence`](../redis-handson/05-persistence/) |
| `缓存.md`、`缓存穿透.md`(穿透/击穿/雪崩/布隆) | [`06-caching-patterns`](../redis-handson/06-caching-patterns/) |
| `redisson-rlock.md`、`redlock.md`、`分布式锁-redlock.md` | [`07-distributed-locks`](../redis-handson/07-distributed-locks/) |
| `事务-lua.md` | [`08-transactions-scripting`](../redis-handson/08-transactions-scripting/) |
| `部署模式.md`(主从/哨兵/cluster) | [`10-replication-sentinel`](../redis-handson/10-replication-sentinel/) + [`11-cluster`](../redis-handson/11-cluster/) |
| `redis-QA.md`(477 行 QA) | [`99-interview-cards/`](../redis-handson/99-interview-cards/) |
| `和Memcached的区别.md`、`参考.md` | 散见各章 README 的「面试高频」段 |

> 旧笔记里少数新课暂未单列的点(布谷鸟过滤器等)仍可在 `_archive/缓存穿透.md` 查阅。
