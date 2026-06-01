# 用 Redis 实现分布式锁，正确姿势是什么？

## 一句话回答

加锁 `SET key <唯一token> NX PX <ttl>`（一条命令搞定互斥 + 防死锁 + 标识归属）；解锁用 **Lua CAS**（GET 比对 token == 自己再 DEL，原子）；业务可能超时就上**看门狗**续期。生产直接用 Redisson `RLock`。

## 三个异常路径与对策

| 异常 | 后果 | 对策 |
|---|---|---|
| 持有者崩溃 | 锁永不释放 → 死锁 | `PX <ttl>` 自动过期兜底 |
| 锁过期被别人拿走，原持有者解锁 | 误删别人的锁 | 解锁带 token + **Lua CAS** 原子校验（[sc01](../07-distributed-locks/scenarios/01-setnx-lua-safe-release.md)） |
| 业务比 ttl 慢 | 锁中途过期，别人闯入 | **看门狗**每 ttl/3 续期（[sc02](../07-distributed-locks/scenarios/02-watchdog-renewal.md)） |

## 关键点

- **为什么不能 `SETNX` + 单独 `EXPIRE`？** 两条命令非原子，中间崩溃就只有锁没过期 → 死锁。必须 `SET ... NX PX`。
- **为什么解锁要 Lua？** 「判断归属 + 删除」要原子，否则判断后、删除前锁过期被抢走仍会误删（sc01 实测裸 DEL 删掉了别人的锁）。
- **ttl 和看门狗的关系？** 看门狗让锁随持有者存活续命；ttl 是「持有者连看门狗一起崩溃」的兜底，不能省。
- **可重入怎么做？** 用 hash 存 `{token: 重入计数}`，同 token 再加锁计数 +1，释放 -1 到 0 才真删（Redisson 默认这么做）。

## 证据链接

- 章节原理：[07-distributed-locks §3](../07-distributed-locks/README.md)
- 实测：[sc01 误删+CAS](../07-distributed-locks/scenarios/01-setnx-lua-safe-release.md)、[sc02 看门狗](../07-distributed-locks/scenarios/02-watchdog-renewal.md)
- 主从丢锁的更深问题见：[q-redlock-controversy](q-redlock-controversy.md)
