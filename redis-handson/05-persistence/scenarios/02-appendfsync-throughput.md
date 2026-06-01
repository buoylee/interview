# Scenario 02: appendfsync always vs everysec 吞吐对比

## 我想验证的问题

AOF 的 `appendfsync` 三档（`always` / `everysec` / 关 AOF）对写吞吐影响多大？「每条命令都 fsync」到底慢多少？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - `appendfsync everysec` 的 SET 吞吐大约 _____ rps。
> - `appendfsync always`（每条都刷盘）大约 _____ rps，比 everysec 慢 _____ 倍。
> - 关掉 AOF（纯内存）大约 _____ rps。
>
> 填完单独 commit 一次。

## 环境

- 用独立临时容器跑 `redis-benchmark`（不污染 lab）。

## 步骤

```bash
cleanup(){ docker rm -f rbench >/dev/null 2>&1; }
# everysec
cleanup; docker run -d --name rbench redis:7.4 redis-server --appendonly yes --appendfsync everysec --save ''; sleep 1
docker exec rbench redis-benchmark -t set -n 100000 -q | tail -1
# always
cleanup; docker run -d --name rbench redis:7.4 redis-server --appendonly yes --appendfsync always --save ''; sleep 1
docker exec rbench redis-benchmark -t set -n 100000 -q | tail -1
# 关 AOF
cleanup; docker run -d --name rbench redis:7.4 redis-server --appendonly no --save ''; sleep 1
docker exec rbench redis-benchmark -t set -n 100000 -q | tail -1
cleanup
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑，单机本地）

```
appendfsync everysec : SET 289017 rps  (p50=0.103ms)
appendfsync always   : SET  35323 rps  (p50=1.159ms)   ← 慢约 8 倍
appendonly no        : SET 313479 rps  (p50=0.095ms)
```

观察到的关键事实：

- `always`（每条命令都 fsync 落盘）只有 **35k rps**，比 `everysec` 的 289k **慢约 8 倍**，p50 延迟从 0.1ms 升到 1.16ms。
- `everysec`（289k）非常接近**完全关 AOF**（313k）——每秒刷一次盘的代价很小。
- 瓶颈在 **fsync（磁盘）**:`always` 把磁盘 fsync 拉进了每条写的关键路径。

## ⚠️ 预期 vs 实机落差

- 我以为：开 AOF 会明显拖慢,everysec 也会慢不少。
- 实际:**`everysec` 几乎不损吞吐**(289k vs 关 AOF 313k);真正昂贵的是 **`always`(慢 8 倍)**——因为它每条命令都等磁盘 fsync。
- 我学到:(1) `everysec` 是耐久性与吞吐的甜点(默认就是它),最多丢 1s 数据换近乎无损的吞吐。(2) `always` 只在「一条都不能丢」且能吃下 8 倍吞吐损失时才用,极少见。(3) 性能瓶颈是 fsync(磁盘),不是写 AOF buffer 本身。

## 连到的面试卡

- `99-interview-cards/q-redis-persistence.md`
