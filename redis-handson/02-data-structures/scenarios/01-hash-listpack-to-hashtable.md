# Scenario 01: hash listpack → hashtable 转换阈值

## 我想验证的问题

一个 hash，字段数从 128 涨到 129 时，`OBJECT ENCODING` 会不会从 `listpack` 变 `hashtable`？如果字段数不到 128 但某个 value 超过 64 字节呢？转成 hashtable 后再删回很小，会变回 listpack 吗？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1，不要查）：
>
> - 触发转 hashtable 的两个条件：字段数 > _____ **或** 单个 value 字节 > _____。
> - 我以为加到第 _____ 个字段时编码翻转。
> - 我以为删回 1 个字段后编码会 / 不会 退回 listpack（选一个），因为 _____。
>
> 填完单独 commit 一次（"prediction only"），再跑下面步骤。

## 环境

- compose: `00-lab/docker-compose.yml`
- 起 lab：`make up`
- 默认阈值：`hash-max-listpack-entries 128`、`hash-max-listpack-value 64`
- 下文 `R` = `docker compose exec -T redis redis-cli`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
# 1) 128 个字段:看是否还在 listpack
R del h; for i in $(seq 1 128); do R hset h f$i v$i >/dev/null; done; R object encoding h
# 2) 加第 129 个:看是否翻转
R hset h f129 v129; R object encoding h
# 3) value 长度触发:新 hash,只 1 个字段但 value 65 字节
R del h2; R hset h2 f1 "$(printf 'x%.0s' $(seq 1 65))"; R object encoding h2
# 4) 删回很小,看能否退回 listpack
R del h3; for i in $(seq 1 200); do R hset h3 f$i v$i >/dev/null; done; R object encoding h3
for i in $(seq 2 200); do R hdel h3 f$i >/dev/null; done; echo "hlen=$(R hlen h3)"; R object encoding h3
```

## 实机告诉我（跑完当天填）

```
<贴每步 OBJECT ENCODING 输出>
```

观察到的关键事实：

- ...

## ⚠️ 预期 vs 实机落差

- 我以为：……
- 实际：……
- 我学到：……

## 连到的面试卡

- `99-interview-cards/q-redis-encoding-transitions.md`
