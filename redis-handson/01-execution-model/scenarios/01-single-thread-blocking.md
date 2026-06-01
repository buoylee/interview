# Scenario 01: 单线程串行 —— 慢命令阻塞并发请求

## 我想验证的问题

Redis 命令执行是单线程的。如果一个客户端跑一条会阻塞 1 秒的命令（`DEBUG SLEEP 1`），另一个客户端在这期间发 `PING`，它要等多久才有响应？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §2/§3.1，不要查）：
>
> - A 在 t=0 发 `DEBUG SLEEP 1`，B 在 t=0.2s 发 `PING`。B 的 `PING` 大约 _____ 秒后才返回。
> - 为什么？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`（本 lab 已开 `enable-debug-command yes`）。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# A:后台跑阻塞 1s 的命令
( R debug sleep 1 >/dev/null ) &
sleep 0.2
# B:阻塞期间发 PING,计时
t0=$(date +%s.%N); R ping >/dev/null; t1=$(date +%s.%N)
echo "阻塞期间 PING 耗时 = $(echo "$t1 - $t0"|bc)s"
wait
# 对照:无阻塞时
t0=$(date +%s.%N); R ping >/dev/null; t1=$(date +%s.%N)
echo "正常 PING 耗时 = $(echo "$t1 - $t0"|bc)s"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
阻塞期间 PING 耗时 = 0.908s     ← 被 A 的 DEBUG SLEEP 堵住,等它跑完才轮到
正常 PING 耗时   = 0.101s       ← 正常 ~0.1s(主要是 docker exec 开销)
```

观察到的关键事实：

- A 的 `DEBUG SLEEP 1` 占住单线程整整 1 秒；B 的 `PING`（t=0.2s 发出）一直排队，直到 A 的 1 秒跑完才被处理 → 耗时 ~0.8s（0.9s 含 exec 开销）。
- 对照组正常 `PING` 只要 0.1s。

## ⚠️ 预期 vs 实机落差

- 我以为：`PING` 这么轻量，应该立刻返回，跟别的连接在干嘛无关。
- 实际：命令执行是**单线程串行**的，B 的 `PING` 必须排在 A 的慢命令后面——A 卡 1 秒，B 就等 1 秒。
- 我学到：(1) Redis 的「慢」往往不是这条命令本身慢，而是**它前面有人占着单线程**。(2) 这就是为什么线上一条 `KEYS *` / 大 key `HGETALL` / 重 Lua 能让**所有**请求延迟飙升,不只是它自己。(3) 排查「整体变慢」先用 `SLOWLOG` 找那个占线程的家伙（12 章）。

## 连到的面试卡

- `99-interview-cards/q-redis-single-thread.md`
