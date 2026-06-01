# Scenario 03: 雪崩 —— TTL 同时过期 vs 随机抖动

## 我想验证的问题

1000 个 key，一种全设 `EX 100`，另一种设 `EX 100 + rand(0,100)`。100 秒后，落在「同一秒过期」的 key 有多少？两种方式的到期时间分散程度差多少？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3 / §6，不要查）：
>
> - 固定 TTL：1000 个 key 的「到期秒」去重后大约有 _____ 个不同的秒值。
> - 抖动 TTL（+0~100 随机）：去重后大约 _____ 个秒值。
> - 哪种会让 DB 在某一秒被打满？
>
> 填完单独 commit 一次，再跑。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- 用 `EXPIRETIME`（key 的绝对到期 Unix 秒）统计「到期秒」的去重数：越小=越扎堆，越大=越分散。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 固定 TTL:1000 key 全 EX 100
{ for i in $(seq 1 1000); do echo "SET fixed:$i v EX 100"; done; } | R --pipe
# 抖动 TTL:EX 100 + 0..100 随机
{ for i in $(seq 1 1000); do echo "SET jit:$i v EX $((100 + RANDOM % 100))"; done; } | R --pipe
# 单个 Lua 统计「到期秒」去重数(别循环 1000 次 docker exec,会很慢)
DISTINCT='local s={} for i=1,1000 do local t=redis.call("expiretime",KEYS[1]..i) if t>0 then s[t]=1 end end local c=0 for _ in pairs(s) do c=c+1 end return c'
echo "固定TTL 到期秒去重数(越小=越扎堆): $(R eval "$DISTINCT" 1 fixed:)"
echo "抖动TTL 到期秒去重数(越大=越分散): $(R eval "$DISTINCT" 1 jit:)"
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
固定TTL 到期秒去重数(越小=越扎堆): 1
抖动TTL 到期秒去重数(越大=越分散): 100
```

观察到的关键事实：

- **固定 TTL = 1 个到期秒**：1000 个 key 全挤在同一秒过期——那一秒它们同时 miss，1000 个回源请求一起砸 DB，这就是雪崩。
- **抖动 TTL = 100 个到期秒**：均匀摊到 100 个秒上，平均每秒只有 ~10 个 key 过期，DB 压力降为 1/100。

## ⚠️ 预期 vs 实机落差

- 我以为：固定 TTL 也会因为 SET 的细微时间差散开一点。
- 实际：`EX 100` 是「相对当前」的整秒，批量 SET 在同一秒内完成 → 到期时间**完全相同（去重后只剩 1 个秒值）**，一点不散。
- 我学到：(1) 雪崩不需要「同时 SET」很精确，只要 TTL 一样、设置时间接近，就会齐刷刷过期。(2) **加随机抖动是最便宜的防护**——一行 `base + rand` 就把尖峰摊平 100 倍。(3) 抖动范围要和「能接受的缓存新鲜度」权衡：抖太大数据可能偏旧，抖太小摊不开。

## 连到的面试卡

- `99-interview-cards/q-cache-penetration-breakdown-avalanche.md`
