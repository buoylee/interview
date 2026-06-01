# Scenario 02: 滑动窗口（ZSet）堵住突刺

## 我想验证的问题

把限流换成滑动窗口（ZSet 存最近 1 秒内每个请求的时间戳，只数窗口内的）。sc01 里固定窗口能放过的「边界 2 倍突刺」，滑动窗口能不能堵住？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - 滑动窗口 limit=5/秒。先 burst 7 个放行 _____ 个；**0.45 秒后**再 burst 7 个放行 _____ 个（前 5 个还在 1 秒滑窗内）。
> - 再等 1.1 秒（滑窗清空）后 burst 7 个放行 _____ 个。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 滑动窗口 Lua:删 1s 外的 → 数 → <5 才加入并放行
SHA=$(R script load "local t=redis.call('TIME') local now=t[1]*1000+math.floor(t[2]/1000) local k='slw' redis.call('zremrangebyscore',k,0,now-1000) local c=redis.call('zcard',k) if c<5 then local s=redis.call('incr','slw:seq') redis.call('zadd',k,now,s) redis.call('expire',k,2) return 1 else return 0 end" | tr -d '\r')
burst(){ for i in $(seq 1 7); do echo "EVALSHA $SHA 0"; done | docker compose exec -T redis redis-cli | tr -d '\r' | paste -sd' ' -; }
echo "burst(7发): [$(burst)]"
sleep 0.45
echo "0.45s 后 burst(7发): [$(burst)]"
sleep 1.1
echo "再等 1.1s(滑窗清空)后 burst(7发): [$(burst)]"
R flushall
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
burst(7发):            [1 1 1 1 1 0 0]     ← 5 放行
0.45s 后 burst(7发):    [0 0 0 0 0 0 0]     ← 全拒!前 5 个还在 1 秒滑窗内
再等 1.1s 后 burst(7发): [1 1 1 1 1 0 0]     ← 滑窗清空,又放 5
```

观察到的关键事实：

- 第一批放行 5（达到 limit）。
- **0.45 秒后的第二批全部被拒**——因为滑动窗口看的是「最近 1000ms」，前 5 个请求（0.45 秒前）仍在窗口内，`zcard` 已是 5，不再放行。这正是 sc01 固定窗口会放过的那批，被滑动窗口挡住了。
- 等 1.1 秒（超过窗口长度），前 5 个滑出窗口、`zremrangebyscore` 清掉，又能放 5 个。

## ⚠️ 预期 vs 实机落差

- 我以为：滑动窗口和固定窗口差不多，就是换个实现。
- 实际:差别正是 sc01 的突刺——固定窗口边界放过 10 个/秒,滑动窗口**任意 1 秒严格 ≤5**(0.45s 后的 burst 全拒)。它不分死桶,而是每次都回看「此刻往前 1 秒」。
- 我学到:(1) 滑动窗口用 ZSet 存时间戳:`zremrangebyscore` 删窗外 + `zcard` 数窗内 + 不超就 `zadd`,整段用 Lua 原子。(2) 代价是**内存随 QPS×窗口增长**(每请求一条 ZSet 记录);超高 QPS 用「滑动窗口计数器」(细分小桶加权)近似折中。(3) member 要唯一(这里用 `INCR` 序号),否则同毫秒多请求会覆盖。

## 连到的面试卡

- `99-interview-cards/q-redis-rate-limiting.md`
