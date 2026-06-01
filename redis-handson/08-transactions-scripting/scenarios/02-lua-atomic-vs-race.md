# Scenario 02: Lua 原子扣库存 vs 非原子超卖

## 我想验证的问题

库存 5 件，20 个并发请求来抢。用「`GET` 看库存 → 若 >0 则 `DECR`」这种**非原子**两步操作，会不会超卖（卖出超过 5）？用 **Lua** 把「检查 + 扣减」做成一个原子脚本，能不能精确不超卖？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - 非原子 `GET`-then-`DECR`，20 抢 5，最终 stock = _____（会不会负）？
> - Lua 原子 check-and-decr，20 抢 5，最终 stock = _____。
> - 为什么 Lua 能防超卖？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# 非原子:GET 看库存,sleep 放大窗口,再 DECR
R set stock 5
for i in $(seq 1 20); do
  ( v=$(R get stock); if [ "$v" -gt 0 ] 2>/dev/null; then sleep 0.05; R decr stock >/dev/null; fi ) &
done; wait
echo "非原子最终 stock = $(R get stock)"
# Lua 原子:检查 + 扣减一个脚本
R set stock 5
LUA='local s=tonumber(redis.call("get",KEYS[1])) if s>0 then return redis.call("decr",KEYS[1]) else return -1 end'
for i in $(seq 1 20); do ( R eval "$LUA" 1 stock >/dev/null ) & done; wait
echo "Lua 原子最终 stock = $(R get stock)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
非原子最终 stock = -15      ← 超卖!20 个都看到 stock>0 后才各自 DECR
Lua 原子最终 stock = 0      ← 精确卖 5 件,不超卖
```

观察到的关键事实：

- **非原子超卖**:`GET` 和 `DECR` 是两步,20 个请求几乎都在「还没人 DECR」时 `GET` 到 stock>0,于是全部 `DECR` → stock 被扣到 **-15**（超卖 15 件）。
- **Lua 原子不超卖**:整个「检查 + 扣减」在一个脚本里原子执行（单线程串行，不被打断），第 6 个请求进来时 stock 已是 0、`s>0` 不成立、不扣 → 精确停在 **0**。

## ⚠️ 预期 vs 实机落差

- 我以为：`DECR` 本身是原子的，扣库存应该不会超卖。
- 实际:`DECR` 原子,但「**先 GET 判断、再 DECR**」是**两步**,两步之间会被其他请求插入——大家都在 0 之前读到了正数,于是一起扣穿。超卖的根因是「检查」和「修改」不原子。
- 我学到:(1) 防超卖的关键是把**检查-修改合并成一个原子操作**:Lua 脚本(本 scenario)、或 `DECR` 后判断负数再回补、或分布式锁(07 章)。(2) `MULTI` 做不到这个(它不能在执行中拿 GET 的结果分支),所以这类逻辑用 Lua。(3) 这也是缓存击穿互斥重建(06 章 sc02)、限流(13 章)都用 Lua 的原因——都是「读了再据此决定写」。

## 连到的面试卡

- `99-interview-cards/q-redis-transaction-vs-lua.md`
