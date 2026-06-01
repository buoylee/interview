# Scenario 04: Set intset / listpack / hashtable 三编码

> 版本注：`listpack` 作为 Set 的编码是 **Redis 7.2+** 引入。7.0/7.1 只有 intset→hashtable 两态。本 lab 用 7.4。

## 我想验证的问题

Set 全是整数时是什么编码？加一个非整数元素后变什么？超过 512 个整数呢？三条转换路径分别由哪个参数触发？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - 全整数且 ≤512 个 → 编码 _____。
> - 加入一个非整数（且元素少）→ 编码 _____。
> - 整数个数 > _____ → 直接 _____。
> - 非整数 Set 元素 > 128 或某元素 > 64 字节 → _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`；阈值 `set-max-intset-entries 512`、`set-max-listpack-entries 128`、`set-max-listpack-value 64`。
- `R` = `docker compose exec -T redis redis-cli`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R del st1; R sadd st1 1 2 3;            R object encoding st1   # intset?
R sadd st1 hello;                       R object encoding st1   # listpack?
R del st2; R sadd st2 $(seq 1 513);     R object encoding st2   # hashtable?
R del st3; for i in $(seq 1 129); do R sadd st3 m$i >/dev/null; done; R object encoding st3  # hashtable?
# 边界:512 整数 vs 513;少元素但有大 value
R del st4; R sadd st4 $(seq 1 512);     R object encoding st4   # 512: intset?
R del st5; R sadd st5 a "$(printf 'y%.0s' $(seq 1 65))"; R object encoding st5  # 2 元素含 65B
```

## 实机告诉我（2026-06-01，Redis 7.4.9 实跑）

```
st1 {1,2,3}                  -> intset
st1 + "hello"                -> listpack
st2 513 个整数               -> hashtable
st3 129 个非整数             -> hashtable
st4 512 个整数               -> intset      ← 512 仍 intset
st5 {a, 65字节串}(2 元素)     -> hashtable   ← value>64 直接 hashtable
```

观察到的关键事实：

- 三条路径：**全整数 ≤512 → intset**；**含非整数且小（≤128 个、每个 ≤64B）→ listpack**；**超任一阈值 → hashtable**。
- **512 整数仍 intset，513 直接 hashtable**——注意 513 并没有先变 listpack，因为 513 > `set-max-listpack-entries`(128)，所以跳过 listpack 直奔 hashtable。
- **value 长度独立触发**：st5 只有 2 个元素，但有一个 65 字节（>64），直接 hashtable。

## ⚠️ 预期 vs 实机落差

- 我以为：Set 就 intset 和 hashtable 两种；加非整数应该直接 hashtable。
- 实际：7.2+ 多了 **listpack** 作为「小且非全整数」的中间编码；非整数小集合先落 listpack，不是 hashtable；整数集超 512 会**跳过 listpack 直接 hashtable**（因为 513>128）。
- 我学到：(1) Set 编码是**三态**（intset / listpack / hashtable），版本相关——面试讲清「7.2 引入 listpack」是加分点。(2) intset 阈值 512 比 listpack 的 128 大，因为纯整数数组更紧凑、二分也快，可以多放。(3) 用 Set 存「标签/小集合」时，元素短（<64B）、数量压在 128 内能留在 listpack 省内存；一旦混入长字符串或元素暴涨就退化为 hashtable。