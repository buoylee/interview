# Scenario 01: bitmap 签到 vs Set 内存对比

## 我想验证的问题

10 万用户某天签到，用 bitmap（`SETBIT sign:<日> <userid> 1`）记录 vs 用 Set 存签到用户 id，内存差多少？`BITCOUNT` 能不能直接统计签到人数？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - bitmap 记 10 万用户签到，内存大约 _____ KB。
> - Set 存 10 万用户 id，内存大约 _____ MB。
> - 倍数差大约 _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R eval "for i=1,100000 do redis.call('setbit','sign:0610',i,1) end return 1" 0
R eval "for i=1,100000 do redis.call('sadd','sign:set:0610',i) end return 1" 0
echo "bitmap: BITCOUNT=$(R bitcount sign:0610)  内存=$(R memory usage sign:0610)B"
echo "Set:    SCARD=$(R scard sign:set:0610)  内存=$(R memory usage sign:set:0610)B"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
bitmap: BITCOUNT=100000  内存=16440B   (~16KB)
Set:    SCARD=100000     内存=4772976B (~4.77MB)
→ bitmap 约为 Set 的 1/290
```

观察到的关键事实：

- bitmap 记 10 万用户签到只要 **~16KB**(每个用户 1 bit + 一点 string 开销),`BITCOUNT` 直接数出签到人数 100000。
- 同样的信息用 Set 存 10 万 id 要 **~4.77MB**(每个 id 是个对象 + dict 开销),是 bitmap 的 **~290 倍**。

## ⚠️ 预期 vs 实机落差

- 我以为：签到这种「用户ID集合」很自然就用 Set。
- 实际:当问题是「**某用户是否做过某事 / 一共多少人做了**」且用户能映射成连续整数 id 时,bitmap 用 **1 bit/用户** 碾压 Set——290 倍内存差。
- 我学到:(1) 签到、日活标记、在线状态、布隆(06 章)都该用 bitmap。(2) `BITCOUNT` 数总数、`BITOP AND/OR` 算「连续签到/活跃交并」。(3) **坑**:offset 是用户 id 时,id 稀疏(如雪花 id)会让 bitmap 按最大 offset 撑大——要先把 id 映射成连续序号。

## 连到的面试卡

- `99-interview-cards/q-redis-advanced-types.md`
