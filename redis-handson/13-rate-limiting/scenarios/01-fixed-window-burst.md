# Scenario 01: 固定窗口的临界突刺（边界放过 2 倍）

## 我想验证的问题

固定窗口限流（每秒最多 5 次，按整秒分桶 `INCR`）。如果在一个窗口的**末尾**发 5 个、紧接着跨进下一个窗口的**开头**再发 5 个，这 10 个会不会都被放行（即 <1 秒内通过了 2 倍限额）？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - limit=5/秒。窗口 N 末尾发 7 个，放行 _____ 个；跨入窗口 N+1 后再发 7 个，放行 _____ 个。
> - 这两批挨在一起（<1 秒），合计放行 _____ 个，是不是超了 5/秒？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。窗口取**服务端 `TIME` 的秒**（避免客户端时钟/exec 开销干扰）。
- 用 `SCRIPT LOAD` + 一次 pipe 发 7 个 `EVALSHA`，让一批 burst 紧凑（绕开每请求的 docker exec 开销）。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 固定窗口 Lua:key=rl:<服务端秒>, INCR, <=5 放行
SHA=$(R script load "local t=redis.call('TIME') local k='rl:'..t[1] local c=redis.call('incr',k) redis.call('expire',k,2) if c<=5 then return 1 else return 0 end" | tr -d '\r')
burst(){ for i in $(seq 1 7); do echo "EVALSHA $SHA 0"; done | docker compose exec -T redis redis-cli | tr -d '\r' | paste -sd' ' -; }
# 对齐到整秒前 ~0.2s
now=$(date +%s.%N); frac=0.${now#*.}; st=$(echo "1.0 - $frac - 0.2"|bc -l); awk "BEGIN{if($st>0)system(\"sleep \"$st)}"
echo "窗口N 末尾 burst(7发): [$(burst)]"
sleep 0.45      # 跨到下一秒
echo "窗口N+1 头部 burst(7发): [$(burst)]"
R flushall
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
窗口N   末尾 burst(7发): [1 1 1 1 1 0 0]     ← 5 放行 + 2 拒
窗口N+1 头部 burst(7发): [1 1 1 1 1 0 0]     ← 又 5 放行(新桶,计数清零)
→ 两批相隔 ~0.45s,合计放行 10 个 → <1 秒内通过了 limit 的 2 倍
```

观察到的关键事实：

- 每个固定窗口（整秒桶）独立计数到 5，所以窗口 N 末尾放 5、窗口 N+1 开头放 5。
- 这两批挨在一起只差 0.45 秒，**合计 10 个请求在 <1 秒内通过**——而限额是 5/秒。固定窗口在**桶边界**处放过了 2 倍流量。

## ⚠️ 预期 vs 实机落差

- 我以为：限了「5 次/秒」就不可能 1 秒内通过 10 个。
- 实际:固定窗口限的是「每个**整秒桶**最多 5」,不是「任意滑动 1 秒最多 5」。桶 N 的末尾和桶 N+1 的开头拼在一起,就有一个跨边界的 1 秒区间通过了 10 个——这就是**临界突刺**。
- 我学到:(1) 固定窗口最简单(一个 `INCR` 计数器),但最坏能放过 **2 倍**瞬时流量。(2) 攻击者只要卡着边界打,就能稳定突破一倍。(3) 要真正「任意 1 秒不超 N」,得用滑动窗口(sc02)或令牌桶。

## 连到的面试卡

- `99-interview-cards/q-redis-rate-limiting.md`
