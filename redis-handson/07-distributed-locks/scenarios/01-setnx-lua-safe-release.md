# Scenario 01: SET NX PX + Lua CAS 安全释放（误删复现）

## 我想验证的问题

`SET key token NX PX ttl` 能不能保证互斥？如果解锁时**不校验归属**直接 `DEL`，会不会把别人的锁删掉？Lua CAS（比对 token 再删）能不能堵住？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.2，不要查）：
>
> - A 已持锁，B 用 `SET ... NX` 抢同一把 → 返回 _____。
> - B 直接 `DEL lock`（不看 token）→ 会不会删掉 A 的锁？_____
> - 用错 token 跑 Lua CAS 释放 → 返回 _____；用对 token → 返回 _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
echo "A 抢锁:        $(R set lock:x tokenA nx px 10000)"
echo "B 抢同一把:    $(R set lock:x tokenB nx px 10000)"
echo "B 无脑 DEL:    $(R del lock:x)"
# Lua CAS:只有 token 匹配才删
R set lock:y tokenA nx px 10000 >/dev/null
CAS='if redis.call("get",KEYS[1])==ARGV[1] then return redis.call("del",KEYS[1]) else return 0 end'
echo "错 token CAS:  $(R eval "$CAS" 1 lock:y tokenB)"
echo "对 token CAS:  $(R eval "$CAS" 1 lock:y tokenA)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
A 抢锁:        OK
B 抢同一把:              ← 空(nil),互斥成功
B 无脑 DEL:    1         ← 删掉了 A 的锁!危险
错 token CAS:  0         ← token 不匹配,不删
对 token CAS:  1         ← token 匹配,删掉
```

观察到的关键事实：

- `SET NX` 互斥有效：A 拿到后 B 抢同一 key 返回 nil。
- **无脑 `DEL` 会删掉别人的锁**：B 对 `lock:x` 执行 `DEL` 返回 1（删成功）——如果这把锁此刻已经是「A 过期后 B 新拿到的」，B 的解锁就误删了别人正在用的锁。
- Lua CAS 把误删堵死：错 token 返回 0（不动），对 token 返回 1（删）。

## ⚠️ 预期 vs 实机落差

- 我以为：解锁就是 `DEL lock`，谁删都一样。
- 实际：`DEL` 不认归属——会删掉「自己锁过期后、别人新拿到的」那把锁；必须「GET 比对 token == 自己 → 再 DEL」，且这两步要 **Lua 原子**（否则判断完、删之前锁过期被抢走，仍会误删）。
- 我学到：(1) 加锁用 `SET key <唯一token> NX PX <ttl>` 一条命令（NX 互斥 + PX 防死锁 + token 标识归属）。(2) 解锁用 Lua CAS，绝不裸 `DEL`。(3) Redisson 的 `unlock()` 内部就是这段 Lua（外加可重入计数）。

## 连到的面试卡

- `99-interview-cards/q-redis-distributed-lock-correctness.md`
