# Scenario 02: HyperLogLog UV 估算 —— 误差与内存

## 我想验证的问题

统计 100 万 UV（不同用户数），用 HyperLogLog（`PFADD`/`PFCOUNT`）vs 用 Set 精确去重，内存差多少？HLL 的计数误差有多大？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - HLL 存 100 万不同元素，`PFCOUNT` 与真值 1000000 的误差大约 _____ %。
> - HLL 的内存大约 _____ KB（跟元素数有关吗？）。
> - Set 精确存 100 万，内存大约 _____ MB。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R eval "for i=1,1000000 do redis.call('pfadd','uv',i) end return 1" 0
echo "HLL: PFCOUNT=$(R pfcount uv) (真值 1000000)  内存=$(R memory usage uv)B"
echo "Set: 内存=$(R eval "for i=1,1000000 do redis.call('sadd','uvset',i) end return redis.call('memory','usage','uvset')" 0)B"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
HLL: PFCOUNT=1009972 (真值 1000000)  内存=14384B  (~14KB)
Set:                                 内存=40388712B (~40MB)
→ HLL 误差 +0.997% (~1%);内存约为 Set 的 1/2800
```

观察到的关键事实：

- HLL 估算 100 万 UV 得 1009972，**误差约 +1%**（HLL 理论标准误差 ~0.81%）。
- HLL 内存只有 **~14KB**，且**不随元素数增长**（再加到一亿也还是这个量级）——因为它不存元素，只存概率估算的「桶」。
- Set 精确存 100 万要 **~40MB**，是 HLL 的 **~2800 倍**。

## ⚠️ 预期 vs 实机落差

- 我以为：要统计「有多少不同的人」总得把人存下来，内存随量增长。
- 实际:HLL **根本不存元素**,用固定 ~12KB 的概率结构估个数,误差 ~1%,内存与元素数**无关**——百万 UV 也才 14KB。
- 我学到:(1) UV / 海量去重计数,**能容忍 ~1% 误差且不需要取出具体元素**时用 HLL,省 ~2800 倍。(2) HLL **取不出元素**、也不能精确——要明细或精确就得 Set/外部存储。(3) `PFMERGE` 可合并多个 HLL(如按天 HLL 合并算周 UV),这是 HLL 的另一大用处。

## 连到的面试卡

- `99-interview-cards/q-redis-advanced-types.md`
