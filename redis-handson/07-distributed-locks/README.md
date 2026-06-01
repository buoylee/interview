# 分布式锁（Distributed Locks）

## 1. 核心问题

多个进程 / 多台机器要互斥访问同一资源（扣库存、防重复下单、定时任务防并跑）。本章解决：**怎么用 Redis 加锁解锁，才能不误删、不死锁、不丢锁？** 以及 Redisson / RedLock 到底解决了什么、没解决什么。

## 2. 直觉理解

锁就是一个「谁先把 key SET 成功，谁就拥有」的约定。简单，但**难点全在异常路径**：
- 持有者拿到锁后**崩溃了** → 锁要能自动过期，否则死锁（别人永远拿不到）。
- 锁**过期了**，业务还没跑完 → 别人拿到了同一把锁，原持有者却以为还握着 → 解锁时把别人的锁删了（误删）。
- **Redis 自己挂了**（主从切换）→ 锁可能凭空蒸发，两个客户端同时"持有"。

正确的锁要把这三条都堵上。

## 3. 原理深入

### 3.1 正确加锁：`SET key <token> NX PX <ttl>`

一条命令同时做三件事：
- `NX`：key 不存在才设 → **互斥**。
- `PX <ttl>`：带过期 → 持有者崩了也会自动释放，**防死锁**。
- `<token>`：写一个**唯一值**（UUID / 线程标识）→ 标识「这把锁是我的」，解锁时校验归属。

⚠️ 不要用「`SETNX` + 单独 `EXPIRE`」两条命令——中间崩溃就只有锁没有过期，退化成死锁。必须用 `SET ... NX PX` 一条原子命令。

### 3.2 为什么解锁必须 Lua CAS

解锁 = 「确认是我的锁，再删」。如果分两步：
```
if GET lock == myToken:   # 判断
    DEL lock              # 删除
```
在「判断通过」和「DEL」之间，锁可能**刚好过期**、被别人抢到——这时 DEL 删掉的是**别人**的锁（sc01 实测：无校验的 `DEL` 直接删掉了他人的锁）。所以「判断 + 删除」必须在一条 Lua 脚本里原子完成：
```lua
if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) else return 0 end
```

### 3.3 看门狗（watchdog）

业务执行时间不确定，ttl 设短了会中途过期，设长了崩溃后占用久。**看门狗**解法：后台线程每 `ttl/3` 给锁 `PEXPIRE` 续期，续到业务结束或客户端崩溃为止（Redisson 默认 30s ttl、10s 续一次）。sc02 模拟验证：有续期则锁存活超过初始 ttl，停了续期就过期。**ttl 不能省**——它是「持有者彻底崩溃（连看门狗都停了）」时的兜底。

### 3.4 主从切换丢锁 & RedLock 争议

Redis 主从复制是**异步**的：master 确认加锁成功并返回 OK 后，若在把这条写命令复制到 slave **之前**就宕机，slave 升为新主后**没有这把锁**——另一个客户端能再次加锁，**两个客户端同时持有**（sc03 实测：真网络分区下复现了「新主无锁 + 重抢成功」的双重持有）。

- **RedLock**：向 N 个**相互独立**的 master 各加锁，过半（N/2+1）成功且总耗时小于 ttl 才算获得。意在消除单点丢锁。
- **Martin Kleppmann 的质疑**：GC 停顿、时钟漂移、网络延迟下，RedLock 也不能保证正确性（持有者 stop-the-world 暂停超过 ttl 后，锁过期被别人拿走，它醒来仍以为持锁）。
- **真正的正确性靠 fencing token**：每次获锁返回一个**单调递增**的 token，被保护资源（DB / 存储）在写入时校验 token，**拒绝比已见过的更小的 token** → 即使旧持有者"复活"也写不进去。锁只是性能优化，fencing 才是正确性保证。
- antirez 的回应：RedLock 在「锁仅用于效率（避免重复工作）而非正确性」的场景足够。

## 4. 日常开发应用

- **别手撸**，用 Redisson `RLock`：自带唯一 token、看门狗续期、可重入。
- 锁**粒度要细**（锁到具体资源 id，别锁整张表），减少竞争。
- 一定设**兜底过期**（即使有看门狗）。
- 涉及**正确性**（钱、库存）的场景，加 **fencing token**，别只靠锁。
- 可重入：用 hash 存 `{token: 重入次数}`，同 token 再次加锁则计数 +1，释放则 -1 到 0 才真删。

## 5. 调优实战

- **锁竞争激烈 / 吞吐低** → 多半是锁粒度太粗；拆细锁、或用分段锁。
- **锁频繁超时** → 业务比 ttl 慢；上看门狗或调大 ttl，并排查业务为何慢。
- **「锁莫名其妙丢了 / 两个任务并跑了」** → 先怀疑主从切换（sc03）；关键场景换 fencing token。

## 6. 面试高频考点

- **为什么解锁用 Lua？** 判断归属 + 删除要原子，否则误删别人的锁（sc01 实测）。
- **`SET NX` 为什么必须带 `PX`？** 防持有者崩溃后死锁（也呼应 06 章击穿互斥锁）。
- **看门狗原理？** 后台每 ttl/3 续期，续到业务结束/崩溃；ttl 是崩溃兜底。
- **RedLock 安全吗？** 消除单点丢锁，但 GC/时钟下仍不保证正确；正确性靠 fencing token（sc03 + 卡片）。
- **可重入怎么实现？** hash 存 token + 重入计数。

## 7. 一句话总结

单实例正确姿势 = **`SET NX PX <token>` 加锁 + Lua CAS 释放 + 看门狗续期**。跨主从存在**异步复制丢锁窗口**（sc03 实证），强正确性不能只靠锁，要靠 **fencing token**。生产直接用 Redisson `RLock`。

## 对照镜像（reference，不在 lab 跑）

```java
// Java / Redisson —— 生产首选,封装了 token + 看门狗 + 可重入
RLock lock = redisson.getLock("order:" + orderId);
if (lock.tryLock(3, TimeUnit.SECONDS)) {     // 等锁最多 3s;不传 leaseTime 则启用看门狗自动续期
    try { /* 临界区 */ }
    finally { lock.unlock(); }                // 内部就是 Lua CAS:校验 token + 计数 -1
}
```

```python
# redis-py —— 手写,看清原理
import uuid
token = str(uuid.uuid4())
if r.set("lock:order", token, nx=True, px=10000):      # SET NX PX
    try:
        ...  # 临界区(生产需自己起续期线程)
    finally:
        # Lua CAS 释放
        r.eval("if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
               1, "lock:order", token)
```

## Scenarios

- [01 - SET NX PX + Lua CAS 安全释放（误删复现）](scenarios/01-setnx-lua-safe-release.md)
- [02 - 看门狗续期](scenarios/02-watchdog-renewal.md)
- [03 - 主从切换丢锁（pause 没丢 vs 真断网丢失 + 双重持有）](scenarios/03-failover-lock-loss.md)
