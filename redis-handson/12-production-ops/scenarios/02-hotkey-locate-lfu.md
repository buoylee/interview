# Scenario 02: 热 key 定位（LFU / OBJECT FREQ / --hotkeys）

## 我想验证的问题

制造一个被频繁访问的热 key，能不能用 `--hotkeys` / `OBJECT FREQ` 把它找出来？`OBJECT FREQ` 返回的数字是真实访问次数吗？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.2，不要查）：
>
> - `--hotkeys` 需要 `maxmemory-policy` 是哪一类？_____
> - 对 `hot:A` 访问 5000 次后，`OBJECT FREQ hot:A` 大约返回 _____（真实次数 / 一个小很多的数）。
> - 热 key 的治理手段有哪些？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`
- `--hotkeys` 依赖 LFU 访问频率统计，需先切 `maxmemory-policy allkeys-lfu`。

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R config set maxmemory-policy allkeys-lfu
R set hot:A 1 >/dev/null; R set hot:B 1 >/dev/null
# 偏斜访问:hot:A 被访问 5000 次,hot:B 只 50 次
R eval "for i=1,5000 do redis.call('get','hot:A') end return 1" 0 >/dev/null
R eval "for i=1,50   do redis.call('get','hot:B') end return 1" 0 >/dev/null
echo "OBJECT FREQ  hot:A=$(R object freq hot:A)  hot:B=$(R object freq hot:B)"
R --hotkeys 2>/dev/null | grep -iE 'hot key found'
R config set maxmemory-policy noeviction
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
OBJECT FREQ  hot:A=38  hot:B=9
--hotkeys:
  hot key found with counter: 38   keyname: "hot:A"
  hot key found with counter: 9    keyname: "hot:B"
```

观察到的关键事实：

- 必须先切 `allkeys-lfu`（或 `volatile-lfu`）`--hotkeys` 才有数据——它读的是 LFU 计数器。
- `--hotkeys` 正确排出 hot:A（38）> hot:B（9）。
- **`OBJECT FREQ` 不是真实次数**：访问 5000 次，freq 只有 38——LFU 用**对数概率计数器**（Morris counter），访问越多增长越慢，且会随时间衰减。它反映「相对热度」而非精确计数。

## ⚠️ 预期 vs 实机落差

- 我以为：FREQ 就是访问计数，5000 次访问应该接近 5000。
- 实际：是**对数衰减计数**，5000 次只到 38；它的用途是「比较谁更热」，不是计数。
- 我学到：(1) 找热 key 先切 LFU 再 `--hotkeys`。(2) FREQ 是相对热度（对数+衰减），别当 QPS 用；要精确 QPS 得靠监控/采样。(3) 治理热 key:本地缓存挡一层、读副本分摊、`hot:A` 打散成 `hot:A:{0..N}` 分散到多 key/多分片（cluster 下尤其重要，避免单节点被打爆）。

## 连到的面试卡

- `99-interview-cards/q-redis-bigkey-hotkey.md`
