# Scenario 02: Stream 消费组 —— 读 / PEL / ack / XAUTOCLAIM / trim

## 我想验证的问题

Stream 消费组里，消费者读了消息但**没 ack 就"崩了"**，消息会丢吗？另一个消费者能不能接管它？`XADD MAXLEN` 能不能限制流长度？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - 消费者 A `XREADGROUP` 读 2 条但不 `XACK`，`XPENDING` 显示未确认数 = _____。
> - A "崩了"后，消费者 B `XAUTOCLAIM` 能不能拿到 A 读了没 ack 的消息？_____
> - `XADD ... MAXLEN 10` 连发 100 条后 `XLEN` ≈ _____。
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R xadd mq '*' task t1; R xadd mq '*' task t2; R xadd mq '*' task t3
R xgroup create mq g1 0
# 消费者 A 读 2 条,不 ack(模拟处理中崩溃)
R xreadgroup group g1 A count 2 streams mq '>'
echo "XPENDING 未ack数 = $(R xpending mq g1 | head -1)"
# 消费者 B 接管 A 滞留的消息(min-idle-time=0 演示)
R xautoclaim mq g1 B 0 0
# ack 第一条
firstid=$(R xrange mq - + count 1 | head -1)
echo "XACK $firstid = $(R xack mq g1 $firstid)"
echo "剩余 XPENDING = $(R xpending mq g1 | head -1)"
# MAXLEN trim
for i in $(seq 1 100); do R xadd mq maxlen 10 '*' n $i >/dev/null; done
echo "XADD MAXLEN 10 连发100 后 XLEN = $(R xlen mq)"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
XPENDING 未ack数 = 2                              ← A 读了 2 条没 ack,都在 PEL
XAUTOCLAIM: B 拿到了 t1、t2 两条(A 的滞留消息)     ← 消费者接管,消息没丢
XACK <id1> = 1                                    ← 确认一条
剩余 XPENDING = 1
XADD MAXLEN 10 后 XLEN = 10                        ← trim 生效,流被裁到 10
```

观察到的关键事实：

- A `XREADGROUP` 读了 2 条但不 `XACK` → 这 2 条进 **PEL**，`XPENDING` 显示未确认数 = 2（**没丢**）。
- A "崩溃"后，B `XAUTOCLAIM mq g1 B 0 0` **接管**了 A 滞留的 t1、t2——这就是消费者故障后的**重投递/死信**机制。
- `XACK` 一条后 PEL 降到 1。
- `XADD MAXLEN 10` 连发 100 条，`XLEN` 稳在 10——trim 防止 Stream 无限增长。

## ⚠️ 预期 vs 实机落差

- 我以为：消费者读了消息就等于消费完了，崩了消息就没了（像 List `BRPOP`）。
- 实际:Stream 的「读」和「确认」是分开的——`XREADGROUP` 读走的消息进 **PEL** 等 `XACK`,**没 ack 就一直在**,消费者崩了别人能 `XAUTOCLAIM` 接管。这才是「可靠消费」:至少一次投递 + 故障接管。
- 我学到:(1) Stream ≈ Redis 版 Kafka 消费组:消费组分摊 + ack + PEL + 死信接管 + 回放。(2) **必须 `XACK`**,否则 PEL 越积越多;消费者崩溃靠 `XAUTOCLAIM`(配 min-idle-time)做重投递。(3) **必须 `MAXLEN`/`XTRIM`**,否则 Stream 无限涨成大 key(12 章)。(4) 这些 List/pub/sub 都没有——要可靠 MQ 就用 Stream。

## 连到的面试卡

- `99-interview-cards/q-redis-mq-pubsub-list-stream.md`
