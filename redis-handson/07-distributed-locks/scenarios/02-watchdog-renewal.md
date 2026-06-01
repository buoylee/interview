# Scenario 02: 看门狗续期

## 我想验证的问题

锁设了 2 秒 ttl，但业务要跑更久。用一个「看门狗」后台定期 `PEXPIRE` 续期，锁能不能活过初始的 2 秒？看门狗一停，锁会不会自动过期释放？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - 锁初始 `PX 2000`，看门狗每 0.6s 续回 2000、续 3 次。2.2s 后锁还在吗？_____
> - 看门狗停止后再过 2.3s，锁还在吗？_____
> - 为什么有了看门狗还要保留 ttl（不直接设永不过期）？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R set lock:wd holder px 2000 >/dev/null
echo "初始 pttl=$(R pttl lock:wd)"
# 后台看门狗:每 0.6s 续回 2000,续 3 次(覆盖 ~1.8s)
( for n in 1 2 3; do sleep 0.6; docker compose exec -T redis redis-cli pexpire lock:wd 2000 >/dev/null; done ) &
sleep 2.2; echo "2.2s 后(无续期本应过期) exists=$(R exists lock:wd) pttl=$(R pttl lock:wd)"
wait
sleep 2.3; echo "停续期 2.3s 后 exists=$(R exists lock:wd)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
初始 pttl=1922
2.2s 后(无续期本应过期) exists=1  pttl=1732     ← 续期续命,活过了 2s
停续期 2.3s 后 exists=0                          ← 续期一停就过期释放
```

观察到的关键事实：

- 初始只设了 2000ms，但 2.2s 后锁**仍存在**（pttl 还有 1732ms）——看门狗每 0.6s 把 ttl 续回 2000，让锁随「持有者存活」续命。
- 看门狗一停，2.3s（> 2s ttl）后锁 `exists=0`，自动过期释放。

## ⚠️ 预期 vs 实机落差

- 我以为：设了 2s ttl，锁 2s 后必然消失。
- 实际：ttl 是「相对当下」的，只要在它到期前不断 `PEXPIRE` 续，锁可以无限续命；续一停就按最后一次 ttl 倒计时过期。
- 我学到：(1) 这就是 Redisson 看门狗的本质——后台线程每 `ttl/3` 续期，把锁绑定到「持有者是否还活着」而非固定时长。(2) **ttl 绝不能省**：它是「持有者连同看门狗一起崩溃」时的兜底，保证锁最终能被释放，不会死锁。(3) 续期间隔要 < ttl（这里 0.6 < 2），否则续期赶不上过期。

## 连到的面试卡

- `99-interview-cards/q-redis-distributed-lock-correctness.md`
