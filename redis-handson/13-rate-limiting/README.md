# 限流（Rate Limiting）

## 1. 核心问题

用 Redis 给接口/用户做限流(每秒最多 N 次)。本章讲清三种算法——**固定窗口 / 滑动窗口 / 令牌桶**——各自怎么实现、有什么坑(尤其固定窗口的「临界突刺」),以及为什么要用 Lua 保证原子。

## 2. 直觉理解

- **固定窗口**:按整秒分桶,每桶计数,超了拒。简单,但**两个相邻桶的边界处会放过 ~2 倍流量**(桶 N 末尾 5 个 + 桶 N+1 开头 5 个,挨在一起就是 1 秒内 10 个,sc01 实测)。
- **滑动窗口**:盯「最近 1 秒」这个一直在滑动的区间,不分死桶,所以没有边界突刺(sc02 实测堵住)。代价:要存每个请求的时间戳(ZSet)。
- **令牌桶**:桶按速率匀速加令牌,每个请求拿一个;桶里有令牌就放、没有就拒。**允许突发**(桶满时能一下放一批),又限均速——很多场景更贴合真实需求。

## 3. 原理深入

### 3.1 固定窗口（INCR + EXPIRE）
```lua
-- key=rl:<当前秒>;INCR,<=limit 放行
local k='rl:'..redis.call('TIME')[1]
local c=redis.call('incr',k); redis.call('expire',k,2)
return c<=LIMIT and 1 or 0
```
- 优点:O(1)、省内存(一个计数器)。
- **缺点:临界突刺**。limit=5/秒,sc01 实测:窗口边界两侧各放行 5,合计 **10 个在 <1 秒内通过**——瞬时是限额的 2 倍。

### 3.2 滑动窗口（ZSet 时间戳日志）
```lua
-- ZSet 存最近窗口内每个请求的时间戳;先删过期的,再数,再决定
local now=...毫秒...
redis.call('zremrangebyscore', k, 0, now-WINDOW_MS)   -- 丢掉窗口外的
if redis.call('zcard', k) < LIMIT then
  redis.call('zadd', k, now, 唯一member); redis.call('expire', k, 2); return 1
else return 0 end
```
- sc02 实测:固定窗口能放过的边界突刺,这里被挡住(前 5 个还在滑动窗内，后续全拒)。
- 代价:每个请求存一条 ZSet 记录(内存随 QPS×窗口增长);高 QPS 用「滑动窗口计数器」近似(分更细的小桶加权)折中。

### 3.3 令牌桶（Lua 原子 refill + consume）
- 状态:`tokens`(当前令牌数)、`last`(上次补充时间)。每次请求:按 `(now-last)*rate` 补令牌(不超 capacity),够 1 个就扣并放行。
- 整个「补 + 扣」必须原子 → Lua。允许突发(桶满放一批)+ 限均速。

### 3.4 为什么都用 Lua
三种算法的核心都是「**读状态 → 判断 → 改状态**」的原子操作;非原子会在并发下放过超额请求(同 08 章 sc02 超卖)。所以生产实现几乎都封装成一段 Lua。

## 4. 日常开发应用

- 要严格「每窗口不超 N」→ 滑动窗口(无突刺)。
- 能容忍突发、要限均速 → 令牌桶(对真实流量更友好)。
- 极简、能接受边界 2 倍 → 固定窗口(最省)。
- 别手撸:Java 用 Redisson `RRateLimiter`;或用成熟的限流中间件(网关层)。

## 5. 调优实战

- **限流「不准」、偶尔放过两倍** → 多半用了固定窗口踩了临界突刺,换滑动窗口/令牌桶。
- **限流器自己成了热 key** → 限流 key 集中(如全局一个),打散按用户/资源分 key;或本地+Redis 两级。
- **滑动窗口内存涨** → ZSet 存了太多时间戳,换滑动计数器近似。

## 6. 面试高频考点

- **固定窗口的缺陷?** 临界突刺(边界放过 2 倍,sc01 实测)。
- **滑动窗口怎么解决?** ZSet 存时间戳、只数最近窗口(sc02 实测堵住),代价是内存。
- **令牌桶 vs 漏桶?** 令牌桶允许突发(攒令牌)、漏桶严格匀速出;令牌桶更常用。
- **为什么限流要用 Lua?** 读-判断-改 要原子,否则并发放超额。
- **分布式限流怎么做?** 状态放 Redis(全局一致),Lua 原子;或 Redisson `RRateLimiter`。

## 7. 一句话总结

固定窗口最简但有**临界突刺(2 倍)**;滑动窗口(ZSet 时间戳)无突刺但费内存;令牌桶限均速且允许突发。三者核心都是「读-判断-改」的**原子操作 → 用 Lua**。

## 对照镜像（reference）

```java
// Java / Redisson —— RRateLimiter(底层就是 Redis + Lua)
RRateLimiter rl = redisson.getRateLimiter("api:user:123");
rl.trySetRate(RateType.OVERALL, 5, 1, RateIntervalUnit.SECONDS);  // 5 次/秒
if (rl.tryAcquire()) { /* 放行 */ } else { /* 限流 */ }
```

```python
# redis-py —— 固定窗口(用 Lua 保证原子)
LUA = "local k='rl:'..redis.call('TIME')[1] local c=redis.call('incr',k) redis.call('expire',k,2) return (c<=tonumber(ARGV[1])) and 1 or 0"
allowed = r.eval(LUA, 0, 5)   # limit=5/秒
```

## Scenarios

- [01 - 固定窗口的临界突刺（边界放过 2 倍）](scenarios/01-fixed-window-burst.md)
- [02 - 滑动窗口（ZSet）堵住突刺](scenarios/02-sliding-window-zset.md)
