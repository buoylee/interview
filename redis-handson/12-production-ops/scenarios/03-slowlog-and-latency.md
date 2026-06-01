# Scenario 03: SLOWLOG 抓慢命令 + LATENCY 延迟归因

## 我想验证的问题

`KEYS *` 在 10 万 key 上有多慢、能不能被 `SLOWLOG` 抓到？`LATENCY` 监控能抓到哪些延迟事件——`DEBUG SLEEP` 这种合成阻塞算不算？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3/§3.4，不要查）：
>
> - `KEYS *`（10 万 key）大约耗时 _____ 微秒，会不会进 SLOWLOG？_____
> - `DEBUG SLEEP 0.2`（阻塞 200ms）会不会被 `LATENCY` 记录？_____
> - 真实重命令（如全量 `LRANGE`）会不会被 `LATENCY` 记录？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up` + `make load N=100000`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up && make load N=100000
R(){ docker compose exec -T redis redis-cli "$@"; }
# 1) SLOWLOG 抓 KEYS *
R config set slowlog-log-slower-than 1000 >/dev/null   # 临时降到 1ms 确保抓到
R slowlog reset >/dev/null
R keys '*' >/dev/null
echo "slowlog 条数=$(R slowlog len)"; R slowlog get 1
R config set slowlog-log-slower-than 10000 >/dev/null
# 2) LATENCY:DEBUG SLEEP vs 真实重命令
R config set latency-monitor-threshold 1 >/dev/null
R latency reset >/dev/null; R debug sleep 0.2 >/dev/null
echo "DEBUG SLEEP 0.2 后 latest=[$(R latency latest)]"
R del biglist >/dev/null; R eval "for i=1,100000 do redis.call('rpush','biglist',i) end return 1" 0 >/dev/null
R latency reset >/dev/null; R lrange biglist 0 -1 >/dev/null
echo "全量 LRANGE 后 latest=[$(R latency latest)]"
R latency doctor
R config set latency-monitor-threshold 100 >/dev/null
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
slowlog 条数=1
SLOWLOG GET 1: id=1, 耗时=4537 微秒, 命令="keys *", client=...
DEBUG SLEEP 0.2 后 latest=[]                        ← 没被记录!
全量 LRANGE 后 latest=[command <ts> 3 3]             ← 真实重命令被记录(3ms)
LATENCY DOCTOR(无事件时):"...no latency spike observed..."
```

观察到的关键事实：

- `KEYS *` 扫 10 万 key 耗 **4537µs（4.5ms）**，被 SLOWLOG 抓到（命令、耗时、客户端都有）。
- **`DEBUG SLEEP 0.2`（阻塞 200ms）没有进 LATENCY**——合成阻塞不计入命令延迟采样。
- **真实重命令**（全量 `LRANGE` 10 万元素）被记为 `command` 事件（3ms）。

## ⚠️ 预期 vs 实机落差

- 我以为：要测延迟监控，`DEBUG SLEEP` 制造一个大延迟就能看到。
- 实际:**`DEBUG SLEEP` 不被 LATENCY 监控记录**(它不是真实命令执行耗时);得用真实的重命令(或真实的 fork/AOF 事件)才会出现在 `LATENCY LATEST`。阈值也要够低(默认 100ms 抓不到几 ms 的命令)。
- 我学到:(1) `SLOWLOG` 按命令耗时记录,排查「哪条命令慢」首选;线上 `KEYS *` 必现身,所以要用 `SCAN`。(2) `LATENCY` 按事件类型(command/fork/aof 等)记录,排查「延迟从哪来」;但**别用 DEBUG SLEEP 自测**(它不计入)。(3) 真实延迟毛刺多来自 fork(bgsave/AOF rewrite)、AOF fsync、swap——这些会以对应事件名出现在 `LATENCY HISTORY`。

## 连到的面试卡

- `99-interview-cards/q-redis-latency-troubleshooting.md`
