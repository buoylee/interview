# Scenario 02: zset listpack → skiplist + 内存对比

## 我想验证的问题

ZSet 在 `listpack` 与 `skiplist` 两种编码下，存同样数量元素的**内存差多少**？转换发生在第几个元素？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.2，不要查）：
>
> - 转 skiplist 的条件：元素数 > _____ 或 member 字节 > _____。
> - 我以为 200 个元素的 zset，skiplist 比 listpack 内存大约 多/少 _____ %（skiplist 有跳表指针 + dict 开销）。
>
> 填完单独 commit 一次（"prediction only"），再跑。

## 环境

- 起 lab：`make up`；阈值 `zset-max-listpack-entries 128`、`zset-max-listpack-value 64`。
- 下文 `R` = `docker compose exec -T redis redis-cli`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# 1) 127 元素:listpack,记内存
R del z; for i in $(seq 1 127); do R zadd z $i m$i >/dev/null; done
R object encoding z; R memory usage z
# 2) 加到 129:转 skiplist,记内存
R zadd z 128 m128 129 m129; R object encoding z; R memory usage z
# 3) 同样 200 元素,分别在两种编码下对比(临时调大阈值造 listpack 版)
R config set zset-max-listpack-entries 1000
R del zlp; for i in $(seq 1 200); do R zadd zlp $i m$i >/dev/null; done
R object encoding zlp; R memory usage zlp     # listpack 版 200 元素
R config set zset-max-listpack-entries 128
R del zsk; for i in $(seq 1 200); do R zadd zsk $i m$i >/dev/null; done
R object encoding zsk; R memory usage zsk     # skiplist 版 200 元素
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
step1: z(127)                          enc=listpack  mem=1072 B
step2: z(129)                          enc=skiplist  mem=14811 B
step3: zlp(200, threshold=1000)        enc=listpack  mem=1840 B
       zsk(200, threshold=128)         enc=skiplist  mem=17880 B
```

观察到的关键事实：

- 127 元素 listpack 1072B；只多加 2 个到 129，跨过阈值转 skiplist，内存**从 1072 暴涨到 14811（~14 倍）**——不是多存 2 个元素的开销，是整个结构换成了 skiplist+dict。
- 同样 200 元素：listpack 1840B vs skiplist 17880B，**skiplist 约 9.7 倍内存**。
- skiplist 的开销来自：每个节点的多层前进指针 + 一个额外 dict（member→score 映射）。

## ⚠️ 预期 vs 实机落差

- 我以为：skiplist 比 listpack 费内存，但可能就大个 2~3 倍。
- 实际：小数据量下 skiplist 是 listpack 的**near 10 倍**内存；且转换是「跨阈值瞬间整体换结构」，不是渐进增长。
- 我学到：(1) 大量「元素数很少」的 zset（例如每个用户一个几十元素的 zset）要尽量留在 listpack——元素数压在 128 内、member 短于 64B，能省近一个数量级内存。(2) skiplist 的内存换的是 `ZRANGEBYSCORE`/`ZRANK` 的 O(logN) 和 `ZSCORE` 的 O(1)；元素少时 listpack O(N) 扫也很快，所以小 zset 用 listpack 是「内存和速度双赢」。(3) 这解释了为什么阈值默认才 128——超过这个规模，O(N) 操作开始划不来，才值得花内存上 skiplist。