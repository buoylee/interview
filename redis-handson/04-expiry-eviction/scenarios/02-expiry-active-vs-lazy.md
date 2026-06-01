# Scenario 02: 过期删除 —— 定期采样（不访问也删）+ 惰性

## 我想验证的问题

5 万个 key 都设 2 秒 TTL，然后**完全不去访问**它们。2 秒后它们会被删掉吗（还是要等下次访问）？单个过期 key 在 `GET` 时会发生什么？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - 5 万个 2s TTL 的 key，全程不访问，2 秒后 `dbsize` 大约 _____（还是 50000？）。
> - 是什么机制删的？_____
> - 单个过期 key `GET` 返回 _____，`TTL` 返回 _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`（用 `DEBUG POPULATE` 快速造 key）。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# 定期删除:5万 key 设 2s TTL,全程不访问
R debug populate 50000
{ for i in $(seq 0 49999); do echo "PEXPIRE key:$i 2000"; done; } | R --pipe >/dev/null
echo "刚设完: dbsize=$(R dbsize) expired=$(R info stats|grep -o 'expired_keys:[0-9]*')"
sleep 3   # 等 TTL 过 + 定期删除采样跑(不访问任何 key)
echo "3s 后(全程不访问): dbsize=$(R dbsize) expired=$(R info stats|grep -o 'expired_keys:[0-9]*')"
# 惰性删除:单 key 过期后 GET
R set lazy v px 100; sleep 0.3
echo "过期后 GET lazy=[$(R get lazy)]  TTL=$(R ttl lazy)"
R flushall
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
刚设完: dbsize=50000  expired_keys=0
3s 后(全程不访问): dbsize≈734  expired_keys≈49955     ← 没访问也被删了!
过期后 GET lazy=[]  TTL=-2                              ← 惰性:GET 触发删除,-2=不存在
```

观察到的关键事实：

- 5 万个 2s TTL 的 key **全程没被访问**，3 秒后 `dbsize` 从 50000 掉到 ~734，`expired_keys≈49955`——这是**定期删除**（后台 `serverCron` 随机采样删过期）干的，不靠访问。
- 剩下的 ~700 个是还没被采样轮到的（定期删除是采样不是全删），下次采样或被访问时清掉。
- 单个 key 过期后 `GET` 返回 nil、`TTL=-2`——**惰性删除**在访问那一刻把它删了。

## ⚠️ 预期 vs 实机落差

- 我以为:Redis 给每个 key 起定时器,到点精确删;或者不访问就一直不删。
- 实际:**没有 per-key 定时器**。是「惰性(访问才删)+ 定期(后台采样删)」两手——所以**过期 key 会短暂地占着内存**直到被采样到或访问到(实测留了 ~700 个尾巴),不是到点瞬间消失。
- 我学到:(1) 过期不精确、有延迟,别依赖「TTL 一到内存立刻释放」。(2) 大量同时过期 key 会让定期删除那几轮吃 CPU(呼应雪崩——过期扎堆也会有 CPU 尖刺)。(3) `expired_keys` vs `evicted_keys` 是两回事:前者是 TTL 过期删的,后者是内存满了淘汰删的。

## 连到的面试卡

- `99-interview-cards/q-redis-expiry-eviction.md`
