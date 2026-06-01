# Scenario 03: SLOWLOG 抓慢命令 + LATENCY 延迟归因

## 我想验证的问题

`KEYS *` 在 10 万 key 上有多慢、能不能被 `SLOWLOG` 抓到？`LATENCY` 监控能抓到哪些事件、阈值怎么影响结果？`DEBUG SLEEP` 这种命令能不能直接用来测延迟监控？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3/§3.4，不要查）：
>
> - `KEYS *`（10 万 key）大约耗时 _____ 微秒，会不会进 SLOWLOG？_____
> - `latency-monitor-threshold` 默认 100ms 时，一个 ~4.5ms 的 `KEYS *` 会被 `LATENCY` 记录吗？_____
> - `DEBUG SLEEP` 在生产实例上能直接跑吗？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up` + `make load N=100000`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- 本 lab 已在 `redis.conf` 开 `enable-debug-command yes`（默认 Redis 是 `no`，DEBUG 被禁）。

## 步骤

```bash
cd 00-lab && make up && make load N=100000
R(){ docker compose exec -T redis redis-cli "$@"; }
# 1) SLOWLOG 抓 KEYS *(阈值临时降到 1ms)
R config set slowlog-log-slower-than 1000 >/dev/null; R slowlog reset >/dev/null
R keys '*' >/dev/null
echo "slowlog len=$(R slowlog len)"; R slowlog get 1
R config set slowlog-log-slower-than 10000 >/dev/null
# 2) LATENCY:阈值降到 50ms,DEBUG SLEEP 0.2(200ms)被记为 command 事件
R config set latency-monitor-threshold 50 >/dev/null; R latency reset >/dev/null
R debug sleep 0.2 >/dev/null
echo "DEBUG SLEEP 0.2 → latest=[$(R latency latest)]"
# 3) 默认阈值 100ms 会漏掉几 ms 的命令
R config set latency-monitor-threshold 100 >/dev/null; R latency reset >/dev/null
R keys '*' >/dev/null
echo "阈值100ms下 KEYS*(~4.5ms) → latest=[$(R latency latest)]"
R latency doctor
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
slowlog len=1
SLOWLOG GET 1: id, 耗时=4702 微秒, 命令="keys *", client=...
DEBUG SLEEP 0.2 → latest=[command <ts> 200 200]     ← 被记为 command 事件(200ms)
阈值100ms下 KEYS*(~4.5ms) → latest=[]                ← 4.5ms < 100ms,被阈值滤掉
LATENCY DOCTOR(无事件时):"...no latency spike observed..."
```

观察到的关键事实：

- `KEYS *` 扫 10 万 key 耗 **4702µs（~4.7ms）**，被 SLOWLOG 抓到（命令、耗时、客户端齐全）。
- `LATENCY` 把超过 `latency-monitor-threshold` 的命令执行记为 **`command` 事件**：阈值 50ms 时 `DEBUG SLEEP 0.2` 留下 200ms 记录。
- **默认阈值 100ms 会漏掉几 ms 的命令**：同样的 `KEYS *`（4.5ms）在 100ms 阈值下 `latest` 为空——排查时必须把阈值调低。

## ⚠️ 预期 vs 实机落差

- 我以为：随便 `DEBUG SLEEP` 一下就能在 LATENCY 里看到延迟;默认配置就能抓命令延迟。
- 实际:踩了两个真实的坑——(1) **`DEBUG` 命令默认被禁**(`enable-debug-command no`),直接跑会报 `ERR DEBUG command not allowed`(本 lab 特意开了才跑得动;如果把输出 `>/dev/null` 还会把这个错误吞掉、误以为"跑了没记录")。(2) **`latency-monitor-threshold` 默认 100ms 太高**,几 ms 的慢命令根本不进 LATENCY;要排查得先调低阈值。开启 DEBUG、调低阈值后,`DEBUG SLEEP` 和真实重命令都会被记为 `command` 事件。
- 我学到:(1) `SLOWLOG`(按命令耗时,微秒阈值)排查「哪条命令慢」最直接;`KEYS *` 必现身 → 线上用 `SCAN`。(2) `LATENCY` 排查「延迟从哪来」,但**默认阈值偏高**,要调低才看得到;生产真实毛刺多来自 fork(bgsave/AOF rewrite)、AOF fsync、swap,会以对应事件名出现在 `LATENCY HISTORY`。(3) `DEBUG` 在生产默认不可用,别指望用它现场测。

## 连到的面试卡

- `99-interview-cards/q-redis-latency-troubleshooting.md`
