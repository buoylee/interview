# 用 Redis 做限流:固定窗口 / 滑动窗口 / 令牌桶怎么选？

## 一句话回答

**固定窗口**(`INCR` 整秒桶)最简但有**临界突刺**(边界放过 2 倍);**滑动窗口**(ZSet 存时间戳,只数最近窗口)无突刺但费内存;**令牌桶**限均速且允许突发。三者核心都是「读-判断-改」原子操作 → **用 Lua**。

## 三种算法对比

| | 实现 | 突刺 | 内存 | 突发 |
|---|---|---|---|---|
| 固定窗口 | `INCR rl:<秒>` + EXPIRE | **有(2倍)** | O(1) | 否 |
| 滑动窗口 | ZSet 时间戳 + zremrangebyscore + zcard | 无 | O(QPS×窗口) | 否 |
| 令牌桶 | tokens+last,按速率补、够则扣(Lua) | 无 | O(1) | **允许** |

## 实测证据

- 固定窗口 limit=5/秒:边界两侧各放 5,**0.45s 内通过 10 个**(2 倍突刺)。[sc01](../13-rate-limiting/scenarios/01-fixed-window-burst.md)
- 滑动窗口:0.45s 后的 burst **全拒**(前 5 个还在 1s 窗内),任意 1 秒严格 ≤5。[sc02](../13-rate-limiting/scenarios/02-sliding-window-zset.md)

## 易追问的延伸

- **固定窗口为什么突刺?** 限的是「每个整秒桶 ≤N」不是「任意滑动 1 秒 ≤N」,桶 N 尾 + 桶 N+1 头拼一起就 2N。
- **滑动窗口内存大怎么办?** 用「滑动窗口计数器」近似(细分小桶,按比例加权当前桶),省掉逐请求时间戳。
- **令牌桶 vs 漏桶?** 令牌桶攒令牌允许突发、漏桶严格匀速出;令牌桶更常用。
- **为什么必须 Lua?** 读状态-判断-改状态要原子,非原子并发下放超额(同 08 章超卖)。
- **分布式限流?** 状态放 Redis 全局一致 + Lua;Java 直接 Redisson `RRateLimiter`。

## 证据链接

- 章节原理:[13-rate-limiting](../13-rate-limiting/README.md)
- 实测:[sc01 固定窗口突刺](../13-rate-limiting/scenarios/01-fixed-window-burst.md)、[sc02 滑动窗口](../13-rate-limiting/scenarios/02-sliding-window-zset.md)
- 原子性根因:[08 章 sc02 Lua 防超卖](../08-transactions-scripting/scenarios/02-lua-atomic-vs-race.md)
