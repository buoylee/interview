# Scenario 01: maxmemory 撑满 —— noeviction 报 OOM vs allkeys-lru 淘汰

## 我想验证的问题

`maxmemory` 设小、把内存灌满后再写：`noeviction` 策略会怎样？切到 `allkeys-lru` 又会怎样？淘汰发生时内存和 key 数怎么变？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - `noeviction` 下内存满了再 `SET` → 返回 _____。
> - 切 `allkeys-lru` 后再 `SET` → 成功还是失败？_____ 会发生什么（dbsize/used_memory）？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`（已开 `enable-debug-command yes`，用 `DEBUG POPULATE` 快速灌 key）。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R config set maxmemory 8mb
# noeviction:DEBUG POPULATE 绕过 maxmemory 直接灌超量,再正常 SET
R config set maxmemory-policy noeviction
R debug populate 100000
echo "noeviction: dbsize=$(R dbsize) used=$(R info memory|grep -o 'used_memory_human:[^\r]*')"
echo "  再 SET: $(R set extra hello)"
# 切 allkeys-lru,同样的 SET
R config set maxmemory-policy allkeys-lru
echo "切 allkeys-lru 后 SET: $(R set extra hello)"
echo "  allkeys-lru: dbsize=$(R dbsize) used=$(R info memory|grep -o 'used_memory_human:[^\r]*') evicted=$(R info stats|grep -o 'evicted_keys:[0-9]*')"
R config set maxmemory 0; R config set maxmemory-policy noeviction; R flushall
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
noeviction: dbsize=100000 used=28.60M          ← DEBUG POPULATE 绕过限制灌到 28.6M(>8mb)
  再 SET extra: OOM command not allowed when used memory > 'maxmemory'.
切 allkeys-lru 后 SET extra: OK
  allkeys-lru: dbsize=22760 used=8.00M evicted_keys=77241   ← 淘汰 7.7 万 key,压回 8M,写成功
```

观察到的关键事实：

- `noeviction` + 内存超 `maxmemory` → 任何写命令直接 **`OOM command not allowed`**（读和删还能用）。
- 切 `allkeys-lru` 后同一条 `SET` 成功:Redis 为腾地方**淘汰了 77241 个 key**,`used_memory` 从 28.6M 压回 8.00M（= maxmemory）。
- (`DEBUG POPULATE` 是 debug 命令,绕过 maxmemory 检查,所以能先把内存灌超;正常 `SET` 才受策略约束。)

## ⚠️ 预期 vs 实机落差

- 我以为：内存满了 Redis 总会自己删点旧的腾地方。
- 实际:**默认策略 `noeviction` 根本不删,直接拒绝写入报 OOM**——这是线上最常见的「Redis 突然写不进去」事故根因。只有显式配 `allkeys-*`/`volatile-*` 才会淘汰。
- 我学到:(1) 生产**必须**配 `maxmemory` + 非 `noeviction` 策略,别裸奔。(2) 淘汰会让 `used_memory` 稳定在 `maxmemory`,代价是丢数据(纯缓存可接受)。(3) `volatile-*` 只淘汰带 TTL 的 key——若想保留某些 key 永不被淘汰,别给它设 TTL 且用 volatile 策略。

## 连到的面试卡

- `99-interview-cards/q-redis-expiry-eviction.md`
