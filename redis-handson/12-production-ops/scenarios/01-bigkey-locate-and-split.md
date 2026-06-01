# Scenario 01: 大 key 定位（--bigkeys）与拆分省内存

## 我想验证的问题

一个 50000 字段的大 hash：`--bigkeys` 能不能定位到它？对它 `HGETALL` 全量读会不会卡（单线程阻塞）？把它拆成多个小分片后，内存和单次操作各变怎样？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1 + 02 章编码，不要查）：
>
> - 50000 字段的 hash 编码是 _____，`MEMORY USAGE` 大约 _____ MB。
> - 拆成 500 个「100 字段」的小分片后，每片编码是 _____；总内存比整块 多/少 _____。
> - `HGETALL` 全量读一个大 hash，会不会在 LATENCY 里留下记录？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- 用 `make load`（造了 `bighash` = 50000 字段）。

## 步骤

```bash
cd 00-lab && make up && make load N=100000
R(){ docker compose exec -T redis redis-cli "$@"; }
# 1) --bigkeys 定位
R --bigkeys 2>/dev/null | grep -E 'Biggest'
echo "bighash: 编码=$(R object encoding bighash) 内存=$(R memory usage bighash)B 字段=$(R hlen bighash)"
# 2) HGETALL 全量的阻塞(开 latency 监控)
R config set latency-monitor-threshold 1 >/dev/null; R latency reset >/dev/null
R hgetall bighash >/dev/null
echo "HGETALL 延迟事件: $(R latency latest)"
# 3) 拆成 500 个 100 字段分片,对比内存
R eval "for i=0,49999 do redis.call('hset','shard:'..math.floor(i/100),'f'..i,'v'..i) end return 'done'" 0 >/dev/null
echo "单片: 编码=$(R object encoding shard:0) 字段=$(R hlen shard:0)"
tot=$(R eval "local s=0 for _,k in ipairs(redis.call('keys','shard:*')) do s=s+redis.call('memory','usage',k) end return s" 0)
echo "整块 bighash=$(R memory usage bighash)B  vs  500 分片合计=${tot}B"
R config set latency-monitor-threshold 100 >/dev/null
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
--bigkeys: Biggest hash found "bighash" has 50000 fields
bighash: 编码=hashtable 内存=2786544B(2.78MB) 字段=50000
HGETALL 延迟事件: command <ts> 4 4          ← 全量读阻塞主线程 4ms
单片: 编码=listpack 字段=100
整块 bighash=2786544B  vs  500 分片合计=895584B(0.87MB)
```

观察到的关键事实：

- `--bigkeys` 一眼定位到 `bighash`（每类型最大）。
- `HGETALL` 全量读这个大 hash 是 O(N)，在 LATENCY 里留下 **4ms 的 `command` 事件**——这 4ms 里主线程不处理任何其他请求。
- 拆成 500 个 100 字段的分片后，每片落 **listpack**，总内存 **2.78MB → 0.87MB（约 1/3）**，且每次只 `HGET shard:x` 操作很小。

## ⚠️ 预期 vs 实机落差

- 我以为：拆分主要是为了避免阻塞，内存差不多甚至更多（多了 key 开销）。
- 实际：拆分后内存**反而降到 ~1/3**——因为每片 100 字段 < 128 阈值落进紧凑的 listpack，省掉了 hashtable 的 dictEntry + 指针开销（呼应 02 章）。同时单次操作从「全量 O(N)」变「小片 O(小)」。
- 我学到：(1) 大 key 的危害是**双重的**:阻塞单线程 + 浪费内存（被迫用 hashtable）。(2) 拆分到「每片落紧凑编码」是一石二鸟。(3) 删大 key 要用 `UNLINK`（异步）而非 `DEL`（同步阻塞）；读用 `HSCAN` 别 `HGETALL`。

## 连到的面试卡

- `99-interview-cards/q-redis-bigkey-hotkey.md`
