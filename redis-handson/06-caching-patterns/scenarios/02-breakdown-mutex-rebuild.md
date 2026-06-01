# Scenario 02: 击穿 —— SET NX 互斥重建 vs 无锁惊群

## 我想验证的问题

一个热点 key 失效的瞬间，10 个并发请求同时 miss。**无锁**时有几个会回源重建 DB？加 **`SET NX` 互斥锁**后又有几个？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - 无锁：我以为 10 个并发里 _____ 个会回源重建。
> - 加 `SET NX` 互斥：我以为 _____ 个回源，其余 _____。
> - 互斥锁为什么要带 `EX` 过期？_____
>
> 填完单独 commit 一次，再跑。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- 用 `rebuild:cnt` 计数器度量「回源重建发生了几次」。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# A) 无锁:10 并发,miss 就重建(模拟慢重建 sleep 1)
R flushall; R set rebuild:cnt 0; R del cache:hot
NOLOCK='if redis.call("exists","cache:hot")==1 then return "hit" end redis.call("incr","rebuild:cnt") return "rebuild"'
for i in $(seq 1 10); do ( R eval "$NOLOCK" 0 >/dev/null; sleep 1; R set cache:hot V >/dev/null ) & done; wait
echo "无锁 重建次数 = $(R get rebuild:cnt)"
# B) 互斥:SET NX 抢锁,抢到才重建
R set rebuild:cnt 0; R del cache:hot lock:hot
MUTEX='if redis.call("exists","cache:hot")==1 then return "hit" end if redis.call("set","lock:hot","1","nx","ex","5") then redis.call("incr","rebuild:cnt") return "rebuild" else return "wait" end'
for i in $(seq 1 10); do ( R eval "$MUTEX" 0 >/dev/null ) & done; wait
echo "互斥 重建次数 = $(R get rebuild:cnt)"
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
无锁 重建次数 = 10
互斥 重建次数 = 1
```

观察到的关键事实：

- **无锁 = 10**：失效瞬间每个并发都 miss、都回源——这就是「惊群」，10 倍 DB 压力。
- **互斥 = 1**：`SET NX` 让第一个请求抢到 `lock:hot` 去重建，其余 9 个拿不到锁直接返回「wait」（生产里应短暂自旋后读缓存）。回源被压成 1 次。

## ⚠️ 预期 vs 实机落差

- 我以为：无锁也许只有几个重建（以为某个先写完缓存挡住后面）。
- 实际：在失效窗口内 10 个**全部**回源（缓存还没被任何一个写回前，大家都 miss）；互斥把它精确压到 1。
- 我学到：(1) 击穿的本质是「失效瞬间的并发回源」，不是慢慢来的。(2) `SET NX EX` 的 `EX` 必须有——否则抢到锁的请求若重建中崩溃，锁永不释放，所有人卡死（这正是 07 章分布式锁要解决的：续期/防误删）。(3) 互斥的代价是其余请求要等待；不想等就用「逻辑过期」（旧值先返回、后台异步重建）。

## 连到的面试卡

- `99-interview-cards/q-cache-penetration-breakdown-avalanche.md`
