# Scenario 01: pub/sub 丢消息 vs Stream 持久不丢

## 我想验证的问题

`PUBLISH` 一条消息到一个**没有订阅者**的频道，会怎样？同样的消息用 Stream（`XADD`）发，过后还能不能读到？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.1/§3.3，不要查）：
>
> - `PUBLISH news hello` 时没有订阅者，返回值（收到方数）= _____，消息还在吗？_____
> - `XADD mq * ...` 发 3 条后，`XLEN`= _____；过一会儿还能 `XRANGE` 读到吗？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
# pub/sub:无订阅者时发布
echo "PUBLISH 收到方数 = $(R publish news hello)"
# Stream:发 3 条,过后还能读
R xadd mq '*' task t1; R xadd mq '*' task t2; R xadd mq '*' task t3
echo "XLEN = $(R xlen mq)"
echo "XRANGE(回看): $(R xrange mq - + | tr '\n' ' ')"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
PUBLISH 收到方数 = 0          ← 没人订阅,消息直接丢,无处可查
XLEN = 3
XRANGE(回看): <id1> task t1 <id2> task t2 <id3> task t3   ← 持久,过后照样读
```

观察到的关键事实：

- `PUBLISH` 到无订阅者的频道返回 **0**（0 个接收者），消息**不存任何地方、直接丢**——pub/sub 是 fire-and-forget。
- `XADD` 的 3 条消息**持久**在 Stream 里，`XLEN=3`，过后还能 `XRANGE` 全部回看。

## ⚠️ 预期 vs 实机落差

- 我以为：发消息总会存一下，订阅者晚点也能收到。
- 实际:**pub/sub 完全不存**——发的那一刻谁在听谁收到,没订阅者就丢、订阅者掉线期间的也漏。Stream 则是**持久日志**,发了就在,可回看、可重放。
- 我学到:(1) pub/sub 只适合「实时广播、丢了无所谓」(通知/配置推送)。(2) 要「不丢、可重放、消费者掉线还能补」必须用 Stream(sc02)。(3) `PUBLISH` 的返回值是「当前收到的订阅者数」,可用来判断有没有人在听。

## 连到的面试卡

- `99-interview-cards/q-redis-mq-pubsub-list-stream.md`
