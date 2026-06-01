# Scenario 01: 穿透 —— bitmap 布隆挡不存在 key

## 我想验证的问题

用 bitmap 自实现一个布隆过滤器（k=2 个 hash），验证两件事：(a) **存在的 key 一定放行**（零假阴性）；(b) 把 bitmap 灌满后，**不存在的 key 会不会被误判为「可能存在」**（假阳性），比例多大？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3 / §6，不要查）：
>
> - 布隆「说不存在」时，结果可不可信？「说存在」呢？
> - 我以为假阴性（存在却说不存在）会有 _____ 个。
> - 我以为往 1024 位的小 bitmap 灌 300 个 id 后，查 300 个不存在的 id，假阳性大约 _____ 个。
>
> 填完单独 commit 一次，再跑。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# A) 直觉:8192 位 bitmap,注册 1001,1002,挡 9999
R eval "for i,v in ipairs(ARGV) do local h1=redis.sha1hex(v) local a=tonumber(string.sub(h1,1,8),16)%8192 local b=tonumber(string.sub(h1,9,16),16)%8192 redis.call('setbit','bf',a,1) redis.call('setbit','bf',b,1) end return 'ok'" 0 1001 1002
CHECK='local h1=redis.sha1hex(ARGV[1]) local a=tonumber(string.sub(h1,1,8),16)%8192 local b=tonumber(string.sub(h1,9,16),16)%8192 if redis.call("getbit","bf",a)==1 and redis.call("getbit","bf",b)==1 then return 1 else return 0 end'
echo "1001->$(R eval "$CHECK" 0 1001)  1002->$(R eval "$CHECK" 0 1002)  9999->$(R eval "$CHECK" 0 9999)"
# B) 假阳性演示:小 bitmap(1024 位)灌 300 个 id,逼出假阳性
R del bf2
R eval "for i=1,300 do local h1=redis.sha1hex(tostring(i)) local a=tonumber(string.sub(h1,1,8),16)%1024 local b=tonumber(string.sub(h1,9,16),16)%1024 redis.call('setbit','bf2',a,1) redis.call('setbit','bf2',b,1) end return 'ok'" 0
CHECK2='local h1=redis.sha1hex(ARGV[1]) local a=tonumber(string.sub(h1,1,8),16)%1024 local b=tonumber(string.sub(h1,9,16),16)%1024 if redis.call("getbit","bf2",a)==1 and redis.call("getbit","bf2",b)==1 then return 1 else return 0 end'
fn=0; for i in $(seq 1 300); do [ "$(R eval "$CHECK2" 0 $i)" = "0" ] && fn=$((fn+1)); done; echo "假阴性(必须=0): $fn"
fp=0; for i in $(seq 10001 10300); do [ "$(R eval "$CHECK2" 0 $i)" = "1" ] && fp=$((fp+1)); done; echo "假阳性: $fp / 300  (bitcount=$(R bitcount bf2)/1024)"
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
1001->1   1002->1   9999->0          ← 注册的放行,没注册的被挡
假阴性(必须=0): 0
假阳性: 71 / 300   (bitcount=466/1024)
```

观察到的关键事实：

- **零假阴性**：注册过的 1..300 全部返回 1，没有一个被误判为「不存在」——这是布隆能安全挡穿透的根本（绝不会把真实 key 拦在门外）。
- **有假阳性**：1024 位灌了 466 位（45%）后，查 300 个不存在的 id 有 71 个（~24%）被误判「可能存在」而放行。
- 假阳性的 key 会漏到 DB，但**只是少挡了一点，不会错杀**。

## ⚠️ 预期 vs 实机落差

- 我以为：布隆要么准要么不准，假阳性可能很少。
- 实际：方向是**不对称**的——「说不存在」100% 可信（零假阴性），「说存在」可能假阳性；假阳性率随 bitmap 装填率飙升（45% 装填 → 24% 假阳性）。
- 我学到：(1) 布隆挡穿透安全的前提就是「零假阴性」——绝不漏真实 key。(2) 假阳性率由 bitmap 大小和元素数决定，**容量必须按预估元素数留够**（Redisson `tryInit(预估量, 误判率)` 就是替你算位数和 hash 个数）。(3) 删除是布隆的软肋（删元素会影响别的 key 的位），要删用 Counting Bloom 或布谷鸟过滤器（见旧笔记 `redis/缓存穿透.md`）。

## 连到的面试卡

- `99-interview-cards/q-cache-penetration-breakdown-avalanche.md`
